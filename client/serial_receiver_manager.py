#!/usr/bin/env python3
"""
serial_receiver_manager.py - Serial Receiver Manager
Responsible for receiving serial commands from Arduino Mega cockpit

This module receives cockpit control commands from Arduino Mega via USB serial
and forwards them to the Raspberry Pi via the network client.

Protocol Format (received from Arduino Mega):
- THROTTLE:<value>   (0-100%)
- BRAKE:<value>      (0-100%)
- STEERING:<value>   (-100 to +100%)
- GEAR_UP
- GEAR_DOWN

Connection:
- Arduino Mega USB → /dev/ttyACM0 or /dev/ttyUSB0 (Linux)
- COM Port (Windows)
- Baud rate: 115200

@author F1 RC Car Project
@date 2025-10-09
"""

import serial
import serial.tools.list_ports
import threading
import time
from typing import Optional, Callable


class SerialReceiverManager:
    """Serial receiver for Arduino Mega cockpit commands"""

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = 115200,
        timeout: float = 1.0,
        command_callback: Optional[Callable[[str, str], None]] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Initialize serial receiver

        Args:
            port: Serial port (auto-detect if None)
            baud_rate: Communication baud rate (default: 115200)
            timeout: Read timeout in seconds
            command_callback: Callback function(command_type, value)
            log_callback: Callback function(level, message)
        """
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.command_callback = command_callback
        self.log_callback = log_callback

        # Serial connection
        self.serial_conn: Optional[serial.Serial] = None
        self.is_running = False
        self.receiver_thread: Optional[threading.Thread] = None

        # Statistics
        self.commands_received = 0
        self.last_command_time = 0.0
        self.errors = 0

        # Last values for change detection
        self.last_throttle = -1
        self.last_brake = -1
        self.last_steering = 0

    def _log(self, level: str, message: str):
        """Send log message"""
        if self.log_callback:
            self.log_callback(level, message)
        else:
            print(f"[{level}] {message}")

    def list_available_ports(self) -> list:
        """
        List all available serial ports with descriptions

        Returns:
            list: List of tuples (port_device, port_description)
        """
        ports = serial.tools.list_ports.comports()
        available_ports = []

        for port in ports:
            description = f"{port.device}"
            if port.description:
                description += f" - {port.description}"
            if port.manufacturer:
                description += f" ({port.manufacturer})"
            available_ports.append((port.device, description))

        return available_ports

    def auto_detect_port(self) -> Optional[str]:
        """
        Auto-detect ESP32 serial port

        Returns:
            str: Detected port or None
        """
        self._log("INFO", "Auto-detecting ESP32 port...")

        # List all available serial ports
        ports = serial.tools.list_ports.comports()

        # Look for ESP32 (VID:PID varies by manufacturer)
        for port in ports:
            # Check for common ESP32 vendor/product IDs
            # Silicon Labs CP2102: 0x10C4:0xEA60
            # FTDI FT232: 0x0403:0x6001
            # CH340: 0x1A86:0x7523
            if port.vid in [0x10C4, 0x0403, 0x1A86]:
                self._log("INFO", f"Found ESP32-like device at {port.device}")
                return port.device

            # Fallback: check description
            if "CP210" in port.description or "CH340" in port.description or "FTDI" in port.description:
                self._log("INFO", f"Found ESP32-like device at {port.device}")
                return port.device

        # If no ESP32 found, try common ports
        common_ports = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1"]
        for common_port in common_ports:
            try:
                test_serial = serial.Serial(common_port, self.baud_rate, timeout=0.5)
                test_serial.close()
                self._log("INFO", f"Found serial port at {common_port}")
                return common_port
            except:
                continue

        self._log("WARN", "Could not auto-detect ESP32 port")
        return None

    def connect_to_port(self, port: str) -> bool:
        """
        Connect to a specific serial port

        Args:
            port: Serial port device path

        Returns:
            bool: True if connected successfully
        """
        try:
            # Close existing connection if any
            if self.serial_conn:
                try:
                    self.serial_conn.close()
                except:
                    pass
                self.serial_conn = None

            # Set new port
            self.port = port

            # Open serial connection
            self._log("INFO", f"Connecting to ESP32 at {self.port}")
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                write_timeout=1.0,
            )

            # Wait for ESP32 to reset (DTR causes reset)
            time.sleep(2.0)

            # Flush any startup garbage
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()

            self._log("INFO", f"Connected to ESP32 at {self.port}")
            return True

        except serial.SerialException as e:
            self._log("ERROR", f"Failed to connect to {self.port}: {e}")
            return False
        except Exception as e:
            self._log("ERROR", f"Unexpected error during connection: {e}")
            return False

    def connect(self) -> bool:
        """
        Connect to ESP32 serial port (auto-detect if not specified)

        Returns:
            bool: True if connected successfully
        """
        try:
            # Auto-detect port if not specified
            if not self.port:
                self.port = self.auto_detect_port()

            if not self.port:
                self._log("ERROR", "No serial port specified or detected")
                return False

            # Use connect_to_port for actual connection
            return self.connect_to_port(self.port)

        except Exception as e:
            self._log("ERROR", f"Unexpected error during connection: {e}")
            return False

    def parse_command(self, line: str):
        """
        Parse command received from Arduino Mega

        Args:
            line: Command line string
        """
        try:
            line = line.strip()
            if not line:
                return

            # Log raw command for debugging
            # self._log("DEBUG", f"Received: {line}")

            # Parse different command types
            if line.startswith("THROTTLE:"):
                value = int(line.split(":")[1])
                if value != self.last_throttle:
                    self.last_throttle = value
                    if self.command_callback:
                        self.command_callback("THROTTLE", str(value))
                    self._log("INFO", f"🎮 Throttle: {value}%")

            elif line.startswith("BRAKE:"):
                value = int(line.split(":")[1])
                if value != self.last_brake:
                    self.last_brake = value
                    if self.command_callback:
                        self.command_callback("BRAKE", str(value))
                    self._log("INFO", f"🎮 Brake: {value}%")

            elif line.startswith("STEERING:"):
                value = int(line.split(":")[1])
                if value != self.last_steering:
                    self.last_steering = value
                    if self.command_callback:
                        self.command_callback("STEERING", str(value))
                    self._log("INFO", f"🎮 Steering: {value:+d}%")

            elif line == "GEAR_UP":
                if self.command_callback:
                    self.command_callback("GEAR_UP", "")
                self._log("INFO", "🎮 Gear Up")

            elif line == "GEAR_DOWN":
                if self.command_callback:
                    self.command_callback("GEAR_DOWN", "")
                self._log("INFO", "🎮 Gear Down")

            else:
                # Unknown command or system message
                if not line.startswith("F1 Cockpit") and not line.startswith("Arduino"):
                    self._log("WARN", f"Unknown command: {line}")

            self.commands_received += 1
            self.last_command_time = time.time()

        except Exception as e:
            self._log("ERROR", f"Error parsing command '{line}': {e}")
            self.errors += 1

    def receiver_loop(self):
        """Main receiver loop (runs in separate thread)"""
        self._log("INFO", "Serial receiver loop started")

        while self.is_running:
            try:
                # Read line from serial
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode("utf-8", errors="ignore")
                    self.parse_command(line)
                else:
                    # Small sleep to prevent CPU spinning
                    time.sleep(0.01)

            except serial.SerialException as e:
                self._log("ERROR", f"Serial connection error: {e}")
                break
            except Exception as e:
                self._log("ERROR", f"Error in receiver loop: {e}")
                self.errors += 1
                time.sleep(0.1)

        self._log("INFO", "Serial receiver loop stopped")

    def start(self) -> bool:
        """
        Start receiving serial commands

        Returns:
            bool: True if started successfully
        """
        if self.is_running:
            self._log("WARN", "Serial receiver already running")
            return False

        # Connect to serial port
        if not self.serial_conn:
            if not self.connect():
                return False

        # Start receiver thread
        self.is_running = True
        self.receiver_thread = threading.Thread(target=self.receiver_loop, daemon=True)
        self.receiver_thread.start()

        self._log("INFO", "Serial receiver started")
        return True

    def stop(self):
        """Stop receiving serial commands"""
        self._log("INFO", "Stopping serial receiver...")

        self.is_running = False

        # Wait for thread to finish
        if self.receiver_thread and self.receiver_thread.is_alive():
            self.receiver_thread.join(timeout=2.0)

        # Close serial connection
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except:
                pass
            self.serial_conn = None

        self._log("INFO", f"Serial receiver stopped - {self.commands_received} commands received")

    def get_statistics(self) -> dict:
        """
        Get receiver statistics

        Returns:
            dict: Statistics dictionary
        """
        return {
            "port": self.port,
            "baud_rate": self.baud_rate,
            "connected": self.serial_conn is not None and self.serial_conn.is_open,
            "running": self.is_running,
            "commands_received": self.commands_received,
            "errors": self.errors,
            "last_command_time": self.last_command_time,
        }

    def is_connected(self) -> bool:
        """Check if serial connection is active"""
        return self.serial_conn is not None and self.serial_conn.is_open
