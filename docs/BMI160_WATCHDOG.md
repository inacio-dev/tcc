# BMI160 Brown-Out Watchdog + Otimizações de Performance

## Problema 1: BMI160 zera permanentemente quando motor acelera

### Sintoma

Quando o throttle vai a 100% (motor RC 775 puxa alta corrente):
- BMI160 retorna `accel_data=[0, 0, 0, 0, 0, 0], gyro_data=[0, 0, 0, 0, 0, 0]`
- Os zeros persistem **indefinidamente** — o sensor nunca recupera
- Telemetria de acelerômetro e giroscópio fica completamente inoperante

### Causa raiz

O motor RC 775 causa **queda momentânea de tensão** (brown-out) no barramento de 3.3V do Raspberry Pi. O BMI160 faz um power-on reset e volta ao estado padrão: **suspend mode** (PMU = 0x00).

Em suspend mode, todos os registradores de dados retornam zero. Porém, a **comunicação I2C continua funcionando** — o sensor responde com dados válidos (zeros), então não há errno 5 nem timeout. O I2C lock com prioridade não resolve porque não é colisão de bus, é reset elétrico.

### Timeline do problema

```
t=0:   Motor idle, BMI160 lê normalmente [50, 249, 206, 245, 157, 62]
t=1:   Throttle 100% → motor puxa ~30A → tensão cai momentaneamente
t=2:   BMI160 faz brown-out reset → PMU volta para suspend (default)
t=3:   read_sensor_data() lê [0, 0, 0, 0, 0, 0] — I2C OK, dados zero
t=4+:  Zeros para sempre — nenhum código re-ativa o PMU
```

### Diferença: I2C collision vs brown-out

| Característica | I2C Collision (errno 5) | Brown-out (zeros) |
|----------------|------------------------|-------------------|
| I2C funciona?  | Não — retorna None      | Sim — retorna [0,0,...] |
| Lock resolve?  | Sim                     | Não |
| Sensor responde? | Não (NACK/timeout)   | Sim (ACK + dados zero) |
| Recupera sozinho? | Sim (retry)          | Não (precisa re-init PMU) |

## Solução: Watchdog de zeros consecutivos

### Implementação

Em `bmi160_manager.py`, adicionamos detecção de zeros consecutivos:

```python
# Inicialização
self._consecutive_zeros = 0
self._ZERO_THRESHOLD = 5  # Re-inicializa após 5 leituras zeradas

# Em read_sensor_data():
all_zero = all(b == 0 for b in accel_data) and all(b == 0 for b in gyro_data)
if all_zero:
    self._consecutive_zeros += 1
    if self._consecutive_zeros >= self._ZERO_THRESHOLD:
        self._rewake_sensor()
        return True  # Usa dados anteriores neste ciclo
else:
    self._consecutive_zeros = 0
```

### _rewake_sensor() — Recovery em 2 estágios

**Estágio 1: Re-ativa PMU (rápido, ~150ms)**
```python
# Re-ativa acelerômetro (CMD 0x11 = normal mode)
self._write_register(REG_CMD, CMD_ACC_SET_PMU_MODE)
time.sleep(0.010)
# Re-configura range e ODR
self._write_register(REG_ACC_RANGE, self.accel_range)
self._write_register(REG_ACC_CONF, acc_conf)

# Re-ativa giroscópio (CMD 0x15 = normal mode)
self._write_register(REG_CMD, CMD_GYR_SET_PMU_MODE)
time.sleep(0.080)  # Startup time do giroscópio conforme datasheet
# Re-configura range e ODR
self._write_register(REG_GYR_RANGE, self.gyro_range)
self._write_register(REG_GYR_CONF, gyr_conf)
```

**Estágio 2: Soft reset completo (se estágio 1 falhar, ~400ms)**
```python
self._write_register(REG_CMD, CMD_SOFT_RESET)
time.sleep(0.200)
# Re-ativa e re-configura tudo do zero
```

### Por que threshold = 5?

- 1-2 zeros podem ser glitch legítimo (vibração, ruído)
- 5 zeros consecutivos a 60Hz = ~83ms sem dados válidos
- Motor leva ~50ms para estabilizar corrente após aceleração
- 5 é conservador o suficiente para não triggerar falso positivo

## Problema 2: UI do client congela periodicamente

### Sintoma

A UI do client (Tkinter) congela por ~1-2s a cada poucos segundos, causando:
- Vídeo desaparece ("Sem Sinal" após 2s sem frame)
- Telemetria para de atualizar
- Sliders não respondem

### Causa raiz

O `process_queues()` (chamado a cada 100ms via `root.after()`) executava `update_hardware_effects()` que fazia **5 `upload_effect` ioctls** para o G923 a cada chamada, mesmo quando os valores não mudavam:

```
A cada 100ms (10x por segundo):
  → update_spring(75%)      → ioctl EVIOCSFF (bloqueante)
  → update_damper(50%)      → ioctl EVIOCSFF (bloqueante)
  → update_friction(30%)    → ioctl EVIOCSFF (bloqueante)
  → update_inertia(5%)      → ioctl EVIOCSFF (bloqueante)
  → update_periodic(40, 3%) → ioctl EVIOCSFF (bloqueante)
```

Cada ioctl pode levar 1-5ms no driver hid-logitech-hidpp. Com 5 chamadas, são 5-25ms de bloqueio da thread UI, 10x por segundo. Se o kernel ou o USB têm latência variável, isso pode acumular e causar frame drops.

### Solução: Deduplicação de uploads FF

Cache do último coeficiente enviado para cada efeito. Só faz ioctl quando o valor realmente muda:

```python
# Cache
self._last_spring_coeff = -1
self._last_damper_coeff = -1
self._last_friction_coeff = -1
self._last_inertia_coeff = -1
self._last_periodic_key = None
self._last_rumble_key = None

def update_spring(self, coefficient_pct):
    coeff = int(pct / 100.0 * 32767)
    if coeff == self._last_spring_coeff:
        return  # Nenhum ioctl!
    with self._ff_lock:
        self._update_condition_effect(...)
        self._last_spring_coeff = coeff
```

**Resultado**: quando sliders estão parados (99% do tempo), zero ioctls por ciclo. Redução de ~50 ioctls/s → 0.

## Problema 3: Auto-save bloqueia thread UI

### Sintoma

A cada 20s, o auto-save serializava 70+ deques × 10k elementos com `pickle.dump()` na thread principal do Tkinter, bloqueando processamento de pacotes UDP.

### Solução

1. **Snapshot rápido** sob lock (~5ms): `{k: list(v) for k, v in history.items()}`
2. **pickle.dump em thread background** (daemon): não bloqueia a UI
3. **Reset via `root.after(0, ...)`** de volta na thread UI (Tkinter não é thread-safe)
4. **sensor_display.export_history_fast()**: snapshot sob lock, I/O fora do lock

## Arquivos modificados

- `raspberry/bmi160_manager.py`: Watchdog de zeros + `_rewake_sensor()` (PMU recovery)
- `client/g923_manager.py`: Cache de coeficientes FF, dedup de uploads
- `client/console/logic/auto_save.py`: I/O em thread background
- `client/sensor_display.py`: Snapshot sob lock, pickle fora do lock
