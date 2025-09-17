#!/usr/bin/env python3
"""
test_brake.py - Teste Independente do Sistema de Freios
Testa o BrakeManager de forma isolada para verificar funcionamento
"""

import sys
import os
import time

# Adiciona o diretório raspberry ao path
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'raspberry'))

try:
    from brake_manager import BrakeManager
    print("✓ BrakeManager importado com sucesso")
except ImportError as e:
    print(f"❌ Erro ao importar BrakeManager: {e}")
    exit(1)

def test_brake_basic():
    """Teste básico do sistema de freios"""
    print("\n=== TESTE BÁSICO DOS FREIOS ===")

    # Cria instância do brake manager
    brake = BrakeManager(
        brake_balance=60.0,  # 60% frontal, 40% traseiro
        max_brake_force=90.0,
        response_time=0.1
    )

    print(f"Brake Manager criado:")
    print(f"  - Balanço de freio: {brake.brake_balance}%")
    print(f"  - Força máxima: {brake.max_brake_force}%")
    print(f"  - GPIO frontal: {brake.front_pin}")
    print(f"  - GPIO traseiro: {brake.rear_pin}")

    # Tenta inicializar
    print("\n--- Inicializando sistema de freios ---")
    if brake.initialize():
        print("✅ Sistema de freios inicializado com sucesso!")
        return brake
    else:
        print("❌ Falha ao inicializar sistema de freios")
        return None

def test_brake_application(brake):
    """Teste de aplicação de freios"""
    print("\n=== TESTE DE APLICAÇÃO DE FREIOS ===")

    # Sequência de testes
    test_sequence = [
        ("Sem freio", 0.0),
        ("Freio leve", 20.0),
        ("Freio médio", 50.0),
        ("Freio forte", 80.0),
        ("Freio máximo", 100.0),
        ("Freio moderado", 60.0),
        ("Liberação gradual", 30.0),
        ("Liberação total", 0.0)
    ]

    for description, brake_force in test_sequence:
        print(f"\n🛑 Testando {description}: {brake_force}%")

        # Aplica freio
        brake.apply_brake(brake_force)

        # Aguarda estabilizar
        time.sleep(1.0)

        # Mostra status
        status = brake.get_brake_status()
        front_percent = status.get("front_brake_percent", 0)
        rear_percent = status.get("rear_brake_percent", 0)
        total = status.get("total_brake_input", 0)

        print(f"   → Freio frontal: {front_percent:.1f}%")
        print(f"   → Freio traseiro: {rear_percent:.1f}%")
        print(f"   → Total aplicado: {total:.1f}%")

        # Pausa entre aplicações
        time.sleep(0.5)

def test_brake_balance(brake):
    """Teste de balanço de freios"""
    print("\n=== TESTE DE BALANÇO DE FREIOS ===")

    # Diferentes configurações de balanço
    balance_configs = [
        (50.0, "Equilibrado"),      # 50% frontal, 50% traseiro
        (70.0, "Mais frontal"),     # 70% frontal, 30% traseiro
        (30.0, "Mais traseiro"),    # 30% frontal, 70% traseiro
        (100.0, "Só frontal"),      # 100% frontal, 0% traseiro
        (0.0, "Só traseiro"),       # 0% frontal, 100% traseiro
        (60.0, "Padrão F1")         # 60% frontal, 40% traseiro
    ]

    # Força de teste constante
    test_force = 50.0

    for balance, description in balance_configs:
        print(f"\n⚖️ Testando {description}: {balance}% frontal")

        # Define novo balanço
        brake.set_brake_balance(balance)

        # Aplica força de teste
        brake.apply_brake(test_force)
        time.sleep(0.5)

        # Mostra distribuição
        status = brake.get_brake_status()
        front_percent = status.get("front_brake_percent", 0)
        rear_percent = status.get("rear_brake_percent", 0)

        print(f"   → Com {test_force}% de força:")
        print(f"   → Frontal: {front_percent:.1f}%")
        print(f"   → Traseiro: {rear_percent:.1f}%")

        # Libera freios
        brake.release_brakes()
        time.sleep(0.3)

