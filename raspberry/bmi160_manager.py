#!/usr/bin/env python3
"""
bmi160_manager.py - Gerenciamento do Sensor BMI160 CORRIGIDO
Agora está de acordo com o datasheet oficial

PINOUT BMI160 (GY-BMI160) -> RASPBERRY PI 4:
============================================
Pinos do módulo: VIN ; 3V3 ; GND ; SCL ; SDA ; CS ; SAO

BMI160 Module -> Raspberry Pi 4 (GPIO)
  - VIN      -> (não conectado)                [Entrada 5V - não usar]
  - 3V3      -> Pin 1  (3.3V)                  [Alimentação 3.3V]
  - GND      -> Pin 6  (GND)                   [Terra comum]
  - SCL      -> Pin 5  (GPIO3/SCL1)            [I2C Clock]
  - SDA      -> Pin 3  (GPIO2/SDA1)            [I2C Data]
  - CS       -> Pin 1  (3.3V)                  [Chip Select - HIGH para I2C]
  - SAO      -> Pin 6  (GND)                   [Endereço 0x68]

Diagrama de conexão:
                  GY-BMI160
                 ┌─────────┐
    (NC)    VIN ─┤         │
    3.3V    3V3 ─┤         │
    GND     GND ─┤         │
    GPIO3   SCL ─┤         │
    GPIO2   SDA ─┤         │
    3.3V     CS ─┤         │  ← HIGH = modo I2C
    GND     SAO ─┤         │  ← GND = endereço 0x68
                 └─────────┘

ENDEREÇO I2C UTILIZADO NESTE PROJETO:
=====================================
  ┌─────────────────────────────────────────────────────────┐
  │  ENDEREÇO: 0x68  (SAO/SDO conectado ao GND)            │
  └─────────────────────────────────────────────────────────┘

  Configuração do pino SAO/SDO:
    - SAO/SDO → GND  = Endereço 0x68 (PADRÃO DESTE PROJETO)
    - SAO/SDO → VCC  = Endereço 0x69 (alternativo)

  Verificar detecção I2C:
    $ sudo i2cdetect -y 1
    Esperado: 0x68 aparece na saída

MAPA DE ENDEREÇOS I2C DO PROJETO (sem conflitos):
=================================================
  - 0x40 : INA219 (Sensor de corrente RPi) - Padrão
  - 0x41 : PCA9685 (PWM Driver - servos) - A0 soldado
  - 0x68 : BMI160 (IMU - este sensor) ← ENDEREÇO ATUAL
  Nota: ACS758 agora lidos via Arduino Pro Micro (USB Serial)

CARACTERÍSTICAS BMI160 (Datasheet Bosch):
=========================================
  - Acelerômetro: ±2g, ±4g, ±8g, ±16g (16-bit)
  - Giroscópio: ±125, ±250, ±500, ±1000, ±2000 °/s (16-bit)
  - ODR: 25Hz a 1600Hz
  - Chip ID: 0xD1
  - Tensão: 1.71V a 3.6V (módulo aceita 3.3V ou 5V)

REGISTRADORES IMPORTANTES (conforme datasheet):
===============================================
  0x00 - CHIP_ID (deve retornar 0xD1)
  0x40 - ACC_CONF (configuração acelerômetro)
  0x41 - ACC_RANGE (range acelerômetro)
  0x42 - GYR_CONF (configuração giroscópio)
  0x43 - GYR_RANGE (range giroscópio)
  0x7E - CMD (comandos de controle)
  0x12-0x17 - ACCEL_DATA (6 bytes: X_LSB, X_MSB, Y_LSB, Y_MSB, Z_LSB, Z_MSB)
  0x0C-0x11 - GYRO_DATA (6 bytes: X_LSB, X_MSB, Y_LSB, Y_MSB, Z_LSB, Z_MSB)
"""

