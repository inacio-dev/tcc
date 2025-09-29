#!/usr/bin/env python3
"""
test_temperature_sensor.py - Teste do Sensor de Temperatura DS18B20
Teste isolado para validar funcionamento do sensor de temperatura

HARDWARE NECESSÁRIO:
===================
• Sensor DS18B20 (1-Wire)
• Resistor pull-up 4.7kΩ entre VDD e DQ
• Conexões:
  - VDD (vermelho) → 3.3V (Pin 1)
  - GND (preto)    → GND (Pin 6)
  - DQ (amarelo)   → GPIO4 (Pin 7) + resistor 4.7kΩ para 3.3V

CONFIGURAÇÃO NECESSÁRIA:
=======================
1. sudo raspi-config → Interface Options → 1-Wire → Enable
2. Adicionar ao /boot/firmware/config.txt:
   dtoverlay=w1-gpio,gpiopin=4
3. sudo reboot
4. Verificar: ls /sys/bus/w1/devices/

EXECUÇÃO:
=========
python3 test_temperature_sensor.py
"""

import os
import sys
import time
import signal
from datetime import datetime

# Adiciona o diretório pai ao path para importar temperature_manager
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'raspberry'))

try:
    from temperature_manager import TemperatureManager
except ImportError as e:
    print(f"❌ ERRO: Não foi possível importar TemperatureManager: {e}")
    print("\nVerifique se o arquivo temperature_manager.py está em ../raspberry/")
    sys.exit(1)


