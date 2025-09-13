#!/usr/bin/env python3
"""
Teste direto do BMI160 para diagnosticar problema e testar comunicação completa
"""

import smbus2
import time

def bytes_to_int16(lsb, msb):
    """Converte 2 bytes para int16 com sinal (complemento de 2)"""
    value = (msb << 8) | lsb
    if value >= 32768:  # Se bit de sinal estiver setado
        value -= 65536
    return value

def test_bmi160_complete():
    print("=== TESTE COMPLETO BMI160 ===")

    # Conectar ao I2C
    try:
        bus = smbus2.SMBus(1)
        print("✓ I2C conectado")
    except Exception as e:
        print(f"❌ Erro I2C: {e}")
        return False

    address = 0x68
    print(f"Testando endereço: 0x{address:02X}")

    # Função auxiliar para leitura com delay
    def read_reg_safe(reg):
        time.sleep(0.01)  # 10ms delay obrigatório
        return bus.read_byte_data(address, reg)

    def write_reg_safe(reg, value):
        bus.write_byte_data(address, reg, value)
        time.sleep(0.01)  # 10ms delay obrigatório

    # Teste 1: CHIP_ID
    print("\n--- Teste 1: CHIP_ID ---")
    try:
        chip_id = read_reg_safe(0x00)
        print(f"✓ CHIP_ID: 0x{chip_id:02X}")
        if chip_id != 0xD1:
            print(f"⚠ CHIP_ID incorreto (esperado: 0xD1)")
            return False
    except Exception as e:
        print(f"❌ Erro ao ler CHIP_ID: {e}")
        return False

    # Teste 2: Verificar PMU Status inicial
    print("\n--- Teste 2: PMU Status inicial ---")
    try:
        pmu_status = read_reg_safe(0x03)
        print(f"PMU Status inicial: 0x{pmu_status:02X}")

        accel_mode = (pmu_status >> 4) & 0x03
        gyro_mode = (pmu_status >> 2) & 0x03

        print(f"  Accel: {accel_mode} ({'suspend' if accel_mode == 0 else 'normal' if accel_mode == 1 else 'low-power' if accel_mode == 2 else 'unknown'})")
        print(f"  Gyro: {gyro_mode} ({'suspend' if gyro_mode == 0 else 'normal' if gyro_mode == 1 else 'fast-startup' if gyro_mode == 3 else 'unknown'})")
    except Exception as e:
        print(f"❌ Erro ao ler PMU: {e}")

    # Teste 3: Ativar sensores
    print("\n--- Teste 3: Ativando sensores ---")
    try:
        # Ativar acelerômetro
        print("Ativando acelerômetro...")
        write_reg_safe(0x7E, 0x11)  # ACC normal mode
        time.sleep(0.01)

        # Ativar giroscópio
        print("Ativando giroscópio...")
        write_reg_safe(0x7E, 0x15)  # GYR normal mode
        time.sleep(0.06)  # Gyro precisa de 55ms

        print("✓ Comandos de ativação enviados")
    except Exception as e:
        print(f"❌ Erro ao ativar sensores: {e}")

    # Teste 4: Verificar PMU Status após ativação
    print("\n--- Teste 4: PMU Status após ativação ---")
    try:
        pmu_status = read_reg_safe(0x03)
        print(f"PMU Status após ativação: 0x{pmu_status:02X}")

        accel_mode = (pmu_status >> 4) & 0x03
        gyro_mode = (pmu_status >> 2) & 0x03

        print(f"  Accel: {accel_mode} ({'suspend' if accel_mode == 0 else 'normal' if accel_mode == 1 else 'low-power' if accel_mode == 2 else 'unknown'})")
        print(f"  Gyro: {gyro_mode} ({'suspend' if gyro_mode == 0 else 'normal' if gyro_mode == 1 else 'fast-startup' if gyro_mode == 3 else 'unknown'})")

        if accel_mode == 1 and gyro_mode == 1:
            print("✓ Ambos sensores ativados com sucesso!")
        else:
            print("⚠ Sensores podem não estar totalmente ativos")
    except Exception as e:
        print(f"❌ Erro ao verificar PMU: {e}")

    # Teste 5: Configurar ranges
    print("\n--- Teste 5: Configurando ranges ---")
    try:
        # Accel ±2g (0x03)
        write_reg_safe(0x41, 0x03)
        print("✓ Accel range: ±2g")

        # Gyro ±250°/s (0x03)
        write_reg_safe(0x43, 0x03)
        print("✓ Gyro range: ±250°/s")

        # Verificar se foi escrito
        accel_range = read_reg_safe(0x41)
        gyro_range = read_reg_safe(0x43)
        print(f"  Confirmação - Accel: 0x{accel_range:02X}, Gyro: 0x{gyro_range:02X}")

    except Exception as e:
        print(f"❌ Erro ao configurar ranges: {e}")

    # Teste 6: Configurar ODR (Output Data Rate)
    print("\n--- Teste 6: Configurando ODR ---")
    try:
        # ODR 200Hz = 0x09, BWP = 0x02
        acc_conf = 0x09 | (0x02 << 4)
        gyr_conf = 0x09 | (0x02 << 4)

        write_reg_safe(0x40, acc_conf)  # ACC_CONF
        write_reg_safe(0x42, gyr_conf)  # GYR_CONF

        print("✓ ODR configurado para 200Hz")

        # Verificar configuração
        acc_conf_read = read_reg_safe(0x40)
        gyr_conf_read = read_reg_safe(0x42)
        print(f"  Confirmação - ACC_CONF: 0x{acc_conf_read:02X}, GYR_CONF: 0x{gyr_conf_read:02X}")

    except Exception as e:
        print(f"❌ Erro ao configurar ODR: {e}")

    # Teste 7: Ler dados dos sensores
    print("\n--- Teste 7: Lendo dados dos sensores ---")
    try:
        print("Aguardando estabilização...")
        time.sleep(0.1)

        for i in range(5):
            print(f"\nLeitura {i+1}:")

            # Ler acelerômetro (6 bytes a partir de 0x12)
            accel_data = []
            for reg in range(0x12, 0x18):
                accel_data.append(read_reg_safe(reg))

            # Ler giroscópio (6 bytes a partir de 0x0C)
            gyro_data = []
            for reg in range(0x0C, 0x12):
                gyro_data.append(read_reg_safe(reg))

            # Converter para valores com sinal
            accel_x = bytes_to_int16(accel_data[0], accel_data[1])
            accel_y = bytes_to_int16(accel_data[2], accel_data[3])
            accel_z = bytes_to_int16(accel_data[4], accel_data[5])

            gyro_x = bytes_to_int16(gyro_data[0], gyro_data[1])
            gyro_y = bytes_to_int16(gyro_data[2], gyro_data[3])
            gyro_z = bytes_to_int16(gyro_data[4], gyro_data[5])

            print(f"  Accel RAW: X={accel_x:6d} Y={accel_y:6d} Z={accel_z:6d}")
            print(f"  Gyro RAW:  X={gyro_x:6d} Y={gyro_y:6d} Z={gyro_z:6d}")

            # Converter para unidades físicas
            # ±2g -> 2.0/32768 = 0.000061 g/LSB
            # ±250°/s -> 250.0/32768 = 0.0076 °/s/LSB
            accel_scale = 2.0 / 32768.0
            gyro_scale = 250.0 / 32768.0

            accel_x_g = accel_x * accel_scale
            accel_y_g = accel_y * accel_scale
            accel_z_g = accel_z * accel_scale

            gyro_x_dps = gyro_x * gyro_scale
            gyro_y_dps = gyro_y * gyro_scale
            gyro_z_dps = gyro_z * gyro_scale

            print(f"  Accel (g): X={accel_x_g:6.3f} Y={accel_y_g:6.3f} Z={accel_z_g:6.3f}")
            print(f"  Gyro(°/s): X={gyro_x_dps:6.1f} Y={gyro_y_dps:6.1f} Z={gyro_z_dps:6.1f}")

            # Verificar se dados fazem sentido
            total_g = (accel_x_g**2 + accel_y_g**2 + accel_z_g**2)**0.5
            print(f"  Magnitude total: {total_g:.3f}g (esperado ~1.0g em repouso)")

            time.sleep(0.2)

        print("\n✓ Teste de leitura concluído!")

    except Exception as e:
        print(f"❌ Erro ao ler dados: {e}")

    # Teste 8: Informações de status
    print("\n--- Teste 8: Status final ---")
    try:
        status = read_reg_safe(0x1B)  # STATUS register
        print(f"Status: 0x{status:02X}")

        if status & 0x80:
            print("  ✓ Dados do acelerômetro prontos")
        if status & 0x40:
            print("  ✓ Dados do giroscópio prontos")

    except Exception as e:
        print(f"❌ Erro ao ler status: {e}")

    bus.close()
    print("\n=== TESTE COMPLETO FINALIZADO ===")
    return True

if __name__ == "__main__":
    test_bmi160_complete()