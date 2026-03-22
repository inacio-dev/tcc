# Arquitetura Multi-Thread do Raspberry Pi

Documentação sobre a arquitetura de threads do sistema F1 Car no Raspberry Pi.

## Visão Geral

O sistema foi refatorado de um loop sequencial para uma arquitetura multi-thread, permitindo que cada componente opere de forma independente e em sua taxa ideal.

---

## Arquitetura Anterior (Sequencial)

```
Loop Principal (120Hz):
  1. Captura frame        (~10-20ms)
  2. Lê BMI160            (~1-2ms)
  3. Lê temperatura       (~1ms)
  4. Lê energia           (~1-2ms)
  5. Consolida dados      (~0.5ms)
  6. Envia UDP            (~1-2ms)
  7. Sleep                (~8ms)
```

**Problemas:**
- Câmera atrasa sensores
- Sensores atrasam envio
- Componente mais lento limita todo o sistema
- Latência acumulada

---

## Arquitetura Atual (Multi-Thread + Dual Port)

```
┌───────────────────────────────────────────────────────────────────┐
│                    F1 Car Multi-Thread                            │
├───────────────────────────────────────────────────────────────────┤
│  RASPBERRY PI                                                     │
│  ────────────                                                     │
│  Thread Câmera (60Hz)     ──► current_frame ──┐                   │
│  Thread Sensores (100Hz)  ──┬► current_sensor ─┼──► TX Rede ──┐   │
│                             └──────────────────┼──► UDP 9997 ─┼─┐ │
│  Thread Energia (10Hz)    ──► current_power ───┤              │ │ │
│  Thread Temperatura (1Hz) ──► current_temp ────┘              │ │ │
│                                                               │ │ │
│  Thread TX Vídeo (camera_fps Hz) ◄── frame + dados ──────────┘ │ │
│       │                                                         │ │
│       └──► UDP 9999 (Vídeo + Dados consolidados) ───────────────┘ │
│                                                                   │
│  Thread RX Comandos (daemon) ◄── UDP 9998 ◄── Cliente             │
└───────────────────────────────────────────────────────────────────┘

┌───────────────────────────────────────────────────────────────────┐
│  CLIENTE                                                          │
│  ───────                                                          │
│  Thread Principal      ◄── UDP 9999 ── Vídeo + Dados              │
│  Thread Fast Sensors   ◄── UDP 9997 ── BMI160 (100Hz)             │
│  Thread TX Comandos    ──► UDP 9998 ── Controles                  │
└───────────────────────────────────────────────────────────────────┘
```

### Portas UDP

| Porta | Direção | Conteúdo | Taxa |
|-------|---------|----------|------|
| 9999 | RPi → Cliente | Vídeo MJPEG + dados consolidados | ~60Hz |
| 9997 | RPi → Cliente | Sensores BMI160 (accel/gyro) | 100Hz |
| 9998 | Cliente → RPi | Comandos de controle | On-demand |

---

## Threads do Sistema

### Raspberry Pi

| Thread | Taxa | Função | Daemon |
|--------|------|--------|--------|
| `CameraThread` | 60Hz | Captura frames da OV5647 | Sim |
| `SensorThread` | 100Hz | Lê BMI160 + envia UDP 9997 | Sim |
| `PowerThread` | 10Hz | Lê ADS1115 + INA219 | Sim |
| `TempThread` | 1Hz | Lê DS18B20 | Sim |
| `VideoTXThread` | camera_fps Hz | Consolida e transmite UDP 9999 | Sim |
| `SensorTXThread` | sensor_rate Hz | Transmite sensores UDP 9997 | Sim |
| RX Comandos | - | Recebe comandos do cliente (9998) | Sim |

### Cliente

| Thread | Taxa | Função | Daemon |
|--------|------|--------|--------|
| Main Loop | ~60Hz | Recebe vídeo + dados (9999) | Não |
| `FastSensorThread` | 100Hz | Recebe sensores BMI160 (9997) | Sim |
| `CommandTX` | 100Hz | Envia STATE:s,t,b ao RPi | Sim |
| `SensorProcessing` | 100Hz | Cálculos + Force Feedback | Sim |
| `G923 Input` | ~1kHz | Lê eventos evdev do volante | Sim |
| `KeyWorker` | On-demand | Processa teclas M/N (gear shift) | Sim |

