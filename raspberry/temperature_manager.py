#!/usr/bin/env python3
"""
Temperature Manager - DS18B20 Digital Temperature Sensor Control

Manages DS18B20 temperature sensor for F1 remote-controlled car system.
Provides real-time temperature monitoring for system thermal management.

PINOUT DS18B20 -> RASPBERRY PI 4:
=================================
DS18B20 (TO-92 package) -> Raspberry Pi 4 (GPIO)
  - Pino 1 (GND)   -> Pin 6  (GND)
  - Pino 2 (DQ)    -> Pin 7  (GPIO4) + Resistor pull-up 4.7kΩ para 3.3V
  - Pino 3 (VDD)   -> Pin 1  (3.3V)

Circuito com Pull-up:
    3.3V (Pin 1) ─── 4.7kΩ ───┬─── GPIO4 (Pin 7)
                              │
                          DS18B20 DQ
                              │
                             GND

CARACTERÍSTICAS DS18B20:
========================
- Tensão: 3V a 5.5V DC
- Faixa de medição: -55°C a +125°C (recomendado até 100°C)
- Precisão: ±0.5°C (-10°C a +85°C)
- Resolução: 9 ou 12 bits (configurável)
- Tempo de conversão: < 750ms (12 bits)
- Protocolo: 1-Wire (Dallas/Maxim)
- Endereçamento: Cada sensor tem ID único de 64 bits

MAPEAMENTO DE PINOS OCUPADOS:
=============================
- GPIO4 (Pin 7) -> DS18B20 Data (1-Wire) - OCUPADO

PINOS UTILIZADOS POR OUTROS COMPONENTES:
=========================================
- GPIO2 (Pin 3)  -> I2C SDA (BMI160, PCA9685, ADS1115, INA219)
- GPIO3 (Pin 5)  -> I2C SCL (BMI160, PCA9685, ADS1115, INA219)
- GPIO18 (Pin 12) -> Motor BTS7960 RPWM
- GPIO27 (Pin 13) -> Motor BTS7960 LPWM
- GPIO22 (Pin 15) -> Motor BTS7960 R_EN
- GPIO23 (Pin 16) -> Motor BTS7960 L_EN
- Slot CSI        -> Câmera OV5647

CONFIGURAÇÃO NECESSÁRIA:
========================
1. Habilitar 1-Wire no Raspberry Pi:
   sudo raspi-config -> Interface Options -> 1-Wire -> Enable

2. Adicionar ao /boot/config.txt (já feito pelo raspi-config):
   dtoverlay=w1-gpio,gpiopin=4

3. Carregar módulos do kernel (automático após reboot):
   sudo modprobe w1-gpio
   sudo modprobe w1-therm

4. Verificar se sensor foi detectado:
   ls /sys/bus/w1/devices/
   # Deve aparecer algo como: 28-xxxxxxxxxxxx

5. Ler temperatura manualmente (teste):
   cat /sys/bus/w1/devices/28-*/w1_slave
"""

import glob
import os
import threading
import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, Optional

from logger import debug, error, info, warn


class TemperatureUnit(Enum):
    """Temperature unit enumeration"""

    CELSIUS = "C"
    FAHRENHEIT = "F"
    KELVIN = "K"


@dataclass
class TemperatureReading:
    """Temperature reading data structure"""

    temperature_c: float
    temperature_f: float
    temperature_k: float
    sensor_id: str
    timestamp: float
    is_valid: bool


