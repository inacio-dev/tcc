#!/usr/bin/env python3
"""
test_direção_360.py - Teste Direção com Rotação Completa
Testa direção com range de 360° para máxima agilidade
"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685
from adafruit_motor import servo

print("🏎️ === DIREÇÃO 360° F1 ===")
print("Teste de direção com rotação completa para máxima agilidade")

try:
    # Inicializar PCA9685
    i2c = busio.I2C(board.SCL, board.SDA)
    pca = PCA9685(i2c, address=0x40)
    pca.frequency = 50
    print("✓ PCA9685 inicializado @ 50Hz")

    # Configurar servo direção com range máximo
    steering_servo = servo.Servo(
        pca.channels[2],        # Canal 2 (direção)
        min_pulse=500,          # 0.5ms (mais amplo)
        max_pulse=2500,         # 2.5ms (mais amplo)
    )
    print("✓ Servo direção configurado no canal 2 (range ampliado)")

    print("\n=== DIREÇÃO F1 COM 360° ===")

    # Sequência F1 com rotação completa
    f1_sequence = [
        ("Centro", 180),                    # Centro (meio da rotação)
        ("Esquerda suave", 150),            # -30°
        ("Esquerda média", 120),            # -60°
        ("Esquerda forte", 90),             # -90°
        ("Esquerda EXTREMA", 45),           # -135°
        ("Esquerda MÁXIMA", 0),             # -180° (meia volta)
        ("Centro", 180),
        ("Direita suave", 210),             # +30°
        ("Direita média", 240),             # +60°
        ("Direita forte", 270),             # +90°
        ("Direita EXTREMA", 315),           # +135°
        ("Direita MÁXIMA", 360),            # +180° (meia volta oposta)
        ("Centro", 180),
    ]

    for description, angle in f1_sequence:
        print(f"\n🏎️ {description}: {angle}°")

        try:
            steering_servo.angle = angle
            print(f"   ✓ Comando enviado: {angle}°")

            # Calcular esterçamento relativo ao centro
            relative = angle - 180
            print(f"   → Esterçamento: {relative:+d}° do centro")

        except Exception as e:
            print(f"   ❌ Erro: {e}")
            # Tentar com duty cycle direto
            try:
                # Converter ângulo para duty cycle aproximado
                duty = int((angle / 360.0) * 1000) + 102  # Aproximação
                pca.channels[2].duty_cycle = duty
                print(f"   → Duty cycle alternativo: {duty}")
            except:
                print(f"   → Falha completa em {angle}°")

        time.sleep(2)
        input("   Pressione ENTER para próximo movimento...")

    print("\n=== CURVAS RÁPIDAS F1 ===")

    # Simulação de curvas fechadas F1
    print("\n1. Curva chicane (esquerda-direita-esquerda)")

    chicane_moves = [180, 90, 270, 45, 315, 180]  # Centro→Esq→Dir→ExtrEsq→ExtrDir→Centro

    for i, angle in enumerate(chicane_moves):
        print(f"   Movimento {i+1}: {angle}°")
        try:
            steering_servo.angle = angle
            time.sleep(0.8)  # Movimento rápido
        except:
            duty = int((angle / 360.0) * 1000) + 102
            pca.channels[2].duty_cycle = duty
            time.sleep(0.8)

    print("\n2. Rotação contínua (simulação derrapagem)")

    # Rotação contínua para simular derrapagem/manobra
    print("   Rotação completa horária...")
    for angle in range(0, 361, 20):  # 0°, 20°, 40°... 360°
        try:
            steering_servo.angle = angle
            print(f"     {angle}°")
            time.sleep(0.3)
        except:
            duty = int((angle / 360.0) * 1000) + 102
            pca.channels[2].duty_cycle = duty
            time.sleep(0.3)

    print("   Rotação completa anti-horária...")
    for angle in range(360, -1, -20):  # 360°, 340°, 320°... 0°
        try:
            steering_servo.angle = angle
            print(f"     {angle}°")
            time.sleep(0.3)
        except:
            duty = int((angle / 360.0) * 1000) + 102
            pca.channels[2].duty_cycle = duty
            time.sleep(0.3)

    # Voltar ao centro
    try:
        steering_servo.angle = 180
    except:
        pca.channels[2].duty_cycle = 307  # 1.5ms

    print("\n✅ TESTE 360° CONCLUÍDO!")
    print("\nSe funcionou:")
    print("  🏎️ Direção F1 COMPLETA ativada!")
    print("  🌀 Curvas de até ±180° possíveis!")
    print("  ⚡ Manobras extremas habilitadas!")
    print("\nSe não funcionou:")
    print("  📝 Servo limitado a 180° (ainda muito bom)")

except KeyboardInterrupt:
    print("\n⚠️ Teste interrompido")
except Exception as e:
    print(f"❌ Erro: {e}")
    import traceback
    traceback.print_exc()
finally:
    try:
        # Centralizar
        steering_servo.angle = 180  # Centro em 360°
        pca.deinit()
        print("✓ Sistema finalizado (posição central)")
    except:
        pass