def test_emergency_brake(brake):
    """Teste de freio de emergência"""
    print("\n=== TESTE DE FREIO DE EMERGÊNCIA ===")

    print("🚨 Ativando freio de emergência...")

    # Ativa freio de emergência
    brake.emergency_brake()
    time.sleep(1.0)

    # Verifica status
    status = brake.get_brake_status()
    front_percent = status.get("front_brake_percent", 0)
    rear_percent = status.get("rear_brake_percent", 0)

    print(f"   → Freio frontal emergência: {front_percent:.1f}%")
    print(f"   → Freio traseiro emergência: {rear_percent:.1f}%")

    # Aguarda e libera
    time.sleep(2.0)
    print("\n✅ Liberando freio de emergência...")
    brake.release_brakes()
    time.sleep(1.0)

def test_brake_limits(brake):
    """Teste dos limites do sistema"""
    print("\n=== TESTE DE LIMITES ===")

    # Testa valores extremos
    extreme_values = [-50.0, 0.0, 100.0, 150.0]

    for value in extreme_values:
        print(f"\n⚠️ Testando valor extremo: {value}%")
        brake.apply_brake(value)
        time.sleep(0.5)

        status = brake.get_brake_status()
        actual_input = status.get("total_brake_input", 0)
        front_percent = status.get("front_brake_percent", 0)
        rear_percent = status.get("rear_brake_percent", 0)

        print(f"   → Valor aplicado: {actual_input:.1f}%")
        print(f"   → Frontal: {front_percent:.1f}%")
        print(f"   → Traseiro: {rear_percent:.1f}%")

        # Libera freios
        brake.release_brakes()
        time.sleep(0.3)

def test_brake_statistics(brake):
    """Teste das estatísticas do sistema"""
    print("\n=== ESTATÍSTICAS DO SISTEMA ===")

    stats = brake.get_statistics()

    print("📊 Estatísticas:")
    print(f"   → Aplicações de freio: {stats.get('brake_applications', 0)}")
    print(f"   → Freios de emergência: {stats.get('emergency_brakes', 0)}")
    print(f"   → Tempo ativo: {stats.get('active_time', 0):.1f}s")
    print(f"   → Força máxima aplicada: {stats.get('max_force_applied', 0):.1f}%")
    print(f"   → Sistema inicializado: {stats.get('is_initialized', False)}")

    # Status atual
    status = brake.get_brake_status()
    print("\n📋 Status atual:")
    print(f"   → Balanço: {status.get('brake_balance', 0):.1f}%")
    print(f"   → Força total: {status.get('total_brake_input', 0):.1f}%")
    print(f"   → Frontal: {status.get('front_brake_percent', 0):.1f}%")
    print(f"   → Traseiro: {status.get('rear_brake_percent', 0):.1f}%")

def main():
    """Função principal do teste"""
    print("🛑 === TESTE DO BRAKE MANAGER ===")
    print("Este teste verifica o funcionamento do sistema de freios")
    print("Certifique-se de que os servos estão conectados:")
    print("  - Freio frontal: GPIO4 (Pin 7)")
    print("  - Freio traseiro: GPIO17 (Pin 11)")
    print()

    # Teste básico
    brake = test_brake_basic()
    if not brake:
        print("❌ Não foi possível inicializar - encerrando teste")
        return

    try:
        # Aguarda estabilização
        print("\n⏳ Aguardando estabilização do sistema...")
        time.sleep(2.0)

        # Testes funcionais
        test_brake_application(brake)
        test_brake_balance(brake)
        test_emergency_brake(brake)
        test_brake_limits(brake)
        test_brake_statistics(brake)

        print("\n✅ Teste concluído com sucesso!")

    except KeyboardInterrupt:
        print("\n⚠️ Teste interrompido pelo usuário")

    except Exception as e:
        print(f"\n❌ Erro durante teste: {e}")

    finally:
        # Cleanup
        print("\n🔧 Finalizando sistema...")
        try:
            brake.release_brakes()
            time.sleep(0.5)
            brake.cleanup()
            print("✓ Sistema finalizado corretamente")
        except:
            print("⚠️ Erro na finalização")

if __name__ == "__main__":
    main()