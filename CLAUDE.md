# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is an F1-style remote-controlled car project that implements a complete telemetry and control system using a Raspberry Pi 4 Model B (8GB RAM). The system captures video, sensor data, and vehicle control information, transmitting it over UDP to a client application.

## Architecture

### System Components

**Raspberry Pi Side (`codigo/raspberry/`):**
- **Main Controller** (`main.py`): Orchestrates all hardware components
- **Camera Manager** (`camera_manager.py`): OV5647 camera capture and video encoding  
- **BMI160 Manager** (`bmi160_manager.py`): IMU sensor (accelerometer/gyroscope) data collection
- **Motor Manager** (`motor_manager.py`): RS550 motor control with 5-speed manual transmission
- **Brake Manager** (`brake_manager.py`): Dual servo brake system (front/rear)
- **Steering Manager** (`steering_manager.py`): Direct servo-based steering (0°-180° range)
- **Network Manager** (`network_manager.py`): UDP transmission of video + telemetry

**Client Side (`codigo/client/`):**
- **Main Client** (`main.py`): Main application orchestrator
- **Network Client** (`network_client.py`): UDP receiver and packet processing
- **Serial Receiver Manager** (`serial_receiver_manager.py`): Arduino Mega cockpit command receiver
- **Video Display** (`video_display.py`): OpenCV-based video rendering
- **Sensor Display** (`sensor_display.py`): Real-time telemetry visualization
- **Console Interface** (`console_interface.py`): User interface with instrument panel
- **Keyboard Controller** (`keyboard_controller.py`): Asynchronous keyboard input handling

**ESP32 Cockpit (`codigo/esp32/`):**
- **Main Controller** (`esp32.ino`): ESP32 dual-core main orchestrator for cockpit hardware
- **Throttle Manager** (`throttle_manager.h/cpp`): LPD3806-600BM-G5-24C encoder for throttle control (600 PPR)
- **Brake Manager** (`brake_manager.h/cpp`): LPD3806-600BM-G5-24C encoder for brake control (600 PPR)
- **Steering Manager** (`steering_manager.h/cpp`): LPD3806-600BM-G5-24C encoder for steering control (600 PPR)
- **Gear Manager** (`gear_manager.h/cpp`): Push button gear shift controls (up/down)
- **Serial Sender Manager** (`serial_sender_manager.h/cpp`): USB serial transmission to client PC
- **Force Feedback Motor Manager** (`ff_motor_manager.h/cpp`): BTS7960 H-bridge motor control for steering force feedback

### Hardware Configuration

**Current Setup:**
- **Vehicle Hardware**: Raspberry Pi 4 Model B (8GB RAM)
- **Cockpit Hardware**: ESP32 DevKit V1 (240 MHz dual-core, 520KB RAM)
- **Network Configuration**:
  - Raspberry Pi IP: 192.168.5.33
  - Client PC IP: 192.168.5.11
  - Fixed IP communication (auto-discovery disabled)
- **Serial Configuration** (ESP32 Cockpit):
  - ESP32 → Client PC via USB Serial
  - Baud rate: 115200
  - Update rate: 100Hz (10ms intervals)
  - Auto-detection of COM port (/dev/ttyUSB0, /dev/ttyACM0, etc.)
  - **Performance**: Dual-core processing with hardware interrupts on all GPIOs

**Raspberry Pi 4 Pinout:**
- Camera OV5647 → CSI slot
- BMI160 (I2C) → GPIO2/3 (SDA/SCL)
- PCA9685 PWM Driver (I2C) → GPIO2/3 (SDA/SCL, shared with BMI160)
- Motor BTS7960 RPWM → GPIO18
- Motor BTS7960 LPWM → GPIO27
- Motor BTS7960 R_EN → GPIO22
- Motor BTS7960 L_EN → GPIO23
- **Note**: GPIO4, GPIO17, GPIO24 are now available (previously used for servos)

**Detailed Pin Mapping:**
- **Power**: 3.3V (Pin 1,17), 5V (Pin 2,4), GND (Pin 6,9,14,20,25,30,34,39)
- **I2C**: SDA (GPIO2/Pin 3), SCL (GPIO3/Pin 5)
- **SPI**: MOSI (GPIO10/Pin 19), MISO (GPIO9/Pin 21), SCLK (GPIO11/Pin 23)
- **PWM**: GPIO12 (Pin 32), GPIO13 (Pin 33), GPIO18 (Pin 12), GPIO19 (Pin 35)
- **UART**: TXD (GPIO14/Pin 8), RXD (GPIO15/Pin 10)
- **PCM**: PCM_CLK (GPIO18/Pin 12), PCM_FS (GPIO19/Pin 35), PCM_DIN (GPIO20/Pin 38), PCM_DOUT (GPIO21/Pin 40)

**ESP32 DevKit V1 Pinout (Cockpit):**
- **CPU**: Dual-core Xtensa LX6 @ 240MHz (Core 0: encoders, Core 1: serial)
- **Memory**: 520KB SRAM
- **USB Serial**: 115200 baud, auto-detected by client
- **Hardware Interrupts**: All GPIO pins support interrupts
- **Components**: 3x LPD3806-600BM-G5-24C rotary encoders (600 PPR), 2x push buttons, 1x BTS7960 H-bridge
- **Throttle Encoder**: GPIO 25 (CLK), GPIO 26 (DT)
- **Brake Encoder**: GPIO 27 (CLK), GPIO 14 (DT)
- **Steering Encoder**: GPIO 12 (CLK), GPIO 13 (DT)
- **Gear Up Button**: GPIO 32 (with internal pull-up, active LOW)
- **Gear Down Button**: GPIO 33 (with internal pull-up, active LOW)
- **Force Feedback Motor (BTS7960)**:
  - GPIO 16: RPWM (Right PWM - clockwise rotation)
  - GPIO 17: LPWM (Left PWM - counter-clockwise rotation)
  - GPIO 18: R_EN (Right enable)
  - GPIO 19: L_EN (Left enable)
- **Power**: 3.3V/5V (VCC), GND - encoders powered by 5V, logic at 3.3V
- **Note**: All rotary encoders use hardware interrupts with pattern matching for precise quadrature decoding

## Development Commands

### Environment Setup

**Raspberry Pi Setup:**
```bash
# Enable required interfaces
sudo raspi-config  # Enable Camera, I2C, SPI

# Install system dependencies
sudo apt update
sudo apt install build-essential python3-dev libcap-dev
sudo apt install libcamera-apps python3-libcamera
sudo apt install python3-opencv python3-numpy python3-picamera2 python3-libcamera

# Install Python dependencies
pip install --upgrade pip wheel
pip install -r requirements.txt
```

**Client Setup:**
```bash
pip install opencv-python numpy tkinter pyserial
```

