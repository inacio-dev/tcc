#!/usr/bin/env python3
"""
debug_servo_commands.py - Debug dos comandos sendo enviados para o servo
Compara teste direto vs steering_manager
"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

print("🔍 === DEBUG DOS COMANDOS DO SERVO ===")

def test_direct_commands():
    """Teste direto - igual ao que funcionou"""
    print("\n1. === TESTE DIRETO (que funcionou) ===")

    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50

    # Configuração do teste direto
    direct_servo = servo.Servo(
        pca.channels[2],
        min_pulse=1000,  # 1ms
        max_pulse=2000,  # 2ms
    )

    print("Configuração TESTE DIRETO:")
    print(f"  min_pulse: 1000 µs")
    print(f"  max_pulse: 2000 µs")
    print(f"  frequency: {pca.frequency} Hz")

    # Teste os mesmos ângulos
    test_angles = [90, 45, 135, 0, 180, 90]

    for angle in test_angles:
        print(f"\nComando direto: {angle}°")
        direct_servo.angle = angle

        # Mostrar o duty_cycle sendo usado
        channel = pca.channels[2]
        print(f"  duty_cycle: {channel.duty_cycle} (0x{channel.duty_cycle:04X})")

        time.sleep(2)
        input("  Pressione ENTER para próximo...")

    pca.deinit()
    return True

def test_steering_manager_config():
    """Teste com configuração do steering_manager"""
    print("\n2. === TESTE COM CONFIG STEERING_MANAGER ===")

    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50

    # Configuração idêntica ao steering_manager
    PULSE_MIN = 1.0  # 1.0ms
    PULSE_MAX = 2.0  # 2.0ms

    steering_servo = servo.Servo(
        pca.channels[2],
        min_pulse=int(PULSE_MIN * 1000),  # 1000 µs
        max_pulse=int(PULSE_MAX * 1000),  # 2000 µs
    )

    print("Configuração STEERING_MANAGER:")
    print(f"  PULSE_MIN: {PULSE_MIN} ms = {int(PULSE_MIN * 1000)} µs")
    print(f"  PULSE_MAX: {PULSE_MAX} ms = {int(PULSE_MAX * 1000)} µs")
    print(f"  frequency: {pca.frequency} Hz")

    # Simular os cálculos do steering_manager
    STEERING_CENTER = 90
    STEERING_MIN_ANGLE = 45
    STEERING_MAX_ANGLE = 135

    print("\nConstantes do steering_manager:")
    print(f"  STEERING_CENTER: {STEERING_CENTER}°")
    print(f"  STEERING_MIN_ANGLE: {STEERING_MIN_ANGLE}°")
    print(f"  STEERING_MAX_ANGLE: {STEERING_MAX_ANGLE}°")

    # Simular inputs como no steering_manager
    test_inputs = [-100, -50, 0, 50, 100]  # Percentuais de direção
    max_steering_angle = 45.0

    for steering_input in test_inputs:
        # Cálculo do steering_manager
        target_angle = steering_input * (max_steering_angle / 100.0)
        servo_angle = STEERING_CENTER + target_angle

        # Limitação
        final_angle = max(STEERING_MIN_ANGLE, min(STEERING_MAX_ANGLE, servo_angle))

        print(f"\nInput: {steering_input}%")
        print(f"  target_angle: {target_angle:+6.1f}°")
        print(f"  servo_angle: {servo_angle:5.1f}°")
        print(f"  final_angle: {final_angle:5.1f}°")

        steering_servo.angle = final_angle

        # Mostrar o duty_cycle
        channel = pca.channels[2]
        print(f"  duty_cycle: {channel.duty_cycle} (0x{channel.duty_cycle:04X})")

        time.sleep(2)
        input("  Pressione ENTER para próximo...")

    pca.deinit()
    return True

def test_raw_duty_cycle():
    """Teste com duty_cycle direto"""
    print("\n3. === TESTE COM DUTY_CYCLE DIRETO ===")

    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50

    # Calcular duty_cycles para 1ms, 1.5ms, 2ms
    # PCA9685 é 12-bit (0-4095)
    # Para 50Hz: período = 20ms
    # 1ms = 1/20 = 5% = 0.05 * 4095 = ~205
    # 1.5ms = 1.5/20 = 7.5% = 0.075 * 4095 = ~307
    # 2ms = 2/20 = 10% = 0.1 * 4095 = ~410

    duty_cycles = [
        (205, "1.0ms (0°)"),
        (307, "1.5ms (90°)"),
        (410, "2.0ms (180°)")
    ]

    channel = pca.channels[2]

    for duty, description in duty_cycles:
        print(f"\nDuty cycle direto: {duty} ({description})")
        channel.duty_cycle = duty
        time.sleep(2)
        input("  Pressione ENTER para próximo...")

    pca.deinit()
    return True

def main():
    """Função principal"""
    try:
        # Teste 1: Direto (sabemos que funciona)
        test_direct_commands()

        # Teste 2: Configuração steering_manager
        test_steering_manager_config()

        # Teste 3: Duty cycle direto
        test_raw_duty_cycle()

        print("\n✅ Todos os testes concluídos!")
        print("\nCompare os duty_cycles entre os testes para identificar diferenças")

    except KeyboardInterrupt:
        print("\n⚠️ Teste interrompido")
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()