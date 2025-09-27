#!/usr/bin/env python3
"""
test_steering.py - Teste Independente do Sistema de Direção
Testa o SteeringManager de forma isolada para verificar funcionamento
"""

import os
import sys
import time

# Adiciona o diretório raspberry ao path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "raspberry"))

try:
    from steering_manager import SteeringManager, SteeringMode

    print("✓ SteeringManager importado com sucesso")
except ImportError as e:
    print(f"❌ Erro ao importar SteeringManager: {e}")
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


def test_steering_basic():
    """Teste básico do sistema de direção"""
    print("\n=== TESTE BÁSICO DA DIREÇÃO ===")

    # Cria instância do steering manager COM MOVIMENTO DIRETO
    steering = SteeringManager(
        steering_sensitivity=1.0,
        max_steering_angle=45.0,
        steering_mode=SteeringMode.NORMAL,
        response_time=0.1,
    )

    # DESABILITAR MOVIMENTO SUAVE para teste
    steering.smooth_movement = False
    print("⚡ Movimento suave DESABILITADO para testes")

    print("Steering Manager criado:")
    print(f"  - Sensibilidade: {steering.steering_sensitivity}")
    print(f"  - Ângulo máximo: {steering.max_steering_angle}°")
    print(f"  - Modo: {steering.steering_mode.value}")
    print(f"  - Canal PCA9685: {steering.steering_channel}")
    print(f"  - Endereço I2C: 0x{steering.pca9685_address:02X}")
    print(f"  - Movimento suave: {steering.smooth_movement}")

    # Tenta inicializar
    print("\n--- Inicializando sistema de direção ---")
    if steering.initialize():
        print("✅ Sistema de direção inicializado com sucesso!")
        return steering
    else:
        print("❌ Falha ao inicializar sistema de direção")
        return None


def test_steering_movements(steering):
    """Teste de movimentos da direção com movimento direto"""
    print("\n=== TESTE DE MOVIMENTOS DIRETOS ===")

    # Sequência de testes mais agressiva
    test_sequence = [
        ("Centro", 0.0),
        ("Esquerda leve", -25.0),
        ("Esquerda média", -50.0),
        ("Esquerda forte", -75.0),
        ("Esquerda máxima", -100.0),
        ("Centro", 0.0),
        ("Direita leve", 25.0),
        ("Direita média", 50.0),
        ("Direita forte", 75.0),
        ("Direita máxima", 100.0),
        ("Centro", 0.0),
    ]

    for description, steering_input in test_sequence:
        print(f"\n🏎️ Testando {description}: {steering_input}%")

        # Aplica comando direto
        steering.set_steering_input(steering_input)

        # Mostrar status imediatamente (sem movimento suave)
        status = steering.get_steering_status()
        current_angle = status.get("current_angle", 0)
        servo_angle = status.get("servo_angle", 0)
        steering_input_actual = status.get("steering_input", 0)

        print(f"   → Input: {steering_input_actual:.1f}%")
        print(f"   → Ângulo direção: {current_angle:+6.1f}°")
        print(f"   → Ângulo servo: {servo_angle:5.1f}°")

        # Aguardar para ver movimento
        time.sleep(2.0)
        input("   Pressione ENTER para próximo movimento...")


def test_steering_speed(steering):
    """Teste de velocidade e responsividade da direção"""
    print("\n=== TESTE DE VELOCIDADE ===")

    print("\n1. Teste de responsividade (movimentos rápidos)")

    # Sequência rápida para testar responsividade
    quick_sequence = [0, -100, 100, -50, 50, 0]

    for i, angle in enumerate(quick_sequence):
        print(f"   Movimento {i+1}: {angle}%")
        start_time = time.time()
        steering.set_steering_input(angle)
        end_time = time.time()

        response_time = (end_time - start_time) * 1000  # em ms
        print(f"   → Tempo de resposta: {response_time:.1f}ms")

        time.sleep(0.3)  # Pausa curta entre movimentos

    print("\n2. Teste de oscilação rápida")
    print("   Oscilando entre -100% e +100% rapidamente...")

    for cycle in range(5):
        print(f"   Ciclo {cycle+1}/5")

        # Esquerda máxima
        start = time.time()
        steering.set_steering_input(-100)
        time.sleep(0.2)

        # Direita máxima
        steering.set_steering_input(100)
        time.sleep(0.2)

        end = time.time()
        cycle_time = (end - start) * 1000
        print(f"   → Tempo do ciclo: {cycle_time:.0f}ms")

    # Voltar ao centro
    steering.set_steering_input(0)
    print("   → Retornado ao centro")

    print("\n3. Teste de precisão (movimentos pequenos)")

    # Movimentos pequenos para testar precisão
    precision_sequence = [0, 5, 10, 15, 20, 15, 10, 5, 0, -5, -10, -15, -20, -15, -10, -5, 0]

    for angle in precision_sequence:
        print(f"   Movimento fino: {angle}%")
        steering.set_steering_input(angle)

        status = steering.get_steering_status()
        actual_angle = status.get("current_angle", 0)
        print(f"   → Ângulo real: {actual_angle:+5.1f}°")

        time.sleep(0.5)