**ESP32 Setup:**
```bash
# Install Arduino IDE or PlatformIO
# Option 1: Arduino IDE
# 1. Download from https://www.arduino.cc/en/software
# 2. Add ESP32 board support:
#    - File → Preferences → Additional Board Manager URLs
#    - Add: https://raw.githubusercontent.com/espressif/arduino-esp32/gh-pages/package_esp32_index.json
# 3. Tools → Board → Boards Manager → Search "ESP32" → Install
# 4. Select Board: "ESP32 Dev Module" or "ESP32-WROOM-DA Module"

# Option 2: PlatformIO (recommended for advanced users)
# Install PlatformIO extension for VS Code
# Platform: espressif32
# Board: esp32dev
# Framework: arduino

# Compile and upload esp32.ino to ESP32
# Arduino IDE: Open esp32.ino → Select Board "ESP32 Dev Module" → Upload
# PlatformIO: platformio run --target upload

# No configuration needed - ESP32 uses USB serial (auto-detected by client)
```

### Running the System

**Start Raspberry Pi System:**
```bash
cd codigo/raspberry
# Fixed IP mode (current configuration)
python3 main.py
```

**Start Client Application:**
```bash
cd codigo/client  
# Fixed IP mode - connects to Raspberry Pi at 192.168.5.33
python3 main.py --port 9999
```

**Communication Flow (Fixed IP Mode + ESP32 Serial Cockpit):**
1. **Network Communication (Raspberry Pi ↔ Client PC):**
   - Raspberry Pi starts and listens on 192.168.5.33:9999 (data) and :9998 (commands)
   - Client starts and connects to Raspberry Pi at 192.168.5.33
   - Bidirectional UDP communication established immediately
   - Optimized for real-time performance with reduced latency

2. **Serial Communication (ESP32 → Client PC → Raspberry Pi):**
   - ESP32 reads cockpit controls (encoders + buttons) at 100Hz using dual-core processing
   - **Core 0**: Real-time encoder tracking with hardware interrupts (high priority)
   - **Core 1**: USB serial transmission to client PC (115200 baud, normal priority)
   - Client PC receives serial commands and forwards to Raspberry Pi via UDP
   - End-to-end latency: ~10-20ms from cockpit input to vehicle response
   - Commands sent: THROTTLE, BRAKE, STEERING (analog), GEAR_UP, GEAR_DOWN (digital)
   - **Performance**: Dual-core 240MHz CPU with hardware interrupts on all GPIOs

### Testing

**Basic Network Test:**
```bash
cd codigo/test/01
python3 rasp.py    # On Raspberry Pi
python3 client.py  # On client PC
```

### Type Checking

The project uses mypy for type checking:
```bash
mypy codigo/
```

## Key Dependencies

- **opencv-python**: Video capture and processing
- **numpy**: Numerical computations for sensor data
- **picamera2**: Raspberry Pi camera interface
- **Pillow**: Image processing for optimized video display
- **smbus2**: I2C communication (Raspberry Pi only)
- **adafruit-circuitpython-pca9685**: PCA9685 PWM driver for servo control
- **adafruit-blinka**: CircuitPython compatibility for Raspberry Pi
- **adafruit-circuitpython-motor**: Motor control via PCA9685
- **adafruit-circuitpython-servokit**: High-level servo control interface

## Development Notes

### Code Style
- All Python modules follow PEP 8 conventions
- Comprehensive docstrings with hardware pinout information
- Type hints used throughout for better code maintainability
- Modular architecture with clear separation of concerns

### Network Protocol
- **Fixed IP UDP communication** optimized for real-time performance
- **Current Configuration**:
  - **Raspberry Pi**: 192.168.5.33 (fixed IP)
  - **Client PC**: 192.168.5.11 (fixed IP)
  - **Direct communication** without auto-discovery overhead
- **Raspberry Pi (Server)**:
  - Port 9999: Sends video + telemetry data to fixed client IP
  - Port 9998: Receives commands from client (CONNECT, DISCONNECT, PING, CONTROL)
  - Thread-safe client management with connection tracking
- **Client (Receiver)**:
  - Port 9999: Receives data from Raspberry Pi
  - Port 9998: Sends commands to Raspberry Pi
  - Direct connection to fixed Raspberry Pi IP
- **Connection Flow**:
  1. Raspberry Pi starts and begins sending data to fixed client IP
  2. Client starts and immediately receives data stream
  3. Bidirectional communication active from startup
  4. Client can send control commands (THROTTLE, BRAKE, STEERING, BRAKE_BALANCE, GEAR_UP, GEAR_DOWN)
- **Protocol Features**:
  - **Fixed IP configuration** for maximum performance
  - **Real-time optimized** with minimal latency
  - Connection timeout and graceful disconnection
  - Command acknowledgment and ping/pong heartbeat
  - 128KB buffer size with automatic packet loss handling
  - **Asynchronous keyboard controls** preventing UI freezing

### Hardware Control
- **Motor System**: RS550 motor with 5-speed manual transmission
  - Direct PWM control with F1-style efficiency zones
  - Manual gear shifting only (M/N keys for gear up/down)
  - Thread-safe motor control with immediate response
- **Servo Control System**: PCA9685-based PWM servo control
  - **PCA9685 I2C Address**: 0x40 (shared I2C bus with BMI160)
  - **Channel Mapping**: Channel 0 (front brake), Channel 1 (rear brake), Channel 2 (steering)
  - **Power Configuration**: External 5V-6V power supply for servos (V+), 3.3V logic (VCC)
  - **Current Requirements**: 8A total capacity for 3x MG996R servos (1-2A each)
- **Brake System**: Dual servo brake system (MG996R front/rear via PCA9685)
  - Full 0°-180° range utilization for maximum braking force
  - Direct servo control without smooth movement
  - F1-style brake balance with immediate response
- **Steering System**: Direct servo control (via PCA9685 Channel 2)
  - Full 0°-180° range utilization (no artificial limits)
  - Immediate servo response without smooth movement
- **Sensor Integration**: BMI160 6-axis IMU for real-time feedback
  - Automatic event detection (curves, braking, acceleration, impacts)
  - Force feedback calculation for immersive control
- **Safety Features**: Emergency stops, impact detection, hardware timeouts

### Client Interface Features
- **Real-time Instrument Panel**: F1-style dashboard with motor telemetry
  - **RPM Gauge**: Digital tachometer display showing engine RPM in real-time
  - **Gear Display**: Large numeric gear indicator (1-5) with manual control
  - **Throttle Display**: Current throttle percentage with color-coded feedback
  - **Speed Display**: Calculated vehicle speed in km/h
- **Comprehensive Telemetry Display**: 
  - BMI160 sensor data (accelerometer, gyroscope, G-forces)
  - Vehicle dynamics (steering angle, brake balance, battery level)
  - Force feedback indicators for immersive control
  - Event detection (turning, braking, acceleration, impacts)
- **Asynchronous Keyboard Controls**: Non-blocking input system
  - Real-time WASD/Arrow key control without UI freezing
  - Visual feedback for active controls (blue highlighting)
  - Instant gear shift commands with green flash feedback
  - Thread-safe command processing at 20Hz update rate
- **Network Status Monitoring**: Live connection quality indicators
  - FPS, data throughput, packet loss statistics
  - Connection status with color-coded indicators
  - Real-time latency measurement and display
- **Brake Balance Control**: Interactive slider for brake distribution
  - Real-time adjustment between front (0-100%) and rear braking
  - Visual feedback and immediate command transmission
  - Default 60% front / 40% rear distribution

### Interface Improvements (Latest Updates)

