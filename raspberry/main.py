#!/usr/bin/env python3
"""
main_server.py - Aplicação Principal do Raspberry Pi
Integra câmera, sensores e transmissão UDP

SISTEMA COMPLETO:
================
├── camera_manager.py   - Gerencia câmera OV5647
├── bmi160_manager.py   - Gerencia sensor BMI160
├── network_manager.py  - Gerencia comunicação UDP
└── main_server.py      - Aplicação principal (este arquivo)

CONFIGURAÇÃO INICIAL:
====================
1. Conectar câmera OV5647 no slot CSI
2. Conectar BMI160 nos pinos I2C (GPIO2/3)
3. Configurar IP do PC de destino
4. Habilitar câmera e I2C no raspi-config
5. Instalar dependências

DEPENDÊNCIAS:
=============
sudo apt update
sudo apt install -y python3-opencv python3-picamera2 i2c-tools
pip install numpy bmi160-i2c

EXECUÇÃO:
=========
python3 main_server.py --ip 192.168.1.100 --port 9999

Para parar: Ctrl+C
"""

import argparse
import signal
import sys
import time
import threading
from typing import Optional

# Importa nossos gerenciadores
from camera_manager import CameraManager
from bmi160_manager import BMI160Manager
from network_manager import NetworkManager


class F1CarServer:
    """Servidor principal do carrinho F1 controlável"""

    def __init__(
        self,
        target_ip: str = "192.168.5.120",
        target_port: int = 9999,
        camera_fps: int = 30,
        sensor_rate: int = 100,
    ):
        """
        Inicializa o servidor do carrinho

        Args:
            target_ip (str): IP do PC cliente
            target_port (int): Porta UDP de destino
            camera_fps (int): Taxa de frames da câmera
            sensor_rate (int): Taxa de amostragem dos sensores (Hz)
        """
        self.target_ip = target_ip
        self.target_port = target_port
        self.camera_fps = camera_fps
        self.sensor_rate = sensor_rate

        # Gerenciadores
        self.camera_mgr: Optional[CameraManager] = None
        self.bmi160_mgr: Optional[BMI160Manager] = None
        self.network_mgr: Optional[NetworkManager] = None

        # Controle de execução
        self.running = False
        self.main_thread: Optional[threading.Thread] = None

        # Estatísticas
        self.start_time = time.time()
        self.frames_processed = 0
        self.sensor_readings = 0
        self.last_stats_time = time.time()

        # Configuração de sinal para parada limpa
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)

    def _signal_handler(self, signum, frame):
        """Manipulador de sinais para parada limpa"""
        print(f"\nRecebido sinal {signum} - Iniciando parada limpa...")
        self.stop()

    def initialize_components(self) -> bool:
        """
        Inicializa todos os componentes do sistema

        Returns:
            bool: True se todos inicializados com sucesso
        """
        print("=== INICIALIZANDO SISTEMA F1 CAR SERVER ===")
        print(f"Destino: {self.target_ip}:{self.target_port}")
        print(f"FPS câmera: {self.camera_fps}")
        print(f"Taxa sensores: {self.sensor_rate} Hz")
        print()

        # 1. Inicializa gerenciador de rede
        print("1. Inicializando rede...")
        self.network_mgr = NetworkManager(
            target_ip=self.target_ip, target_port=self.target_port, buffer_size=131072
        )

        if not self.network_mgr.initialize():
            print("✗ Falha ao inicializar rede")
            return False

        # 2. Inicializa câmera
        print("\n2. Inicializando câmera...")
        self.camera_mgr = CameraManager(
            resolution=(640, 480), frame_rate=self.camera_fps, jpeg_quality=20
        )

        if not self.camera_mgr.initialize():
            print("✗ Falha ao inicializar câmera")
            return False

        # 3. Inicializa sensor BMI160
        print("\n3. Inicializando sensor BMI160...")
        self.bmi160_mgr = BMI160Manager(
            sample_rate=self.sensor_rate,
            buffer_size=50,
            accel_range=BMI160Manager.ACCEL_RANGE_2G,
            gyro_range=BMI160Manager.GYRO_RANGE_250,
        )

        if not self.bmi160_mgr.initialize():
            print("✗ Falha ao inicializar BMI160")
            return False

        print("\n✓ TODOS OS COMPONENTES INICIALIZADOS COM SUCESSO")
        return True

    def run_main_loop(self):
        """Loop principal de captura e transmissão"""
        print("\n=== INICIANDO TRANSMISSÃO ===")
