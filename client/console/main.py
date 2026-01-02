"""
console/main.py - Interface Gráfica do Console (Refatorada)
Interface principal com dados de sensores, logs e controles

FUNCIONALIDADES:
===============
- Status da conexão em tempo real
- Dados completos do BMI160 (37+ campos)
- Console de logs com cores
- Controles de pausa/limpeza
- Estatísticas de rede
- Área para controles futuros
- Interface responsiva e amigável

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
from datetime import datetime
from tkinter import ttk

from keyboard_controller import KeyboardController
from simple_logger import debug, error
from slider_controller import SliderController

from .frames.bmi160 import create_bmi160_frame

# Imports dos módulos locais
from .frames.connection_status import create_connection_status_frame
from .frames.controls import create_controls_frame
from .frames.force_feedback import create_force_feedback_frame
from .frames.instrument_panel import create_instrument_panel
from .frames.log import create_log_frame
from .frames.serial_port import create_serial_port_selector_frame
from .frames.telemetry_plotter import F1TelemetryPlotter
from .frames.video import create_video_frame
from .logic.auto_save import AutoSaveManager
from .logic.force_feedback_calc import ForceFeedbackCalculator
from .logic.velocity_calc import VelocityCalculator
from .utils.constants import (
    AUTO_SAVE_INTERVAL,
    BRAKE_BALANCE_DEFAULT,
    FF_DAMPING_DEFAULT,
    FF_FILTER_DEFAULT,
    FF_FRICTION_DEFAULT,
    FF_SENSITIVITY_DEFAULT,
    MAX_LOG_LINES,
    UPDATE_INTERVAL,
)


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
        self.update_interval = UPDATE_INTERVAL

        # Auto-save periódico
        self.auto_save_interval = AUTO_SAVE_INTERVAL

        # Calculadores de lógica (serão inicializados após criar variáveis)
        self.ff_calculator = None
        self.velocity_calculator = None
        self.auto_save_manager = None
        self.telemetry_plotter = None

    def create_tkinter_variables(self):
        """Cria variáveis do Tkinter"""
        # Status da conexão
        self.connection_var = tk.StringVar(value="Desconectado")
        self.fps_var = tk.StringVar(value="0.0")
        self.frame_size_var = tk.StringVar(value="0 KB")
        self.packets_var = tk.StringVar(value="0")
        self.data_var = tk.StringVar(value="0 MB")
        self.quality_var = tk.StringVar(value="100%")

        # Controles de veículo
        self.brake_balance_var = tk.DoubleVar(value=BRAKE_BALANCE_DEFAULT)

        # Parâmetros de Force Feedback
        self.ff_damping_var = tk.DoubleVar(value=FF_DAMPING_DEFAULT)
        self.ff_friction_var = tk.DoubleVar(value=FF_FRICTION_DEFAULT)
        self.ff_filter_var = tk.DoubleVar(value=FF_FILTER_DEFAULT)
        self.ff_sensitivity_var = tk.DoubleVar(value=FF_SENSITIVITY_DEFAULT)

        # Instrumentos do motor
        self.rpm_var = tk.StringVar(value="0")
        self.gear_var = tk.StringVar(value="1")
        self.throttle_var = tk.StringVar(value="0.0")
        self.speed_var = tk.StringVar(value="0.0")

        # Serial Port Selector
        self.serial_port_var = tk.StringVar(value="")
        self.serial_status_var = tk.StringVar(value="Desconectado")
        self.serial_ports_list = []
        self.port_device_map = {}

        # Dados dos sensores BMI160
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
            # Dados do sensor de temperatura DS18B20
            "temperature_c": tk.StringVar(value="--"),
            "temperature_f": tk.StringVar(value="--"),
            "temperature_k": tk.StringVar(value="--"),
            "thermal_status": tk.StringVar(value="NORMAL"),
            # Monitoramento de Energia
            "current_rpi": tk.StringVar(value="--"),
            "current_servos": tk.StringVar(value="--"),
            "current_motor": tk.StringVar(value="--"),
            "voltage_rpi": tk.StringVar(value="--"),
            "voltage_battery": tk.StringVar(value="--"),
            "battery_percentage": tk.StringVar(value="--"),
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

        # Inicializa calculadores de lógica
        self.ff_calculator = ForceFeedbackCalculator(self)
        self.velocity_calculator = VelocityCalculator(self)
        self.auto_save_manager = AutoSaveManager(self)

    def create_main_window(self):
        """Cria janela principal com scroll vertical e layout em grid"""
        self.root = tk.Tk()
        self.root.title("F1 Car - Console de Controle")
        self.root.geometry("1400x1000")
        self.root.configure(bg="#2b2b2b")

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
        self.main_canvas.bind("<MouseWheel>", self._on_mousewheel)
        self.main_canvas.bind("<Button-4>", self._on_mousewheel)
        self.main_canvas.bind("<Button-5>", self._on_mousewheel)
        self.root.bind("<MouseWheel>", self._on_mousewheel)
        self.root.bind("<Button-4>", self._on_mousewheel)
        self.root.bind("<Button-5>", self._on_mousewheel)

        # Bind para redimensionamento da janela
        self.main_canvas.bind("<Configure>", self._on_canvas_configure)

        # Aplicar scroll a todos os widgets após criação da interface
        self.root.after(100, self._bind_mousewheel_to_all)

    def _on_mousewheel(self, event):
        """Handler para scroll com mouse wheel (multiplataforma)"""
        if not hasattr(self, "main_canvas"):
            return "break"

        try:
            if hasattr(event, "delta"):
                delta = int(-1 * (event.delta / 120))
            elif hasattr(event, "num"):
                delta = -1 if event.num == 4 else 1
            else:
                delta = 1

            self.main_canvas.yview_scroll(delta * 3, "units")
        except Exception:
            pass

        return "break"

    def _bind_mousewheel_to_all(self):
        """Aplica scroll do mouse a todos os widgets da interface"""

        def bind_to_widget(widget):
            try:
                widget.bind("<MouseWheel>", self._on_mousewheel, add="+")
                widget.bind("<Button-4>", self._on_mousewheel, add="+")
                widget.bind("<Button-5>", self._on_mousewheel, add="+")
            except tk.TclError:
                pass

            try:
                for child in widget.winfo_children():
                    bind_to_widget(child)
            except tk.TclError:
                pass

        bind_to_widget(self.root)

    def _on_scrollable_frame_configure(self, event):
        """Handler para configuração do scrollable frame"""
        if hasattr(self, "main_canvas"):
            try:
                self.main_canvas.configure(scrollregion=self.main_canvas.bbox("all"))
            except Exception:
                pass

    def _on_canvas_configure(self, event):
        """Handler para redimensionamento do canvas"""
        if hasattr(self, "main_canvas") and hasattr(self, "canvas_window"):
            try:
                canvas_width = event.width
                self.main_canvas.itemconfig(self.canvas_window, width=canvas_width)
            except Exception:
                pass

    def create_widgets(self):
        """Cria todos os widgets da interface"""
        # Coluna Esquerda
        create_connection_status_frame(self)
        create_serial_port_selector_frame(self)
        create_instrument_panel(self)
        create_bmi160_frame(self)
        create_force_feedback_frame(self)
        create_log_frame(self)

        # Coluna Direita
        create_video_frame(self)
        self.create_telemetry_frame()  # Gráficos F1 abaixo do vídeo
        self.create_slider_controls_frame()
        create_controls_frame(self)
        self.create_keyboard_controls_frame()

        # Conecta video_display se já foi definido
        if hasattr(self, "video_display") and self.video_display:
            if hasattr(self.video_display, "set_tkinter_label"):
                self.video_display.set_tkinter_label(self.video_label)
            if hasattr(self.video_display, "set_status_callback"):
                self.video_display.set_status_callback(self.update_video_status)

    def create_telemetry_frame(self):
        """Cria frame com gráficos de telemetria F1"""
        try:
            self.telemetry_plotter = F1TelemetryPlotter(
                max_points=500, update_interval=100  # 10Hz de atualização dos gráficos
            )
            telemetry_frame = self.telemetry_plotter.create_frame(self.right_column)
            telemetry_frame.pack(fill=tk.X, padx=5, pady=5)
        except Exception as e:
            error(f"Erro ao criar frame de telemetria: {e}", "CONSOLE")

    def create_slider_controls_frame(self):
        """Cria frame com controles de sliders"""
        slider_frame = self.slider_controller.create_control_frame(self.right_column)
        slider_frame.pack(fill=tk.X, padx=5, pady=5)

    def create_keyboard_controls_frame(self):
        """Cria frame com controles de teclado"""
        keyboard_frame = self.keyboard_controller.create_status_frame(self.right_column)
        keyboard_frame.pack(fill=tk.X, padx=5, pady=5)

    def set_video_display(self, video_display):
        """Define o video_display para integração"""
        self.video_display = video_display

    def update_video_status(self, status_dict):
        """Atualiza status do vídeo"""
        if hasattr(self, "video_status_var"):
            if status_dict.get("connected", False):
                fps = status_dict.get("fps", 0)
                self.video_status_var.set(f"Conectado ({fps:.1f} FPS)")
            else:
                self.video_status_var.set("Desconectado")

        if hasattr(self, "video_resolution_var"):
            width = status_dict.get("width", 0)
            height = status_dict.get("height", 0)
            if width > 0 and height > 0:
                self.video_resolution_var.set(f"{width}x{height}")
            else:
                self.video_resolution_var.set("N/A")

    def set_serial_receiver(self, serial_receiver):
        """Define o serial receiver manager"""
        self.serial_receiver = serial_receiver

    def _refresh_serial_ports(self):
        """Atualiza lista de portas seriais disponíveis"""
        try:
            if self.serial_receiver:
                ports = self.serial_receiver.list_available_ports()
                self.serial_ports_list = [port[1] for port in ports]
                self.port_device_map = {port[1]: port[0] for port in ports}

                self.port_combobox["values"] = self.serial_ports_list

                if self.serial_ports_list and not self.serial_port_var.get():
                    self.serial_port_var.set(self.serial_ports_list[0])

                self.log(
                    "INFO", f"Encontradas {len(self.serial_ports_list)} portas seriais"
                )
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

            port_device = self.port_device_map.get(selected_desc)
            if not port_device:
                self.log("ERROR", f"Porta serial inválida: {selected_desc}")
                return

            self.log("INFO", f"Conectando à porta {port_device}...")
            success = self.serial_receiver.connect_to_port(port_device)

            if success:
                if not self.serial_receiver.is_running:
                    self.serial_receiver.start()

                self.serial_status_var.set(f"Conectado - {port_device}")
                self.connect_btn.config(state=tk.DISABLED)
                self.disconnect_btn.config(state=tk.NORMAL)
                self.port_combobox.config(state=tk.DISABLED)
                self.log("INFO", f"Conectado à porta {port_device}")
            else:
                self.serial_status_var.set("Falha na conexão")
                self.log("ERROR", f"Falha ao conectar à porta {port_device}")

        except Exception as e:
            self.log("ERROR", f"Erro ao conectar: {e}")
            self.serial_status_var.set("Erro")

    def _disconnect_serial(self):
        """Desconecta da porta serial"""
        try:
            if self.serial_receiver:
                self.log("INFO", "Desconectando porta serial...")
                self.serial_receiver.stop()

                self.serial_status_var.set("Desconectado")
                self.connect_btn.config(state=tk.NORMAL)
                self.disconnect_btn.config(state=tk.DISABLED)
                self.port_combobox.config(state="readonly")
                self.log("INFO", "Porta serial desconectada")

        except Exception as e:
            self.log("ERROR", f"Erro ao desconectar: {e}")

    def log(self, level, message):
        """Adiciona mensagem ao log"""
        if self.paused:
            return

        if not hasattr(self, "log_text") or self.log_text is None:
            return

        try:
            timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

            self.log_text.insert(tk.END, f"[{timestamp}] ", "TIMESTAMP")
            self.log_text.insert(tk.END, f"[{level}] ", level)
            self.log_text.insert(tk.END, f"{message}\n", level)

            # Limita número de linhas
            line_count = int(self.log_text.index("end-1c").split(".")[0])
            if line_count > MAX_LOG_LINES:
                self.auto_save_manager.auto_export_on_limit()
                self.log_text.delete("1.0", "501.0")

            # Auto-scroll se habilitado
            if hasattr(self, "autoscroll_var") and self.autoscroll_var.get():
                self.log_text.see(tk.END)
        except Exception:
            pass

    def update_connection_status(self, status_dict):
        """Atualiza status de conexão"""
        if "connection" in status_dict:
            connection_text = status_dict["connection"]
            if "Conectado" in connection_text:
                self.connection_var.set(f"Conectado - {connection_text}")
            else:
                self.connection_var.set(f"Desconectado - {connection_text}")

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
            self.quality_var.set(f"{quality:.1f}%")

    def update_sensor_data(self, sensor_data):
        """Atualiza dados dos sensores"""
        # Calcular velocidade baseada no BMI160
        self.velocity_calculator.calculate_velocity(sensor_data)

        # Calcular forças G e force feedback
        self.ff_calculator.calculate_g_forces_and_ff(sensor_data)

        # Atualizar LEDs de force feedback
        ff_intensity = sensor_data.get("steering_feedback_intensity", 0.0)
        ff_direction = sensor_data.get("steering_feedback_direction", "neutral")
        self.ff_calculator.update_ff_leds(ff_intensity, ff_direction)

        # Enviar comando FF para ESP32 via serial
        self.ff_calculator.send_ff_command(ff_intensity, ff_direction)

        # Atualizar dados do motor
        self._update_motor_display(sensor_data)

        # Atualizar gráficos de telemetria F1
        if self.telemetry_plotter:
            self.telemetry_plotter.update_data(sensor_data)

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
            # Temperatura
            "temperature_c": "temperature_c",
            "temperature_f": "temperature_f",
            "temperature_k": "temperature_k",
            "thermal_status": "thermal_status",
            # Energia
            "current_rpi": "current_rpi",
            "current_servos": "current_servos",
            "current_motor": "current_motor",
            "voltage_rpi": "voltage_rpi",
            "voltage_battery": "voltage_battery",
            "battery_percentage": "battery_percentage",
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

                # Formatação especial
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
                    formatted_value = f"{value:+.3f}"
                elif var_name in ["temperature_c", "temperature_f", "temperature_k"]:
                    formatted_value = f"{value:.1f}"
                elif var_name in ["current_rpi", "current_servos", "current_motor"]:
                    formatted_value = f"{value:.2f}A"
                elif var_name in ["voltage_rpi", "voltage_battery"]:
                    formatted_value = f"{value:.2f}V"
                elif var_name in ["battery_percentage"]:
                    formatted_value = f"{value:.0f}%"
                elif var_name in [
                    "power_rpi",
                    "power_servos",
                    "power_motor",
                    "power_total",
                ]:
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

        # Atualiza cores de temperatura e bateria
        self._update_temperature_colors(sensor_data)
        self._update_battery_colors(sensor_data)

    def _update_battery_colors(self, sensor_data):
        """Atualiza as cores do display de bateria baseado na porcentagem de carga"""
        try:
            if hasattr(self, "battery_voltage_display") and hasattr(
                self, "battery_pct_display"
            ):
                battery_pct = sensor_data.get("battery_percentage", 100)

                # Cores baseadas na porcentagem
                # >50% = verde, 25-50% = amarelo, <25% = vermelho
                if battery_pct > 50:
                    color = "#00ff00"  # Verde
                elif battery_pct > 25:
                    color = "#ffaa00"  # Amarelo/Laranja
                elif battery_pct > 10:
                    color = "#ff4444"  # Vermelho
                else:
                    color = "#ff0000"  # Vermelho intenso (crítico)

                self.battery_voltage_display.config(fg=color)
                self.battery_pct_display.config(fg=color)

                # Pisca em vermelho se bateria crítica (<10%)
                if battery_pct <= 10:
                    current_color = self.battery_voltage_display.cget("fg")
                    flash_color = "#ffffff" if current_color != "#ffffff" else color
                    self.root.after(
                        500, lambda: self.battery_voltage_display.config(fg=flash_color)
                    )
                    self.root.after(
                        500, lambda: self.battery_pct_display.config(fg=flash_color)
                    )

        except Exception as e:
            error(f"Erro ao atualizar cores de bateria: {e}", "CONSOLE")

    def _update_temperature_colors(self, sensor_data):
        """Atualiza as cores do display de temperatura baseado no status térmico"""
        try:
            if hasattr(self, "temp_display"):
                thermal_status = sensor_data.get("thermal_status", "NORMAL")

                color_mapping = {
                    "NORMAL": "#00ff88",
                    "WARNING": "#ffaa00",
                    "CRITICAL": "#ff4444",
                    "CRITICAL_SHUTDOWN": "#ff0000",
                }

                color = color_mapping.get(thermal_status, "#00ff88")
                self.temp_display.config(fg=color)

                if thermal_status in ["CRITICAL", "CRITICAL_SHUTDOWN"]:
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
            # rpm_display = % dentro da zona IDEAL (calculado no RPi)
            if "rpm_display" in sensor_data:
                rpm = sensor_data["rpm_display"]
                self.rpm_var.set(f"{rpm:.0f}")

            if "current_gear" in sensor_data:
                gear = sensor_data["current_gear"]
                self.gear_var.set(str(gear))

            if "current_pwm" in sensor_data:
                throttle = sensor_data["current_pwm"]
                self.throttle_var.set(f"{throttle:.1f}%")

        except Exception as e:
            error(f"Erro ao atualizar painel de instrumentos: {e}", "CONSOLE")

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
        text = "Continuar" if self.paused else "Pausar"
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
        except Exception:
            pass

    def run_interface(self):
        """Executa a interface principal"""
        try:
            self.create_main_window()
            self.create_tkinter_variables()
            self.create_widgets()

            self.is_running = True

            # Inicia processamento de filas
            self.root.after(self.update_interval, self.process_queues)

            # Inicia auto-save periódico
            self.root.after(
                self.auto_save_interval, self.auto_save_manager.periodic_auto_save
            )

            # Configura controles de teclado
            self.keyboard_controller.bind_to_widget(self.root)
            self.keyboard_controller.start()

            # Inicia controlador de sliders
            self.slider_controller.start()

            # Inicia gráficos de telemetria F1
            if self.telemetry_plotter:
                self.telemetry_plotter.start(self.root)

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
            except Exception:
                pass
        finally:
            self._cleanup_tkinter_resources()

    def _cleanup_tkinter_resources(self):
        """Limpa todos os recursos Tkinter de forma segura"""
        try:
            # Para o controlador de teclado
            if hasattr(self, "keyboard_controller") and self.keyboard_controller:
                self.keyboard_controller.stop()

            # Para o controlador de sliders
            if hasattr(self, "slider_controller") and self.slider_controller:
                self.slider_controller.stop()

            # Para os gráficos de telemetria
            if hasattr(self, "telemetry_plotter") and self.telemetry_plotter:
                self.telemetry_plotter.stop()

            # Lista de variáveis Tkinter
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
                "autoscroll_var",
            ]

            for var_name in tkinter_vars:
                if hasattr(self, var_name):
                    try:
                        var = getattr(self, var_name)
                        if var is not None:
                            try:
                                var._tk = None
                            except Exception:
                                pass
                        delattr(self, var_name)
                    except Exception:
                        pass

            # Limpa sensor vars
            if hasattr(self, "sensor_vars"):
                try:
                    for key, var in list(self.sensor_vars.items()):
                        if var is not None:
                            try:
                                var._tk = None
                            except Exception:
                                pass
                    self.sensor_vars.clear()
                    delattr(self, "sensor_vars")
                except Exception:
                    pass

            # Limpa imagem do vídeo para evitar erro de thread
            if hasattr(self, "video_label") and self.video_label:
                try:
                    self.video_label.configure(image="")
                    self.video_label.image = None
                except Exception:
                    pass

            # Para o video_display
            if hasattr(self, "video_display") and self.video_display:
                try:
                    self.video_display.stop()
                except Exception:
                    pass

            # Força garbage collection
            try:
                import gc

                gc.collect()
            except Exception:
                pass

            # Destrói a janela principal
            if hasattr(self, "root") and self.root:
                try:
                    self.root.after_cancel("all")
                    try:
                        self.root.update_idletasks()
                    except Exception:
                        pass
                    try:
                        self.root.winfo_exists()
                        self.root.destroy()
                    except tk.TclError:
                        pass
                    except Exception:
                        try:
                            self.root.destroy()
                        except Exception:
                            pass
                    self.root = None
                except Exception:
                    pass

        except Exception:
            pass

    def _on_brake_balance_change(self, value):
        """Callback quando o slider de brake balance muda"""
        try:
            balance = float(value)
            front_pct = balance
            rear_pct = 100 - balance
            self.brake_balance_label.config(
                text=f"{front_pct:.0f}% Dianteiro / {rear_pct:.0f}% Traseiro"
            )
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
        except Exception as e:
            error(f"Erro ao alterar damping: {e}", "FF")

    def _on_ff_friction_change(self, value):
        """Callback quando o slider de friction muda"""
        try:
            friction = float(value)
            self.friction_value_label.config(text=f"{friction:.0f}%")
            debug(f"Friction alterado: {friction:.0f}%", "FF")
        except Exception as e:
            error(f"Erro ao alterar friction: {e}", "FF")

    def _on_ff_filter_change(self, value):
        """Callback quando o slider de filter muda"""
        try:
            filter_val = float(value)
            self.filter_value_label.config(text=f"{filter_val:.0f}%")
            debug(f"Filter alterado: {filter_val:.0f}%", "FF")
        except Exception as e:
            error(f"Erro ao alterar filter: {e}", "FF")

    def _on_ff_sensitivity_change(self, value):
        """Callback quando o slider de sensitivity muda"""
        try:
            sensitivity = float(value)
            self.sensitivity_value_label.config(text=f"{sensitivity:.0f}%")
            debug(f"Sensitivity alterado: {sensitivity:.0f}%", "FF")
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
            return

        self.is_running = False

        if hasattr(self, "root") and self.root:
            try:
                self.root.after_idle(self._cleanup_tkinter_resources)
                self.root.quit()
            except Exception:
                self._cleanup_tkinter_resources()
        else:
            self._cleanup_tkinter_resources()