#### **Modern UI Layout**
- **Responsive 2-Column Grid Layout**: Interface optimally divided for maximum screen width usage
  - **Left Column**: Technical data (Status, Instruments, BMI160 sensors, Force Feedback)
  - **Right Column**: Interactive elements (Video, Vehicle controls, Commands, Logs)
  - **Dynamic sizing**: Columns adapt automatically to window resizing
  - **Professional spacing**: Consistent 5px padding and sticky expansion

#### **Advanced Scroll System**
- **Vertical Mouse Wheel Support**: Smooth scrolling through extensive telemetry data
- **Canvas-Based Scrolling**: Responsive scrollbar with dynamic content sizing
- **Intelligent Content Management**: Interface automatically adjusts to content height
- **Optimized Performance**: Scroll events handled at optimal frame rates

#### **Integrated Video Display**
- **Seamless Integration**: Video feed embedded directly in main interface (no separate window)
- **Optimized Tkinter Rendering**: Custom-optimized video pipeline for minimal delay
  - **Frame Dropping Algorithm**: Automatically discards old frames to maintain real-time display
  - **Batch Processing**: Drains entire video queue and displays only latest frame
  - **Smart Resizing**: Conditional resizing only when necessary (>50px difference)
  - **Fast Interpolation**: Uses INTER_NEAREST for reduced CPU overhead
  - **Optimized Overlays**: Renders FPS/resolution info only every 5th frame
- **Performance Optimizations**:
  - **60 FPS Maximum**: 16ms sleep cycle for minimal latency
  - **Direct PIL Conversion**: RGB mode specified for faster image conversion
  - **Error-Resilient**: Protected against widget destruction and callback failures
  - **Memory Efficient**: Automatic reference management for PhotoImage objects

#### **Video Performance Metrics**
- **Latency Comparison**:
  - **Previous OpenCV Window**: ~50-80ms delay (separate window overhead)
  - **Optimized Tkinter Integration**: ~30-50ms delay (competitive with OpenCV)
  - **Frame Drop Prevention**: Maintains real-time display even under load
- **Quality Enhancements**:
  - **Aspect Ratio Preservation**: Automatic scaling while maintaining video proportions
  - **Resolution Display**: Real-time resolution information (320px width optimized)
  - **Connection Status**: Live video status with color-coded indicators
  - **FPS Monitoring**: Continuous frame rate measurement and display

#### **Responsive Window Management**
- **Resizable Main Window**: Default 1400x900px with full resize capability
- **Adaptive Content**: All widgets automatically adjust to new window dimensions
- **Scroll Integration**: Content flows naturally with window height changes
- **Professional Appearance**: Dark theme with consistent color scheme

#### **Updated File Structure**
- **`console_interface.py`**: Enhanced with Canvas scroll system and 2-column grid
- **`video_display.py`**: Completely rewritten for Tkinter-only operation
- **`main.py`**: Updated initialization order for proper video integration
- **`requirements.txt`**: Added Pillow dependency for optimized image processing

#### **Technical Fixes & Improvements**
- **BMI160 Communication Stability**:
  - **I2C Timing Optimization**: Added 5ms delays between I2C operations for reliable sensor communication
  - **Robust Initialization**: Enhanced initialization sequence with retry logic and error handling
  - **Null Safety**: Protected against None values in sensor readings that could cause crashes
- **Network Command Reliability**:
  - **Fixed IP Mode**: Corrected NetworkClient to properly configure raspberry_pi_ip in fixed IP mode
  - **Command Transmission**: Resolved issue where keyboard commands weren't being sent to Raspberry Pi
  - **Connection Stability**: Improved connection handling and automatic reconnection logic
- **Video Integration Fixes**:
  - **Initialization Order**: Fixed widget creation order to prevent video_label initialization errors
  - **Thread Safety**: Enhanced thread synchronization between video processing and UI updates
  - **Memory Management**: Improved image reference handling to prevent memory leaks

### Code Optimization
- **Direct Hardware Control**: All servo movements use immediate `servo.angle` commands
- **No Smooth Movement**: Removed all threading and gradual movement systems
- **Clean Codebase**: Eliminated unused variables, functions, and imports
- **Optimized Performance**: Reduced latency through direct control methods
- **F1-Style Efficiency**: Motor system uses efficiency zones for realistic F1 behavior

### Error Handling
- Graceful degradation when hardware components are unavailable
- Comprehensive logging and status reporting
- Clean shutdown procedures with proper resource cleanup

## Important Files

**Python Client:**
- `codigo/requirements.txt`: Python dependencies (includes pyserial for Arduino Mega)
- `codigo/README.md`: Hardware setup instructions
- `codigo/INTERFACE_IMPROVEMENTS.md`: Detailed documentation of recent UI improvements
- `codigo/client/main.py`: Primary client application (integrates serial + network)
- `codigo/client/serial_receiver_manager.py`: Arduino Mega serial command receiver
- `codigo/client/console_interface.py`: Main GUI with instrument panel and 2-column layout
- `codigo/client/video_display.py`: Optimized Tkinter-only video display system
- `codigo/client/keyboard_controller.py`: Asynchronous keyboard input
- `codigo/client/calibration_manager.py`: Encoder calibration logic and persistence
- `codigo/client/slider_controller.py`: Vehicle control sliders with calibration UI

**Raspberry Pi:**
- `codigo/raspberry/main.py`: Primary Raspberry Pi application

**ESP32 Cockpit:**
- `codigo/esp32/esp32.ino`: ESP32 dual-core main orchestrator with calibration protocol and FF motor control
- `codigo/esp32/throttle_manager.h/cpp`: Throttle encoder manager with calibration
- `codigo/esp32/brake_manager.h/cpp`: Brake encoder manager with calibration
- `codigo/esp32/steering_manager.h/cpp`: Steering encoder manager with calibration
- `codigo/esp32/gear_manager.h/cpp`: Gear shift button manager
- `codigo/esp32/serial_sender_manager.h/cpp`: USB serial transmission manager
- `codigo/esp32/encoder_calibration.h/cpp`: Generic encoder calibration class with EEPROM storage
- `codigo/esp32/ff_motor_manager.h/cpp`: Force feedback motor control via BTS7960 H-bridge

**Tests:**
- `codigo/test/01/`: Basic network communication tests
- `codigo/test/test_steering_direto_simples.py`: Direct steering servo test (0°-180°)
- `codigo/test/test_brake_direto_simples.py`: Direct brake servo test (0°-180°)

## Configuration

System parameters can be configured via command-line arguments:

**Raspberry Pi Parameters:**
- `--port`: UDP port for sending data (default: 9999)  
- `--fps`: Camera frame rate (default: 30)
- `--sensor-rate`: Sensor sampling rate in Hz (default: 100)
- `--brake-balance`: Brake distribution percentage (default: 60%)
- `--transmission`: Always manual (no automatic mode)
- `--servo-range`: Servo range optimization (0-180°)

**Client Parameters:**
- `--port`: UDP port for receiving data (default: 9999)
- `--buffer`: Buffer size in KB (default: 128)
- `--debug`: Enable debug mode with verbose logging

**Control Options:**

The system supports two control methods:

