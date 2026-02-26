# CLAUDE.md

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║                           ⚠️  AVISO CRÍTICO  ⚠️                               ║
║                                                                               ║
║   Este arquivo NÃO DEVE EXCEDER 40.000 CARACTERES (40k chars)               ║
║                                                                               ║
║   Tamanho Atual: ~13k chars                                                  ║
║   Limite Máximo: 40k chars                                                   ║
║   Impacto se exceder: Performance degradada do Claude Code                   ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

F1-style remote-controlled car with complete telemetry system using Raspberry Pi 4 (8GB RAM), Logitech G923 racing wheel, and client application. Captures video, sensor data, and vehicle control via UDP.

## Architecture

### System Components

**Raspberry Pi Side (`raspberry/`):**

- `main.py`: Orchestrates all hardware
- `camera_manager.py`: OV5647 camera + MJPEG video encoding
- `bmi160_manager.py`: IMU sensor (accel/gyro) data
- `motor_manager.py`: RC 775 motor + 5-speed transmission
- `brake_manager.py`: Dual servo brake (front/rear)
- `steering_manager.py`: Direct servo steering (0°-180°)
- `network_manager.py`: UDP transmission
- `power_monitor_manager.py`: Energy monitoring (Pro Micro USB + INA219)

**Client Side (`client/`):**

- `main.py`: Main orchestrator
- `network_client.py`: UDP receiver (filters by configured IP)
- `g923_manager.py`: Logitech G923 wheel input (evdev) + force feedback
- `video_display.py`: MJPEG video rendering (OpenCV)
- `console_interface.py`: UI with instrument panel + auto-save
- `sensor_display.py`: Sensor data processing + history
- `keyboard_controller.py`: Async keyboard input
- `slider_controller.py`: Control sliders + G923 axis calibration

### Hardware Configuration

**Current Setup:**

- **Vehicle**: Raspberry Pi 4B (8GB), OV5647 camera, BMI160 IMU, RC 775 motor, 3x MG996R servos
- **Simulador**: Logitech G923 racing wheel (steering 900°, pedals, paddle shifters, force feedback nativo via evdev)
- **Monitoramento de energia**: Arduino Pro Micro (ATmega32U4) via USB Serial + INA219 I2C
- **Network**: mDNS (RPi: `f1car.local`, Client: `f1client.local`)

**Raspberry Pi 4 Pinout:**

- Camera OV5647 → CSI slot
- BMI160 (I2C) → GPIO2/3 (SDA/SCL), Address: 0x68
- INA219 (I2C) → GPIO2/3 (shared), Address: 0x40 (padrão)
- PCA9685 PWM (I2C) → GPIO2/3 (shared), Address: 0x41 (A0 soldado)
- Arduino Pro Micro → USB Serial (115200 baud)
- Motor BTS7960: RPWM→GPIO18, LPWM→GPIO27, R_EN→GPIO22, L_EN→GPIO23

**Power Monitoring (Pro Micro channels):**

- A0: Divisor de tensão 20kΩ/10kΩ → Tensão bateria 3S LiPo
- A1: ACS758 50A → UBEC current (Servos) - high-side
- A2: ACS758 100A → Motor DC 775 current - high-side

**Arduino Pro Micro (ATmega32U4) Pinout:**

- A0: Divisor de tensão (20kΩ/10kΩ) → Tensão bateria 3S LiPo
- A1: ACS758 50A OUT → Corrente Servos/UBEC (high-side)
- A2: ACS758 100A OUT → Corrente Motor DC 775 (high-side)
- VCC: 5V para ACS758 (ratiométrico)
- USB: Serial CDC → Raspberry Pi 4

**Logitech G923 (evdev Linux):**

- ABS_X → Steering (volante, ~0-65535) → mapeia para -100 a +100
- ABS_RZ → Throttle (acelerador, invertido) → mapeia para 0 a 100
- ABS_Z → Brake (freio, invertido) → mapeia para 0 a 100
- BTN_GEAR_UP (711) → Paddle direito → GEAR_UP
- BTN_GEAR_DOWN (710) → Paddle esquerdo → GEAR_DOWN
- FF_CONSTANT → Force feedback direcional via evdev

## Network Configuration (mDNS)

### Setup

**Raspberry Pi:**
```bash
sudo hostnamectl set-hostname f1car
# Add "127.0.1.1 f1car" to /etc/hosts
sudo systemctl restart avahi-daemon
```

**Client (Arch Linux):**
```bash
sudo pacman -S avahi nss-mdns
sudo hostnamectl set-hostname f1client
# Add "127.0.1.1 f1client" to /etc/hosts
# Add "mdns_minimal [NOTFOUND=return]" to hosts line in /etc/nsswitch.conf
sudo systemctl enable --now avahi-daemon
```

