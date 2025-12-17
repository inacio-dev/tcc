#!/usr/bin/env python3
"""
main.py - Sistema Completo do Carrinho F1
Integra todos os componentes: câmera, sensores, motor, freios, direção, display e rede

SISTEMA COMPLETO INTEGRADO:
==========================
├── camera_manager.py     - Câmera OV5647
├── bmi160_manager.py     - Sensor IMU BMI160
├── brake_manager.py      - Sistema de freios (2x servos MG996R)
├── motor_manager.py      - Motor RS550 + transmissão 8 marchas
├── steering_manager.py   - Direção (servo MG996R)
├── network_manager.py    - Comunicação UDP
└── main.py               - Aplicação principal (este arquivo)

HARDWARE CONECTADO:
==================
• Câmera OV5647        -> Slot CSI
• BMI160 (I2C)         -> GPIO2/3 (SDA/SCL)
• PCA9685 (I2C)        -> GPIO2/3 (SDA/SCL) [COMPARTILHADO COM BMI160]
  ├── Servo Freio Diant. -> Canal 0 do PCA9685
  ├── Servo Freio Tras.  -> Canal 1 do PCA9685
  └── Servo Direção      -> Canal 2 do PCA9685
• Motor BTS7960 RPWM   -> GPIO18 (Pin 12)
• Motor BTS7960 LPWM   -> GPIO27 (Pin 13)
• Motor BTS7960 R_EN   -> GPIO22 (Pin 15)
• Motor BTS7960 L_EN   -> GPIO23 (Pin 16)

PINOS GPIO LIBERADOS (agora via PCA9685):
• GPIO4  (Pin 7)  -> LIBERADO (era freio frontal)
• GPIO17 (Pin 11) -> LIBERADO (era freio traseiro)
• GPIO24 (Pin 18) -> LIBERADO (era direção)

CONFIGURAÇÃO INICIAL:
====================
1. sudo raspi-config -> Interface Options -> Camera -> Enable
2. sudo raspi-config -> Interface Options -> I2C -> Enable
3. sudo raspi-config -> Interface Options -> SPI -> Enable
4. sudo apt update && sudo apt install -y python3-opencv python3-picamera2 i2c-tools python3-rpi.gpio
5. pip install numpy RPLCD smbus2
6. sudo pip3 install adafruit-circuitpython-pca9685 adafruit-motor adafruit-blinka
7. sudo i2cdetect -y 1  # Verificar dispositivos I2C (BMI160: 0x69, PCA9685: 0x40)

EXECUÇÃO:
=========
python3 main.py                    # Descoberta automática (recomendado)
python3 main.py --ip 192.168.1.100 # Target IP manual (fallback)

Para parar: Ctrl+C
"""

import argparse
import signal
import sys
import threading
import time
from typing import Any, Dict, Optional

# Importa todos os gerenciadores
try:
    from bmi160_manager import BMI160Manager
    from brake_manager import BrakeManager
    from camera_manager import CameraManager
    from logger import LogLevel, debug, error, info, init_logger, warn
    from motor_manager import MotorManager
    from network_manager import NetworkManager
    from power_monitor_manager import PowerMonitorManager
    from steering_manager import SteeringManager, SteeringMode
    from temperature_manager import TemperatureManager
except ImportError as e:
    print(f"❌ ERRO: Não foi possível importar módulos necessários: {e}")
    print("\nVerifique se todos os arquivos estão na mesma pasta:")
    print("  - camera_manager.py, bmi160_manager.py, brake_manager.py")
    print("  - motor_manager.py, steering_manager.py, network_manager.py")
    print("  - logger.py, main.py")
    sys.exit(1)