1. **Keyboard Controls** (Default fallback):
   - `↑` or `W`: Accelerate (THROTTLE: 100%)
   - `↓` or `S`: Brake (BRAKE: 100%)
   - `←` or `A`: Steer left (STEERING: -100%)
   - `→` or `D`: Steer right (STEERING: +100%)
   - `M`: Shift gear up (GEAR_UP)
   - `N`: Shift gear down (GEAR_DOWN)
   - **Control Types**: Continuous (hold key) for movement, instant (tap key) for gear shifts
   - **Visual Feedback**: Active controls highlighted in blue, gear shifts flash green
   - **Real-time Commands**: 20 commands/second for smooth control
   - **Focus Required**: Click on interface window to activate keyboard controls

2. **ESP32 Cockpit Controls** (Professional setup):
   - **Throttle Encoder**: 360-pulse rotary encoder (0-360° → 0-100% throttle)
   - **Brake Encoder**: 360-pulse rotary encoder (0-360° → 0-100% brake)
   - **Steering Encoder**: 360-pulse rotary encoder (0-360° → -100% to +100% steering)
   - **Gear Up Button**: Push button for upshifts (1→2→3→4→5)
   - **Gear Down Button**: Push button for downshifts (5→4→3→2→1)
   - **Update Rate**: 100Hz (10ms intervals) for real-time analog control
   - **Connection**: USB serial (auto-detected on /dev/ttyUSB0 or /dev/ttyACM0)
   - **Debouncing**: 50ms debounce on gear shift buttons
   - **Interrupts**: Hardware interrupts on all GPIOs for precise encoder tracking
   - **Dual-Core**: Core 0 for encoders (high priority), Core 1 for serial transmission
   - **Performance**: 240MHz CPU, 520KB RAM, IRAM_ATTR ISRs for ultra-fast response

**Command Protocols:**

1. **UDP Network Protocol** (Client ↔ Raspberry Pi):
   - `CONNECT`: Establish connection (sent automatically)
   - `DISCONNECT`: Close connection (sent on exit)
   - `PING:<timestamp>`: Heartbeat with latency measurement
   - `CONTROL:THROTTLE:<value>`: Accelerate (0-100%)
   - `CONTROL:BRAKE:<value>`: Brake force (0-100%)
   - `CONTROL:STEERING:<value>`: Steering angle (-100 to +100)
   - `CONTROL:BRAKE_BALANCE:<value>`: Brake distribution (0-100%)
   - `CONTROL:GEAR_UP`: Shift to next higher gear (1→2, 2→3, etc.)
   - `CONTROL:GEAR_DOWN`: Shift to next lower gear (5→4, 4→3, etc.)

2. **Serial Protocol** (ESP32 → Client):
   - `THROTTLE:<value>`: Throttle position (0-100%)
   - `BRAKE:<value>`: Brake position (0-100%)
   - `STEERING:<value>`: Steering position (-100 to +100%)
   - `GEAR_UP`: Gear up button pressed
   - `GEAR_DOWN`: Gear down button pressed
   - **Format**: Plain text, newline-terminated
   - **Baud Rate**: 115200
   - **Update Rate**: 100Hz for analog values (only when changed), instant for buttons
   - **Architecture**: Dual-core processing (Core 0: encoders, Core 1: serial)

## ESP32 Cockpit Integration

### Serial to Interface Synchronization

**IMPORTANT**: The serial_receiver_manager must update the client interface in real-time to provide visual feedback of cockpit inputs. This creates a bidirectional control system where both the physical cockpit and on-screen interface stay synchronized.

**Implementation Requirements:**

1. **Visual Feedback System**:
   - When ESP32 sends `THROTTLE:50`, the interface throttle slider must update to 50%
   - When ESP32 sends `BRAKE:75`, the interface brake slider must update to 75%
   - When ESP32 sends `STEERING:-30`, the interface steering indicator must update to -30%
   - When ESP32 sends `GEAR_UP/GEAR_DOWN`, the interface gear display must update immediately

2. **Non-Blocking Interface Updates**:
   - Serial commands update interface widgets WITHOUT blocking user interaction
   - User can still manually adjust sliders/controls via mouse while serial input is active
   - Latest value (serial OR manual) always takes precedence
   - No mutex locks or blocking operations on UI thread

3. **Update Flow**:
   ```
   ESP32 Encoder → Serial Command → serial_receiver_manager
       ↓
   handle_serial_command() → Forward to Raspberry Pi (UDP)
       ↓
   Update console_interface widgets (Tkinter sliders/indicators)
       ↓
   Visual feedback + actual vehicle control
   ```

4. **Required Interface Methods** (to be implemented in console_interface.py):
   - `update_throttle_display(value)`: Update throttle slider to value (0-100%)
   - `update_brake_display(value)`: Update brake slider to value (0-100%)
   - `update_steering_display(value)`: Update steering indicator to value (-100 to +100%)
   - `update_gear_display(gear)`: Update gear display (1-5)
   - All methods must be **thread-safe** and use `root.after()` for Tkinter updates

5. **Dual Control Support**:
   - ESP32 cockpit = primary control method (when connected)
   - Keyboard + mouse = backup/override control (always available)
   - Both methods can coexist without conflicts
   - Interface always reflects the most recent command from ANY source

**Example Implementation Pattern:**
```python
# In console_interface.py
def update_throttle_display(self, value: int):
    """Update throttle slider from external source (serial/keyboard)"""
    def _update():
        self.throttle_slider.set(value)  # Update slider position
        self.throttle_label.config(text=f"{value}%")  # Update label
    self.root.after(0, _update)  # Thread-safe Tkinter update
```

This design allows seamless switching between physical cockpit and software interface, providing maximum flexibility during operation.

### Encoder Calibration System

**Overview:**
The encoder calibration system allows dynamic configuration of incremental rotary encoders without hardcoded pulse limits. This ensures accurate mapping regardless of encoder starting position or mechanical range.

**Key Features:**
- **Dynamic Range Detection**: Automatically calculates min/max/center values from user input
- **EEPROM Persistence**: Calibration data stored in ESP32 EEPROM with checksum validation
- **Unipolar/Bipolar Modes**: Throttle/brake use 0-100%, steering uses -100% to +100%
- **Real-time Feedback**: Live raw encoder values displayed during calibration
- **Bidirectional Protocol**: Client-initiated calibration with ESP32 response

**Calibration Workflow:**

1. **Throttle/Brake Calibration** (Unipolar: 0-100%):
   - User clicks "Calibrar" button in interface
   - Interface displays: "Pressione o pedal completamente e depois solte"
   - User presses pedal fully (records max value) and releases (records min value)
   - Client sends `CAL_START:THROTTLE` or `CAL_START:BRAKE` to ESP32
   - ESP32 enters calibration mode and sends raw encoder values at 100Hz
   - Client displays raw values in real-time: `CAL_THROTTLE:1290` or `CAL_BRAKE:856`
   - User confirms calibration → Client sends `CAL_SAVE:THROTTLE:360:1290`
   - ESP32 saves to EEPROM and responds `CAL_COMPLETE:THROTTLE`
   - Example: Encoder at position 360 = 0%, position 1290 = 100%

