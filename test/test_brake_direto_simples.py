#!/usr/bin/env python3
"""
test_brake_direto_simples.py - Teste DIRETO dos servos de freio
Range completo: -180° a +180° usando duty cycle direto
"""

import time
import board
import busio
from adafruit_pca9685 import PCA9685

print("🛑 === TESTE DIRETO FREIOS (-180° a +180°) ===")
print("Controle direto por duty cycle para range completo")
print("Canal 0: Freio frontal | Canal 1: Freio traseiro")

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

    # Usar canais diretos (sem biblioteca servo)
    front_brake_channel = pca.channels[0]  # Canal 0 (freio frontal)
    rear_brake_channel = pca.channels[1]   # Canal 1 (freio traseiro)
    print("✓ Canais 0 e 1 configurados para controle direto")

    print("\n=== TESTE DE FREIOS INDIVIDUAIS ===")

    # Teste freio frontal com range COMPLETO: -180° a +180°
    print("\n1. Testando FREIO FRONTAL (Canal 0)")
    brake_sequence = [
        ("Anti-freio MÁXIMO", -180),    # Extremo oposto
        ("Anti-freio médio", -90),      # Pode ser posição de ajuda
        ("Neutro", 0),                  # Centro absoluto
        ("Freio leve", 45),             # Freio suave
        ("Freio médio", 90),            # Freio moderado
        ("Freio forte", 135),           # Freio intenso
        ("Freio MÁXIMO", 180),          # Extremo máximo
        ("Neutro", 0),                  # Volta ao centro
    ]

    for description, angle in brake_sequence:
        print(f"   Freio frontal {description}: {angle}°")
        duty = angle_to_duty_cycle(angle)
        front_brake_channel.duty_cycle = duty
        print(f"     → Duty cycle: {duty}")
        time.sleep(1.5)
        input("     Pressione ENTER para próximo...")

    # Teste freio traseiro
    print("\n2. Testando FREIO TRASEIRO (Canal 1)")
    for description, angle in brake_sequence:
        print(f"   Freio traseiro {description}: {angle}°")
        duty = angle_to_duty_cycle(angle)
        rear_brake_channel.duty_cycle = duty
        print(f"     → Duty cycle: {duty}")
        time.sleep(1.5)
        input("     Pressione ENTER para próximo...")

    print("\n=== TESTE DE FREIOS COMBINADOS ===")

    # Teste com ambos os freios - range COMPLETO
    combined_tests = [
        ("Neutro", 0, 0),               # Ambos no centro
        ("Freio leve F1", 30, 20),      # Mais dianteiro (estilo F1)
        ("Freio médio", 60, 45),        # Balanço 60/40
        ("Freio forte", 120, 90),       # Balanço agressivo
        ("Freio máximo", 180, 150),     # Máximo com balanço F1
        ("Emergência TOTAL", 180, 180), # Ambos no extremo
        ("Anti-freio teste", -90, -90), # Teste direção oposta
        ("Neutro", 0, 0),               # Volta ao centro
    ]

    for description, front_angle, rear_angle in combined_tests:
        print(f"\n🛑 {description}")
        print(f"   Frontal: {front_angle}° | Traseiro: {rear_angle}°")

        # Comandos DIRETOS por duty cycle
        front_duty = angle_to_duty_cycle(front_angle)
        rear_duty = angle_to_duty_cycle(rear_angle)

        front_brake_channel.duty_cycle = front_duty
        rear_brake_channel.duty_cycle = rear_duty

        print(f"   → Duty frontal: {front_duty} | Duty traseiro: {rear_duty}")

        time.sleep(2)
        input("   Pressione ENTER para próximo...")

    print("\n=== TESTE DE VELOCIDADE ===")

    # Teste de freada de emergência com range COMPLETO
    print("\n1. Freada de emergência EXTREMA")
    for cycle in range(3):
        print(f"   Emergência {cycle+1}/3")

        # Neutro → Freio MÁXIMO → Neutro
        angles_emergency = [0, 180, 0]  # Centro → Máximo → Centro

        for angle in angles_emergency:
            front_duty = angle_to_duty_cycle(angle)
            rear_duty = angle_to_duty_cycle(angle)

            front_brake_channel.duty_cycle = front_duty
            rear_brake_channel.duty_cycle = rear_duty
            time.sleep(0.6)

    print("\n2. Modulação gradual COMPLETA (-180° a +180°)")
    # Varredura completa do range
    for angle in range(-180, 181, 30):  # -180°, -150°, ... +180°
        print(f"   Freio: {angle}°")

        front_duty = angle_to_duty_cycle(angle)
        rear_duty = angle_to_duty_cycle(max(-180, angle - 30))  # Traseiro offset

        front_brake_channel.duty_cycle = front_duty
        rear_brake_channel.duty_cycle = rear_duty
        time.sleep(0.5)

    # Posição neutra final
    center_duty = angle_to_duty_cycle(0)
    front_brake_channel.duty_cycle = center_duty
    rear_brake_channel.duty_cycle = center_duty
    print("\n✓ Freios liberados (posição neutra: 0°)")

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
        center_duty = angle_to_duty_cycle(0)
        front_brake_channel.duty_cycle = center_duty
        rear_brake_channel.duty_cycle = center_duty
        pca.deinit()
        print("✓ Sistema finalizado (freios na posição neutra)")
    except:
        pass