class TemperatureSensorTest:
    """Teste isolado do sensor de temperatura DS18B20"""

    def __init__(self, gpio_pin=4, test_duration=60):
        """
        Inicializa teste do sensor

        Args:
            gpio_pin (int): GPIO do sensor (padrão: 4 - Pin 7)
            test_duration (int): Duração do teste em segundos
        """
        self.gpio_pin = gpio_pin
        self.test_duration = test_duration
        self.temperature_mgr = None
        self.running = False

        # Configurar sinal para parada limpa
        signal.signal(signal.SIGINT, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Handler para Ctrl+C"""
        print(f"\n🛑 Recebido sinal {signum} - Parando teste...")
        self.running = False

    def check_hardware_requirements(self):
        """Verifica se o hardware 1-Wire está configurado"""
        print("🔍 Verificando configuração 1-Wire...")

        # Verifica se módulo 1-Wire está carregado
        w1_dir = "/sys/bus/w1/devices/"
        if not os.path.exists(w1_dir):
            print("❌ Módulo 1-Wire não encontrado!")
            print("\nConfiguração necessária:")
            print("1. sudo raspi-config → Interface Options → 1-Wire → Enable")
            print("2. Adicionar ao /boot/config.txt: dtoverlay=w1-gpio,gpiopin=25")
            print("3. sudo reboot")
            return False

        # Lista dispositivos 1-Wire
        try:
            devices = os.listdir(w1_dir)
            ds18b20_devices = [d for d in devices if d.startswith('28-')]

            if not ds18b20_devices:
                print("⚠️  Nenhum sensor DS18B20 encontrado!")
                print(f"Dispositivos 1-Wire encontrados: {devices}")
                print("\nVerifique:")
                print("• Conexões do sensor (VDD, GND, DQ)")
                print("• Resistor pull-up 4.7kΩ entre DQ e VDD")
                print("• GPIO configurado corretamente")
                return False
            else:
                print(f"✅ Sensor(es) DS18B20 encontrado(s): {ds18b20_devices}")
                return True

        except Exception as e:
            print(f"❌ Erro ao verificar dispositivos 1-Wire: {e}")
            return False

    def test_temperature_manager_initialization(self):
        """Testa inicialização do TemperatureManager"""
        print(f"\n🧪 Testando inicialização do TemperatureManager (GPIO {self.gpio_pin})...")

        try:
            self.temperature_mgr = TemperatureManager(
                gpio_pin=self.gpio_pin,
                sampling_rate=1.0,  # 1 leitura por segundo
                enable_history=True
            )

            if self.temperature_mgr.initialize():
                print("✅ TemperatureManager inicializado com sucesso!")
                return True
            else:
                print("❌ Falha na inicialização do TemperatureManager")
                return False

        except Exception as e:
            print(f"❌ Erro na inicialização: {e}")
            return False

    def test_single_reading(self):
        """Testa uma leitura única de temperatura"""
        print("\n🌡️  Testando leitura única...")

        try:
            # Força uma leitura
            if self.temperature_mgr.update():
                temp_data = self.temperature_mgr.get_temperature_status()

                print(f"Temperatura: {temp_data.get('temperature_c', 'N/A')}°C")
                print(f"Status térmico: {temp_data.get('thermal_status', 'N/A')}")
                print(f"Timestamp: {temp_data.get('timestamp', 'N/A')}")

                return True
            else:
                print("❌ Falha na leitura de temperatura")
                return False

        except Exception as e:
            print(f"❌ Erro na leitura: {e}")
            return False

    def test_continuous_reading(self):
        """Testa leituras contínuas por um período"""
        print(f"\n📊 Testando leituras contínuas ({self.test_duration}s)...")
        print("Pressione Ctrl+C para parar antecipadamente\n")

        self.running = True
        start_time = time.time()
        reading_count = 0
        temperatures = []

        try:
            while self.running and (time.time() - start_time) < self.test_duration:
                current_time = time.time()

                # Atualiza temperatura
                if self.temperature_mgr.update():
                    temp_data = self.temperature_mgr.get_temperature_status()
                    reading_count += 1

                    temp_c = temp_data.get('temperature_c', 0.0)
                    temp_f = temp_data.get('temperature_f', 0.0)
                    temp_k = temp_data.get('temperature_k', 0.0)
                    thermal_status = temp_data.get('thermal_status', 'UNKNOWN')

                    temperatures.append(temp_c)

                    # Exibe leitura atual
                    elapsed = current_time - start_time
                    timestamp = datetime.now().strftime("%H:%M:%S")

                    print(f"[{timestamp}] #{reading_count:3d} | "
                          f"{temp_c:6.2f}°C | {temp_f:6.2f}°F | {temp_k:6.2f}K | "
                          f"Status: {thermal_status:8s} | "
                          f"Elapsed: {elapsed:6.1f}s")

                    # Detecta mudanças bruscas
                    if len(temperatures) >= 2:
                        temp_change = abs(temperatures[-1] - temperatures[-2])
                        if temp_change > 2.0:  # Mudança > 2°C
                            print(f"⚠️  Mudança brusca detectada: {temp_change:+.2f}°C")

                else:
                    print("❌ Falha na leitura - continuando...")

                # Aguarda próxima leitura
                time.sleep(1.0)

        except KeyboardInterrupt:
            print("\n🛑 Teste interrompido pelo usuário")
            self.running = False
        except Exception as e:
            print(f"\n❌ Erro durante teste contínuo: {e}")
            self.running = False

        # Estatísticas finais
        elapsed_total = time.time() - start_time
        if temperatures:
            temp_min = min(temperatures)
            temp_max = max(temperatures)
            temp_avg = sum(temperatures) / len(temperatures)
            temp_range = temp_max - temp_min

            print(f"\n📈 ESTATÍSTICAS ({elapsed_total:.1f}s):")
            print(f"   Leituras realizadas: {reading_count}")
            print(f"   Taxa real: {reading_count/elapsed_total:.2f} Hz")
            print(f"   Temperatura mínima: {temp_min:.2f}°C")
            print(f"   Temperatura máxima: {temp_max:.2f}°C")
            print(f"   Temperatura média: {temp_avg:.2f}°C")
            print(f"   Variação total: {temp_range:.2f}°C")

        return reading_count > 0

    def test_thermal_zones(self):
        """Testa detecção de zonas térmicas"""
        print("\n🔥 Testando detecção de zonas térmicas...")

        try:
            # Simula diferentes temperaturas para testar limites
            test_temperatures = [20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0]

            for temp in test_temperatures:
                # Simula temperatura forçando valor interno (apenas para teste)
                thermal_status = self.temperature_mgr._get_thermal_status(temp)
                print(f"Temp: {temp:5.1f}°C → Status: {thermal_status}")

            return True

        except Exception as e:
            print(f"❌ Erro no teste de zonas térmicas: {e}")
            return False

    def test_history_functionality(self):
        """Testa funcionalidade de histórico"""
        print("\n📚 Testando histórico de temperaturas...")

        try:
            # Coleta algumas leituras
            for i in range(5):
                if self.temperature_mgr.update():
                    print(f"Leitura {i+1}/5 coletada")
                    time.sleep(1)
                else:
                    print(f"❌ Falha na leitura {i+1}")

            # Obtém histórico
            history = self.temperature_mgr.get_temperature_history()
            print(f"Entradas no histórico: {len(history)}")

            if history:
                print("Últimas 3 entradas:")
                for entry in history[-3:]:
                    timestamp = datetime.fromtimestamp(entry['timestamp']).strftime("%H:%M:%S")
                    print(f"  [{timestamp}] {entry['temperature_c']:.2f}°C")

            return len(history) > 0

        except Exception as e:
            print(f"❌ Erro no teste de histórico: {e}")
            return False

    def cleanup(self):
        """Limpa recursos do teste"""
        print("\n🧹 Limpando recursos...")

        if self.temperature_mgr:
            try:
                self.temperature_mgr.cleanup()
                print("✅ TemperatureManager finalizado")
            except Exception as e:
                print(f"⚠️  Erro na limpeza: {e}")

    def run_complete_test(self):
        """Executa bateria completa de testes"""
        print("=" * 60)
        print("🌡️  TESTE DO SENSOR DE TEMPERATURA DS18B20")
        print("=" * 60)

        tests_passed = 0
        total_tests = 6

        # Teste 1: Verificação de hardware
        if self.check_hardware_requirements():
            tests_passed += 1
            print("✅ Teste 1/6: Hardware OK")
        else:
            print("❌ Teste 1/6: Hardware FALHOU")
            print("\n⚠️  Não é possível continuar sem hardware configurado")
            return False

        # Teste 2: Inicialização
        if self.test_temperature_manager_initialization():
            tests_passed += 1
            print("✅ Teste 2/6: Inicialização OK")
        else:
            print("❌ Teste 2/6: Inicialização FALHOU")
            return False

        # Teste 3: Leitura única
        if self.test_single_reading():
            tests_passed += 1
            print("✅ Teste 3/6: Leitura única OK")
        else:
            print("❌ Teste 3/6: Leitura única FALHOU")

        # Teste 4: Zonas térmicas
        if self.test_thermal_zones():
            tests_passed += 1
            print("✅ Teste 4/6: Zonas térmicas OK")
        else:
            print("❌ Teste 4/6: Zonas térmicas FALHOU")

        # Teste 5: Histórico
        if self.test_history_functionality():
            tests_passed += 1
            print("✅ Teste 5/6: Histórico OK")
        else:
            print("❌ Teste 5/6: Histórico FALHOU")

        # Teste 6: Leituras contínuas
        if self.test_continuous_reading():
            tests_passed += 1
            print("✅ Teste 6/6: Leituras contínuas OK")
        else:
            print("❌ Teste 6/6: Leituras contínuas FALHOU")

        # Resultado final
        print("\n" + "=" * 60)
        print(f"RESULTADO FINAL: {tests_passed}/{total_tests} testes passaram")

        if tests_passed == total_tests:
            print("🎉 TODOS OS TESTES PASSARAM!")
            print("✅ Sensor de temperatura DS18B20 está funcionando corretamente")
        elif tests_passed >= total_tests - 1:
            print("✅ Sensor funcionando com pequenos problemas")
        else:
            print("❌ Sensor com problemas significativos")

        print("=" * 60)

        return tests_passed >= (total_tests - 1)


def main():
    """Função principal do teste"""
    print("🌡️  Teste do Sensor de Temperatura DS18B20")
    print("Pressione Ctrl+C a qualquer momento para parar\n")

    # Configura teste
    test_duration = 30  # 30 segundos de teste contínuo
    gpio_pin = 4        # GPIO4 (Pin 7) - padrão 1-Wire

    # Cria e executa teste
    tester = TemperatureSensorTest(gpio_pin=gpio_pin, test_duration=test_duration)

    try:
        success = tester.run_complete_test()

        if success:
            print("\n🎯 Sensor de temperatura validado com sucesso!")
            print("Pode ser usado no sistema principal do F1 Car")
        else:
            print("\n⚠️  Sensor apresentou problemas")
            print("Verifique hardware e configuração antes de usar no sistema principal")

    except Exception as e:
        print(f"\n❌ Erro crítico durante teste: {e}")
        import traceback
        traceback.print_exc()

    finally:
        tester.cleanup()
        print("\n👋 Teste finalizado")


if __name__ == "__main__":
    main()