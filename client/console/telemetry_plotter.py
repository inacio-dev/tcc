"""
telemetry_plotter.py - Gráficos de Telemetria Estilo F1 em Tempo Real
Inspirado no Fast-F1, mas usando dados locais dos sensores
"""

import tkinter as tk
from tkinter import ttk
from collections import deque
from typing import Optional
import time

try:
    import matplotlib
    matplotlib.use('TkAgg')
    from matplotlib.figure import Figure
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.lines import Line2D
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False

from simple_logger import error, debug, info


class F1TelemetryPlotter:
    """
    Gera gráficos de telemetria estilo F1 em tempo real

    Gráficos disponíveis:
    - Speed trace (velocidade ao longo do tempo)
    - Throttle/Brake overlay
    - G-Forces (lateral e frontal)
    - Gear indicator
    """

    # Cores estilo F1
    COLORS = {
        'speed': '#00D2BE',      # Teal (Mercedes style)
        'throttle': '#00FF00',   # Verde
        'brake': '#FF0000',      # Vermelho
        'g_lateral': '#FF8700',  # Laranja
        'g_frontal': '#0090FF',  # Azul
        'gear': '#FFD700',       # Dourado
        'background': '#1E1E1E', # Fundo escuro
        'grid': '#3C3C3C',       # Grid
        'text': '#FFFFFF',       # Texto
    }

    def __init__(self, max_points: int = 500, update_interval: int = 100):
        """
        Args:
            max_points: Número máximo de pontos no gráfico (histórico)
            update_interval: Intervalo de atualização em ms
        """
        self.max_points = max_points
        self.update_interval = update_interval

        # Buffers de dados (deque para performance)
        self.time_data = deque(maxlen=max_points)
        self.speed_data = deque(maxlen=max_points)
        self.throttle_data = deque(maxlen=max_points)
        self.brake_data = deque(maxlen=max_points)
        self.g_lateral_data = deque(maxlen=max_points)
        self.g_frontal_data = deque(maxlen=max_points)
        self.gear_data = deque(maxlen=max_points)

        # Timestamp inicial
        self.start_time = time.time()

        # Widgets
        self.frame = None
        self.canvas = None
        self.figure = None
        self.axes = {}
        self.lines = {}

        # Controle
        self.is_running = False
        self.root = None

    def create_frame(self, parent) -> ttk.LabelFrame:
        """
        Cria o frame com os gráficos de telemetria

        Args:
            parent: Widget pai (Tkinter)

        Returns:
            Frame com os gráficos
        """
        if not MATPLOTLIB_AVAILABLE:
            # Fallback se matplotlib não estiver disponível
            self.frame = ttk.LabelFrame(
                parent, text="Telemetria F1", style="Dark.TLabelframe"
            )
            ttk.Label(
                self.frame,
                text="Matplotlib não instalado.\npip install matplotlib",
                style="Dark.TLabel"
            ).pack(pady=20)
            return self.frame

        self.frame = ttk.LabelFrame(
            parent, text="Telemetria F1 - Tempo Real", style="Dark.TLabelframe"
        )

        # Criar figura matplotlib com 3 subplots
        self.figure = Figure(figsize=(6, 4), dpi=80, facecolor=self.COLORS['background'])

        # Subplot 1: Speed
        self.axes['speed'] = self.figure.add_subplot(311)
        self._setup_axis(self.axes['speed'], 'Velocidade (km/h)', 0, 50)

        # Subplot 2: Throttle/Brake
        self.axes['pedals'] = self.figure.add_subplot(312)
        self._setup_axis(self.axes['pedals'], 'Pedais (%)', 0, 100)

        # Subplot 3: G-Forces
        self.axes['gforce'] = self.figure.add_subplot(313)
        self._setup_axis(self.axes['gforce'], 'Forças G', -2, 2)

        # Ajustar layout
        self.figure.tight_layout(pad=1.0)

        # Criar linhas iniciais (vazias)
        self._create_lines()

        # Criar canvas Tkinter
        self.canvas = FigureCanvasTkAgg(self.figure, master=self.frame)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

        # Legenda
        self._create_legend()

        return self.frame

    def _setup_axis(self, ax, ylabel: str, ymin: float, ymax: float):
        """Configura um eixo com estilo F1"""
        ax.set_facecolor(self.COLORS['background'])
        ax.set_ylabel(ylabel, color=self.COLORS['text'], fontsize=8)
        ax.set_ylim(ymin, ymax)
        ax.set_xlim(0, 30)  # 30 segundos de janela
        ax.tick_params(colors=self.COLORS['text'], labelsize=7)
        ax.grid(True, color=self.COLORS['grid'], alpha=0.3, linestyle='--')
        ax.spines['bottom'].set_color(self.COLORS['grid'])
        ax.spines['top'].set_color(self.COLORS['grid'])
        ax.spines['left'].set_color(self.COLORS['grid'])
        ax.spines['right'].set_color(self.COLORS['grid'])

    def _create_lines(self):
        """Cria as linhas dos gráficos"""
        # Speed line
        self.lines['speed'], = self.axes['speed'].plot(
            [], [], color=self.COLORS['speed'], linewidth=1.5, label='Velocidade'
        )

        # Throttle line
        self.lines['throttle'], = self.axes['pedals'].plot(
            [], [], color=self.COLORS['throttle'], linewidth=1.5, label='Acelerador'
        )

        # Brake line
        self.lines['brake'], = self.axes['pedals'].plot(
            [], [], color=self.COLORS['brake'], linewidth=1.5, label='Freio'
        )

        # G-force lateral
        self.lines['g_lateral'], = self.axes['gforce'].plot(
            [], [], color=self.COLORS['g_lateral'], linewidth=1.5, label='G Lateral'
        )

        # G-force frontal
        self.lines['g_frontal'], = self.axes['gforce'].plot(
            [], [], color=self.COLORS['g_frontal'], linewidth=1.5, label='G Frontal'
        )

    def _create_legend(self):
        """Cria legenda compacta"""
        legend_frame = tk.Frame(self.frame, bg=self.COLORS['background'])
        legend_frame.pack(fill=tk.X, padx=5, pady=2)

        legends = [
            ('Velocidade', self.COLORS['speed']),
            ('Acelerador', self.COLORS['throttle']),
            ('Freio', self.COLORS['brake']),
            ('G Lateral', self.COLORS['g_lateral']),
            ('G Frontal', self.COLORS['g_frontal']),
        ]

        for name, color in legends:
            item = tk.Frame(legend_frame, bg=self.COLORS['background'])
            item.pack(side=tk.LEFT, padx=5)

            # Cor
            color_box = tk.Canvas(item, width=12, height=12,
                                  bg=self.COLORS['background'], highlightthickness=0)
            color_box.pack(side=tk.LEFT)
            color_box.create_rectangle(2, 2, 10, 10, fill=color, outline=color)

            # Nome
            tk.Label(item, text=name, fg=self.COLORS['text'],
                    bg=self.COLORS['background'], font=('Arial', 7)).pack(side=tk.LEFT)

    def update_data(self, sensor_data: dict):
        """
        Atualiza os buffers de dados com novos valores

        Args:
            sensor_data: Dicionário com dados dos sensores
        """
        current_time = time.time() - self.start_time

        self.time_data.append(current_time)

        # Speed (usa velocidade calculada ou 0)
        speed = sensor_data.get('velocity_total', 0.0)
        if speed == 0:
            # Tenta pegar de outros campos
            speed = sensor_data.get('speed', 0.0)
        self.speed_data.append(speed)

        # Throttle
        throttle = sensor_data.get('throttle', 0.0)
        if throttle == 0:
            throttle = sensor_data.get('current_pwm', 0.0)
        self.throttle_data.append(throttle)

        # Brake
        brake = sensor_data.get('brake', 0.0)
        self.brake_data.append(brake)

        # G-Forces
        g_lateral = sensor_data.get('g_force_lateral', 0.0)
        g_frontal = sensor_data.get('g_force_frontal', 0.0)
        self.g_lateral_data.append(g_lateral)
        self.g_frontal_data.append(g_frontal)

        # Gear
        gear = sensor_data.get('current_gear', 1)
        self.gear_data.append(gear)

    def refresh_plots(self):
        """Atualiza os gráficos com os dados atuais"""
        if not MATPLOTLIB_AVAILABLE or not self.is_running:
            return

        if len(self.time_data) < 2:
            return

        try:
            time_list = list(self.time_data)

            # Ajusta janela de tempo (últimos 30 segundos)
            if time_list:
                current_time = time_list[-1]
                time_window = 30  # segundos
                xmin = max(0, current_time - time_window)
                xmax = current_time + 1

                for ax in self.axes.values():
                    ax.set_xlim(xmin, xmax)

            # Atualiza linha de velocidade
            self.lines['speed'].set_data(time_list, list(self.speed_data))

            # Ajusta escala Y da velocidade dinamicamente
            if self.speed_data:
                max_speed = max(self.speed_data) * 1.2
                if max_speed > 10:
                    self.axes['speed'].set_ylim(0, max(50, max_speed))

            # Atualiza linhas de pedais
            self.lines['throttle'].set_data(time_list, list(self.throttle_data))
            self.lines['brake'].set_data(time_list, list(self.brake_data))

            # Atualiza linhas de G-force
            self.lines['g_lateral'].set_data(time_list, list(self.g_lateral_data))
            self.lines['g_frontal'].set_data(time_list, list(self.g_frontal_data))

            # Redesenha canvas
            self.canvas.draw_idle()

        except Exception as e:
            debug(f"Erro ao atualizar gráficos: {e}", "PLOTTER")

    def start(self, root):
        """
        Inicia atualização automática dos gráficos

        Args:
            root: Janela principal Tkinter
        """
        self.root = root
        self.is_running = True
        self.start_time = time.time()
        self._schedule_refresh()
        info("Telemetry plotter iniciado", "PLOTTER")

    def _schedule_refresh(self):
        """Agenda próxima atualização"""
        if self.is_running and self.root:
            self.refresh_plots()
            self.root.after(self.update_interval, self._schedule_refresh)

    def stop(self):
        """Para a atualização dos gráficos"""
        self.is_running = False
        info("Telemetry plotter parado", "PLOTTER")

    def reset(self):
        """Reseta todos os dados"""
        self.time_data.clear()
        self.speed_data.clear()
        self.throttle_data.clear()
        self.brake_data.clear()
        self.g_lateral_data.clear()
        self.g_frontal_data.clear()
        self.gear_data.clear()
        self.start_time = time.time()
        debug("Dados do plotter resetados", "PLOTTER")


def create_telemetry_frame(console) -> Optional[ttk.LabelFrame]:
    """
    Cria o frame de telemetria e integra com o console

    Args:
        console: Instância de ConsoleInterface

    Returns:
        Frame de telemetria ou None se falhar
    """
    try:
        plotter = F1TelemetryPlotter(max_points=500, update_interval=100)
        frame = plotter.create_frame(console.right_column)

        # Armazena referência no console
        console.telemetry_plotter = plotter

        return frame

    except Exception as e:
        error(f"Erro ao criar frame de telemetria: {e}", "PLOTTER")
        return None
