# I2C Bus Lock com Prioridade

## Problema

O Raspberry Pi 4 possui um barramento I2C (bus 1, GPIO2/GPIO3) compartilhado entre 3 dispositivos:

| Dispositivo | Endereço | Lib       | Thread         | Frequência |
|-------------|----------|-----------|----------------|------------|
| PCA9685     | 0x41     | busio     | RX Comandos    | até 100Hz  |
| BMI160      | 0x68     | smbus2    | Sensores       | 100Hz      |
| INA219      | 0x40     | smbus2    | Energia        | 10Hz       |

O PCA9685 controla 3 servos (steering canal 0, brake front canal 4, brake rear canal 8).

### Sintoma

Quando o client conecta e envia comandos STATE a 100Hz via UDP:
- Thread RX Comandos escreve no PCA9685 (steering + brake) a cada 10ms
- Thread Sensores lê BMI160 a cada 10ms
- Ambas acessam o bus I2C 1 **simultaneamente sem coordenação**
- BMI160 recebe `errno 5` (I/O Error) → retorna dados zerados
- Resultado: todos os dados de acelerômetro e giroscópio ficam zero

### Causa raiz

Não havia lock compartilhado no barramento I2C. Cada driver (smbus2 e busio) acessava o bus independentemente. Quando duas transações I2C colidem no mesmo bus físico, o kernel retorna erro de I/O.

## Solução: PriorityI2CLock

Implementamos um lock com **3 níveis de prioridade** ao invés de um `threading.Lock` simples. Threads de maior prioridade "furam a fila" quando o bus fica livre.

### Prioridades

| Prioridade | Valor | Dispositivos       | Justificativa                              |
|------------|-------|---------------------|--------------------------------------------|
| Alta       | 0     | Steering, Brake     | Controle do veículo, segurança crítica     |
| Média      | 1     | BMI160              | Dados de sensores para telemetria e FF     |
| Baixa      | 2     | INA219              | Monitoramento de energia (não-crítico)     |

### Funcionamento

```
Thread Steering (prioridade 0):   acquire(0) → escreve PCA9685 → release()
Thread BMI160 (prioridade 1):     acquire(1) → lê BMI160 → release()
Thread INA219 (prioridade 2):     acquire(2) → lê INA219 → release()
```

Quando múltiplas threads esperam pelo lock:
1. O lock é liberado
2. Threads de **menor valor** (maior prioridade) são acordadas primeiro
3. Se há thread prioridade 0 esperando, as de 1 e 2 continuam esperando
4. Se há thread prioridade 1 esperando, as de 2 continuam esperando

### Implementação

```python
class PriorityI2CLock:
    PRIORITY_HIGH = 0    # Steering, Brake
    PRIORITY_MEDIUM = 1  # BMI160
    PRIORITY_LOW = 2     # INA219

    def __init__(self):
        self._lock = threading.Lock()
        self._condition = threading.Condition(self._lock)
        self._waiting = [0, 0, 0]  # Contadores por prioridade
        self._busy = False

    def acquire(self, priority=1):
        with self._condition:
            self._waiting[priority] += 1
            while self._busy or any(self._waiting[p] > 0 for p in range(priority)):
                self._condition.wait()
            self._waiting[priority] -= 1
            self._busy = True

    def release(self):
        with self._condition:
            self._busy = False
            self._condition.notify_all()
```

## Bandwidth do I2C

O barramento I2C 1 do RPi 4 opera a **100 kbps** por padrão (pode ser configurado até 400 kbps em `/boot/config.txt`).

### Cálculo de uso

Uma transação I2C (1 dispositivo) = ~50 bits (addr + reg + data + ACK/start/stop):

| Operação               | Tamanho | Frequência | Bits/s  |
|------------------------|---------|------------|---------|
| BMI160 leitura (2x6B)  | ~120b   | 100Hz      | 12.000  |
| PCA9685 steering (1x)  | ~50b    | 100Hz      | 5.000   |
| PCA9685 brake (2x)     | ~100b   | 100Hz      | 10.000  |
| INA219 leitura          | ~50b    | 10Hz       | 500     |
| **Total**               |         |            | **27.500** |

**27.5 kbps de 100 kbps = 27.5%** de utilização do bus. O gargalo não é bandwidth, é **colisão temporal** (duas transações ao mesmo tempo).

## Otimizações adicionais

### Deduplicação de escritas

Os servos PCA9685 operam a 50Hz PWM. Escrita repetida com o mesmo valor é inútil. Cada manager mantém o último ângulo enviado e só faz I2C write quando a diferença é >= 0.1°:

```python
if self._last_servo_angle is None or abs(final_angle - self._last_servo_angle) >= 0.1:
    self.i2c_lock.acquire(priority=0)
    try:
        self.steering_servo.angle = final_angle
    finally:
        self.i2c_lock.release()
    self._last_servo_angle = final_angle
```

Quando o volante está parado, zero escritas I2C. Quando está em movimento ativo, escritas limitadas pela taxa real de mudança.

## Arquivos modificados

- `raspberry/main.py`: Cria `PriorityI2CLock` e passa para todos os managers
- `raspberry/bmi160_manager.py`: `acquire(priority=1)` em `_write_register`, `_read_register`, `_read_sensor_registers`
- `raspberry/steering_manager.py`: `acquire(priority=0)` em `set_steering_input` e `initialize`
- `raspberry/brake_manager.py`: `acquire(priority=0)` em `_apply_brake_to_servos` e `initialize`
- `raspberry/power_monitor_manager.py`: `acquire(priority=2)` em `_write_ina219_register` e `_read_ina219_register`