def test_steering_modes(steering):
    """Teste dos diferentes modos de direção"""
    print("\n=== TESTE DE MODOS DE DIREÇÃO ===")

    modes = [
        (SteeringMode.NORMAL, "Normal"),
        (SteeringMode.SPORT, "Sport"),
        (SteeringMode.COMFORT, "Comfort"),
        (SteeringMode.PARKING, "Parking"),
    ]

    for mode, name in modes:
        print(f"\n🔧 Testando modo {name}")
        steering.set_steering_mode(mode)

        # Teste com entrada padrão
        steering.set_steering_input(-50.0)
        time.sleep(0.5)

        status = steering.get_steering_status()
        angle = status.get("current_servo_angle", 0)
        sensitivity = steering._get_mode_sensitivity()

        print(f"   → Sensibilidade do modo: {sensitivity:.2f}")
        print(f"   → Ângulo resultante: {angle:.1f}°")

        # Volta ao centro
        steering.set_steering_input(0.0)
        time.sleep(0.3)


def test_steering_limits(steering):
    """Teste dos limites do sistema"""
    print("\n=== TESTE DE LIMITES ===")

    # Testa valores extremos
    extreme_values = [-150.0, -100.0, 100.0, 150.0]

    for value in extreme_values:
        print(f"\n⚠️ Testando valor extremo: {value}%")
        steering.set_steering_input(value)
        time.sleep(0.5)

        status = steering.get_steering_status()
        actual_input = status.get("steering_input", 0)
        angle = status.get("current_servo_angle", 0)

        print(f"   → Valor aplicado: {actual_input:.1f}%")
        print(f"   → Ângulo servo: {angle:.1f}°")

        # Volta ao centro
        steering.set_steering_input(0.0)
        time.sleep(0.3)


def test_steering_statistics(steering):
    """Teste das estatísticas do sistema"""
    print("\n=== ESTATÍSTICAS DO SISTEMA ===")

    stats = steering.get_statistics()

    print("📊 Estatísticas:")
    print(f"   → Comandos processados: {stats.get('commands_processed', 0)}")
    print(f"   → Movimentos realizados: {stats.get('movements_made', 0)}")
    print(f"   → Tempo ativo: {stats.get('active_time', 0):.1f}s")
    print(f"   → Última posição: {stats.get('last_angle', 0):.1f}°")
    print(f"   → Sistema inicializado: {stats.get('is_initialized', False)}")


def main():
    """Função principal do teste"""
    print("🏎️ === TESTE DO STEERING MANAGER ===")
    print("Este teste verifica o funcionamento do sistema de direção")
    print("Certifique-se de que o servo está conectado ao PCA9685:")
    print("  - Servo direção: Canal 2 do PCA9685")
    print("  - PCA9685 conectado via I2C (SDA=GPIO2, SCL=GPIO3)")
    if not PCA9685_AVAILABLE:
        print("⚠️ Aviso: PCA9685 não disponível - sistema funcionará em modo simulação")
    print()

    # Teste básico
    steering = test_steering_basic()
    if not steering:
        print("❌ Não foi possível inicializar - encerrando teste")
        return

    try:
        # Aguarda estabilização
        print("\n⏳ Aguardando estabilização do sistema...")
        time.sleep(2.0)

        # Testes funcionais
        test_steering_movements(steering)

        # Teste de velocidade
        print("\n" + "="*50)
        choice = input("🚀 Deseja executar teste de velocidade? (s/N): ").lower().strip()
        if choice in ['s', 'sim', 'y', 'yes']:
            test_steering_speed(steering)

        # Outros testes
        test_steering_modes(steering)
        test_steering_limits(steering)
        test_steering_statistics(steering)

        print("\n✅ Teste concluído com sucesso!")

    except KeyboardInterrupt:
        print("\n⚠️ Teste interrompido pelo usuário")

    except Exception as e:
        print(f"\n❌ Erro durante teste: {e}")

    finally:
        # Cleanup
        print("\n🔧 Finalizando sistema...")
        try:
            steering.center_steering()
            time.sleep(0.5)
            steering.cleanup()
            print("✓ Sistema finalizado corretamente")
        except:
            print("⚠️ Erro na finalização")


if __name__ == "__main__":
    main()
