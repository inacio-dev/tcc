# CLAUDE.md

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║                           ⚠️  AVISO CRÍTICO  ⚠️                               ║
║                                                                               ║
║   Este arquivo NÃO DEVE EXCEDER 40.000 CARACTERES (40k chars)               ║
║                                                                               ║
║   Tamanho Atual: ~35k chars                                                  ║
║   Limite Máximo: 40k chars                                                   ║
║   Impacto se exceder: Performance degradada do Claude Code                   ║
║                                                                               ║
║   ANTES DE ADICIONAR CONTEÚDO:                                               ║
║   1. Verifique o tamanho atual do arquivo (wc -c CLAUDE.md)                 ║
║   2. Se próximo do limite, REMOVA informações menos críticas                ║
║   3. Priorize informações de arquitetura e configuração                      ║
║   4. Detalhes técnicos extensos devem ir em arquivos separados              ║
║                                                                               ║
╚═══════════════════════════════════════════════════════════════════════════════╝
```

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

F1-style remote-controlled car with complete telemetry system using Raspberry Pi 4 (8GB RAM), ESP32 cockpit, and client application. Captures video, sensor data, and vehicle control via UDP.

## Architecture

### System Components

**Raspberry Pi Side (`raspberry/`):**

- `main.py`: Orchestrates all hardware
- `camera_manager.py`: OV5647 camera + video encoding
- `bmi160_manager.py`: IMU sensor (accel/gyro) data
- `motor_manager.py`: RS550 motor + 5-speed transmission
- `brake_manager.py`: Dual servo brake (front/rear)
- `steering_manager.py`: Direct servo steering (0°-180°)
- `network_manager.py`: UDP transmission
- `power_monitor_manager.py`: Energy monitoring (ADS1115 + INA219)

**Client Side (`codigo/client/`):**

- `main.py`: Main orchestrator
- `network_client.py`: UDP receiver
- `serial_receiver_manager.py`: ESP32 cockpit receiver
- `video_display.py`: Video rendering
- `console_interface.py`: UI with instrument panel
- `keyboard_controller.py`: Async keyboard input
- `calibration_manager.py`: Encoder calibration
- `slider_controller.py`: Control sliders + calibration UI

**ESP32 Cockpit (`codigo/esp32/`):**

- `esp32.ino`: Dual-core orchestrator
- `throttle_manager.h/cpp`: LPD3806-600BM-G5-24C encoder (600 PPR)
- `brake_manager.h/cpp`: LPD3806-600BM-G5-24C encoder
- `steering_manager.h/cpp`: LPD3806-600BM-G5-24C encoder
- `gear_manager.h/cpp`: Push button gear controls
- `serial_sender_manager.h/cpp`: USB serial transmission
- `ff_motor_manager.h/cpp`: BTS7960 force feedback motor
- `encoder_calibration.h/cpp`: Generic calibration with EEPROM

### Hardware Configuration

**Current Setup:**

- **Vehicle**: Raspberry Pi 4B (8GB), OV5647 camera, BMI160 IMU, RS550 motor, 3x MG996R servos
- **Cockpit**: ESP32 DevKit V1 (240MHz dual-core), 3x rotary encoders (600 PPR), 2x buttons, BTS7960 H-bridge
- **Network**: Fixed IPs (RPi: 192.168.5.33, Client: 192.168.5.11)
- **Serial**: ESP32→Client via USB (115200 baud, 100Hz)

**Raspberry Pi 4 Pinout:**

- Camera OV5647 → CSI slot
- BMI160 (I2C) → GPIO2/3 (SDA/SCL), Address: 0x68
- PCA9685 PWM (I2C) → GPIO2/3 (shared), Address: 0x40
- ADS1115 ADC (I2C) → GPIO2/3 (shared), Address: 0x48
- INA219 (I2C) → GPIO2/3 (shared), Address: 0x41 (A0=VCC, evita conflito com PCA9685)
- Motor BTS7960: RPWM→GPIO18, LPWM→GPIO27, R_EN→GPIO22, L_EN→GPIO23

**Power Monitoring (ADS1115 channels):**

- A0: ACS758 50A → XL4015 current (Raspberry Pi)
- A1: ACS758 50A → UBEC current (Servos)
- A2: ACS758 100A → Motor DC 775 current

**ESP32 DevKit V1 Pinout:**

- **Throttle Encoder**: GPIO 25 (CLK), GPIO 26 (DT) - **PINS SWAPPED** (white→CLK, green→DT) for correct increasing direction
- **Brake Encoder**: GPIO 27 (CLK), GPIO 14 (DT)
- **Steering Encoder**: GPIO 12 (CLK), GPIO 13 (DT) - **PINS SWAPPED** (white→CLK, green→DT) for correct direction (left=-100%, right=+100%)
- **Gear Buttons**: GPIO 32 (UP), GPIO 33 (DOWN)
- **Force Feedback Motor (BTS7960)**: GPIO 16 (RPWM), GPIO 17 (LPWM), GPIO 18 (R_EN), GPIO 19 (L_EN)

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
pip install opencv-python numpy tkinter pyserial Pillow
```