---

## Comunicação Entre Threads

### Dados Compartilhados

```python
# Lock principal para dados atuais
self.current_data_lock = threading.Lock()

# Dados protegidos pelo lock
self.current_frame = None
self.current_sensor_data = {}
self.current_power_data = {}
self.current_temp_data = {}
```

### Padrão de Escrita (Threads de Aquisição)

```python
def _sensor_thread_loop(self):
    while self.running:
        sensor_data = self.bmi160_mgr.get_sensor_data()

        with self.current_data_lock:
            self.current_sensor_data = sensor_data

        time.sleep(1.0 / self.sensor_rate)
```

### Padrão de Leitura (Thread TX) — Timing Compensado

Os loops TX usam timing compensado com `next_tick` para manter a taxa real precisa.
O padrão `time.sleep(interval)` simples causa drift porque não desconta o tempo de
processamento (ex: envio UDP leva ~2ms, ciclo real seria 12ms em vez de 10ms).

```python
def _network_tx_thread_loop(self):
    interval = 1.0 / self.camera_fps
    next_tick = time.monotonic()

    while self.running:
        with self.current_data_lock:
            frame_data = self.current_frame
            sensor_data = self.current_sensor_data.copy()

        self.network_mgr.send_frame_with_sensors(frame_data, sensor_data)

        next_tick += interval
        sleep_time = next_tick - time.monotonic()
        if sleep_time > 0:
            time.sleep(sleep_time)
        else:
            next_tick = time.monotonic()  # Reset se ficou muito atrasado
```

Este padrão é usado nos 3 loops TX: vídeo (RPi), sensores (RPi) e comandos (Client).

---

## Thread-Safety dos Managers

Cada manager tem seu próprio lock para proteger acesso concorrente:

### managers/motor.py

```python
self.state_lock = threading.Lock()

# Métodos protegidos:
- set_throttle()
- get_motor_status()
- shift_gear_up() / shift_gear_down()  # _shift_gear() executado dentro do lock
- _acceleration_loop()                  # Loop 100Hz roda sob state_lock
- emergency_stop()                      # Zera PWM sob state_lock
```

Nota: `brake_input` é escrito pelo main.py também sob `state_lock` para
consistência com a leitura em `_apply_f1_acceleration()`.

### managers/brake.py

```python
self.state_lock = threading.Lock()

# Métodos protegidos:
- set_brake_balance()
- apply_brake()   # Calcula ângulos sob state_lock, I2C FORA do lock
- get_brake_status()
```

**Lock ordering**: `apply_brake()` adquire `state_lock` para calcular ângulos,
copia os valores, libera o lock, e só então faz as escritas I2C. Isso evita que
a thread TX fique bloqueada esperando o I2C lock enquanto segura o `state_lock`.

### managers/steering.py

```python
self.state_lock = threading.Lock()

# Métodos protegidos:
- set_steering_input()
- get_steering_status()
```

Nota: `cleanup()` NÃO chama `pca9685.deinit()` — o brake_manager é responsável
por desligar o PCA9685 compartilhado (endereço 0x41), pois é o último no cleanup.

### managers/bmi160.py

```python
self.state_lock = threading.Lock()

# Métodos protegidos:
- read_sensor_data()
- get_sensor_data()
```

### managers/power_monitor.py

```python
self.state_lock = threading.Lock()

# Métodos protegidos:
- get_sensor_data()
```

### managers/network.py (RPi)

```python
self.clients_lock = threading.Lock()

# Métodos protegidos:
- _send_to_client()      # Adquire clients_lock
- _send_to_client_unlocked()  # Versão sem lock para uso interno
```

Nota: `cleanup()` usa `_send_to_client_unlocked()` para evitar deadlock, pois
já segura `clients_lock` quando precisa enviar mensagem de desconexão.

### Outros managers com locks:

- `managers/camera.py` → `self.lock`
- `managers/temperature.py` → `self.thread_lock` + `deque(maxlen=)` para histórico
- `managers/logger.py` → `last_log_times` limitado a 500 entries (auto-cleanup)

---

## Fluxo de Dados

### Raspberry Pi: Aquisição → Transmissão

