#!/usr/bin/env python3
"""
test_steering_direto_simples.py - Teste DIRETO do servo de direção
Range completo: -180° a +180° usando duty cycle direto
"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685

print("🏎️ === TESTE DIRETO STEERING (-180° a +180°) ===")
print("Controle direto por duty cycle para range completo")
print("Servo direção: Canal 2 do PCA9685")

def angle_to_duty_cycle(angle):
    """Converte ângulo (-180 a +180) para duty cycle do PCA9685"""
    # Normalizar -180/+180 para 0-360
    normalized = angle + 180  # -180 vira 0, +180 vira 360

    # Mapear 0-360 para duty cycle (102 a 512 aproximadamente)
    # 102 = 0.5ms, 512 = 2.5ms (range ampliado)
    min_duty = 102   # 0.5ms
    max_duty = 512   # 2.5ms

    duty = int(min_duty + (normalized / 360.0) * (max_duty - min_duty))
    return duty

try:
    # Inicializar PCA9685
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50
    print("✓ PCA9685 inicializado @ 50Hz")

    # Usar canal direto (sem biblioteca servo)
    steering_channel = pca.channels[2]
    print("✓ Canal 2 configurado para controle direto")

    print("\n=== TESTE DE MOVIMENTOS DIRETOS ===")

    # Sequência F1 com range COMPLETO: -180° a +180°
    steering_sequence = [
        ("Centro", 0),              # Centro absoluto
        ("Esquerda leve", -30),     # 30° à esquerda
        ("Esquerda média", -60),    # 60° à esquerda
        ("Esquerda forte", -90),    # 90° à esquerda
        ("Esquerda EXTREMA", -135), # 135° à esquerda
        ("Esquerda MÁXIMA", -180),  # 180° à esquerda (EXTREMO)
        ("Centro", 0),
        ("Direita leve", 30),       # 30° à direita
        ("Direita média", 60),      # 60° à direita
        ("Direita forte", 90),      # 90° à direita
        ("Direita EXTREMA", 135),   # 135° à direita
        ("Direita MÁXIMA", 180),    # 180° à direita (EXTREMO)
        ("Centro", 0),
    ]

    for description, angle in steering_sequence:
        print(f"\n🏎️ {description}: {angle}°")

        # COMANDO DIRETO por duty cycle
        duty = angle_to_duty_cycle(angle)
        steering_channel.duty_cycle = duty

        print(f"   → Ângulo: {angle}°")
        print(f"   → Duty cycle: {duty}")
        print(f"   → Aguardando movimento...")

        time.sleep(2)  # Tempo para ver movimento
        input("   Pressione ENTER para próximo movimento...")

    print("\n=== TESTE DE VELOCIDADE ===")

    # Teste de responsividade
    print("\n1. Oscilação rápida esquerda-direita EXTREMA")
    for cycle in range(3):
        print(f"   Ciclo {cycle+1}/3")

        # Esquerda MÁXIMA → Centro → Direita MÁXIMA → Centro
        angles = [-180, 0, 180, 0]
        for angle in angles:
            duty = angle_to_duty_cycle(angle)
            steering_channel.duty_cycle = duty
            time.sleep(0.4)

    print("\n2. Varredura completa (-180° a +180°)")
    # Varredura COMPLETA - todo o range possível
    for angle in range(-180, 181, 20):  # -180°, -160°, -140°... +180°
        print(f"   Ângulo: {angle}°")
        duty = angle_to_duty_cycle(angle)
        steering_channel.duty_cycle = duty
        time.sleep(0.3)

    # Retornar ao centro
    duty_center = angle_to_duty_cycle(0)
    steering_channel.duty_cycle = duty_center
    print("\n✓ Retornado ao centro (0°)")

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
        duty_center = angle_to_duty_cycle(0)
        steering_channel.duty_cycle = duty_center
        pca.deinit()
        print("✓ Sistema finalizado (posição central)")
    except:
        pass