class TemperatureManager:
    """
    DS18B20 Temperature Sensor Manager

    Handles communication with DS18B20 digital temperature sensor using
    1-Wire protocol through Linux kernel w1 driver interface.

    Features:
    - Real-time temperature monitoring
    - Multiple temperature units (°C, °F, K)
    - Configurable sampling rate
    - Temperature history tracking
    - Thermal event detection (overheating alerts)
    - Thread-safe operations
    """

    # DS18B20 Constants
    DS18B20_BASE_DIR = "/sys/bus/w1/devices/"
    DS18B20_DEVICE_FOLDER = "28-*"  # DS18B20 device ID pattern
    DS18B20_DEVICE_FILE = "w1_slave"

    # Temperature thresholds (°C)
    TEMP_WARNING_THRESHOLD = 65.0  # CPU temperature warning
    TEMP_CRITICAL_THRESHOLD = 80.0  # CPU temperature critical
    TEMP_SHUTDOWN_THRESHOLD = 85.0  # Emergency shutdown temperature

    def __init__(
        self,
        gpio_pin: int = 4,
        sampling_rate: float = 1.0,
        enable_history: bool = True,
        history_size: int = 100,
    ):
        """
        Initialize Temperature Manager

        Args:
            gpio_pin: GPIO pin number for DS18B20 data line (default: 4 - Pin 7)
            sampling_rate: Temperature sampling rate in Hz (default: 1.0)
            enable_history: Enable temperature history tracking
            history_size: Maximum number of historical readings to store
        """
        self.gpio_pin = gpio_pin
        self.sampling_rate = sampling_rate
        self.sampling_interval = 1.0 / sampling_rate
        self.enable_history = enable_history
        self.history_size = history_size

        # Sensor state
        self.is_initialized = False
        self.is_running = False
        self.sensor_detected = False
        self.device_file_path = None
        self.sensor_id = None

        # Current readings
        self.current_temperature_c = 0.0
        self.current_temperature_f = 32.0
        self.current_temperature_k = 273.15
        self.last_reading_time = 0.0
        self.reading_count = 0

        # Temperature history
        self.temperature_history = []
        self.min_temperature = float("inf")
        self.max_temperature = float("-inf")
        self.avg_temperature = 0.0

        # Threading
        self.temperature_thread = None
        self.thread_lock = threading.Lock()

        # Status tracking
        self.last_warning_time = 0.0
        self.warning_cooldown = 30.0  # 30 seconds between warnings

        info(
            f"TemperatureManager inicializado - GPIO{self.gpio_pin} @ {self.sampling_rate}Hz",
            "TEMP",
        )

    def initialize(self) -> bool:
        """
        Initialize DS18B20 temperature sensor

        Returns:
            bool: True if initialization successful
        """
        try:
            info("Inicializando sensor DS18B20...", "TEMP")

            # Enable 1-Wire interface (requires modprobe w1-gpio w1-therm)
            if not self._enable_1wire_interface():
                error("Falha ao habilitar interface 1-Wire", "TEMP")
                return False

            # Detect DS18B20 sensor
            if not self._detect_sensor():
                error("Sensor DS18B20 não detectado", "TEMP")
                return False

            # Validate sensor communication
            if not self._validate_sensor():
                error("Falha na validação do sensor DS18B20", "TEMP")
                return False

            self.is_initialized = True
            info(
                f"Sensor DS18B20 inicializado com sucesso - ID: {self.sensor_id}",
                "TEMP",
            )

            # Start temperature monitoring thread
            self.start_monitoring()

            return True

        except Exception as e:
            error(f"Erro na inicialização do DS18B20: {e}", "TEMP")
            return False

    def _enable_1wire_interface(self) -> bool:
        """
        Enable 1-Wire kernel modules for DS18B20

        Returns:
            bool: True if 1-Wire interface enabled successfully
        """
        try:
            # Load required kernel modules
            os.system("sudo modprobe w1-gpio")
            os.system("sudo modprobe w1-therm")
            time.sleep(2.0)  # Wait for modules to load

            # Check if w1 devices directory exists
            if not os.path.exists(self.DS18B20_BASE_DIR):
                warn("Diretório /sys/bus/w1/devices/ não encontrado", "TEMP")
                return False

            debug("Interface 1-Wire habilitada", "TEMP")
            return True

        except Exception as e:
            error(f"Erro ao habilitar interface 1-Wire: {e}", "TEMP")
            return False

    def _detect_sensor(self) -> bool:
        """
        Detect DS18B20 sensor on 1-Wire bus

        Returns:
            bool: True if sensor detected
        """
        try:
            # Search for DS18B20 devices (ID pattern: 28-xxxxxxxxxxxx)
            device_folders = glob.glob(
                os.path.join(self.DS18B20_BASE_DIR, self.DS18B20_DEVICE_FOLDER)
            )

            if not device_folders:
                warn("Nenhum sensor DS18B20 detectado no barramento 1-Wire", "TEMP")
                return False

            # Use first detected sensor
            device_folder = device_folders[0]
            self.device_file_path = os.path.join(
                device_folder, self.DS18B20_DEVICE_FILE
            )
            self.sensor_id = os.path.basename(device_folder)

            # Verify device file exists
            if not os.path.exists(self.device_file_path):
                error(
                    f"Arquivo do dispositivo não encontrado: {self.device_file_path}",
                    "TEMP",
                )
                return False

            self.sensor_detected = True
            info(f"Sensor DS18B20 detectado: {self.sensor_id}", "TEMP")
            return True

        except Exception as e:
            error(f"Erro na detecção do sensor: {e}", "TEMP")
            return False

    def _validate_sensor(self) -> bool:
        """
        Validate sensor communication by reading temperature

        Returns:
            bool: True if sensor validation successful
        """
        try:
            # Attempt to read temperature
            reading = self._read_temperature_raw()

            if reading is None:
                error("Falha na leitura de validação do sensor", "TEMP")
                return False

            # Check if temperature is within reasonable range (-55°C to +125°C)
            if -55.0 <= reading.temperature_c <= 125.0:
                info(
                    f"Sensor validado - Temperatura inicial: {reading.temperature_c:.1f}°C",
                    "TEMP",
                )
                return True
            else:
                error(
                    f"Temperatura fora da faixa válida: {reading.temperature_c:.1f}°C",
                    "TEMP",
                )
                return False

        except Exception as e:
            error(f"Erro na validação do sensor: {e}", "TEMP")
            return False

    def _read_temperature_raw(self) -> Optional[TemperatureReading]:
        """
        Read raw temperature data from DS18B20

        Returns:
            Optional[TemperatureReading]: Temperature reading or None if failed
        """
        try:
            if not self.device_file_path or not os.path.exists(self.device_file_path):
                return None

            # Read raw data from device file
            with open(self.device_file_path, "r") as f:
                lines = f.readlines()

            # Validate CRC (first line should end with 'YES')
            if len(lines) < 2 or "YES" not in lines[0]:
                debug("Falha na verificação CRC - tentando novamente", "TEMP")
                return None

            # Extract temperature from second line
            temp_line = lines[1]
            temp_start = temp_line.find("t=")

            if temp_start == -1:
                debug("Formato de temperatura inválido", "TEMP")
                return None

            # Parse temperature (in millidegrees Celsius)
            temp_string = temp_line[temp_start + 2 :]
            temp_millidegrees = int(temp_string)
            temp_celsius = temp_millidegrees / 1000.0

            # Convert to other units
            temp_fahrenheit = (temp_celsius * 9.0 / 5.0) + 32.0
            temp_kelvin = temp_celsius + 273.15

            # Create temperature reading
            reading = TemperatureReading(
                temperature_c=temp_celsius,
                temperature_f=temp_fahrenheit,
                temperature_k=temp_kelvin,
                sensor_id=self.sensor_id,
                timestamp=time.time(),
                is_valid=True,
            )

            return reading

        except Exception as e:
            debug(f"Erro na leitura de temperatura: {e}", "TEMP")
            return None

    def start_monitoring(self):
        """Start temperature monitoring in background thread"""
        if self.is_running or not self.is_initialized:
            return

        self.is_running = True
        self.temperature_thread = threading.Thread(
            target=self._monitoring_loop, daemon=True
        )
        self.temperature_thread.start()

        info(f"Monitoramento de temperatura iniciado @ {self.sampling_rate}Hz", "TEMP")

    def stop_monitoring(self):
        """Stop temperature monitoring"""
        self.is_running = False

        if self.temperature_thread and self.temperature_thread.is_alive():
            self.temperature_thread.join(timeout=2.0)

        info("Monitoramento de temperatura parado", "TEMP")

    def _monitoring_loop(self):
        """Main temperature monitoring loop"""
        while self.is_running:
            try:
                loop_start = time.time()

                # Read temperature
                reading = self._read_temperature_raw()

                if reading and reading.is_valid:
                    with self.thread_lock:
                        # Update current values
                        self.current_temperature_c = reading.temperature_c
                        self.current_temperature_f = reading.temperature_f
                        self.current_temperature_k = reading.temperature_k
                        self.last_reading_time = reading.timestamp
                        self.reading_count += 1

                        # Update statistics
                        self._update_statistics(reading.temperature_c)

                        # Add to history
                        if self.enable_history:
                            self._add_to_history(reading)

                        # Check thermal alerts
                        self._check_thermal_alerts(reading.temperature_c)

                # Maintain sampling rate
                elapsed = time.time() - loop_start
                sleep_time = max(0, self.sampling_interval - elapsed)
                if sleep_time > 0:
                    time.sleep(sleep_time)

            except Exception as e:
                error(f"Erro no loop de monitoramento: {e}", "TEMP")
                time.sleep(1.0)  # Error recovery delay

    def _update_statistics(self, temperature: float):
        """Update temperature statistics"""
        self.min_temperature = min(self.min_temperature, temperature)
        self.max_temperature = max(self.max_temperature, temperature)

        # Calculate rolling average
        if self.reading_count == 1:
            self.avg_temperature = temperature
        else:
            alpha = 0.1  # Smoothing factor
            self.avg_temperature = (alpha * temperature) + (
                (1 - alpha) * self.avg_temperature
            )

    def _add_to_history(self, reading: TemperatureReading):
        """Add reading to temperature history"""
        self.temperature_history.append(reading)

        # Maintain history size limit
        if len(self.temperature_history) > self.history_size:
            self.temperature_history.pop(0)

    def _check_thermal_alerts(self, temperature: float):
        """Check for thermal alert conditions"""
        current_time = time.time()

        # Only send warnings with cooldown period
        if current_time - self.last_warning_time < self.warning_cooldown:
            return

        if temperature >= self.TEMP_SHUTDOWN_THRESHOLD:
            error(
                f"TEMPERATURA CRÍTICA: {temperature:.1f}°C - SHUTDOWN RECOMENDADO!",
                "TEMP",
            )
            self.last_warning_time = current_time
        elif temperature >= self.TEMP_CRITICAL_THRESHOLD:
            error(f"Temperatura crítica: {temperature:.1f}°C", "TEMP")
            self.last_warning_time = current_time
        elif temperature >= self.TEMP_WARNING_THRESHOLD:
            warn(f"Temperatura elevada: {temperature:.1f}°C", "TEMP")
            self.last_warning_time = current_time

    def get_temperature(self, unit: TemperatureUnit = TemperatureUnit.CELSIUS) -> float:
        """
        Get current temperature in specified unit

        Args:
            unit: Temperature unit (CELSIUS, FAHRENHEIT, KELVIN)

        Returns:
            float: Current temperature in specified unit
        """
        with self.thread_lock:
            if unit == TemperatureUnit.CELSIUS:
                return self.current_temperature_c
            elif unit == TemperatureUnit.FAHRENHEIT:
                return self.current_temperature_f
            elif unit == TemperatureUnit.KELVIN:
                return self.current_temperature_k
            else:
                return self.current_temperature_c

    def get_temperature_status(self) -> Dict[str, Any]:
        """
        Get comprehensive temperature status

        Returns:
            Dict[str, Any]: Temperature status data
        """
        with self.thread_lock:
            return {
                "is_initialized": self.is_initialized,
                "sensor_detected": self.sensor_detected,
                "sensor_id": self.sensor_id,
                "gpio_pin": self.gpio_pin,
                "sampling_rate": self.sampling_rate,
                # Current readings
                "temperature_c": round(self.current_temperature_c, 2),
                "temperature_f": round(self.current_temperature_f, 2),
                "temperature_k": round(self.current_temperature_k, 2),
                "last_reading_time": self.last_reading_time,
                "reading_count": self.reading_count,
                # Statistics
                "min_temperature_c": (
                    round(self.min_temperature, 2)
                    if self.min_temperature != float("inf")
                    else None
                ),
                "max_temperature_c": (
                    round(self.max_temperature, 2)
                    if self.max_temperature != float("-inf")
                    else None
                ),
                "avg_temperature_c": round(self.avg_temperature, 2),
                # Status indicators
                "is_warning": self.current_temperature_c >= self.TEMP_WARNING_THRESHOLD,
                "is_critical": self.current_temperature_c
                >= self.TEMP_CRITICAL_THRESHOLD,
                "thermal_status": self._get_thermal_status(),
                "uptime": (
                    time.time()
                    - (
                        self.last_reading_time
                        - (self.reading_count * self.sampling_interval)
                    )
                    if self.reading_count > 0
                    else 0
                ),
                "last_update": time.time(),
            }

    def _get_thermal_status(self) -> str:
        """Get thermal status string"""
        temp = self.current_temperature_c

        if temp >= self.TEMP_SHUTDOWN_THRESHOLD:
            return "CRITICAL_SHUTDOWN"
        elif temp >= self.TEMP_CRITICAL_THRESHOLD:
            return "CRITICAL"
        elif temp >= self.TEMP_WARNING_THRESHOLD:
            return "WARNING"
        else:
            return "NORMAL"

    def get_temperature_history(self, count: int = None) -> list:
        """
        Get temperature history

        Args:
            count: Number of recent readings to return (None for all)

        Returns:
            list: List of temperature readings
        """
        with self.thread_lock:
            if count is None:
                return self.temperature_history.copy()
            else:
                return (
                    self.temperature_history[-count:].copy()
                    if self.temperature_history
                    else []
                )

    def reset_statistics(self):
        """Reset temperature statistics"""
        with self.thread_lock:
            self.min_temperature = float("inf")
            self.max_temperature = float("-inf")
            self.avg_temperature = 0.0
            self.reading_count = 0
            self.temperature_history.clear()

        info("Estatísticas de temperatura redefinidas", "TEMP")

    def shutdown(self):
        """Shutdown temperature manager"""
        info("Desligando TemperatureManager...", "TEMP")
        self.stop_monitoring()
        self.is_initialized = False
        info("TemperatureManager desligado", "TEMP")
