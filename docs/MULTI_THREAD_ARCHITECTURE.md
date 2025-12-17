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

## Arquitetura Atual (Multi-Thread)

```
┌─────────────────────────────────────────────────────────────┐
│                    F1 Car Multi-Thread                      │
├─────────────────────────────────────────────────────────────┤
│  Thread Câmera (30Hz)     ──┐                               │
│  Thread Sensores (100Hz)  ──┼──► current_data (Lock) ──┐    │
│  Thread Energia (10Hz)    ──┤                          │    │
│  Thread Temperatura (1Hz) ──┘                          │    │
│                                                        ▼    │
│  Thread TX Rede (120Hz)  ◄── Consolida ◄── Lê dados ───┘    │
│       │                                                     │
│       └──► UDP ──► Cliente                                  │
│                                                             │
│  Thread RX Comandos (daemon) ◄── UDP ◄── Cliente            │
└─────────────────────────────────────────────────────────────┘
```

---

## Threads do Sistema

| Thread | Taxa | Função | Daemon |
|--------|------|--------|--------|
| `CameraThread` | 30Hz | Captura frames da OV5647 | Sim |
| `SensorThread` | 100Hz | Lê BMI160 (accel/gyro) | Sim |
| `PowerThread` | 10Hz | Lê ADS1115 + INA219 | Sim |
| `TempThread` | 1Hz | Lê DS18B20 | Sim |
| `NetworkTXThread` | 120Hz | Consolida e transmite UDP | Sim |
| RX Comandos | - | Recebe comandos do cliente | Sim |

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

### Padrão de Leitura (Thread TX)

```python
def _network_tx_thread_loop(self):
    while self.running:
        with self.current_data_lock:
            frame_data = self.current_frame
            sensor_data = self.current_sensor_data.copy()

        self.network_mgr.send_frame_with_sensors(frame_data, sensor_data)
        time.sleep(1.0 / 120.0)
```

---

## Thread-Safety dos Managers

Cada manager tem seu próprio lock para proteger acesso concorrente:

### motor_manager.py

```python
self.state_lock = threading.Lock()

# Métodos protegidos:
- set_throttle()
- get_motor_status()
- shift_gear_up()
- shift_gear_down()
```

### brake_manager.py

```python
self.state_lock = threading.Lock()

# Métodos protegidos:
- set_brake_balance()
- apply_brake()
- get_brake_status()
```

### steering_manager.py

```python
self.state_lock = threading.Lock()

# Métodos protegidos:
- set_steering_input()
- get_steering_status()
```

### bmi160_manager.py

```python
self.state_lock = threading.Lock()

# Métodos protegidos:
- read_sensor_data()
- get_sensor_data()
```

### power_monitor_manager.py

```python
self.state_lock = threading.Lock()

# Métodos protegidos:
- get_sensor_data()
```

### Managers que já tinham locks:

- `camera_manager.py` → `self.lock`
- `temperature_manager.py` → `self.thread_lock`
- `network_manager.py` → `self.clients_lock`

---

## Fluxo de Dados

### Aquisição → Transmissão

```
BMI160 ──► SensorThread ──► current_sensor_data ──┐
OV5647 ──► CameraThread ──► current_frame ────────┼──► NetworkTXThread ──► UDP
ADS1115 ─► PowerThread ──► current_power_data ────┤
DS18B20 ─► TempThread ──► current_temp_data ──────┘
```

### Recepção → Atuadores

```
UDP ──► RX Comandos ──► command_callback ──┬──► motor_mgr.set_throttle()
                                           ├──► brake_mgr.apply_brake()
                                           └──► steering_mgr.set_steering_input()
```

---

## Benefícios da Arquitetura

| Aspecto | Antes | Depois |
|---------|-------|--------|
| Câmera | Bloqueava sensores | Independente |
| Sensores BMI160 | ~60Hz real | 100Hz real |
| Latência | Acumulada | Mínima |
| Falhas | Afetavam todo sistema | Isoladas |
| Escalabilidade | Difícil | Fácil adicionar threads |

---

## Execução

```bash
# Modo normal
cd ~/tcc/raspberry && python3 main.py

# Modo debug (verbose)
python3 main.py --debug

# Parâmetros customizados
python3 main.py --fps 30 --sensor-rate 100
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

- `raspberry/main.py` - Orquestrador multi-thread
- `raspberry/motor_manager.py` - Controle do motor (thread-safe)
- `raspberry/brake_manager.py` - Controle de freios (thread-safe)
- `raspberry/steering_manager.py` - Controle de direção (thread-safe)
- `raspberry/bmi160_manager.py` - Sensor IMU (thread-safe)
- `raspberry/power_monitor_manager.py` - Monitor de energia (thread-safe)
- `raspberry/camera_manager.py` - Câmera (já era thread-safe)
- `raspberry/temperature_manager.py` - Temperatura (já era thread-safe)
- `raspberry/network_manager.py` - Rede UDP (já era thread-safe)

---

## Data

- **Implementação**: 2025-12-17
- **Status**: Produção