### Network Protocol

- **mDNS UDP**: RPi (`f1car.local:9999/9998`) ↔ Client (`f1client.local`)
- **Ports**: 9999 (data), 9998 (commands)
- **IP Filtering**: Client only accepts packets from configured RPi IP
- **Commands**: CONNECT, DISCONNECT, PING, CONTROL:THROTTLE/BRAKE/STEERING/BRAKE_BALANCE/GEAR_UP/GEAR_DOWN

## Auto-Save System

### Features

- **Periodic save**: Every 20 seconds (if data available)
- **Minimum threshold**: 10 logs OR 100 sensor readings
- **Auto-reset**: Clears console and sensor history after save
- **Directory**: `exports/auto/`

### File Formats

- **Logs**: `logs_YYYYMMDD_HHMMSS.txt` (plain text)
- **Sensors**: `sensors_YYYYMMDD_HHMMSS.pkl` (Python Pickle - faster than CSV)

### Reading Pickle Files

```python
import pickle
with open("sensors_20241216_143000.pkl", "rb") as f:
    data = pickle.load(f)
# data is a dict with all sensor lists
```

## Development Commands

### Environment Setup

**Raspberry Pi:**

```bash
sudo raspi-config  # Enable Camera, I2C, SPI
sudo apt update && sudo apt install build-essential python3-dev libcap-dev libcamera-apps python3-libcamera python3-opencv python3-numpy python3-picamera2
pip install -r requirements.txt
```

**Client:**

```bash
cd client
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# Permissão para evdev (G923): sudo usermod -a -G input $USER
```

**Arduino Pro Micro:**

```bash
# Arduino IDE: Board → Arduino Micro → Upload pro_micro/pro_micro.ino
# Conectar via USB ao Raspberry Pi (detectado como /dev/serial/by-id/usb-Arduino_LLC_Arduino_Micro-if00)
```

### Running the System

```bash
# Raspberry Pi
cd raspberry && python3 main.py

# Client
cd client && python3 main.py --port 9999
```

## Key Dependencies

- **opencv-python**: Video processing and MJPEG decoding
- **numpy**: Sensor computations
- **evdev**: G923 input reading + force feedback (Linux)
- **picamera2**: Raspberry Pi camera
- **Pillow**: Image processing
- **smbus2**: I2C communication
- **adafruit-circuitpython-pca9685**: PCA9685 PWM driver
- **adafruit-circuitpython-servokit**: Servo control

## Hardware Control

- **Motor**: RC 775 with 5-speed manual transmission, F1-style efficiency zones
- **Servos**: PCA9685-based (Channel 0: front brake, 1: rear brake, 2: steering)
- **Brake Balance**: Default 60% front / 40% rear
- **BMI160**: 100Hz sampling, event detection (curves, braking, impacts)

## Client Interface Features

- **Instrument Panel**: RPM, gear, throttle, speed
- **Telemetry**: BMI160 data, G-forces, vehicle dynamics
- **Async Keyboard**: WASD/Arrows (20Hz), M/N (gear shifts)
- **Video Display**: Embedded Tkinter with MJPEG decoding
- **Auto-Save**: Automatic data export every 20s
- **2-Column Layout**: Left (telemetry), Right (video/controls)

## Control Methods

**1. Keyboard (Fallback):**

- W/↑: Throttle 100%, S/↓: Brake 100%, A/←: Left, D/→: Right, M: Gear Up, N: Gear Down

**2. Logitech G923 (Primary):**

- Steering wheel 900° rotation
- Progressive throttle/brake pedals
- Paddle shifters (gear up/down)
- 7-effect force feedback via evdev (spring/damper/friction/inertia + constant + rumble + periodic)
- Auto-detection via evdev (busca "G923" ou "Driving Force" em /dev/input/event*)

## G923 Integration

### Axis Calibration System

- User clicks "Calibrar" for a specific axis (Throttle, Brake, Steering)
- Moves the axis through its full physical range
- System records raw min/max from evdev values
- On save: updates G923Manager ranges + persists to `g923_calibration.json`
- Calibration loaded and applied automatically on startup

### G923 to Interface Synchronization

**IMPORTANT**: g923_manager must update client interface in real-time via command_callback:

- G923 steering → command_callback("STEERING", "-30") → update interface
- G923 throttle → command_callback("THROTTLE", "75") → update interface
- G923 brake → command_callback("BRAKE", "50") → update interface
- G923 paddle → command_callback("GEAR_UP"/"GEAR_DOWN", "") → update gear display

## Force Feedback System

### Architecture (7-Effect Multi-Effect)

