#!/usr/bin/env python3
"""
main_client.py - Cliente Principal do Sistema F1
Recebe vídeo + dados de sensores do Raspberry Pi e exibe interface completa

SISTEMA COMPLETO:
================
├── main_client.py        - Aplicação principal (este arquivo)
├── network_client.py     - Gerencia recepção UDP
├── video_display.py      - Gerencia janela de vídeo
├── sensor_display.py     - Gerencia dados dos sensores
└── console_interface.py  - Interface do console

CONFIGURAÇÃO:
=============
1. Instalar dependências: pip install opencv-python numpy tkinter
2. Executar: python3 main_client.py
3. Aguardar conexão do Raspberry Pi

ESTRUTURA DOS DADOS RECEBIDOS:
=============================
O cliente está preparado para receber TODOS os dados do BMI160:
- Dados raw (LSB)
- Dados físicos (m/s², °/s)
- Forças G calculadas
- Eventos detectados (curvas, freios, etc.)
- Intensidades de force feedback
- Metadados (timestamp, contadores)
"""

import sys
import threading
import time
import queue
import argparse

# Importa nossos módulos
try:
    from network_client import NetworkClient
    from video_display import VideoDisplay
    from sensor_display import SensorDisplay
    from console_interface import ConsoleInterface
except ImportError as e:
    print(f"❌ ERRO: Não foi possível importar módulos necessários: {e}")
    print("\nVerifique se os arquivos estão na mesma pasta:")
    print("  - network_client.py")
    print("  - video_display.py")
    print("  - sensor_display.py")
    print("  - console_interface.py")
    print("  - main_client.py")
    sys.exit(1)

# Filas para comunicação entre threads
log_queue = queue.Queue()
status_queue = queue.Queue()
sensor_queue = queue.Queue()
video_queue = queue.Queue()

# Configurações padrão
DEFAULT_PORT = 9999
DEFAULT_BUFFER_SIZE = 131072


class F1ClientApplication:
    """Aplicação cliente principal do sistema F1"""

    def __init__(self, port=DEFAULT_PORT, buffer_size=DEFAULT_BUFFER_SIZE):
        """
        Inicializa a aplicação cliente

        Args:
            port (int): Porta UDP para escutar
            buffer_size (int): Tamanho do buffer UDP
        """
        self.port = port
        self.buffer_size = buffer_size

        # Componentes do sistema
        self.network_client = None
        self.video_display = None
        self.sensor_display = None
        self.console_interface = None

        # Controle de execução
        self.running = False

        # Threads
        self.network_thread = None
        self.console_thread = None
        self.video_thread = None

        # Estatísticas
        self.start_time = time.time()

    def initialize_components(self):
        """Inicializa todos os componentes do sistema"""
        print("🚀 Inicializando F1 Client...")
        print(f"📡 Porta UDP: {self.port}")
        print(f"📦 Buffer: {self.buffer_size // 1024} KB")
        print()

        try:
            # 1. Inicializa cliente de rede
            print("1. Inicializando cliente de rede...")
            self.network_client = NetworkClient(
                port=self.port,
                buffer_size=self.buffer_size,
                log_queue=log_queue,
                status_queue=status_queue,
                sensor_queue=sensor_queue,
                video_queue=video_queue,
            )

            # 2. Inicializa exibição de vídeo
            print("2. Inicializando exibição de vídeo...")
            self.video_display = VideoDisplay(
                video_queue=video_queue, log_queue=log_queue
            )

            # 3. Inicializa exibição de sensores
            print("3. Inicializando interface de sensores...")
            self.sensor_display = SensorDisplay(
                sensor_queue=sensor_queue, log_queue=log_queue
            )

            # 4. Inicializa interface do console
            print("4. Inicializando console...")
            self.console_interface = ConsoleInterface(
                log_queue=log_queue,
                status_queue=status_queue,
                sensor_display=self.sensor_display,
            )

            print("✅ Todos os componentes inicializados com sucesso!")
            return True

        except Exception as e:
            print(f"❌ Erro ao inicializar componentes: {e}")
            return False

    def start_network_thread(self):
        """Inicia thread de rede"""
        if self.network_client:
            self.network_thread = threading.Thread(
                target=self.network_client.run_receiver, daemon=True
            )
            self.network_thread.start()
            log_queue.put(("INFO", "Thread de rede iniciada"))

    def start_video_thread(self):
        """Inicia thread de vídeo"""
        if self.video_display:
            self.video_thread = threading.Thread(
                target=self.video_display.run_display, daemon=True
            )
            self.video_thread.start()
            log_queue.put(("INFO", "Thread de vídeo iniciada"))

    def start_console_thread(self):
        """Inicia thread do console (interface principal)"""
        if self.console_interface:
            self.console_thread = threading.Thread(
                target=self.console_interface.run_interface,
                daemon=False,  # Thread principal - não daemon
            )
            self.console_thread.start()
            log_queue.put(("INFO", "Interface do console iniciada"))

    def run(self):
        """Executa a aplicação principal"""
        # Inicializa componentes
        if not self.initialize_components():
            print("❌ Falha na inicialização dos componentes")
            return False

        print("\n=== INICIANDO SISTEMA F1 CLIENT ===")
        print("🎥 Aguardando vídeo do Raspberry Pi...")
        print("📊 Aguardando dados dos sensores...")
        print("🎮 Interface pronta para uso!")
        print("\nPara parar: Feche a janela do console ou pressione Ctrl+C")
        print()

        # Marca como executando
        self.running = True

        try:
            # Inicia threads na ordem correta
            self.start_network_thread()
            time.sleep(0.1)  # Pequena pausa

            self.start_video_thread()
            time.sleep(0.1)  # Pequena pausa

            # Console por último (thread principal)
            self.start_console_thread()

            # Aguarda thread principal (console)
            if self.console_thread:
                self.console_thread.join()

            print("\n✅ Sistema encerrado com sucesso!")
            return True

        except KeyboardInterrupt:
            print("\n⚠️ Interrompido pelo usuário (Ctrl+C)")
            return True
        except Exception as e:
            print(f"\n❌ Erro durante execução: {e}")
            import traceback

            traceback.print_exc()
            return False
        finally:
            self.stop()

    def stop(self):
        """Para a aplicação de forma limpa"""
        print("🛑 Parando F1 Client...")

        self.running = False

        # Para componentes
        try:
            if self.network_client:
                self.network_client.stop()

            if self.video_display:
                self.video_display.stop()

            if self.console_interface:
                self.console_interface.stop()

        except Exception as e:
            print(f"⚠️ Erro durante parada: {e}")

        # Aguarda threads (timeout para evitar travamento)
        threads = [self.network_thread, self.video_thread]
        for thread in threads:
            if thread and thread.is_alive():
                thread.join(timeout=1.0)

        print("✅ F1 Client parado")


