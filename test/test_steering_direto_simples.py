#!/usr/bin/env python3
"""
test_steering_direto_simples.py - Teste DIRETO do servo de direção
Usa exatamente o mesmo approach do test_servo_direto.py que funcionou
"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

print("🏎️ === TESTE DIRETO STEERING (SIMPLES) ===")
print("Usa o mesmo código que funcionou no test_servo_direto.py")
print("Servo direção: Canal 2 do PCA9685")

try:
    # Inicializar PCA9685 - EXATAMENTE como no test_servo_direto.py
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50
    print("✓ PCA9685 inicializado @ 50Hz")

    # Configurar servo - EXATAMENTE como no test_servo_direto.py
    steering_servo = servo.Servo(
        pca.channels[2],        # Canal 2 (direção)
        min_pulse=1000,         # 1ms
        max_pulse=2000,         # 2ms
    )
    print("✓ Servo direção configurado no canal 2")

    print("\n=== TESTE DE MOVIMENTOS DIRETOS ===")

    # Sequência de testes de direção F1 - RANGE COMPLETO
    steering_sequence = [
        ("Centro", 90),
        ("Esquerda leve", 70),      # 90° - 20° = 70°
        ("Esquerda média", 45),     # 90° - 45° = 45°
        ("Esquerda forte", 20),     # 90° - 70° = 20°
        ("Esquerda MÁXIMA", 0),     # EXTREMO ESQUERDA
        ("Centro", 90),
        ("Direita leve", 110),      # 90° + 20° = 110°
        ("Direita média", 135),     # 90° + 45° = 135°
        ("Direita forte", 160),     # 90° + 70° = 160°
        ("Direita MÁXIMA", 180),    # EXTREMO DIREITA
        ("Centro", 90),
    ]

    for description, angle in steering_sequence:
        print(f"\n🏎️ {description}: {angle}°")

        # COMANDO DIRETO - igual ao test_servo_direto.py
        steering_servo.angle = angle

        print(f"   → Comando enviado: {angle}°")
        print(f"   → Aguardando movimento...")

        time.sleep(2)  # Tempo para ver movimento
        input("   Pressione ENTER para próximo movimento...")

    print("\n=== TESTE DE VELOCIDADE ===")

    # Teste de responsividade
    print("\n1. Oscilação rápida esquerda-direita")
    for cycle in range(3):
        print(f"   Ciclo {cycle+1}/3")

        # Esquerda MÁXIMA → Centro → Direita MÁXIMA → Centro
        steering_servo.angle = 0    # EXTREMO ESQUERDA
        time.sleep(0.5)
        steering_servo.angle = 90   # Centro
        time.sleep(0.3)
        steering_servo.angle = 180  # EXTREMO DIREITA
        time.sleep(0.5)
        steering_servo.angle = 90   # Centro
        time.sleep(0.3)

    print("\n2. Varredura completa (0° a 180°)")
    # Varredura COMPLETA - aproveitando todo o range do servo
    for angle in range(0, 181, 10):  # 0°, 10°, 20°... 180°
        print(f"   Ângulo: {angle}°")
        steering_servo.angle = angle
        time.sleep(0.2)

    # Retornar ao centro
    steering_servo.angle = 90
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
        steering_servo.angle = 90  # Centro
        pca.deinit()
        print("✓ Sistema finalizado")
    except:
        pass