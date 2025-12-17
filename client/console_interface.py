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

        # Serial receiver manager (será definido externamente)
        self.serial_receiver = None

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

        # Parâmetros de Force Feedback
        self.ff_damping_var = None
        self.ff_friction_var = None
        self.ff_filter_var = None
        self.ff_sensitivity_var = None

        # Widgets principais
        self.log_text = None
        self.pause_btn = None
        self.brake_balance_scale = None
        self.autoscroll_var = None

        # Atualização
        self.update_interval = 100  # ms

        # Auto-save periódico
        self.auto_save_interval = 20000  # 20 segundos em ms
        self.last_log_count = 0
        self.last_sensor_count = 0

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

        # Parâmetros de Force Feedback (valores padrão 0-100)
        self.ff_damping_var = tk.DoubleVar(value=50.0)  # Damping: reduz oscilações
        self.ff_friction_var = tk.DoubleVar(value=30.0)  # Friction: resistência dos pneus
        self.ff_filter_var = tk.DoubleVar(value=40.0)  # Filter: suavização do sinal
        self.ff_sensitivity_var = tk.DoubleVar(value=75.0)  # Sensitivity: resposta aos eventos

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

        # Serial Port Selector
        self.serial_port_var = tk.StringVar(value="")
        self.serial_status_var = tk.StringVar(value="🔴 Desconectado")
        self.serial_ports_list = []  # Lista de portas disponíveis
        self.port_device_map = {}  # Mapa descrição -> device path

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
            # Monitoramento de Energia
            "current_rpi": tk.StringVar(value="--"),
            "current_servos": tk.StringVar(value="--"),
            "current_motor": tk.StringVar(value="--"),
            "voltage_rpi": tk.StringVar(value="--"),
            "power_rpi": tk.StringVar(value="--"),
            "power_servos": tk.StringVar(value="--"),
            "power_motor": tk.StringVar(value="--"),
            "power_total": tk.StringVar(value="--"),
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

        # Configurar scroll (usa método para proteção)
        self.scrollable_frame.bind("<Configure>", self._on_scrollable_frame_configure)

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
        if not hasattr(self, 'main_canvas'):
            return "break"

        try:
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
        except Exception:
            # Ignora erros durante inicialização ou destruição
            pass

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

    def _on_scrollable_frame_configure(self, event):
        """Handler para configuração do scrollable frame"""
        if hasattr(self, 'main_canvas'):
            try:
                self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
            except Exception:
                # Ignora erros durante inicialização ou destruição
                pass

    def _on_canvas_configure(self, event):
        """Handler para redimensionamento do canvas"""
        # Ajustar largura do frame interno
        if hasattr(self, 'main_canvas') and hasattr(self, 'canvas_window'):
            try:
                canvas_width = event.width
                self.main_canvas.itemconfig(self.canvas_window, width=canvas_width)
            except Exception:
                # Ignora erros durante inicialização ou destruição
                pass

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

        # Energia - Painel de monitoramento de potência
        power_frame = tk.Frame(instruments_inner, bg="#2c2c2c", relief=tk.RAISED, bd=2)
        power_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

        tk.Label(
            power_frame,
            text="⚡ ENERGIA",
            bg="#2c2c2c",
            fg="white",
            font=("Arial", 10, "bold"),
        ).pack(pady=2)

        # Grid para dados de energia
        power_grid = tk.Frame(power_frame, bg="#2c2c2c")
        power_grid.pack(pady=2)

        # Potência total (destaque)
        tk.Label(
            power_grid, text="Total:", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 9)
        ).grid(row=0, column=0, sticky="e", padx=2)
        self.power_total_display = tk.Label(
            power_grid,
            textvariable=self.sensor_vars["power_total"],
            bg="#2c2c2c",
            fg="#ffcc00",
            font=("Arial", 12, "bold"),
        )
        self.power_total_display.grid(row=0, column=1, sticky="w", padx=2)

        # Motor
        tk.Label(
            power_grid, text="Motor:", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
        ).grid(row=1, column=0, sticky="e", padx=2)
        tk.Label(
            power_grid,
            textvariable=self.sensor_vars["power_motor"],
            bg="#2c2c2c",
            fg="#ff6666",
            font=("Arial", 9),
        ).grid(row=1, column=1, sticky="w", padx=2)

        # Servos
        tk.Label(
            power_grid, text="Servos:", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
        ).grid(row=2, column=0, sticky="e", padx=2)
        tk.Label(
            power_grid,
            textvariable=self.sensor_vars["power_servos"],
            bg="#2c2c2c",
            fg="#66ff66",
            font=("Arial", 9),
        ).grid(row=2, column=1, sticky="w", padx=2)

        # RPi
        tk.Label(
            power_grid, text="RPi:", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
        ).grid(row=3, column=0, sticky="e", padx=2)
        tk.Label(
            power_grid,
            textvariable=self.sensor_vars["power_rpi"],
            bg="#2c2c2c",
            fg="#6699ff",
            font=("Arial", 9),
        ).grid(row=3, column=1, sticky="w", padx=2)

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
        """Cria frame com dados do force feedback da direção"""
        ff_frame = ttk.LabelFrame(
            self.left_column, text="🎮 Force Feedback - Direção", style="Dark.TLabelframe"
        )
        ff_frame.pack(fill=tk.X, padx=5, pady=5)

        # Frame interno para melhor organização
        inner_frame = tk.Frame(ff_frame, bg="#3c3c3c")
        inner_frame.pack(padx=10, pady=10, fill=tk.X)

        # === FORÇA NO VOLANTE ===
        steering_frame = tk.Frame(inner_frame, bg="#3c3c3c")
        steering_frame.pack(fill=tk.X, pady=5)

        ttk.Label(steering_frame, text="🎯 Força no Volante:", style="Dark.TLabel", font=("Arial", 10, "bold")).pack(side=tk.LEFT, padx=5)

        # LEDs de direção (esquerda/direita)
        self.ff_led_left = tk.Canvas(steering_frame, width=20, height=20, bg="#3c3c3c", highlightthickness=0)
        self.ff_led_left.pack(side=tk.LEFT, padx=5)
        self.ff_led_left_circle = self.ff_led_left.create_oval(2, 2, 18, 18, fill="#333333", outline="#666666")

        ttk.Label(steering_frame, text="←", style="Dark.TLabel", font=("Arial", 12, "bold")).pack(side=tk.LEFT)

        # Valor da força (0-100%)
        self.steering_ff_intensity = ttk.Label(
            steering_frame,
            text="0",
            style="Dark.TLabel",
            font=("Arial", 14, "bold"),
            foreground="#00ff00"
        )
        self.steering_ff_intensity.pack(side=tk.LEFT, padx=5)

        ttk.Label(steering_frame, text="%", style="Dark.TLabel", font=("Arial", 10)).pack(side=tk.LEFT)

        ttk.Label(steering_frame, text="→", style="Dark.TLabel", font=("Arial", 12, "bold")).pack(side=tk.LEFT, padx=(5, 0))

        self.ff_led_right = tk.Canvas(steering_frame, width=20, height=20, bg="#3c3c3c", highlightthickness=0)
        self.ff_led_right.pack(side=tk.LEFT, padx=5)
        self.ff_led_right_circle = self.ff_led_right.create_oval(2, 2, 18, 18, fill="#333333", outline="#666666")

        # Descrição
        desc_label = tk.Label(
            inner_frame,
            text="Calculado com base em forças laterais (G) e rotação (gyro_z)",
            bg="#3c3c3c",
            fg="#888888",
            font=("Arial", 8),
            justify=tk.LEFT
        )
        desc_label.pack(pady=(0, 5), anchor=tk.W)

        # === COMPONENTES DO CÁLCULO ===
        components_frame = ttk.LabelFrame(
            ff_frame, text="Componentes do Cálculo", style="Dark.TLabelframe"
        )
        components_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        comp_inner = tk.Frame(components_frame, bg="#3c3c3c")
        comp_inner.pack(padx=10, pady=10, fill=tk.X)

        # Força Lateral (G)
        lateral_frame = tk.Frame(comp_inner, bg="#3c3c3c")
        lateral_frame.pack(fill=tk.X, pady=2)

        ttk.Label(lateral_frame, text="↔️ Força Lateral (G):", style="Dark.TLabel").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            lateral_frame,
            textvariable=self.sensor_vars["g_force_lateral"],
            style="Dark.TLabel",
            font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(lateral_frame, text="g", style="Dark.TLabel").pack(side=tk.LEFT)

        # Rotação (Yaw)
        yaw_frame = tk.Frame(comp_inner, bg="#3c3c3c")
        yaw_frame.pack(fill=tk.X, pady=2)

        ttk.Label(yaw_frame, text="🔄 Rotação (gyro_z):", style="Dark.TLabel").pack(side=tk.LEFT, padx=5)
        ttk.Label(
            yaw_frame,
            textvariable=self.sensor_vars["gyro_z"],
            style="Dark.TLabel",
            font=("Arial", 10, "bold")
        ).pack(side=tk.LEFT, padx=5)
        ttk.Label(yaw_frame, text="°/s", style="Dark.TLabel").pack(side=tk.LEFT)

        # Fórmula (informativo)
        formula_label = tk.Label(
            comp_inner,
            text="📊 Fórmula: (|G_lateral| × 50) + (|gyro_z| / 60 × 50)",
            bg="#3c3c3c",
            fg="#4488ff",
            font=("Arial", 8, "italic"),
            justify=tk.LEFT
        )
        formula_label.pack(pady=(5, 0), anchor=tk.W)

        # === PARÂMETROS AJUSTÁVEIS ===
        params_frame = ttk.LabelFrame(
            ff_frame, text="⚙️ Parâmetros de Force Feedback", style="Dark.TLabelframe"
        )
        params_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        params_inner = tk.Frame(params_frame, bg="#3c3c3c")
        params_inner.pack(padx=10, pady=10, fill=tk.X)

        # Slider 1: Damping (Amortecimento)
        damping_frame = tk.Frame(params_inner, bg="#3c3c3c")
        damping_frame.pack(fill=tk.X, pady=5)

        ttk.Label(
            damping_frame,
            text="🔧 Damping (Amortecimento):",
            style="Dark.TLabel",
            font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT, padx=5)

        self.damping_value_label = ttk.Label(
            damping_frame,
            text="50%",
            style="Dark.TLabel",
            font=("Arial", 9)
        )
        self.damping_value_label.pack(side=tk.RIGHT, padx=5)

        damping_slider = tk.Scale(
            params_inner,
            from_=0,
            to=100,
            resolution=5,
            orient=tk.HORIZONTAL,
            variable=self.ff_damping_var,
            command=self._on_ff_damping_change,
            bg="#3c3c3c",
            fg="white",
            highlightbackground="#3c3c3c",
            troughcolor="#2c2c2c",
            activebackground="#4488ff",
            showvalue=0
        )
        damping_slider.pack(fill=tk.X, pady=(0, 2))

        damping_desc = tk.Label(
            params_inner,
            text="Reduz oscilações e vibrações indesejadas no volante",
            bg="#3c3c3c",
            fg="#888888",
            font=("Arial", 7),
            justify=tk.LEFT
        )
        damping_desc.pack(anchor=tk.W, pady=(0, 10))

        # Slider 2: Friction (Atrito)
        friction_frame = tk.Frame(params_inner, bg="#3c3c3c")
        friction_frame.pack(fill=tk.X, pady=5)

        ttk.Label(
            friction_frame,
            text="🏎️ Friction (Atrito):",
            style="Dark.TLabel",
            font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT, padx=5)

        self.friction_value_label = ttk.Label(
            friction_frame,
            text="30%",
            style="Dark.TLabel",
            font=("Arial", 9)
        )
        self.friction_value_label.pack(side=tk.RIGHT, padx=5)

        friction_slider = tk.Scale(
            params_inner,
            from_=0,
            to=100,
            resolution=5,
            orient=tk.HORIZONTAL,
            variable=self.ff_friction_var,
            command=self._on_ff_friction_change,
            bg="#3c3c3c",
            fg="white",
            highlightbackground="#3c3c3c",
            troughcolor="#2c2c2c",
            activebackground="#ff8800",
            showvalue=0
        )
        friction_slider.pack(fill=tk.X, pady=(0, 2))

        friction_desc = tk.Label(
            params_inner,
            text="Simula a resistência dos pneus (grip disponível)",
            bg="#3c3c3c",
            fg="#888888",
            font=("Arial", 7),
            justify=tk.LEFT
        )
        friction_desc.pack(anchor=tk.W, pady=(0, 10))

        # Slider 3: Filter (Filtro)
        filter_frame = tk.Frame(params_inner, bg="#3c3c3c")
        filter_frame.pack(fill=tk.X, pady=5)

        ttk.Label(
            filter_frame,
            text="📊 Filter (Filtro):",
            style="Dark.TLabel",
            font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT, padx=5)

        self.filter_value_label = ttk.Label(
            filter_frame,
            text="40%",
            style="Dark.TLabel",
            font=("Arial", 9)
        )
        self.filter_value_label.pack(side=tk.RIGHT, padx=5)

        filter_slider = tk.Scale(
            params_inner,
            from_=0,
            to=100,
            resolution=5,
            orient=tk.HORIZONTAL,
            variable=self.ff_filter_var,
            command=self._on_ff_filter_change,
            bg="#3c3c3c",
            fg="white",
            highlightbackground="#3c3c3c",
            troughcolor="#2c2c2c",
            activebackground="#00ff00",
            showvalue=0
        )
        filter_slider.pack(fill=tk.X, pady=(0, 2))

        filter_desc = tk.Label(
            params_inner,
            text="Suaviza o sinal para uma experiência mais realista",
            bg="#3c3c3c",
            fg="#888888",
            font=("Arial", 7),
            justify=tk.LEFT
        )
        filter_desc.pack(anchor=tk.W, pady=(0, 10))

        # Slider 4: Sensitivity (Sensibilidade)
        sensitivity_frame = tk.Frame(params_inner, bg="#3c3c3c")
        sensitivity_frame.pack(fill=tk.X, pady=5)

        ttk.Label(
            sensitivity_frame,
            text="⚡ Sensitivity (Sensibilidade):",
            style="Dark.TLabel",
            font=("Arial", 9, "bold")
        ).pack(side=tk.LEFT, padx=5)

        self.sensitivity_value_label = ttk.Label(
            sensitivity_frame,
            text="75%",
            style="Dark.TLabel",
            font=("Arial", 9)
        )
        self.sensitivity_value_label.pack(side=tk.RIGHT, padx=5)

        sensitivity_slider = tk.Scale(
            params_inner,
            from_=0,
            to=100,
            resolution=5,
            orient=tk.HORIZONTAL,
            variable=self.ff_sensitivity_var,
            command=self._on_ff_sensitivity_change,
            bg="#3c3c3c",
            fg="white",
            highlightbackground="#3c3c3c",
            troughcolor="#2c2c2c",
            activebackground="#ff00ff",
            showvalue=0
        )
        sensitivity_slider.pack(fill=tk.X, pady=(0, 2))

        sensitivity_desc = tk.Label(
            params_inner,
            text="Controla a intensidade da resposta aos eventos in-game",
            bg="#3c3c3c",
            fg="#888888",
            font=("Arial", 7),
            justify=tk.LEFT
        )
        sensitivity_desc.pack(anchor=tk.W, pady=(0, 10))

    def create_controls_frame(self):
        """Cria frame de controles"""
        control_frame = ttk.LabelFrame(
            self.right_column, text="🎛️ Controles do Veículo", style="Dark.TLabelframe"
        )
        control_frame.pack(fill=tk.X, padx=5, pady=5)

        # Frame superior para botões
        btn_frame = tk.Frame(control_frame, bg="#3c3c3c")
        btn_frame.pack(fill=tk.X, padx=5, pady=2)

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

    def create_serial_port_selector_frame(self):
        """Cria frame para seleção de porta serial ESP32"""
        serial_frame = ttk.LabelFrame(
            self.left_column, text="🔌 Conexão ESP32 Cockpit", style="Dark.TLabelframe"
        )
        serial_frame.pack(fill=tk.X, padx=5, pady=5)

        # Frame interno para organizar os controles
        inner_frame = tk.Frame(serial_frame, bg="#3c3c3c")
        inner_frame.pack(fill=tk.X, padx=5, pady=5)

        # Status da conexão serial
        status_frame = tk.Frame(inner_frame, bg="#3c3c3c")
        status_frame.pack(fill=tk.X, pady=2)

        ttk.Label(status_frame, text="Status:", style="Dark.TLabel").pack(
            side=tk.LEFT, padx=5
        )
        ttk.Label(
            status_frame, textvariable=self.serial_status_var, style="Dark.TLabel"
        ).pack(side=tk.LEFT)

        # Frame para seleção de porta
        port_frame = tk.Frame(inner_frame, bg="#3c3c3c")
        port_frame.pack(fill=tk.X, pady=5)

        ttk.Label(port_frame, text="Porta Serial:", style="Dark.TLabel").pack(
            side=tk.LEFT, padx=5
        )

        # Combobox para seleção de porta
        self.port_combobox = ttk.Combobox(
            port_frame,
            textvariable=self.serial_port_var,
            state="readonly",
            width=40,
        )
        self.port_combobox.pack(side=tk.LEFT, padx=5)

        # Botão para atualizar lista de portas
        ttk.Button(
            port_frame,
            text="🔄 Atualizar",
            command=self._refresh_serial_ports,
            style="Dark.TButton",
        ).pack(side=tk.LEFT, padx=2)

        # Frame para botões de conexão
        button_frame = tk.Frame(inner_frame, bg="#3c3c3c")
        button_frame.pack(fill=tk.X, pady=2)

        # Botão conectar
        self.connect_btn = ttk.Button(
            button_frame,
            text="🔌 Conectar",
            command=self._connect_serial,
            style="Dark.TButton",
        )
        self.connect_btn.pack(side=tk.LEFT, padx=5)

        # Botão desconectar
        self.disconnect_btn = ttk.Button(
            button_frame,
            text="🔌 Desconectar",
            command=self._disconnect_serial,
            style="Dark.TButton",
            state=tk.DISABLED,
        )
        self.disconnect_btn.pack(side=tk.LEFT, padx=5)

        # Atualizar lista de portas ao iniciar
        self._refresh_serial_ports()

    def _refresh_serial_ports(self):
        """Atualiza lista de portas seriais disponíveis"""
        try:
            if self.serial_receiver:
                # Obter lista de portas disponíveis
                ports = self.serial_receiver.list_available_ports()
                self.serial_ports_list = [port[1] for port in ports]  # Descrições
                self.port_device_map = {port[1]: port[0] for port in ports}  # Mapa descrição -> device

                # Atualizar combobox
                self.port_combobox['values'] = self.serial_ports_list

                # Selecionar primeira porta se disponível
                if self.serial_ports_list and not self.serial_port_var.get():
                    self.serial_port_var.set(self.serial_ports_list[0])

                self.log("INFO", f"Encontradas {len(self.serial_ports_list)} portas seriais")
            else:
                self.log("WARN", "Serial receiver não inicializado")
        except Exception as e:
            self.log("ERROR", f"Erro ao atualizar portas seriais: {e}")

    def _connect_serial(self):
        """Conecta à porta serial selecionada"""
        try:
            if not self.serial_receiver:
                self.log("ERROR", "Serial receiver não inicializado")
                return

            selected_desc = self.serial_port_var.get()
            if not selected_desc:
                self.log("WARN", "Nenhuma porta serial selecionada")
                return

            # Obter device path da descrição
            port_device = self.port_device_map.get(selected_desc)
            if not port_device:
                self.log("ERROR", f"Porta serial inválida: {selected_desc}")
                return

            # Conectar à porta
            self.log("INFO", f"Conectando à porta {port_device}...")
            success = self.serial_receiver.connect_to_port(port_device)

            if success:
                # Iniciar recepção se ainda não estiver rodando
                if not self.serial_receiver.is_running:
                    self.serial_receiver.start()

                # Atualizar status
                self.serial_status_var.set(f"🟢 Conectado - {port_device}")
                self.connect_btn.config(state=tk.DISABLED)
                self.disconnect_btn.config(state=tk.NORMAL)
                self.port_combobox.config(state=tk.DISABLED)
                self.log("INFO", f"Conectado à porta {port_device}")
            else:
                self.serial_status_var.set("🔴 Falha na conexão")
                self.log("ERROR", f"Falha ao conectar à porta {port_device}")

        except Exception as e:
            self.log("ERROR", f"Erro ao conectar: {e}")
            self.serial_status_var.set("🔴 Erro")

    def _disconnect_serial(self):
        """Desconecta da porta serial"""
        try:
            if self.serial_receiver:
                self.log("INFO", "Desconectando porta serial...")
                self.serial_receiver.stop()

                # Atualizar status
                self.serial_status_var.set("🔴 Desconectado")
                self.connect_btn.config(state=tk.NORMAL)
                self.disconnect_btn.config(state=tk.DISABLED)
                self.port_combobox.config(state="readonly")
                self.log("INFO", "Porta serial desconectada")

        except Exception as e:
            self.log("ERROR", f"Erro ao desconectar: {e}")

    def set_serial_receiver(self, serial_receiver):
        """Define o serial receiver manager"""
        self.serial_receiver = serial_receiver

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
            self.left_column, text="📋 Console de Log", style="Dark.TLabelframe"
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
        self.create_serial_port_selector_frame()  # Seletor de porta ESP32
        self.create_instrument_panel()
        self.create_bmi160_frame()
        self.create_force_feedback_frame()
        self.create_log_frame()  # Console de log movido para cá

        # Coluna Direita
        self.create_video_frame()
        self.create_slider_controls_frame()
        self.create_controls_frame()
        self.create_keyboard_controls_frame()

        # Conecta video_display se já foi definido
        if hasattr(self, "video_display") and self.video_display:
            if hasattr(self.video_display, "set_tkinter_label"):
                self.video_display.set_tkinter_label(self.video_label)
            if hasattr(self.video_display, "set_status_callback"):
                self.video_display.set_status_callback(self.update_video_status)

    # Limite máximo de linhas no console de log
    MAX_LOG_LINES = 5000
    AUTO_EXPORT_DIR = "exports/auto"

    def _auto_export_on_limit(self):
        """Exporta automaticamente logs e dados quando o limite é atingido"""
        try:
            import os
            from datetime import datetime

            # Cria diretório de export automático se não existir
            os.makedirs(self.AUTO_EXPORT_DIR, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # 1. Exporta logs do console
            log_filename = os.path.join(self.AUTO_EXPORT_DIR, f"logs_{timestamp}.txt")
            try:
                log_content = self.log_text.get("1.0", tk.END)
                with open(log_filename, "w", encoding="utf-8") as f:
                    f.write(f"# F1 Client - Auto Export (Limite atingido)\n")
                    f.write(f"# Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                    f.write(f"# Linhas: {self.MAX_LOG_LINES}\n")
                    f.write("#" + "=" * 60 + "\n\n")
                    f.write(log_content)
            except Exception as e:
                print(f"Erro ao exportar logs: {e}")

            # 2. Exporta dados de sensores (Pickle - mais rápido que CSV)
            if self.sensor_display:
                sensor_filename = os.path.join(self.AUTO_EXPORT_DIR, f"sensors_{timestamp}.pkl")
                try:
                    self.sensor_display.export_history_fast(sensor_filename)
                except Exception:
                    pass

            # Log discreto (não vai para o console principal para evitar loop)
            print(f"[AUTO-EXPORT] Dados salvos em: {self.AUTO_EXPORT_DIR}/")

        except Exception as e:
            print(f"[AUTO-EXPORT] Erro: {e}")

    def _periodic_auto_save(self):
        """Auto-save periódico a cada 10 segundos (apenas se houver dados novos)"""
        if not self.is_running:
            return

        try:
            has_new_data = False

            # Verifica se há novos logs
            current_log_count = 0
            if hasattr(self, 'log_text') and self.log_text:
                try:
                    current_log_count = int(self.log_text.index('end-1c').split('.')[0])
                except:
                    pass

            # Verifica se há novos dados de sensores
            current_sensor_count = 0
            if self.sensor_display and hasattr(self.sensor_display, 'history'):
                try:
                    current_sensor_count = len(self.sensor_display.history.get("timestamp", []))
                except:
                    pass

            # Só salva se houver dados significativos (mínimo 10 logs ou 100 sensores)
            MIN_LOGS = 10
            MIN_SENSORS = 100

            if (current_log_count >= MIN_LOGS or current_sensor_count >= MIN_SENSORS) and \
               (current_log_count > self.last_log_count or current_sensor_count > self.last_sensor_count):
                has_new_data = True
                self.last_log_count = current_log_count
                self.last_sensor_count = current_sensor_count

            if has_new_data:
                import os
                from datetime import datetime

                os.makedirs(self.AUTO_EXPORT_DIR, exist_ok=True)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

                # Salva logs
                if current_log_count > 0:
                    log_filename = os.path.join(self.AUTO_EXPORT_DIR, f"logs_{timestamp}.txt")
                    try:
                        log_content = self.log_text.get("1.0", tk.END)
                        with open(log_filename, "w", encoding="utf-8") as f:
                            f.write(f"# F1 Client - Auto Save (10s)\n")
                            f.write(f"# Data: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                            f.write(f"# Linhas: {current_log_count}\n")
                            f.write("#" + "=" * 60 + "\n\n")
                            f.write(log_content)
                    except:
                        pass

                # Salva sensores
                if current_sensor_count > 0 and self.sensor_display:
                    sensor_filename = os.path.join(self.AUTO_EXPORT_DIR, f"sensors_{timestamp}.pkl")
                    try:
                        self.sensor_display.export_history_fast(sensor_filename)
                    except:
                        pass

                print(f"[AUTO-SAVE] {current_log_count} logs, {current_sensor_count} sensores -> {self.AUTO_EXPORT_DIR}/")

                # Reset após salvar para não duplicar dados
                try:
                    # Limpa console de logs
                    if self.log_text:
                        self.log_text.delete('1.0', tk.END)
                    # Reseta histórico de sensores
                    if self.sensor_display:
                        self.sensor_display.reset_statistics()
                    # Reseta contadores
                    self.last_log_count = 0
                    self.last_sensor_count = 0
                except:
                    pass

        except Exception as e:
            print(f"[AUTO-SAVE] Erro: {e}")

        # Reagenda próximo auto-save
        if self.is_running and self.root:
            try:
                self.root.after(self.auto_save_interval, self._periodic_auto_save)
            except:
                pass

    def log(self, level, message):
        """Adiciona mensagem ao log"""
        if self.paused:
            return

        # Verifica se log_text existe e está válido
        if not hasattr(self, 'log_text') or self.log_text is None:
            return

        try:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]  # Inclui milissegundos

            # Adiciona ao log
            self.log_text.insert(tk.END, f"[{timestamp}] ", "TIMESTAMP")
            self.log_text.insert(tk.END, f"[{level}] ", level)
            self.log_text.insert(tk.END, f"{message}\n", level)

            # Limita número de linhas para evitar uso excessivo de memória
            line_count = int(self.log_text.index('end-1c').split('.')[0])
            if line_count > self.MAX_LOG_LINES:
                # Auto-export antes de limpar
                self._auto_export_on_limit()
                # Remove as primeiras 500 linhas quando exceder o limite
                self.log_text.delete('1.0', '501.0')

            # Auto-scroll se habilitado
            if hasattr(self, 'autoscroll_var') and self.autoscroll_var.get():
                self.log_text.see(tk.END)
        except Exception:
            # Ignora erros durante destruição da interface
            pass

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

        # Calcular forças G e force feedback localmente
        self._calculate_g_forces_and_ff(sensor_data)

        # Atualizar LEDs de force feedback (IMPORTANTE: alta taxa de atualização)
        ff_intensity = sensor_data.get("steering_feedback_intensity", 0.0)
        ff_direction = sensor_data.get("steering_feedback_direction", "neutral")
        self.update_ff_leds(ff_intensity, ff_direction)

        # Enviar comando FF para ESP32 via serial
        self.send_ff_command(ff_intensity, ff_direction)

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
            # Monitoramento de Energia
            "current_rpi": "current_rpi",
            "current_servos": "current_servos",
            "current_motor": "current_motor",
            "voltage_rpi": "voltage_rpi",
            "power_rpi": "power_rpi",
            "power_servos": "power_servos",
            "power_motor": "power_motor",
            "power_total": "power_total",
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
                elif var_name in ["current_rpi", "current_servos", "current_motor"]:
                    formatted_value = f"{value:.2f}A"
                elif var_name in ["voltage_rpi"]:
                    formatted_value = f"{value:.2f}V"
                elif var_name in ["power_rpi", "power_servos", "power_motor", "power_total"]:
                    formatted_value = f"{value:.1f}W"
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

    def _calculate_g_forces_and_ff(self, sensor_data):
        """
        Calcula forças G e force feedback localmente baseado em dados raw do BMI160

        Args:
            sensor_data (dict): Dados dos sensores incluindo aceleração e giroscópio raw
        """
        try:
            # Obtém dados de aceleração em m/s² (já convertidos pelo Raspberry Pi)
            accel_x = sensor_data.get("bmi160_accel_x", 0.0)  # Frontal (frente/trás)
            accel_y = sensor_data.get("bmi160_accel_y", 0.0)  # Lateral (esquerda/direita)
            accel_z = sensor_data.get("bmi160_accel_z", 9.81)  # Vertical (cima/baixo)

            # Obtém dados de giroscópio em °/s (já convertidos pelo Raspberry Pi)
            gyro_z = sensor_data.get("bmi160_gyro_z", 0.0)  # Rotação (yaw)

            # === CALCULA FORÇAS G ===
            # Divide pela gravidade padrão (9.81 m/s²) para converter para G
            g_force_frontal = accel_x / 9.81  # Aceleração/frenagem
            g_force_lateral = accel_y / 9.81  # Curvas
            g_force_vertical = (accel_z - 9.81) / 9.81  # Solavancos (remove gravidade base)

            # Armazena forças G calculadas de volta no sensor_data
            sensor_data["g_force_frontal"] = g_force_frontal
            sensor_data["g_force_lateral"] = g_force_lateral
            sensor_data["g_force_vertical"] = g_force_vertical

            # === CALCULA FORCE FEEDBACK DA DIREÇÃO ===
            # Componente 1: Força lateral (curvas)
            # Quanto maior a força G lateral, mais resistência no volante
            lateral_component = min(abs(g_force_lateral) * 50, 100)

            # Componente 2: Rotação (yaw)
            # Quanto mais rápido estiver girando, mais força no volante
            yaw_component = min(abs(gyro_z) / 60.0 * 50, 50)

            # Componente 3: Ângulo da direção (centering spring)
            # Quanto mais afastado do centro, mais força para retornar
            # steering_value vai de -100% (esquerda) a +100% (direita)
            steering_value = sensor_data.get("steering", 0)  # -100 a +100
            steering_angle_ratio = abs(steering_value) / 100.0  # 0.0 a 1.0
            centering_component = steering_angle_ratio * 40  # 0-40% baseado no ângulo

            # Força base combinada (0-100%)
            base_steering_ff = min(lateral_component + yaw_component + centering_component, 100)

            # === APLICA PARÂMETROS DE FF (SLIDERS) ===
            # Obtém valores dos sliders (0-100%)
            damping = self.ff_damping_var.get() / 100.0  # 0.0 a 1.0
            friction = self.ff_friction_var.get() / 100.0  # 0.0 a 1.0
            filter_strength = self.ff_filter_var.get() / 100.0  # 0.0 a 1.0
            sensitivity = self.ff_sensitivity_var.get() / 100.0  # 0.0 a 1.0

            # PASSO 1: Aplica sensibilidade (multiplica a força base)
            # Sensitivity controla a magnitude geral da resposta
            adjusted_ff = base_steering_ff * sensitivity

            # PASSO 2: Aplica friction (resistência proporcional à velocidade de rotação)
            # Friction simula o atrito dos pneus - quanto mais rápido gira, mais resistência
            friction_force = min(abs(gyro_z) / 100.0, 1.0) * friction * 30  # 0-30% extra
            adjusted_ff = min(adjusted_ff + friction_force, 100.0)

            # PASSO 3: Aplica filter (suavização exponencial - ANTES do damping)
            # Filter remove ruídos de alta frequência do sensor
            if hasattr(self, '_filtered_steering_ff'):
                adjusted_ff = adjusted_ff * (1.0 - filter_strength) + self._filtered_steering_ff * filter_strength
            self._filtered_steering_ff = adjusted_ff

            # PASSO 4: Aplica damping (reduz mudanças bruscas - média móvel)
            # Damping simula inércia do sistema - suaviza transições
            if hasattr(self, '_last_steering_ff'):
                adjusted_ff = adjusted_ff * (1.0 - damping) + self._last_steering_ff * damping
            self._last_steering_ff = adjusted_ff

            # Limita ao intervalo 0-100%
            final_steering_ff = max(0.0, min(100.0, adjusted_ff))

            # Determina direção do force feedback
            # A direção é determinada por TRÊS fatores:

            # 1. Centering force: Sempre puxa para o centro (oposto ao ângulo atual)
            #    Se volante está à esquerda (negativo), força puxa para direita (positiva)
            #    Se volante está à direita (positivo), força puxa para esquerda (negativa)
            centering_direction_value = -steering_value  # Inverte o sinal

            # 2. Força lateral: Resiste ao movimento (mesma direção da força G)
            lateral_direction_value = g_force_lateral * 10  # Amplifica para dar peso

            # 3. Rotação (yaw): Resiste à rotação
            yaw_direction_value = gyro_z

            # Combina os três fatores para determinar direção final
            total_direction_value = centering_direction_value + lateral_direction_value + yaw_direction_value

            # Determina direção baseado no valor combinado
            # Positivo = direita, Negativo = esquerda
            if total_direction_value > 5:
                direction = "right"
            elif total_direction_value < -5:
                direction = "left"
            else:
                direction = "neutral"

            # Se a força for muito pequena, considera neutro
            if final_steering_ff < 5.0:
                direction = "neutral"

            # Armazena force feedback calculado de volta no sensor_data
            sensor_data["steering_feedback_intensity"] = final_steering_ff
            sensor_data["steering_feedback_direction"] = direction

            # Outros force feedbacks (ainda não implementados - valores placeholder)
            sensor_data["brake_pedal_resistance"] = 0.0
            sensor_data["seat_vibration_intensity"] = 0.0
            sensor_data["seat_tilt_x"] = 0.0
            sensor_data["seat_tilt_y"] = 0.0

        except Exception as e:
            error(f"Erro ao calcular forças G e force feedback: {e}", "CONSOLE")

    def update_ff_leds(self, intensity: float, direction: str):
        """
        Atualiza LEDs de direção do force feedback

        Args:
            intensity: Intensidade da força (0-100%)
            direction: Direção da força ("left", "right", "neutral")
        """
        try:
            # Atualiza valor numérico
            self.steering_ff_intensity.config(text=f"{int(intensity)}")

            # Cor baseada na intensidade
            if intensity < 30:
                color = "#00ff00"  # Verde (baixo)
            elif intensity < 70:
                color = "#ffaa00"  # Laranja (médio)
            else:
                color = "#ff0000"  # Vermelho (alto)

            self.steering_ff_intensity.config(foreground=color)

            # Atualiza LEDs
            if direction == "left":
                # LED esquerdo LIGADO (amarelo/laranja)
                self.ff_led_left.itemconfig(self.ff_led_left_circle, fill="#ffaa00", outline="#ff8800")
                # LED direito DESLIGADO
                self.ff_led_right.itemconfig(self.ff_led_right_circle, fill="#333333", outline="#666666")
            elif direction == "right":
                # LED esquerdo DESLIGADO
                self.ff_led_left.itemconfig(self.ff_led_left_circle, fill="#333333", outline="#666666")
                # LED direito LIGADO (azul/ciano)
                self.ff_led_right.itemconfig(self.ff_led_right_circle, fill="#00aaff", outline="#0088ff")
            else:  # neutral
                # Ambos os LEDs DESLIGADOS
                self.ff_led_left.itemconfig(self.ff_led_left_circle, fill="#333333", outline="#666666")
                self.ff_led_right.itemconfig(self.ff_led_right_circle, fill="#333333", outline="#666666")

        except Exception as e:
            error(f"Erro ao atualizar LEDs de FF: {e}", "CONSOLE")

    def send_ff_command(self, intensity: float, direction: str):
        """
        Envia comando de Force Feedback para o ESP32 via serial

        Args:
            intensity: Intensidade da força (0-100%)
            direction: Direção da força ("left", "right", "neutral")

        Formato do comando: FF_MOTOR:direction:intensity
        Exemplos:
            FF_MOTOR:LEFT:45    - Força de 45% para a esquerda
            FF_MOTOR:RIGHT:80   - Força de 80% para a direita
            FF_MOTOR:NEUTRAL:0  - Sem força (motor parado)
        """
        try:
            # Converte direção para maiúsculas
            direction_upper = direction.upper()

            # Formata intensidade como inteiro
            intensity_int = int(intensity)

            # Cria comando
            command = f"FF_MOTOR:{direction_upper}:{intensity_int}"

            # Envia via serial (se disponível)
            if hasattr(self, 'serial_manager') and self.serial_manager:
                self.serial_manager.send_command(command)

        except Exception as e:
            # Não loga erro para não poluir o console (alta frequência de envio)
            pass

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

            # Inicia auto-save periódico (a cada 10s)
            self.root.after(self.auto_save_interval, self._periodic_auto_save)

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

    def _on_ff_damping_change(self, value):
        """Callback quando o slider de damping muda"""
        try:
            damping = float(value)
            self.damping_value_label.config(text=f"{damping:.0f}%")
            debug(f"Damping alterado: {damping:.0f}%", "FF")
            # Parâmetro armazenado localmente - não envia para Raspberry Pi
        except Exception as e:
            error(f"Erro ao alterar damping: {e}", "FF")

    def _on_ff_friction_change(self, value):
        """Callback quando o slider de friction muda"""
        try:
            friction = float(value)
            self.friction_value_label.config(text=f"{friction:.0f}%")
            debug(f"Friction alterado: {friction:.0f}%", "FF")
            # Parâmetro armazenado localmente - não envia para Raspberry Pi
        except Exception as e:
            error(f"Erro ao alterar friction: {e}", "FF")

    def _on_ff_filter_change(self, value):
        """Callback quando o slider de filter muda"""
        try:
            filter_val = float(value)
            self.filter_value_label.config(text=f"{filter_val:.0f}%")
            debug(f"Filter alterado: {filter_val:.0f}%", "FF")
            # Parâmetro armazenado localmente - não envia para Raspberry Pi
        except Exception as e:
            error(f"Erro ao alterar filter: {e}", "FF")

    def _on_ff_sensitivity_change(self, value):
        """Callback quando o slider de sensitivity muda"""
        try:
            sensitivity = float(value)
            self.sensitivity_value_label.config(text=f"{sensitivity:.0f}%")
            debug(f"Sensitivity alterado: {sensitivity:.0f}%", "FF")
            # Parâmetro armazenado localmente - não envia para Raspberry Pi
        except Exception as e:
            error(f"Erro ao alterar sensitivity: {e}", "FF")

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
