#!/usr/bin/env python3
"""
power_monitor_manager.py - Monitoramento de Energia do Sistema F1 Car

Gerencia a leitura de energia de múltiplos pontos do sistema:
- Arduino Pro Micro (USB Serial): Tensão bateria (divisor) + correntes 2x ACS758
- INA219 (I2C): Tensão e corrente do Raspberry Pi (5V após XL4015)

ARQUITETURA DE MEDIÇÃO:
=======================
Divisor de tensão (bateria) + ACS758 (2 unidades) → Pro Micro (ADC 10-bit) → USB Serial → RPi 4
INA219 (I2C) → RPi 4 (medição direta de tensão/corrente 5V)

SENSORES (via Pro Micro):
=========================
- A0: Divisor de tensão → Tensão bateria 3S LiPo (R1=20kΩ, R2=10kΩ, ratio 3)
- A1: ACS758 50A  → Corrente UBEC (Servos PCA9685)
- A2: ACS758 100A → Corrente Motor DC 775

PROTOCOLO SERIAL (Pro Micro → RPi):
===================================
- Dados:  "PWR:<v_bat>,<i_servos>,<i_motor>\n"  (tensão V e correntes A)
- Status: "STATUS:READY\n" | "STATUS:CALIBRATING\n"
- Calibração: "CAL_DONE:<off_servos>,<off_motor>\n"
- Baudrate: 115200

PROTOCOLO SERIAL (RPi → Pro Micro):
===================================
- Recalibrar: "CAL\n" (recalibra offsets dos ACS758, NÃO afeta canal de tensão)

DETECÇÃO USB:
=============
O Pro Micro (ATmega32U4) aparece como /dev/ttyACM* no Linux.
Detecção automática via:
  1. /dev/serial/by-id/ (preferido, estável)
  2. USB VID/PID (0x2341 Arduino, 0x1B4F SparkFun)
  3. Fallback /dev/ttyACM0

INA219 (I2C):
=============
- Endereço I2C: 0x40 (endereço padrão)
- Mede tensão (0-26V) e corrente (±3.2A) na entrada 5V do Raspberry Pi

PINOUT INA219 (Pinos: VIN-, VIN+, VCC, GND, SCL, SDA):
======================================================
  - VIN+  → Saída OUT+ do XL4015 (5.1V, lado fonte)
  - VIN-  → Entrada VBUS do USB Breakout (lado carga, vai para RPi)
  - VCC   → 3.3V do Raspberry Pi (alimentação do sensor)
  - GND   → GND comum do sistema
  - SCL   → GPIO3 (Pin 5) do Raspberry Pi [I2C Clock]
  - SDA   → GPIO2 (Pin 3) do Raspberry Pi [I2C Data]

Circuito de Medição:
    XL4015 OUT+ ─── VIN+ ───┬─── VIN- ─── USB Breakout VBUS (→ RPi)
                            │
                      [Shunt 0.1Ω]
                       (interno)

MAPA DE ENDEREÇOS I2C DO PROJETO (Atualizado):
===============================================
| Dispositivo      | Endereço | Configuração    | Função                |
|------------------|----------|-----------------|------------------------|
| INA219 (Corrente)| 0x40     | Padrão          | Medição corrente RPi   |
| PCA9685 (PWM)    | 0x41     | A0 soldado      | Controle de servos     |
| BMI160 (IMU)     | 0x68     | SAO/SDO→GND     | Acelerômetro/giroscópio|

Nota: ADS1115 removido do barramento I2C. Leituras de corrente ACS758
      agora são feitas pelo Arduino Pro Micro via USB Serial.

FILTROS DE SOFTWARE (este módulo):
==================================
1. Filtro EMA (Exponential Moving Average)
2. Filtro de Mediana (rejeita spikes/outliers)
"""

import glob
import os
import threading
import time
from collections import deque
from statistics import median
from typing import Any, Dict, Optional


