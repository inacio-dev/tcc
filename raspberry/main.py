#!/usr/bin/env python3
"""
main.py - Sistema Completo do Carrinho F1 (Arquitetura Multi-Thread)
Integra todos os componentes: câmera, sensores, motor, freios, direção, display e rede

ARQUITETURA DE THREADS:
=======================
├── Thread Câmera (30Hz)      - Captura frames independente
├── Thread Sensores (100Hz)   - Lê BMI160 em alta taxa
├── Thread Energia (10Hz)     - Monitora ADS1115 + INA219
├── Thread Temperatura (1Hz)  - Lê DS18B20
├── Thread TX Rede (120Hz)    - Consolida e transmite dados
└── Thread RX Comandos        - Recebe comandos (daemon no NetworkManager)

COMUNICAÇÃO ENTRE THREADS:
=========================
- Filas thread-safe (queue.Queue) para dados
- Variáveis atômicas para estado atual
- Locks para acesso a recursos compartilhados

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

ALIMENTAÇÃO DO RASPBERRY PI (XL4015 5A + USB Breakout):
======================================================
Bateria LiPo 3S (11.1V) → XL4015 5A → USB Breakout → Raspberry Pi USB-C

XL4015 5A (Regulador Step-Down):
  - IN+   → Positivo da bateria (11.1V)
  - IN-   → GND da bateria
  - OUT+  → VBUS do USB Breakout (ajustar para 5.1V)
  - OUT-  → GND do USB Breakout

USB Breakout (Pinos: VBUS, GND, CC1, CC2, D+, D-):
  - VBUS  → OUT+ do XL4015 (5.1V)
  - GND   → OUT- do XL4015 (GND comum)
  - CC1   → Resistor 5.1kΩ → GND (identifica como fonte de energia)
  - CC2   → Resistor 5.1kΩ → GND (identifica como fonte de energia)
  - D+    → Não conectado (apenas alimentação)
  - D-    → Não conectado (apenas alimentação)

Notas:
  - Ajustar XL4015 para 5.1V (usar multímetro no potenciômetro)
  - Resistores 5.1kΩ nos CC1/CC2 são OBRIGATÓRIOS para USB-C
  - Raspberry Pi 4 requer mínimo 3A (XL4015 suporta até 5A)
  - GND do XL4015 passa pelo ACS758 50A antes do GND geral

EXECUÇÃO:
=========
python3 main.py                    # Descoberta automática (recomendado)
python3 main.py --ip 192.168.1.100 # Target IP manual (fallback)

Para parar: Ctrl+C
"""

import argparse
import queue
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
    from rpi_system_monitor import RpiSystemMonitor
    from steering_manager import SteeringManager, SteeringMode
    from temperature_manager import TemperatureManager
except ImportError as e:
    print(f"ERRO: Não foi possível importar módulos necessários: {e}")
    print("\nVerifique se todos os arquivos estão na mesma pasta:")
    print("  - camera_manager.py, bmi160_manager.py, brake_manager.py")
    print("  - motor_manager.py, steering_manager.py, network_manager.py")
    print("  - logger.py, main.py")
    sys.exit(1)


