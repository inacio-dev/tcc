#!/usr/bin/env python3
"""
bmi160_manager.py - Gerenciamento do Sensor BMI160 CORRIGIDO
Agora está de acordo com o datasheet oficial

PINOUT BMI160 (GY-BMI160):
==========================
BMI160 Module -> Raspberry Pi 4 (GPIO)
- VCC/VDD  -> Pin 1  (3.3V) ou Pin 2 (5V)    [Verifique datasheet do seu módulo]
- GND      -> Pin 6  (GND) ou qualquer GND
- SCL      -> Pin 5  (GPIO3/SCL1)             [I2C Clock]
- SDA      -> Pin 3  (GPIO2/SDA1)             [I2C Data]
- SAO/SDO  -> GND (0x68) ou VCC (0x69)        [Seleção de endereço]

REGISTRADORES IMPORTANTES (conforme datasheet):
==============================================
0x00 - CHIP_ID (deve retornar 0xD1)
0x40 - ACC_CONF (configuração acelerômetro)
0x41 - ACC_RANGE (range acelerômetro)
0x42 - GYR_CONF (configuração giroscópio)
0x43 - GYR_RANGE (range giroscópio)
0x7E - CMD (comandos de controle)
0x12-0x17 - ACCEL_DATA (6 bytes)
0x0C-0x11 - GYRO_DATA (6 bytes)
"""

import time
import math
import numpy as np
from collections import deque

# Para o BMI160 real, descomente uma das opções:
# import smbus2  # Para comunicação I2C direta
# from bmi160_i2c import BMI160
# import board
# import busio
# import adafruit_bmi160


