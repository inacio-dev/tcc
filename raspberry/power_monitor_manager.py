#!/usr/bin/env python3
"""
power_monitor_manager.py - Monitoramento de Energia do Sistema F1 Car

Gerencia a leitura de tensão e corrente de múltiplos pontos do sistema:
- INA219: Tensão e corrente do Raspberry Pi (5V após XL4015)
- ADS1115 + ACS758: Correntes dos subsistemas (motor, servos, RPi)

CONFIGURAÇÃO DE HARDWARE:
=========================
ADS1115 (ADC 16-bit I2C):
- Endereço I2C: 0x48 (ADDR → GND)
- Canal A0: ACS758 50A  → Corrente XL4015 (Raspberry Pi)
- Canal A1: ACS758 50A  → Corrente UBEC (Servos PCA9685)
- Canal A2: ACS758 100A → Corrente Motor DC 775
- Canal A3: Livre (pode ser usado para tensão bateria com divisor)

INA219 (I2C):
- Endereço I2C: 0x41 (A0=VCC para evitar conflito com PCA9685)
- Mede tensão (0-26V) e corrente (±3.2A) na entrada 5V do Raspberry Pi

PINOUT RASPBERRY PI 4:
=====================
- SDA → GPIO2 (Pin 3)  [Compartilhado com BMI160, PCA9685]
- SCL → GPIO3 (Pin 5)  [Compartilhado com BMI160, PCA9685]

CARACTERÍSTICAS DOS SENSORES ACS758:
===================================
- ACS758 50A (ACS758LCB-050B):
  - Sensibilidade: 40 mV/A
  - Vref (zero current): VCC/2 = 2.5V @ 5V
  - Faixa: ±50A

- ACS758 100A (ACS758LCB-100B):
  - Sensibilidade: 20 mV/A
  - Vref (zero current): VCC/2 = 2.5V @ 5V
  - Faixa: ±100A

FILTRO RC RECOMENDADO (hardware):
=================================
Para cada ACS758, adicionar filtro passa-baixa:

    ACS758 OUT ──┬── 1kΩ ──┬── ADS1115 (Ax)
                 │         │
                GND      100nF
                           │
                          GND

- Resistor: 1kΩ (limita corrente + filtro)
- Capacitor: 100nF (filtra ruído PWM)
- Frequência de corte: ~1.6 kHz

FILTROS DE SOFTWARE (este módulo):
==================================
1. Média Móvel (buffer_size amostras)
2. Filtro EMA (Exponential Moving Average)
3. Filtro de Mediana (rejeita spikes/outliers)
"""

import threading
import time
from collections import deque
from statistics import median
from typing import Any, Dict, Optional


