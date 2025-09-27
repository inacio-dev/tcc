#!/usr/bin/env python3
"""
test_brake.py - Teste Independente do Sistema de Freios
Testa o BrakeManager de forma isolada para verificar funcionamento
"""

import os
import sys
import time

# Adiciona o diretório raspberry ao path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "raspberry"))

try:
    from brake_manager import BrakeManager

    print("✓ BrakeManager importado com sucesso")
except ImportError as e:
    print(f"❌ Erro ao importar BrakeManager: {e}")
    exit(1)

try:
    import board
    import busio
    from adafruit_pca9685 import PCA9685

    print("✓ Bibliotecas PCA9685 importadas com sucesso")
    PCA9685_AVAILABLE = True
except ImportError as e:
    print(f"⚠️ PCA9685 não disponível: {e}")
    print("   Instale: sudo pip3 install adafruit-circuitpython-pca9685")
    PCA9685_AVAILABLE = False


def test_brake_basic():
    """Teste básico do sistema de freios"""
    print("\n=== TESTE BÁSICO DOS FREIOS ===")

    # Cria instância do brake manager
    brake = BrakeManager(
        brake_balance=60.0,  # 60% frontal, 40% traseiro
        max_brake_force=90.0,
        response_time=0.1,
    )

    # DESABILITAR MOVIMENTO SUAVE para teste
    brake.smooth_movement = False
    print("⚡ Movimento suave DESABILITADO para testes")

    print("Brake Manager criado:")
    print(f"  - Balanço de freio: {brake.brake_balance}%")
    print(f"  - Força máxima: {brake.max_brake_force}%")
    print(f"  - Canal frontal PCA9685: {brake.front_channel}")
    print(f"  - Canal traseiro PCA9685: {brake.rear_channel}")
    print(f"  - Endereço I2C: 0x{brake.pca9685_address:02X}")
    print(f"  - Movimento suave: {brake.smooth_movement}")

    # Tenta inicializar
    print("\n--- Inicializando sistema de freios ---")
    if brake.initialize():
        print("✅ Sistema de freios inicializado com sucesso!")
        return brake
    else:
        print("❌ Falha ao inicializar sistema de freios")
        return None


def test_brake_application(brake):
    """Teste de aplicação de freios com movimento direto"""
    print("\n=== TESTE DE APLICAÇÃO DE FREIOS (DIRETO) ===")

    # Sequência de testes mais agressiva
    test_sequence = [
        ("Sem freio", 0.0),
        ("Freio leve", 25.0),
        ("Freio médio", 50.0),
        ("Freio forte", 75.0),
        ("Freio máximo", 100.0),
        ("Freio moderado", 60.0),
        ("Liberação gradual", 30.0),
        ("Liberação total", 0.0),
    ]

    for description, brake_force in test_sequence:
        print(f"\n🛑 Testando {description}: {brake_force}%")

        # Aplica freio direto
        brake.apply_brake(brake_force)

        # Mostra status imediatamente (sem movimento suave)
        status = brake.get_brake_status()
        front_force = status.get("front_brake_force", 0)
        rear_force = status.get("rear_brake_force", 0)
        front_angle = status.get("front_brake_angle", 0)
        rear_angle = status.get("rear_brake_angle", 0)
        total = status.get("total_brake_input", 0)

        print(f"   → Input total: {total:.1f}%")
        print(f"   → Freio frontal: {front_force:.1f}% (ângulo: {front_angle:.1f}°)")
        print(f"   → Freio traseiro: {rear_force:.1f}% (ângulo: {rear_angle:.1f}°)")

        # Aguardar para ver movimento
        time.sleep(2.0)
        input("   Pressione ENTER para próximo teste...")


def test_brake_speed(brake):
    """Teste de velocidade e responsividade dos freios"""
    print("\n=== TESTE DE VELOCIDADE DOS FREIOS ===")

    print("\n1. Teste de responsividade (freadas rápidas)")

    # Sequência rápida para testar responsividade
    quick_sequence = [0, 50, 100, 25, 75, 0]

    for i, force in enumerate(quick_sequence):
        print(f"   Freada {i+1}: {force}%")
        start_time = time.time()
        brake.apply_brake(force)
        end_time = time.time()

        response_time = (end_time - start_time) * 1000  # em ms
        print(f"   → Tempo de resposta: {response_time:.1f}ms")

        time.sleep(0.5)  # Pausa curta entre freadas

    print("\n2. Teste de freada de emergência")
    print("   Simulando freadas de emergência rápidas...")

    for cycle in range(3):
        print(f"   Emergência {cycle+1}/3")

        # Sem freio → Freio máximo rapidamente
        start = time.time()
        brake.apply_brake(0)
        time.sleep(0.1)
        brake.apply_brake(100)  # Freada de emergência
        time.sleep(0.3)
        brake.apply_brake(0)    # Liberar
        end = time.time()

        cycle_time = (end - start) * 1000
        print(f"   → Tempo total: {cycle_time:.0f}ms")
        time.sleep(0.5)

    print("\n3. Teste de modulação (controle fino)")

    # Modulação fina para testar precisão
    modulation_sequence = [0, 10, 20, 30, 40, 50, 40, 30, 20, 10, 0]

    for force in modulation_sequence:
        print(f"   Modulação: {force}%")
        brake.apply_brake(force)

        status = brake.get_brake_status()
        actual_force = status.get("total_brake_input", 0)
        print(f"   → Força real: {actual_force:.1f}%")

        time.sleep(0.8)

    # Liberar completamente
    brake.release_brakes()
    print("   → Freios liberados")


def test_brake_balance(brake):
    """Teste de balanço de freios"""
    print("\n=== TESTE DE BALANÇO DE FREIOS ===")

    # Diferentes configurações de balanço
    balance_configs = [
        (50.0, "Equilibrado"),  # 50% frontal, 50% traseiro
        (70.0, "Mais frontal"),  # 70% frontal, 30% traseiro
        (30.0, "Mais traseiro"),  # 30% frontal, 70% traseiro
        (100.0, "Só frontal"),  # 100% frontal, 0% traseiro
        (0.0, "Só traseiro"),  # 0% frontal, 100% traseiro
        (60.0, "Padrão F1"),  # 60% frontal, 40% traseiro
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
    print("Certifique-se de que os servos estão conectados ao PCA9685:")
    print("  - Freio frontal: Canal 0 do PCA9685")
    print("  - Freio traseiro: Canal 1 do PCA9685")
    print("  - PCA9685 conectado via I2C (SDA=GPIO2, SCL=GPIO3)")
    if not PCA9685_AVAILABLE:
        print("⚠️ Aviso: PCA9685 não disponível - sistema funcionará em modo simulação")
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

        # Teste de velocidade
        print("\n" + "="*50)
        choice = input("🚀 Deseja executar teste de velocidade dos freios? (s/N): ").lower().strip()
        if choice in ['s', 'sim', 'y', 'yes']:
            test_brake_speed(brake)

        # Outros testes
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
