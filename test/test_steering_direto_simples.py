#!/usr/bin/env python3
"""
test_steering_direto_simples.py - Teste DIRETO do servo de direção
Range: 0° a 180° usando servo.angle normal
"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

print("🏎️ === TESTE DIRETO STEERING (0° a 180°) ===")
print("Range completo do MG996R com servo.angle")
print("Servo direção: Canal 2 do PCA9685")

try:
    # Inicializar PCA9685
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50
    print("✓ PCA9685 inicializado @ 50Hz")

    # Configurar servo - igual ao que funcionou
    steering_servo = servo.Servo(
        pca.channels[2],        # Canal 2 (direção)
        min_pulse=1000,         # 1ms
        max_pulse=2000,         # 2ms
    )
    print("✓ Servo direção configurado no canal 2")

    print("\n=== TESTE DE MOVIMENTOS DIRETOS ===")

    # Sequência F1 com range COMPLETO: 0° a 180°
    steering_sequence = [
        ("Centro", 90),             # Centro (meio do range)
        ("Esquerda leve", 70),      # 20° à esquerda do centro
        ("Esquerda média", 45),     # 45° à esquerda do centro
        ("Esquerda forte", 20),     # 70° à esquerda do centro
        ("Esquerda MÁXIMA", 0),     # EXTREMO ESQUERDA
        ("Centro", 90),
        ("Direita leve", 110),      # 20° à direita do centro
        ("Direita média", 135),     # 45° à direita do centro
        ("Direita forte", 160),     # 70° à direita do centro
        ("Direita MÁXIMA", 180),    # EXTREMO DIREITA
        ("Centro", 90),
    ]

    for description, angle in steering_sequence:
        print(f"\n🏎️ {description}: {angle}°")

        # COMANDO DIRETO - igual ao test_servo_direto.py
        steering_servo.angle = angle

        print(f"   → Ângulo: {angle}°")
        print(f"   → Aguardando movimento...")

        time.sleep(2)  # Tempo para ver movimento
        input("   Pressione ENTER para próximo movimento...")

    print("\n=== TESTE DE VELOCIDADE ===")

    # Teste de responsividade
    print("\n1. Oscilação rápida esquerda-direita EXTREMA")
    for cycle in range(3):
        print(f"   Ciclo {cycle+1}/3")

        # Esquerda MÁXIMA → Centro → Direita MÁXIMA → Centro
        angles = [0, 90, 180, 90]  # 0°→Centro→180°→Centro
        for angle in angles:
            steering_servo.angle = angle
            time.sleep(0.4)

    print("\n2. Varredura completa (0° a 180°)")
    # Varredura COMPLETA - todo o range possível do servo
    for angle in range(0, 181, 20):  # 0°, 20°, 40°... 180°
        print(f"   Ângulo: {angle}°")
        steering_servo.angle = angle
        time.sleep(0.3)

    # Retornar ao centro
    steering_servo.angle = 90  # Centro
    print("\n✓ Retornado ao centro (90°)")

    print("\n✅ Teste concluído!")
    print("\nSe o servo se moveu:")
    print("  ✓ Hardware está OK")
    print("  ✓ O problema está no steering_manager.py")
    print("\nSe o servo NÃO se moveu:")
    print("  ❌ Problema de hardware (alimentação, conexão)")

except KeyboardInterrupt:
    print("\n⚠️ Teste interrompido")
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        # Centralizar
        steering_servo.angle = 90  # Centro
        pca.deinit()
        print("✓ Sistema finalizado (posição central)")
    except:
        pass