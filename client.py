#!/usr/bin/env python3
# Cliente UDP com interface de vídeo e console de log separados
# Permite selecionar, copiar e pausar os logs para análise

import queue
import socket
import struct
import sys
import threading
import time
import tkinter as tk
from datetime import datetime
from tkinter import scrolledtext, ttk

import cv2
import numpy as np

# Configurações de rede
HOST_IP = "0.0.0.0"  # Escuta em todas as interfaces
PORT = 9999  # Porta do servidor UDP

# Configurações do buffer
BUFFER_SIZE = 65536  # Tamanho do buffer UDP

# Configuração da interface
VIDEO_WIDTH = 854
VIDEO_HEIGHT = 480
CONSOLE_WIDTH = 500
CONSOLE_HEIGHT = 600

# Fila para comunicação entre threads
log_queue = queue.Queue()
status_queue = queue.Queue()

# Classes de nível de log
LOG_INFO = "INFO"
LOG_ERROR = "ERROR"
LOG_WARNING = "WARNING"


class ConsoleWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Console de Controle do Carrinho")
        self.root.geometry(f"{CONSOLE_WIDTH}x{CONSOLE_HEIGHT}")

        self.create_widgets()
        self.auto_scroll = True
        self.paused = False

        # Configurar fechamento adequado
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Estatísticas
        self.status_vars = {
            "connection": tk.StringVar(value="Desconectado"),
            "fps": tk.StringVar(value="0.0"),
            "frame_size": tk.StringVar(value="0 KB"),
            "packets": tk.StringVar(value="0"),
            "data": tk.StringVar(value="0 MB"),
        }

    def create_widgets(self):
        # Frame para estatísticas
        stats_frame = ttk.LabelFrame(self.root, text="Estatísticas")
        stats_frame.pack(fill=tk.X, padx=10, pady=5)

        # Variáveis de status
        self.connection_var = tk.StringVar(value="Desconectado")
        self.fps_var = tk.StringVar(value="0.0")
        self.frame_size_var = tk.StringVar(value="0 KB")
        self.packets_var = tk.StringVar(value="0")
        self.data_var = tk.StringVar(value="0 MB")

        # Grid de estatísticas
        ttk.Label(stats_frame, text="Status:").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(stats_frame, textvariable=self.connection_var).grid(
            row=0, column=1, sticky=tk.W, padx=5, pady=2
        )

        ttk.Label(stats_frame, text="FPS:").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(stats_frame, textvariable=self.fps_var).grid(
            row=1, column=1, sticky=tk.W, padx=5, pady=2
        )

        ttk.Label(stats_frame, text="Frame:").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(stats_frame, textvariable=self.frame_size_var).grid(
            row=2, column=1, sticky=tk.W, padx=5, pady=2
        )

        ttk.Label(stats_frame, text="Pacotes:").grid(
            row=1, column=2, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(stats_frame, textvariable=self.packets_var).grid(
            row=1, column=3, sticky=tk.W, padx=5, pady=2
        )

        ttk.Label(stats_frame, text="Dados:").grid(
            row=2, column=2, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(stats_frame, textvariable=self.data_var).grid(
            row=2, column=3, sticky=tk.W, padx=5, pady=2
        )

        # Frame para área de controles futuros
        control_frame = ttk.LabelFrame(self.root, text="Controles")
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        ttk.Label(control_frame, text="Área reservada para controles futuros").pack(
            pady=10
        )

        # Frame para console de log
        log_frame = ttk.LabelFrame(self.root, text="Console de Log")
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Botões de controle
        btn_frame = ttk.Frame(log_frame)
        btn_frame.pack(fill=tk.X)

        self.pause_btn = ttk.Button(btn_frame, text="Pausar", command=self.toggle_pause)
        self.pause_btn.pack(side=tk.LEFT, padx=5, pady=5)

        self.clear_btn = ttk.Button(btn_frame, text="Limpar", command=self.clear_log)
        self.clear_btn.pack(side=tk.LEFT, padx=5, pady=5)

        self.autoscroll_var = tk.BooleanVar(value=True)
        self.autoscroll_cb = ttk.Checkbutton(
            btn_frame,
            text="Auto-rolagem",
            variable=self.autoscroll_var,
            command=self.toggle_autoscroll,
        )
        self.autoscroll_cb.pack(side=tk.LEFT, padx=5, pady=5)

        # Área de texto com scroll
        self.log_text = scrolledtext.ScrolledText(log_frame, wrap=tk.WORD)
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configurar tags para colorir diferentes tipos de mensagens
        self.log_text.tag_configure("INFO", foreground="white")
        self.log_text.tag_configure("ERROR", foreground="red")
        self.log_text.tag_configure("WARNING", foreground="orange")
        self.log_text.tag_configure("TIMESTAMP", foreground="gray")

    def log(self, level, message):
        """Adiciona uma mensagem ao log"""
        if self.paused:
            return

        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_text.insert(tk.END, f"[{timestamp}] ", "TIMESTAMP")
        self.log_text.insert(tk.END, f"[{level}] ", level)
        self.log_text.insert(tk.END, f"{message}\n", level)

        if self.autoscroll_var.get():
            self.log_text.see(tk.END)

    def update_status(self, status_dict):
        """Atualiza as estatísticas exibidas"""
        if "connection" in status_dict:
            self.connection_var.set(status_dict["connection"])
        if "fps" in status_dict:
            self.fps_var.set(f"{status_dict['fps']:.1f}")
        if "frame_size" in status_dict:
            self.frame_size_var.set(f"{status_dict['frame_size']:.1f} KB")
        if "packets" in status_dict:
            self.packets_var.set(str(status_dict["packets"]))
        if "data" in status_dict:
            self.data_var.set(f"{status_dict['data']:.2f} MB")

    def toggle_pause(self):
        """Pausa ou continua a exibição de logs"""
        self.paused = not self.paused
        self.pause_btn.config(text="Continuar" if self.paused else "Pausar")

    def clear_log(self):
        """Limpa o conteúdo do log"""
        self.log_text.delete(1.0, tk.END)

    def toggle_autoscroll(self):
        """Ativa/desativa rolagem automática"""
        self.auto_scroll = self.autoscroll_var.get()

    def on_closing(self):
        """Manipulador para quando a janela é fechada"""
        self.root.quit()


def update_console(console_window):
    """Função para atualizar o console a partir das filas"""
    try:
        # Processar mensagens de log
        while not log_queue.empty():
            level, message = log_queue.get_nowait()
            console_window.log(level, message)

        # Processar atualizações de status
        while not status_queue.empty():
            status_dict = status_queue.get_nowait()
            console_window.update_status(status_dict)

        # Agendar próxima atualização
        console_window.root.after(100, update_console, console_window)
    except Exception as e:
        print(f"Erro ao atualizar console: {e}")
        console_window.root.after(100, update_console, console_window)


def console_thread_function():
    """Função principal para a thread do console"""
    root = tk.Tk()
    console = ConsoleWindow(root)

    # Configurar atualização periódica
    root.after(100, update_console, console)

    # Iniciar o loop principal do Tkinter
    root.mainloop()


def video_thread_function():
    """Função principal para o processamento de vídeo e rede"""
    # Cria o socket UDP
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    # Aumenta o buffer de recepção
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, BUFFER_SIZE * 2)
    actual_buffer = server_socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)

    log_queue.put((LOG_INFO, "Sistema iniciado"))
    log_queue.put((LOG_INFO, f"Escutando na porta UDP {PORT}"))
    log_queue.put((LOG_INFO, f"Buffer: {actual_buffer // 1024} KB"))
    log_queue.put((LOG_INFO, "Aguardando conexão do Raspberry Pi..."))

    # Pequeno timeout para não bloquear para sempre
    server_socket.settimeout(0.5)

    # Vincula o socket à porta
    server_socket.bind((HOST_IP, PORT))

    # Cria a janela para exibição de vídeo
    cv2.namedWindow("Video do Carrinho", cv2.WINDOW_NORMAL)
    cv2.resizeWindow("Video do Carrinho", VIDEO_WIDTH, VIDEO_HEIGHT)

    # Variáveis para estatísticas
    frames_received = 0
    last_time = time.time()
    last_frame = None  # Guarda o último frame para mostrar em caso de problemas

    # Estatísticas
    fps = 0
    frame_size = 0
    packet_count = 0
    total_bytes = 0
    connection_status = "Desconectado"
    last_packet_time = time.time()
    connected_addr = None

    try:
        while True:
            # Verificar se ainda estamos conectados
            if connected_addr and time.time() - last_packet_time > 3.0:
                log_queue.put((LOG_WARNING, f"Conexão perdida com {connected_addr}"))
                connection_status = "Desconectado"
                connected_addr = None
                # Atualiza o status no console
                status_queue.put({"connection": connection_status})

            try:
                # Recebe pacote
                packet, addr = server_socket.recvfrom(BUFFER_SIZE)

                # Atualiza status de conexão
                if connected_addr != addr:
                    connected_addr = addr
                    connection_status = f"Conectado a {addr[0]}:{addr[1]}"
                    log_queue.put(
                        (LOG_INFO, f"Conexão estabelecida com {addr[0]}:{addr[1]}")
                    )
                    # Atualiza o status no console
                    status_queue.put({"connection": connection_status})

                last_packet_time = time.time()
                packet_count += 1
                total_bytes += len(packet)

                # Atualiza o status no console periodicamente
                status_queue.put(
                    {"packets": packet_count, "data": total_bytes / 1024 / 1024}
                )

                # Verifica se é um sinal de término (tamanho 1 byte)
                if len(packet) == 1 and packet[0] == 1:
                    log_queue.put((LOG_INFO, "Sinal de encerramento recebido"))
                    break

                # Verifica se o pacote tem pelo menos 4 bytes (tamanho)
                if len(packet) >= 4:
                    try:
                        # Os primeiros 4 bytes são o tamanho
                        frame_size = struct.unpack("<i", packet[:4])[0]
                        frame_data = packet[4:]

                        # Verifica se o tamanho parece válido
                        if frame_size <= 0 or frame_size > 1000000:  # Limitado a 1MB
                            log_queue.put(
                                (LOG_ERROR, f"Tamanho inválido: {frame_size}")
                            )
                            continue

                        # Decodifica o frame JPEG
                        frame_array = np.frombuffer(frame_data, dtype=np.uint8)
                        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

                        if frame is None:
                            log_queue.put((LOG_ERROR, "Erro ao decodificar frame"))

                            # Tentativa alternativa: ajuste o offset se os primeiros bytes parecerem JPEG
                            for i in range(min(20, len(frame_data))):
                                if frame_data[i : i + 2] == b"\xff\xd8":
                                    log_queue.put(
                                        (
                                            LOG_INFO,
                                            f"Encontrado início JPEG no offset {i}",
                                        )
                                    )
                                    frame_array = np.frombuffer(
                                        frame_data[i:], dtype=np.uint8
                                    )
                                    frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
                                    if frame is not None:
                                        break

                            if frame is None:
                                log_queue.put((LOG_ERROR, "Decodificação falhou"))
                                continue

                        # Exibe o frame
                        cv2.imshow("Video do Carrinho", frame)

                        # Armazena o último frame bem-sucedido
                        last_frame = frame.copy()

                        # Atualiza estatísticas
                        frames_received += 1
                        current_time = time.time()
                        elapsed = current_time - last_time

                        if elapsed >= 1.0:
                            fps = frames_received / elapsed
                            frames_received = 0
                            last_time = current_time

                            # Atualiza os logs e estatísticas
                            log_queue.put(
                                (
                                    LOG_INFO,
                                    f"FPS: {fps:.1f}, Tamanho: {len(frame_data)/1024:.1f} KB",
                                )
                            )
                            status_queue.put(
                                {"fps": fps, "frame_size": len(frame_data) / 1024}
                            )

                    except Exception as e:
                        log_queue.put((LOG_ERROR, f"Erro ao processar frame: {e}"))

                        # Se tivermos um frame anterior, mostramos ele
                        if last_frame is not None:
                            cv2.imshow("Video do Carrinho", last_frame)

            except socket.timeout:
                # Timeout é normal, não é preciso logar toda vez
                pass

            except Exception as e:
                log_queue.put((LOG_ERROR, f"Erro de rede: {e}"))
                time.sleep(0.1)  # Pausa para evitar loop infinito em caso de erro

            # Verifica se o usuário pressionou ESC
            key = cv2.waitKey(1) & 0xFF
            if key == 27:  # ESC
                log_queue.put((LOG_INFO, "Encerramento solicitado pelo usuário"))
                break

    except KeyboardInterrupt:
        log_queue.put((LOG_INFO, "Recepção interrompida pelo usuário"))
    finally:
        # Libera recursos
        server_socket.close()
        cv2.destroyAllWindows()
        log_queue.put((LOG_INFO, "Cliente encerrado"))
        # Espera um pouco para garantir que as mensagens foram processadas
        time.sleep(0.5)
        sys.exit(0)


def main():
    # Iniciar a thread do console
    console_thread = threading.Thread(target=console_thread_function)
    console_thread.daemon = True
    console_thread.start()

    # Iniciar a thread de vídeo
    video_thread = threading.Thread(target=video_thread_function)
    video_thread.daemon = True
    video_thread.start()

    # Aguardar as threads terminarem
    try:
        console_thread.join()
        video_thread.join()
    except KeyboardInterrupt:
        print("Programa encerrado pelo usuário")


if __name__ == "__main__":
    main()