def create_argument_parser():
    """Cria parser para argumentos da linha de comando"""
    parser = argparse.ArgumentParser(
        description="🏎️ F1 Client - Receptor de dados do carrinho controlável",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos de uso:
  python3 main_client.py
  python3 main_client.py --port 9999
  python3 main_client.py --port 8888 --buffer 256

O cliente ficará aguardando a conexão do Raspberry Pi.
Para parar: Feche a janela do console ou pressione Ctrl+C.
        """,
    )

    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Porta UDP para escutar (padrão: {DEFAULT_PORT})",
    )

    parser.add_argument(
        "--buffer",
        type=int,
        default=DEFAULT_BUFFER_SIZE // 1024,
        help=f"Tamanho do buffer em KB (padrão: {DEFAULT_BUFFER_SIZE // 1024})",
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

    # Converte buffer de KB para bytes
    buffer_size = args.buffer * 1024

    # Banner de inicialização
    print("🏎️" + "=" * 60)
    print("    F1 CAR CLIENT - REMOTE CONTROL RECEIVER")
    print("    Recebe vídeo + sensores do Raspberry Pi")
    print("=" * 62)
    print()

    # Configurações
    print("📋 CONFIGURAÇÕES:")
    print(f"   🔌 Porta: {args.port}")
    print(f"   📦 Buffer: {args.buffer} KB")
    print(f"   🐛 Debug: {'Ativado' if args.debug else 'Desativado'}")
    print()

    # Validação de argumentos
    if not (1024 <= args.port <= 65535):
        print("❌ ERRO: Porta deve estar entre 1024 e 65535")
        sys.exit(1)

    if not (32 <= args.buffer <= 1024):
        print("❌ ERRO: Buffer deve estar entre 32 e 1024 KB")
        sys.exit(1)

    # Criar e executar aplicação
    app = F1ClientApplication(port=args.port, buffer_size=buffer_size)

    try:
        # Executar aplicação
        success = app.run()

        if not success:
            print("\n❌ Falha na execução da aplicação")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️ Interrompido pelo usuário")
    except Exception as e:
        print(f"\n❌ Erro crítico: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)
    finally:
        print("\n👋 Obrigado por usar o F1 Client!")


if __name__ == "__main__":
    main()