```
BMI160 ──► SensorThread ──┬► current_sensor_data ──┐
                          │                        │
                          └──► send_fast_sensors() ──► UDP 9997 (100Hz)
                                                   │
OV5647 ──► CameraThread ──► current_frame ─────────┼──► VideoTXThread ──► UDP 9999 (60Hz)
ADS1115 ─► PowerThread ──► current_power_data ─────┤
DS18B20 ─► TempThread ──► current_temp_data ───────┘
```

### Cliente: Recepção

```
UDP 9999 ──► Main Loop ──────────► Vídeo + Dados consolidados
UDP 9997 ──► FastSensorThread ──► Sensores BMI160 (100Hz)
```

### Comandos → Atuadores

```
Cliente ──► UDP 9998 ──► RX Comandos ──► command_callback ──┬──► motor_mgr.set_throttle()
                                                            ├──► brake_mgr.apply_brake()
                                                            └──► steering_mgr.set_steering_input()
```

---

## Benefícios da Arquitetura

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Câmera | Bloqueava sensores | Independente |
| Sensores BMI160 | ~60Hz (junto com vídeo) | 100Hz real (porta dedicada) |
| Latência de sensores | ~33ms (espera frame) | ~10ms (envio direto) |
| Falhas | Afetavam todo sistema | Isoladas |
| Escalabilidade | Difícil | Fácil adicionar threads |
| Force Feedback | Dados atrasados | Tempo real 100Hz |

---

## Execução

```bash
# Modo normal
cd ~/tcc/raspberry && python3 main.py

# Modo debug (verbose)
python3 main.py --debug

# Parâmetros customizados
python3 main.py --fps 60 --sensor-rate 100
```

---

## Estatísticas em Runtime

O sistema exibe estatísticas a cada 10 segundos:

```
STATS: 120s | 29.8fps | 99Hz | 118pps | 8/8 online
```

- `fps`: Frames por segundo (câmera)
- `Hz`: Taxa de sensores BMI160
- `pps`: Pacotes por segundo (rede)
- `online`: Componentes ativos

---

## Tratamento de Erros

Cada thread tem tratamento de exceção independente:

```python
def _sensor_thread_loop(self):
    while self.running:
        try:
            # ... código ...
        except Exception as e:
            warn(f"Erro na thread de sensores: {e}", "BMI160", rate_limit=5.0)
            time.sleep(0.01)  # Evita loop infinito em caso de erro
```

---

## Shutdown Coordenado

O sistema para de forma ordenada:

1. Define `self.running = False`
2. Aguarda cada thread finalizar (timeout 2s)
3. Para componentes na ordem inversa de dependência
4. Libera recursos (GPIO, I2C, sockets)

```python
def stop(self):
    self.running = False

    # Aguarda threads
    for name, thread in threads:
        if thread and thread.is_alive():
            thread.join(timeout=2.0)

    # Para componentes
    for name, component in components:
        if component:
            component.cleanup()
```

---

## Arquivos Relacionados

### Raspberry Pi

- `raspberry/main.py` - Orquestrador multi-thread
- `raspberry/managers/network.py` - Rede UDP (3 portas: 9999, 9998, 9997)
- `raspberry/managers/motor.py` - Controle do motor (thread-safe)
- `raspberry/managers/brake.py` - Controle de freios (thread-safe)
- `raspberry/managers/steering.py` - Controle de direção (thread-safe)
- `raspberry/managers/bmi160.py` - Sensor IMU (thread-safe)
- `raspberry/managers/power_monitor.py` - Monitor de energia (thread-safe)
- `raspberry/managers/camera.py` - Câmera (thread-safe)
- `raspberry/managers/temperature.py` - Temperatura (thread-safe)

### Cliente

- `client/network_client.py` - Cliente UDP multi-thread (2 portas: 9999, 9997)
- `client/main.py` - Orquestrador principal
- `client/sensor_display.py` - Processamento de sensores

---

## Formato dos Pacotes

### Porta 9999 (Vídeo + Dados)

```
| 4 bytes    | 4 bytes     | N bytes    | M bytes      |
| frame_size | sensor_size | frame_data | sensor_json  |
```

### Porta 9997 (Sensores Rápidos)

```
| 4 bytes     | N bytes      |
| sensor_size | sensor_json  |
```

---

## Data

- **Implementação inicial**: 2025-12-17
- **Atualização (dual-port)**: 2025-12-17
- **Correções de race conditions e timing**: 2026-03-22
- **Status**: Produção