class F1CarCompleteSystem:
    """Sistema completo do carrinho F1 com todos os componentes"""

    def __init__(
        self,
        target_ip: Optional[str] = None,
        target_port: int = 9999,
        camera_fps: int = 30,
        sensor_rate: int = 100,
        brake_balance: float = 60.0,
        steering_mode: str = "sport",
    ):
        """
        Inicializa o sistema completo

        Args:
            target_ip (str, optional): IP do PC cliente (None = descoberta automática)
            target_port (int): Porta UDP de destino
            camera_fps (int): Taxa de frames da câmera
            sensor_rate (int): Taxa de amostragem dos sensores (Hz)
            brake_balance (float): Balanço de freio 0-100%
            steering_mode (str): Modo de direção
        """
        self.target_ip = target_ip  # None = usar descoberta automática
        self.target_port = target_port
        self.use_auto_discovery = target_ip is None
        self.camera_fps = camera_fps
        self.sensor_rate = sensor_rate
        self.brake_balance = brake_balance

        # REMOVIDO: transmission_map não usado (transmissão sempre manual)
        steering_map = {
            "normal": SteeringMode.NORMAL,
            "sport": SteeringMode.SPORT,
            "comfort": SteeringMode.COMFORT,
            "parking": SteeringMode.PARKING,
        }

        # Transmissão sempre manual - variável removida
        self.steering_mode = steering_map.get(steering_mode, SteeringMode.SPORT)

        # Gerenciadores de componentes
        self.camera_mgr: Optional[CameraManager] = None
        self.bmi160_mgr: Optional[BMI160Manager] = None
        self.brake_mgr: Optional[BrakeManager] = None
        self.motor_mgr: Optional[MotorManager] = None
        self.steering_mgr: Optional[SteeringManager] = None
        self.network_mgr: Optional[NetworkManager] = None
        self.temperature_mgr: Optional[TemperatureManager] = None
        self.power_mgr: Optional[PowerMonitorManager] = None

        # Controle de execução
        self.running = False
        self._stopping = False
        self.main_thread: Optional[threading.Thread] = None

        # Estatísticas gerais
        self.start_time = time.time()
        self.frames_processed = 0
        self.sensor_readings = 0
        self.control_commands_received = 0
        self.last_stats_time = time.time()

        # Estado do sistema
        self.system_status = {
            "camera": "Offline",
            "sensors": "Offline",
            "motor": "Offline",
            "brakes": "Offline",
            "steering": "Offline",
            "network": "Offline",
            "temperature": "Offline",
            "power": "Offline",
        }

        # Dados consolidados para exibição
        self.consolidated_data = {
            "wifi_connected": False,
            "wifi_ip": "Disconnected",
            "current_speed": 0.0,
            "current_gear": 1,
            "engine_rpm": 0,
            "battery_voltage": 12.0,
            "system_temp": 25.0,
            "uptime": 0,
        }

        # Configuração de sinal para parada limpa
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Manipulador de sinais para parada limpa"""
        print(
            f"\nRecebido sinal {signum} - Iniciando parada limpa do sistema completo..."
        )
        if hasattr(self, "_stopping") and self._stopping:
            print("\n⚠️  Forçando saída imediata...")
            sys.exit(0)
        self._stopping = True
        self.stop()

    def initialize_all_components(self) -> bool:
        """
        Inicializa todos os componentes do sistema

        Returns:
            bool: True se todos inicializados com sucesso
        """
        info("F1 CAR SYSTEM - Inicializando componentes", "MAIN")
        if self.use_auto_discovery:
            info("🔍 Modo: Descoberta automática de clientes", "MAIN")
            debug(
                f"Porta: {self.target_port}, FPS: {self.camera_fps}, Sensores: {self.sensor_rate}Hz",
                "MAIN",
            )
        else:
            info(
                f"📡 Modo: Target IP fixo → {self.target_ip}:{self.target_port}", "MAIN"
            )
            debug(f"FPS: {self.camera_fps}, Sensores: {self.sensor_rate}Hz", "MAIN")
        debug(
            f"Freio: {self.brake_balance}%, Transmissão: manual, Direção: {self.steering_mode.value}",
            "MAIN",
        )

        success_count = 0
        total_components = 8

        # 1. Rede
        debug("Inicializando rede UDP...", "MAIN")
        self.network_mgr = NetworkManager(
            data_port=self.target_port, command_port=9998, buffer_size=131072
        )
        # Configura callback para processar comandos do cliente
        self.network_mgr.command_callback = self._process_client_command

        if self.network_mgr.initialize():
            self.system_status["network"] = "Online"
            success_count += 1
            debug("Rede inicializada", "MAIN")
        else:
            error("Rede não inicializada", "MAIN")
            return False

        # 2. Câmera (H.264 hardware encoder)
        debug("Inicializando câmera com H.264 hardware encoder...", "MAIN")
        self.camera_mgr = CameraManager(
            resolution=(640, 480), frame_rate=self.camera_fps, bitrate=1500000
        )
        if self.camera_mgr.initialize():
            self.system_status["camera"] = "Online"
            success_count += 1
            debug("Câmera inicializada", "MAIN")
        else:
            warn("Câmera não inicializada", "MAIN")

        # 3. Sensor BMI160
        debug("Inicializando sensor BMI160...", "MAIN")
        self.bmi160_mgr = BMI160Manager(
            sample_rate=self.sensor_rate,
            accel_range=BMI160Manager.ACCEL_RANGE_2G,
            gyro_range=BMI160Manager.GYRO_RANGE_250,
        )
        if self.bmi160_mgr.initialize():
            self.system_status["sensors"] = "Online"
            success_count += 1
            debug("Sensor BMI160 inicializado", "MAIN")
        else:
            warn("Sensor BMI160 não inicializado", "MAIN")

        # 4. Sistema de freios via PCA9685
        debug("Inicializando freios via PCA9685...", "MAIN")
        self.brake_mgr = BrakeManager(
            front_channel=0,  # Canal 0 do PCA9685
            rear_channel=1,  # Canal 1 do PCA9685
            pca9685_address=0x40,  # Endereço I2C padrão
            brake_balance=self.brake_balance,
            max_brake_force=100.0,  # FORÇA MÁXIMA COMPLETA
            response_time=0.1,
        )
        if self.brake_mgr.initialize():
            self.system_status["brakes"] = "Online"
            success_count += 1
            info(
                "✅ Freios inicializados - PCA9685 canais 0 (frontal) e 1 (traseiro)",
                "MAIN",
            )
        else:
            error(
                "❌ Freios não inicializados - Verifique PCA9685 e conexões dos servos",
                "MAIN",
            )

        # 5. Motor e transmissão
        debug("Inicializando motor...", "MAIN")
        self.motor_mgr = MotorManager()
        if self.motor_mgr.initialize():
            self.system_status["motor"] = "Online"
            success_count += 1
            debug("Motor inicializado", "MAIN")
        else:
            warn("Motor não inicializado", "MAIN")

        # 6. Sistema de direção via PCA9685
        debug("Inicializando direção via PCA9685...", "MAIN")
        self.steering_mgr = SteeringManager(
            steering_channel=2,  # Canal 2 do PCA9685
            pca9685_address=0x40,  # Endereço I2C compartilhado
            steering_sensitivity=1.2,
            max_steering_angle=90.0,  # RANGE COMPLETO 0°-180°
            steering_mode=self.steering_mode,
            response_time=0.12,
        )
        if self.steering_mgr.initialize():
            self.system_status["steering"] = "Online"
            success_count += 1
            info("✅ Direção inicializada - PCA9685 canal 2 servo MG996R", "MAIN")
        else:
            error(
                "❌ Direção não inicializada - Verifique PCA9685 e conexão servo canal 2",
                "MAIN",
            )

        # 7. Sensor de temperatura DS18B20
        debug("Inicializando sensor de temperatura DS18B20...", "MAIN")
        self.temperature_mgr = TemperatureManager(
            gpio_pin=4, sampling_rate=1.0, enable_history=True
        )
        if self.temperature_mgr.initialize():
            self.system_status["temperature"] = "Online"
            success_count += 1
            debug("Sensor de temperatura inicializado", "MAIN")
        else:
            warn("Sensor de temperatura não inicializado", "MAIN")

        # 8. Monitor de energia (ADS1115 + INA219)
        debug("Inicializando monitor de energia...", "MAIN")
        self.power_mgr = PowerMonitorManager(
            sample_rate=10,  # 10Hz para energia
            buffer_size=20,
        )
        if self.power_mgr.initialize():
            self.system_status["power"] = "Online"
            success_count += 1
            info("✅ Monitor de energia inicializado (ADS1115 + INA219)", "MAIN")
        else:
            warn("Monitor de energia não inicializado", "MAIN")

        if success_count >= 2:  # Mínimo: rede + pelo menos 1 componente
            info(
                f"SISTEMA PRONTO - {success_count}/{total_components} componentes online",
                "MAIN",
            )
            return True
        else:
            error(
                f"FALHA CRÍTICA - Apenas {success_count}/{total_components} componentes",
                "MAIN",
            )
            return False

    def run_main_loop(self):
        """Loop principal de operação do sistema completo"""
        info("Modo direto - Enviando dados para cliente fixo", "MAIN")
        info("Cliente: f1client.local:9999 (mDNS)", "MAIN")

        # Configura cliente fixo no NetworkManager (via mDNS)
        self.network_mgr.set_fixed_client("f1client.local", 9999)

        info("Iniciando transmissão - Ctrl+C para parar", "MAIN")

        # Garante que o sistema está executando
        self.running = True
        last_stats_display = time.time()
        last_display_update = time.time()
        last_connect_ping = time.time()  # Controle para envio periódico de CONNECT
        loop_count = 0

        try:
            while self.running:
                # Modo direto - transmissão contínua (sem verificar clientes)
                loop_count += 1
                current_time = time.time()

                # === AQUISIÇÃO DE DADOS ===

                # Captura frame da câmera
                frame_data = None
                if self.camera_mgr and self.system_status["camera"] == "Online":
                    frame_data = self.camera_mgr.capture_frame()
                    if frame_data:
                        self.frames_processed += 1

                # Atualiza sensores
                sensor_data = {}
                if self.bmi160_mgr and self.system_status["sensors"] == "Online":
                    if self.bmi160_mgr.update():
                        sensor_data = self.bmi160_mgr.get_sensor_data()
                        self.sensor_readings += 1

                        # Log dos dados BMI160 a cada 60 loops (debug)
                        if loop_count % 60 == 0:  # ~0.5s @ 120Hz
                            debug(
                                f"BMI160 dados: accel({sensor_data.get('bmi160_accel_x', 0):.3f}, "
                                f"{sensor_data.get('bmi160_accel_y', 0):.3f}, "
                                f"{sensor_data.get('bmi160_accel_z', 0):.3f}) m/s² | "
                                f"gyro({sensor_data.get('bmi160_gyro_x', 0):.3f}, "
                                f"{sensor_data.get('bmi160_gyro_y', 0):.3f}, "
                                f"{sensor_data.get('bmi160_gyro_z', 0):.3f}) °/s",
                                "BMI160",
                            )
                    else:
                        if loop_count % 120 == 0:  # Log erro menos frequente
                            warn("BMI160 update() falhou", "BMI160")

                # Obter status dos outros componentes
                motor_status = {}
                if self.motor_mgr and self.system_status["motor"] == "Online":
                    motor_status = self.motor_mgr.get_motor_status()

                brake_status = {}
                if self.brake_mgr and self.system_status["brakes"] == "Online":
                    brake_status = self.brake_mgr.get_brake_status()

                steering_status = {}
                if self.steering_mgr and self.system_status["steering"] == "Online":
                    steering_status = self.steering_mgr.get_steering_status()

                temperature_status = {}
                if (
                    self.temperature_mgr
                    and self.system_status["temperature"] == "Online"
                ):
                    temperature_status = self.temperature_mgr.get_temperature_status()

                power_status = {}
                if self.power_mgr and self.system_status["power"] == "Online":
                    if self.power_mgr.update():
                        power_status = self.power_mgr.get_sensor_data()

                # === CONSOLIDAÇÃO DE DADOS ===

                # Consolida todos os dados em um pacote
                consolidated_data = {
                    **sensor_data,  # Dados do BMI160
                    **motor_status,  # Status do motor
                    **brake_status,  # Status dos freios
                    **steering_status,  # Status da direção
                    **temperature_status,  # Status da temperatura
                    **power_status,  # Status de energia (correntes/tensões)
                    # Metadados do sistema
                    "system_status": self.system_status.copy(),
                    "frame_count": self.frames_processed,
                    "sensor_count": self.sensor_readings,
                    "loop_count": loop_count,
                    "system_uptime": current_time - self.start_time,
                }

                # === TRANSMISSÃO DE DADOS ===

                if self.network_mgr and self.system_status["network"] == "Online":
                    success = self.network_mgr.send_frame_with_sensors(
                        frame_data, consolidated_data
                    )
                    if not success and loop_count <= 10:
                        warn(
                            f"Falha na transmissão do pacote {loop_count}",
                            "MAIN",
                            rate_limit=5.0,
                        )

                    # Log da transmissão a cada 120 loops (debug)
                    if loop_count % 120 == 0:  # ~1s @ 120Hz
                        sensor_count = len(sensor_data) if sensor_data else 0
                        debug(
                            f"Transmissão: {sensor_count} campos de sensor enviados para cliente",
                            "NET",
                        )

                # === CONTROLE MANUAL APENAS ===

                # BMI160 é usado APENAS para telemetria - não interfere nos controles
                # Todos os comandos vêm exclusivamente do cliente via network

                # === ESTATÍSTICAS ===

                # Exibe status de controles principais a cada mudança
                if current_time - last_display_update >= 0.5:  # A cada 500ms
                    self._display_control_status(
                        motor_status, brake_status, steering_status
                    )
                    last_display_update = current_time

                # Envio periódico de CONNECT para reconexão automática (a cada 10s)
                if current_time - last_connect_ping >= 10.0:
                    self.network_mgr.send_connect_to_client("f1client.local", 9998)
                    debug("CONNECT periódico enviado para cliente", "MAIN")
                    last_connect_ping = current_time

                # Stats menos frequentes para tempo real
                if current_time - last_stats_display >= 10.0:
                    self._display_system_stats()
                    last_stats_display = current_time

                # Controla taxa de loop para tempo real máximo (120 FPS)
                time.sleep(1.0 / 120.0)  # ~8.3ms por loop

        except KeyboardInterrupt:
            info("Interrupção do usuário (Ctrl+C)", "MAIN")
            self.running = False
        except Exception as e:
            error(f"Erro durante execução: {e}", "MAIN")
            import traceback

            traceback.print_exc()
            self.running = False
        finally:
            info("Parando sistema completo...", "MAIN")
            self.stop()

    def _display_control_status(self, motor_status, brake_status, steering_status):
        """Exibe status atual de todos os controles"""
        try:
            # Dados do motor
            throttle = motor_status.get("current_pwm", 0.0) if motor_status else 0.0
            gear = motor_status.get("current_gear", 1) if motor_status else 1
            rpm = motor_status.get("engine_rpm", 0.0) if motor_status else 0.0

            # Dados dos freios
            brake_front = (
                brake_status.get("front_brake_percent", 0.0) if brake_status else 0.0
            )
            brake_rear = (
                brake_status.get("rear_brake_percent", 0.0) if brake_status else 0.0
            )
            brake_total = max(brake_front, brake_rear)

            # Dados da direção
            steering = (
                steering_status.get("current_steering_percent", 0.0)
                if steering_status
                else 0.0
            )

            # Só exibe se houver mudança significativa
            if throttle > 0.1 or brake_total > 0.1 or abs(steering) > 0.1:
                print(
                    f"🔧 Motor: {throttle:.1f}% | Freio: {brake_total:.1f}% | Direção: {steering:+.1f}% "
                    f"(Marcha: {gear}ª, RPM: {rpm:.0f})"
                )
        except Exception as e:
            debug(f"Erro ao exibir status de controles: {e}", "MAIN")

    def _display_system_stats(self):
        """Exibe estatísticas do sistema"""
        elapsed = time.time() - self.start_time

        # Calcula taxas
        fps = self.frames_processed / elapsed if elapsed > 0 else 0
        sensor_rate = self.sensor_readings / elapsed if elapsed > 0 else 0

        # Conta componentes online
        components_online = sum(
            1 for status in self.system_status.values() if status == "Online"
        )
        total_components = len(self.system_status)

        # Estatísticas de rede
        net_stats = {}
        if self.network_mgr:
            net_stats = self.network_mgr.get_transmission_stats()

        debug(
            f"STATS: {elapsed:.1f}s | {fps:.1f}fps | {sensor_rate:.1f}Hz | "
            f"{components_online}/{total_components} OK | {net_stats.get('packets_sent', 0)} pkts | "
            f"{net_stats.get('mbps', 0):.2f}Mbps",
            "STATS",
        )

    def start(self):
        """Inicia o sistema completo"""
        info("Iniciando F1 Car Complete System...", "MAIN")

        # Inicializa todos os componentes
        if not self.initialize_all_components():
            error("Falha na inicialização dos componentes", "MAIN")
            return False

        # Executa loop principal
        self.run_main_loop()
        return True

    def stop(self):
        """Para o sistema completo de forma coordenada"""
        info("Parando F1 Car Complete System...", "MAIN")

        self.running = False

        # Para componentes em ordem reversa para evitar conflitos
        components_to_stop = [
            ("steering", self.steering_mgr),
            ("motor", self.motor_mgr),
            ("brakes", self.brake_mgr),
            ("power", self.power_mgr),
            ("temperature", self.temperature_mgr),
            ("sensors", self.bmi160_mgr),
            ("camera", self.camera_mgr),
            ("network", self.network_mgr),
        ]

        for name, component in components_to_stop:
            if component:
                try:
                    debug(f"Parando {name}...", "STOP")
                    # Timeout de 2 segundos para cada componente
                    import threading

                    if hasattr(component, "cleanup"):
                        cleanup_thread = threading.Thread(target=component.cleanup)
                    elif hasattr(component, "shutdown"):
                        cleanup_thread = threading.Thread(target=component.shutdown)
                    else:
                        debug(f"Componente {name} sem método cleanup/shutdown", "STOP")
                        continue

                    cleanup_thread.start()
                    cleanup_thread.join(timeout=2.0)

                    if cleanup_thread.is_alive():
                        warn(f"Timeout ao parar {name} - forçando", "STOP")

                    self.system_status[name] = "Offline"
                except Exception as e:
                    warn(f"Erro ao parar {name}: {e}", "STOP")

        info("F1 Car System parado com sucesso", "MAIN")

    def get_system_status(self) -> Dict[str, Any]:
        """
        Obtém status completo do sistema

        Returns:
            dict: Status de todos os componentes
        """
        elapsed = time.time() - self.start_time

        # Estatísticas gerais
        stats = {
            "system_uptime": round(elapsed, 2),
            "frames_processed": self.frames_processed,
            "sensor_readings": self.sensor_readings,
            "components_status": self.system_status.copy(),
            "components_online": sum(
                1 for s in self.system_status.values() if s == "Online"
            ),
            "total_components": len(self.system_status),
        }

        # Adiciona estatísticas específicas de cada componente
        if self.camera_mgr:
            stats["camera_stats"] = self.camera_mgr.get_statistics()

        if self.bmi160_mgr:
            stats["sensor_stats"] = self.bmi160_mgr.get_statistics()

        if self.brake_mgr:
            stats["brake_stats"] = self.brake_mgr.get_statistics()

        if self.motor_mgr:
            stats["motor_stats"] = self.motor_mgr.get_statistics()

        if self.steering_mgr:
            stats["steering_stats"] = self.steering_mgr.get_statistics()

        if self.temperature_mgr:
            stats["temperature_stats"] = self.temperature_mgr.get_temperature_status()

        if self.power_mgr:
            stats["power_stats"] = self.power_mgr.get_statistics()

        if self.network_mgr:
            stats["network_stats"] = self.network_mgr.get_transmission_stats()

        return stats

    def _process_client_command(self, client_ip: str, command: str):
        """
        Processa comandos recebidos do cliente

        Args:
            client_ip (str): IP do cliente que enviou o comando
            command (str): Comando recebido
        """
        try:
            debug(f"Comando de {client_ip}: {command}", "COMMAND")

            # Processa diferentes tipos de comando
            if command.startswith("CONTROL:"):
                control_cmd = command[8:]  # Remove "CONTROL:"

                if control_cmd.startswith("BRAKE_BALANCE:"):
                    # Comando: CONTROL:BRAKE_BALANCE:60.0
                    balance_str = control_cmd[14:]  # Remove "BRAKE_BALANCE:"
                    try:
                        balance = float(balance_str)
                        if self.brake_mgr:
                            self.brake_mgr.set_brake_balance(balance)
                            info(
                                f"Balanço de freio alterado para {balance:.1f}% por {client_ip}",
                                "COMMAND",
                            )
                        else:
                            warn("Sistema de freios não disponível", "COMMAND")
                    except ValueError:
                        warn(
                            f"Valor inválido para brake_balance: {balance_str}",
                            "COMMAND",
                        )

                elif control_cmd.startswith("BRAKE:"):
                    # Comando: CONTROL:BRAKE:50.0
                    force_str = control_cmd[6:]  # Remove "BRAKE:"
                    try:
                        force = float(force_str)
                        if self.brake_mgr:
                            self.brake_mgr.apply_brake(force)
                            info(f"✅ Freio aplicado: {force:.1f}%", "COMMAND")
                        else:
                            warn("Sistema de freios não disponível", "COMMAND")
                    except ValueError:
                        warn(f"Valor inválido para brake: {force_str}", "COMMAND")

                elif control_cmd.startswith("THROTTLE:"):
                    # Comando: CONTROL:THROTTLE:30.0
                    throttle_str = control_cmd[9:]  # Remove "THROTTLE:"
                    try:
                        throttle = float(throttle_str)
                        info(
                            f"🔧 Comando THROTTLE recebido: {throttle:.1f}% de {client_ip}",
                            "COMMAND",
                        )
                        if self.motor_mgr:
                            self.motor_mgr.set_throttle(throttle)
                            info(f"✅ Acelerador aplicado: {throttle:.1f}%", "COMMAND")
                        else:
                            warn("Sistema de motor não disponível", "COMMAND")
                    except ValueError:
                        warn(f"Valor inválido para throttle: {throttle_str}", "COMMAND")

                elif control_cmd.startswith("STEERING:"):
                    # Comando: CONTROL:STEERING:-100.0 (entrada -100% a +100%)
                    steering_str = control_cmd[9:]  # Remove "STEERING:"
                    try:
                        steering_input = float(steering_str)
                        if self.steering_mgr:
                            # Controle direto - apenas comando do usuário
                            self.steering_mgr.set_steering_input(steering_input)
                            info(f"✅ Direção: {steering_input:.1f}%", "COMMAND")
                        else:
                            warn("Sistema de direção não disponível", "COMMAND")
                    except ValueError:
                        warn(f"Valor inválido para steering: {steering_str}", "COMMAND")

                elif control_cmd.startswith("GEAR_UP"):
                    # Comando: CONTROL:GEAR_UP
                    if self.motor_mgr:
                        success = self.motor_mgr.shift_gear_up()
                        if success:
                            info(
                                f"Marcha aumentada por {client_ip} → Marcha {self.motor_mgr.current_gear}",
                                "COMMAND",
                            )
                        else:
                            warn(
                                f"Não foi possível aumentar marcha (já na máxima: {self.motor_mgr.current_gear})",
                                "COMMAND",
                            )
                    else:
                        warn("Sistema de motor não disponível", "COMMAND")

                elif control_cmd.startswith("GEAR_DOWN"):
                    # Comando: CONTROL:GEAR_DOWN
                    if self.motor_mgr:
                        success = self.motor_mgr.shift_gear_down()
                        if success:
                            info(
                                f"Marcha diminuída por {client_ip} → Marcha {self.motor_mgr.current_gear}",
                                "COMMAND",
                            )
                        else:
                            warn(
                                f"Não foi possível diminuir marcha (já na mínima: {self.motor_mgr.current_gear})",
                                "COMMAND",
                            )
                    else:
                        warn("Sistema de motor não disponível", "COMMAND")

                else:
                    debug(f"Comando de controle desconhecido: {control_cmd}", "COMMAND")

            else:
                debug(f"Comando não reconhecido: {command}", "COMMAND")

        except Exception as e:
            error(
                f"Erro ao processar comando '{command}' de {client_ip}: {e}", "COMMAND"
            )


def create_argument_parser():
    """Cria parser para argumentos da linha de comando"""
    parser = argparse.ArgumentParser(
        description="🏎️ F1 Car Complete System - Sistema completo de controle remoto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python3 main.py                                    # Descoberta automática (recomendado)
  python3 main.py --fps 30 --sensor-rate 200        # Auto-discovery com parâmetros
  python3 main.py --ip 192.168.1.100                # Target IP manual
  python3 main.py --ip 192.168.1.100 --port 9999    # IP + porta específicos

Componentes incluídos:
  • Câmera OV5647 (640x480 @ 30fps)
  • Sensor IMU BMI160 (acelerômetro + giroscópio)
  • Sistema de freios (servos dianteiro/traseiro)
  • Motor RS550 + transmissão 8 marchas
  • Sistema de direção (servo com geometria Ackermann)
  • Comunicação UDP (vídeo + telemetria)
  • Descoberta automática de clientes (recomendado)
  • Target IP manual como fallback

Para descobrir seu IP (se usar --ip manual):
  hostname -I        # No Raspberry Pi
  ipconfig           # No Windows (cliente)
  ifconfig           # No Linux/Mac (cliente)
        """,
    )

    parser.add_argument(
        "--ip",
        type=str,
        default=None,
        help="IP do PC cliente (opcional - usará descoberta automática se não especificado)",
    )

    parser.add_argument(
        "--port", type=int, default=9999, help="Porta UDP de destino (padrão: 9999)"
    )

    parser.add_argument(
        "--fps", type=int, default=30, help="Taxa de frames da câmera (padrão: 30)"
    )

    parser.add_argument(
        "--sensor-rate",
        type=int,
        default=200,
        help="Taxa de amostragem dos sensores em Hz (padrão: 200 para tempo real)",
    )

    parser.add_argument(
        "--brake-balance",
        type=float,
        default=60.0,
        help="Balanço de freio 0-100%% (0=dianteiro, 100=traseiro, padrão: 60)",
    )

    parser.add_argument(
        "--transmission",
        type=str,
        choices=["automatic", "manual", "sport"],
        default="automatic",
        help="Modo de transmissão (padrão: automatic)",
    )

    parser.add_argument(
        "--steering-mode",
        type=str,
        choices=["normal", "sport", "comfort", "parking"],
        default="sport",
        help="Modo de direção (padrão: sport)",
    )

    parser.add_argument(
        "--debug", action="store_true", help="Modo debug com mais informações"
    )

    return parser