```
Condition effects (kernel ~1kHz):
  FF_SPRING    ← centering (Sensitivity slider, mín 5%)
  FF_DAMPER    ← amortecimento (Damping slider)
  FF_FRICTION  ← grip do pneu (Friction slider, mín 3%)
  FF_INERTIA   ← peso do volante (auto: velocidade/throttle, 5-80%)

Force effects (software, a cada pacote BMI160):
  FF_CONSTANT  ← G lateral + yaw → empurra volante

Vibration effects:
  FF_RUMBLE    ← impactos/estrada (accel_z + accel_x → strong + weak motor)
  FF_PERIODIC  ← engine RPM (throttle → 25-50Hz sine wave)

Idle (sempre ativo): spring 5%, friction 3%, inertia 5%, periodic 25Hz/3%
```

### Adjustable Parameters → Hardware Effects

- **Sensitivity** (default 75%): FF_SPRING coefficient + FF_CONSTANT multiplier
- **Friction** (default 30%): FF_FRICTION coefficient (mín 3%)
- **Damping** (default 50%): FF_DAMPER coefficient
- **Filter** (default 40%): Software EMA on FF_CONSTANT only
- **Max Force** (default 15%): FF_GAIN global (limits ALL 7 effects)

### evdev FF Protocol

```python
# Condition effects (slider-based):
# g923_manager.update_spring(pct)    → FF_SPRING (mín 5%)
# g923_manager.update_damper(pct)    → FF_DAMPER
# g923_manager.update_friction(pct)  → FF_FRICTION (mín 3%)

# Dynamic effects (sensor-based, updated per BMI160 packet):
# g923_manager.apply_constant_force(intensity, direction) → FF_CONSTANT
# g923_manager.update_rumble(strong_pct, weak_pct)        → FF_RUMBLE
# g923_manager.update_periodic(period_ms, magnitude_pct)  → FF_PERIODIC
# g923_manager.update_inertia(coefficient_pct)             → FF_INERTIA

# Global safety limit:
# g923_manager.set_ff_max_percent(pct) → FF_GAIN (0-0xFFFF)
```

## Important Files

**Documentation:**

- `raspberry/MODULOS.md`: Technical specifications of all hardware modules
- `raspberry/DIAGRAMA.drawio.pdf`: Complete electrical diagram
- `datasheets/`: Component datasheets (BTS7960, etc.) for detailed technical reference

**Monografia (`monografia/`):**

- Template LaTeX UFCTeX (abnTeX2) para trabalhos acadêmicos da UFC
- `documento.tex`: Arquivo principal que inclui todos os capítulos
- `lib/preambulo.tex`: Configurações de pacotes e formatação
- `lib/ufctex.sty`: Customizações do template
- `2-textuais/`: Capítulos da monografia:
  - `1-introducao.tex`: Introdução, justificativa e objetivos
  - `2-fundamentacao-teorica.tex`: Revisão de literatura (54 artigos)
  - `3-metodologia.tex`: Arquitetura, algoritmos e especificações
  - `4-resultados.tex`: Métricas, benchmarks e análise estatística
  - `4.5-discussao.tex`: Interpretação teórica e implicações
  - `5-conclusao.tex`: Conclusões e trabalhos futuros
- Compilação: `make compile` (requer texlive + abntex2)
- Verificação: `chktex documento.tex` (warnings suprimidos em `.chktexrc`)
- **IMPORTANTE - Citações**: Usar o comando correto conforme o contexto:
  - **Em texto corrido**: Usar `\citeonline{chave}` → "Dreger e Rinkenauer (2024)"
  - **Em tabelas**: Usar `\cite{chave}` → "(DREGER; RINKENAUER, 2024)" - mais compacto
  - Exemplo texto: `\citeonline{dreger2024evaluation}` → "Dreger e Rinkenauer (2024)"
  - Exemplo tabela: `Sensor BMI160 \cite{bosch2015bmi160}` → "Sensor BMI160 (BOSCH, 2015)"
- **IMPORTANTE - Edição**: Ao editar a monografia, SEMPRE ler o arquivo primeiro e seguir o padrão já estabelecido:
  - Manter o estilo de escrita, tom e vocabulário existente
  - Seguir a estrutura de seções e subseções já definida
  - Respeitar a formatação LaTeX utilizada (comandos, ambientes, macros)
  - Manter consistência com as convenções de nomenclatura técnica
- **IMPORTANTE - Referências**: Ao citar artigos na monografia:
  1. Primeiro consultar os arquivos JSON em `artigos/artigos_part*.json` para obter os dados do artigo
  2. Depois verificar a chave BibTeX correspondente em `monografia/3-pos-textuais/referencias.bib`
  3. Usar a chave exata do BibTeX com `\citeonline{chave}`