**ESP32:**

```bash
# Arduino IDE: Add ESP32 board support → Upload esp32.ino
# PlatformIO: platformio run --target upload
```

### Running the System

```bash
# Raspberry Pi
cd codigo/raspberry && python3 main.py

# Client
cd codigo/client && python3 main.py --port 9999
```

## Key Dependencies

- **opencv-python**: Video processing
- **numpy**: Sensor computations
- **picamera2**: Raspberry Pi camera
- **Pillow**: Image processing
- **smbus2**: I2C communication
- **adafruit-circuitpython-pca9685**: PCA9685 PWM driver
- **adafruit-circuitpython-servokit**: Servo control

## Development Notes

### Network Protocol

- **Fixed IP UDP**: RPi (192.168.5.33:9999/9998) ↔ Client (192.168.5.11)
- **Ports**: 9999 (data), 9998 (commands)
- **Commands**: CONNECT, DISCONNECT, PING, CONTROL:THROTTLE/BRAKE/STEERING/BRAKE_BALANCE/GEAR_UP/GEAR_DOWN

### Hardware Control

- **Motor**: RS550 with 5-speed manual transmission, F1-style efficiency zones
- **Servos**: PCA9685-based (Channel 0: front brake, 1: rear brake, 2: steering)
- **Brake Balance**: Default 60% front / 40% rear
- **BMI160**: 100Hz sampling, event detection (curves, braking, impacts)

### Client Interface Features

- **Instrument Panel**: RPM, gear, throttle, speed
- **Telemetry**: BMI160 data, G-forces, vehicle dynamics
- **Async Keyboard**: WASD/Arrows (20Hz), M/N (gear shifts)
- **Video Display**: Embedded Tkinter (30-50ms latency)
- **2-Column Layout**: Left (telemetry), Right (video/controls)
- **Scroll Support**: Canvas-based vertical scrolling

### Control Methods

**1. Keyboard (Fallback):**

- W/↑: Throttle 100%, S/↓: Brake 100%, A/←: Left, D/→: Right, M: Gear Up, N: Gear Down

**2. ESP32 Cockpit (Primary):**

- 3x rotary encoders (throttle, brake, steering)
- 2x push buttons (gear up/down)
- 100Hz update rate via USB serial
- Hardware interrupts on all GPIOs

## ESP32 Cockpit Integration

### Encoder Calibration System

**Protocol:**

- Client → ESP32: `CAL_START:THROTTLE/BRAKE/STEERING`
- ESP32 → Client: `CAL_THROTTLE/BRAKE/STEERING:<raw_value>` (100Hz)
- Client → ESP32: `CAL_SAVE:THROTTLE:min:max` or `CAL_SAVE:STEERING:left:center:right`
- ESP32 → Client: `CAL_COMPLETE:<component>` or `CAL_ERROR:<component>`

**EEPROM Structure:**

```cpp
struct CalibrationData {
    uint16_t magic;      // 0xCAFE
    int32_t min_value;
    int32_t max_value;
    int32_t center_value; // bipolar only
    uint8_t checksum;
};
// Addresses: THROTTLE=0, BRAKE=16, STEERING=32 (16 bytes each)
```

**Features:**

- Dynamic range detection (no hardcoded limits)
- Unipolar (throttle/brake: 0-100%) and bipolar (steering: -100% to +100%)
- EEPROM persistence with checksum validation
- Real-time raw value display

### Serial to Interface Synchronization

**IMPORTANT**: serial_receiver_manager must update client interface in real-time:

- ESP32 `THROTTLE:50` → update throttle slider to 50%
- ESP32 `BRAKE:75` → update brake slider to 75%
- ESP32 `STEERING:-30` → update steering indicator to -30%
- ESP32 `GEAR_UP/DOWN` → update gear display

**Implementation:**

```python
def update_throttle_display(self, value: int):
    def _update():
        self.throttle_slider.set(value)
        self.throttle_label.config(text=f"{value}%")
    self.root.after(0, _update)  # Thread-safe
```

## Force Feedback System

### Overview

Client-side calculation of steering resistance based on BMI160 data (lateral G-forces, yaw rotation) and steering angle. Controls ESP32 force feedback motor via BTS7960 H-bridge.

### Architecture

```
BMI160 (RPi) → UDP → Client Calculation → USB Serial → ESP32 FF Manager → BTS7960 → DC Motor
```

### Calculation Pipeline

