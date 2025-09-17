#!/usr/bin/env python3
"""
test_steering_brake.py - Teste Combinado de Direção e Freios
Testa ambos os sistemas em conjunto para simular uso real
"""

import sys
import os
import time

# Adiciona o diretório raspberry ao path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'raspberry'))

try:
    from steering_manager import SteeringManager, SteeringMode
    from brake_manager import BrakeManager
    print("✓ Managers importados com sucesso")
except ImportError as e:
    print(f"❌ Erro ao importar managers: {e}")
    exit(1)

def initialize_systems():
    """Inicializa ambos os sistemas"""
    print("\n=== INICIALIZANDO SISTEMAS ===")

    # Steering Manager
    print("🏎️ Inicializando sistema de direção...")
    steering = SteeringManager(
        steering_sensitivity=1.0,
        max_steering_angle=45.0,
        steering_mode=SteeringMode.SPORT,
        response_time=0.1
    )

    if not steering.initialize():
        print("❌ Falha ao inicializar direção")
        return None, None

    print("✅ Direção inicializada")

    # Brake Manager
    print("🛑 Inicializando sistema de freios...")
    brake = BrakeManager(
        brake_balance=60.0,
        max_brake_force=90.0,
        response_time=0.1
    )

    if not brake.initialize():
        print("❌ Falha ao inicializar freios")
        steering.cleanup()
        return None, None

    print("✅ Freios inicializados")
    print("✅ Ambos os sistemas prontos!")

    return steering, brake

def test_combined_movements(steering, brake):
    """Teste de movimentos combinados"""
    print("\n=== TESTE DE MOVIMENTOS COMBINADOS ===")

    # Sequências realistas de direção + freio
    sequences = [
        {
            "name": "Curva à esquerda suave",
            "actions": [
                ("steering", -30.0),
                ("brake", 20.0),
                ("wait", 1.0),
                ("brake", 0.0),
                ("steering", 0.0)
            ]
        },
        {
            "name": "Curva à direita acentuada",
            "actions": [
                ("steering", 60.0),
                ("brake", 40.0),
                ("wait", 1.5),
                ("brake", 10.0),
                ("steering", 20.0),
                ("wait", 0.5),
                ("brake", 0.0),
                ("steering", 0.0)
            ]
        },
        {
            "name": "Freada de emergência com correção",
            "actions": [
                ("brake", 100.0),
                ("steering", -20.0),
                ("wait", 1.0),
                ("brake", 50.0),
                ("steering", 0.0),
                ("wait", 0.5),
                ("brake", 0.0)
            ]
        },
        {
            "name": "Slalom (zigue-zague)",
            "actions": [
                ("steering", -50.0),
                ("wait", 0.5),
                ("steering", 50.0),
                ("wait", 0.5),
                ("steering", -40.0),
                ("wait", 0.5),
                ("steering", 40.0),
                ("wait", 0.5),
                ("steering", 0.0)
            ]
        }
    ]

    for sequence in sequences:
        print(f"\n🎯 Executando: {sequence['name']}")

        for action, value in sequence["actions"]:
            if action == "steering":
                print(f"   🏎️ Direção: {value}%")
                steering.set_steering_input(value)
            elif action == "brake":
                print(f"   🛑 Freio: {value}%")
                brake.apply_brake(value)
            elif action == "wait":
                print(f"   ⏳ Aguardando {value}s...")
                time.sleep(value)

            # Pequena pausa entre ações
            if action != "wait":
                time.sleep(0.3)

        # Pausa entre sequências
        print("   ✅ Sequência concluída")
        time.sleep(1.0)

def test_emergency_scenarios(steering, brake):
    """Teste de cenários de emergência"""
    print("\n=== TESTE DE CENÁRIOS DE EMERGÊNCIA ===")

    scenarios = [
        {
            "name": "Obstáculo à frente",
            "description": "Freada brusca com correção de direção",
            "actions": [
                ("brake", 100.0),
                ("steering", -30.0),
                ("wait", 1.0),
                ("brake", 0.0),
                ("steering", 0.0)
            ]
        },
        {
            "name": "Derrapagem simulada",
            "description": "Correção rápida com contra-esterço",
            "actions": [
                ("steering", -80.0),
                ("brake", 30.0),
                ("wait", 0.3),
                ("steering", 40.0),
                ("wait", 0.3),
                ("steering", -20.0),
                ("wait", 0.3),
                ("steering", 0.0),
                ("brake", 0.0)
            ]
        }
    ]

    for scenario in scenarios:
        print(f"\n🚨 Cenário: {scenario['name']}")
        print(f"   📝 {scenario['description']}")

        for action, value in scenario["actions"]:
            if action == "steering":
                print(f"   🏎️ Direção: {value}%")
                steering.set_steering_input(value)
            elif action == "brake":
                print(f"   🛑 Freio: {value}%")
                brake.apply_brake(value)
            elif action == "wait":
                time.sleep(value)

            if action != "wait":
                time.sleep(0.2)

        print("   ✅ Cenário concluído")
        time.sleep(1.5)