2. **Steering Calibration** (Bipolar: -100% to +100%):
   - User clicks "Calibrar" button for steering
   - Interface displays: "Gire totalmente para a esquerda, depois para a direita, e pare no centro"
   - User rotates steering wheel through full range: left → right → center
   - Client sends `CAL_START:STEERING` to ESP32
   - ESP32 sends raw values: `CAL_STEERING:-543` (left), `CAL_STEERING:1876` (right)
   - Client tracks min (left), max (right), and center values
   - User confirms → Client sends `CAL_SAVE:STEERING:-543:412:1876`
   - ESP32 saves and responds `CAL_COMPLETE:STEERING`
   - Example: -543 = -100% (left), 412 = 0% (center), 1876 = +100% (right)

**Serial Protocol:**

**Client → ESP32 Commands:**
```
CAL_START:THROTTLE    - Start throttle calibration
CAL_START:BRAKE       - Start brake calibration
CAL_START:STEERING    - Start steering calibration
CAL_SAVE:THROTTLE:min:max         - Save throttle calibration (e.g., CAL_SAVE:THROTTLE:360:1290)
CAL_SAVE:BRAKE:min:max            - Save brake calibration (e.g., CAL_SAVE:BRAKE:120:980)
CAL_SAVE:STEERING:left:center:right - Save steering calibration (e.g., CAL_SAVE:STEERING:-543:412:1876)
```

**ESP32 → Client Responses:**
```
CAL_STARTED:component     - Calibration mode activated
CAL_THROTTLE:raw_value    - Raw throttle encoder position (e.g., CAL_THROTTLE:856)
CAL_BRAKE:raw_value       - Raw brake encoder position (e.g., CAL_BRAKE:412)
CAL_STEERING:raw_value    - Raw steering encoder position (e.g., CAL_STEERING:-234)
CAL_COMPLETE:component    - Calibration saved successfully
CAL_ERROR:component       - Calibration save failed (checksum or EEPROM error)
```

**Implementation Files:**

**Client Side (Python):**
- **`calibration_manager.py`**: Core calibration logic
  - Tracks min/max/center values during calibration
  - Maps raw encoder values to percentages
  - Persists calibration data to `calibration_data.json`
  - Handles unipolar (throttle/brake) and bipolar (steering) modes

- **`slider_controller.py`**: Calibration UI
  - Calibration buttons for each control
  - Real-time raw value display
  - Instructions and status messages
  - Save/Cancel buttons

- **`serial_receiver_manager.py`**: Serial command handler
  - Parses `CAL_*` commands from ESP32
  - Forwards calibration data to UI
  - Sends calibration commands to ESP32 via `send_command()`

**ESP32 Side (C++):**
- **`encoder_calibration.h/cpp`**: Generic calibration class
  - EEPROM storage at addresses: THROTTLE=0, BRAKE=16, STEERING=32
  - Magic number validation (0xCAFE) and checksum verification
  - Unipolar/bipolar mapping modes
  - Methods: `begin()`, `start_calibration()`, `update_calibration()`, `save_calibration()`, `map_to_percent()`

- **`throttle_manager.h/cpp`**: Throttle encoder with calibration
  - Unipolar mode (0-100%)
  - Unlimited encoder range during calibration
  - ISR without artificial constraints

- **`brake_manager.h/cpp`**: Brake encoder with calibration
  - Unipolar mode (0-100%)
  - Same implementation as throttle

- **`steering_manager.h/cpp`**: Steering encoder with calibration
  - Bipolar mode (-100% to +100%)
  - Three-point calibration (left, center, right)

- **`esp32.ino`**: Main controller with serial command processor
  - `process_serial_command()`: Parses incoming calibration commands
  - SerialTask: Handles bidirectional communication
  - Sends raw encoder values during calibration at 100Hz
  - Automatic mode switching between calibration and normal operation

**EEPROM Structure:**
```cpp
struct CalibrationData {
    uint16_t magic;         // 0xCAFE - validation marker
    int32_t min_value;      // Minimum encoder position
    int32_t max_value;      // Maximum encoder position
    int32_t center_value;   // Center position (bipolar only)
    uint8_t checksum;       // XOR checksum of all bytes
};

// EEPROM Addresses:
// Throttle: Address 0 (16 bytes)
// Brake:    Address 16 (16 bytes)
// Steering: Address 32 (16 bytes)
```

**Advantages:**
- **No Hardcoded Limits**: Works regardless of encoder starting position
- **Flexible Ranges**: Adapts to any mechanical range or encoder resolution
- **Persistent Storage**: Calibration survives power cycles
- **Data Integrity**: Checksum validation prevents corrupted calibration
- **User-Friendly**: Simple interface with clear instructions
- **Real-time Feedback**: Live encoder values for confidence during calibration

**Example Calibration Scenarios:**

**Scenario 1: Throttle encoder starts at position 360**
- User presses pedal → encoder moves to 1290
- Calibration saves: min=360 (0%), max=1290 (100%)
- Result: Position 360 = 0% throttle, 1290 = 100% throttle

**Scenario 2: Steering encoder doesn't start at 0**
- User rotates left → encoder at -543
- User rotates right → encoder at 1876
- User centers → encoder at 412
- Calibration saves: left=-543 (-100%), center=412 (0%), right=1876 (+100%)
- Result: Perfectly centered steering regardless of mechanical offset

**Scenario 3: Brake encoder with limited range**
- User presses brake → encoder moves from 120 to 980 (860 pulses)
- Calibration saves: min=120 (0%), max=980 (100%)
- Result: Full 0-100% brake control within available mechanical range

## Hardware Datasheets Summary

### BMI160 IMU Sensor

**Overview:**
- 6-axis IMU combining 3-axis accelerometer and 3-axis gyroscope
- 16-bit resolution for both sensors
- Low power consumption: 925 μA
- Operating voltage: 1.71V - 3.6V (VDD), 1.2V - 3.6V (VDDIO)
- Temperature range: -40°C to +85°C
- FIFO buffer: 1024 bytes

**Sensor Specifications:**
- **Accelerometer**: 
  - Selectable ranges: ±2g, ±4g, ±8g, ±16g
  - Data rates: 12.5 Hz to 1600 Hz
  - Noise: ~180-300 μg/√Hz
  - Startup time: 3.2-3.8 ms

- **Gyroscope**:
  - Selectable ranges: ±125°/s, ±250°/s, ±500°/s, ±1000°/s, ±2000°/s
  - Data rates: 25 Hz to 3200 Hz
  - Noise: ~0.007 °/s/√Hz
  - Startup time: 55 ms (suspend → normal)

**I2C Configuration:**
- Default address: 0x68 (SAO = GND) or 0x69 (SAO = VDD)
- Clock speed: Up to 1MHz
- Key registers:
  - CHIP_ID (0x00): 0xD1
  - ACC_CONF (0x40): Accelerometer configuration
  - ACC_RANGE (0x41): Accelerometer range
  - GYR_CONF (0x42): Gyroscope configuration
  - GYR_RANGE (0x43): Gyroscope range
  - CMD (0x7E): Commands (reset, calibration)

