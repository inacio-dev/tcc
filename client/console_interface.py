#!/usr/bin/env python3
"""
console_interface.py - Interface Gráfica do Console CORRIGIDA
Interface principal com dados de sensores, logs e controles

FUNCIONALIDADES:
===============
✅ Status da conexão em tempo real
✅ Dados completos do BMI160 (37+ campos)
✅ Console de logs com cores
✅ Controles de pausa/limpeza
✅ Estatísticas de rede
✅ Área para controles futuros
✅ Interface responsiva e amigável

DADOS EXIBIDOS:
==============
- Dados raw BMI160 (LSB)
- Dados físicos (m/s², °/s)
- Forças G calculadas
- Eventos detectados
- Force feedback
- Status do sistema
- Dados derivados (velocidade, direção, bateria)
"""

import tkinter as tk
from tkinter import scrolledtext, ttk
import time
import queue
from datetime import datetime
from typing import Optional


class ConsoleInterface:
    """Interface gráfica principal do cliente F1"""

    def __init__(
        self,
        log_queue=None,
        status_queue=None,
        sensor_display=None,
        window_width=700,
        window_height=800,
    ):
        """
        Inicializa a interface do console

        Args:
            log_queue (Queue): Fila de mensagens de log
            status_queue (Queue): Fila de status de rede
            sensor_display (SensorDisplay): Processador de sensores
            window_width (int): Largura da janela
            window_height (int): Altura da janela
        """
        self.log_queue = log_queue
        self.status_queue = status_queue
        self.sensor_display = sensor_display
        self.window_width = window_width
        self.window_height = window_height

        # Tkinter
        self.root = None
        self.is_running = False

        # Controles de interface
        self.auto_scroll = True
        self.paused = False

        # Variáveis de status da conexão
        self.connection_var = None
        self.fps_var = None
        self.frame_size_var = None
        self.packets_var = None
        self.data_var = None
        self.quality_var = None

        # Variáveis dos sensores BMI160
        self.sensor_vars = {}

        # Widgets principais
        self.log_text = None
        self.pause_btn = None
        self.autoscroll_var = None

        # Atualização
        self.update_interval = 100  # ms

    def create_tkinter_variables(self):
        """Cria variáveis do Tkinter"""
        # Status da conexão
        self.connection_var = tk.StringVar(value="🔴 Desconectado")
        self.fps_var = tk.StringVar(value="0.0")
        self.frame_size_var = tk.StringVar(value="0 KB")
        self.packets_var = tk.StringVar(value="0")
        self.data_var = tk.StringVar(value="0 MB")
        self.quality_var = tk.StringVar(value="100%")

        # Dados dos sensores BMI160 - Raw (LSB)
        self.sensor_vars = {
            # Raw BMI160
            "bmi160_accel_x_raw": tk.StringVar(value="0"),
            "bmi160_accel_y_raw": tk.StringVar(value="0"),
            "bmi160_accel_z_raw": tk.StringVar(value="0"),
            "bmi160_gyro_x_raw": tk.StringVar(value="0"),
            "bmi160_gyro_y_raw": tk.StringVar(value="0"),
            "bmi160_gyro_z_raw": tk.StringVar(value="0"),
            # Dados físicos
            "accel_x": tk.StringVar(value="0.000"),
            "accel_y": tk.StringVar(value="0.000"),
            "accel_z": tk.StringVar(value="9.810"),
            "gyro_x": tk.StringVar(value="0.000"),
            "gyro_y": tk.StringVar(value="0.000"),
            "gyro_z": tk.StringVar(value="0.000"),
            # Forças G
            "g_force_frontal": tk.StringVar(value="0.000"),
            "g_force_lateral": tk.StringVar(value="0.000"),
            "g_force_vertical": tk.StringVar(value="0.000"),
            # Ângulos
            "roll_angle": tk.StringVar(value="0.0"),
            "pitch_angle": tk.StringVar(value="0.0"),
            "yaw_angle": tk.StringVar(value="0.0"),
            # Eventos (como texto)
            "events_detected": tk.StringVar(value="Nenhum"),
            # Force Feedback
            "steering_feedback": tk.StringVar(value="0.0"),
            "brake_resistance": tk.StringVar(value="0.0"),
            "seat_vibration": tk.StringVar(value="0.0"),
            "seat_tilt_x": tk.StringVar(value="0.0"),
            "seat_tilt_y": tk.StringVar(value="0.0"),
            # Dados derivados
            "velocidade": tk.StringVar(value="0.0"),
            "steering_angle": tk.StringVar(value="0.0"),
            "bateria_nivel": tk.StringVar(value="100.0"),
            "temperatura": tk.StringVar(value="25.0"),
            # Configurações
            "accel_range": tk.StringVar(value="±2g"),
            "gyro_range": tk.StringVar(value="±250°/s"),
            "sample_rate": tk.StringVar(value="100Hz"),
            # Metadados
            "timestamp": tk.StringVar(value="0"),
            "frame_count": tk.StringVar(value="0"),
            "readings_count": tk.StringVar(value="0"),
        }

    def create_main_window(self):
        """Cria janela principal"""
        self.root = tk.Tk()
        self.root.title("🏎️ F1 Car - Console de Controle")
        self.root.geometry(f"{self.window_width}x{self.window_height}")
        self.root.configure(bg="#2b2b2b")  # Tema escuro

        # Configurar fechamento
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)

        # Configurar estilo
        style = ttk.Style()
        style.theme_use("clam")

        # Cores do tema escuro
        style.configure("Dark.TLabelframe", background="#3c3c3c", foreground="white")
        style.configure("Dark.TLabel", background="#3c3c3c", foreground="white")
        style.configure("Dark.TButton", background="#4c4c4c", foreground="white")
        style.configure("Dark.TCheckbutton", background="#3c3c3c", foreground="white")

    def create_connection_status_frame(self):
        """Cria frame de status da conexão"""
        status_frame = ttk.LabelFrame(
            self.root, text="📡 Status da Conexão", style="Dark.TLabelframe"
        )
        status_frame.pack(fill=tk.X, padx=10, pady=5)

        # Linha 1: Status e FPS
        ttk.Label(status_frame, text="Status:", style="Dark.TLabel").grid(
            row=0, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(
            status_frame, textvariable=self.connection_var, style="Dark.TLabel"
        ).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(status_frame, text="FPS:", style="Dark.TLabel").grid(
            row=0, column=2, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(status_frame, textvariable=self.fps_var, style="Dark.TLabel").grid(
            row=0, column=3, sticky=tk.W, padx=5, pady=2
        )

        # Linha 2: Frame e Pacotes
        ttk.Label(status_frame, text="Frame:", style="Dark.TLabel").grid(
            row=1, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(
            status_frame, textvariable=self.frame_size_var, style="Dark.TLabel"
        ).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

        ttk.Label(status_frame, text="Pacotes:", style="Dark.TLabel").grid(
            row=1, column=2, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(
            status_frame, textvariable=self.packets_var, style="Dark.TLabel"
        ).grid(row=1, column=3, sticky=tk.W, padx=5, pady=2)

        # Linha 3: Dados e Qualidade
        ttk.Label(status_frame, text="Dados:", style="Dark.TLabel").grid(
            row=2, column=0, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(status_frame, textvariable=self.data_var, style="Dark.TLabel").grid(
            row=2, column=1, sticky=tk.W, padx=5, pady=2
        )

        ttk.Label(status_frame, text="Qualidade:", style="Dark.TLabel").grid(
            row=2, column=2, sticky=tk.W, padx=5, pady=2
        )
        ttk.Label(
            status_frame, textvariable=self.quality_var, style="Dark.TLabel"
        ).grid(row=2, column=3, sticky=tk.W, padx=5, pady=2)

    def create_bmi160_frame(self):
        """Cria frame com dados do BMI160"""
        sensor_frame = ttk.LabelFrame(
            self.root, text="🔧 Dados do BMI160", style="Dark.TLabelframe"
        )
        sensor_frame.pack(fill=tk.X, padx=10, pady=5)

        # Sub-frame para dados raw
        raw_frame = ttk.LabelFrame(
            sensor_frame, text="Raw (LSB)", style="Dark.TLabelframe"
        )
        raw_frame.pack(fill=tk.X, padx=5, pady=2)

        # Raw Acelerômetro
        ttk.Label(raw_frame, text="Accel:", style="Dark.TLabel").grid(
            row=0, column=0, padx=2
        )
        ttk.Label(raw_frame, text="X:", style="Dark.TLabel").grid(
            row=0, column=1, padx=2
        )
        ttk.Label(
            raw_frame,
            textvariable=self.sensor_vars["bmi160_accel_x_raw"],
            style="Dark.TLabel",
        ).grid(row=0, column=2, padx=2)
        ttk.Label(raw_frame, text="Y:", style="Dark.TLabel").grid(
            row=0, column=3, padx=2
        )
        ttk.Label(
            raw_frame,
            textvariable=self.sensor_vars["bmi160_accel_y_raw"],
            style="Dark.TLabel",
        ).grid(row=0, column=4, padx=2)
        ttk.Label(raw_frame, text="Z:", style="Dark.TLabel").grid(
            row=0, column=5, padx=2
        )
        ttk.Label(
            raw_frame,
            textvariable=self.sensor_vars["bmi160_accel_z_raw"],
            style="Dark.TLabel",
        ).grid(row=0, column=6, padx=2)

        # Raw Giroscópio
        ttk.Label(raw_frame, text="Gyro:", style="Dark.TLabel").grid(
            row=1, column=0, padx=2
        )
        ttk.Label(raw_frame, text="X:", style="Dark.TLabel").grid(
            row=1, column=1, padx=2
        )
        ttk.Label(
            raw_frame,
            textvariable=self.sensor_vars["bmi160_gyro_x_raw"],
            style="Dark.TLabel",
        ).grid(row=1, column=2, padx=2)
        ttk.Label(raw_frame, text="Y:", style="Dark.TLabel").grid(
            row=1, column=3, padx=2
        )
        ttk.Label(
            raw_frame,
            textvariable=self.sensor_vars["bmi160_gyro_y_raw"],
            style="Dark.TLabel",
        ).grid(row=1, column=4, padx=2)
        ttk.Label(raw_frame, text="Z:", style="Dark.TLabel").grid(
            row=1, column=5, padx=2
        )
        ttk.Label(
            raw_frame,
            textvariable=self.sensor_vars["bmi160_gyro_z_raw"],
            style="Dark.TLabel",
        ).grid(row=1, column=6, padx=2)

        # Sub-frame para dados físicos
        physical_frame = ttk.LabelFrame(
            sensor_frame, text="Físicos", style="Dark.TLabelframe"
        )
        physical_frame.pack(fill=tk.X, padx=5, pady=2)

        # Acelerômetro físico (m/s²)
        ttk.Label(physical_frame, text="Accel (m/s²):", style="Dark.TLabel").grid(
            row=0, column=0, padx=2
        )
        ttk.Label(physical_frame, text="X:", style="Dark.TLabel").grid(
            row=0, column=1, padx=2
        )
        ttk.Label(
            physical_frame,
            textvariable=self.sensor_vars["accel_x"],
            style="Dark.TLabel",
        ).grid(row=0, column=2, padx=2)
        ttk.Label(physical_frame, text="Y:", style="Dark.TLabel").grid(
            row=0, column=3, padx=2
        )
        ttk.Label(
            physical_frame,
            textvariable=self.sensor_vars["accel_y"],
            style="Dark.TLabel",
        ).grid(row=0, column=4, padx=2)
        ttk.Label(physical_frame, text="Z:", style="Dark.TLabel").grid(
            row=0, column=5, padx=2
        )
        ttk.Label(
            physical_frame,
            textvariable=self.sensor_vars["accel_z"],
            style="Dark.TLabel",
        ).grid(row=0, column=6, padx=2)

        # Giroscópio físico (°/s)
        ttk.Label(physical_frame, text="Gyro (°/s):", style="Dark.TLabel").grid(
            row=1, column=0, padx=2
        )
        ttk.Label(physical_frame, text="X:", style="Dark.TLabel").grid(
            row=1, column=1, padx=2
        )
        ttk.Label(
            physical_frame, textvariable=self.sensor_vars["gyro_x"], style="Dark.TLabel"
        ).grid(row=1, column=2, padx=2)
        ttk.Label(physical_frame, text="Y:", style="Dark.TLabel").grid(
            row=1, column=3, padx=2
        )
        ttk.Label(
            physical_frame, textvariable=self.sensor_vars["gyro_y"], style="Dark.TLabel"
        ).grid(row=1, column=4, padx=2)
        ttk.Label(physical_frame, text="Z:", style="Dark.TLabel").grid(
            row=1, column=5, padx=2
        )
        ttk.Label(
            physical_frame, textvariable=self.sensor_vars["gyro_z"], style="Dark.TLabel"
        ).grid(row=1, column=6, padx=2)

        # Sub-frame para forças G
        gforce_frame = ttk.LabelFrame(
            sensor_frame, text="Forças G", style="Dark.TLabelframe"
        )
        gforce_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(gforce_frame, text="Frontal:", style="Dark.TLabel").grid(
            row=0, column=0, padx=2
        )
        ttk.Label(
            gforce_frame,
            textvariable=self.sensor_vars["g_force_frontal"],
            style="Dark.TLabel",
        ).grid(row=0, column=1, padx=2)
        ttk.Label(gforce_frame, text="g", style="Dark.TLabel").grid(
            row=0, column=2, padx=2
        )

        ttk.Label(gforce_frame, text="Lateral:", style="Dark.TLabel").grid(
            row=0, column=3, padx=2
        )
        ttk.Label(
            gforce_frame,
            textvariable=self.sensor_vars["g_force_lateral"],
            style="Dark.TLabel",
        ).grid(row=0, column=4, padx=2)
        ttk.Label(gforce_frame, text="g", style="Dark.TLabel").grid(
            row=0, column=5, padx=2
        )

        ttk.Label(gforce_frame, text="Vertical:", style="Dark.TLabel").grid(
            row=0, column=6, padx=2
        )
        ttk.Label(
            gforce_frame,
            textvariable=self.sensor_vars["g_force_vertical"],
            style="Dark.TLabel",
        ).grid(row=0, column=7, padx=2)
        ttk.Label(gforce_frame, text="g", style="Dark.TLabel").grid(
            row=0, column=8, padx=2
        )

    def create_vehicle_data_frame(self):
        """Cria frame com dados do veículo"""
        vehicle_frame = ttk.LabelFrame(
            self.root, text="🏎️ Dados do Veículo", style="Dark.TLabelframe"
        )
        vehicle_frame.pack(fill=tk.X, padx=10, pady=5)

        # Linha 1: Velocidade e Direção
        ttk.Label(vehicle_frame, text="Velocidade:", style="Dark.TLabel").grid(
            row=0, column=0, padx=5
        )
        ttk.Label(
            vehicle_frame,
            textvariable=self.sensor_vars["velocidade"],
            style="Dark.TLabel",
        ).grid(row=0, column=1, padx=5)
        ttk.Label(vehicle_frame, text="km/h", style="Dark.TLabel").grid(
            row=0, column=2, padx=5
        )

        ttk.Label(vehicle_frame, text="Direção:", style="Dark.TLabel").grid(
            row=0, column=3, padx=5
        )
        ttk.Label(
            vehicle_frame,
            textvariable=self.sensor_vars["steering_angle"],
            style="Dark.TLabel",
        ).grid(row=0, column=4, padx=5)
        ttk.Label(vehicle_frame, text="°", style="Dark.TLabel").grid(
            row=0, column=5, padx=5
        )

        # Linha 2: Bateria e Temperatura
        ttk.Label(vehicle_frame, text="Bateria:", style="Dark.TLabel").grid(
            row=1, column=0, padx=5
        )
        ttk.Label(
            vehicle_frame,
            textvariable=self.sensor_vars["bateria_nivel"],
            style="Dark.TLabel",
        ).grid(row=1, column=1, padx=5)
        ttk.Label(vehicle_frame, text="%", style="Dark.TLabel").grid(
            row=1, column=2, padx=5
        )

        ttk.Label(vehicle_frame, text="Temperatura:", style="Dark.TLabel").grid(
            row=1, column=3, padx=5
        )
        ttk.Label(
            vehicle_frame,
            textvariable=self.sensor_vars["temperatura"],
            style="Dark.TLabel",
        ).grid(row=1, column=4, padx=5)
        ttk.Label(vehicle_frame, text="°C", style="Dark.TLabel").grid(
            row=1, column=5, padx=5
        )

        # Linha 3: Eventos detectados
        ttk.Label(vehicle_frame, text="Eventos:", style="Dark.TLabel").grid(
            row=2, column=0, padx=5
        )
        ttk.Label(
            vehicle_frame,
            textvariable=self.sensor_vars["events_detected"],
            style="Dark.TLabel",
        ).grid(row=2, column=1, columnspan=5, sticky=tk.W, padx=5)

    def create_force_feedback_frame(self):
        """Cria frame com dados do force feedback"""
        ff_frame = ttk.LabelFrame(
            self.root, text="🎮 Force Feedback", style="Dark.TLabelframe"
        )
        ff_frame.pack(fill=tk.X, padx=10, pady=5)

        # Linha 1: Volante e Freio
        ttk.Label(ff_frame, text="Volante:", style="Dark.TLabel").grid(
            row=0, column=0, padx=5
        )
        ttk.Label(
            ff_frame,
            textvariable=self.sensor_vars["steering_feedback"],
            style="Dark.TLabel",
        ).grid(row=0, column=1, padx=5)
        ttk.Label(ff_frame, text="%", style="Dark.TLabel").grid(row=0, column=2, padx=5)

        ttk.Label(ff_frame, text="Freio:", style="Dark.TLabel").grid(
            row=0, column=3, padx=5
        )
        ttk.Label(
            ff_frame,
            textvariable=self.sensor_vars["brake_resistance"],
            style="Dark.TLabel",
        ).grid(row=0, column=4, padx=5)
        ttk.Label(ff_frame, text="%", style="Dark.TLabel").grid(row=0, column=5, padx=5)

        # Linha 2: Vibração e Inclinação
        ttk.Label(ff_frame, text="Vibração:", style="Dark.TLabel").grid(
            row=1, column=0, padx=5
        )
        ttk.Label(
            ff_frame,
            textvariable=self.sensor_vars["seat_vibration"],
            style="Dark.TLabel",
        ).grid(row=1, column=1, padx=5)
        ttk.Label(ff_frame, text="%", style="Dark.TLabel").grid(row=1, column=2, padx=5)

        ttk.Label(ff_frame, text="Inclinação X:", style="Dark.TLabel").grid(
            row=1, column=3, padx=5
        )
        ttk.Label(
            ff_frame, textvariable=self.sensor_vars["seat_tilt_x"], style="Dark.TLabel"
        ).grid(row=1, column=4, padx=5)
        ttk.Label(ff_frame, text="°", style="Dark.TLabel").grid(row=1, column=5, padx=5)

    def create_controls_frame(self):
        """Cria frame de controles"""
        control_frame = ttk.LabelFrame(
            self.root, text="🎛️ Controles", style="Dark.TLabelframe"
        )
        control_frame.pack(fill=tk.X, padx=10, pady=5)

        # Botões de controle
        ttk.Button(
            control_frame,
            text="Reset Stats",
            command=self.reset_statistics,
            style="Dark.TButton",
        ).pack(side=tk.LEFT, padx=5, pady=5)

        ttk.Button(
            control_frame,
            text="Export Data",
            command=self.export_data,
            style="Dark.TButton",
        ).pack(side=tk.LEFT, padx=5, pady=5)

        # Status das configurações
        ttk.Label(control_frame, text="Config:", style="Dark.TLabel").pack(
            side=tk.LEFT, padx=10
        )
        ttk.Label(
            control_frame,
            textvariable=self.sensor_vars["accel_range"],
            style="Dark.TLabel",
        ).pack(side=tk.LEFT, padx=2)
        ttk.Label(
            control_frame,
            textvariable=self.sensor_vars["gyro_range"],
            style="Dark.TLabel",
        ).pack(side=tk.LEFT, padx=2)
        ttk.Label(
            control_frame,
            textvariable=self.sensor_vars["sample_rate"],
            style="Dark.TLabel",
        ).pack(side=tk.LEFT, padx=2)

    def create_log_frame(self):
        """Cria frame do console de log"""
        log_frame = ttk.LabelFrame(
            self.root, text="📋 Console de Log", style="Dark.TLabelframe"
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        # Botões de controle do log
        btn_frame = tk.Frame(log_frame, bg="#3c3c3c")
        btn_frame.pack(fill=tk.X, padx=5, pady=2)

        self.pause_btn = ttk.Button(
            btn_frame, text="⏸️ Pausar", command=self.toggle_pause, style="Dark.TButton"
        )
        self.pause_btn.pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame, text="🗑️ Limpar", command=self.clear_log, style="Dark.TButton"
        ).pack(side=tk.LEFT, padx=5)

        self.autoscroll_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            btn_frame,
            text="Auto-rolagem",
            variable=self.autoscroll_var,
            command=self.toggle_autoscroll,
            style="Dark.TCheckbutton",
        ).pack(side=tk.LEFT, padx=5)

        # Área de texto do log
        self.log_text = scrolledtext.ScrolledText(
            log_frame,
            wrap=tk.WORD,
            bg="#1e1e1e",  # Fundo preto
            fg="#ffffff",  # Texto branco
            insertbackground="#ffffff",  # Cursor branco
            selectbackground="#0078d4",  # Seleção azul
            selectforeground="#ffffff",  # Texto selecionado branco
            font=("Consolas", 10),  # Fonte monospace
        )
        self.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Configurar tags para cores
        self.log_text.tag_configure("INFO", foreground="#00ff00")  # Verde
        self.log_text.tag_configure("ERROR", foreground="#ff0000")  # Vermelho
        self.log_text.tag_configure("WARNING", foreground="#ffff00")  # Amarelo
        self.log_text.tag_configure("TIMESTAMP", foreground="#808080")  # Cinza

    def create_widgets(self):
        """Cria todos os widgets da interface"""
        self.create_connection_status_frame()
        self.create_bmi160_frame()
        self.create_vehicle_data_frame()
        self.create_force_feedback_frame()
        self.create_controls_frame()
        self.create_log_frame()

    def log(self, level, message):
        """Adiciona mensagem ao log"""
        if self.paused:
            return

        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Inclui milissegundos

        # Adiciona ao log
        self.log_text.insert(tk.END, f"[{timestamp}] ", "TIMESTAMP")
        self.log_text.insert(tk.END, f"[{level}] ", level)
        self.log_text.insert(tk.END, f"{message}\n", level)

        # Auto-scroll se habilitado
        if self.autoscroll_var.get():
            self.log_text.see(tk.END)

    def update_connection_status(self, status_dict):
        """Atualiza status de conexão"""
        if "connection" in status_dict:
            connection_text = status_dict["connection"]
            if "Conectado" in connection_text:
                self.connection_var.set(f"🟢 {connection_text}")
            else:
                self.connection_var.set(f"🔴 {connection_text}")

        if "fps" in status_dict:
            self.fps_var.set(f"{status_dict['fps']:.1f}")

        if "frame_size" in status_dict:
            self.frame_size_var.set(f"{status_dict['frame_size']:.1f} KB")

        if "packets" in status_dict:
            self.packets_var.set(str(status_dict["packets"]))

        if "data" in status_dict:
            self.data_var.set(f"{status_dict['data']:.2f} MB")

        if "data_quality" in status_dict:
            quality = status_dict["data_quality"]
            color = "🟢" if quality > 80 else "🟡" if quality > 50 else "🔴"
            self.quality_var.set(f"{color} {quality:.1f}%")

    def update_sensor_data(self, sensor_data):
        """Atualiza dados dos sensores"""
        # Mapeamento de campos
        field_mapping = {
            # Dados raw BMI160
            "bmi160_accel_x_raw": "bmi160_accel_x_raw",
            "bmi160_accel_y_raw": "bmi160_accel_y_raw",
            "bmi160_accel_z_raw": "bmi160_accel_z_raw",
            "bmi160_gyro_x_raw": "bmi160_gyro_x_raw",
            "bmi160_gyro_y_raw": "bmi160_gyro_y_raw",
            "bmi160_gyro_z_raw": "bmi160_gyro_z_raw",
            # Dados físicos
            "bmi160_accel_x": "accel_x",
            "bmi160_accel_y": "accel_y",
            "bmi160_accel_z": "accel_z",
            "bmi160_gyro_x": "gyro_x",
            "bmi160_gyro_y": "gyro_y",
            "bmi160_gyro_z": "gyro_z",
            # Forças G
            "g_force_frontal": "g_force_frontal",
            "g_force_lateral": "g_force_lateral",
            "g_force_vertical": "g_force_vertical",
            # Force feedback
            "steering_feedback_intensity": "steering_feedback",
            "brake_pedal_resistance": "brake_resistance",
            "seat_vibration_intensity": "seat_vibration",
            "seat_tilt_x": "seat_tilt_x",
            "seat_tilt_y": "seat_tilt_y",
            # Dados derivados
            "velocidade": "velocidade",
            "steering_angle": "steering_angle",
            "bateria_nivel": "bateria_nivel",
            "temperatura": "temperatura",
            # Configurações
            "accel_range_g": "accel_range",
            "gyro_range_dps": "gyro_range",
            "sample_rate": "sample_rate",
            # Metadados
            "timestamp": "timestamp",
            "frame_count": "frame_count",
            "readings_count": "readings_count",
        }

        # Atualiza campos mapeados
        for sensor_field, var_name in field_mapping.items():
            if sensor_field in sensor_data and var_name in self.sensor_vars:
                value = sensor_data[sensor_field]

                # Formatação especial para alguns campos
                if var_name in [
                    "accel_x",
                    "accel_y",
                    "accel_z",
                    "gyro_x",
                    "gyro_y",
                    "gyro_z",
                ]:
                    formatted_value = f"{value:.3f}"
                elif var_name in [
                    "g_force_frontal",
                    "g_force_lateral",
                    "g_force_vertical",
                ]:
                    formatted_value = f"{value:+.3f}"  # Com sinal
                elif var_name in ["velocidade", "temperatura"]:
                    formatted_value = f"{value:.1f}"
                elif var_name in ["accel_range"]:
                    formatted_value = f"±{value}g"
                elif var_name in ["gyro_range"]:
                    formatted_value = f"±{value}°/s"
                elif var_name in ["sample_rate"]:
                    formatted_value = f"{value}Hz"
                elif isinstance(value, float):
                    formatted_value = f"{value:.1f}"
                else:
                    formatted_value = str(value)

                self.sensor_vars[var_name].set(formatted_value)

        # Atualiza eventos detectados
        events = []
        if sensor_data.get("is_turning_left", False):
            events.append("🔄 Curva ESQ")
        if sensor_data.get("is_turning_right", False):
            events.append("🔄 Curva DIR")
        if sensor_data.get("is_accelerating", False):
            events.append("⚡ Acelerando")
        if sensor_data.get("is_braking", False):
            events.append("🛑 Freando")
        if sensor_data.get("is_bouncing", False):
            events.append("📳 Solavancos")
        if sensor_data.get("impact_detected", False):
            events.append("💥 Impacto")

        events_text = ", ".join(events) if events else "😴 Nenhum"
        self.sensor_vars["events_detected"].set(events_text)

    def process_queues(self):
        """Processa filas de comunicação"""
        try:
            # Processar logs
            while self.log_queue and not self.log_queue.empty():
                level, message = self.log_queue.get_nowait()
                self.log(level, message)

            # Processar status de rede
            while self.status_queue and not self.status_queue.empty():
                status_dict = self.status_queue.get_nowait()
                self.update_connection_status(status_dict)

            # Processar dados de sensores
            if self.sensor_display:
                if self.sensor_display.process_queue():
                    sensor_data = self.sensor_display.get_display_data()
                    self.update_sensor_data(sensor_data)

        except Exception as e:
            print(f"Erro ao processar filas: {e}")

        # Agenda próxima atualização
        if self.is_running:
            self.root.after(self.update_interval, self.process_queues)

    def toggle_pause(self):
        """Alterna pausa do log"""
        self.paused = not self.paused
        text = "▶️ Continuar" if self.paused else "⏸️ Pausar"
        self.pause_btn.config(text=text)

    def clear_log(self):
        """Limpa o log"""
        self.log_text.delete(1.0, tk.END)

    def toggle_autoscroll(self):
        """Alterna auto-scroll"""
        self.auto_scroll = self.autoscroll_var.get()

    def reset_statistics(self):
        """Reseta estatísticas"""
        if self.sensor_display:
            self.sensor_display.reset_statistics()
        self.log("INFO", "Estatísticas resetadas")

    def export_data(self):
        """Exporta dados para arquivo"""
        if self.sensor_display:
            filename = self.sensor_display.export_history()
            if filename:
                self.log("INFO", f"Dados exportados para: {filename}")
            else:
                self.log("WARNING", "Falha ao exportar dados")
        else:
            self.log("WARNING", "Processador de sensores não disponível")

    def on_closing(self):
        """Manipula fechamento da janela"""
        self.log("INFO", "Fechando interface do console...")
        self.stop()

    def run_interface(self):
        """Executa a interface principal"""
        try:
            # Cria janela principal
            self.create_main_window()

            # Cria variáveis Tkinter
            self.create_tkinter_variables()

            # Cria widgets
            self.create_widgets()

            # Marca como executando
            self.is_running = True

            # Inicia processamento de filas
            self.root.after(self.update_interval, self.process_queues)

            # Log inicial
            self.log("INFO", "Interface do console iniciada")
            self.log("INFO", "Aguardando dados do Raspberry Pi...")

            # Inicia loop principal do Tkinter
            self.root.mainloop()

        except Exception as e:
            print(f"Erro na interface: {e}")
            import traceback

            traceback.print_exc()

    def stop(self):
        """Para a interface"""
        self.is_running = False

        if self.root:
            try:
                self.root.quit()
                self.root.destroy()
            except:
                pass


# Teste independente
if __name__ == "__main__":
    import queue
    import threading
    import time
    import random

    print("=== TESTE DA CONSOLE INTERFACE CORRIGIDA ===")

    # Cria filas de teste
    log_q = queue.Queue()
    status_q = queue.Queue()

    # Cria interface
    interface = ConsoleInterface(log_queue=log_q, status_queue=status_q)

    def generate_test_data():
        """Gera dados de teste"""
        time.sleep(2)  # Aguarda interface inicializar

        for i in range(100):
            # Log de teste
            levels = ["INFO", "WARNING", "ERROR"]
            level = levels[i % 3]
            log_q.put((level, f"Mensagem de teste {i+1} - {level}"))

            # Status de teste
            if i % 5 == 0:
                status_q.put(
                    {
                        "connection": "Conectado a 192.168.1.100:9999",
                        "fps": random.uniform(25, 35),
                        "frame_size": random.uniform(10, 25),
                        "packets": i * 2,
                        "data": i * 0.1,
                        "data_quality": random.uniform(80, 100),
                    }
                )

            time.sleep(0.5)

    # Inicia gerador em thread separada
    generator_thread = threading.Thread(target=generate_test_data, daemon=True)
    generator_thread.start()

    print("✅ Interface de teste iniciada")
    print("📱 Aguarde 2 segundos para dados aparecerem...")

    # Executa interface
    interface.run_interface()

    print("✅ Teste concluído")