def test_progressive_control(steering, brake):
    """Teste de controle progressivo"""
    print("\n=== TESTE DE CONTROLE PROGRESSIVO ===")

    print("🔄 Teste de aplicação progressiva...")

    # Direção progressiva
    print("\n🏎️ Direção progressiva (0 → 100% → 0):")
    for i in range(0, 101, 10):
        steering.set_steering_input(i)
        print(f"   Direção: {i}%")
        time.sleep(0.2)

    for i in range(100, -1, -10):
        steering.set_steering_input(i)
        print(f"   Direção: {i}%")
        time.sleep(0.2)

    # Freio progressivo
    print("\n🛑 Freio progressivo (0 → 100% → 0):")
    for i in range(0, 101, 10):
        brake.apply_brake(i)
        print(f"   Freio: {i}%")
        time.sleep(0.2)

    for i in range(100, -1, -10):
        brake.apply_brake(i)
        print(f"   Freio: {i}%")
        time.sleep(0.2)

    print("✅ Controle progressivo concluído")

def display_system_status(steering, brake):
    """Mostra status detalhado dos sistemas"""
    print("\n=== STATUS ATUAL DOS SISTEMAS ===")

    # Status da direção
    steering_status = steering.get_steering_status()
    print("🏎️ Sistema de Direção:")
    print(f"   → Entrada atual: {steering_status.get('steering_input', 0):.1f}%")
    print(f"   → Ângulo servo: {steering_status.get('current_servo_angle', 0):.1f}°")
    print(f"   → Modo: {steering_status.get('steering_mode', 'N/A')}")
    print(f"   → Inicializado: {steering_status.get('is_initialized', False)}")

    # Status dos freios
    brake_status = brake.get_brake_status()
    print("\n🛑 Sistema de Freios:")
    print(f"   → Força total: {brake_status.get('total_brake_input', 0):.1f}%")
    print(f"   → Freio frontal: {brake_status.get('front_brake_percent', 0):.1f}%")
    print(f"   → Freio traseiro: {brake_status.get('rear_brake_percent', 0):.1f}%")
    print(f"   → Balanço: {brake_status.get('brake_balance', 0):.1f}%")
    print(f"   → Inicializado: {brake_status.get('is_initialized', False)}")

def main():
    """Função principal do teste combinado"""
    print("🏁 === TESTE COMBINADO: DIREÇÃO + FREIOS ===")
    print("Este teste simula cenários reais de uso dos sistemas")
    print("Certifique-se de que todos os servos estão conectados:")
    print("  - Direção: GPIO24 (Pin 18)")
    print("  - Freio frontal: GPIO4 (Pin 7)")
    print("  - Freio traseiro: GPIO17 (Pin 11)")
    print()

    # Inicialização
    steering, brake = initialize_systems()
    if not steering or not brake:
        print("❌ Falha na inicialização - encerrando teste")
        return

    try:
        # Aguarda estabilização
        print("\n⏳ Aguardando estabilização dos sistemas...")
        time.sleep(3.0)

        # Mostra status inicial
        display_system_status(steering, brake)

        # Executa testes
        test_combined_movements(steering, brake)
        test_emergency_scenarios(steering, brake)
        test_progressive_control(steering, brake)

        # Status final
        display_system_status(steering, brake)

        print("\n🏁 Teste combinado concluído com sucesso!")

    except KeyboardInterrupt:
        print("\n⚠️ Teste interrompido pelo usuário")

    except Exception as e:
        print(f"\n❌ Erro durante teste: {e}")
        import traceback
        traceback.print_exc()

    finally:
        # Cleanup completo
        print("\n🔧 Finalizando sistemas...")
        try:
            # Para e centraliza direção
            steering.center_steering()
            time.sleep(0.5)

            # Libera freios
            brake.release_brakes()
            time.sleep(0.5)

            # Cleanup final
            steering.cleanup()
            brake.cleanup()

            print("✓ Sistemas finalizados corretamente")
        except Exception as e:
            print(f"⚠️ Erro na finalização: {e}")

if __name__ == "__main__":
    main()