**Recommended Settings for F1 Car:**
- Accelerometer: ±2g or ±4g range for smooth movements
- Gyroscope: ±250°/s or ±500°/s for normal curves
- Data rate: 100-200Hz for real-time control
- Use accel_x for forward/backward forces, gyro_z for turning

**Advanced Features:**
- Fast Offset Compensation (FOC) for automatic calibration
- Motion detection: any-motion, no-motion, tap, orientation
- Step counter and significant motion detection
- Multiple interrupt pins (INT1, INT2) for synchronization
- FIFO buffering to prevent data loss

**Initialization Sequence:**
1. Power-on → wait 10ms
2. Verify CHIP_ID (0xD1)
3. Soft reset → CMD = 0xB6
4. Configure accelerometer range + ODR
5. Configure gyroscope range + ODR
6. Activate normal mode → CMD = 0x11, 0x15
7. Wait for ready → ~60ms
8. Optional calibration → CMD = 0x03
9. Start readings

**Connection to Raspberry Pi:**
- VIN → 3.3V or 5V
- GND → Ground
- SCL → GPIO3 (Pin 5)
- SDA → GPIO2 (Pin 3)
- INT1 → GPIO4 (optional, for interrupts)
- SAO → GND (for 0x68 address) or 3.3V (for 0x69 address)

### MG996R Servo Motor

**Overview:**
- High-torque digital servo motor
- Metal gear construction for durability
- Operating voltage: 4.8V to 7.2V
- PWM control with 50Hz frequency (20ms period)

**Pin Configuration:**
- **PWM Signal (Orange)**: Control signal input
- **VCC (Red)**: Power supply positive (+)
- **Ground (Brown)**: Power supply negative (-)

**PWM Control:**
- **Frequency**: 50Hz (20ms period)
- **Pulse width range**: 1ms to 2ms
  - 1.0ms pulse → 0° position
  - 1.5ms pulse → 90° position (center)
  - 2.0ms pulse → 180° position
- **Duty cycle**: Variable based on desired position

**Technical Specifications:**
- **Rotation**: ~180° (limited rotation)
- **Torque**: 9.4 kg⋅cm (4.8V), 11 kg⋅cm (6V)
- **Speed**: 0.17 sec/60° (4.8V), 0.14 sec/60° (6V)
- **Dead band**: 10μs
- **Control system**: Digital with feedback
- **Motor type**: 3-pole ferrite magnet DC motor

**Connection via PCA9685 PWM Driver:**
- PWM Signal → PCA9685 channels (Channel 0: front brake, Channel 1: rear brake, Channel 2: steering)
- VCC → External 5V-6V power supply connected to PCA9685 V+ terminal
- Ground → Common ground between Raspberry Pi, PCA9685, and external power supply
- Control → I2C communication via GPIO2/3 (SDA/SCL)

**Usage in F1 Car:**
- **Steering Servo**: Connected to PCA9685 Channel 2, full 0°-180° range
- **Front Brake Servo**: Connected to PCA9685 Channel 0, full 0°-180° range
- **Rear Brake Servo**: Connected to PCA9685 Channel 1, full 0°-180° range
- **Control**: Direct `servo.angle` commands via PCA9685 I2C interface
- **Performance**: Immediate response without artificial range limitations

### PCA9685 16-Channel PWM/Servo Driver

**Overview:**
- 16-channel PWM driver with I2C interface
- 12-bit resolution (4096 steps) for precise servo control
- Operating voltage: 2.3V-5.5V (logic), up to 6V (servo power)
- External power input for high-current servo operation
- Frequency range: 24Hz to 1526Hz (servo standard: 50Hz)

**I2C Configuration:**
- Default address: 0x40 (configurable via address pins A0-A5)
- Clock speed: Up to 1MHz
- Shared I2C bus with BMI160 (address 0x68/0x69)

**Power Requirements:**
- **VCC (Logic)**: 3.3V from Raspberry Pi (low current, ~10mA)
- **V+ (Servos)**: External 5V-6V power supply (high current, 8A recommended)
- **GND**: Common ground between all components

**Channel Mapping for F1 Car:**
- **Channel 0**: Front brake servo (MG996R)
- **Channel 1**: Rear brake servo (MG996R)
- **Channel 2**: Steering servo (MG996R)
- **Channels 3-15**: Available for expansion (additional servos, LEDs, etc.)

**Servo Control Specifications:**
- **Frequency**: 50Hz (20ms period) for servo compatibility
- **Pulse Width**: 1ms-2ms (servo standard range)
- **Resolution**: 12-bit (4096 steps) for smooth servo movement
- **Current Capacity**: Up to 25mA per channel (sufficient for servo control signals)

**Wiring Configuration:**
```
Raspberry Pi → PCA9685:
- 3.3V (Pin 1) → VCC
- GND (Pin 6) → GND
- GPIO2/SDA (Pin 3) → SDA
- GPIO3/SCL (Pin 5) → SCL

External Power → PCA9685:
- 5V-6V → V+
- GND → GND (common with RPi)

Servos → PCA9685:
- Channel 0 → Front Brake Servo
- Channel 1 → Rear Brake Servo
- Channel 2 → Steering Servo
```

**Advantages of PCA9685 Integration:**
- **GPIO Liberation**: Frees GPIO4, GPIO17, GPIO24 for other uses
- **Precise Control**: 12-bit resolution vs 8-bit GPIO PWM
- **Current Protection**: Isolates Raspberry Pi from servo power requirements
- **Expandability**: 13 additional channels for future enhancements
- **Reliability**: Dedicated PWM hardware reduces timing jitter
- **I2C Efficiency**: Single I2C interface controls all servos

## Force Feedback System

### Overview
The Force Feedback system calculates real-time steering resistance based on BMI160 sensor data (lateral G-forces and yaw rotation) and current steering wheel angle. This creates an immersive driving experience by simulating tire grip, road surface friction, vehicle dynamics, and self-aligning torque (centering force).

**Key Principle**: All calculations are performed **client-side** - the Raspberry Pi only sends raw BMI160 data, and the client processes it locally to compute force feedback values and control the ESP32 force feedback motor.

### Architecture

**Complete Data Flow:**
```
Raspberry Pi (BMI160) → Raw Sensor Data → Client PC → Local Calculation → ESP32 Motor Control
                         (accel_x/y/z,                  (G-forces +          (FF_MOTOR commands)
                          gyro_x/y/z)                    FF parameters)
                                                              ↓
                                              Visual Feedback + Motor PWM
                                              (LEDs + Intensity)  (BTS7960 H-Bridge)
```

**End-to-End System:**
```
BMI160 Sensor (Raspberry Pi) → UDP Network → Client Calculation → Serial USB → ESP32 FF Manager → BTS7960 → DC Motor
                                                      ↓
                                            ESP32 Steering Encoder (feedback loop)
```

