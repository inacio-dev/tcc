# CLAUDE.md

```
╔═══════════════════════════════════════════════════════════════════════════════╗
║                                                                               ║
║                           ⚠️  AVISO CRÍTICO  ⚠️                               ║
║                                                                               ║
║   Este arquivo NÃO DEVE EXCEDER 40.000 CARACTERES (40k chars)               ║
║                                                                               ║
║   Tamanho Atual: ~32k chars                                                  ║
║   Limite Máximo: 40k chars                                                   ║
║   Impacto se exceder: Performance degradada do Claude Code                   ║
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
- `camera_manager.py`: OV5647 camera + H.264 video encoding
- `bmi160_manager.py`: IMU sensor (accel/gyro) data
- `motor_manager.py`: RC 775 motor + 5-speed transmission
- `brake_manager.py`: Dual servo brake (front/rear)
- `steering_manager.py`: Direct servo steering (0°-180°)
- `network_manager.py`: UDP transmission
- `power_monitor_manager.py`: Energy monitoring (ADS1115 + INA219)

**Client Side (`client/`):**

- `main.py`: Main orchestrator
- `network_client.py`: UDP receiver (filters by configured IP)
- `serial_receiver_manager.py`: ESP32 cockpit receiver
- `video_display.py`: H.264 video rendering (PyAV/FFmpeg)
- `console_interface.py`: UI with instrument panel + auto-save
- `sensor_display.py`: Sensor data processing + history
- `keyboard_controller.py`: Async keyboard input
- `calibration_manager.py`: Encoder calibration
- `slider_controller.py`: Control sliders + calibration UI

**ESP32 Cockpit (`esp32/`):**

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

- **Vehicle**: Raspberry Pi 4B (8GB), OV5647 camera, BMI160 IMU, RC 775 motor, 3x MG996R servos
- **Cockpit**: ESP32 DevKit V1 (240MHz dual-core), 3x rotary encoders (600 PPR), 2x buttons, BTS7960 H-bridge
- **Network**: mDNS (RPi: `f1car.local`, Client: `f1client.local`)
- **Serial**: ESP32→Client via USB (115200 baud, 100Hz)

**Raspberry Pi 4 Pinout:**

- Camera OV5647 → CSI slot
- BMI160 (I2C) → GPIO2/3 (SDA/SCL), Address: 0x68
- PCA9685 PWM (I2C) → GPIO2/3 (shared), Address: 0x40
- ADS1115 ADC (I2C) → GPIO2/3 (shared), Address: 0x48
- INA219 (I2C) → GPIO2/3 (shared), Address: 0x41 (A0=VCC)
- Motor BTS7960: RPWM→GPIO18, LPWM→GPIO27, R_EN→GPIO22, L_EN→GPIO23

**Power Monitoring (ADS1115 channels):**

- A0: ACS758 50A → XL4015 current (Raspberry Pi)
- A1: ACS758 50A → UBEC current (Servos)
- A2: ACS758 100A → Motor DC 775 current

**ESP32 DevKit V1 Pinout:**

- **Throttle Encoder**: GPIO 25 (CLK), GPIO 26 (DT) - **PINS SWAPPED**
- **Brake Encoder**: GPIO 27 (CLK), GPIO 14 (DT)
- **Steering Encoder**: GPIO 12 (CLK), GPIO 13 (DT) - **PINS SWAPPED**
- **Gear Buttons**: GPIO 32 (UP), GPIO 33 (DOWN)
- **Force Feedback Motor (BTS7960)**: GPIO 16 (RPWM), GPIO 17 (LPWM), GPIO 18 (R_EN), GPIO 19 (L_EN)

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
pip install opencv-python numpy pyserial Pillow av
```

**ESP32:**

```bash
# Arduino IDE: Add ESP32 board support → Upload esp32.ino
# PlatformIO: platformio run --target upload
```

### Running the System

```bash
# Raspberry Pi
cd raspberry && python3 main.py

# Client
cd client && python3 main.py --port 9999
```

## Key Dependencies

- **opencv-python**: Video processing
- **numpy**: Sensor computations
- **picamera2**: Raspberry Pi camera
- **Pillow**: Image processing
- **av (PyAV)**: H.264 decoding (FFmpeg wrapper)
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
- **Video Display**: Embedded Tkinter with H.264 decoding
- **Auto-Save**: Automatic data export every 20s
- **2-Column Layout**: Left (telemetry), Right (video/controls)

## Control Methods

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

### Serial to Interface Synchronization

**IMPORTANT**: serial_receiver_manager must update client interface in real-time:

- ESP32 `THROTTLE:50` → update throttle slider to 50%
- ESP32 `BRAKE:75` → update brake slider to 75%
- ESP32 `STEERING:-30` → update steering indicator to -30%
- ESP32 `GEAR_UP/DOWN` → update gear display

## Force Feedback System

### Architecture

```
BMI160 (RPi) → UDP → Client Calculation → USB Serial → ESP32 FF Manager → BTS7960 → DC Motor
```

### Force Components

```python
# Component 1: Lateral G-forces (0-100%)
lateral_component = min(abs(g_force_lateral) * 50, 100)

# Component 2: Yaw rotation (0-50%)
yaw_component = min(abs(gyro_z) / 60.0 * 50, 50)

# Component 3: Centering spring (0-40%)
centering_component = abs(steering_value) / 100.0 * 40

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

## Important Files

**Documentation:**

- `raspberry/MODULOS.md`: Technical specifications of all hardware modules
- `raspberry/DIAGRAMA.drawio.pdf`: Complete electrical diagram

**Client:**

- `client/main.py`: Primary application
- `client/console_interface.py`: Main GUI + auto-save
- `client/network_client.py`: UDP receiver with IP filtering
- `client/video_display.py`: H.264 decoder
- `client/sensor_display.py`: Sensor processing + pickle export

**Raspberry Pi:**

- `raspberry/main.py`: Primary application
- `raspberry/bmi160_manager.py`: IMU sensor manager
- `raspberry/power_monitor_manager.py`: Energy monitoring (ADS1115 + INA219)

**ESP32:**

- `esp32/esp32.ino`: Dual-core orchestrator
- `esp32/encoder_calibration.h/cpp`: Generic calibration
- `esp32/ff_motor_manager.h/cpp`: Force feedback control

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
- I2C address: 0x40
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
- Optimized video pipeline (H.264 + frame dropping)
- Thread-safe operations with `root.after()`
- Auto-save with Pickle (5-10x faster than CSV)

## Error Handling

- Graceful hardware degradation
- Comprehensive logging
- Clean shutdown with `os._exit(0)` (avoids Tcl_AsyncDelete error)
- I2C timing optimization (5ms delays)
- Null safety for sensor readings