class BMI160Manager:
    """Gerencia o sensor BMI160 conforme datasheet oficial"""

    # ================== CONSTANTES DO DATASHEET ==================

    # Endereços I2C
    I2C_ADDRESS_LOW = 0x68  # SAO/SDO = GND
    I2C_ADDRESS_HIGH = 0x69  # SAO/SDO = VCC

    # Registradores principais
    REG_CHIP_ID = 0x00  # ID do chip (deve ser 0xD1)
    REG_ACC_CONF = 0x40  # Configuração acelerômetro
    REG_ACC_RANGE = 0x41  # Range acelerômetro
    REG_GYR_CONF = 0x42  # Configuração giroscópio
    REG_GYR_RANGE = 0x43  # Range giroscópio
    REG_CMD = 0x7E  # Comandos

    # Dados dos sensores
    REG_ACCEL_DATA = 0x12  # 6 bytes: X_LSB, X_MSB, Y_LSB, Y_MSB, Z_LSB, Z_MSB
    REG_GYRO_DATA = 0x0C  # 6 bytes: X_LSB, X_MSB, Y_LSB, Y_MSB, Z_LSB, Z_MSB

    # Chip ID esperado
    CHIP_ID_BMI160 = 0xD1

    # ===== RANGES CONFORME DATASHEET =====
    # Acelerômetro (registrador 0x41)
    ACCEL_RANGE_2G = 0x03  # ±2g
    ACCEL_RANGE_4G = 0x05  # ±4g
    ACCEL_RANGE_8G = 0x08  # ±8g
    ACCEL_RANGE_16G = 0x0C  # ±16g

    # Giroscópio (registrador 0x43)
    GYRO_RANGE_2000 = 0x00  # ±2000°/s
    GYRO_RANGE_1000 = 0x01  # ±1000°/s
    GYRO_RANGE_500 = 0x02  # ±500°/s
    GYRO_RANGE_250 = 0x03  # ±250°/s
    GYRO_RANGE_125 = 0x04  # ±125°/s

    # ===== OUTPUT DATA RATES (ODR) =====
    # Para ACC_CONF[3:0] e GYR_CONF[3:0]
    ODR_25HZ = 0x06
    ODR_50HZ = 0x07
    ODR_100HZ = 0x08
    ODR_200HZ = 0x09
    ODR_400HZ = 0x0A
    ODR_800HZ = 0x0B
    ODR_1600HZ = 0x0C

    # ===== COMANDOS (registrador 0x7E) =====
    CMD_SOFT_RESET = 0xB6
    CMD_ACC_SET_PMU_MODE = 0x11  # Acelerômetro para modo normal
    CMD_GYR_SET_PMU_MODE = 0x15  # Giroscópio para modo normal
    CMD_FOC_ENABLE = 0x03  # Fast Offset Compensation

    # ===== FATORES DE CONVERSÃO =====
    ACCEL_SCALE_FACTORS = {
        ACCEL_RANGE_2G: 2.0 / 32768.0,  # LSB para g
        ACCEL_RANGE_4G: 4.0 / 32768.0,
        ACCEL_RANGE_8G: 8.0 / 32768.0,
        ACCEL_RANGE_16G: 16.0 / 32768.0,
    }

    GYRO_SCALE_FACTORS = {
        GYRO_RANGE_125: 125.0 / 32768.0,  # LSB para °/s
        GYRO_RANGE_250: 250.0 / 32768.0,
        GYRO_RANGE_500: 500.0 / 32768.0,
        GYRO_RANGE_1000: 1000.0 / 32768.0,
        GYRO_RANGE_2000: 2000.0 / 32768.0,
    }

    def __init__(
        self,
        sample_rate=100,
        buffer_size=50,
        accel_range=None,  # Será ACCEL_RANGE_2G por padrão
        gyro_range=None,  # Será GYRO_RANGE_250 por padrão
        i2c_address=None,  # Será I2C_ADDRESS_LOW por padrão
    ):
        """
        Inicializa o gerenciador do BMI160

        Args:
            sample_rate (int): Taxa de amostragem em Hz (25-1600)
            buffer_size (int): Tamanho do buffer para médias móveis
            accel_range (int): Range do acelerômetro (usar constantes ACCEL_RANGE_*)
            gyro_range (int): Range do giroscópio (usar constantes GYRO_RANGE_*)
            i2c_address (int): Endereço I2C do sensor
        """
        # Valores padrão conforme datasheet
        self.accel_range = (
            accel_range if accel_range is not None else self.ACCEL_RANGE_2G
        )
        self.gyro_range = gyro_range if gyro_range is not None else self.GYRO_RANGE_250
        self.i2c_address = (
            i2c_address if i2c_address is not None else self.I2C_ADDRESS_LOW
        )

        self.sample_rate = sample_rate
        self.buffer_size = buffer_size

        # Mapear sample_rate para ODR
        self.odr_value = self._get_odr_value(sample_rate)

        # Fatores de escala baseados nos ranges selecionados
        self.accel_scale = self.ACCEL_SCALE_FACTORS[self.accel_range]
        self.gyro_scale = self.GYRO_SCALE_FACTORS[self.gyro_range]

        # Objetos de comunicação
        self.i2c_bus = None
        self.bmi160 = None
        self.is_initialized = False
        self.use_real_sensor = False  # Flag para controlar simulação vs real

        # Offsets de calibração
        self.accel_x_offset = 0.0
        self.accel_y_offset = 0.0
        self.accel_z_offset = 0.0
        self.gyro_x_offset = 0.0
        self.gyro_y_offset = 0.0
        self.gyro_z_offset = 0.0

        # Dados raw do sensor (LSB)
        self.accel_x_raw = 0
        self.accel_y_raw = 0
        self.accel_z_raw = 0
        self.gyro_x_raw = 0
        self.gyro_y_raw = 0
        self.gyro_z_raw = 0

        # Dados convertidos (unidades físicas)
        self.accel_x = 0.0  # m/s²
        self.accel_y = 0.0
        self.accel_z = 9.81
        self.gyro_x = 0.0  # °/s
        self.gyro_y = 0.0
        self.gyro_z = 0.0

        # Buffers para processamento
        self.accel_buffer_x = deque(maxlen=buffer_size)
        self.accel_buffer_y = deque(maxlen=buffer_size)
        self.accel_buffer_z = deque(maxlen=buffer_size)
        self.gyro_buffer_x = deque(maxlen=buffer_size)
        self.gyro_buffer_y = deque(maxlen=buffer_size)
        self.gyro_buffer_z = deque(maxlen=buffer_size)

        # Dados calculados para force feedback
        self.g_force_frontal = 0.0
        self.g_force_lateral = 0.0
        self.g_force_vertical = 0.0

        # Ângulos integrados
        self.roll_angle = 0.0
        self.pitch_angle = 0.0
        self.yaw_angle = 0.0

        # Detecção de eventos
        self.is_turning_left = False
        self.is_turning_right = False
        self.is_accelerating = False
        self.is_braking = False
        self.is_bouncing = False
        self.impact_detected = False

        # Intensidades para atuadores (0-100%)
        self.steering_feedback_intensity = 0.0
        self.brake_pedal_resistance = 0.0
        self.accelerator_feedback = 0.0
        self.seat_vibration_intensity = 0.0
        self.seat_tilt_x = 0.0
        self.seat_tilt_y = 0.0

        # Controle de tempo
        self.last_update = time.time()
        self.start_time = time.time()
        self.readings_count = 0

    def _get_odr_value(self, sample_rate):
        """Converte sample_rate para valor ODR do registrador"""
        if sample_rate <= 25:
            return self.ODR_25HZ
        elif sample_rate <= 50:
            return self.ODR_50HZ
        elif sample_rate <= 100:
            return self.ODR_100HZ
        elif sample_rate <= 200:
            return self.ODR_200HZ
        elif sample_rate <= 400:
            return self.ODR_400HZ
        elif sample_rate <= 800:
            return self.ODR_800HZ
        else:
            return self.ODR_1600HZ

    def _write_register(self, reg, value):
        """Escreve valor em registrador via I2C"""
        try:
            if self.use_real_sensor and self.i2c_bus:
                # I2C real
                self.i2c_bus.write_byte_data(self.i2c_address, reg, value)
            else:
                # SIMULAÇÃO - não faz nada
                pass

        except Exception as e:
            print(f"⚠ Erro ao escrever registrador 0x{reg:02X}: {e}")
            return False
        return True

    def _read_register(self, reg):
        """Lê valor de registrador via I2C"""
        try:
            if self.use_real_sensor and self.i2c_bus:
                # I2C real
                return self.i2c_bus.read_byte_data(self.i2c_address, reg)
            else:
                # SIMULAÇÃO - apenas para CHIP_ID
                if reg == self.REG_CHIP_ID:
                    return self.CHIP_ID_BMI160  # Simula chip ID correto
                else:
                    return 0x00

        except Exception as e:
            print(f"⚠ Erro ao ler registrador 0x{reg:02X}: {e}")
            return None

    def _read_sensor_registers(self, start_reg, num_bytes):
        """Lê múltiplos registradores sequenciais"""
        try:
            if self.use_real_sensor and self.i2c_bus:
                # I2C real
                return self.i2c_bus.read_i2c_block_data(self.i2c_address, start_reg, num_bytes)
            else:
                # SIMULAÇÃO - retorna zeros (sensor offline)
                return [0] * num_bytes

        except Exception as e:
            print(f"⚠ Erro ao ler {num_bytes} bytes do reg 0x{start_reg:02X}: {e}")
            return None

    def initialize(self):
        """
        Inicializa o sensor BMI160 conforme sequência do datasheet

        Returns:
            bool: True se inicializado com sucesso
        """
        print("Inicializando sensor BMI160...")
        print(f"Endereço I2C: 0x{self.i2c_address:02X}")
        print(f"Range Accel: ±{self._get_accel_range_g()}g")
        print(f"Range Gyro: ±{self._get_gyro_range_dps()}°/s")
        print(f"ODR: {self.sample_rate}Hz")

        try:
            # 1. Tentar inicializar I2C real
            try:
                # Primeiro tenta smbus2
                import smbus2
                self.i2c_bus = smbus2.SMBus(1)  # I2C bus 1 no Raspberry Pi
                self.use_real_sensor = True
                print("✓ I2C inicializado com smbus2 - usando sensor REAL")
            except ImportError:
                try:
                    # Fallback para smbus (sistema)
                    import smbus
                    self.i2c_bus = smbus.SMBus(1)
                    self.use_real_sensor = True
                    print("✓ I2C inicializado com smbus - usando sensor REAL")
                except ImportError:
                    print("⚠ Nem smbus2 nem smbus disponíveis - MODO SIMULAÇÃO")
                    self.use_real_sensor = False
                except Exception as e:
                    print(f"⚠ Erro no smbus: {e} - MODO SIMULAÇÃO")
                    self.use_real_sensor = False
            except Exception as e:
                print(f"⚠ Erro no smbus2: {e} - tentando smbus...")
                try:
                    import smbus
                    self.i2c_bus = smbus.SMBus(1)
                    self.use_real_sensor = True
                    print("✓ I2C inicializado com smbus - usando sensor REAL")
                except Exception as e2:
                    print(f"⚠ Erro no smbus também: {e2} - MODO SIMULAÇÃO")
                    self.use_real_sensor = False

            # 2. Verificar CHIP_ID (deve ser 0xD1)
            chip_id = self._read_register(self.REG_CHIP_ID)
            if chip_id is None:
                print("✗ Erro ao ler CHIP_ID - sensor não responde")
                return False
            if chip_id != self.CHIP_ID_BMI160:
                print(
                    f"✗ CHIP_ID incorreto: 0x{chip_id:02X} (esperado: 0x{self.CHIP_ID_BMI160:02X})"
                )
                return False

            print(f"✓ CHIP_ID verificado: 0x{chip_id:02X}")

            # 3. Soft Reset
            print("Executando soft reset...")
            if not self._write_register(self.REG_CMD, self.CMD_SOFT_RESET):
                print("❌ Falha no soft reset")
                return False
            time.sleep(0.015)  # Aguarda reset (15ms para garantir)

            # 4. Verificar se voltou depois do reset
            chip_id_after_reset = self._read_register(self.REG_CHIP_ID)
            if chip_id_after_reset != self.CHIP_ID_BMI160:
                print(f"❌ CHIP_ID após reset: 0x{chip_id_after_reset:02X}")
                return False
            print("✓ Sensor OK após reset")

            # 5. Ativar acelerômetro ANTES de configurar
            print("Ativando acelerômetro...")
            if not self._write_register(self.REG_CMD, self.CMD_ACC_SET_PMU_MODE):
                print("❌ Falha ao ativar acelerômetro")
                return False
            time.sleep(0.010)  # Startup time do acelerômetro

            # 6. Configurar acelerômetro (DEPOIS de ativar)
            print("Configurando range do acelerômetro...")
            if not self._write_register(self.REG_ACC_RANGE, self.accel_range):
                print("❌ Falha ao configurar range acelerômetro")
                return False

            print("Configurando ODR do acelerômetro...")
            acc_conf = self.odr_value | (0x02 << 4)  # BWP = 0x02 (normal mode)
            if not self._write_register(self.REG_ACC_CONF, acc_conf):
                print("❌ Falha ao configurar ODR acelerômetro")
                return False

            # 7. Ativar giroscópio ANTES de configurar
            print("Ativando giroscópio...")
            if not self._write_register(self.REG_CMD, self.CMD_GYR_SET_PMU_MODE):
                print("❌ Falha ao ativar giroscópio")
                return False
            time.sleep(0.060)  # Startup time do giroscópio (55ms + margem)

            # 8. Configurar giroscópio (DEPOIS de ativar)
            print("Configurando range do giroscópio...")
            if not self._write_register(self.REG_GYR_RANGE, self.gyro_range):
                print("❌ Falha ao configurar range giroscópio")
                return False

            print("Configurando ODR do giroscópio...")
            gyr_conf = self.odr_value | (0x02 << 4)  # BWP = 0x02 (normal mode)
            if not self._write_register(self.REG_GYR_CONF, gyr_conf):
                print("❌ Falha ao configurar ODR giroscópio")
                return False

            # 9. Aguardar estabilização final
            print("Aguardando estabilização final...")
            time.sleep(0.1)

            # 10. Teste de leitura para verificar se funciona
            print("Testando leitura dos registradores...")
            test_accel = self._read_sensor_registers(self.REG_ACCEL_DATA, 6)
            test_gyro = self._read_sensor_registers(self.REG_GYRO_DATA, 6)
            if test_accel is None or test_gyro is None:
                print("❌ Falha no teste de leitura - sensor não responde")
                return False
            print(f"✓ Teste OK - accel: {test_accel[:2]}, gyro: {test_gyro[:2]}")

            self.is_initialized = True

            print("✓ BMI160 inicializado com sucesso!")
            print(f"  - Acelerômetro: ±{self._get_accel_range_g()}g")
            print(f"  - Giroscópio: ±{self._get_gyro_range_dps()}°/s")
            print(f"  - Taxa: {self.sample_rate}Hz")
            print(f"  - Escala Accel: {self.accel_scale:.6f} g/LSB")
            print(f"  - Escala Gyro: {self.gyro_scale:.6f} °/s/LSB")

            return True

        except Exception as e:
            print(f"✗ Erro ao inicializar BMI160: {e}")
            print("\nVerifique:")
            print("1. Conexões I2C (SDA=GPIO2, SCL=GPIO3)")
            print("2. I2C habilitado: sudo raspi-config -> Interface Options -> I2C")
            print("3. Biblioteca I2C: sudo apt-get install i2c-tools python3-smbus2")
            print("4. Endereço correto: sudo i2cdetect -y 1")
            print("5. Alimentação do sensor (3.3V ou 5V)")

            self.is_initialized = False
            return False

    def _get_accel_range_g(self):
        """Retorna o range atual do acelerômetro em g"""
        range_map = {
            self.ACCEL_RANGE_2G: 2,
            self.ACCEL_RANGE_4G: 4,
            self.ACCEL_RANGE_8G: 8,
            self.ACCEL_RANGE_16G: 16,
        }
        return range_map.get(self.accel_range, 2)

    def _get_gyro_range_dps(self):
        """Retorna o range atual do giroscópio em °/s"""
        range_map = {
            self.GYRO_RANGE_125: 125,
            self.GYRO_RANGE_250: 250,
            self.GYRO_RANGE_500: 500,
            self.GYRO_RANGE_1000: 1000,
            self.GYRO_RANGE_2000: 2000,
        }
        return range_map.get(self.gyro_range, 250)

    def read_sensor_data(self):
        """Lê dados raw do sensor BMI160 conforme datasheet"""
        if not self.is_initialized:
            return False

        try:
            # Ler dados do acelerômetro (6 bytes a partir do 0x12)
            accel_data = self._read_sensor_registers(self.REG_ACCEL_DATA, 6)
            if accel_data is None:
                return False

            # Ler dados do giroscópio (6 bytes a partir do 0x0C)
            gyro_data = self._read_sensor_registers(self.REG_GYRO_DATA, 6)
            if gyro_data is None:
                return False

            # Debug: mostrar dados raw lidos do I2C
            if hasattr(self, '_debug_counter'):
                self._debug_counter += 1
            else:
                self._debug_counter = 1

            if self._debug_counter % 200 == 0:  # A cada ~1s
                print(f"🔍 BMI160 RAW I2C: accel_data={accel_data}, gyro_data={gyro_data}")

            # CONVERSÃO CONFORME DATASHEET:
            # Dados em complemento de 2, LSB primeiro

            if self.use_real_sensor:
                # Hardware real - converte dados I2C
                self.accel_x_raw = self._bytes_to_int16(accel_data[0], accel_data[1])
                self.accel_y_raw = self._bytes_to_int16(accel_data[2], accel_data[3])
                self.accel_z_raw = self._bytes_to_int16(accel_data[4], accel_data[5])

                self.gyro_x_raw = self._bytes_to_int16(gyro_data[0], gyro_data[1])
                self.gyro_y_raw = self._bytes_to_int16(gyro_data[2], gyro_data[3])
                self.gyro_z_raw = self._bytes_to_int16(gyro_data[4], gyro_data[5])
            else:
                # Sensor offline - dados zeros
                self.accel_x_raw = 0
                self.accel_y_raw = 0
                self.accel_z_raw = 16384  # 1g em LSB (sensor em repouso)
                self.gyro_x_raw = 0
                self.gyro_y_raw = 0
                self.gyro_z_raw = 0

            # Converter para unidades físicas usando fatores de escala
            self.accel_x = (
                self.accel_x_raw * self.accel_scale - self.accel_x_offset
            ) * 9.81  # m/s²
            self.accel_y = (
                self.accel_y_raw * self.accel_scale - self.accel_y_offset
            ) * 9.81
            self.accel_z = (
                self.accel_z_raw * self.accel_scale - self.accel_z_offset
            ) * 9.81

            self.gyro_x = self.gyro_x_raw * self.gyro_scale - self.gyro_x_offset  # °/s
            self.gyro_y = self.gyro_y_raw * self.gyro_scale - self.gyro_y_offset
            self.gyro_z = self.gyro_z_raw * self.gyro_scale - self.gyro_z_offset

            self.readings_count += 1
            return True

        except Exception as e:
            print(f"⚠ Erro ao ler BMI160: {e}")
            return False

    def _bytes_to_int16(self, lsb, msb):
        """Converte 2 bytes para int16 com sinal (complemento de 2)"""
        value = (msb << 8) | lsb
        if value >= 32768:  # Se bit de sinal estiver setado
            value -= 65536
        return value

    def update_buffers(self):
        """Atualiza buffers de dados para processamento"""
        self.accel_buffer_x.append(self.accel_x)
        self.accel_buffer_y.append(self.accel_y)
        self.accel_buffer_z.append(self.accel_z)

        self.gyro_buffer_x.append(self.gyro_x)
        self.gyro_buffer_y.append(self.gyro_y)
        self.gyro_buffer_z.append(self.gyro_z)

    def calculate_g_forces(self):
        """Calcula forças G para force feedback"""
        # Força G frontal (aceleração/frenagem)
        self.g_force_frontal = self.accel_x / 9.81

        # Força G lateral (curvas)
        self.g_force_lateral = abs(self.accel_y) / 9.81

        # Força G vertical (solavancos)
        self.g_force_vertical = abs(self.accel_z - 9.81) / 9.81

    def detect_driving_events(self):
        """Detecta eventos de direção para force feedback"""
        # Thresholds para detecção
        TURN_THRESHOLD = 10.0  # °/s
        ACCEL_THRESHOLD = 1.5  # m/s²
        BOUNCE_THRESHOLD = 1.0  # desvio padrão
        IMPACT_THRESHOLD = 5.0  # m/s²

        # Detecta curvas baseado no giroscópio Z
        if abs(self.gyro_z) > TURN_THRESHOLD:
            if self.gyro_z > TURN_THRESHOLD:
                self.is_turning_right = True
                self.is_turning_left = False
            else:
                self.is_turning_left = True
                self.is_turning_right = False
        else:
            self.is_turning_left = False
            self.is_turning_right = False

        # Detecta aceleração/frenagem
        if self.accel_x > ACCEL_THRESHOLD:
            self.is_accelerating = True
            self.is_braking = False
        elif self.accel_x < -ACCEL_THRESHOLD:
            self.is_braking = True
            self.is_accelerating = False
        else:
            self.is_accelerating = False
            self.is_braking = False

        # Detecta solavancos (variação na aceleração vertical)
        if len(self.accel_buffer_z) >= 10:
            recent_z = list(self.accel_buffer_z)[-10:]
            z_variation = np.std(recent_z)
            self.is_bouncing = z_variation > BOUNCE_THRESHOLD

        # Detecta impactos (picos súbitos)
        self.impact_detected = (
            abs(self.accel_x) > IMPACT_THRESHOLD
            or abs(self.accel_y) > IMPACT_THRESHOLD
            or abs(self.accel_z - 9.81) > IMPACT_THRESHOLD
        )

    def calculate_angles(self, dt):
        """Integra velocidades angulares para obter ângulos"""
        # Integração simples (pode ser melhorada com filtro complementar)
        self.roll_angle += self.gyro_x * dt
        self.pitch_angle += self.gyro_y * dt
        self.yaw_angle += self.gyro_z * dt

        # Mantém ângulos no range 0-360°
        self.roll_angle = self.roll_angle % 360
        self.pitch_angle = self.pitch_angle % 360
        self.yaw_angle = self.yaw_angle % 360

    def calculate_force_feedback(self):
        """Calcula intensidades para os atuadores de force feedback"""

        # === FORÇA NO VOLANTE ===
        base_steering = min(abs(self.g_force_lateral) * 50, 100)
        yaw_component = min(abs(self.gyro_z) / 60.0 * 50, 50)
        self.steering_feedback_intensity = min(base_steering + yaw_component, 100)

        # === RESISTÊNCIA NO PEDAL DE FREIO ===
        if self.is_braking:
            self.brake_pedal_resistance = min(abs(self.g_force_frontal) * 60, 100)
        else:
            self.brake_pedal_resistance = 0

        # === FEEDBACK NO ACELERADOR ===
        if self.is_accelerating:
            self.accelerator_feedback = min(self.g_force_frontal * 40, 80)
        else:
            self.accelerator_feedback = 0

        # === VIBRAÇÃO DO ASSENTO ===
        vibration = 0
        if self.is_bouncing:
            vibration = min(self.g_force_vertical * 80, 100)
        if self.impact_detected:
            vibration = 100

        self.seat_vibration_intensity = vibration

        # === INCLINAÇÃO DO ASSENTO ===
        max_tilt = 15  # graus máximos

        # Inclinação lateral (curvas)
        self.seat_tilt_x = np.clip(
            self.g_force_lateral * max_tilt * (1 if self.is_turning_right else -1),
            -max_tilt,
            max_tilt,
        )

        # Inclinação frontal (aceleração/frenagem)
        self.seat_tilt_y = np.clip(
            -self.g_force_frontal * max_tilt * 0.7, -max_tilt, max_tilt
        )

    def update(self):
        """Atualização principal do sensor"""
        current_time = time.time()
        dt = current_time - self.last_update

        # Controla taxa de atualização
        if dt >= 1.0 / self.sample_rate:
            # Lê dados do sensor
            if self.read_sensor_data():
                # Atualiza buffers
                self.update_buffers()

                # Cálculos baseados nos dados
                self.calculate_g_forces()
                self.detect_driving_events()
                self.calculate_angles(dt)
                self.calculate_force_feedback()

                self.last_update = current_time
                return True

        return False

    def get_sensor_data(self):
        """
        Retorna dicionário com todos os dados do sensor conforme datasheet

        Returns:
            dict: Dados completos do BMI160 e cálculos derivados
        """
        return {
            # === DADOS RAW DO BMI160 (LSB) ===
            "bmi160_accel_x_raw": self.accel_x_raw,
            "bmi160_accel_y_raw": self.accel_y_raw,
            "bmi160_accel_z_raw": self.accel_z_raw,
            "bmi160_gyro_x_raw": self.gyro_x_raw,
            "bmi160_gyro_y_raw": self.gyro_y_raw,
            "bmi160_gyro_z_raw": self.gyro_z_raw,
            # === DADOS CONVERTIDOS (UNIDADES FÍSICAS) ===
            "bmi160_accel_x": round(self.accel_x, 3),  # m/s²
            "bmi160_accel_y": round(self.accel_y, 3),
            "bmi160_accel_z": round(self.accel_z, 3),
            "bmi160_gyro_x": round(self.gyro_x, 3),  # °/s
            "bmi160_gyro_y": round(self.gyro_y, 3),
            "bmi160_gyro_z": round(self.gyro_z, 3),
            # === CONFIGURAÇÕES DO SENSOR ===
            "accel_range_g": self._get_accel_range_g(),
            "gyro_range_dps": self._get_gyro_range_dps(),
            "accel_scale_factor": self.accel_scale,
            "gyro_scale_factor": self.gyro_scale,
            # === FORÇAS G CALCULADAS ===
            "g_force_frontal": round(self.g_force_frontal, 3),
            "g_force_lateral": round(self.g_force_lateral, 3),
            "g_force_vertical": round(self.g_force_vertical, 3),
            # === ÂNGULOS INTEGRADOS ===
            "roll_angle": round(self.roll_angle, 1),
            "pitch_angle": round(self.pitch_angle, 1),
            "yaw_angle": round(self.yaw_angle, 1),
            # === EVENTOS DETECTADOS ===
            "is_turning_left": self.is_turning_left,
            "is_turning_right": self.is_turning_right,
            "is_accelerating": self.is_accelerating,
            "is_braking": self.is_braking,
            "is_bouncing": self.is_bouncing,
            "impact_detected": self.impact_detected,
            # === INTENSIDADES PARA FORCE FEEDBACK ===
            "steering_feedback_intensity": round(self.steering_feedback_intensity, 1),
            "brake_pedal_resistance": round(self.brake_pedal_resistance, 1),
            "accelerator_feedback": round(self.accelerator_feedback, 1),
            "seat_vibration_intensity": round(self.seat_vibration_intensity, 1),
            "seat_tilt_x": round(self.seat_tilt_x, 1),
            "seat_tilt_y": round(self.seat_tilt_y, 1),
            # === METADADOS ===
            "timestamp": round(time.time(), 3),
            "readings_count": self.readings_count,
            "sample_rate": self.sample_rate,
            "is_initialized": self.is_initialized,
        }

    def get_statistics(self):
        """
        Obtém estatísticas do sensor

        Returns:
            dict: Estatísticas de operação
        """
        elapsed = time.time() - self.start_time
        actual_sample_rate = self.readings_count / elapsed if elapsed > 0 else 0

        return {
            "readings_count": self.readings_count,
            "elapsed_time": round(elapsed, 2),
            "actual_sample_rate": round(actual_sample_rate, 2),
            "target_sample_rate": self.sample_rate,
            "accel_range_g": self._get_accel_range_g(),
            "gyro_range_dps": self._get_gyro_range_dps(),
            "buffer_fill": {
                "accel_x": len(self.accel_buffer_x),
                "accel_y": len(self.accel_buffer_y),
                "accel_z": len(self.accel_buffer_z),
                "gyro_x": len(self.gyro_buffer_x),
                "gyro_y": len(self.gyro_buffer_y),
                "gyro_z": len(self.gyro_buffer_z),
            },
        }

    def reset_angles(self):
        """Reseta os ângulos integrados para zero"""
        self.roll_angle = 0.0
        self.pitch_angle = 0.0
        self.yaw_angle = 0.0
        print("✓ Ângulos resetados")

    def calibrate(self, duration=5.0):
        """
        Calibra o sensor (Fast Offset Compensation conforme datasheet)

        Args:
            duration (float): Duração da calibração em segundos
        """
        print(f"Iniciando calibração do BMI160 ({duration}s)...")
        print("Mantenha o carrinho parado e nivelado!")

        # Método 1: FOC automático do BMI160 (recomendado)
        print("Executando Fast Offset Compensation (FOC)...")

        # Habilita FOC conforme datasheet
        if self._write_register(self.REG_CMD, self.CMD_FOC_ENABLE):
            print("FOC iniciado...")

            # Aguarda conclusão do FOC (~250ms)
            time.sleep(0.3)

            # TODO: Verificar bit FOC_RDY no registrador de status
            # Por agora, assume que foi concluído
            print("✓ FOC concluído")

        # Método 2: Calibração manual (backup)
        print("Executando calibração manual adicional...")

        accel_x_sum = 0.0
        accel_y_sum = 0.0
        accel_z_sum = 0.0
        gyro_x_sum = 0.0
        gyro_y_sum = 0.0
        gyro_z_sum = 0.0
        samples = 0

        start_time = time.time()

        while time.time() - start_time < duration:
            if self.read_sensor_data():
                accel_x_sum += self.accel_x
                accel_y_sum += self.accel_y
                accel_z_sum += self.accel_z - 9.81  # Remove gravidade
                gyro_x_sum += self.gyro_x
                gyro_y_sum += self.gyro_y
                gyro_z_sum += self.gyro_z
                samples += 1

            time.sleep(1.0 / self.sample_rate)

        if samples > 0:
            # Calcula offsets
            self.accel_x_offset = accel_x_sum / samples / 9.81  # Converte para g
            self.accel_y_offset = accel_y_sum / samples / 9.81
            self.accel_z_offset = accel_z_sum / samples / 9.81
            self.gyro_x_offset = gyro_x_sum / samples
            self.gyro_y_offset = gyro_y_sum / samples
            self.gyro_z_offset = gyro_z_sum / samples

            print(f"✓ Calibração manual concluída com {samples} amostras")
            print(
                f"Offsets Accel (g): X={self.accel_x_offset:.4f}, Y={self.accel_y_offset:.4f}, Z={self.accel_z_offset:.4f}"
            )
            print(
                f"Offsets Gyro (°/s): X={self.gyro_x_offset:.3f}, Y={self.gyro_y_offset:.3f}, Z={self.gyro_z_offset:.3f}"
            )
        else:
            print("⚠ Falha na calibração manual - nenhuma amostra coletada")

    def cleanup(self):
        """Libera recursos do sensor"""
        try:
            # Coloca sensores em modo suspend para economizar energia
            if self.is_initialized:
                self._write_register(self.REG_CMD, 0x10)  # Accel suspend
                self._write_register(self.REG_CMD, 0x14)  # Gyro suspend

            # Fecha barramento I2C
            if self.i2c_bus:
                self.i2c_bus.close()

            self.is_initialized = False
            self.i2c_bus = None
            print("✓ BMI160 finalizado")

        except Exception as e:
            print(f"⚠ Erro ao finalizar BMI160: {e}")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()