**Calculation Pipeline:**
1. **Raw Data Reception**: Client receives `bmi160_accel_x/y/z` and `bmi160_gyro_x/y/z` from Raspberry Pi
2. **G-Force Calculation**: Convert acceleration to G-forces (`g = accel / 9.81`)
3. **Base Force Calculation**: Combine lateral G-force, yaw rotation, and steering angle (centering spring)
4. **Parameter Application**: Apply user-adjustable parameters (Sensitivity, Friction, Filter, Damping)
5. **Direction Detection**: Determine force direction based on centering force, lateral G-forces, and yaw rotation
6. **Serial Transmission**: Send `FF_MOTOR:direction:intensity` to ESP32 via USB serial
7. **Motor Control**: ESP32 controls BTS7960 H-bridge to apply physical force to steering wheel
8. **Visual Feedback**: Update LED indicators and intensity display on client interface

### Force Feedback Calculation

**Complete Formula:**
```python
# Step 1: Calculate G-forces from raw acceleration
g_force_lateral = accel_y / 9.81  # Lateral force (left/right in curves)
g_force_frontal = accel_x / 9.81  # Frontal force (acceleration/braking)

# Step 2: Calculate base force components (THREE sources)
# Component 1: Lateral G-forces (resistance in curves)
lateral_component = min(abs(g_force_lateral) * 50, 100)  # 0-100%

# Component 2: Yaw rotation (resistance to turning motion)
yaw_component = min(abs(gyro_z) / 60.0 * 50, 50)  # 0-50%

# Component 3: Centering spring (self-aligning torque)
# The further from center, the stronger the pull back to center
steering_value = sensor_data.get("steering", 0)  # -100 to +100
steering_angle_ratio = abs(steering_value) / 100.0  # 0.0 to 1.0
centering_component = steering_angle_ratio * 40  # 0-40% force

# Combine all three components
base_steering_ff = min(lateral_component + yaw_component + centering_component, 100)

# Step 3: Apply adjustable parameters (in order)
# 1. Sensitivity: Controls overall magnitude
adjusted_ff = base_steering_ff * (sensitivity / 100.0)

# 2. Friction: Adds resistance proportional to rotation speed
friction_force = min(abs(gyro_z) / 100.0, 1.0) * (friction / 100.0) * 30
adjusted_ff = min(adjusted_ff + friction_force, 100.0)

# 3. Filter: Removes high-frequency noise (exponential smoothing)
adjusted_ff = adjusted_ff * (1.0 - filter_strength) + last_filtered * filter_strength

# 4. Damping: Reduces sudden changes (moving average)
adjusted_ff = adjusted_ff * (1.0 - damping) + last_value * damping

# Final result: 0-100% intensity
final_steering_ff = max(0.0, min(100.0, adjusted_ff))

# Step 4: Calculate force direction (THREE factors combined)
# Factor 1: Centering force (always pulls toward center, opposite to current angle)
centering_direction_value = -steering_value  # Inverts the sign

# Factor 2: Lateral resistance (resists the turn direction)
lateral_direction_value = g_force_lateral * 10  # Amplified for weight

# Factor 3: Yaw resistance (resists rotation speed)
yaw_direction_value = gyro_z

# Combine all three factors to determine final direction
total_direction_value = centering_direction_value + lateral_direction_value + yaw_direction_value

# Determine direction: positive = right, negative = left
if total_direction_value > 5:
    direction = "right"
elif total_direction_value < -5:
    direction = "left"
else:
    direction = "neutral"

# Override to neutral if force is very weak
if final_steering_ff < 5.0:
    direction = "neutral"
```

### Adjustable Parameters

**1. Sensitivity (Sensibilidade)** - Default: 75%
- **Purpose**: Controls overall force magnitude
- **Range**: 0% (no force) to 100% (full force)
- **Effect**: Multiplies the base force directly
- **Use Case**:
  - Low (50%): Lighter steering for casual driving
  - Medium (75%): Balanced realistic feel
  - High (100%): Heavy steering for simulation

**2. Friction (Atrito)** - Default: 30%
- **Purpose**: Simulates tire friction and road grip
- **Range**: 0% (no friction) to 100% (maximum friction)
- **Effect**: Adds resistance proportional to rotation speed (up to +30% force)
- **Use Case**:
  - Low (10%): Arcade-style, easy steering
  - Medium (30%): Realistic tire grip
  - High (50%): Heavy, high-grip tires

**3. Filter (Filtro)** - Default: 40%
- **Purpose**: Removes sensor noise and vibrations
- **Range**: 0% (no filtering) to 100% (heavy smoothing)
- **Effect**: Exponential moving average (EMA) smoothing
- **Use Case**:
  - Low (20%): Instant response, may have jitter
  - Medium (40%): Smooth + responsive balance
  - High (60%): Very smooth, slight lag

**4. Damping (Amortecimento)** - Default: 50%
- **Purpose**: Simulates mechanical inertia
- **Range**: 0% (instant changes) to 100% (very slow transitions)
- **Effect**: Moving average to prevent abrupt changes
- **Use Case**:
  - Low (30%): Quick response, may oscillate
  - Medium (50%): Natural transitions
  - High (70%): Heavy, simulation-style feel

### Visual Feedback System

**LED Indicators:**
- **Left LED** (🟠 Orange): Lights when force pulls steering wheel left
  - Activated when: `g_force_lateral < 0` OR `gyro_z < 0` (counter-clockwise rotation)
  - Color: `#ffaa00` (amber/orange)

- **Right LED** (🔵 Cyan): Lights when force pulls steering wheel right
  - Activated when: `g_force_lateral > 0` OR `gyro_z > 0` (clockwise rotation)
  - Color: `#00aaff` (cyan/blue)

- **Neutral State**: Both LEDs off when intensity < 5%

**Intensity Display:**
- **Value**: 0-100% shown numerically
- **Color Coding**:
  - 🟢 Green (0-29%): Low force
  - 🟠 Orange (30-69%): Medium force
  - 🔴 Red (70-100%): High force

**Layout:**
```
🎯 Força no Volante: [🟠 LED] ← 0% → [🔵 LED]
                      Left      Value    Right
```

### Update Rate & Performance

- **Sensor Sampling**: 100Hz (BMI160 → Raspberry Pi → Client)
- **FF Calculation**: Every sensor update (~100Hz)
- **LED Update**: Immediate (no artificial delay)
- **Latency**: < 10ms from sensor reading to visual feedback
- **Thread-Safe**: All calculations in main event loop

### Physical Motor Control (ESP32 + BTS7960)

**Hardware Implementation:**
The force feedback system is fully implemented with a DC motor controlled by ESP32 via BTS7960 H-bridge driver.

**Serial Protocol (Client → ESP32):**
```
Format: FF_MOTOR:direction:intensity

Examples:
  FF_MOTOR:LEFT:45     - Apply 45% force counter-clockwise (pull wheel left)
  FF_MOTOR:RIGHT:80    - Apply 80% force clockwise (pull wheel right)
  FF_MOTOR:NEUTRAL:0   - Release wheel (no force)
```

**Client-Side Transmission:**
```python
# In console_interface.py (line 1874-1904)
def send_ff_command(self, intensity: float, direction: str):
    """Send Force Feedback command to ESP32 via serial"""
    direction_upper = direction.upper()  # LEFT, RIGHT, NEUTRAL
    intensity_int = int(intensity)       # 0-100
    command = f"FF_MOTOR:{direction_upper}:{intensity_int}"

    if hasattr(self, 'serial_manager') and self.serial_manager:
        self.serial_manager.send_command(command)
```

