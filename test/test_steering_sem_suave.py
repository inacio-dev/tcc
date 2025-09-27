#!/usr/bin/env python3
"""
test_steering_sem_suave.py - Teste do Steering sem movimento suave
"""

import os
import sys
import time

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "raspberry"))

from steering_manager import SteeringManager, SteeringMode

print("🏎️ === TESTE STEERING SEM MOVIMENTO SUAVE ===")

def test_steering_direct():
    """Teste com movimento direto (sem suavização)"""

    # Criar steering manager SEM movimento suave
    steering = SteeringManager(
        steering_sensitivity=1.0,
        max_steering_angle=45.0,
        steering_mode=SteeringMode.NORMAL,
    )

    # Desabilitar movimento suave
    steering.smooth_movement = False

    print("Steering Manager criado (movimento suave DESABILITADO):")
    print(f"  - Canal PCA9685: {steering.steering_channel}")
    print(f"  - Movimento suave: {steering.smooth_movement}")

    # Inicializar
    if not steering.initialize():
        print("❌ Falha ao inicializar")
        return

    print("\n=== TESTE DE MOVIMENTOS DIRETOS ===")

    # Movimentos mais agressivos
    test_movements = [
        ("Centro", 0),
        ("Esquerda máxima", -100),
        ("Centro", 0),
        ("Direita máxima", 100),
        ("Centro", 0),
        ("Esquerda média", -50),
        ("Direita média", 50),
        ("Centro", 0)
    ]

    for description, steering_input in test_movements:
        print(f"\n🎯 {description}: {steering_input}%")
        steering.set_steering(steering_input)

        # Mostrar estado
        status = steering.get_steering_status()
        print(f"   Ângulo atual: {status['current_angle']:+6.1f}°")
        print(f"   Ângulo servo: {status['servo_angle']:5.1f}°")

        time.sleep(2)  # Aguardar movimento
        input("   Pressione ENTER para continuar...")

    # Finalizar
    steering.cleanup()
    print("✅ Teste concluído")

if __name__ == "__main__":
    try:
        test_steering_direct()
    except KeyboardInterrupt:
        print("\n⚠️ Teste interrompido")
    except Exception as e:
        print(f"❌ Erro: {e}")
        import traceback
        traceback.print_exc()