import threading
import time


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
        accel_range=None,  # Será ACCEL_RANGE_2G por padrão
        gyro_range=None,  # Será GYRO_RANGE_250 por padrão
        i2c_address=None,  # Será I2C_ADDRESS_LOW por padrão
    ):
        """
        Inicializa o gerenciador do BMI160

        Args:
            sample_rate (int): Taxa de amostragem em Hz (25-1600)
            accel_range (int): Range do acelerômetro (usar constantes ACCEL_RANGE_*)
            gyro_range (int): Range do giroscópio (usar constantes GYRO_RANGE_*)
            i2c_address (int): Endereço I2C do sensor
        """
        # Valores padrão recomendados para veículos (melhor dinâmica)
        self.accel_range = (
            accel_range if accel_range is not None else self.ACCEL_RANGE_4G
        )
        self.gyro_range = gyro_range if gyro_range is not None else self.GYRO_RANGE_500
        self.i2c_address = (
            i2c_address if i2c_address is not None else self.I2C_ADDRESS_LOW
        )

        self.sample_rate = sample_rate

        # Lock para thread-safety (acesso concorrente por threads de sensores e TX)
        self.state_lock = threading.Lock()

        # Mapear sample_rate para ODR
        self.odr_value = self._get_odr_value(sample_rate)

        # Fatores de escala baseados nos ranges selecionados
        self.accel_scale = self.ACCEL_SCALE_FACTORS[self.accel_range]
        self.gyro_scale = self.GYRO_SCALE_FACTORS[self.gyro_range]

        # Objetos de comunicação
        self.i2c_bus = None
        self.bmi160 = None
        self.is_initialized = False

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
            if self.i2c_bus:
                # I2C real com delay obrigatório
                self.i2c_bus.write_byte_data(self.i2c_address, reg, value)
                time.sleep(0.005)  # 5ms delay otimizado
            else:
                print("⚠ I2C bus não inicializado")
                return False

        except Exception as e:
            print(f"⚠ Erro ao escrever registrador 0x{reg:02X}: {e}")
            return False
        return True

    def _read_register(self, reg):
        """Lê valor de registrador via I2C"""
        try:
            if self.i2c_bus:
                # I2C real com delay obrigatório
                time.sleep(0.005)  # 5ms delay otimizado
                return self.i2c_bus.read_byte_data(self.i2c_address, reg)
            else:
                print("⚠ I2C bus não inicializado")
                return None

        except Exception as e:
            print(f"⚠ Erro ao ler registrador 0x{reg:02X}: {e}")
            return None

    def _read_sensor_registers(self, start_reg, num_bytes):
        """Lê múltiplos registradores sequenciais com recuperação de erros"""
        if not self.i2c_bus:
            print("⚠ I2C bus não inicializado")
            return None

        # Tenta ler com até 3 tentativas
        for attempt in range(3):
            try:
                # I2C real
                return self.i2c_bus.read_i2c_block_data(
                    self.i2c_address, start_reg, num_bytes
                )

            except OSError as e:
                if e.errno == 5:  # Input/output error
                    if attempt == 0:
                        # Primeira tentativa falhou - aguarda um pouco
                        time.sleep(0.001)  # 1ms
                    elif attempt == 1:
                        # Segunda tentativa falhou - aguarda mais e tenta reinicializar I2C
                        time.sleep(0.005)  # 5ms
                        try:
                            # Tenta reinicializar o barramento I2C
                            import smbus2

                            self.i2c_bus = smbus2.SMBus(1)
                            time.sleep(0.001)
                        except Exception:
                            pass
                    else:
                        # Terceira tentativa falhou - reporta erro mas não trava o sistema
                        if not hasattr(self, "_error_count"):
                            self._error_count = 0
                        self._error_count += 1

                        # Só mostra erro a cada 50 falhas para evitar spam
                        if self._error_count % 50 == 0:
                            print(
                                f"⚠ BMI160 I2C Error (erro #{self._error_count}): reg 0x{start_reg:02X}"
                            )

                        # Retorna dados zero para manter o sistema funcionando
                        return [0] * num_bytes
                else:
                    # Outro tipo de erro OSError
                    print(f"⚠ Erro I2C ao ler reg 0x{start_reg:02X}: {e}")
                    return [0] * num_bytes

            except Exception as e:
                # Outros erros
                print(f"⚠ Erro inesperado ao ler reg 0x{start_reg:02X}: {e}")
                return [0] * num_bytes

        # Não deveria chegar aqui, mas por segurança
        return [0] * num_bytes

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
                print("✓ I2C inicializado com smbus2")
            except ImportError:
                try:
                    # Fallback para smbus (sistema)
                    import smbus

                    self.i2c_bus = smbus.SMBus(1)
                    print("✓ I2C inicializado com smbus")
                except ImportError:
                    print(
                        "❌ Nem smbus2 nem smbus disponíveis - hardware I2C obrigatório"
                    )
                    return False
                except Exception as e:
                    print(f"❌ Erro no smbus: {e} - hardware I2C obrigatório")
                    return False
            except Exception as e:
                print(f"⚠ Erro no smbus2: {e} - tentando smbus...")
                try:
                    import smbus

                    self.i2c_bus = smbus.SMBus(1)
                    print("✓ I2C inicializado com smbus")
                except Exception as e2:
                    print(f"❌ Erro no smbus também: {e2} - hardware I2C obrigatório")
                    return False

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

            # BMI160 precisa de tempo para resetar completamente
            print("Aguardando estabilização após reset...")
            time.sleep(0.2)  # 200ms para garantir reset completo

            # 4. Verificar se voltou depois do reset (com retry)
            chip_id_after_reset = None
            for retry in range(3):
                chip_id_after_reset = self._read_register(self.REG_CHIP_ID)
                if chip_id_after_reset == self.CHIP_ID_BMI160:
                    break
                print(f"Retry {retry+1}: aguardando sensor...")
                time.sleep(0.1)

            if chip_id_after_reset != self.CHIP_ID_BMI160:
                print(
                    f"❌ CHIP_ID após reset: 0x{chip_id_after_reset if chip_id_after_reset else 'None':02X}"
                )
                # Sensor pode estar funcional mesmo sem confirmar reset
                print("⚠ Continuando sem confirmação de reset...")
            else:
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
            time.sleep(0.080)  # Startup time do giroscópio (80ms conforme datasheet)

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
                # Usa dados anteriores ou zeros se não houver
                accel_data = getattr(self, "_last_accel_data", [0, 0, 0, 0, 0, 0])
            else:
                self._last_accel_data = accel_data

            # Ler dados do giroscópio (6 bytes a partir do 0x0C)
            gyro_data = self._read_sensor_registers(self.REG_GYRO_DATA, 6)
            if gyro_data is None:
                # Usa dados anteriores ou zeros se não houver
                gyro_data = getattr(self, "_last_gyro_data", [0, 0, 0, 0, 0, 0])
            else:
                self._last_gyro_data = gyro_data

            # Debug: mostrar dados raw lidos do I2C
            if hasattr(self, "_debug_counter"):
                self._debug_counter += 1
            else:
                self._debug_counter = 1

            if self._debug_counter % 200 == 0:  # A cada ~1s
                print(
                    f"🔍 BMI160 RAW I2C: accel_data={accel_data}, gyro_data={gyro_data}"
                )

            # CONVERSÃO CONFORME DATASHEET:
            # Dados em complemento de 2, LSB primeiro

            with self.state_lock:
                # Hardware real - converte dados I2C
                self.accel_x_raw = self._bytes_to_int16(accel_data[0], accel_data[1])
                self.accel_y_raw = self._bytes_to_int16(accel_data[2], accel_data[3])
                self.accel_z_raw = self._bytes_to_int16(accel_data[4], accel_data[5])

                self.gyro_x_raw = self._bytes_to_int16(gyro_data[0], gyro_data[1])
                self.gyro_y_raw = self._bytes_to_int16(gyro_data[2], gyro_data[3])
                self.gyro_z_raw = self._bytes_to_int16(gyro_data[4], gyro_data[5])

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

                self.gyro_x = (
                    self.gyro_x_raw * self.gyro_scale - self.gyro_x_offset
                )  # °/s
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

    def update(self):
        """Atualização principal do sensor - apenas lê dados, não processa"""
        current_time = time.time()
        dt = current_time - self.last_update

        # Controla taxa de atualização
        if dt >= 1.0 / self.sample_rate:
            # Lê dados do sensor
            if self.read_sensor_data():
                # Apenas atualiza o timestamp - NENHUM processamento
                self.last_update = current_time
                return True

        return False

    def get_sensor_data(self):
        """
        Retorna apenas os dados brutos do BMI160 - SEM processamento

        Returns:
            dict: Dados RAW do BMI160 apenas
        """
        with self.state_lock:
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
        }

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
