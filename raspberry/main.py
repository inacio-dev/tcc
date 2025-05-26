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
try:
    from camera_manager import CameraManager
    from bmi160_manager import BMI160Manager
    from network_manager import NetworkManager
except ImportError as e:
    print(f"❌ ERRO: Não foi possível importar módulos necessários: {e}")
    print("\nVerifique se os arquivos estão na mesma pasta:")
    print("  - camera_manager.py")
    print("  - bmi160_manager.py")
    print("  - network_manager.py")
    print("  - main_server.py")
    sys.exit(1)


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
        print("Para parar: Ctrl+C")
        print()

        self.running = True
        last_stats_display = time.time()

        try:
            while self.running:
                # Captura frame da câmera
                frame_data = None
                if self.camera_mgr:
                    frame_data = self.camera_mgr.capture_frame()
                    if frame_data:
                        self.frames_processed += 1

                # Atualiza dados dos sensores
                sensor_data = {}
                if self.bmi160_mgr:
                    if self.bmi160_mgr.update():
                        sensor_data = self.bmi160_mgr.get_sensor_data()
                        self.sensor_readings += 1

                # Transmite via UDP
                if self.network_mgr and (frame_data or sensor_data):
                    self.network_mgr.send_frame_with_sensors(frame_data, sensor_data)

                # Exibe estatísticas a cada 2 segundos
                current_time = time.time()
                if current_time - last_stats_display >= 2.0:
                    self._display_stats()
                    last_stats_display = current_time

                # Pequena pausa para controlar taxa de loop
                time.sleep(0.001)  # 1ms

        except KeyboardInterrupt:
            print("\n⚠️ Interrupção do usuário detectada")
        except Exception as e:
            print(f"\n❌ Erro durante execução: {e}")
            import traceback

            traceback.print_exc()
        finally:
            self.stop()

    def _display_stats(self):
        """Exibe estatísticas do sistema"""
        elapsed = time.time() - self.start_time

        # Calcular taxas
        fps = self.frames_processed / elapsed if elapsed > 0 else 0
        sensor_rate = self.sensor_readings / elapsed if elapsed > 0 else 0

        # Estatísticas de rede
        net_stats = {}
        if self.network_mgr:
            net_stats = self.network_mgr.get_transmission_stats()

        print(
            f"📊 STATS | "
            f"⏱️ {elapsed:.1f}s | "
            f"🎥 {fps:.1f} FPS | "
            f"📡 {sensor_rate:.1f} Hz | "
            f"📤 {net_stats.get('packets_sent', 0)} pkts | "
            f"🌐 {net_stats.get('mbps', 0):.2f} Mbps"
        )

    def start(self):
        """Inicia o servidor"""
        print("🚀 Iniciando F1 Car Server...")

        # Inicializa componentes
        if not self.initialize_components():
            print("❌ Falha na inicialização dos componentes")
            return False

        # Inicia loop principal em thread separada
        self.main_thread = threading.Thread(target=self.run_main_loop, daemon=True)
        self.main_thread.start()

        # Aguarda execução
        try:
            while self.running and self.main_thread.is_alive():
                time.sleep(0.1)
        except KeyboardInterrupt:
            print("\n⚠️ Parando servidor...")

        return True

    def stop(self):
        """Para o servidor de forma limpa"""
        print("\n🛑 Parando F1 Car Server...")

        self.running = False

        # Para componentes
        try:
            if self.camera_mgr:
                self.camera_mgr.cleanup()

            if self.bmi160_mgr:
                self.bmi160_mgr.cleanup()

            if self.network_mgr:
                self.network_mgr.cleanup()

        except Exception as e:
            print(f"⚠️ Erro durante parada: {e}")

        # Aguarda thread principal
        if self.main_thread and self.main_thread.is_alive():
            self.main_thread.join(timeout=2.0)

        print("✅ F1 Car Server parado com sucesso")


def create_argument_parser():
    """Cria parser para argumentos da linha de comando"""
    parser = argparse.ArgumentParser(
        description="🏎️ F1 Car Server - Sistema de controle remoto com force feedback",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python3 main_server.py --ip 192.168.1.100
  python3 main_server.py --ip 192.168.1.100 --port 9999 --fps 30
  python3 main_server.py --ip 192.168.1.100 --sensor-rate 200

Para descobrir seu IP:
  hostname -I        # No Raspberry Pi
  ipconfig           # No Windows (cliente)
  ifconfig           # No Linux/Mac (cliente)
        """,
    )

    parser.add_argument(
        "--ip",
        type=str,
        default="192.168.5.120",
        help="IP do PC cliente (padrão: 192.168.5.120)",
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
        default=100,
        help="Taxa de amostragem dos sensores em Hz (padrão: 100)",
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

    # Banner de inicialização
    print("🏎️" + "=" * 60)
    print("    F1 CAR REMOTE CONTROL SYSTEM")
    print("    Raspberry Pi 4 Server with Force Feedback")
    print("=" * 62)
    print()

    # Configurações
    print("📋 CONFIGURAÇÕES:")
    print(f"   🎯 IP Destino: {args.ip}")
    print(f"   🔌 Porta: {args.port}")
    print(f"   🎥 FPS Câmera: {args.fps}")
    print(f"   📡 Taxa Sensores: {args.sensor_rate} Hz")
    print(f"   🐛 Debug: {'Ativado' if args.debug else 'Desativado'}")
    print()

    # Validação de argumentos
    if not (1 <= args.fps <= 60):
        print("❌ ERRO: FPS deve estar entre 1 e 60")
        sys.exit(1)

    if not (10 <= args.sensor_rate <= 1000):
        print("❌ ERRO: Taxa de sensores deve estar entre 10 e 1000 Hz")
        sys.exit(1)

    # Criar e iniciar servidor
    server = F1CarServer(
        target_ip=args.ip,
        target_port=args.port,
        camera_fps=args.fps,
        sensor_rate=args.sensor_rate,
    )

    try:
        # Iniciar servidor
        success = server.start()

        if success:
            print("\n🎉 Sistema executado com sucesso!")
        else:
            print("\n❌ Falha na execução do sistema")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️ Interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro crítico: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\n👋 Obrigado por usar o F1 Car Server!")


if __name__ == "__main__":
    main()
