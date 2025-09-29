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
    from simple_logger import init_logger, info, debug, error, LogLevel
except ImportError as e:
    print(f"❌ ERRO: Não foi possível importar módulos necessários: {e}")
    print("\nVerifique se os arquivos estão na mesma pasta:")
    print("  - network_client.py, video_display.py, sensor_display.py")
    print("  - console_interface.py, simple_logger.py, main_client.py")
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

    def __init__(
        self,
        port=DEFAULT_PORT,
        buffer_size=DEFAULT_BUFFER_SIZE,
        rpi_ip=None,
        client_ip=None,
    ):
        """
        Inicializa a aplicação cliente

        Args:
            port (int): Porta UDP para escutar dados
            buffer_size (int): Tamanho do buffer UDP
            rpi_ip (str): IP do Raspberry Pi
            client_ip (str): IP do cliente (este PC)
        """
        self.port = port
        self.buffer_size = buffer_size
        self.rpi_ip = rpi_ip
        self.client_ip = client_ip

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
        info("Inicializando F1 Client...", "CLIENT")
        debug(f"Porta UDP: {self.port}, Buffer: {self.buffer_size // 1024}KB", "CLIENT")

        try:
            # 1. Inicializa cliente de rede
            debug("Inicializando cliente de rede...", "CLIENT")
            self.network_client = NetworkClient(
                port=self.port,
                command_port=9998,
                buffer_size=self.buffer_size,
                rpi_ip=self.rpi_ip,
                client_ip=self.client_ip,
                log_queue=log_queue,
                status_queue=status_queue,
                sensor_queue=sensor_queue,
                video_queue=video_queue,
            )

            # 2. Inicializa exibição de vídeo COM melhorias habilitadas
            debug("Inicializando exibição de vídeo...", "CLIENT")
            self.video_display = VideoDisplay(
                video_queue=video_queue,
                log_queue=log_queue,
                enable_video_enhancements=True  # ATIVA correção de cor e outras melhorias
            )

            # 3. Inicializa exibição de sensores
            debug("Inicializando interface de sensores...", "CLIENT")
            self.sensor_display = SensorDisplay(
                sensor_queue=sensor_queue, log_queue=log_queue
            )

            # 4. Inicializa interface do console
            debug("Inicializando console...", "CLIENT")
            self.console_interface = ConsoleInterface(
                log_queue=log_queue,
                status_queue=status_queue,
                sensor_display=self.sensor_display,
            )
            # Conecta network client com console para envio de comandos
            self.console_interface.set_network_client(self.network_client)

            # 5. Conecta video display com console para exibição integrada
            debug("Conectando vídeo com interface...", "CLIENT")
            self.console_interface.set_video_display(self.video_display)

            debug("Todos os componentes inicializados!", "CLIENT")
            return True

        except Exception as e:
            error(f"Erro ao inicializar componentes: {e}", "CLIENT")
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
            error("Falha na inicialização dos componentes", "CLIENT")
            return False

        info("INICIANDO SISTEMA F1 CLIENT", "CLIENT")
        info("Aguardando Raspberry Pi... (Ctrl+C para parar)", "CLIENT")

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

            info("Sistema encerrado com sucesso!", "CLIENT")
            return True

        except KeyboardInterrupt:
            info("Interrompido pelo usuário (Ctrl+C)", "CLIENT")
            return True
        except Exception as e:
            error(f"Erro durante execução: {e}", "CLIENT")
            import traceback

            traceback.print_exc()
            return False
        finally:
            self.stop()

    def stop(self):
        """Para a aplicação de forma limpa"""
        if not self.running:
            return  # Já parou

        try:
            debug("Parando F1 Client...", "CLIENT")
        except:
            pass

        self.running = False

        # Para componentes na ordem correta (interface primeiro)
        try:
            if hasattr(self, "console_interface") and self.console_interface:
                self.console_interface.stop()
        except:
            pass

        try:
            if hasattr(self, "video_display") and self.video_display:
                self.video_display.stop()
        except:
            pass

        try:
            if hasattr(self, "network_client") and self.network_client:
                self.network_client.stop()
        except:
            pass

        # Aguarda threads (timeout para evitar travamento)
        try:
            threads = [self.network_thread, self.video_thread]
            for thread in threads:
                if thread and thread.is_alive():
                    thread.join(timeout=0.5)  # Timeout menor
        except:
            pass

        try:
            debug("F1 Client parado", "CLIENT")
        except:
            pass


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


def get_raspberry_pi_ip():
    """Solicita o IP do Raspberry Pi ao usuário"""
    print("🔍 CONEXÃO COM RASPBERRY PI")
    print("=" * 30)

    while True:
        try:
            # Sugere o IP padrão do projeto
            rpi_ip = input(
                "📡 Digite o IP do Raspberry Pi (ex: 192.168.5.12): "
            ).strip()

            if not rpi_ip:
                print("❌ Por favor, digite um IP válido!")
                continue

            # Validação básica de IP
            parts = rpi_ip.split(".")
            if len(parts) != 4:
                print("❌ Formato de IP inválido! Use o formato: xxx.xxx.xxx.xxx")
                continue

            # Verifica se cada parte é um número entre 0-255
            valid = True
            for part in parts:
                try:
                    num = int(part)
                    if not (0 <= num <= 255):
                        valid = False
                        break
                except ValueError:
                    valid = False
                    break

            if not valid:
                print("❌ IP inválido! Cada número deve estar entre 0 e 255")
                continue

            # Confirmação
            confirm = (
                input(f"✅ Conectar ao Raspberry Pi em {rpi_ip}? (s/n): ")
                .strip()
                .lower()
            )
            if confirm in ["s", "sim", "y", "yes", ""]:
                return rpi_ip
            elif confirm in ["n", "não", "nao", "no"]:
                continue
            else:
                print("❌ Responda com 's' para sim ou 'n' para não")

        except KeyboardInterrupt:
            print("\n⚠️ Operação cancelada pelo usuário")
            return None
        except Exception as e:
            print(f"❌ Erro: {e}")
            continue


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

    # Configuração fixa - sem descoberta
    rpi_ip = "192.168.5.33"
    client_ip = "192.168.5.12"

    print("🔗 CONFIGURAÇÃO FIXA:")
    print(f"   📡 Raspberry Pi: {rpi_ip}:9999 → 192.168.5.12:9999 (dados)")
    print(f"   🎮 Cliente: {client_ip}:9998 → 192.168.5.33:9998 (comandos)")
    print()

    # Criar e executar aplicação com IPs fixos
    app = F1ClientApplication(
        port=args.port, buffer_size=buffer_size, rpi_ip=rpi_ip, client_ip=client_ip
    )

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
        # Garante que a aplicação pare corretamente
        try:
            app.stop()
        except:
            pass
        print("\n👋 Obrigado por usar o F1 Client!")


if __name__ == "__main__":
    main()