class F1CarMultiThreadSystem:
    """Sistema completo do carrinho F1 com arquitetura multi-thread"""

    def __init__(
        self,
        target_ip: Optional[str] = None,
        target_port: int = 9999,
        camera_resolution: tuple = (640, 480),
        camera_fps: int = 30,
        camera_quality: int = 85,
        camera_sharpness: float = 1.0,
        camera_contrast: float = 1.0,
        camera_saturation: float = 1.0,
        camera_brightness: float = 0.0,
        sensor_rate: int = 100,
        brake_balance: float = 60.0,
        steering_mode: str = "sport",
    ):
        """
        Inicializa o sistema multi-thread

        Args:
            target_ip: IP do PC cliente (None = descoberta automática)
            target_port: Porta UDP de destino
            camera_resolution: Resolução da câmera (largura, altura)
            camera_fps: Taxa de frames da câmera
            camera_quality: Qualidade MJPEG 1-100
            camera_sharpness: Nitidez 0.0-2.0
            camera_contrast: Contraste 0.0-2.0
            camera_saturation: Saturação 0.0-2.0
            camera_brightness: Brilho -1.0 a 1.0
            sensor_rate: Taxa de amostragem dos sensores (Hz)
            brake_balance: Balanço de freio 0-100%
            steering_mode: Modo de direção
        """
        self.target_ip = target_ip
        self.target_port = target_port
        self.use_auto_discovery = target_ip is None
        self.camera_resolution = camera_resolution
        self.camera_fps = camera_fps
        self.camera_quality = camera_quality
        self.camera_sharpness = camera_sharpness
        self.camera_contrast = camera_contrast
        self.camera_saturation = camera_saturation
        self.camera_brightness = camera_brightness
        self.sensor_rate = sensor_rate
        self.brake_balance = brake_balance

        steering_map = {
            "normal": SteeringMode.NORMAL,
            "sport": SteeringMode.SPORT,
            "comfort": SteeringMode.COMFORT,
            "parking": SteeringMode.PARKING,
        }
        self.steering_mode = steering_map.get(steering_mode, SteeringMode.SPORT)

        # === GERENCIADORES DE COMPONENTES ===
        self.camera_mgr: Optional[CameraManager] = None
        self.bmi160_mgr: Optional[BMI160Manager] = None
        self.brake_mgr: Optional[BrakeManager] = None
        self.motor_mgr: Optional[MotorManager] = None
        self.steering_mgr: Optional[SteeringManager] = None
        self.network_mgr: Optional[NetworkManager] = None
        self.temperature_mgr: Optional[TemperatureManager] = None
        self.power_mgr: Optional[PowerMonitorManager] = None
        self.rpi_sys_mgr: Optional[RpiSystemMonitor] = None

        # === FILAS THREAD-SAFE ===
        self.frame_queue = queue.Queue(maxsize=2)  # Últimos 2 frames
        self.sensor_queue = queue.Queue(maxsize=10)  # Últimas 10 leituras
        self.power_queue = queue.Queue(maxsize=5)  # Últimas 5 leituras
        self.temp_queue = queue.Queue(maxsize=3)  # Últimas 3 leituras

        # === DADOS ATUAIS (thread-safe via locks) ===
        self.current_data_lock = threading.Lock()
        self.current_frame = None
        self.current_sensor_data = {}
        self.current_power_data = {}
        self.current_temp_data = {}
        self.current_rpi_sys_data = {}  # Métricas do sistema Raspberry Pi (CPU, memória, disco, rede)
        self.current_motor_status = {}
        self.current_brake_status = {}
        self.current_steering_status = {}

        # === THREADS ===
        self.camera_thread: Optional[threading.Thread] = None
        self.sensor_thread: Optional[threading.Thread] = None
        self.power_thread: Optional[threading.Thread] = None
        self.temp_thread: Optional[threading.Thread] = None
        self.network_tx_thread: Optional[threading.Thread] = None

        # === CONTROLE DE EXECUÇÃO ===
        self.running = False
        self._stopping = False
        self.start_time = time.time()

        # === ESTATÍSTICAS ===
        self.stats_lock = threading.Lock()
        self.frames_captured = 0
        self.sensor_readings = 0
        self.packets_sent = 0
        self.commands_received = 0

        # === STATUS DO SISTEMA ===
        self.system_status = {
            "camera": "Offline",
            "sensors": "Offline",
            "motor": "Offline",
            "brakes": "Offline",
            "steering": "Offline",
            "network": "Offline",
            "temperature": "Offline",
            "power": "Offline",
            "rpi_system": "Offline",
        }

        # Configuração de sinal para parada limpa
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Manipulador de sinais para parada limpa"""
        print(f"\nRecebido sinal {signum} - Iniciando parada limpa...")
        if self._stopping:
            print("\n Forçando saída imediata...")
            sys.exit(0)
        self._stopping = True
        self.stop()

    def initialize_all_components(self) -> bool:
        """Inicializa todos os componentes do sistema"""
        info("F1 CAR SYSTEM - Inicializando componentes (Multi-Thread)", "MAIN")
        info(
            f"Porta: {self.target_port}, FPS: {self.camera_fps}, Sensores: {self.sensor_rate}Hz",
            "MAIN",
        )

        success_count = 0
        total_components = 9

        # 1. Rede (crítico - deve inicializar primeiro)
        debug("Inicializando rede UDP...", "MAIN")
        self.network_mgr = NetworkManager(
            data_port=self.target_port, command_port=9998, buffer_size=131072
        )
        self.network_mgr.command_callback = self._process_client_command

        if self.network_mgr.initialize():
            self.system_status["network"] = "Online"
            success_count += 1
            debug("Rede inicializada", "MAIN")
        else:
            error("Rede não inicializada - CRÍTICO", "MAIN")
            return False

        # 2. Câmera
        debug("Inicializando câmera...", "MAIN")
        self.camera_mgr = CameraManager(
            resolution=self.camera_resolution,
            frame_rate=self.camera_fps,
            quality=self.camera_quality,
            sharpness=self.camera_sharpness,
            contrast=self.camera_contrast,
            saturation=self.camera_saturation,
            brightness=self.camera_brightness,
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

        # 4. Sistema de freios
        debug("Inicializando freios...", "MAIN")
        self.brake_mgr = BrakeManager(
            front_channel=0,
            rear_channel=1,
            pca9685_address=0x40,
            brake_balance=self.brake_balance,
            max_brake_force=100.0,
            response_time=0.1,
        )
        if self.brake_mgr.initialize():
            self.system_status["brakes"] = "Online"
            success_count += 1
            info("Freios inicializados - PCA9685 canais 0/1", "MAIN")
        else:
            error("Freios não inicializados", "MAIN")

        # 5. Motor
        debug("Inicializando motor...", "MAIN")
        self.motor_mgr = MotorManager()
        if self.motor_mgr.initialize():
            self.system_status["motor"] = "Online"
            success_count += 1
            debug("Motor inicializado", "MAIN")
        else:
            warn("Motor não inicializado", "MAIN")

        # 6. Direção
        debug("Inicializando direção...", "MAIN")
        self.steering_mgr = SteeringManager(
            steering_channel=2,
            pca9685_address=0x40,
            steering_sensitivity=1.2,
            max_steering_angle=90.0,
            steering_mode=self.steering_mode,
            response_time=0.12,
        )
        if self.steering_mgr.initialize():
            self.system_status["steering"] = "Online"
            success_count += 1
            info("Direção inicializada - PCA9685 canal 2", "MAIN")
        else:
            error("Direção não inicializada", "MAIN")

        # 7. Temperatura
        debug("Inicializando sensor de temperatura...", "MAIN")
        self.temperature_mgr = TemperatureManager(
            gpio_pin=4, sampling_rate=1.0, enable_history=True
        )
        if self.temperature_mgr.initialize():
            self.system_status["temperature"] = "Online"
            success_count += 1
            debug("Sensor de temperatura inicializado", "MAIN")
        else:
            warn("Sensor de temperatura não inicializado", "MAIN")

        # 8. Monitor de energia
        debug("Inicializando monitor de energia...", "MAIN")
        self.power_mgr = PowerMonitorManager(sample_rate=10, buffer_size=20)
        if self.power_mgr.initialize():
            self.system_status["power"] = "Online"
            success_count += 1
            info("Monitor de energia inicializado", "MAIN")
        else:
            warn("Monitor de energia não inicializado", "MAIN")

        # 9. Monitor de sistema do Raspberry Pi (CPU, memória, disco, rede)
        debug("Inicializando monitor de sistema do RPi...", "MAIN")
        self.rpi_sys_mgr = RpiSystemMonitor(sample_rate=1.0)  # 1Hz
        if self.rpi_sys_mgr.initialize():
            self.system_status["rpi_system"] = "Online"
            success_count += 1
            info("Monitor de sistema do RPi inicializado", "MAIN")
        else:
            warn("Monitor de sistema do RPi não inicializado", "MAIN")

        if success_count >= 2:
            info(
                f"SISTEMA PRONTO - {success_count}/{total_components} componentes",
                "MAIN",
            )
            return True
        else:
            error(
                f"FALHA - Apenas {success_count}/{total_components} componentes", "MAIN"
            )
            return False

    # === THREADS DE AQUISIÇÃO ===

    def _camera_thread_loop(self):
        """Thread dedicada para captura de câmera (30Hz)"""
        debug("Thread de câmera iniciada", "CAM")
        interval = 1.0 / self.camera_fps

        while self.running:
            try:
                if self.camera_mgr and self.system_status["camera"] == "Online":
                    frame_data = self.camera_mgr.capture_frame()
                    if frame_data:
                        # Atualiza frame atual
                        with self.current_data_lock:
                            self.current_frame = frame_data

                        # Estatísticas
                        with self.stats_lock:
                            self.frames_captured += 1

                time.sleep(interval)

            except Exception as e:
                warn(f"Erro na thread de câmera: {e}", "CAM", rate_limit=5.0)
                time.sleep(0.1)

        debug("Thread de câmera finalizada", "CAM")

    def _sensor_thread_loop(self):
        """Thread dedicada para sensores BMI160 (100Hz)

        Envia dados de duas formas:
        1. Atualiza current_sensor_data (para thread TX incluir no pacote de vídeo)
        2. Envia diretamente via send_fast_sensors() na porta 9997 (100Hz)
        """
        debug("Thread de sensores iniciada (100Hz direto)", "BMI160")
        interval = 1.0 / self.sensor_rate

        while self.running:
            try:
                if self.bmi160_mgr and self.system_status["sensors"] == "Online":
                    if self.bmi160_mgr.update():
                        sensor_data = self.bmi160_mgr.get_sensor_data()

                        # Atualiza dados atuais (para thread TX)
                        with self.current_data_lock:
                            self.current_sensor_data = sensor_data

                        # Envia diretamente via porta de sensores rápidos (100Hz)
                        if (
                            self.network_mgr
                            and self.system_status["network"] == "Online"
                        ):
                            self.network_mgr.send_fast_sensors(sensor_data)

                        # Estatísticas
                        with self.stats_lock:
                            self.sensor_readings += 1

                time.sleep(interval)

            except Exception as e:
                warn(f"Erro na thread de sensores: {e}", "BMI160", rate_limit=5.0)
                time.sleep(0.01)

        debug("Thread de sensores finalizada", "BMI160")

    def _power_thread_loop(self):
        """Thread dedicada para monitor de energia (10Hz)"""
        debug("Thread de energia iniciada", "PWR")
        interval = 0.1  # 10Hz

        while self.running:
            try:
                if self.power_mgr and self.system_status["power"] == "Online":
                    if self.power_mgr.update():
                        power_data = self.power_mgr.get_sensor_data()

                        with self.current_data_lock:
                            self.current_power_data = power_data

                time.sleep(interval)

            except Exception as e:
                warn(f"Erro na thread de energia: {e}", "PWR", rate_limit=5.0)
                time.sleep(0.1)

        debug("Thread de energia finalizada", "PWR")

    def _temp_thread_loop(self):
        """Thread dedicada para temperatura (1Hz) - DS18B20 + métricas do sistema RPi"""
        debug("Thread de temperatura iniciada", "TEMP")
        interval = 1.0  # 1Hz

        while self.running:
            try:
                # Temperatura do sensor DS18B20 (externo)
                if (
                    self.temperature_mgr
                    and self.system_status["temperature"] == "Online"
                ):
                    temp_data = self.temperature_mgr.get_temperature_status()

                    with self.current_data_lock:
                        self.current_temp_data = temp_data

                # Métricas do sistema Raspberry Pi (CPU, memória, disco, rede)
                if (
                    self.rpi_sys_mgr
                    and self.system_status["rpi_system"] == "Online"
                ):
                    if self.rpi_sys_mgr.update():
                        rpi_sys_data = self.rpi_sys_mgr.get_sensor_data()

                        with self.current_data_lock:
                            self.current_rpi_sys_data = rpi_sys_data

                time.sleep(interval)

            except Exception as e:
                warn(f"Erro na thread de temperatura: {e}", "TEMP", rate_limit=5.0)
                time.sleep(1.0)

        debug("Thread de temperatura finalizada", "TEMP")

    def _network_tx_thread_loop(self):
        """Thread dedicada para transmissão de rede (120Hz)"""
        debug("Thread de transmissão iniciada", "NET-TX")
        interval = 1.0 / 120.0  # 120Hz
        last_stats_time = time.time()
        last_connect_ping = time.time()

        while self.running:
            try:
                current_time = time.time()

                # === COLETA DADOS ATUAIS ===
                with self.current_data_lock:
                    frame_data = self.current_frame
                    sensor_data = self.current_sensor_data.copy()
                    power_data = self.current_power_data.copy()
                    temp_data = self.current_temp_data.copy()
                    rpi_sys_data = self.current_rpi_sys_data.copy()

                # Atualiza status dos atuadores (não bloqueante)
                motor_status = {}
                if self.motor_mgr and self.system_status["motor"] == "Online":
                    motor_status = self.motor_mgr.get_motor_status()

                brake_status = {}
                if self.brake_mgr and self.system_status["brakes"] == "Online":
                    brake_status = self.brake_mgr.get_brake_status()

                steering_status = {}
                if self.steering_mgr and self.system_status["steering"] == "Online":
                    steering_status = self.steering_mgr.get_steering_status()

                # === CONSOLIDA DADOS ===
                consolidated_data = {
                    **sensor_data,
                    **motor_status,
                    **brake_status,
                    **steering_status,
                    **temp_data,
                    **power_data,
                    **rpi_sys_data,
                    "system_status": self.system_status.copy(),
                    "system_uptime": current_time - self.start_time,
                }

                # === TRANSMITE ===
                if self.network_mgr and self.system_status["network"] == "Online":
                    success = self.network_mgr.send_frame_with_sensors(
                        frame_data, consolidated_data
                    )
                    if success:
                        with self.stats_lock:
                            self.packets_sent += 1

                # === PING PERIÓDICO (a cada 10s) ===
                if current_time - last_connect_ping >= 10.0:
                    self.network_mgr.send_connect_to_client("f1client.local", 9998)
                    last_connect_ping = current_time

                # === ESTATÍSTICAS (a cada 10s) ===
                if current_time - last_stats_time >= 10.0:
                    self._display_system_stats()
                    last_stats_time = current_time

                time.sleep(interval)

            except Exception as e:
                warn(f"Erro na thread de transmissão: {e}", "NET-TX", rate_limit=5.0)
                time.sleep(0.01)

        debug("Thread de transmissão finalizada", "NET-TX")

    # === PROCESSAMENTO DE COMANDOS ===

    def _process_client_command(self, client_ip: str, command: str):
        """Processa comandos recebidos do cliente"""
        try:
            debug(f"Comando de {client_ip}: {command}", "CMD")

            with self.stats_lock:
                self.commands_received += 1

            if command.startswith("CONTROL:"):
                control_cmd = command[8:]

                if control_cmd.startswith("BRAKE_BALANCE:"):
                    balance = float(control_cmd[14:])
                    if self.brake_mgr:
                        self.brake_mgr.set_brake_balance(balance)
                        info(f"Balanço de freio: {balance:.1f}%", "CMD")

                elif control_cmd.startswith("BRAKE:"):
                    force = float(control_cmd[6:])
                    if self.brake_mgr:
                        self.brake_mgr.apply_brake(force)
                        debug(f"Freio: {force:.1f}%", "CMD")

                elif control_cmd.startswith("THROTTLE:"):
                    throttle = float(control_cmd[9:])
                    if self.motor_mgr:
                        self.motor_mgr.set_throttle(throttle)
                        debug(f"Acelerador: {throttle:.1f}%", "CMD")

                elif control_cmd.startswith("STEERING:"):
                    steering = float(control_cmd[9:])
                    if self.steering_mgr:
                        self.steering_mgr.set_steering_input(steering)
                        debug(f"Direção: {steering:.1f}%", "CMD")

                elif control_cmd.startswith("GEAR_UP"):
                    if self.motor_mgr:
                        if self.motor_mgr.shift_gear_up():
                            info(f"Marcha: {self.motor_mgr.current_gear}", "CMD")

                elif control_cmd.startswith("GEAR_DOWN"):
                    if self.motor_mgr:
                        if self.motor_mgr.shift_gear_down():
                            info(f"Marcha: {self.motor_mgr.current_gear}", "CMD")

                elif control_cmd.startswith("CAMERA_RESOLUTION:"):
                    resolution = control_cmd[18:]  # e.g., "720p", "1080p", "480p"
                    if self.camera_mgr:
                        if self.camera_mgr.set_resolution(resolution):
                            info(f"Resolução da câmera: {resolution}", "CMD")
                        else:
                            warn(f"Falha ao mudar resolução: {resolution}", "CMD")

                elif control_cmd.startswith("CAMERA_QUALITY:"):
                    quality = int(control_cmd[15:])
                    if self.camera_mgr:
                        # Atualiza a qualidade via recriação do encoder
                        self.camera_mgr.quality = max(1, min(100, quality))
                        info(f"Qualidade MJPEG: {quality}", "CMD")

                elif control_cmd.startswith("CAMERA_CONTROLS:"):
                    # Formato: CAMERA_CONTROLS:sharpness:contrast:saturation:brightness
                    try:
                        parts = control_cmd[16:].split(":")
                        if len(parts) >= 4:
                            sharpness = float(parts[0])
                            contrast = float(parts[1])
                            saturation = float(parts[2])
                            brightness = float(parts[3])
                            if self.camera_mgr:
                                self.camera_mgr.set_controls(
                                    sharpness=sharpness,
                                    contrast=contrast,
                                    saturation=saturation,
                                    brightness=brightness
                                )
                                debug(f"Controles: sharp={sharpness}, cont={contrast}, sat={saturation}, bri={brightness}", "CMD")
                    except ValueError:
                        warn("Formato inválido para CAMERA_CONTROLS", "CMD")

        except Exception as e:
            error(f"Erro ao processar comando: {e}", "CMD")

    # === CONTROLE DO SISTEMA ===

    def _display_system_stats(self):
        """Exibe estatísticas do sistema"""
        elapsed = time.time() - self.start_time

        with self.stats_lock:
            fps = self.frames_captured / elapsed if elapsed > 0 else 0
            sensor_hz = self.sensor_readings / elapsed if elapsed > 0 else 0
            pps = self.packets_sent / elapsed if elapsed > 0 else 0

        components_online = sum(
            1 for status in self.system_status.values() if status == "Online"
        )

        info(
            f"STATS: {elapsed:.0f}s | {fps:.1f}fps | {sensor_hz:.0f}Hz | "
            f"{pps:.0f}pps | {components_online}/9 online",
            "STATS",
        )

    def start(self):
        """Inicia o sistema multi-thread"""
        info("Iniciando F1 Car Multi-Thread System...", "MAIN")

        if not self.initialize_all_components():
            error("Falha na inicialização", "MAIN")
            return False

        # Configura cliente fixo
        self.network_mgr.set_fixed_client("f1client.local", 9999)
        info("Cliente: f1client.local:9999 (mDNS)", "MAIN")

        self.running = True

        # Inicia todas as threads
        info("Iniciando threads de aquisição...", "MAIN")

        self.camera_thread = threading.Thread(
            target=self._camera_thread_loop, name="CameraThread", daemon=True
        )
        self.sensor_thread = threading.Thread(
            target=self._sensor_thread_loop, name="SensorThread", daemon=True
        )
        self.power_thread = threading.Thread(
            target=self._power_thread_loop, name="PowerThread", daemon=True
        )
        self.temp_thread = threading.Thread(
            target=self._temp_thread_loop, name="TempThread", daemon=True
        )
        self.network_tx_thread = threading.Thread(
            target=self._network_tx_thread_loop, name="NetworkTXThread", daemon=True
        )

        # Inicia threads
        self.camera_thread.start()
        self.sensor_thread.start()
        self.power_thread.start()
        self.temp_thread.start()
        self.network_tx_thread.start()

        info("Sistema multi-thread ativo - Ctrl+C para parar", "MAIN")

        # Loop principal (mantém processo vivo)
        try:
            while self.running:
                time.sleep(0.5)
        except KeyboardInterrupt:
            info("Interrupção do usuário", "MAIN")
            self.running = False

        self.stop()
        return True

    def stop(self):
        """Para o sistema de forma coordenada"""
        info("Parando F1 Car System...", "MAIN")

        self.running = False

        # Aguarda threads finalizarem
        threads = [
            ("camera", self.camera_thread),
            ("sensor", self.sensor_thread),
            ("power", self.power_thread),
            ("temp", self.temp_thread),
            ("network_tx", self.network_tx_thread),
        ]

        for name, thread in threads:
            if thread and thread.is_alive():
                debug(f"Aguardando thread {name}...", "STOP")
                thread.join(timeout=2.0)
                if thread.is_alive():
                    warn(f"Thread {name} não finalizou", "STOP")

        # Para componentes
        components = [
            ("steering", self.steering_mgr),
            ("motor", self.motor_mgr),
            ("brakes", self.brake_mgr),
            ("power", self.power_mgr),
            ("rpi_system", self.rpi_sys_mgr),
            ("temperature", self.temperature_mgr),
            ("sensors", self.bmi160_mgr),
            ("camera", self.camera_mgr),
            ("network", self.network_mgr),
        ]

        for name, component in components:
            if component:
                try:
                    if hasattr(component, "cleanup"):
                        component.cleanup()
                    elif hasattr(component, "shutdown"):
                        component.shutdown()
                    self.system_status[name] = "Offline"
                except Exception as e:
                    warn(f"Erro ao parar {name}: {e}", "STOP")

        info("Sistema parado com sucesso", "MAIN")

    def get_system_status(self) -> Dict[str, Any]:
        """Obtém status completo do sistema"""
        elapsed = time.time() - self.start_time

        with self.stats_lock:
            return {
                "system_uptime": round(elapsed, 2),
                "frames_captured": self.frames_captured,
                "sensor_readings": self.sensor_readings,
                "packets_sent": self.packets_sent,
                "commands_received": self.commands_received,
                "components_status": self.system_status.copy(),
                "components_online": sum(
                    1 for s in self.system_status.values() if s == "Online"
                ),
            }


def create_argument_parser():
    """Cria parser para argumentos da linha de comando"""
    parser = argparse.ArgumentParser(
        description="F1 Car Multi-Thread System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python3 main.py                                    # Padrão (480p@30fps)
  python3 main.py --resolution 720p --fps 60        # HD 720p a 60fps
  python3 main.py --resolution 1080p --fps 30       # Full HD a 30fps
  python3 main.py --quality 95 --sharpness 1.5      # Alta qualidade + nitidez
  python3 main.py --debug                            # Modo verbose

Presets de resolução:
  480p  = 640x480   (leve, até 90fps)
  720p  = 1280x720  (HD, até 60fps)
  1080p = 1920x1080 (Full HD, até 30fps)
        """,
    )

    parser.add_argument("--ip", type=str, default=None, help="IP do cliente (opcional)")
    parser.add_argument(
        "--port", type=int, default=9999, help="Porta UDP (default: 9999)"
    )

    # Configurações de câmera
    parser.add_argument(
        "--resolution",
        type=str,
        choices=["480p", "720p", "1080p"],
        default="480p",
        help="Resolução da câmera (default: 480p)",
    )
    parser.add_argument(
        "--fps", type=int, default=30, help="FPS da câmera (default: 30)"
    )
    parser.add_argument(
        "--quality", type=int, default=85, help="Qualidade MJPEG 1-100 (default: 85)"
    )
    parser.add_argument(
        "--sharpness", type=float, default=1.0, help="Nitidez 0.0-2.0 (default: 1.0)"
    )
    parser.add_argument(
        "--contrast", type=float, default=1.0, help="Contraste 0.0-2.0 (default: 1.0)"
    )
    parser.add_argument(
        "--saturation", type=float, default=1.0, help="Saturação 0.0-2.0 (default: 1.0)"
    )
    parser.add_argument(
        "--brightness", type=float, default=0.0, help="Brilho -1.0 a 1.0 (default: 0.0)"
    )

    # Outras configurações
    parser.add_argument(
        "--sensor-rate", type=int, default=100, help="Taxa sensores Hz (default: 100)"
    )
    parser.add_argument(
        "--brake-balance",
        type=float,
        default=60.0,
        help="Balanço freio %% (default: 60)",
    )
    parser.add_argument(
        "--steering-mode",
        type=str,
        choices=["normal", "sport", "comfort", "parking"],
        default="sport",
    )
    parser.add_argument("--debug", action="store_true", help="Modo debug")

    return parser