- **IMPORTANTE - Listas LaTeX**: NUNCA usar o padrão `\begin{itemize}` com `\item \textbf{Título}: descrição` na monografia. Este formato é visualmente poluído e não segue boas práticas acadêmicas. Preferir SEMPRE texto corrido em formato de parágrafo.
- **IMPORTANTE - Evitar Redundâncias**: Ao editar a monografia, evitar repetições de informações entre capítulos:
  - Detalhes técnicos de citações (ex: "1,33ms", "16 sensores") devem aparecer com detalhes APENAS na Fundamentação Teórica
  - Em outros capítulos, apenas referenciar: "conforme \citeonline{autor}" sem repetir os dados numéricos
  - Não duplicar equações entre capítulos (ex: equação de suavização)
  - Não duplicar labels de seções/subseções (verificar com grep antes de criar)
  - Valores como custos devem ser consistentes em todo o documento
  - Verificar se uma informação já foi dita antes de adicioná-la novamente
  - Formato da chave: `sobrenome_primeiro_autor+ano+palavra_chave` (ex: `dreger2024evaluation`)
- **IMPORTANTE - Nomenclatura do Projeto**:
  - NUNCA usar "carrinho" ou "carro" para se referir ao projeto. SEMPRE usar "veículo" ou "veículo teleoperado" para manter o tom acadêmico e profissional da monografia. Exceção: quando se refere a "carros de F1 reais" ou "modelo de carro de Fórmula 1" (chassi) é aceitável.
  - NUNCA usar "cockpit" para se referir ao sistema de controle. SEMPRE usar "simulador" que representa o volante e os pedais (acelerador e freio). O termo "cockpit" é inadequado pois o projeto não possui uma cabine completa, apenas os controles de direção.

**Client:**

- `client/main.py`: Primary application
- `client/console_interface.py`: Main GUI + auto-save
- `client/network_client.py`: UDP receiver with IP filtering
- `client/video_display.py`: MJPEG decoder
- `client/sensor_display.py`: Sensor processing + pickle export

**Raspberry Pi:**

- `raspberry/main.py`: Primary application
- `raspberry/bmi160_manager.py`: IMU sensor manager
- `raspberry/power_monitor_manager.py`: Energy monitoring (Pro Micro USB + INA219 I2C)

**Arduino Pro Micro (`pro_micro/`):**

- `pro_micro.ino`: ADC reading (bateria + 2x ACS758) + USB Serial to RPi

## Configuration

**Raspberry Pi Parameters:**

- `--port`: UDP port (default: 9999)
- `--fps`: Camera FPS (default: 30)
- `--sensor-rate`: Sensor Hz (default: 100)
- `--brake-balance`: Front % (default: 60)

**Client Parameters:**

- `--port`: UDP port (default: 9999)
- `--buffer`: Buffer KB (default: 128)
- `--debug`: Verbose logging

## Hardware Datasheets (Summary)

### BMI160 IMU Sensor

- 6-axis (3-axis accel + 3-axis gyro), 16-bit resolution
- I2C address: 0x68 (SAO=GND) or 0x69 (SAO=VDD)
- Accel ranges: ±2g/±4g/±8g/±16g
- Gyro ranges: ±125°/s to ±2000°/s
- Recommended: ±4g accel, ±500°/s gyro, 100Hz sampling

### MG996R Servo Motor

- High-torque digital servo, 180° rotation
- Operating voltage: 4.8V-7.2V
- Torque: 9.4 kg⋅cm (4.8V), 11 kg⋅cm (6V)
- PWM: 50Hz, 1ms-2ms pulse width

### PCA9685 PWM Driver

- 16-channel, 12-bit resolution (4096 steps)
- I2C address: 0x41 (A0 soldado, evita conflito com INA219 em 0x40)
- F1 Car channels: 0 (front brake), 1 (rear brake), 2 (steering)

### BTS7960 H-Bridge (Motor principal no veículo)

- 43A continuous current capacity
- Operating voltage: 6V-27V
- PWM control: 1kHz, 8-bit
- RPi pinout: RPWM→GPIO18, LPWM→GPIO27, R_EN→GPIO22, L_EN→GPIO23

## Code Optimization

- Direct hardware control (no smooth movement threads)
- Clean codebase (no unused code)
- F1-style efficiency zones
- Optimized video pipeline (MJPEG + frame dropping)
- Thread-safe operations with `root.after()`
- Auto-save with Pickle (5-10x faster than CSV)

## Error Handling

- Graceful hardware degradation
- Comprehensive logging
- Clean shutdown with `os._exit(0)` (avoids Tcl_AsyncDelete error)
- I2C timing optimization (5ms delays)
- Null safety for sensor readings
