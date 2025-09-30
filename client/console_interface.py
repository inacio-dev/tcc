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
- Dados derivados do BMI160
"""

import tkinter as tk
from tkinter import scrolledtext, ttk
import time
import queue
from datetime import datetime
from typing import Optional
from simple_logger import error, debug, info
from keyboard_controller import KeyboardController
from slider_controller import SliderController


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

        # Network client para enviar comandos
        self.network_client = None

        # Controlador de teclado
        self.keyboard_controller = KeyboardController(log_callback=self.log)

        # Controlador de sliders
        self.slider_controller = SliderController(log_callback=self.log)

        # Variáveis de status da conexão
        self.connection_var = None
        self.fps_var = None
        self.frame_size_var = None
        self.packets_var = None
        self.data_var = None
        self.quality_var = None

        # Variáveis dos sensores BMI160
        self.sensor_vars = {}

        # Controles de veículo
        self.brake_balance_var = None
        self.current_brake_force = 0.0
        self.current_throttle = 0.0
        self.current_steering = 0.0

        # Widgets principais
        self.log_text = None
        self.pause_btn = None
        self.brake_balance_scale = None
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

        # Controles de veículo
        self.brake_balance_var = tk.DoubleVar(value=60.0)  # 60% dianteiro padrão

        # Instrumentos do motor
        self.rpm_var = tk.StringVar(value="0")
        self.gear_var = tk.StringVar(value="1")
        self.throttle_var = tk.StringVar(value="0.0")
        self.speed_var = tk.StringVar(value="0.0")

        # Cálculo de velocidade baseado no BMI160
        self.velocity_x = 0.0  # Velocidade em m/s no eixo X
        self.velocity_y = 0.0  # Velocidade em m/s no eixo Y
        self.velocity_total = 0.0  # Velocidade total em km/h
        self.last_accel_time = None  # Timestamp da última leitura
        self.accel_threshold = 0.3  # Threshold para filtrar ruído (m/s²)

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
            # Force Feedback
            "steering_feedback": tk.StringVar(value="0.0"),
            "brake_resistance": tk.StringVar(value="0.0"),
            "seat_vibration": tk.StringVar(value="0.0"),
            "seat_tilt_x": tk.StringVar(value="0.0"),
            "seat_tilt_y": tk.StringVar(value="0.0"),
            # Dados do sensor de temperatura DS18B20 (valores reais)
            "temperature_c": tk.StringVar(value="--"),
            "temperature_f": tk.StringVar(value="--"),
            "temperature_k": tk.StringVar(value="--"),
            "thermal_status": tk.StringVar(value="NORMAL"),
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
        """Cria janela principal com scroll vertical e layout em grid"""
        self.root = tk.Tk()
        self.root.title("🏎️ F1 Car - Console de Controle")
        self.root.geometry(
            "1400x1000"
        )  # Janela maior para acomodar vídeo em resolução original
        self.root.configure(bg="#2b2b2b")  # Tema escuro

        # Permitir redimensionamento
        self.root.resizable(True, True)

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

        # Criar canvas principal com scrollbar
        self.main_canvas = tk.Canvas(self.root, bg="#2b2b2b", highlightthickness=0)
        self.main_scrollbar = ttk.Scrollbar(
            self.root, orient="vertical", command=self.main_canvas.yview
        )
        self.scrollable_frame = ttk.Frame(self.main_canvas, style="Dark.TLabelframe")

        # Configurar scroll
        self.scrollable_frame.bind(
            "<Configure>",
            lambda e: self.main_canvas.configure(
                scrollregion=self.main_canvas.bbox("all")
            ),
        )

        # Criar janela no canvas
        self.canvas_window = self.main_canvas.create_window(
            (0, 0), window=self.scrollable_frame, anchor="nw"
        )

        # Configurar canvas
        self.main_canvas.configure(yscrollcommand=self.main_scrollbar.set)

        # Posicionar elementos
        self.main_canvas.pack(side="left", fill="both", expand=True)
        self.main_scrollbar.pack(side="right", fill="y")

        # Configurar grid principal (2 colunas)
        self.scrollable_frame.grid_columnconfigure(0, weight=1)
        self.scrollable_frame.grid_columnconfigure(1, weight=1)

        # Criar frames principais para as duas colunas
        self.left_column = ttk.Frame(self.scrollable_frame, style="Dark.TLabelframe")
        self.right_column = ttk.Frame(self.scrollable_frame, style="Dark.TLabelframe")

        self.left_column.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
        self.right_column.grid(row=0, column=1, sticky="nsew", padx=5, pady=5)

        # Configurar scroll com mouse wheel (multiplataforma)
        self.main_canvas.bind("<MouseWheel>", self._on_mousewheel)  # Windows
        self.main_canvas.bind("<Button-4>", self._on_mousewheel)  # Linux scroll up
        self.main_canvas.bind("<Button-5>", self._on_mousewheel)  # Linux scroll down
        self.root.bind("<MouseWheel>", self._on_mousewheel)  # Windows - janela toda
        self.root.bind(
            "<Button-4>", self._on_mousewheel
        )  # Linux scroll up - janela toda
        self.root.bind(
            "<Button-5>", self._on_mousewheel
        )  # Linux scroll down - janela toda

        # Bind para redimensionamento da janela
        self.main_canvas.bind("<Configure>", self._on_canvas_configure)

        # Aplicar scroll a todos os widgets após criação da interface
        self.root.after(100, self._bind_mousewheel_to_all)

    def _on_mousewheel(self, event):
        """Handler para scroll com mouse wheel (multiplataforma)"""
        # Windows usa event.delta, Linux usa event.num
        if hasattr(event, "delta"):
            # Windows: delta é múltiplo de 120
            delta = int(-1 * (event.delta / 120))
        elif hasattr(event, "num"):
            # Linux: Button-4 (scroll up) = -1, Button-5 (scroll down) = +1
            delta = -1 if event.num == 4 else 1
        else:
            # Fallback
            delta = 1

        # Scroll mais suave (3 unidades por vez)
        self.main_canvas.yview_scroll(delta * 3, "units")

        # Retorna "break" para evitar propagação adicional
        return "break"

    def _bind_mousewheel_to_all(self):
        """Aplica scroll do mouse a todos os widgets da interface"""

        def bind_to_widget(widget):
            try:
                # Bind eventos de scroll multiplataforma
                widget.bind("<MouseWheel>", self._on_mousewheel, add="+")  # Windows
                widget.bind(
                    "<Button-4>", self._on_mousewheel, add="+"
                )  # Linux scroll up
                widget.bind(
                    "<Button-5>", self._on_mousewheel, add="+"
                )  # Linux scroll down
            except tk.TclError:
                # Alguns widgets não suportam bind, ignora
                pass

            # Aplica recursivamente aos filhos
            try:
                for child in widget.winfo_children():
                    bind_to_widget(child)
            except tk.TclError:
                pass

        # Aplica a toda a árvore de widgets
        bind_to_widget(self.root)

    def _on_canvas_configure(self, event):
        """Handler para redimensionamento do canvas"""
        # Ajustar largura do frame interno
        canvas_width = event.width
        self.main_canvas.itemconfig(self.canvas_window, width=canvas_width)

    def create_connection_status_frame(self):
        """Cria frame de status da conexão"""
        status_frame = ttk.LabelFrame(
            self.left_column, text="📡 Status da Conexão", style="Dark.TLabelframe"
        )
        status_frame.pack(fill=tk.X, padx=5, pady=5)

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

    def create_instrument_panel(self):
        """Cria painel de instrumentos (RPM, marcha, velocidade)"""
        instrument_frame = ttk.LabelFrame(
            self.left_column, text="🏎️ Painel de Instrumentos", style="Dark.TLabelframe"
        )
        instrument_frame.pack(fill=tk.X, padx=5, pady=5)

        # Frame interno para organizar os instrumentos
        instruments_inner = tk.Frame(instrument_frame, bg="#3c3c3c")
        instruments_inner.pack(fill=tk.X, padx=10, pady=10)

        # Conta-giros (RPM) - Lado esquerdo
        rpm_frame = tk.Frame(instruments_inner, bg="#2c2c2c", relief=tk.RAISED, bd=2)
        rpm_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        tk.Label(
            rpm_frame,
            text="🔧 ZONA DE EFICIÊNCIA",
            bg="#2c2c2c",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(pady=5)

        # RPM em fonte grande
        self.rpm_display = tk.Label(
            rpm_frame,
            textvariable=self.rpm_var,
            bg="#2c2c2c",
            fg="#00ff00",
            font=("Digital-7", 24, "bold"),
        )
        self.rpm_display.pack(pady=5)

        tk.Label(
            rpm_frame, text="% IDEAL", bg="#2c2c2c", fg="#cccccc", font=("Arial", 8)
        ).pack()

        # Marcha - Centro
        gear_frame = tk.Frame(instruments_inner, bg="#2c2c2c", relief=tk.RAISED, bd=2)
        gear_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        tk.Label(
            gear_frame,
            text="⚙️ MARCHA",
            bg="#2c2c2c",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(pady=5)

        # Marcha em fonte muito grande
        self.gear_display = tk.Label(
            gear_frame,
            textvariable=self.gear_var,
            bg="#2c2c2c",
            fg="#ffaa00",
            font=("Arial", 36, "bold"),
        )
        self.gear_display.pack(pady=10)

        tk.Label(
            gear_frame, text="ª", bg="#2c2c2c", fg="#cccccc", font=("Arial", 12)
        ).pack()

        # Motor e Velocidade - Lado direito
        speed_frame = tk.Frame(instruments_inner, bg="#2c2c2c", relief=tk.RAISED, bd=2)
        speed_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

        tk.Label(
            speed_frame,
            text="🚀 MOTOR",
            bg="#2c2c2c",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(pady=5)

        # Throttle
        throttle_inner = tk.Frame(speed_frame, bg="#2c2c2c")
        throttle_inner.pack(fill=tk.X, pady=2)

        tk.Label(
            throttle_inner,
            text="Acelerador:",
            bg="#2c2c2c",
            fg="#cccccc",
            font=("Arial", 8),
        ).pack(side=tk.LEFT)
        tk.Label(
            throttle_inner,
            textvariable=self.throttle_var,
            bg="#2c2c2c",
            fg="#ff6600",
            font=("Arial", 14, "bold"),
        ).pack(side=tk.RIGHT)

        # Motor não tem sensor de velocidade - velocidade está na seção BMI160

        # Temperatura - Painel adicional na linha inferior
        temp_frame = tk.Frame(instruments_inner, bg="#2c2c2c", relief=tk.RAISED, bd=2)
        temp_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        tk.Label(
            temp_frame,
            text="🌡️ TEMPERATURA",
            bg="#2c2c2c",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(pady=5)

        # Display de temperatura com cor baseada na faixa
        self.temp_display = tk.Label(
            temp_frame,
            textvariable=self.sensor_vars["temperature_c"],
            bg="#2c2c2c",
            fg="#00ff88",
            font=("Digital-7", 20, "bold"),
        )
        self.temp_display.pack(pady=5)

        tk.Label(
            temp_frame, text="°C", bg="#2c2c2c", fg="#cccccc", font=("Arial", 10)
        ).pack()

    def create_bmi160_frame(self):
        """Cria frame com dados do BMI160"""
        sensor_frame = ttk.LabelFrame(
            self.left_column, text="🔧 Dados do BMI160", style="Dark.TLabelframe"
        )
        sensor_frame.pack(fill=tk.X, padx=5, pady=5)

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

        # Velocidade calculada pelo BMI160
        velocity_frame = tk.LabelFrame(
            sensor_frame,
            text="Velocidade (Calculada)",
            bg="#3c3c3c",
            fg="white",
            font=("Arial", 9, "bold"),
        )
        velocity_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Label(velocity_frame, text="Velocidade:", style="Dark.TLabel").grid(
            row=0, column=0, padx=5, sticky=tk.W
        )
        self.velocity_label = ttk.Label(
            velocity_frame, text="0.0 km/h", style="Dark.TLabel"
        )
        self.velocity_label.grid(row=0, column=1, padx=5, sticky=tk.W)

    def create_force_feedback_frame(self):
        """Cria frame com dados do force feedback"""
        ff_frame = ttk.LabelFrame(
            self.left_column, text="🎮 Force Feedback", style="Dark.TLabelframe"
        )
        ff_frame.pack(fill=tk.X, padx=5, pady=5)

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
            self.right_column, text="🎛️ Controles do Veículo", style="Dark.TLabelframe"
        )
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Frame superior para botões
        btn_frame = tk.Frame(control_frame, bg="#3c3c3c")
        btn_frame.pack(fill=tk.X, padx=5, pady=2)

        ttk.Button(
            btn_frame,
            text="Reset Stats",
            command=self.reset_statistics,
            style="Dark.TButton",
        ).pack(side=tk.LEFT, padx=5)

        ttk.Button(
            btn_frame,
            text="Export Data",
            command=self.export_data,
            style="Dark.TButton",
        ).pack(side=tk.LEFT, padx=5)

        # Separador
        ttk.Separator(btn_frame, orient="vertical").pack(
            side=tk.LEFT, fill=tk.Y, padx=10, pady=5
        )

        # Status das configurações
        ttk.Label(btn_frame, text="Config:", style="Dark.TLabel").pack(
            side=tk.LEFT, padx=5
        )
        ttk.Label(
            btn_frame,
            textvariable=self.sensor_vars["accel_range"],
            style="Dark.TLabel",
        ).pack(side=tk.LEFT, padx=2)
        ttk.Label(
            btn_frame,
            textvariable=self.sensor_vars["gyro_range"],
            style="Dark.TLabel",
        ).pack(side=tk.LEFT, padx=2)

        # Frame para controle de freio
        brake_frame = tk.Frame(control_frame, bg="#3c3c3c")
        brake_frame.pack(fill=tk.X, padx=5, pady=5)

        ttk.Label(brake_frame, text="🚥 Balanço de Freio:", style="Dark.TLabel").pack(
            side=tk.LEFT, padx=5
        )

        # Slider para balanço de freio (0% = mais traseiro, 100% = mais dianteiro)
        self.brake_balance_scale = tk.Scale(
            brake_frame,
            from_=0,
            to=100,
            resolution=5,
            orient=tk.HORIZONTAL,
            length=200,
            variable=self.brake_balance_var,
            command=self._on_brake_balance_change,
            bg="#3c3c3c",
            fg="white",
            highlightbackground="#3c3c3c",
            troughcolor="#2c2c2c",
            activebackground="#0078d4",
        )
        self.brake_balance_scale.pack(side=tk.LEFT, padx=10)

        # Labels informativos
        ttk.Label(brake_frame, text="Traseiro", style="Dark.TLabel").pack(
            side=tk.LEFT, padx=2
        )
        ttk.Label(brake_frame, text="←", style="Dark.TLabel").pack(side=tk.LEFT)
        ttk.Label(brake_frame, text="→", style="Dark.TLabel").pack(side=tk.LEFT)
        ttk.Label(brake_frame, text="Dianteiro", style="Dark.TLabel").pack(
            side=tk.LEFT, padx=2
        )

        # Label com valor atual
        self.brake_balance_label = ttk.Label(
            brake_frame, text="60% Dianteiro / 40% Traseiro", style="Dark.TLabel"
        )
        self.brake_balance_label.pack(side=tk.LEFT, padx=10)

    def create_video_frame(self):
        """Cria frame para exibição do vídeo"""
        video_frame = ttk.LabelFrame(
            self.right_column, text="📹 Vídeo da Câmera", style="Dark.TLabelframe"
        )
        video_frame.pack(fill=tk.X, padx=5, pady=5)

        # Frame interno para o vídeo (altura aumentada para resolução original da câmera)
        self.video_container = tk.Frame(video_frame, bg="#1a1a1a", height=480)
        self.video_container.pack(fill=tk.X, padx=5, pady=5)
        self.video_container.pack_propagate(False)  # Manter altura fixa

        # Label para exibir o vídeo (será atualizado pelo video_display)
        self.video_label = tk.Label(
            self.video_container,
            text="🎥 Aguardando vídeo...\nVídeo será exibido aqui quando conectado",
            bg="#1a1a1a",
            fg="white",
            font=("Arial", 10),
            justify=tk.CENTER,
        )
        self.video_label.pack(expand=True)

        # Frame para controles do vídeo
        video_controls = tk.Frame(video_frame, bg="#3c3c3c")
        video_controls.pack(fill=tk.X, padx=5, pady=2)

        # Status do vídeo
        self.video_status_var = tk.StringVar(value="🔴 Sem vídeo")
        ttk.Label(video_controls, text="Status:", style="Dark.TLabel").pack(
            side=tk.LEFT, padx=5
        )
        ttk.Label(
            video_controls, textvariable=self.video_status_var, style="Dark.TLabel"
        ).pack(side=tk.LEFT)

        # Resolução
        self.video_resolution_var = tk.StringVar(value="N/A")
        ttk.Label(video_controls, text="Resolução:", style="Dark.TLabel").pack(
            side=tk.LEFT, padx=(20, 5)
        )
        ttk.Label(
            video_controls, textvariable=self.video_resolution_var, style="Dark.TLabel"
        ).pack(side=tk.LEFT)

        # NOVOS CONTROLES: Melhorias de Vídeo
        enhancements_frame = tk.Frame(video_controls, bg="#1a1a1a")
        enhancements_frame.pack(side=tk.LEFT, padx=(20, 0))

        ttk.Label(enhancements_frame, text="Melhorias:", style="Dark.TLabel").pack(
            side=tk.LEFT
        )

        # Correção de Cor
        self.color_correction_var = tk.BooleanVar(value=True)  # Ativo por padrão
        color_check = ttk.Checkbutton(
            enhancements_frame,
            text="🎨 Cor",
            variable=self.color_correction_var,
            command=self.toggle_color_correction,
            style="Dark.TCheckbutton",
        )
        color_check.pack(side=tk.LEFT, padx=2)

        # Sharpening
        self.sharpening_var = tk.BooleanVar(value=True)  # Ativo por padrão
        sharp_check = ttk.Checkbutton(
            enhancements_frame,
            text="🔍 Nitidez",
            variable=self.sharpening_var,
            command=self.toggle_sharpening,
            style="Dark.TCheckbutton",
        )
        sharp_check.pack(side=tk.LEFT, padx=2)

        # Brilho Automático
        self.brightness_var = tk.BooleanVar(value=True)  # Ativo por padrão
        brightness_check = ttk.Checkbutton(
            enhancements_frame,
            text="💡 Brilho",
            variable=self.brightness_var,
            command=self.toggle_brightness,
            style="Dark.TCheckbutton",
        )
        brightness_check.pack(side=tk.LEFT, padx=2)

    def toggle_color_correction(self):
        """Ativa/desativa correção automática de cor"""
        if hasattr(self, "video_display") and self.video_display:
            self.video_display.toggle_color_correction(self.color_correction_var.get())

    def toggle_sharpening(self):
        """Ativa/desativa sharpening inteligente"""
        if hasattr(self, "video_display") and self.video_display:
            self.video_display.toggle_sharpening(self.sharpening_var.get())

    def toggle_brightness(self):
        """Ativa/desativa ajuste automático de brilho"""
        if hasattr(self, "video_display") and self.video_display:
            self.video_display.toggle_brightness_adjustment(self.brightness_var.get())

    def set_video_display(self, video_display):
        """Define o video_display para integração"""
        self.video_display = video_display

        # A conexão será feita automaticamente quando create_widgets() for chamado
        # Não fazemos nada aqui pois os widgets ainda não foram criados

    def update_video_status(self, status_dict):
        """Atualiza status do vídeo"""
        if hasattr(self, "video_status_var"):
            if status_dict.get("connected", False):
                fps = status_dict.get("fps", 0)
                self.video_status_var.set(f"🟢 Conectado ({fps:.1f} FPS)")
            else:
                self.video_status_var.set("🔴 Desconectado")

        if hasattr(self, "video_resolution_var"):
            width = status_dict.get("width", 0)
            height = status_dict.get("height", 0)
            if width > 0 and height > 0:
                self.video_resolution_var.set(f"{width}x{height}")
            else:
                self.video_resolution_var.set("N/A")

    def create_slider_controls_frame(self):
        """Cria frame com controles de sliders"""
        slider_frame = self.slider_controller.create_control_frame(self.right_column)
        slider_frame.pack(fill=tk.X, padx=5, pady=5)

    def create_keyboard_controls_frame(self):
        """Cria frame com controles de teclado"""
        keyboard_frame = self.keyboard_controller.create_status_frame(self.right_column)
        keyboard_frame.pack(fill=tk.X, padx=5, pady=5)

    def create_log_frame(self):
        """Cria frame do console de log"""
        log_frame = ttk.LabelFrame(
            self.right_column, text="📋 Console de Log", style="Dark.TLabelframe"
        )
        log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

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
        # Coluna Esquerda
        self.create_connection_status_frame()
        self.create_instrument_panel()
        self.create_bmi160_frame()
        self.create_force_feedback_frame()

        # Coluna Direita
        self.create_video_frame()
        self.create_slider_controls_frame()
        self.create_controls_frame()
        self.create_keyboard_controls_frame()
        self.create_log_frame()

        # Conecta video_display se já foi definido
        if hasattr(self, "video_display") and self.video_display:
            if hasattr(self.video_display, "set_tkinter_label"):
                self.video_display.set_tkinter_label(self.video_label)
            if hasattr(self.video_display, "set_status_callback"):
                self.video_display.set_status_callback(self.update_video_status)

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
        # Calcular velocidade baseada no BMI160 (deve ser chamado primeiro)
        self._calculate_velocity_from_bmi160(sensor_data)

        # Atualizar dados do motor (RPM, marcha, throttle, velocidade)
        self._update_motor_display(sensor_data)

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
            # Dados do sensor de temperatura DS18B20
            "temperature_c": "temperature_c",
            "temperature_f": "temperature_f",
            "temperature_k": "temperature_k",
            "thermal_status": "thermal_status",
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
                elif var_name in ["temperature_c", "temperature_f", "temperature_k"]:
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

        # Eventos detectados são mostrados apenas no log, não na interface visual

        # Atualiza cor do display de temperatura baseado no status térmico
        self._update_temperature_colors(sensor_data)

    def _update_temperature_colors(self, sensor_data):
        """Atualiza as cores do display de temperatura baseado no status térmico"""
        try:
            if hasattr(self, "temp_display"):
                thermal_status = sensor_data.get("thermal_status", "NORMAL")
                temperature_c = sensor_data.get("temperature_c", 0.0)

                # Define cores baseadas no status térmico
                color_mapping = {
                    "NORMAL": "#00ff88",  # Verde - temperatura normal
                    "WARNING": "#ffaa00",  # Laranja - temperatura elevada
                    "CRITICAL": "#ff4444",  # Vermelho - temperatura crítica
                    "CRITICAL_SHUTDOWN": "#ff0000",  # Vermelho intenso - shutdown crítico
                }

                # Atualiza cor do display
                color = color_mapping.get(thermal_status, "#00ff88")
                self.temp_display.config(fg=color)

                # Adiciona indicador visual de alerta se necessário
                if thermal_status in ["CRITICAL", "CRITICAL_SHUTDOWN"]:
                    # Pisca o display em caso crítico
                    current_color = self.temp_display.cget("fg")
                    flash_color = "#ffffff" if current_color != "#ffffff" else color
                    self.root.after(
                        500, lambda: self.temp_display.config(fg=flash_color)
                    )

        except Exception as e:
            error(f"Erro ao atualizar cores de temperatura: {e}", "CONSOLE")

    def _update_motor_display(self, sensor_data):
        """Atualiza o painel de instrumentos do motor"""
        try:
            # RPM do motor
            if "engine_rpm" in sensor_data:
                rpm = sensor_data["engine_rpm"]
                self.rpm_var.set(f"{rpm:.0f}")

            # Marcha atual
            if "current_gear" in sensor_data:
                gear = sensor_data["current_gear"]
                self.gear_var.set(str(gear))

            # Throttle atual (PWM)
            if "current_pwm" in sensor_data:
                throttle = sensor_data["current_pwm"]
                self.throttle_var.set(f"{throttle:.1f}%")

            # Velocidade não é exibida no motor - apenas na seção BMI160

        except Exception as e:
            error(f"Erro ao atualizar painel de instrumentos: {e}", "CONSOLE")

    def _calculate_velocity_from_bmi160(self, sensor_data):
        """
        Calcula velocidade baseada nos dados de aceleração do BMI160

        Args:
            sensor_data (dict): Dados dos sensores incluindo aceleração
        """
        try:
            import time

            # Obtém dados de aceleração em m/s²
            accel_x = sensor_data.get(
                "bmi160_accel_x", 0.0
            )  # Longitudinal (frente/trás)
            accel_y = sensor_data.get(
                "bmi160_accel_y", 0.0
            )  # Lateral (esquerda/direita)

            current_time = time.time()

            # Inicializa tempo se for a primeira leitura
            if self.last_accel_time is None:
                self.last_accel_time = current_time
                return

            # Calcula delta time
            dt = current_time - self.last_accel_time
            self.last_accel_time = current_time

            # Ignora se dt muito pequeno ou muito grande (evita erros)
            if dt <= 0 or dt > 0.1:  # Máximo 100ms entre leituras
                return

            # Filtra ruído - só considera acelerações significativas
            if abs(accel_x) < self.accel_threshold:
                accel_x = 0.0
            if abs(accel_y) < self.accel_threshold:
                accel_y = 0.0

            # Integração da aceleração para obter velocidade
            # v = v0 + a*dt
            self.velocity_x += accel_x * dt
            self.velocity_y += accel_y * dt

            # Aplicar decay para simular atrito/resistência do ar
            decay_factor = 0.98  # 2% de redução por leitura (simula atrito)
            self.velocity_x *= decay_factor
            self.velocity_y *= decay_factor

            # Zera velocidades muito pequenas (evita deriva)
            if abs(self.velocity_x) < 0.1:
                self.velocity_x = 0.0
            if abs(self.velocity_y) < 0.1:
                self.velocity_y = 0.0

            # Calcula velocidade total (magnitude do vetor velocidade)
            velocity_ms = (self.velocity_x**2 + self.velocity_y**2) ** 0.5

            # Converte m/s para km/h
            self.velocity_total = velocity_ms * 3.6

            # Atualiza display da velocidade na seção BMI160
            if hasattr(self, "velocity_label"):
                self.velocity_label.config(text=f"{self.velocity_total:.1f} km/h")

        except Exception as e:
            error(f"Erro ao calcular velocidade: {e}", "CONSOLE")

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
            error(f"Erro ao processar filas: {e}", "CONSOLE")

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
        try:
            if self.is_running:
                self.log("INFO", "Fechando interface do console...")
            self.stop()
        except:
            # Ignora erros durante o shutdown
            pass

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

            # Configura controles de teclado
            self.keyboard_controller.bind_to_widget(self.root)
            self.keyboard_controller.start()

            # Inicia controlador de sliders
            self.slider_controller.start()

            # Log inicial
            self.log("INFO", "Interface do console iniciada")
            self.log("INFO", "Aguardando dados do Raspberry Pi...")
            self.log(
                "INFO", "Controles: Use as setas ou WASD para controlar o carrinho"
            )

            # Inicia loop principal do Tkinter
            self.root.mainloop()

        except Exception as e:
            try:
                error(f"Erro na interface: {e}", "CONSOLE")
            except:
                pass
        finally:
            # Garante limpeza mesmo em caso de erro
            self._cleanup_tkinter_resources()

    def _cleanup_tkinter_resources(self):
        """Limpa todos os recursos Tkinter de forma segura"""
        try:
            import tkinter as tk
            # Para o controlador de teclado
            if hasattr(self, "keyboard_controller") and self.keyboard_controller:
                self.keyboard_controller.stop()

            # Para o controlador de sliders
            if hasattr(self, "slider_controller") and self.slider_controller:
                self.slider_controller.stop()

            # Lista COMPLETA de todas as variáveis Tkinter
            tkinter_vars = [
                "connection_var",
                "fps_var",
                "frame_size_var",
                "packets_var",
                "data_var",
                "quality_var",
                "brake_balance_var",
                "rpm_var",
                "gear_var",
                "throttle_var",
                "speed_var",
                "video_status_var",
                "video_resolution_var",
                "color_correction_var",
                "sharpening_var",
                "brightness_var",
                "autoscroll_var",
            ]

            # Remove todas as variáveis Tkinter individuais
            for var_name in tkinter_vars:
                if hasattr(self, var_name):
                    try:
                        var = getattr(self, var_name)
                        if var is not None:
                            try:
                                var._tk = None  # Quebra referência ao Tcl
                            except:
                                pass
                        delattr(self, var_name)
                    except:
                        pass

            # Limpa dicionário de sensor vars de forma mais agressiva
            if hasattr(self, "sensor_vars"):
                try:
                    for key, var in list(self.sensor_vars.items()):
                        if var is not None:
                            try:
                                var._tk = None  # Quebra referência ao Tcl
                            except:
                                pass
                    self.sensor_vars.clear()
                    delattr(self, "sensor_vars")
                except:
                    pass

            # Remove outras referências Tkinter
            widget_refs = [
                "log_text",
                "pause_btn",
                "brake_balance_scale",
                "video_label",
                "main_canvas",
                "main_scrollbar",
                "scrollable_frame",
                "canvas_window",
                "left_column",
                "right_column",
                "video_container",
                "rpm_display",
                "gear_display",
                "temp_display",
                "velocity_label",
                "brake_balance_label",
            ]

            for widget_name in widget_refs:
                if hasattr(self, widget_name):
                    try:
                        delattr(self, widget_name)
                    except:
                        pass

            # Força garbage collection antes de destruir janela
            try:
                import gc

                gc.collect()
            except:
                pass

            # Destrói a janela principal por último
            if hasattr(self, "root") and self.root:
                try:
                    # Para todos os after() e after_idle()
                    self.root.after_cancel("all")

                    # Força a finalização de todos os eventos pendentes
                    try:
                        self.root.update_idletasks()
                    except:
                        pass

                    # Só destrói se a janela ainda existe
                    try:
                        # Verifica se a janela ainda está válida
                        self.root.winfo_exists()
                        # Se chegou aqui, a janela existe, então destroi
                        self.root.destroy()
                    except tk.TclError:
                        # Janela já foi destruída, ok
                        pass
                    except:
                        # Outro erro, tenta destroy mesmo assim
                        try:
                            self.root.destroy()
                        except:
                            pass

                    self.root = None
                except:
                    pass

        except:
            pass

    def _on_brake_balance_change(self, value):
        """Callback quando o slider de brake balance muda"""
        try:
            balance = float(value)
            # Atualiza o label
            front_pct = balance
            rear_pct = 100 - balance
            self.brake_balance_label.config(
                text=f"{front_pct:.0f}% Dianteiro / {rear_pct:.0f}% Traseiro"
            )

            # Envia comando para o Raspberry Pi
            self._send_brake_balance_command(balance)

        except Exception as e:
            error(f"Erro ao alterar balanço de freio: {e}", "CONTROL")

    def _send_brake_balance_command(self, balance: float):
        """Envia comando de brake balance para o Raspberry Pi"""
        try:
            if hasattr(self, "network_client") and self.network_client:
                success = self.network_client.send_control_command(
                    "BRAKE_BALANCE", balance
                )
                if success:
                    debug(f"Comando enviado: BRAKE_BALANCE:{balance}", "CONTROL")
                    self.log(
                        "INFO", f"Balanço de freio alterado: {balance:.0f}% dianteiro"
                    )
                else:
                    debug("Falha ao enviar comando brake_balance", "CONTROL")
            else:
                debug("Network client não disponível para enviar comando", "CONTROL")
        except Exception as e:
            error(f"Erro ao enviar comando brake_balance: {e}", "CONTROL")

    def set_network_client(self, network_client):
        """Define o cliente de rede para envio de comandos"""
        self.network_client = network_client
        self.keyboard_controller.set_network_client(network_client)
        self.slider_controller.set_network_client(network_client)

    def stop(self):
        """Para a interface"""
        if not self.is_running:
            return  # Já parou

        self.is_running = False

        # Se estamos na thread principal do Tkinter, limpa diretamente
        # Senão, agenda para a thread principal
        if hasattr(self, "root") and self.root:
            try:
                # Força execução na thread principal do Tkinter
                self.root.after_idle(self._cleanup_tkinter_resources)
                # Inicia processo de saída
                self.root.quit()
            except:
                # Se falhar, tenta limpeza direta
                self._cleanup_tkinter_resources()
        else:
            # Sem janela ativa, limpa diretamente
            self._cleanup_tkinter_resources()
