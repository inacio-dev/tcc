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

    # Sequência de testes de direção F1
    steering_sequence = [
        ("Centro", 90),
        ("Esquerda leve", 67),      # 90° - 23° = 67°
        ("Esquerda média", 45),     # 90° - 45° = 45°
        ("Esquerda máxima", 22),    # 90° - 68° = 22°
        ("Centro", 90),
        ("Direita leve", 113),      # 90° + 23° = 113°
        ("Direita média", 135),     # 90° + 45° = 135°
        ("Direita máxima", 158),    # 90° + 68° = 158°
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

        # Esquerda → Centro → Direita → Centro
        steering_servo.angle = 45   # Esquerda
        time.sleep(0.5)
        steering_servo.angle = 90   # Centro
        time.sleep(0.3)
        steering_servo.angle = 135  # Direita
        time.sleep(0.5)
        steering_servo.angle = 90   # Centro
        time.sleep(0.3)

    print("\n2. Varredura completa")
    # Varredura de 45° a 135° (range do steering)
    for angle in range(45, 136, 5):  # 45°, 50°, 55°... 135°
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