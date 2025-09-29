#!/usr/bin/env python3
"""
diagnose_1wire.py - Diagnóstico do Sistema 1-Wire
Verifica configuração completa do 1-Wire no Raspberry Pi

EXECUÇÃO:
=========
python test/diagnose_1wire.py
"""

import os
import subprocess
import glob


def check_boot_config():
    """Verifica configuração no boot"""
    print("🔍 1. Verificando /boot/config.txt...")

    try:
        with open('/boot/config.txt', 'r') as f:
            config_content = f.read()

        # Procura por configurações 1-Wire
        w1_configs = []
        for line in config_content.split('\n'):
            if 'w1' in line.lower() or '1-wire' in line.lower():
                w1_configs.append(line.strip())

        if w1_configs:
            print("✅ Configurações 1-Wire encontradas:")
            for config in w1_configs:
                if config.startswith('#'):
                    print(f"   ⚠️  COMENTADO: {config}")
                else:
                    print(f"   ✅ ATIVO: {config}")
        else:
            print("❌ Nenhuma configuração 1-Wire encontrada!")
            print("\nAdicione ao /boot/config.txt:")
            print("   dtoverlay=w1-gpio,gpiopin=25")

    except Exception as e:
        print(f"❌ Erro ao ler /boot/config.txt: {e}")


def check_kernel_modules():
    """Verifica módulos do kernel"""
    print("\n🔍 2. Verificando módulos do kernel...")

    modules_to_check = ['w1_gpio', 'w1_therm']

    try:
        result = subprocess.run(['lsmod'], capture_output=True, text=True)
        loaded_modules = result.stdout

        for module in modules_to_check:
            if module in loaded_modules:
                print(f"   ✅ Módulo {module} carregado")
            else:
                print(f"   ❌ Módulo {module} NÃO carregado")

    except Exception as e:
        print(f"❌ Erro ao verificar módulos: {e}")


def check_w1_directory():
    """Verifica diretório 1-Wire"""
    print("\n🔍 3. Verificando diretório 1-Wire...")

    w1_dir = "/sys/bus/w1/devices/"

    if os.path.exists(w1_dir):
        print(f"✅ Diretório {w1_dir} existe")

        try:
            devices = os.listdir(w1_dir)
            print(f"   Dispositivos encontrados: {len(devices)}")

            for device in devices:
                print(f"   📱 {device}")

                # Verifica se é um sensor DS18B20 (família 28)
                if device.startswith('28-'):
                    print(f"      ✅ DS18B20 detectado!")

                    # Tenta ler o sensor
                    sensor_file = os.path.join(w1_dir, device, 'w1_slave')
                    if os.path.exists(sensor_file):
                        try:
                            with open(sensor_file, 'r') as f:
                                data = f.read()
                            print(f"      📄 Dados do sensor:")
                            for line in data.strip().split('\n'):
                                print(f"         {line}")
                        except Exception as e:
                            print(f"      ❌ Erro ao ler sensor: {e}")
                    else:
                        print(f"      ❌ Arquivo w1_slave não encontrado")

        except Exception as e:
            print(f"❌ Erro ao listar dispositivos: {e}")
    else:
        print(f"❌ Diretório {w1_dir} NÃO existe")
        print("   Sistema 1-Wire não está funcionando")


def check_gpio_configuration():
    """Verifica configuração GPIO"""
    print("\n🔍 4. Verificando configuração GPIO...")

    try:
        # Verifica se GPIO25 está sendo usado para 1-Wire
        gpio_dir = "/sys/class/gpio/"

        if os.path.exists(gpio_dir):
            print(f"✅ Sistema GPIO disponível")

            # Lista GPIOs exportados
            exported_gpios = []
            for item in os.listdir(gpio_dir):
                if item.startswith('gpio'):
                    exported_gpios.append(item)

            if exported_gpios:
                print(f"   GPIOs exportados: {exported_gpios}")
            else:
                print("   Nenhum GPIO exportado manualmente")

        # Verifica device tree overlays
        dt_dir = "/proc/device-tree/soc/"
        if os.path.exists(dt_dir):
            overlays = []
            for item in os.listdir(dt_dir):
                if 'w1' in item:
                    overlays.append(item)

            if overlays:
                print(f"   ✅ Overlays 1-Wire: {overlays}")
            else:
                print("   ❌ Nenhum overlay 1-Wire encontrado")

    except Exception as e:
        print(f"❌ Erro ao verificar GPIO: {e}")


def check_dmesg_logs():
    """Verifica logs do sistema"""
    print("\n🔍 5. Verificando logs do sistema (dmesg)...")

    try:
        result = subprocess.run(['dmesg'], capture_output=True, text=True)
        dmesg_output = result.stdout

        # Procura por mensagens relacionadas ao 1-Wire
        w1_messages = []
        for line in dmesg_output.split('\n'):
            if 'w1' in line.lower() or '1-wire' in line.lower():
                w1_messages.append(line.strip())

        if w1_messages:
            print("✅ Mensagens 1-Wire encontradas:")
            for msg in w1_messages[-10:]:  # Últimas 10 mensagens
                print(f"   {msg}")
        else:
            print("❌ Nenhuma mensagem 1-Wire encontrada nos logs")

    except Exception as e:
        print(f"❌ Erro ao verificar dmesg: {e}")


def provide_solution():
    """Fornece soluções baseadas no diagnóstico"""
    print("\n" + "="*50)
    print("🔧 SOLUÇÕES POSSÍVEIS")
    print("="*50)

    print("\n1️⃣ CONFIGURAÇÃO BÁSICA:")
    print("   sudo raspi-config")
    print("   → Interface Options → 1-Wire → Enable")
    print("   → Finish → Yes (reboot)")

    print("\n2️⃣ CONFIGURAÇÃO MANUAL:")
    print("   sudo nano /boot/config.txt")
    print("   Adicionar linha: dtoverlay=w1-gpio,gpiopin=25")
    print("   sudo reboot")

    print("\n3️⃣ CARREGAR MÓDULOS MANUALMENTE:")
    print("   sudo modprobe w1-gpio")
    print("   sudo modprobe w1-therm")

    print("\n4️⃣ VERIFICAR HARDWARE:")
    print("   • Sensor DS18B20 conectado corretamente")
    print("   • VDD → Pin 1 (3.3V)")
    print("   • GND → Pin 6 (GND)")
    print("   • DQ  → Pin 22 (GPIO25)")
    print("   • Resistor 4.7kΩ entre DQ e VDD")

    print("\n5️⃣ TESTAR OUTRO GPIO:")
    print("   dtoverlay=w1-gpio,gpiopin=4")
    print("   (GPIO4 é o padrão)")

    print("\n6️⃣ VERIFICAR SENSOR:")
    print("   • Sensor pode estar danificado")
    print("   • Testar com multímetro")
    print("   • Verificar continuidade dos fios")


def main():
    """Executa diagnóstico completo"""
    print("🩺 DIAGNÓSTICO COMPLETO DO SISTEMA 1-WIRE")
    print("="*50)

    check_boot_config()
    check_kernel_modules()
    check_w1_directory()
    check_gpio_configuration()
    check_dmesg_logs()
    provide_solution()

    print("\n💡 PRÓXIMOS PASSOS:")
    print("1. Aplique as soluções sugeridas")
    print("2. Reinicie o sistema: sudo reboot")
    print("3. Execute novamente: python test/quick_temp_test.py")


if __name__ == "__main__":
    main()