1. **G-Force Calculation**: `g = accel / 9.81`
2. **Base Force**: Combine lateral G-force + yaw rotation + centering spring
3. **Parameter Application**: Sensitivity, Friction, Filter, Damping
4. **Direction Detection**: Centering force + lateral resistance + yaw resistance
5. **Serial Command**: `FF_MOTOR:LEFT/RIGHT/NEUTRAL:<intensity>`

### Force Components

```python
# Component 1: Lateral G-forces (0-100%)
lateral_component = min(abs(g_force_lateral) * 50, 100)

# Component 2: Yaw rotation (0-50%)
yaw_component = min(abs(gyro_z) / 60.0 * 50, 50)

# Component 3: Centering spring (0-40%)
steering_angle_ratio = abs(steering_value) / 100.0
centering_component = steering_angle_ratio * 40

# Combined
base_steering_ff = min(lateral_component + yaw_component + centering_component, 100)
```

### Adjustable Parameters

- **Sensitivity** (default 75%): Overall force magnitude
- **Friction** (default 30%): Tire friction simulation
- **Filter** (default 40%): Noise removal (EMA smoothing)
- **Damping** (default 50%): Mechanical inertia

### Serial Protocol

```
Format: FF_MOTOR:direction:intensity

Examples:
  FF_MOTOR:LEFT:45      - 45% force counter-clockwise
  FF_MOTOR:RIGHT:80     - 80% force clockwise
  FF_MOTOR:NEUTRAL:0    - Release wheel
```

### Visual Feedback

- **Left LED** (🟠 Orange): Force pulls left
- **Right LED** (🔵 Cyan): Force pulls right
- **Intensity**: 0-100% with color coding (Green/Orange/Red)

### Hardware

- **Motor Driver**: BTS7960 43A H-Bridge
- **ESP32 Pinout**: GPIO 16 (RPWM), 17 (LPWM), 18 (R_EN), 19 (L_EN)
- **PWM**: 1kHz, 8-bit (0-255)
- **Power**: 6V-27V motor, 5V logic

### Implementation Files

- **Client**: `console_interface.py` (`_calculate_g_forces_and_ff()`, `send_ff_command()`)
- **ESP32**: `esp32.ino` (`process_serial_command()`), `ff_motor_manager.h/cpp`
- **Raspberry Pi**: `bmi160_manager.py` (raw data only, no FF calculation)

## Important Files

**Documentation:**

- `raspberry/MODULOS.md`: Especificações técnicas de todos os módulos de hardware
- `raspberry/DIAGRAMA.drawio.pdf`: Diagrama elétrico completo do sistema

**Client:**

- `codigo/client/main.py`: Primary application
- `codigo/client/console_interface.py`: Main GUI
- `codigo/client/serial_receiver_manager.py`: ESP32 serial handler
- `codigo/client/calibration_manager.py`: Encoder calibration logic
- `codigo/requirements.txt`: Python dependencies

**Raspberry Pi:**

- `raspberry/main.py`: Primary application
- `raspberry/bmi160_manager.py`: IMU sensor manager
- `raspberry/power_monitor_manager.py`: Energy monitoring (ADS1115 + INA219)

**ESP32:**

- `codigo/esp32/esp32.ino`: Dual-core orchestrator
- `codigo/esp32/encoder_calibration.h/cpp`: Generic calibration
- `codigo/esp32/ff_motor_manager.h/cpp`: Force feedback control

**Tests:**

- `codigo/test/01/`: Network communication tests
- `codigo/test/test_steering_direto_simples.py`: Steering test
- `codigo/test/test_brake_direto_simples.py`: Brake test

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
- Raspberry Pi connection: GPIO2 (SDA), GPIO3 (SCL)

### MG996R Servo Motor

- High-torque digital servo, 180° rotation
- Operating voltage: 4.8V-7.2V
- Torque: 9.4 kg⋅cm (4.8V), 11 kg⋅cm (6V)
- PWM: 50Hz, 1ms-2ms pulse width
- F1 Car usage: PCA9685 channels 0/1/2 (brakes/steering)

### PCA9685 PWM Driver

- 16-channel, 12-bit resolution (4096 steps)
- I2C address: 0x40
- Power: 3.3V logic (VCC), 5V-6V servo power (V+)
- F1 Car channels: 0 (front brake), 1 (rear brake), 2 (steering)

### BTS7960 H-Bridge

- 43A continuous current capacity
- Operating voltage: 6V-27V
- PWM control: 1kHz, 8-bit
- ESP32 pinout: GPIO 16/17 (RPWM/LPWM), GPIO 18/19 (R_EN/L_EN)

## Code Optimization

- Direct hardware control (no smooth movement threads)
- Clean codebase (no unused code)
- F1-style efficiency zones
- Optimized video pipeline (frame dropping, batch processing)
- Thread-safe operations with `root.after()`

## Error Handling

- Graceful hardware degradation
- Comprehensive logging
- Clean shutdown procedures
- I2C timing optimization (5ms delays)
- Null safety for sensor readings
