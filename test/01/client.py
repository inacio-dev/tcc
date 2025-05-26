#!/usr/bin/env python3
# Cliente UDP com interface de vídeo e dados de sensores
# Recebe frames + dados de sensores do Raspberry Pi

import json
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
BUFFER_SIZE = 131072  # 128KB para comportar frame + dados de sensor

# Configuração da interface
VIDEO_WIDTH = 854
VIDEO_HEIGHT = 480
CONSOLE_WIDTH = 600
CONSOLE_HEIGHT = 700

# Filas para comunicação entre threads
log_queue = queue.Queue()
status_queue = queue.Queue()
sensor_queue = queue.Queue()

# Classes de nível de log
LOG_INFO = "INFO"
LOG_ERROR = "ERROR"
LOG_WARNING = "WARNING"


class ConsoleWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Console de Controle do Carrinho")
        self.root.geometry(f"{CONSOLE_WIDTH}x{CONSOLE_HEIGHT}")

        # MOVER ESTAS VARIÁVEIS PARA ANTES DE create_widgets()
        # Variáveis de status da conexão
        self.connection_var = tk.StringVar(value="Desconectado")
        self.fps_var = tk.StringVar(value="0.0")
        self.frame_size_var = tk.StringVar(value="0 KB")
        self.packets_var = tk.StringVar(value="0")
        self.data_var = tk.StringVar(value="0 MB")

        # Variáveis dos sensores
        self.sensor_vars = {
            "accel_x": tk.StringVar(value="0.000"),
            "accel_y": tk.StringVar(value="0.000"),
            "accel_z": tk.StringVar(value="0.000"),
            "gyro_x": tk.StringVar(value="0.000"),
            "gyro_y": tk.StringVar(value="0.000"),
            "gyro_z": tk.StringVar(value="0.000"),
            "velocidade": tk.StringVar(value="0.0"),
            "steering_angle": tk.StringVar(value="0.0"),
            "bateria_nivel": tk.StringVar(value="0.0"),
            "temperatura": tk.StringVar(value="0.0"),
            "timestamp": tk.StringVar(value="0"),
            "frame_count": tk.StringVar(value="0"),
        }

        self.create_widgets()  # AGORA PODE USAR AS VARIÁVEIS
        self.auto_scroll = True
        self.paused = False

        # Configurar fechamento adequado
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

    def create_widgets(self):
        # Frame para estatísticas de conexão
        stats_frame = ttk.LabelFrame(self.root, text="Status da Conexão")
        stats_frame.pack(fill=tk.X, padx=10, pady=5)

        # Grid de estatísticas de conexão
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

        # Frame para dados de sensores
        sensor_frame = ttk.LabelFrame(self.root, text="Dados dos Sensores")
        sensor_frame.pack(fill=tk.X, padx=10, pady=5)

        # Acelerômetro
        accel_subframe = ttk.LabelFrame(sensor_frame, text="Acelerômetro (m/s²)")
        accel_subframe.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(accel_subframe, text="X:").grid(row=0, column=0, sticky=tk.W, padx=2)
        ttk.Label(accel_subframe, textvariable=self.sensor_vars["accel_x"]).grid(
            row=0, column=1, sticky=tk.W, padx=2
        )

        ttk.Label(accel_subframe, text="Y:").grid(row=0, column=2, sticky=tk.W, padx=2)
        ttk.Label(accel_subframe, textvariable=self.sensor_vars["accel_y"]).grid(
            row=0, column=3, sticky=tk.W, padx=2
        )

        ttk.Label(accel_subframe, text="Z:").grid(row=0, column=4, sticky=tk.W, padx=2)
        ttk.Label(accel_subframe, textvariable=self.sensor_vars["accel_z"]).grid(
            row=0, column=5, sticky=tk.W, padx=2
        )

        # Giroscópio
        gyro_subframe = ttk.LabelFrame(sensor_frame, text="Giroscópio (°/s)")
        gyro_subframe.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(gyro_subframe, text="X:").grid(row=0, column=0, sticky=tk.W, padx=2)
        ttk.Label(gyro_subframe, textvariable=self.sensor_vars["gyro_x"]).grid(
            row=0, column=1, sticky=tk.W, padx=2
        )

        ttk.Label(gyro_subframe, text="Y:").grid(row=0, column=2, sticky=tk.W, padx=2)
        ttk.Label(gyro_subframe, textvariable=self.sensor_vars["gyro_y"]).grid(
            row=0, column=3, sticky=tk.W, padx=2
        )

        ttk.Label(gyro_subframe, text="Z:").grid(row=0, column=4, sticky=tk.W, padx=2)
        ttk.Label(gyro_subframe, textvariable=self.sensor_vars["gyro_z"]).grid(
            row=0, column=5, sticky=tk.W, padx=2
        )

        # Dados do veículo
        vehicle_subframe = ttk.LabelFrame(sensor_frame, text="Dados do Veículo")
        vehicle_subframe.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(vehicle_subframe, text="Velocidade (km/h):").grid(
            row=0, column=0, sticky=tk.W, padx=2
        )
        ttk.Label(vehicle_subframe, textvariable=self.sensor_vars["velocidade"]).grid(
            row=0, column=1, sticky=tk.W, padx=2
        )

        ttk.Label(vehicle_subframe, text="Direção (°):").grid(
            row=0, column=2, sticky=tk.W, padx=2
        )
        ttk.Label(
            vehicle_subframe, textvariable=self.sensor_vars["steering_angle"]
        ).grid(row=0, column=3, sticky=tk.W, padx=2)

        # Status do sistema
        system_subframe = ttk.LabelFrame(sensor_frame, text="Status do Sistema")
        system_subframe.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(system_subframe, text="Bateria (%):").grid(
            row=0, column=0, sticky=tk.W, padx=2
        )
        ttk.Label(system_subframe, textvariable=self.sensor_vars["bateria_nivel"]).grid(
            row=0, column=1, sticky=tk.W, padx=2
        )

        ttk.Label(system_subframe, text="Temperatura (°C):").grid(
            row=0, column=2, sticky=tk.W, padx=2
        )
        ttk.Label(system_subframe, textvariable=self.sensor_vars["temperatura"]).grid(
            row=0, column=3, sticky=tk.W, padx=2
        )

        ttk.Label(system_subframe, text="Frames:").grid(
            row=1, column=0, sticky=tk.W, padx=2
        )
        ttk.Label(system_subframe, textvariable=self.sensor_vars["frame_count"]).grid(
            row=1, column=1, sticky=tk.W, padx=2
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
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            bg="black",  # Fundo preto
            fg="white",  # Texto padrão branco
            insertbackground="white",  # Cursor branco
            selectbackground="darkblue",  # Seleção azul escuro
            selectforeground="white",  # Texto selecionado branco
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configurar tags para colorir diferentes tipos de mensagens
        self.log_text.tag_configure(
            "INFO", foreground="lightgreen"
        )  # Verde claro para INFO
        self.log_text.tag_configure("ERROR", foreground="red")  # Vermelho para ERROR
        self.log_text.tag_configure(
            "WARNING", foreground="yellow"
        )  # Amarelo para WARNING
        self.log_text.tag_configure(
            "TIMESTAMP", foreground="cyan"
        )  # Ciano para timestamp

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

    def update_sensors(self, sensor_dict):
        """Atualiza os dados dos sensores exibidos"""
        for key, value in sensor_dict.items():
            if key in self.sensor_vars:
                if isinstance(value, float):
                    self.sensor_vars[key].set(f"{value:.3f}")
                else:
                    self.sensor_vars[key].set(str(value))

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

        # Processar dados de sensores
        while not sensor_queue.empty():
            sensor_dict = sensor_queue.get_nowait()
            console_window.update_sensors(sensor_dict)

        # Agendar próxima atualização
        console_window.root.after(50, update_console, console_window)
    except Exception as e:
        print(f"Erro ao atualizar console: {e}")
        console_window.root.after(50, update_console, console_window)


def console_thread_function():
    """Função principal para a thread do console"""
    root = tk.Tk()
    console = ConsoleWindow(root)

    # Configurar atualização periódica
    root.after(50, update_console, console)

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
                    status_queue.put({"connection": connection_status})

                last_packet_time = time.time()
                packet_count += 1
                total_bytes += len(packet)

                # Atualiza o status no console periodicamente
                status_queue.put(
                    {"packets": packet_count, "data": total_bytes / 1024 / 1024}
                )

                # Verifica se é um sinal de término (pacote com tamanhos zero)
                if (
                    len(packet) == 8
                ):  # 4 bytes para frame_size + 4 bytes para sensor_size
                    frame_size_check, sensor_size_check = struct.unpack(
                        "<II", packet[:8]
                    )
                    if frame_size_check == 0 and sensor_size_check == 0:
                        log_queue.put((LOG_INFO, "Sinal de encerramento recebido"))
                        break

                # Verifica se o pacote tem pelo menos 8 bytes (4 + 4 para os tamanhos)
                if len(packet) >= 8:
                    try:
                        # Os primeiros 8 bytes são os tamanhos
                        frame_size, sensor_size = struct.unpack("<II", packet[:8])

                        # Verifica se os tamanhos parecem válidos
                        if (
                            frame_size <= 0 or frame_size > 1000000
                        ):  # Limitado a 1MB para frame
                            log_queue.put(
                                (LOG_ERROR, f"Tamanho de frame inválido: {frame_size}")
                            )
                            continue

                        if (
                            sensor_size < 0 or sensor_size > 10000
                        ):  # Limitado a 10KB para dados de sensor
                            log_queue.put(
                                (
                                    LOG_ERROR,
                                    f"Tamanho de sensor inválido: {sensor_size}",
                                )
                            )
                            continue

                        # Calcula as posições dos dados
                        frame_start = 8
                        frame_end = frame_start + frame_size
                        sensor_start = frame_end
                        sensor_end = sensor_start + sensor_size

                        # Verifica se o pacote tem o tamanho esperado
                        expected_size = 8 + frame_size + sensor_size
                        if len(packet) < expected_size:
                            log_queue.put(
                                (
                                    LOG_ERROR,
                                    f"Pacote incompleto: {len(packet)} < {expected_size}",
                                )
                            )
                            continue

                        # Extrai os dados do frame
                        frame_data = packet[frame_start:frame_end]

                        # Extrai os dados dos sensores
                        sensor_data = packet[sensor_start:sensor_end]

                        # Processa o frame de vídeo
                        frame_array = np.frombuffer(frame_data, dtype=np.uint8)
                        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

                        if frame is None:
                            log_queue.put((LOG_ERROR, "Erro ao decodificar frame"))
                            # Se tivermos um frame anterior, mostramos ele
                            if last_frame is not None:
                                cv2.imshow("Video do Carrinho", last_frame)
                            continue

                        # Exibe o frame
                        cv2.imshow("Video do Carrinho", frame)
                        # Armazena o último frame bem-sucedido
                        last_frame = frame.copy()

                        # Processa os dados dos sensores
                        if sensor_size > 0:
                            try:
                                sensor_json = sensor_data.decode("utf-8")
                                sensor_dict = json.loads(sensor_json)

                                # Envia dados dos sensores para a interface
                                sensor_queue.put(sensor_dict)

                            except (json.JSONDecodeError, UnicodeDecodeError) as e:
                                log_queue.put(
                                    (
                                        LOG_ERROR,
                                        f"Erro ao decodificar dados dos sensores: {e}",
                                    )
                                )

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
                                    f"FPS: {fps:.1f}, Frame: {len(frame_data)/1024:.1f} KB, Sensores: {len(sensor_data)} bytes",
                                )
                            )
                            status_queue.put(
                                {"fps": fps, "frame_size": len(frame_data) / 1024}
                            )

                    except Exception as e:
                        log_queue.put((LOG_ERROR, f"Erro ao processar pacote: {e}"))
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
