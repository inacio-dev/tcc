#!/usr/bin/env python3
"""
test_brake_direto_simples.py - Teste DIRETO dos servos de freio
Usa comandos diretos como no test_servo_direto.py que funcionou
"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

print("🛑 === TESTE DIRETO FREIOS (SIMPLES) ===")
print("Usa comandos diretos nos servos de freio")
print("Canal 0: Freio frontal | Canal 1: Freio traseiro")

try:
    # Inicializar PCA9685 - EXATAMENTE como no test_servo_direto.py
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50
    print("✓ PCA9685 inicializado @ 50Hz")

    # Configurar servos - EXATAMENTE como no test_servo_direto.py
    front_brake_servo = servo.Servo(
        pca.channels[0],        # Canal 0 (freio frontal)
        min_pulse=1000,         # 1ms
        max_pulse=2000,         # 2ms
    )

    rear_brake_servo = servo.Servo(
        pca.channels[1],        # Canal 1 (freio traseiro)
        min_pulse=1000,         # 1ms
        max_pulse=2000,         # 2ms
    )
    print("✓ Servos de freio configurados (canais 0 e 1)")

    print("\n=== TESTE DE FREIOS INDIVIDUAIS ===")

    # Teste freio frontal
    print("\n1. Testando FREIO FRONTAL (Canal 0)")
    brake_sequence = [
        ("Solto", 90),          # Neutro
        ("Leve", 110),          # Pouco freio
        ("Médio", 130),         # Freio médio
        ("Forte", 150),         # Freio forte
        ("Máximo", 180),        # Freio máximo
        ("Solto", 90),          # Volta ao neutro
    ]

    for description, angle in brake_sequence:
        print(f"   Freio frontal {description}: {angle}°")
        front_brake_servo.angle = angle
        time.sleep(1.5)
        input("     Pressione ENTER para próximo...")

    # Teste freio traseiro
    print("\n2. Testando FREIO TRASEIRO (Canal 1)")
    for description, angle in brake_sequence:
        print(f"   Freio traseiro {description}: {angle}°")
        rear_brake_servo.angle = angle
        time.sleep(1.5)
        input("     Pressione ENTER para próximo...")

    print("\n=== TESTE DE FREIOS COMBINADOS ===")

    # Teste com ambos os freios
    combined_tests = [
        ("Sem freio", 90, 90),
        ("Freio leve", 110, 105),       # Mais dianteiro
        ("Freio médio", 130, 120),      # Balanço 60/40
        ("Freio forte", 150, 135),      # Balanço 60/40
        ("Freio máximo", 180, 160),     # Máximo com balanço
        ("Freio emergência", 180, 180), # Ambos no máximo
        ("Sem freio", 90, 90),
    ]

    for description, front_angle, rear_angle in combined_tests:
        print(f"\n🛑 {description}")
        print(f"   Frontal: {front_angle}° | Traseiro: {rear_angle}°")

        # Comandos DIRETOS
        front_brake_servo.angle = front_angle
        rear_brake_servo.angle = rear_angle

        time.sleep(2)
        input("   Pressione ENTER para próximo...")

    print("\n=== TESTE DE VELOCIDADE ===")

    # Teste de freada de emergência
    print("\n1. Freada de emergência (rápida)")
    for cycle in range(3):
        print(f"   Emergência {cycle+1}/3")

        # Sem freio → Freio máximo → Sem freio
        front_brake_servo.angle = 90    # Solto
        rear_brake_servo.angle = 90     # Solto
        time.sleep(0.5)

        front_brake_servo.angle = 180   # Máximo
        rear_brake_servo.angle = 180    # Máximo
        time.sleep(1.0)

        front_brake_servo.angle = 90    # Solto
        rear_brake_servo.angle = 90     # Solto
        time.sleep(0.5)

    print("\n2. Modulação gradual")
    # Aplicação gradual do freio
    for angle in range(90, 181, 10):  # 90°, 100°, 110°... 180°
        print(f"   Freio gradual: {angle}°")
        front_brake_servo.angle = angle
        rear_brake_servo.angle = angle - 10  # Traseiro um pouco menos
        time.sleep(0.8)

    # Liberação gradual
    for angle in range(180, 89, -10):  # 180°, 170°, 160°... 90°
        print(f"   Liberação: {angle}°")
        front_brake_servo.angle = angle
        rear_brake_servo.angle = angle - 10
        time.sleep(0.5)

    # Posição neutra final
    front_brake_servo.angle = 90
    rear_brake_servo.angle = 90
    print("\n✓ Freios liberados (posição neutra)")

    print("\n✅ Teste concluído!")
    print("\nSe os servos se moveram:")
    print("  ✓ Hardware está OK")
    print("  ✓ O problema está no brake_manager.py")
    print("\nSe os servos NÃO se moveram:")
    print("  ❌ Problema de hardware (alimentação, conexão)")

except KeyboardInterrupt:
    print("\n⚠️ Teste interrompido")
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        # Liberar freios
        front_brake_servo.angle = 90
        rear_brake_servo.angle = 90
        pca.deinit()
        print("✓ Sistema finalizado")
    except:
        pass