#!/usr/bin/env python3
"""
main_client.py - Cliente Principal do Sistema F1
Recebe vídeo + dados de sensores do Raspberry Pi e exibe interface completa

SISTEMA COMPLETO:
================
├── main.py                    - Aplicação principal (este arquivo)
├── managers/network.py        - Gerencia recepção UDP
├── managers/video.py          - Gerencia janela de vídeo
├── managers/sensor.py         - Gerencia dados dos sensores
└── console/                   - Interface do console

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

import argparse
import gc
import os
import queue
import socket
import sys
import threading
import time
import tkinter as tk
import traceback

# Importa nossos módulos
try:
    from console import ConsoleInterface
    from managers.g923 import G923Manager
    from managers.network import NetworkClient
    from managers.sensor import SensorDisplay
    from simple_logger import debug, error, info, warn
    from managers.video import VideoDisplay
    from managers.constants import VIDEO_PORT, SENSOR_PORT, COMMAND_PORT
except ImportError as e:
    print(f"❌ ERRO: Não foi possível importar módulos necessários: {e}")
    print("\nVerifique se os arquivos estão na mesma pasta:")
    print("  - managers/ (g923.py, network.py, video.py, sensor.py, ...)")
    print("  - console/, simple_logger.py, main.py")
    sys.exit(1)

# Filas para comunicação entre threads
log_queue = queue.Queue()
status_queue = queue.Queue()
sensor_queue = queue.Queue()
video_queue = queue.Queue()

# Configurações padrão
DEFAULT_PORT = VIDEO_PORT
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
        self.g923_manager = None

        # Controle de execução
        self.running = False

        # Threads
        self.network_thread = None
        self.console_thread = None
        self.video_thread = None
        self.command_tx_thread = None

        # Estado de controle compartilhado (atualizado pelo G923/teclado, enviado a 100Hz)
        self._control_state = "0,0,0"  # steering,throttle,brake
        self._control_state_lock = threading.Lock()

        # Estatísticas
        self.start_time = time.time()

        # Logging throttle para G923 (evita spam no console)
        self._g923_last_log_time = 0.0
        self._g923_log_interval = 1.0  # Log a cada 1 segundo no máximo

    def handle_slider_state(self, steering: float, throttle: float, brake: float):
        """Atualiza estado de controle a partir dos sliders/teclado.
        Mesmo formato que G923 — o loop 100Hz envia STATE:s,t,b ao RPi."""
        with self._control_state_lock:
            self._control_state = f"{steering:.0f},{throttle:.0f},{brake:.0f}"

    def handle_g923_command(self, command_type: str, value: str):
        """
        Trata comandos recebidos do G923 via evdev
        Encaminha para o Raspberry Pi via network client (só se RPi conectado)

        Args:
            command_type: Tipo do comando (STATE, GEAR_UP, GEAR_DOWN)
            value: Para STATE: "steering,throttle,brake". Vazio para GEAR.
        """
        try:
            # Log throttled (1x por segundo para não poluir console)
            now = time.time()
            if command_type == "STATE":
                if now - self._g923_last_log_time >= self._g923_log_interval:
                    self._g923_last_log_time = now
                    g923 = self.g923_manager
                    if g923:
                        log_queue.put((
                            "DEBUG",
                            f"G923: DIR={g923._steering:+4d}° "
                            f"ACEL={g923._throttle:3d}% "
                            f"FREIO={g923._brake:3d}%",
                        ))
            elif command_type in ["GEAR_UP", "GEAR_DOWN"]:
                log_queue.put(("INFO", f"G923: {command_type}"))

            if command_type == "STATE":
                # Apenas atualiza estado — o loop 100Hz envia continuamente
                with self._control_state_lock:
                    self._control_state = value
            elif command_type in ["GEAR_UP", "GEAR_DOWN"]:
                # Eventos de marcha: envia imediatamente (não são estado contínuo)
                if (
                    self.network_client
                    and self.network_client.packets_received > 0
                ):
                    self.network_client.send_control_command(command_type, 1.0)
        except Exception as e:
            log_queue.put(("WARN", f"Falha ao enviar comando: {command_type}:{value}"))

    def initialize_components(self):
        """Inicializa todos os componentes do sistema"""
        info("Inicializando F1 Client...", "CLIENT")
        debug(f"Porta UDP: {self.port}, Buffer: {self.buffer_size // 1024}KB", "CLIENT")

        try:
            # 1. Inicializa cliente de rede
            debug("Inicializando cliente de rede...", "CLIENT")
            self.network_client = NetworkClient(
                video_port=self.port,
                sensor_port=SENSOR_PORT,
                command_port=COMMAND_PORT,
                buffer_size=self.buffer_size,
                rpi_ip=self.rpi_ip,
                client_ip=self.client_ip,
                log_queue=log_queue,
                status_queue=status_queue,
                sensor_queue=sensor_queue,
                video_queue=video_queue,
            )

            # 1.5. Inicializa gerenciador do G923
            debug("Inicializando G923 Manager...", "CLIENT")
            self.g923_manager = G923Manager(
                command_callback=self.handle_g923_command,
                log_callback=lambda level, msg: log_queue.put((level, msg)),
            )

            # 2. Inicializa exibição de vídeo
            debug("Inicializando exibição de vídeo...", "CLIENT")
            self.video_display = VideoDisplay(
                video_queue=video_queue,
                log_queue=log_queue,
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
            # Conecta network client e state callback com console
            self.console_interface.set_network_client(self.network_client)
            self.console_interface.set_slider_state_callback(self.handle_slider_state)

            # 4.5. Conecta G923 manager com console
            debug("Conectando G923 manager com interface...", "CLIENT")
            self.console_interface.set_g923_manager(self.g923_manager)

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

    def start_g923(self):
        """Inicia leitura do G923 (auto-detecta e conecta)"""
        if self.g923_manager:
            if self.g923_manager.find_device():
                # Reaplicar calibração após find_device (que sobrescreve ranges com evdev)
                if hasattr(self, "console_interface") and self.console_interface:
                    sc = getattr(self.console_interface, "slider_controller", None)
                    if sc:
                        sc._apply_saved_calibration()
                self.g923_manager.start()
                log_queue.put(("INFO", "G923 conectado e ativo"))
            else:
                log_queue.put(
                    ("WARN", "G923 não encontrado - use sliders ou teclado como fallback")
                )

    def start_command_tx_thread(self):
        """Inicia loop de envio de comandos a 100Hz"""
        self.command_tx_thread = threading.Thread(
            target=self._command_tx_loop, name="CommandTX", daemon=True
        )
        self.command_tx_thread.start()
        log_queue.put(("INFO", "Thread de comandos TX 100Hz iniciada"))

    def _command_tx_loop(self):
        """Envia o estado de controle atual ao RPi a 100Hz continuamente.
        Tanto G923 quanto sliders/teclado atualizam _control_state,
        e este loop envia STATE:steering,throttle,brake uniformemente."""
        interval = 1.0 / 100.0  # 100Hz
        while self.running:
            try:
                if (
                    self.network_client
                    and self.network_client.packets_received > 0
                ):
                    with self._control_state_lock:
                        state = self._control_state
                    self.network_client.send_control_command("STATE", state)
                time.sleep(interval)
            except Exception:
                time.sleep(interval)

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

            # Inicia G923 (opcional - não bloqueia se não conectado)
            self.start_g923()
            time.sleep(0.1)  # Pequena pausa

            # Loop de envio de comandos a 100Hz
            self.start_command_tx_thread()
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
        except Exception:
            pass

        self.running = False

        # Para componentes na ordem correta:
        # 1. Video PRIMEIRO (para de atualizar Tkinter)
        # 2. Serial
        # 3. Console/Tkinter POR ÚLTIMO
        try:
            if hasattr(self, "video_display") and self.video_display:
                self.video_display.stop()
                # Aguarda thread do vídeo parar antes de destruir Tkinter
                if self.video_thread and self.video_thread.is_alive():
                    self.video_thread.join(timeout=1.0)
        except Exception as e:
            try:
                debug(f"Erro ao parar video: {e}", "CLIENT")
            except Exception:
                pass

        try:
            if hasattr(self, "g923_manager") and self.g923_manager:
                self.g923_manager.stop()
        except Exception as e:
            try:
                debug(f"Erro ao parar G923: {e}", "CLIENT")
            except Exception:
                pass

        try:
            if hasattr(self, "console_interface") and self.console_interface:
                self.console_interface.stop()

            # Aguarda thread do console finalizar
            if self.console_thread and self.console_thread.is_alive():
                self.console_thread.join(timeout=3.0)
                if self.console_thread.is_alive():
                    debug("Thread do console não finalizou - continuando", "CLIENT")

        except Exception as e:
            try:
                debug(f"Erro ao parar console: {e}", "CLIENT")
            except Exception:
                pass

        try:
            if hasattr(self, "network_client") and self.network_client:
                self.network_client.stop()
        except Exception as e:
            try:
                debug(f"Erro ao parar network: {e}", "CLIENT")
            except Exception:
                pass

        # Aguarda threads (timeout para evitar travamento)
        try:
            threads_to_wait = []

            # Coleta todas as threads ativas
            if self.network_thread and self.network_thread.is_alive():
                threads_to_wait.append(("network", self.network_thread))
            if self.video_thread and self.video_thread.is_alive():
                threads_to_wait.append(("video", self.video_thread))

            # Aguarda cada thread com timeout
            for name, thread in threads_to_wait:
                try:
                    debug(f"Aguardando thread {name}...", "CLIENT")
                    thread.join(timeout=1.0)
                    if thread.is_alive():
                        debug(f"Thread {name} não finalizou no timeout", "CLIENT")
                    else:
                        debug(f"Thread {name} finalizada", "CLIENT")
                except Exception as e:
                    debug(f"Erro ao aguardar thread {name}: {e}", "CLIENT")

        except Exception as e:
            try:
                debug(f"Erro ao aguardar threads: {e}", "CLIENT")
            except Exception:
                pass

        # Força finalização de threads daemon restantes
        try:
            active_threads = threading.active_count()
            if active_threads > 1:  # Main thread + outras
                debug(f"Ainda há {active_threads} threads ativas", "CLIENT")

                # Lista todas as threads ativas para debug
                for thread in threading.enumerate():
                    if thread != threading.current_thread():
                        debug(
                            f"Thread ativa: {thread.name} (daemon: {thread.daemon})",
                            "CLIENT",
                        )

                # Aguarda múltiplas vezes para threads daemon temporárias finalizarem
                for i in range(5):  # Máximo 2.5 segundos
                    time.sleep(0.5)
                    current_count = threading.active_count()
                    if current_count <= 1:
                        debug("Todas as threads finalizaram", "CLIENT")
                        break
                    debug(
                        f"Aguardando threads finalizar: {current_count} restantes",
                        "CLIENT",
                    )

                # Verifica estado final
                final_count = threading.active_count()
                if final_count > 1:
                    debug(f"AVISO: Ainda restam {final_count} threads ativas", "CLIENT")
                    # Lista threads que não finalizaram
                    for thread in threading.enumerate():
                        if thread != threading.current_thread():
                            debug(
                                f"Thread não finalizada: {thread.name} (daemon: {thread.daemon})",
                                "CLIENT",
                            )
        except Exception:
            pass

        # Limpa referências e força garbage collection agressivo
        try:
            # Remove referências aos componentes
            self.console_interface = None
            self.video_display = None
            self.network_client = None
            self.g923_manager = None

            # Força garbage collection múltiplas vezes
            # Força limpeza de objetos Tkinter órfãos
            try:
                # Destrói qualquer instância de Tkinter restante
                for obj in gc.get_objects():
                    if isinstance(
                        obj,
                        (
                            tk.Variable,
                            tk.StringVar,
                            tk.IntVar,
                            tk.DoubleVar,
                            tk.BooleanVar,
                        ),
                    ):
                        try:
                            obj._tk = None
                        except Exception:
                            pass
            except Exception:
                pass

            # Múltiplas passadas de garbage collection
            for _ in range(3):
                gc.collect()

        except Exception:
            pass

        try:
            debug("F1 Client parado", "CLIENT")
        except Exception:
            pass

        # Última tentativa: força o Python a esperar todas as threads
        try:
            # Aguarda até máximo 5 segundos para todas as threads não-daemon finalizarem
            for _ in range(50):  # 50 x 100ms = 5 segundos máximo
                non_daemon_threads = [
                    t
                    for t in threading.enumerate()
                    if t != threading.current_thread() and not t.daemon
                ]
                if not non_daemon_threads:
                    break
                time.sleep(0.1)

            # Log final das threads restantes
            final_threads = threading.enumerate()
            if len(final_threads) > 1:
                debug(f"Threads restantes no final: {len(final_threads)}", "CLIENT")
                for t in final_threads:
                    if t != threading.current_thread():
                        debug(f"Thread final: {t.name} (daemon: {t.daemon})", "CLIENT")

        except Exception:
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


def main():
    """Função principal do programa"""
    # Parse argumentos
    parser = create_argument_parser()
    args = parser.parse_args()

    # Converte buffer de KB para bytes
    buffer_size = args.buffer * 1024

    # Banner de inicialização
    info("=" * 60)
    info("F1 CAR CLIENT - REMOTE CONTROL RECEIVER")
    info("Recebe vídeo + sensores do Raspberry Pi")
    info("=" * 60)
    info(f"Porta: {args.port} | Buffer: {args.buffer} KB | Debug: {'Ativado' if args.debug else 'Desativado'}")

    # Validação de argumentos
    if not (1024 <= args.port <= 65535):
        error("Porta deve estar entre 1024 e 65535")
        sys.exit(1)

    if not (32 <= args.buffer <= 1024):
        error("Buffer deve estar entre 32 e 1024 KB")
        sys.exit(1)

    # Configuração via mDNS - funciona em qualquer rede
    rpi_hostname = "f1car.local"
    client_ip = "f1client.local"

    # Resolve hostname mDNS uma vez e guarda IP numérico (evita resolução por pacote)
    try:
        rpi_ip = socket.gethostbyname(rpi_hostname)
        info(f"mDNS resolvido: {rpi_hostname} → {rpi_ip}")
    except socket.gaierror:
        warn(f"Não foi possível resolver {rpi_hostname}, usando hostname direto")
        rpi_ip = rpi_hostname

    info(f"Vídeo: {rpi_ip}:{VIDEO_PORT} | Sensores: {rpi_ip}:{SENSOR_PORT} | Comandos: {client_ip}:{COMMAND_PORT}")

    # Criar e executar aplicação com IPs fixos
    app = F1ClientApplication(
        port=args.port, buffer_size=buffer_size, rpi_ip=rpi_ip, client_ip=client_ip
    )

    try:
        # Executar aplicação
        success = app.run()

        if not success:
            error("Falha na execução da aplicação")
            sys.exit(1)

    except KeyboardInterrupt:
        warn("Interrompido pelo usuário")
    except Exception as e:
        error(f"Erro crítico: {e}")
        traceback.print_exc()
        sys.exit(1)
    finally:
        # Garante que a aplicação pare corretamente
        try:
            app.stop()
        except Exception:
            pass
        info("F1 Client finalizado")

        # Força saída limpa para evitar erro "Tcl_AsyncDelete" do Tkinter
        # Este erro ocorre quando objetos Tkinter são garbage-collected em threads secundárias
        os._exit(0)


if __name__ == "__main__":
    main()
