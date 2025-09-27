#!/usr/bin/env python3
"""
test_servo_360_graus.py - Teste de Rotação Completa 360°
Testa se o MG996R consegue fazer rotação contínua
"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

print("🌀 === TESTE ROTAÇÃO 360° ===")
print("Testando se o MG996R consegue rotação contínua")
print("Servos: Canal 0 (freio), Canal 1 (freio), Canal 2 (direção)")

try:
    # Inicializar PCA9685
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50
    print("✓ PCA9685 inicializado @ 50Hz")

    # Configurar servos nos 3 canais
    servos = []
    for channel in [0, 1, 2]:
        servo_obj = servo.Servo(
            pca.channels[channel],
            min_pulse=500,          # Mais amplo: 0.5ms
            max_pulse=2500,         # Mais amplo: 2.5ms
        )
        servos.append(servo_obj)
        print(f"✓ Servo configurado no canal {channel}")

    print("\n=== TESTE 1: RANGE EXTREMO (0° a 360°) ===")

    # Teste com valores além de 180°
    extreme_angles = [0, 45, 90, 135, 180, 225, 270, 315, 360]

    for angle in extreme_angles:
        print(f"\nTestando {angle}°")

        for i, servo_obj in enumerate(servos):
            try:
                servo_obj.angle = angle
                print(f"  Canal {i}: {angle}° ✓")
            except Exception as e:
                print(f"  Canal {i}: {angle}° ❌ ({e})")

        time.sleep(2)
        input("  Pressione ENTER para próximo ângulo...")

    print("\n=== TESTE 2: ROTAÇÃO CONTÍNUA ===")

    # Teste de rotação contínua
    print("Testando rotação contínua no canal 2 (direção)")

    servo_2 = servos[2]  # Canal 2 (direção)

    print("\n1. Rotação horária completa")
    for angle in range(0, 361, 30):  # 0°, 30°, 60°... 360°
        try:
            servo_2.angle = angle
            print(f"   {angle}° ✓")
            time.sleep(0.5)
        except Exception as e:
            print(f"   {angle}° ❌ ({e})")

    print("\n2. Rotação anti-horária completa")
    for angle in range(360, -1, -30):  # 360°, 330°, 300°... 0°
        try:
            servo_2.angle = angle
            print(f"   {angle}° ✓")
            time.sleep(0.5)
        except Exception as e:
            print(f"   {angle}° ❌ ({e})")

    print("\n=== TESTE 3: DUTY CYCLE DIRETO ===")

    # Se o servo não aceitar ângulos > 180°, testar duty cycle direto
    print("Testando duty cycles extremos no canal 2")

    channel_2 = pca.channels[2]

    # Duty cycles para diferentes posições
    # PCA9685 é 12-bit: 0 a 4095
    # Para 50Hz (20ms período):
    # 0.5ms = 2.5% = ~102
    # 1.0ms = 5% = ~204
    # 1.5ms = 7.5% = ~307
    # 2.0ms = 10% = ~409
    # 2.5ms = 12.5% = ~512

    duty_cycles = [
        (102, "0.5ms - Extremo"),
        (204, "1.0ms - Mínimo padrão"),
        (307, "1.5ms - Centro"),
        (409, "2.0ms - Máximo padrão"),
        (512, "2.5ms - Extremo"),
        (600, "Além do padrão 1"),
        (700, "Além do padrão 2"),
        (800, "Além do padrão 3"),
    ]

    for duty, description in duty_cycles:
        print(f"\nDuty cycle: {duty} ({description})")
        try:
            channel_2.duty_cycle = duty
            print("  ✓ Comando aceito")
            time.sleep(1.5)
            input("  Pressione ENTER para próximo...")
        except Exception as e:
            print(f"  ❌ Erro: {e}")

    print("\n=== TESTE 4: ROTAÇÃO CONTÍNUA COM DUTY CYCLE ===")

    # Testar se o servo entra em modo de rotação contínua
    print("Tentando ativar rotação contínua...")

    # Valores que podem ativar rotação contínua em alguns servos
    continuous_values = [0, 50, 100, 4095]

    for value in continuous_values:
        print(f"\nTentando duty cycle {value} por 3 segundos...")
        channel_2.duty_cycle = value
        time.sleep(3)

    # Voltar ao centro
    channel_2.duty_cycle = 307  # 1.5ms
    print("\n✓ Retornado ao centro")

    print("\n✅ TESTE COMPLETO!")
    print("\nResultados:")
    print("- Se funcionou até 180°: Servo padrão (normal)")
    print("- Se funcionou até 360°: Servo com rotação contínua")
    print("- Se duty cycles extremos funcionaram: Hardware mais flexível")

except KeyboardInterrupt:
    print("\n⚠️ Teste interrompido")
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        # Centralizar todos os servos
        for servo_obj in servos:
            servo_obj.angle = 90
        # Ou usar duty cycle neutro
        for channel in [0, 1, 2]:
            pca.channels[channel].duty_cycle = 307  # 1.5ms
        pca.deinit()
        print("✓ Sistema finalizado")
    except:
        pass