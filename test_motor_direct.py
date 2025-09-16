#!/usr/bin/env python3
"""
Teste direto do motor BTS7960 - similar ao teste do BMI160
Testa configuração e controle PWM do motor RS550
"""

import time
import sys

print("=== TESTE DIRETO DO MOTOR BTS7960 ===")

# Verificar disponibilidade do GPIO
try:
    import RPi.GPIO as GPIO
    GPIO_AVAILABLE = True
    print("✓ RPi.GPIO disponível")
except ImportError:
    GPIO_AVAILABLE = False
    print("❌ RPi.GPIO não disponível - MODO SIMULAÇÃO")

if not GPIO_AVAILABLE:
    print("❌ Este teste requer hardware real (Raspberry Pi)")
    sys.exit(1)

# Configurações conforme CLAUDE.md
RPWM_PIN = 18  # GPIO18 (Pin 12) - PWM Frente
LPWM_PIN = 27  # GPIO27 (Pin 13) - PWM Ré
R_EN_PIN = 22  # GPIO22 (Pin 15) - Enable Frente
L_EN_PIN = 23  # GPIO23 (Pin 16) - Enable Ré
PWM_FREQ = 2000  # 2kHz

print(f"Configuração BTS7960:")
print(f"  RPWM (Frente): GPIO{RPWM_PIN}")
print(f"  LPWM (Ré): GPIO{LPWM_PIN}")
print(f"  R_EN: GPIO{R_EN_PIN}")
print(f"  L_EN: GPIO{L_EN_PIN}")
print(f"  PWM Freq: {PWM_FREQ}Hz")

def cleanup_gpio():
    """Limpa configuração GPIO"""
    try:
        GPIO.cleanup()
        print("✓ GPIO limpo")
    except:
        pass

def test_motor():
    """Teste completo do motor"""
    try:
        print("\n--- INICIALIZANDO GPIO ---")
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        # Configura pinos como saída
        GPIO.setup(RPWM_PIN, GPIO.OUT)
        GPIO.setup(LPWM_PIN, GPIO.OUT)
        GPIO.setup(R_EN_PIN, GPIO.OUT)
        GPIO.setup(L_EN_PIN, GPIO.OUT)
        print("✓ Pinos configurados como saída")

        # Cria objetos PWM
        rpwm = GPIO.PWM(RPWM_PIN, PWM_FREQ)
        lpwm = GPIO.PWM(LPWM_PIN, PWM_FREQ)
        print("✓ Objetos PWM criados")

        print("\n--- TESTE 1: CONFIGURAÇÃO INICIAL ---")
        # Desabilita ponte H inicialmente
        GPIO.output(R_EN_PIN, GPIO.LOW)
        GPIO.output(L_EN_PIN, GPIO.LOW)
        print("✓ Enables desabilitados (segurança)")

        # Inicia PWM com duty cycle zero
        rpwm.start(0)
        lpwm.start(0)
        print("✓ PWM iniciado (0% duty cycle)")

        print("\n--- TESTE 2: HABILITANDO PONTE H ---")
        # Habilita ponte H (enables em HIGH)
        GPIO.output(R_EN_PIN, GPIO.HIGH)
        GPIO.output(L_EN_PIN, GPIO.HIGH)
        print("✓ Ponte H habilitada (R_EN=HIGH, L_EN=HIGH)")
        print("🔊 Motor deve fazer um pequeno ruído agora")
        time.sleep(2)

        print("\n--- TESTE 3: PWM FRENTE (RPWM) ---")
        print("Testando diferentes intensidades de PWM...")

        for pwm_value in [10, 25, 50, 75, 100]:
            print(f"  🔧 Aplicando PWM frente: {pwm_value}%")
            rpwm.ChangeDutyCycle(pwm_value)
            lpwm.ChangeDutyCycle(0)  # Ré desligada

            print(f"     Motor deve girar no sentido FRENTE com {pwm_value}% de potência")
            time.sleep(3)  # 3 segundos para observar

            # Para motor
            rpwm.ChangeDutyCycle(0)
            print(f"     Motor parado")
            time.sleep(1)

        print("\n--- TESTE 4: PWM RÉ (LPWM) ---")
        print("Testando ré...")

        for pwm_value in [10, 25, 50]:
            print(f"  🔧 Aplicando PWM ré: {pwm_value}%")
            rpwm.ChangeDutyCycle(0)  # Frente desligada
            lpwm.ChangeDutyCycle(pwm_value)

            print(f"     Motor deve girar no sentido RÉ com {pwm_value}% de potência")
            time.sleep(3)  # 3 segundos para observar

            # Para motor
            lpwm.ChangeDutyCycle(0)
            print(f"     Motor parado")
            time.sleep(1)

        print("\n--- TESTE 5: FREIO ELÉTRICO ---")
        print("  🔧 Aplicando freio elétrico (ambos PWM=0)")
        rpwm.ChangeDutyCycle(0)
        lpwm.ChangeDutyCycle(0)
        print("     Motor deve parar completamente")
        time.sleep(2)

        print("\n--- FINALIZANDO ---")
        # Para PWM
        rpwm.stop()
        lpwm.stop()

        # Desabilita ponte H
        GPIO.output(R_EN_PIN, GPIO.LOW)
        GPIO.output(L_EN_PIN, GPIO.LOW)
        print("✓ PWM parado e ponte H desabilitada")

        print("\n=== TESTE CONCLUÍDO ===")
        print("✅ Se o motor girou = Hardware OK")
        print("❌ Se motor não girou = Verificar:")
        print("   - Conexões dos fios (RPWM, LPWM, R_EN, L_EN)")
        print("   - Alimentação 5V da ponte H")
        print("   - Alimentação do motor (12V separada)")
        print("   - Motor em curto ou com defeito")

    except Exception as e:
        print(f"❌ Erro durante teste: {e}")

    finally:
        cleanup_gpio()