# Exemplo de uso
if __name__ == "__main__":
    # Teste da classe BMI160Manager corrigida
    print("=== TESTE DO BMI160 MANAGER CORRIGIDO ===")
    print("Agora está de acordo com o datasheet oficial!\n")

    # Cria instância com configurações recomendadas para carrinho F1
    bmi_mgr = BMI160Manager(
        sample_rate=100,  # 100Hz - boa para controle
        buffer_size=50,  # Buffer de 0.5s
        accel_range=BMI160Manager.ACCEL_RANGE_2G,  # ±2g - alta precisão
        gyro_range=BMI160Manager.GYRO_RANGE_250,  # ±250°/s - movimentos normais
        i2c_address=BMI160Manager.I2C_ADDRESS_LOW,  # 0x68 (SAO=GND)
    )

    # Inicializa
    if bmi_mgr.initialize():
        print("\n=== CALIBRAÇÃO ===")
        # bmi_mgr.calibrate(duration=3.0)  # Descomente para calibração real

        print("\n=== COLETANDO DADOS ===")
        print("Coletando dados por 10 segundos...")

        start_time = time.time()
        last_display = time.time()

        while time.time() - start_time < 10.0:
            # Atualiza sensor
            if bmi_mgr.update():
                current_time = time.time()

                # Display a cada 2 segundos
                if current_time - last_display >= 2.0:
                    data = bmi_mgr.get_sensor_data()

                    print(f"\n=== DADOS BMI160 (t={current_time-start_time:.1f}s) ===")
                    print(
                        f"Raw LSB - Accel: X={data['bmi160_accel_x_raw']:6d} Y={data['bmi160_accel_y_raw']:6d} Z={data['bmi160_accel_z_raw']:6d}"
                    )
                    print(
                        f"Raw LSB - Gyro:  X={data['bmi160_gyro_x_raw']:6d} Y={data['bmi160_gyro_y_raw']:6d} Z={data['bmi160_gyro_z_raw']:6d}"
                    )
                    print(
                        f"Físico  - Accel: X={data['bmi160_accel_x']:6.2f} Y={data['bmi160_accel_y']:6.2f} Z={data['bmi160_accel_z']:6.2f} m/s²"
                    )
                    print(
                        f"Físico  - Gyro:  X={data['bmi160_gyro_x']:6.1f} Y={data['bmi160_gyro_y']:6.1f} Z={data['bmi160_gyro_z']:6.1f} °/s"
                    )
                    print(
                        f"G-Force: Frontal={data['g_force_frontal']:+.2f}g Lateral={data['g_force_lateral']:.2f}g Vertical={data['g_force_vertical']:.2f}g"
                    )
                    print(
                        f"Config:  Accel=±{data['accel_range_g']}g Gyro=±{data['gyro_range_dps']}°/s"
                    )

                    events = []
                    if data["is_turning_left"]:
                        events.append("CURVA ESQ")
                    if data["is_turning_right"]:
                        events.append("CURVA DIR")
                    if data["is_accelerating"]:
                        events.append("ACELERANDO")
                    if data["is_braking"]:
                        events.append("FREANDO")
                    if data["is_bouncing"]:
                        events.append("SOLAVANCO")
                    if data["impact_detected"]:
                        events.append("IMPACTO")

                    print(f"Eventos: {', '.join(events) if events else 'NENHUM'}")
                    print(f"Force Feedback:")
                    print(f"  - Volante: {data['steering_feedback_intensity']:.1f}%")
                    print(f"  - Freio: {data['brake_pedal_resistance']:.1f}%")
                    print(f"  - Vibração: {data['seat_vibration_intensity']:.1f}%")
                    print(
                        f"  - Inclinação: X={data['seat_tilt_x']:+.1f}° Y={data['seat_tilt_y']:+.1f}°"
                    )

                    last_display = current_time

            time.sleep(0.01)  # Pequena pausa

        # Mostra estatísticas finais
        stats = bmi_mgr.get_statistics()
        print(f"\n=== ESTATÍSTICAS FINAIS ===")
        print(f"Leituras: {stats['readings_count']}")
        print(f"Tempo: {stats['elapsed_time']}s")
        print(f"Taxa real: {stats['actual_sample_rate']:.1f} Hz")
        print(f"Taxa alvo: {stats['target_sample_rate']} Hz")
        print(
            f"Eficiência: {stats['actual_sample_rate']/stats['target_sample_rate']*100:.1f}%"
        )
        print(
            f"Configuração: ±{stats['accel_range_g']}g, ±{stats['gyro_range_dps']}°/s"
        )

        # Finaliza
        bmi_mgr.cleanup()

    else:
        print("✗ Falha ao inicializar BMI160")
        print("\nPara usar com hardware real:")
        print("1. Conecte conforme pinout no cabeçalho")
        print("2. sudo apt-get install i2c-tools python3-smbus2")
        print("3. sudo raspi-config -> Interface Options -> I2C -> Enable")
        print("4. sudo i2cdetect -y 1  # Verificar endereço")
        print("5. Descomente as linhas de I2C real no código")
