#!/usr/bin/env python3
"""
test_brake_direto_simples.py - Teste DIRETO dos servos de freio
Range: 0° a 180° usando servo.angle normal
"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

print("🛑 === TESTE DIRETO FREIOS (0° a 180°) ===")
print("Range completo do MG996R com servo.angle")
print("Canal 4: Freio frontal | Canal 8: Freio traseiro")

try:
    # Inicializar PCA9685
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x41)
    pca.frequency = 50
    print("✓ PCA9685 inicializado @ 50Hz")

    # Configurar servos - igual ao que funcionou
    front_brake_servo = servo.Servo(
        pca.channels[4],        # Canal 4 (freio frontal)
        min_pulse=1000,         # 1ms
        max_pulse=2000,         # 2ms
    )
    rear_brake_servo = servo.Servo(
        pca.channels[8],        # Canal 8 (freio traseiro)
        min_pulse=1000,         # 1ms
        max_pulse=2000,         # 2ms
    )
    print("✓ Servos de freio configurados nos canais 4 e 8")

    print("\n=== TESTE DE FREIOS INDIVIDUAIS ===")

    # Teste freio frontal com range COMPLETO: 0° a 180°
    print("\n1. Testando FREIO FRONTAL (Canal 0)")
    brake_sequence = [
        ("Freio MÍNIMO", 0),            # Extremo mínimo
        ("Freio leve", 30),             # Freio suave
        ("Freio médio", 60),            # Freio moderado
        ("Centro", 90),                 # Centro
        ("Freio forte", 120),           # Freio intenso
        ("Freio forte+", 150),          # Freio muito intenso
        ("Freio MÁXIMO", 180),          # Extremo máximo
        ("Centro", 90),                 # Volta ao centro
    ]

    for description, angle in brake_sequence:
        print(f"   Freio frontal {description}: {angle}°")

        # COMANDO DIRETO - igual ao test_steering_direto_simples.py
        front_brake_servo.angle = angle

        print(f"     → Ângulo: {angle}°")
        time.sleep(1.5)
        input("     Pressione ENTER para próximo...")

    # Teste freio traseiro
    print("\n2. Testando FREIO TRASEIRO (Canal 1)")
    for description, angle in brake_sequence:
        print(f"   Freio traseiro {description}: {angle}°")

        # COMANDO DIRETO - igual ao test_steering_direto_simples.py
        rear_brake_servo.angle = angle

        print(f"     → Ângulo: {angle}°")
        time.sleep(1.5)
        input("     Pressione ENTER para próximo...")

    print("\n=== TESTE DE FREIOS COMBINADOS ===")

    # Teste com ambos os freios - range COMPLETO
    combined_tests = [
        ("Centro", 90, 90),             # Ambos no centro
        ("Freio leve F1", 120, 110),    # Mais dianteiro (estilo F1)
        ("Freio médio", 135, 120),      # Balanço 60/40
        ("Freio forte", 160, 140),      # Balanço agressivo
        ("Freio máximo", 180, 170),     # Máximo com balanço F1
        ("Emergência TOTAL", 180, 180), # Ambos no extremo
        ("Freio mínimo", 30, 30),       # Teste mínimo
        ("Centro", 90, 90),             # Volta ao centro
    ]

    for description, front_angle, rear_angle in combined_tests:
        print(f"\n🛑 {description}")
        print(f"   Frontal: {front_angle}° | Traseiro: {rear_angle}°")

        # Comandos DIRETOS - igual ao test_steering_direto_simples.py
        front_brake_servo.angle = front_angle
        rear_brake_servo.angle = rear_angle

        print(f"   → Ângulo frontal: {front_angle}° | Ângulo traseiro: {rear_angle}°")

        time.sleep(2)
        input("   Pressione ENTER para próximo...")

    print("\n=== TESTE DE VELOCIDADE ===")

    # Teste de freada de emergência com range COMPLETO
    print("\n1. Freada de emergência EXTREMA")
    for cycle in range(3):
        print(f"   Emergência {cycle+1}/3")

        # Centro → Freio MÁXIMO → Centro
        angles_emergency = [90, 180, 90]  # Centro → Máximo → Centro

        for angle in angles_emergency:
            front_brake_servo.angle = angle
            rear_brake_servo.angle = angle
            time.sleep(0.6)

    print("\n2. Modulação gradual COMPLETA (0° a 180°)")
    # Varredura completa do range
    for angle in range(0, 181, 30):  # 0°, 30°, 60°... 180°
        print(f"   Freio: {angle}°")

        front_brake_servo.angle = angle
        rear_brake_servo.angle = max(0, angle - 20)  # Traseiro com offset mínimo

        time.sleep(0.5)

    # Posição neutra final
    front_brake_servo.angle = 90  # Centro
    rear_brake_servo.angle = 90   # Centro
    print("\n✓ Freios liberados (posição neutra: 90°)")

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
        # Liberar freios (posição neutra)
        front_brake_servo.angle = 90  # Centro
        rear_brake_servo.angle = 90   # Centro
        pca.deinit()
        print("✓ Sistema finalizado (freios na posição neutra)")
    except Exception:
        pass