def interactive_test():
    """Teste interativo para controle manual"""
    print("\n" + "="*50)
    print("MODO INTERATIVO - Controle manual do motor")
    print("="*50)
    print("Comandos:")
    print("  f [PWM] - Frente com PWM% (ex: f 50)")
    print("  r [PWM] - Ré com PWM% (ex: r 30)")
    print("  s       - Parar motor")
    print("  q       - Sair")
    print()

    try:
        GPIO.setmode(GPIO.BCM)
        GPIO.setwarnings(False)

        GPIO.setup(RPWM_PIN, GPIO.OUT)
        GPIO.setup(LPWM_PIN, GPIO.OUT)
        GPIO.setup(R_EN_PIN, GPIO.OUT)
        GPIO.setup(L_EN_PIN, GPIO.OUT)

        rpwm = GPIO.PWM(RPWM_PIN, PWM_FREQ)
        lpwm = GPIO.PWM(LPWM_PIN, PWM_FREQ)

        # Habilita ponte H
        GPIO.output(R_EN_PIN, GPIO.HIGH)
        GPIO.output(L_EN_PIN, GPIO.HIGH)

        rpwm.start(0)
        lpwm.start(0)

        print("✓ Motor pronto para controle manual")

        while True:
            try:
                cmd = input("Motor> ").strip().lower()

                if cmd == 'q':
                    break
                elif cmd == 's':
                    rpwm.ChangeDutyCycle(0)
                    lpwm.ChangeDutyCycle(0)
                    print("🛑 Motor parado")
                elif cmd.startswith('f '):
                    try:
                        pwm = float(cmd.split()[1])
                        pwm = max(0, min(100, pwm))
                        rpwm.ChangeDutyCycle(pwm)
                        lpwm.ChangeDutyCycle(0)
                        print(f"⬆️ Frente {pwm}%")
                    except:
                        print("❌ Formato: f [PWM] (ex: f 50)")
                elif cmd.startswith('r '):
                    try:
                        pwm = float(cmd.split()[1])
                        pwm = max(0, min(100, pwm))
                        rpwm.ChangeDutyCycle(0)
                        lpwm.ChangeDutyCycle(pwm)
                        print(f"⬇️ Ré {pwm}%")
                    except:
                        print("❌ Formato: r [PWM] (ex: r 30)")
                else:
                    print("❌ Comando inválido")

            except KeyboardInterrupt:
                break

    except Exception as e:
        print(f"❌ Erro: {e}")
    finally:
        cleanup_gpio()

if __name__ == "__main__":
    print("Escolha o modo de teste:")
    print("1. Teste automático (recomendado)")
    print("2. Teste interativo")

    try:
        choice = input("Opção (1 ou 2): ").strip()

        if choice == "1":
            test_motor()
        elif choice == "2":
            interactive_test()
        else:
            print("Opção inválida")

    except KeyboardInterrupt:
        print("\n\n🛑 Teste interrompido pelo usuário")
        cleanup_gpio()