**ESP32-Side Control:**
```cpp
// In esp32.ino (line 181-194)
void process_serial_command(String command) {
    if (command.startsWith("FF_MOTOR:")) {
        int first_colon = command.indexOf(':', 9);
        int second_colon = command.indexOf(':', first_colon + 1);

        String direction = command.substring(first_colon + 1, second_colon);
        int intensity = command.substring(second_colon + 1).toInt();

        ff_motor.set_force(direction, intensity);  // Control BTS7960
    }
}
```

**BTS7960 H-Bridge Control:**
```cpp
// In ff_motor_manager.cpp
void FFMotorManager::set_force(String direction, int intensity) {
    int pwm_value = map(intensity, 0, 100, 0, 255);  // Convert to 8-bit PWM

    if (direction == "LEFT") {
        ledcWrite(PWM_CHANNEL_L, pwm_value);  // Counter-clockwise
        ledcWrite(PWM_CHANNEL_R, 0);
    } else if (direction == "RIGHT") {
        ledcWrite(PWM_CHANNEL_R, pwm_value);  // Clockwise
        ledcWrite(PWM_CHANNEL_L, 0);
    } else {  // NEUTRAL
        ledcWrite(PWM_CHANNEL_R, 0);
        ledcWrite(PWM_CHANNEL_L, 0);
    }
}
```

**Hardware Specifications:**
- **Motor Driver**: BTS7960 43A Dual H-Bridge
- **Microcontroller**: ESP32 DevKit V1 (240MHz dual-core)
- **ESP32 Pinout**:
  - GPIO 16: RPWM (Right PWM - clockwise rotation)
  - GPIO 17: LPWM (Left PWM - counter-clockwise rotation)
  - GPIO 18: R_EN (Right enable - always HIGH)
  - GPIO 19: L_EN (Left enable - always HIGH)
- **PWM Configuration**: 1kHz frequency, 8-bit resolution (0-255)
- **Power Supply**: 6V-27V motor power (depends on DC motor specs), 5V logic
- **Current Capacity**: Up to 43A continuous (BTS7960 rating)
- **Feedback Loop**: ESP32 steering encoder (GPIO 12/13) provides position feedback

### Implementation Files

**Client Side (Python):**
- **`console_interface.py`**:
  - `_calculate_g_forces_and_ff()`: Main FF calculation function (lines 1769-1847)
    - Calculates 3 force components: lateral G-forces, yaw rotation, centering spring
    - Applies 4 adjustable parameters: Sensitivity, Friction, Filter, Damping
    - Determines force direction based on 3 factors: centering, lateral, yaw
  - `send_ff_command()`: Serial transmission to ESP32 (lines 1874-1904)
    - Format: `FF_MOTOR:direction:intensity`
    - Sends at ~100Hz update rate
  - `update_ff_leds()`: LED and display update (lines 1833-1872)
  - `create_force_feedback_frame()`: UI components with LED indicators
  - Parameter sliders with real-time callbacks (Damping, Friction, Filter, Sensitivity)

- **`serial_receiver_manager.py`**:
  - Manages USB serial connection to ESP32
  - Sends FF_MOTOR commands via `send_command()`
  - Receives encoder data and calibration responses

**Raspberry Pi Side (Python):**
- **`bmi160_manager.py`**:
  - **NO force feedback calculation** - only reads raw sensor data
  - `get_sensor_data()`: Returns raw BMI160 values without processing
  - Sends: `bmi160_accel_x/y/z`, `bmi160_gyro_x/y/z`, `timestamp`, `sample_rate`

**ESP32 Side (C++):**
- **`esp32.ino`**:
  - `process_serial_command()`: Parses FF_MOTOR commands (lines 181-194)
  - `SerialTask()`: Handles bidirectional USB serial communication on Core 1
  - Updated header documentation with BTS7960 pinout (lines 19-23)

- **`ff_motor_manager.h/cpp`**:
  - `FFMotorManager` class for BTS7960 H-bridge control
  - `begin()`: Initializes GPIO pins and PWM channels
  - `set_force(direction, intensity)`: Controls motor direction and strength
  - `stop()`: Stops motor immediately
  - PWM channels: 0 (RPWM), 1 (LPWM) at 1kHz, 8-bit resolution
  - Pin definitions: GPIO 16/17 (PWM), GPIO 18/19 (Enable)

### Configuration Recommendations

**Realistic F1 Feel:**
```
Sensitivity: 75%
Friction: 30%
Filter: 40%
Damping: 50%
```

**Arcade Style (More Responsive):**
```
Sensitivity: 100%
Friction: 10%
Filter: 20%
Damping: 30%
```

**Simulation (Heavy/Realistic):**
```
Sensitivity: 60%
Friction: 50%
Filter: 50%
Damping: 70%
```

### Technical Notes

**Why Client-Side Processing?**
1. **Reduced Network Traffic**: Only raw data transmitted (6 floats vs calculated values)
2. **Adjustable in Real-Time**: User can change parameters without ESP32/RPi communication
3. **No Latency Penalty**: Calculation is fast (<1ms on modern PC)
4. **Separation of Concerns**: Raspberry Pi focuses on data acquisition, client handles presentation

**Direction Detection Logic:**
The direction is determined by **combining three factors**:

1. **Centering Force** (Self-Aligning Torque):
   - Always pulls toward center (opposite to current steering angle)
   - If steering is left (-50%), centering force is right (+50)
   - If steering is right (+70%), centering force is left (-70)
   - Formula: `centering_direction_value = -steering_value`

2. **Lateral Resistance** (G-Force):
   - Resists the turn direction based on lateral acceleration
   - Amplified by factor of 10 for proper weighting
   - Formula: `lateral_direction_value = g_force_lateral * 10`

3. **Yaw Resistance** (Rotation Rate):
   - Resists rotational motion based on yaw rate
   - Formula: `yaw_direction_value = gyro_z`

**Combined Direction Calculation:**
```python
total_direction_value = centering_direction_value + lateral_direction_value + yaw_direction_value

if total_direction_value > 5:
    direction = "right"    # Motor pulls clockwise
elif total_direction_value < -5:
    direction = "left"     # Motor pulls counter-clockwise
else:
    direction = "neutral"  # Motor released
```

**Practical Examples:**

1. **Steering left (-60%), car stationary:**
   - Centering: +60 (pulls right to center)
   - Lateral: 0
   - Yaw: 0
   - **Result**: Motor pulls RIGHT (back to center)

2. **Steering centered (0%), turning right in curve:**
   - Centering: 0
   - Lateral: +positive (G-force to left)
   - Yaw: +positive (rotating clockwise)
   - **Result**: Motor resists turn (pulls LEFT)

3. **Steering right (+80%), exiting curve:**
   - Centering: -80 (pulls left to center)
   - Lateral: -negative (G-force reversing)
   - Yaw: -negative (rotation slowing)
   - **Result**: Motor pulls LEFT (helps return to center)

This creates a realistic self-aligning torque effect where:
- **Steering wheel naturally returns to center** when released
- **Resistance increases with steering angle** (progressive feel)
- **Force feedback matches vehicle dynamics** (turning, grip, weight transfer)