class PowerMonitorManager:
    """Gerencia monitoramento de energia do sistema F1 Car

    Fontes de dados:
    - Arduino Pro Micro (USB Serial): Tensão bateria + correntes 2x ACS758
    - INA219 (I2C): Tensão e corrente do Raspberry Pi
    """

    # Endereço I2C do INA219
    INA219_ADDRESS = 0x40

    # Registradores INA219
    INA219_REG_CONFIG = 0x00
    INA219_REG_SHUNT_VOLTAGE = 0x01
    INA219_REG_BUS_VOLTAGE = 0x02
    INA219_REG_POWER = 0x03
    INA219_REG_CURRENT = 0x04
    INA219_REG_CALIBRATION = 0x05

    # Configuração INA219 (32V, 3.2A range)
    INA219_CONFIG_32V_3A2 = 0x399F

    # Calibração INA219 (shunt 0.1Ω, max 3.2A)
    INA219_CALIBRATION = 4096
    INA219_CURRENT_LSB = 0.0001  # 0.1mA/bit

    # Configuração serial do Pro Micro
    SERIAL_BAUDRATE = 115200
    SERIAL_TIMEOUT = 1.0  # Timeout de leitura (segundos)
    SERIAL_RECONNECT_INTERVAL = 5.0  # Tentativa de reconexão (segundos)
    SERIAL_DATA_TIMEOUT = 3.0  # Sem dados = desconectado (segundos)

    # Device ID estável do Pro Micro (não muda com a porta USB)
    PRO_MICRO_DEVICE_ID = "usb-Arduino_LLC_Arduino_Micro-if00"

    def __init__(
        self,
        sample_rate: int = 10,
        buffer_size: int = 20,
        ina219_address: int = None,
        serial_port: str = None,
        i2c_lock=None,  # Lock compartilhado do bus I2C
    ):
        """
        Inicializa o gerenciador de monitoramento de energia

        Args:
            sample_rate: Taxa de amostragem em Hz para INA219 (1-100)
            buffer_size: Tamanho do buffer para médias móveis
            ina219_address: Endereço I2C do INA219 (padrão 0x40)
            serial_port: Porta serial do Pro Micro (None = auto-detect)
            i2c_lock: threading.Lock compartilhado entre dispositivos I2C
        """
        self.i2c_lock = i2c_lock
        self.sample_rate = min(max(sample_rate, 1), 100)
        self.buffer_size = buffer_size
        self.ina219_address = ina219_address or self.INA219_ADDRESS
        self.serial_port_path = serial_port

        # Lock para thread-safety
        self.state_lock = threading.Lock()

        # I2C (INA219)
        self.i2c_bus = None
        self.ina219_available = False

        # Serial (Pro Micro)
        self.serial_conn = None
        self.serial_thread = None
        self.pro_micro_connected = False
        self._running = False
        self._last_serial_data = 0.0
        self._last_reconnect_attempt = 0.0

        # Estado geral
        self.is_initialized = False

        # Dados do Pro Micro (tensão bateria + correntes ACS758)
        self.voltage_battery = 0.0
        self.battery_percentage = 0.0
        self.current_servos = 0.0
        self.current_motor = 0.0

        # Dados de tensão/corrente (INA219)
        self.voltage_rpi = 0.0
        self.current_rpi_ina = 0.0
        self.power_rpi = 0.0

        # Buffers para média móvel
        self.buffer_voltage_battery = deque(maxlen=buffer_size)
        self.buffer_current_servos = deque(maxlen=buffer_size)
        self.buffer_current_motor = deque(maxlen=buffer_size)
        self.buffer_voltage_rpi = deque(maxlen=buffer_size)

        # Estatísticas
        self.readings_count = 0
        self.errors_count = 0
        self.start_time = time.time()
        self.last_update = time.time()

        # Filtros EMA (Exponential Moving Average)
        self.ema_alpha = 0.2
        self.ema_battery = 0.0
        self.ema_servos = 0.0
        self.ema_motor = 0.0
        self.ema_voltage = 0.0
        self.ema_initialized = False

        # Buffer para filtro de mediana (rejeita spikes)
        self.median_buffer_size = 5
        self.median_buffer_battery = deque(maxlen=self.median_buffer_size)
        self.median_buffer_servos = deque(maxlen=self.median_buffer_size)
        self.median_buffer_motor = deque(maxlen=self.median_buffer_size)

    def initialize(self) -> bool:
        """
        Inicializa os sensores de energia

        Returns:
            bool: True se pelo menos um sensor foi inicializado
        """
        print("Inicializando monitoramento de energia...")

        try:
            # Inicializa I2C para INA219
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
                    print("⚠ Bibliotecas I2C não disponíveis (INA219 offline)")

            # Inicializa INA219 (I2C)
            if self.i2c_bus:
                self.ina219_available = self._init_ina219()
                print(f"  INA219: {'Online' if self.ina219_available else 'Offline'}")

            # Inicializa Pro Micro (USB Serial)
            self.pro_micro_connected = self._init_pro_micro()
            print(f"  Pro Micro: {'Online' if self.pro_micro_connected else 'Offline'}")

            # Inicia thread de leitura serial
            self._running = True
            self.serial_thread = threading.Thread(
                target=self._serial_read_loop,
                name="ProMicroSerial",
                daemon=True,
            )
            self.serial_thread.start()

            if self.pro_micro_connected or self.ina219_available:
                self.is_initialized = True
                print("✓ Monitoramento de energia inicializado!")
                return True
            else:
                # Mesmo sem sensores, inicializa (thread tentará reconectar)
                self.is_initialized = True
                print("⚠ Nenhum sensor de energia disponível (tentará reconectar Pro Micro)")
                return True

        except Exception as e:
            print(f"❌ Erro ao inicializar sensores de energia: {e}")
            return False

    # ================================================================
    # PRO MICRO (USB SERIAL)
    # ================================================================

    def _init_pro_micro(self) -> bool:
        """Inicializa conexão serial com o Arduino Pro Micro"""
        port = self.serial_port_path or self._find_pro_micro_port()
        if not port:
            print("⚠ Arduino Pro Micro não encontrado")
            return False

        try:
            import serial
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=self.SERIAL_BAUDRATE,
                timeout=self.SERIAL_TIMEOUT,
            )
            self._last_serial_data = time.time()
            print(f"✓ Pro Micro conectado em {port}")
            return True
        except Exception as e:
            print(f"⚠ Erro ao conectar Pro Micro ({port}): {e}")
            return False

    def _find_pro_micro_port(self) -> Optional[str]:
        """
        Detecta a porta serial do Arduino Pro Micro

        Busca em ordem:
        1. /dev/serial/by-id/ pelo Device ID exato (estável entre portas USB)
        2. /dev/serial/by-id/ por nome genérico "arduino"
        3. pyserial list_ports por VID/PID
        4. Fallback /dev/ttyACM0
        """
        by_id_path = "/dev/serial/by-id/"

        # 1. Device ID exato (mais confiável)
        try:
            exact_path = os.path.join(by_id_path, self.PRO_MICRO_DEVICE_ID)
            if os.path.exists(exact_path):
                print(f"  Pro Micro encontrado via device ID: {exact_path}")
                return exact_path
        except Exception:
            pass

        # 2. Busca genérica por /dev/serial/by-id/ contendo "arduino"
        try:
            if os.path.exists(by_id_path):
                for link in os.listdir(by_id_path):
                    if "arduino" in link.lower():
                        full_path = os.path.join(by_id_path, link)
                        print(f"  Pro Micro encontrado via by-id: {full_path}")
                        return full_path
        except Exception:
            pass

        # 3. Busca por VID/PID via pyserial
        try:
            import serial.tools.list_ports
            # VIDs conhecidos para Pro Micro / Leonardo
            arduino_vids = {0x2341, 0x1B4F, 0x239A}
            for port in serial.tools.list_ports.comports():
                if port.vid in arduino_vids:
                    print(f"  Pro Micro encontrado via VID 0x{port.vid:04X}: {port.device}")
                    return port.device
        except ImportError:
            pass

        # 4. Fallback: primeiro /dev/ttyACM*
        acm_ports = sorted(glob.glob("/dev/ttyACM*"))
        if acm_ports:
            print(f"  Pro Micro (fallback): {acm_ports[0]}")
            return acm_ports[0]

        return None

    def _serial_read_loop(self):
        """Thread de leitura serial do Pro Micro (roda em background)"""
        while self._running:
            try:
                if self.pro_micro_connected and self.serial_conn:
                    self._read_serial_data()
                else:
                    self._try_reconnect()
                    time.sleep(1.0)
            except Exception:
                self.pro_micro_connected = False
                time.sleep(1.0)

    def _read_serial_data(self):
        """Lê e processa uma linha do Pro Micro"""
        try:
            raw = self.serial_conn.readline()
            if not raw:
                # Verifica timeout de dados
                if time.time() - self._last_serial_data > self.SERIAL_DATA_TIMEOUT:
                    print("⚠ Pro Micro: timeout de dados, desconectando")
                    self._disconnect_serial()
                return

            line = raw.decode("utf-8", errors="ignore").strip()
            if not line:
                return

            self._last_serial_data = time.time()

            if line.startswith("PWR:"):
                self._parse_power_data(line)
            elif line.startswith("STATUS:"):
                status = line[7:]
                if status == "READY":
                    print("✓ Pro Micro: pronto")
                elif status == "CALIBRATING":
                    print("ℹ Pro Micro: calibrando sensores...")
                elif status == "NO_CAL":
                    print("ℹ Pro Micro: sem calibração salva, usando offset teórico")
            elif line.startswith("CAL_DONE:"):
                print(f"✓ Pro Micro: calibração concluída ({line[9:]})")

        except (OSError, IOError):
            print("⚠ Pro Micro: erro de comunicação, desconectando")
            self._disconnect_serial()
        except Exception as e:
            self.errors_count += 1
            if self.errors_count % 50 == 0:
                print(f"⚠ Erro serial Pro Micro (#{self.errors_count}): {e}")

    def _parse_power_data(self, line: str):
        """
        Parseia linha de dados do Pro Micro

        Formato: PWR:<v_bat>,<i_servos>,<i_motor>
        - v_bat: Tensão da bateria 3S LiPo (V)
        - i_servos: Corrente dos servos/UBEC (A)
        - i_motor: Corrente do motor DC 775 (A)
        """
        try:
            parts = line[4:].split(",")
            if len(parts) != 3:
                return

            raw_battery = float(parts[0])
            raw_servos = float(parts[1])
            raw_motor = float(parts[2])

            with self.state_lock:
                # Aplica filtros: Mediana → EMA
                filtered_battery, self.ema_battery = self._filter_current(
                    raw_battery, self.median_buffer_battery, self.ema_battery
                )
                filtered_servos, self.ema_servos = self._filter_current(
                    raw_servos, self.median_buffer_servos, self.ema_servos
                )
                filtered_motor, self.ema_motor = self._filter_current(
                    raw_motor, self.median_buffer_motor, self.ema_motor
                )

                self.voltage_battery = filtered_battery
                self.current_servos = filtered_servos
                self.current_motor = filtered_motor

                # Calcula percentual da bateria (3S LiPo: 9.0V-12.6V)
                if filtered_battery > 0:
                    pct = (filtered_battery - 9.0) / (12.6 - 9.0) * 100.0
                    self.battery_percentage = max(0.0, min(100.0, pct))
                else:
                    self.battery_percentage = 0.0

                self.buffer_voltage_battery.append(filtered_battery)
                self.buffer_current_servos.append(filtered_servos)
                self.buffer_current_motor.append(filtered_motor)

                if not self.ema_initialized:
                    self.ema_initialized = True

                self.readings_count += 1

        except (ValueError, IndexError):
            pass

    def _disconnect_serial(self):
        """Desconecta o Pro Micro"""
        self.pro_micro_connected = False
        try:
            if self.serial_conn:
                self.serial_conn.close()
        except Exception:
            pass
        self.serial_conn = None

    def _try_reconnect(self):
        """Tenta reconectar ao Pro Micro periodicamente"""
        now = time.time()
        if now - self._last_reconnect_attempt < self.SERIAL_RECONNECT_INTERVAL:
            return

        self._last_reconnect_attempt = now
        port = self.serial_port_path or self._find_pro_micro_port()
        if not port:
            return

        try:
            import serial
            self.serial_conn = serial.Serial(
                port=port,
                baudrate=self.SERIAL_BAUDRATE,
                timeout=self.SERIAL_TIMEOUT,
            )
            self.pro_micro_connected = True
            self._last_serial_data = time.time()
            print(f"✓ Pro Micro reconectado em {port}")
        except Exception:
            pass

    def calibrate_current_sensors(self):
        """
        Envia comando de recalibração para o Pro Micro

        IMPORTANTE: Desligar motor e servos antes de calibrar!
        Apenas os canais ACS758 (A1, A2) são calibrados.
        O canal de tensão da bateria (A0) não requer calibração.
        """
        if self.pro_micro_connected and self.serial_conn:
            try:
                self.serial_conn.write(b"CAL\n")
                print("ℹ Comando de calibração enviado ao Pro Micro")
                print("  Aguardando calibração (desligar cargas!)...")
            except Exception as e:
                print(f"⚠ Erro ao enviar comando de calibração: {e}")
        else:
            print("⚠ Pro Micro não conectado, calibração não disponível")

    # ================================================================
    # INA219 (I2C)
    # ================================================================

    def _init_ina219(self) -> bool:
        """Inicializa o sensor INA219"""
        try:
            self._write_ina219_register(
                self.INA219_REG_CONFIG, self.INA219_CONFIG_32V_3A2
            )
            time.sleep(0.01)
            self._write_ina219_register(
                self.INA219_REG_CALIBRATION, self.INA219_CALIBRATION
            )
            time.sleep(0.01)

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

    def _write_ina219_register(self, register: int, value: int):
        """Escreve registrador de 16 bits no INA219 (prioridade baixa)"""
        try:
            msb = (value >> 8) & 0xFF
            lsb = value & 0xFF
            if self.i2c_lock:
                self.i2c_lock.acquire(priority=2)  # Baixa
                try:
                    self.i2c_bus.write_i2c_block_data(self.ina219_address, register, [msb, lsb])
                finally:
                    self.i2c_lock.release()
            else:
                self.i2c_bus.write_i2c_block_data(self.ina219_address, register, [msb, lsb])
            return True
        except Exception:
            return False

    def _read_ina219_register(self, register: int) -> Optional[int]:
        """Lê registrador de 16 bits do INA219 (prioridade baixa)"""
        try:
            if self.i2c_lock:
                self.i2c_lock.acquire(priority=2)  # Baixa
                try:
                    data = self.i2c_bus.read_i2c_block_data(self.ina219_address, register, 2)
                finally:
                    self.i2c_lock.release()
            else:
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
            power = raw * 20 * self.INA219_CURRENT_LSB
            return power
        except Exception:
            return None

    # ================================================================
    # FILTROS
    # ================================================================

    def _apply_ema_filter(self, new_value: float, ema_value: float) -> float:
        """Aplica filtro EMA (Exponential Moving Average)"""
        if not self.ema_initialized:
            return new_value
        return self.ema_alpha * ema_value + (1 - self.ema_alpha) * new_value

    def _apply_median_filter(self, value: float, buffer: deque) -> float:
        """Aplica filtro de mediana para rejeitar spikes"""
        buffer.append(value)
        if len(buffer) >= 3:
            return median(buffer)
        return value

    def _filter_current(
        self, raw_current: float, median_buffer: deque, ema_prev: float
    ) -> tuple:
        """Aplica cadeia de filtros: Mediana → EMA"""
        median_filtered = self._apply_median_filter(raw_current, median_buffer)
        ema_filtered = self._apply_ema_filter(median_filtered, ema_prev)
        return ema_filtered, ema_filtered

    # ================================================================
    # ATUALIZAÇÃO E DADOS
    # ================================================================

    def read_ina219(self) -> bool:
        """Lê dados do INA219"""
        if not self.ina219_available:
            return False

        success = False
        try:
            voltage = self._read_ina219_bus_voltage()
            if voltage is not None:
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

        return success

    def update(self) -> bool:
        """
        Atualização principal - lê INA219 (correntes do Pro Micro vêm via thread)

        Returns:
            bool: True se atualizou
        """
        current_time = time.time()
        dt = current_time - self.last_update

        if dt >= 1.0 / self.sample_rate:
            success = self.read_ina219()
            # Pro Micro é considerado sucesso se temos dados recentes
            if self.pro_micro_connected and self.readings_count > 0:
                success = True
            self.last_update = current_time
            return success

        return False

    def get_sensor_data(self) -> Dict[str, Any]:
        """
        Retorna dados dos sensores de energia

        Returns:
            dict: Dados de energia do sistema
        """
        with self.state_lock:
            avg_voltage_battery = (
                sum(self.buffer_voltage_battery) / len(self.buffer_voltage_battery)
                if self.buffer_voltage_battery
                else self.voltage_battery
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

            # Potências calculadas (usa tensão real da bateria)
            battery_v = self.voltage_battery if self.voltage_battery > 0 else 11.1
            power_motor = abs(self.current_motor) * battery_v
            power_servos = abs(self.current_servos) * 5.25  # UBEC 5.25V
            power_total = power_motor + power_servos + self.power_rpi

            return {
                # Tensão da bateria (V) - via Pro Micro (divisor de tensão)
                "voltage_battery": round(self.voltage_battery, 2),
                "voltage_battery_avg": round(avg_voltage_battery, 2),
                "battery_percentage": round(self.battery_percentage, 1),
                # Correntes instantâneas (A) - via Pro Micro (ACS758)
                "current_servos": round(self.current_servos, 3),
                "current_motor": round(self.current_motor, 3),
                # Correntes médias (A)
                "current_servos_avg": round(avg_current_servos, 3),
                "current_motor_avg": round(avg_current_motor, 3),
                # Tensão RPi (V) - via INA219
                "voltage_rpi": round(self.voltage_rpi, 3),
                "voltage_rpi_avg": round(avg_voltage_rpi, 3),
                # INA219 direto (corrente e potência RPi)
                "current_rpi": round(self.current_rpi_ina, 3),
                "current_rpi_ina219": round(self.current_rpi_ina, 3),
                "power_rpi": round(self.power_rpi, 3),
                # Potências calculadas (W)
                "power_motor": round(power_motor, 2),
                "power_servos": round(power_servos, 2),
                "power_total": round(power_total, 2),
                # Status
                "pro_micro_connected": self.pro_micro_connected,
                "ina219_available": self.ina219_available,
                # Metadados
                "power_readings_count": self.readings_count,
                "power_errors_count": self.errors_count,
                "timestamp": round(time.time(), 3),
            }

    def get_power_status(self) -> Dict[str, Any]:
        """Retorna status resumido de energia (compatibilidade)"""
        return self.get_sensor_data()

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas de operação"""
        elapsed = time.time() - self.start_time
        actual_rate = self.readings_count / elapsed if elapsed > 0 else 0

        return {
            "readings_count": self.readings_count,
            "errors_count": self.errors_count,
            "elapsed_time": round(elapsed, 2),
            "actual_sample_rate": round(actual_rate, 2),
            "target_sample_rate": self.sample_rate,
            "pro_micro_connected": self.pro_micro_connected,
            "ina219_available": self.ina219_available,
            "buffer_fill": {
                "voltage_battery": len(self.buffer_voltage_battery),
                "current_servos": len(self.buffer_current_servos),
                "current_motor": len(self.buffer_current_motor),
                "voltage_rpi": len(self.buffer_voltage_rpi),
            },
        }

    def cleanup(self):
        """Libera recursos"""
        self._running = False
        try:
            if self.serial_thread and self.serial_thread.is_alive():
                self.serial_thread.join(timeout=2.0)
            if self.serial_conn:
                self.serial_conn.close()
            if self.i2c_bus:
                self.i2c_bus.close()
            self.is_initialized = False
            print("✓ PowerMonitorManager finalizado")
        except Exception as e:
            print(f"⚠ Erro ao finalizar PowerMonitorManager: {e}")

    def __del__(self):
        """Destrutor"""
        self.cleanup()