class PowerMonitorManager:
    """Gerencia monitoramento de energia do sistema F1 Car"""

    # Endereços I2C
    ADS1115_ADDRESS = 0x48  # ADDR → GND
    INA219_ADDRESS = 0x41  # A0=VCC para evitar conflito com PCA9685 (0x40)

    # Registradores ADS1115
    ADS1115_REG_CONVERSION = 0x00
    ADS1115_REG_CONFIG = 0x01

    # Configuração ADS1115
    # OS=1 (start), MUX=100 (AIN0), PGA=001 (±4.096V), MODE=1 (single-shot)
    # DR=100 (128SPS), COMP_MODE=0, COMP_POL=0, COMP_LAT=0, COMP_QUE=11
    ADS1115_CONFIG_BASE = 0x8583  # Single-shot, ±4.096V, 128SPS

    # MUX bits para cada canal (bits 14:12)
    ADS1115_MUX_AIN0 = 0x4000  # Canal 0
    ADS1115_MUX_AIN1 = 0x5000  # Canal 1
    ADS1115_MUX_AIN2 = 0x6000  # Canal 2
    ADS1115_MUX_AIN3 = 0x7000  # Canal 3

    # Registradores INA219
    INA219_REG_CONFIG = 0x00
    INA219_REG_SHUNT_VOLTAGE = 0x01
    INA219_REG_BUS_VOLTAGE = 0x02
    INA219_REG_POWER = 0x03
    INA219_REG_CURRENT = 0x04
    INA219_REG_CALIBRATION = 0x05

    # Configuração INA219 (32V, 3.2A range)
    INA219_CONFIG_32V_3A2 = 0x399F

    # Características dos sensores ACS758
    ACS758_50A_SENSITIVITY = 0.040  # 40 mV/A
    ACS758_100A_SENSITIVITY = 0.020  # 20 mV/A
    ACS758_VREF = 2.5  # VCC/2 @ 5V (tensão em 0A)

    # Fator de escala ADS1115 (±4.096V, 16-bit signed)
    ADS1115_SCALE = 4.096 / 32768.0  # V/LSB

    # Calibração INA219 (shunt 0.1Ω, max 3.2A)
    INA219_CALIBRATION = 4096
    INA219_CURRENT_LSB = 0.0001  # 0.1mA/bit

    def __init__(
        self,
        sample_rate: int = 10,
        buffer_size: int = 20,
        ads1115_address: int = None,
        ina219_address: int = None,
    ):
        """
        Inicializa o gerenciador de monitoramento de energia

        Args:
            sample_rate (int): Taxa de amostragem em Hz (1-100)
            buffer_size (int): Tamanho do buffer para médias móveis
            ads1115_address (int): Endereço I2C do ADS1115 (padrão 0x48)
            ina219_address (int): Endereço I2C do INA219 (padrão 0x40)
        """
        self.sample_rate = min(max(sample_rate, 1), 100)
        self.buffer_size = buffer_size

        self.ads1115_address = ads1115_address or self.ADS1115_ADDRESS
        self.ina219_address = ina219_address or self.INA219_ADDRESS

        # Lock para thread-safety (acesso concorrente por threads de energia e TX)
        self.state_lock = threading.Lock()

        # Barramento I2C
        self.i2c_bus = None
        self.is_initialized = False
        self.ads1115_available = False
        self.ina219_available = False

        # Dados de corrente (ACS758 via ADS1115)
        self.current_rpi = 0.0  # Corrente XL4015 → RPi (A)
        self.current_servos = 0.0  # Corrente UBEC → Servos (A)
        self.current_motor = 0.0  # Corrente Motor DC 775 (A)

        # Dados de tensão/corrente (INA219)
        self.voltage_rpi = 0.0  # Tensão entrada RPi (V)
        self.current_rpi_ina = 0.0  # Corrente RPi via INA219 (A)
        self.power_rpi = 0.0  # Potência RPi (W)

        # Valores raw do ADS1115
        self.raw_rpi = 0
        self.raw_servos = 0
        self.raw_motor = 0

        # Buffers para média móvel
        self.buffer_current_rpi = deque(maxlen=buffer_size)
        self.buffer_current_servos = deque(maxlen=buffer_size)
        self.buffer_current_motor = deque(maxlen=buffer_size)
        self.buffer_voltage_rpi = deque(maxlen=buffer_size)

        # Estatísticas
        self.readings_count = 0
        self.errors_count = 0
        self.start_time = time.time()
        self.last_update = time.time()

        # Calibração (offsets em Volts para ajustar Vref real)
        self.offset_rpi = 0.0
        self.offset_servos = 0.0
        self.offset_motor = 0.0

        # Filtros EMA (Exponential Moving Average)
        # Alpha: 0.0 = sem filtro, 1.0 = máximo (só valor anterior)
        # Valor típico: 0.1-0.3 para suavização moderada
        self.ema_alpha = 0.2
        self.ema_rpi = 0.0
        self.ema_servos = 0.0
        self.ema_motor = 0.0
        self.ema_voltage = 0.0
        self.ema_initialized = False

        # Buffer para filtro de mediana (rejeita spikes)
        self.median_buffer_size = 5
        self.median_buffer_rpi = deque(maxlen=self.median_buffer_size)
        self.median_buffer_servos = deque(maxlen=self.median_buffer_size)
        self.median_buffer_motor = deque(maxlen=self.median_buffer_size)

    def initialize(self) -> bool:
        """
        Inicializa os sensores de energia

        Returns:
            bool: True se pelo menos um sensor foi inicializado
        """
        print("Inicializando monitoramento de energia...")
        print(f"ADS1115 endereço: 0x{self.ads1115_address:02X}")
        print(f"INA219 endereço: 0x{self.ina219_address:02X}")

        try:
            # Tenta inicializar I2C
            try:
                import smbus2

                self.i2c_bus = smbus2.SMBus(1)
                print("✓ I2C inicializado com smbus2")
            except ImportError:
                try:
                    import smbus

                    self.i2c_bus = smbus.SMBus(1)
                    print("✓ I2C inicializado com smbus")
                except ImportError:
                    print("❌ Bibliotecas I2C não disponíveis")
                    print("   Instale: sudo apt install python3-smbus2")
                    return False

            # Inicializa ADS1115
            self.ads1115_available = self._init_ads1115()

            # Inicializa INA219
            self.ina219_available = self._init_ina219()

            # Verifica se pelo menos um sensor está disponível
            if self.ads1115_available or self.ina219_available:
                self.is_initialized = True
                print("✓ Monitoramento de energia inicializado!")
                print(
                    f"  - ADS1115 (correntes): {'Online' if self.ads1115_available else 'Offline'}"
                )
                print(
                    f"  - INA219 (RPi 5V): {'Online' if self.ina219_available else 'Offline'}"
                )
                return True
            else:
                print("❌ Nenhum sensor de energia disponível")
                return False

        except Exception as e:
            print(f"❌ Erro ao inicializar sensores de energia: {e}")
            return False

    def _init_ads1115(self) -> bool:
        """Inicializa o ADC ADS1115"""
        try:
            # Testa comunicação lendo registrador de config
            config = self._read_ads1115_register(self.ADS1115_REG_CONFIG)
            if config is None:
                print(f"⚠ ADS1115 não responde em 0x{self.ads1115_address:02X}")
                return False

            print(f"✓ ADS1115 detectado (config: 0x{config:04X})")

            # Faz uma leitura de teste
            test_value = self._read_ads1115_channel(0)
            if test_value is not None:
                print(f"✓ ADS1115 leitura de teste OK (raw: {test_value})")
                return True
            else:
                print("⚠ ADS1115 falha na leitura de teste")
                return False

        except Exception as e:
            print(f"⚠ Erro ao inicializar ADS1115: {e}")
            return False

    def _init_ina219(self) -> bool:
        """Inicializa o sensor INA219"""
        try:
            # Escreve configuração
            self._write_ina219_register(
                self.INA219_REG_CONFIG, self.INA219_CONFIG_32V_3A2
            )
            time.sleep(0.01)

            # Escreve calibração
            self._write_ina219_register(
                self.INA219_REG_CALIBRATION, self.INA219_CALIBRATION
            )
            time.sleep(0.01)

            # Lê tensão de teste
            voltage = self._read_ina219_bus_voltage()
            if voltage is not None and voltage >= 0:
                print(f"✓ INA219 detectado (tensão: {voltage:.2f}V)")
                return True
            else:
                print(f"⚠ INA219 não responde em 0x{self.ina219_address:02X}")
                return False

        except Exception as e:
            print(f"⚠ Erro ao inicializar INA219: {e}")
            return False

    def _read_ads1115_register(self, register: int) -> Optional[int]:
        """Lê registrador de 16 bits do ADS1115"""
        try:
            data = self.i2c_bus.read_i2c_block_data(self.ads1115_address, register, 2)
            return (data[0] << 8) | data[1]
        except Exception:
            return None

    def _write_ads1115_register(self, register: int, value: int):
        """Escreve registrador de 16 bits no ADS1115"""
        try:
            msb = (value >> 8) & 0xFF
            lsb = value & 0xFF
            self.i2c_bus.write_i2c_block_data(
                self.ads1115_address, register, [msb, lsb]
            )
            return True
        except Exception:
            return False

    def _read_ads1115_channel(self, channel: int) -> Optional[int]:
        """
        Lê um canal do ADS1115 (single-ended)

        Args:
            channel (int): Canal 0-3

        Returns:
            int: Valor raw (signed 16-bit) ou None se erro
        """
        try:
            # Seleciona MUX para o canal
            mux_values = [
                self.ADS1115_MUX_AIN0,
                self.ADS1115_MUX_AIN1,
                self.ADS1115_MUX_AIN2,
                self.ADS1115_MUX_AIN3,
            ]
            config = self.ADS1115_CONFIG_BASE | mux_values[channel]

            # Inicia conversão
            self._write_ads1115_register(self.ADS1115_REG_CONFIG, config)

            # Aguarda conversão (128 SPS = ~8ms)
            time.sleep(0.01)

            # Lê resultado
            result = self._read_ads1115_register(self.ADS1115_REG_CONVERSION)
            if result is None:
                return None

            # Converte para signed
            if result >= 32768:
                result -= 65536

            return result

        except Exception:
            return None

    def _write_ina219_register(self, register: int, value: int):
        """Escreve registrador de 16 bits no INA219"""
        try:
            msb = (value >> 8) & 0xFF
            lsb = value & 0xFF
            self.i2c_bus.write_i2c_block_data(self.ina219_address, register, [msb, lsb])
            return True
        except Exception:
            return False

    def _read_ina219_register(self, register: int) -> Optional[int]:
        """Lê registrador de 16 bits do INA219"""
        try:
            data = self.i2c_bus.read_i2c_block_data(self.ina219_address, register, 2)
            return (data[0] << 8) | data[1]
        except Exception:
            return None

    def _read_ina219_bus_voltage(self) -> Optional[float]:
        """Lê tensão do barramento (V)"""
        try:
            raw = self._read_ina219_register(self.INA219_REG_BUS_VOLTAGE)
            if raw is None:
                return None
            # Bits 15:3 = voltage, bit 1 = CNVR, bit 0 = OVF
            voltage = (raw >> 3) * 0.004  # 4mV/bit
            return voltage
        except Exception:
            return None

    def _read_ina219_current(self) -> Optional[float]:
        """Lê corrente (A)"""
        try:
            raw = self._read_ina219_register(self.INA219_REG_CURRENT)
            if raw is None:
                return None
            # Signed 16-bit
            if raw >= 32768:
                raw -= 65536
            current = raw * self.INA219_CURRENT_LSB
            return current
        except Exception:
            return None

    def _read_ina219_power(self) -> Optional[float]:
        """Lê potência (W)"""
        try:
            raw = self._read_ina219_register(self.INA219_REG_POWER)
            if raw is None:
                return None
            # Potência = raw * 20 * current_lsb
            power = raw * 20 * self.INA219_CURRENT_LSB
            return power
        except Exception:
            return None

    def _convert_acs758_to_current(
        self, raw_value: int, sensitivity: float, offset: float = 0.0
    ) -> float:
        """
        Converte valor raw do ADS1115 para corrente (A)

        Args:
            raw_value (int): Valor raw do ADC
            sensitivity (float): Sensibilidade do sensor (V/A)
            offset (float): Offset de calibração (V)

        Returns:
            float: Corrente em Amperes
        """
        # Converte raw para tensão
        voltage = raw_value * self.ADS1115_SCALE

        # Calcula corrente: I = (V - Vref - offset) / sensitivity
        current = (voltage - self.ACS758_VREF - offset) / sensitivity

        return current

    def _apply_ema_filter(self, new_value: float, ema_value: float) -> float:
        """
        Aplica filtro EMA (Exponential Moving Average)

        Args:
            new_value: Novo valor lido
            ema_value: Valor EMA anterior

        Returns:
            float: Valor filtrado
        """
        if not self.ema_initialized:
            return new_value
        return self.ema_alpha * ema_value + (1 - self.ema_alpha) * new_value

    def _apply_median_filter(self, value: float, buffer: deque) -> float:
        """
        Aplica filtro de mediana para rejeitar spikes

        Args:
            value: Novo valor
            buffer: Buffer de valores anteriores

        Returns:
            float: Valor filtrado (mediana do buffer)
        """
        buffer.append(value)
        if len(buffer) >= 3:
            return median(buffer)
        return value

    def _filter_current(
        self, raw_current: float, median_buffer: deque, ema_prev: float
    ) -> tuple:
        """
        Aplica cadeia de filtros: Mediana → EMA

        Args:
            raw_current: Corrente bruta calculada
            median_buffer: Buffer para filtro de mediana
            ema_prev: Valor EMA anterior

        Returns:
            tuple: (valor_filtrado, novo_ema)
        """
        # Primeiro: filtro de mediana (remove spikes)
        median_filtered = self._apply_median_filter(raw_current, median_buffer)

        # Segundo: filtro EMA (suaviza)
        ema_filtered = self._apply_ema_filter(median_filtered, ema_prev)

        return ema_filtered, ema_filtered

    def read_all_sensors(self) -> bool:
        """
        Lê todos os sensores de energia

        Returns:
            bool: True se pelo menos uma leitura foi bem sucedida
        """
        if not self.is_initialized:
            return False

        success = False

        # Lê ADS1115 (correntes via ACS758)
        if self.ads1115_available:
            try:
                # Canal 0: ACS758 50A - Corrente RPi (XL4015)
                raw = self._read_ads1115_channel(0)
                if raw is not None:
                    self.raw_rpi = raw
                    raw_current = self._convert_acs758_to_current(
                        raw, self.ACS758_50A_SENSITIVITY, self.offset_rpi
                    )
                    # Aplica filtros: Mediana → EMA
                    filtered, self.ema_rpi = self._filter_current(
                        raw_current, self.median_buffer_rpi, self.ema_rpi
                    )
                    self.current_rpi = filtered
                    self.buffer_current_rpi.append(filtered)
                    success = True

                # Canal 1: ACS758 50A - Corrente Servos (UBEC)
                raw = self._read_ads1115_channel(1)
                if raw is not None:
                    self.raw_servos = raw
                    raw_current = self._convert_acs758_to_current(
                        raw, self.ACS758_50A_SENSITIVITY, self.offset_servos
                    )
                    # Aplica filtros: Mediana → EMA
                    filtered, self.ema_servos = self._filter_current(
                        raw_current, self.median_buffer_servos, self.ema_servos
                    )
                    self.current_servos = filtered
                    self.buffer_current_servos.append(filtered)
                    success = True

                # Canal 2: ACS758 100A - Corrente Motor
                raw = self._read_ads1115_channel(2)
                if raw is not None:
                    self.raw_motor = raw
                    raw_current = self._convert_acs758_to_current(
                        raw, self.ACS758_100A_SENSITIVITY, self.offset_motor
                    )
                    # Aplica filtros: Mediana → EMA
                    filtered, self.ema_motor = self._filter_current(
                        raw_current, self.median_buffer_motor, self.ema_motor
                    )
                    self.current_motor = filtered
                    self.buffer_current_motor.append(filtered)
                    success = True

                # Marca EMA como inicializado após primeira leitura
                if not self.ema_initialized and success:
                    self.ema_initialized = True

            except Exception as e:
                self.errors_count += 1
                if self.errors_count % 50 == 0:
                    print(f"⚠ Erro ADS1115 (#{self.errors_count}): {e}")

        # Lê INA219 (tensão/corrente RPi)
        if self.ina219_available:
            try:
                voltage = self._read_ina219_bus_voltage()
                if voltage is not None:
                    # Aplica filtro EMA na tensão
                    self.ema_voltage = self._apply_ema_filter(voltage, self.ema_voltage)
                    self.voltage_rpi = (
                        self.ema_voltage if self.ema_initialized else voltage
                    )
                    self.buffer_voltage_rpi.append(self.voltage_rpi)
                    success = True

                current = self._read_ina219_current()
                if current is not None:
                    self.current_rpi_ina = current

                power = self._read_ina219_power()
                if power is not None:
                    self.power_rpi = power

            except Exception as e:
                self.errors_count += 1
                if self.errors_count % 50 == 0:
                    print(f"⚠ Erro INA219 (#{self.errors_count}): {e}")

        if success:
            self.readings_count += 1

        return success

    def update(self) -> bool:
        """
        Atualização principal - controla taxa de amostragem

        Returns:
            bool: True se atualizou
        """
        current_time = time.time()
        dt = current_time - self.last_update

        if dt >= 1.0 / self.sample_rate:
            if self.read_all_sensors():
                self.last_update = current_time
                return True

        return False

    def calibrate_zero_current(self, duration: float = 3.0):
        """
        Calibra os offsets com corrente zero

        Args:
            duration (float): Duração da calibração em segundos
        """
        print(f"Calibrando sensores de corrente ({duration}s)...")
        print("Certifique-se que não há carga nos circuitos!")

        samples_rpi = []
        samples_servos = []
        samples_motor = []

        start_time = time.time()
        while time.time() - start_time < duration:
            if self.ads1115_available:
                raw = self._read_ads1115_channel(0)
                if raw is not None:
                    voltage = raw * self.ADS1115_SCALE
                    samples_rpi.append(voltage - self.ACS758_VREF)

                raw = self._read_ads1115_channel(1)
                if raw is not None:
                    voltage = raw * self.ADS1115_SCALE
                    samples_servos.append(voltage - self.ACS758_VREF)

                raw = self._read_ads1115_channel(2)
                if raw is not None:
                    voltage = raw * self.ADS1115_SCALE
                    samples_motor.append(voltage - self.ACS758_VREF)

            time.sleep(0.05)

        # Calcula offsets médios
        if samples_rpi:
            self.offset_rpi = sum(samples_rpi) / len(samples_rpi)
            print(f"✓ Offset RPi: {self.offset_rpi*1000:.2f} mV")

        if samples_servos:
            self.offset_servos = sum(samples_servos) / len(samples_servos)
            print(f"✓ Offset Servos: {self.offset_servos*1000:.2f} mV")

        if samples_motor:
            self.offset_motor = sum(samples_motor) / len(samples_motor)
            print(f"✓ Offset Motor: {self.offset_motor*1000:.2f} mV")

        print("✓ Calibração concluída!")

    def get_sensor_data(self) -> Dict[str, Any]:
        """
        Retorna dados dos sensores de energia

        Returns:
            dict: Dados de energia do sistema
        """
        with self.state_lock:
            # Calcula médias dos buffers
            avg_current_rpi = (
                sum(self.buffer_current_rpi) / len(self.buffer_current_rpi)
                if self.buffer_current_rpi
                else self.current_rpi
            )
            avg_current_servos = (
                sum(self.buffer_current_servos) / len(self.buffer_current_servos)
                if self.buffer_current_servos
                else self.current_servos
            )
            avg_current_motor = (
                sum(self.buffer_current_motor) / len(self.buffer_current_motor)
                if self.buffer_current_motor
                else self.current_motor
            )
            avg_voltage_rpi = (
                sum(self.buffer_voltage_rpi) / len(self.buffer_voltage_rpi)
                if self.buffer_voltage_rpi
                else self.voltage_rpi
            )

            # Calcula potências
            power_motor = abs(self.current_motor) * 11.1  # Bateria 11.1V
            power_servos = abs(self.current_servos) * 5.25  # UBEC 5.25V
            power_total = power_motor + power_servos + self.power_rpi

            return {
                # Correntes instantâneas (A)
                "current_rpi": round(self.current_rpi, 3),
                "current_servos": round(self.current_servos, 3),
                "current_motor": round(self.current_motor, 3),
                # Correntes médias (A)
                "current_rpi_avg": round(avg_current_rpi, 3),
                "current_servos_avg": round(avg_current_servos, 3),
                "current_motor_avg": round(avg_current_motor, 3),
                # Tensão RPi (V)
                "voltage_rpi": round(self.voltage_rpi, 3),
                "voltage_rpi_avg": round(avg_voltage_rpi, 3),
                # INA219 direto
                "current_rpi_ina219": round(self.current_rpi_ina, 3),
                "power_rpi": round(self.power_rpi, 3),
                # Potências calculadas (W)
                "power_motor": round(power_motor, 2),
                "power_servos": round(power_servos, 2),
                "power_total": round(power_total, 2),
                # Valores raw do ADC
                "raw_rpi": self.raw_rpi,
                "raw_servos": self.raw_servos,
                "raw_motor": self.raw_motor,
                # Status
                "ads1115_available": self.ads1115_available,
                "ina219_available": self.ina219_available,
                # Metadados
                "power_readings_count": self.readings_count,
                "power_errors_count": self.errors_count,
                "timestamp": round(time.time(), 3),
            }

    def get_power_status(self) -> Dict[str, Any]:
        """
        Retorna status resumido de energia (para compatibilidade)

        Returns:
            dict: Status de energia
        """
        return self.get_sensor_data()

    def get_statistics(self) -> Dict[str, Any]:
        """
        Retorna estatísticas de operação

        Returns:
            dict: Estatísticas
        """
        elapsed = time.time() - self.start_time
        actual_rate = self.readings_count / elapsed if elapsed > 0 else 0

        return {
            "readings_count": self.readings_count,
            "errors_count": self.errors_count,
            "elapsed_time": round(elapsed, 2),
            "actual_sample_rate": round(actual_rate, 2),
            "target_sample_rate": self.sample_rate,
            "ads1115_available": self.ads1115_available,
            "ina219_available": self.ina219_available,
            "buffer_fill": {
                "current_rpi": len(self.buffer_current_rpi),
                "current_servos": len(self.buffer_current_servos),
                "current_motor": len(self.buffer_current_motor),
                "voltage_rpi": len(self.buffer_voltage_rpi),
            },
        }

    def cleanup(self):
        """Libera recursos"""
        try:
            if self.i2c_bus:
                self.i2c_bus.close()
            self.is_initialized = False
            print("✓ PowerMonitorManager finalizado")
        except Exception as e:
            print(f"⚠ Erro ao finalizar PowerMonitorManager: {e}")

    def __del__(self):
        """Destrutor"""
        self.cleanup()