def main():
    """Função principal do programa"""
    # Parse argumentos
    parser = create_argument_parser()
    args = parser.parse_args()

    # Inicializa logger com nível baseado no debug
    log_level = LogLevel.DEBUG if args.debug else LogLevel.INFO
    init_logger(log_level, enable_timestamp=args.debug)

    info("F1 CAR REMOTE CONTROL SYSTEM", "STARTUP")
    debug(
        f"Porta: {args.port}, FPS: {args.fps}, Sensores: {args.sensor_rate}Hz", "CONFIG"
    )
    debug(
        f"Freio: {args.brake_balance}%, Trans: {args.transmission}, Dir: {args.steering_mode}",
        "CONFIG",
    )

    # Validação de argumentos
    if not (1 <= args.fps <= 60):
        error("FPS deve estar entre 1 e 60", "CONFIG")
        sys.exit(1)

    if not (10 <= args.sensor_rate <= 1000):
        error("Taxa de sensores deve estar entre 10 e 1000 Hz", "CONFIG")
        sys.exit(1)

    if not (0 <= args.brake_balance <= 100):
        error("Balanço de freio deve estar entre 0 e 100%", "CONFIG")
        sys.exit(1)

    # Criar sistema completo
    system = F1CarCompleteSystem(
        target_ip=args.ip,
        target_port=args.port,
        camera_fps=args.fps,
        sensor_rate=args.sensor_rate,
        brake_balance=args.brake_balance,
        steering_mode=args.steering_mode,
    )

    try:
        # Iniciar sistema
        success = system.start()

        if success:
            info("Sistema completo executado com sucesso!", "MAIN")

            # Mostra estatísticas finais
            final_stats = system.get_system_status()
            debug(
                f"Estatísticas: {final_stats['system_uptime']:.1f}s, {final_stats['frames_processed']} frames, {final_stats['sensor_readings']} sensores",
                "FINAL",
            )
            debug(
                f"Componentes: {final_stats['components_online']}/{final_stats['total_components']} online",
                "FINAL",
            )

        else:
            error("Falha na execução do sistema", "MAIN")
            sys.exit(1)

    except KeyboardInterrupt:
        info("Interrompido pelo usuário", "MAIN")
    except Exception as e:
        error(f"Erro crítico: {e}", "MAIN")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        info("Obrigado por usar o F1 Car Complete System!", "MAIN")


if __name__ == "__main__":
    main()
