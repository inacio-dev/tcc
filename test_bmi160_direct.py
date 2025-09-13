#!/usr/bin/env python3
"""
Teste direto do BMI160 para diagnosticar problema
"""

import smbus2
import time

def test_bmi160():
    print("=== TESTE DIRETO BMI160 ===")

    # Conectar ao I2C
    try:
        bus = smbus2.SMBus(1)
        print("✓ I2C conectado")
    except Exception as e:
        print(f"❌ Erro I2C: {e}")
        return False

    address = 0x68
    print(f"Testando endereço: 0x{address:02X}")

    # Teste 1: Verificar se dispositivo responde
    print("\n--- Teste 1: Ping básico ---")
    try:
        # Tentar ler qualquer registrador
        result = bus.read_byte(address)
        print(f"✓ Dispositivo responde: 0x{result:02X}")
    except Exception as e:
        print(f"❌ Dispositivo não responde: {e}")

    # Teste 2: Tentar ler CHIP_ID com delays diferentes
    print("\n--- Teste 2: CHIP_ID com delays ---")
    for delay_ms in [0, 10, 50, 100, 200]:
        try:
            if delay_ms > 0:
                time.sleep(delay_ms / 1000.0)

            chip_id = bus.read_byte_data(address, 0x00)
            print(f"✓ CHIP_ID (delay {delay_ms}ms): 0x{chip_id:02X}")

            if chip_id == 0xD1:
                print("  → BMI160 identificado!")
                break

        except Exception as e:
            print(f"❌ CHIP_ID (delay {delay_ms}ms): {e}")

    # Teste 3: Soft reset + retry
    print("\n--- Teste 3: Soft Reset ---")
    try:
        print("Enviando soft reset...")
        bus.write_byte_data(address, 0x7E, 0xB6)
        print("✓ Comando de reset enviado")

        # Aguardar reset (BMI160 precisa de ~15ms)
        print("Aguardando 100ms...")
        time.sleep(0.1)

        # Tentar ler CHIP_ID após reset
        chip_id = bus.read_byte_data(address, 0x00)
        print(f"✓ CHIP_ID após reset: 0x{chip_id:02X}")

        if chip_id == 0xD1:
            print("  → Reset funcionou! BMI160 OK")
            return True

    except Exception as e:
        print(f"❌ Erro no reset: {e}")

    # Teste 4: Tentar outros endereços
    print("\n--- Teste 4: Outros endereços ---")
    for addr in [0x68, 0x69]:
        try:
            chip_id = bus.read_byte_data(addr, 0x00)
            print(f"✓ Endereço 0x{addr:02X}: CHIP_ID=0x{chip_id:02X}")
        except Exception as e:
            print(f"❌ Endereço 0x{addr:02X}: {e}")

    # Teste 5: Verificar se sensor está em suspend
    print("\n--- Teste 5: Verificar modo PMU ---")
    try:
        # Ler status dos power modes
        pmu_status = bus.read_byte_data(address, 0x03)
        print(f"PMU Status: 0x{pmu_status:02X}")

        # Bits 5:4 = Accel PMU, bits 3:2 = Gyro PMU
        accel_mode = (pmu_status >> 4) & 0x03
        gyro_mode = (pmu_status >> 2) & 0x03

        print(f"  Accel Mode: {accel_mode} ({'suspend' if accel_mode == 0 else 'normal' if accel_mode == 1 else 'low-power' if accel_mode == 2 else 'unknown'})")
        print(f"  Gyro Mode: {gyro_mode} ({'suspend' if gyro_mode == 0 else 'normal' if gyro_mode == 1 else 'fast-startup' if gyro_mode == 3 else 'unknown'})")

    except Exception as e:
        print(f"❌ Erro ao ler PMU status: {e}")

    bus.close()
    return False

if __name__ == "__main__":
    test_bmi160()