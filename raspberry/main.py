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
• Servo Freio Diant.   -> GPIO4  (Pin 7)
• Servo Freio Tras.    -> GPIO17 (Pin 11)
• Motor BTS7960 RPWM   -> GPIO18 (Pin 12)
• Motor BTS7960 LPWM   -> GPIO27 (Pin 13)
• Motor BTS7960 R_EN   -> GPIO22 (Pin 15)
• Motor BTS7960 L_EN   -> GPIO23 (Pin 16)
• Servo Direção        -> GPIO24 (Pin 18)

CONFIGURAÇÃO INICIAL:
====================
1. sudo raspi-config -> Interface Options -> Camera -> Enable
2. sudo raspi-config -> Interface Options -> I2C -> Enable
3. sudo raspi-config -> Interface Options -> SPI -> Enable
4. sudo apt update && sudo apt install -y python3-opencv python3-picamera2 i2c-tools python3-rpi.gpio
5. pip install numpy RPLCD smbus2
6. sudo i2cdetect -y 1  # Verificar dispositivos I2C

EXECUÇÃO:
=========
python3 main.py                    # Descoberta automática (recomendado)
python3 main.py --ip 192.168.1.100 # Target IP manual (fallback)

Para parar: Ctrl+C
"""

import argparse
import signal
import sys
import time
import threading
from typing import Optional, Dict, Any

# Importa todos os gerenciadores
try:
    from camera_manager import CameraManager
    from bmi160_manager import BMI160Manager
    from brake_manager import BrakeManager
    from motor_manager import MotorManager, TransmissionMode
    from steering_manager import SteeringManager, SteeringMode
    from network_manager import NetworkManager
    from logger import info, debug, warn, error, init_logger, LogLevel
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
        transmission_mode: str = "automatic",
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
            transmission_mode (str): Modo de transmissão
            steering_mode (str): Modo de direção
        """
        self.target_ip = target_ip  # None = usar descoberta automática
        self.target_port = target_port
        self.use_auto_discovery = target_ip is None
        self.camera_fps = camera_fps
        self.sensor_rate = sensor_rate
        self.brake_balance = brake_balance

        # Converte strings para enums
        transmission_map = {
            "automatic": TransmissionMode.AUTOMATIC,
            "manual": TransmissionMode.MANUAL,
            "sport": TransmissionMode.SPORT,
        }
        steering_map = {
            "normal": SteeringMode.NORMAL,
            "sport": SteeringMode.SPORT,
            "comfort": SteeringMode.COMFORT,
            "parking": SteeringMode.PARKING,
        }

        self.transmission_mode = transmission_map.get(
            transmission_mode, TransmissionMode.AUTOMATIC
        )
        self.steering_mode = steering_map.get(steering_mode, SteeringMode.SPORT)

        # Gerenciadores de componentes
        self.camera_mgr: Optional[CameraManager] = None
        self.bmi160_mgr: Optional[BMI160Manager] = None
        self.brake_mgr: Optional[BrakeManager] = None
        self.motor_mgr: Optional[MotorManager] = None
        self.steering_mgr: Optional[SteeringManager] = None
        self.network_mgr: Optional[NetworkManager] = None

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
        if hasattr(self, '_stopping') and self._stopping:
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
            debug(f"Porta: {self.target_port}, FPS: {self.camera_fps}, Sensores: {self.sensor_rate}Hz", "MAIN")
        else:
            info(f"📡 Modo: Target IP fixo → {self.target_ip}:{self.target_port}", "MAIN")
            debug(f"FPS: {self.camera_fps}, Sensores: {self.sensor_rate}Hz", "MAIN")
        debug(f"Freio: {self.brake_balance}%, Transmissão: {self.transmission_mode.value}, Direção: {self.steering_mode.value}", "MAIN")

        success_count = 0
        total_components = 6

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

        # 2. Câmera
        debug("Inicializando câmera...", "MAIN")
        self.camera_mgr = CameraManager(
            resolution=(640, 480), frame_rate=self.camera_fps, jpeg_quality=20
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
            buffer_size=50,
            accel_range=BMI160Manager.ACCEL_RANGE_2G,
            gyro_range=BMI160Manager.GYRO_RANGE_250,
        )
        if self.bmi160_mgr.initialize():
            self.system_status["sensors"] = "Online"
            success_count += 1
            debug("Sensor BMI160 inicializado", "MAIN")
        else:
            warn("Sensor BMI160 não inicializado", "MAIN")

        # 4. Sistema de freios
        debug("Inicializando freios...", "MAIN")
        self.brake_mgr = BrakeManager(
            brake_balance=self.brake_balance, max_brake_force=90.0, response_time=0.1
        )
        if self.brake_mgr.initialize():
            self.system_status["brakes"] = "Online"
            success_count += 1
            debug("Freios inicializados", "MAIN")
        else:
            warn("Freios não inicializados", "MAIN")

        # 5. Motor e transmissão
        debug("Inicializando motor...", "MAIN")
        self.motor_mgr = MotorManager(
            max_acceleration=25.0, transmission_mode=self.transmission_mode
        )
        if self.motor_mgr.initialize():
            self.system_status["motor"] = "Online"
            success_count += 1
            debug("Motor inicializado", "MAIN")
        else:
            warn("Motor não inicializado", "MAIN")

        # 6. Sistema de direção
        debug("Inicializando direção...", "MAIN")
        self.steering_mgr = SteeringManager(
            steering_sensitivity=1.2,
            max_steering_angle=40.0,
            steering_mode=self.steering_mode,
            response_time=0.12,
        )
        if self.steering_mgr.initialize():
            self.system_status["steering"] = "Online"
            success_count += 1
            debug("Direção inicializada", "MAIN")
        else:
            warn("Direção não inicializada", "MAIN")

        if success_count >= 2:  # Mínimo: rede + pelo menos 1 componente
            info(f"SISTEMA PRONTO - {success_count}/{total_components} componentes online", "MAIN")
            return True
        else:
            error(f"FALHA CRÍTICA - Apenas {success_count}/{total_components} componentes", "MAIN")
            return False

    def run_main_loop(self):
        """Loop principal de operação do sistema completo"""
        info("Modo direto - Enviando dados para cliente fixo", "MAIN")
        info("Cliente: 192.168.5.11:9999", "MAIN")
        
        # Configura cliente fixo no NetworkManager
        self.network_mgr.set_fixed_client("192.168.5.11", 9999)
        
        info("Iniciando transmissão - Ctrl+C para parar", "MAIN")
        
        # Garante que o sistema está executando
        self.running = True
        last_stats_display = time.time()
        last_display_update = time.time()
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

                # === CONSOLIDAÇÃO DE DADOS ===

                # Consolida todos os dados em um pacote
                consolidated_data = {
                    **sensor_data,  # Dados do BMI160
                    **motor_status,  # Status do motor
                    **brake_status,  # Status dos freios
                    **steering_status,  # Status da direção
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
                        warn(f"Falha na transmissão do pacote {loop_count}", "MAIN", rate_limit=5.0)


                # === CONTROLE AUTOMÁTICO (DEMONSTRAÇÃO) ===

                # Demonstra controle automático baseado nos sensores
                if sensor_data and len(sensor_data) > 0:
                    self._process_automatic_control(sensor_data, motor_status)

                # === ESTATÍSTICAS ===

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


    def _process_automatic_control(
        self, sensor_data: Dict[str, Any], motor_status: Dict[str, Any]
    ):
        """Processa controle automático baseado nos sensores (demonstração)"""
        try:
            # Exemplo de controle automático baseado em sensores
            g_force_lateral = sensor_data.get("g_force_lateral", 0.0)
            is_turning = sensor_data.get("is_turning_left", False) or sensor_data.get(
                "is_turning_right", False
            )
            is_accelerating = sensor_data.get("is_accelerating", False)
            is_braking = sensor_data.get("is_braking", False)
            impact_detected = sensor_data.get("impact_detected", False)

            # Controle de segurança - parada de emergência em caso de impacto
            if impact_detected and self.motor_mgr and self.brake_mgr:
                error("IMPACTO DETECTADO - PARADA DE EMERGÊNCIA!", "SAFETY")
                self.motor_mgr.emergency_stop()
                self.brake_mgr.emergency_brake()
                return

            # Controle automático de freios em curvas (assistência)
            if self.brake_mgr and is_turning and g_force_lateral > 0.5:
                # Aplica freio leve automaticamente em curvas fechadas
                auto_brake = min(g_force_lateral * 20, 30)  # Máximo 30%
                self.brake_mgr.apply_brake(auto_brake)
            elif self.brake_mgr and not is_braking:
                # Libera freios se não há comando manual e não há necessidade automática
                current_brake = self.brake_mgr.total_brake_input
                if current_brake > 0:
                    self.brake_mgr.release_brakes()

            # Controle de motor - simula aceleração automática básica
            if self.motor_mgr:
                current_speed = motor_status.get("speed_kmh", 0.0)

                # Simula aceleração suave automática se velocidade baixa
                if current_speed < 10.0 and not is_braking:
                    auto_throttle = 15.0  # 15% de aceleração suave
                    self.motor_mgr.set_throttle(auto_throttle)
                elif is_turning and g_force_lateral > 0.8:
                    # Reduz potência em curvas fechadas
                    current_throttle = motor_status.get("current_pwm", 0.0)
                    reduced_throttle = current_throttle * 0.7  # Reduz 30%
                    self.motor_mgr.set_throttle(reduced_throttle)

            # Assistência de direção baseada no giroscópio
            if self.steering_mgr and motor_status:
                gyro_z = sensor_data.get("bmi160_gyro_z", 0.0)
                current_speed = motor_status.get("speed_kmh", 0.0)

                # Pequenas correções para compensar rotação excessiva
                if (
                    abs(gyro_z) > 30 and current_speed > 5
                ):  # Só corrige em velocidades maiores
                    correction = -gyro_z * 0.05  # Pequena correção oposta
                    correction = max(-10, min(10, correction))  # Limita correção

                    # Aplica correção sutil (descomente para ativar)
                    # current_input = self.steering_mgr.steering_input
                    # corrected_input = current_input + correction
                    # self.steering_mgr.set_steering_input(corrected_input, current_speed)

        except Exception as e:
            warn(f"Erro no controle automático: {e}", "AUTO", rate_limit=10.0)

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
            f"{net_stats.get('mbps', 0):.2f}Mbps", "STATS"
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
                    cleanup_thread = threading.Thread(target=component.cleanup)
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
                            info(f"Balanço de freio alterado para {balance:.1f}% por {client_ip}", "COMMAND")
                        else:
                            warn("Sistema de freios não disponível", "COMMAND")
                    except ValueError:
                        warn(f"Valor inválido para brake_balance: {balance_str}", "COMMAND")
                        
                elif control_cmd.startswith("BRAKE:"):
                    # Comando: CONTROL:BRAKE:50.0  
                    force_str = control_cmd[6:]  # Remove "BRAKE:"
                    try:
                        force = float(force_str)
                        if self.brake_mgr:
                            self.brake_mgr.apply_brake(force)
                            debug(f"Freio aplicado: {force:.1f}% por {client_ip}", "COMMAND")
                        else:
                            warn("Sistema de freios não disponível", "COMMAND")
                    except ValueError:
                        warn(f"Valor inválido para brake: {force_str}", "COMMAND")
                        
                elif control_cmd.startswith("THROTTLE:"):
                    # Comando: CONTROL:THROTTLE:30.0
                    throttle_str = control_cmd[9:]  # Remove "THROTTLE:"
                    try:
                        throttle = float(throttle_str)
                        if self.motor_mgr:
                            self.motor_mgr.set_throttle(throttle)
                            debug(f"Acelerador: {throttle:.1f}% por {client_ip}", "COMMAND")
                        else:
                            warn("Sistema de motor não disponível", "COMMAND")
                    except ValueError:
                        warn(f"Valor inválido para throttle: {throttle_str}", "COMMAND")
                        
                elif control_cmd.startswith("STEERING:"):
                    # Comando: CONTROL:STEERING:-15.0
                    angle_str = control_cmd[9:]  # Remove "STEERING:"
                    try:
                        angle = float(angle_str)
                        if self.steering_mgr:
                            self.steering_mgr.set_steering_angle(angle)
                            debug(f"Direção: {angle:.1f}° por {client_ip}", "COMMAND")
                        else:
                            warn("Sistema de direção não disponível", "COMMAND")
                    except ValueError:
                        warn(f"Valor inválido para steering: {angle_str}", "COMMAND")
                        
                elif control_cmd.startswith("GEAR_UP"):
                    # Comando: CONTROL:GEAR_UP
                    if self.motor_mgr:
                        success = self.motor_mgr.shift_gear_up()
                        if success:
                            info(f"Marcha aumentada por {client_ip} → Marcha {self.motor_mgr.current_gear}", "COMMAND")
                        else:
                            warn(f"Não foi possível aumentar marcha (já na máxima: {self.motor_mgr.current_gear})", "COMMAND")
                    else:
                        warn("Sistema de motor não disponível", "COMMAND")
                        
                elif control_cmd.startswith("GEAR_DOWN"):
                    # Comando: CONTROL:GEAR_DOWN
                    if self.motor_mgr:
                        success = self.motor_mgr.shift_gear_down()
                        if success:
                            info(f"Marcha diminuída por {client_ip} → Marcha {self.motor_mgr.current_gear}", "COMMAND")
                        else:
                            warn(f"Não foi possível diminuir marcha (já na mínima: {self.motor_mgr.current_gear})", "COMMAND")
                    else:
                        warn("Sistema de motor não disponível", "COMMAND")
                        
                else:
                    debug(f"Comando de controle desconhecido: {control_cmd}", "COMMAND")
                    
            else:
                debug(f"Comando não reconhecido: {command}", "COMMAND")
                
        except Exception as e:
            error(f"Erro ao processar comando '{command}' de {client_ip}: {e}", "COMMAND")


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
    debug(f"Porta: {args.port}, FPS: {args.fps}, Sensores: {args.sensor_rate}Hz", "CONFIG")
    debug(f"Freio: {args.brake_balance}%, Trans: {args.transmission}, Dir: {args.steering_mode}", "CONFIG")

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
        transmission_mode=args.transmission,
        steering_mode=args.steering_mode,
    )

    try:
        # Iniciar sistema
        success = system.start()

        if success:
            info("Sistema completo executado com sucesso!", "MAIN")

            # Mostra estatísticas finais
            final_stats = system.get_system_status()
            debug(f"Estatísticas: {final_stats['system_uptime']:.1f}s, {final_stats['frames_processed']} frames, {final_stats['sensor_readings']} sensores", "FINAL")
            debug(f"Componentes: {final_stats['components_online']}/{final_stats['total_components']} online", "FINAL")

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