def main():
    """Função principal"""
    parser = create_argument_parser()
    args = parser.parse_args()

    log_level = LogLevel.DEBUG if args.debug else LogLevel.INFO
    init_logger(log_level, enable_timestamp=args.debug)

    info("F1 CAR REMOTE CONTROL SYSTEM (Multi-Thread)", "STARTUP")

    # Mapeamento de resolução
    resolution_map = {
        "480p": (640, 480),
        "720p": (1280, 720),
        "1080p": (1920, 1080),
    }
    resolution = resolution_map[args.resolution]

    # Validações
    max_fps = {"480p": 90, "720p": 60, "1080p": 30}[args.resolution]
    if not (1 <= args.fps <= max_fps):
        error(f"FPS deve estar entre 1 e {max_fps} para {args.resolution}", "CONFIG")
        sys.exit(1)

    if not (1 <= args.quality <= 100):
        error("Qualidade deve estar entre 1 e 100", "CONFIG")
        sys.exit(1)

    if not (10 <= args.sensor_rate <= 1000):
        error("Taxa de sensores deve estar entre 10 e 1000 Hz", "CONFIG")
        sys.exit(1)

    # Log configuração de câmera
    info(f"Câmera: {args.resolution} @ {args.fps}fps, qualidade={args.quality}", "CONFIG")

    # Cria e inicia sistema
    system = F1CarMultiThreadSystem(
        target_ip=args.ip,
        target_port=args.port,
        camera_resolution=resolution,
        camera_fps=args.fps,
        camera_quality=args.quality,
        camera_sharpness=args.sharpness,
        camera_contrast=args.contrast,
        camera_saturation=args.saturation,
        camera_brightness=args.brightness,
        sensor_rate=args.sensor_rate,
        brake_balance=args.brake_balance,
        steering_mode=args.steering_mode,
    )

    try:
        system.start()
    except KeyboardInterrupt:
        info("Interrompido pelo usuário", "MAIN")
    except Exception as e:
        error(f"Erro crítico: {e}", "MAIN")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        info("F1 Car System finalizado", "MAIN")


if __name__ == "__main__":
    main()
