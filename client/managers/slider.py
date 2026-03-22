#!/usr/bin/env python3
"""
slider_controller.py - Controlador de Sliders para F1 Car
Gerencia controles analógicos de acelerador, freio e direção via sliders
Inclui sistema de calibração para eixos do G923
"""

import json
import os
import tkinter as tk
import tkinter.ttk as ttk
from datetime import datetime

from .simple_logger import debug, error, info, warn


class SliderController:
    """Gerenciador de controles analógicos (sliders) para acelerador, freio e direção"""

    # UI Colors
    _BG_COLOR = "#3c3c3c"
    _BG_DARK = "#2d2d2d"
    _BG_TROUGH = "#1a1a1a"
    _FG_LABEL = "#888888"
    _FG_TEXT = "#cccccc"
    _FG_THROTTLE = "#00d477"
    _FG_BRAKE = "#ff4444"
    _FG_STEERING = "#4488ff"

    def __init__(self, network_client=None, log_callback=None, g923_manager=None,
                 state_callback=None):
        """
        Inicializa o controlador de sliders

        Args:
            network_client: Cliente de rede para enviar comandos
            log_callback: Função de callback para logging na interface
            g923_manager: Instância do G923Manager para calibração
            state_callback: Callback para atualizar estado de controle compartilhado
                           Recebe (steering, throttle, brake) como floats
        """
        self.network_client = network_client
        self.log_callback = log_callback
        self.g923_manager = g923_manager
        self.state_callback = state_callback

        # Estado dos controles
        self.throttle_value = 0.0  # 0-100%
        self.brake_value = 0.0  # 0-100%
        self.steering_value = 0.0  # -100 a +100% (esquerda/direita)

        # Widgets dos sliders
        self.throttle_slider = None
        self.brake_slider = None
        self.steering_slider = None
        self.throttle_label = None
        self.brake_label = None
        self.steering_label = None

        # Estado de calibração (inline, sem CalibrationManager separado)
        self._cal_active = False
        self._cal_component = None  # "THROTTLE", "BRAKE", "STEERING"
        self._cal_raw_min = None
        self._cal_raw_max = None
        self._cal_raw_current = 0

        # Widgets de calibração
        self.cal_throttle_btn = None
        self.cal_brake_btn = None
        self.cal_steering_btn = None
        self.cal_status_label = None
        self.cal_raw_value_label = None
        self.cal_save_btn = None
        self.cal_cancel_btn = None

        # Arquivo de calibração (em client/, não em managers/)
        client_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        self._cal_config_file = os.path.join(client_dir, "g923_calibration.json")

        # Flag para evitar envio duplo quando G923 atualiza sliders
        self._updating_from_g923 = False

        # Controle de envio
        self.is_active = False

        # Carrega calibração salva e aplica ao G923Manager
        self._load_calibration()

    def set_g923_manager(self, g923_manager):
        """Define o G923Manager para calibração"""
        self.g923_manager = g923_manager
        # Aplica calibração salva ao novo manager
        self._apply_saved_calibration()

    def update_from_g923(self):
        """Atualiza sliders com valores atuais do G923 (chamar do Tkinter thread)"""
        if not self.g923_manager or not self.g923_manager.is_connected():
            return

        self._updating_from_g923 = True
        try:
            steering = self.g923_manager._steering
            throttle = self.g923_manager._throttle
            brake = self.g923_manager._brake

            if self.steering_slider and abs(steering - self.steering_value) >= 1:
                self.steering_slider.set(steering)
            if self.throttle_slider and abs(throttle - self.throttle_value) >= 1:
                self.throttle_slider.set(throttle)
            if self.brake_slider and abs(brake - self.brake_value) >= 1:
                self.brake_slider.set(brake)
        finally:
            self._updating_from_g923 = False

    def _log(self, level: str, message: str):
        """Log com fallback"""
        if self.log_callback:
            self.log_callback(level, message)
        else:
            if level == "INFO":
                info(message, "SLIDERS")
            elif level == "DEBUG":
                debug(message, "SLIDERS")
            elif level == "WARN":
                warn(message, "SLIDERS")
            elif level == "ERROR":
                error(message, "SLIDERS")

    def create_control_frame(self, parent):
        """
        Cria frame com sliders de controle

        Args:
            parent: Widget pai para criar o frame

        Returns:
            Frame criado com sliders
        """
        control_frame = ttk.LabelFrame(
            parent, text="🎚️ Controles Analógicos", style="Dark.TLabelframe"
        )

        # Frame interno para layout
        inner_frame = tk.Frame(control_frame, bg=self._BG_COLOR)
        inner_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # === THROTTLE SLIDER ===
        throttle_frame = tk.Frame(inner_frame, bg=self._BG_COLOR)
        throttle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        # Label do acelerador
        self.throttle_label = tk.Label(
            throttle_frame,
            text="🚀 Acelerador: 0%",
            bg=self._BG_COLOR,
            fg=self._FG_THROTTLE,
            font=("Arial", 12, "bold"),
        )
        self.throttle_label.pack(pady=(0, 10))

        # Slider do throttle (vertical)
        self.throttle_slider = tk.Scale(
            throttle_frame,
            from_=100,
            to=0,
            orient=tk.VERTICAL,
            length=200,
            width=30,
            bg=self._BG_DARK,
            fg="white",
            activebackground=self._FG_THROTTLE,
            highlightthickness=0,
            troughcolor=self._BG_TROUGH,
            sliderrelief=tk.FLAT,
            command=self._on_throttle_change,
        )
        self.throttle_slider.pack()

        # Marcações do throttle
        throttle_marks = tk.Frame(throttle_frame, bg=self._BG_COLOR)
        throttle_marks.pack(pady=(5, 0))

        for i, mark in enumerate(["100%", "75%", "50%", "25%", "0%"]):
            label = tk.Label(
                throttle_marks, text=mark, bg=self._BG_COLOR, fg=self._FG_LABEL, font=("Arial", 8)
            )
            label.pack()

        # === BRAKE SLIDER ===
        brake_frame = tk.Frame(inner_frame, bg=self._BG_COLOR)
        brake_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)

        # Label do freio
        self.brake_label = tk.Label(
            brake_frame,
            text="🛑 Freio: 0%",
            bg=self._BG_COLOR,
            fg=self._FG_BRAKE,
            font=("Arial", 12, "bold"),
        )
        self.brake_label.pack(pady=(0, 10))

        # Slider do brake (vertical)
        self.brake_slider = tk.Scale(
            brake_frame,
            from_=100,
            to=0,
            orient=tk.VERTICAL,
            length=200,
            width=30,
            bg=self._BG_DARK,
            fg="white",
            activebackground=self._FG_BRAKE,
            highlightthickness=0,
            troughcolor=self._BG_TROUGH,
            sliderrelief=tk.FLAT,
            command=self._on_brake_change,
        )
        self.brake_slider.pack()

        # Marcações do brake
        brake_marks = tk.Frame(brake_frame, bg=self._BG_COLOR)
        brake_marks.pack(pady=(5, 0))

        for i, mark in enumerate(["100%", "75%", "50%", "25%", "0%"]):
            label = tk.Label(
                brake_marks, text=mark, bg=self._BG_COLOR, fg=self._FG_LABEL, font=("Arial", 8)
            )
            label.pack()

        # === STEERING SLIDER ===
        steering_container = tk.Frame(control_frame, bg=self._BG_COLOR)
        steering_container.pack(pady=(20, 10), fill=tk.X, padx=10)

        # Label do steering
        self.steering_label = tk.Label(
            steering_container,
            text="🏎️ Direção: 0° (Centro)",
            bg=self._BG_COLOR,
            fg=self._FG_STEERING,
            font=("Arial", 12, "bold"),
        )
        self.steering_label.pack(pady=(0, 10))

        # Slider do steering (horizontal)
        self.steering_slider = tk.Scale(
            steering_container,
            from_=-100,
            to=100,
            orient=tk.HORIZONTAL,
            length=300,
            width=30,
            bg=self._BG_DARK,
            fg="white",
            activebackground=self._FG_STEERING,
            highlightthickness=0,
            troughcolor=self._BG_TROUGH,
            sliderrelief=tk.FLAT,
            command=self._on_steering_change,
        )
        self.steering_slider.set(0)  # Inicia no centro
        self.steering_slider.pack()

        # Marcações do steering
        steering_marks = tk.Frame(steering_container, bg=self._BG_COLOR)
        steering_marks.pack(pady=(5, 0))

        marks_frame = tk.Frame(steering_marks, bg=self._BG_COLOR)
        marks_frame.pack()

        for mark in ["⬅️ ESQ", "⬅️", "🎯 CENTRO", "➡️", "➡️ DIR"]:
            label = tk.Label(
                marks_frame, text=mark, bg=self._BG_COLOR, fg=self._FG_LABEL, font=("Arial", 8)
            )
            label.pack(side=tk.LEFT, padx=15)

        # === INSTRUÇÕES ===
        instructions = tk.Label(
            control_frame,
            text="Arraste os sliders para controlar acelerador, freio e direção de forma suave",
            bg=self._BG_COLOR,
            fg=self._FG_TEXT,
            font=("Arial", 9),
        )
        instructions.pack(pady=5)

        # === CALIBRAÇÃO DO G923 ===
        calibration_frame = ttk.LabelFrame(
            control_frame, text="🎯 Calibração G923", style="Dark.TLabelframe"
        )
        calibration_frame.pack(fill=tk.X, padx=10, pady=10)

        # Frame interno para layout
        cal_inner = tk.Frame(calibration_frame, bg=self._BG_COLOR)
        cal_inner.pack(padx=10, pady=10, fill=tk.X)

        # Botões de calibração para cada componente
        cal_buttons_frame = tk.Frame(cal_inner, bg=self._BG_COLOR)
        cal_buttons_frame.pack(fill=tk.X, pady=5)

        self.cal_throttle_btn = tk.Button(
            cal_buttons_frame,
            text="📊 Calibrar Acelerador",
            command=lambda: self._start_calibration("THROTTLE"),
            bg="#2d8659",
            fg="white",
            font=("Arial", 10),
            relief=tk.RAISED,
            bd=2,
        )
        self.cal_throttle_btn.pack(side=tk.LEFT, padx=5)

        self.cal_brake_btn = tk.Button(
            cal_buttons_frame,
            text="📊 Calibrar Freio",
            command=lambda: self._start_calibration("BRAKE"),
            bg="#c93030",
            fg="white",
            font=("Arial", 10),
            relief=tk.RAISED,
            bd=2,
        )
        self.cal_brake_btn.pack(side=tk.LEFT, padx=5)

        self.cal_steering_btn = tk.Button(
            cal_buttons_frame,
            text="📊 Calibrar Direção",
            command=lambda: self._start_calibration("STEERING"),
            bg="#2d5f99",
            fg="white",
            font=("Arial", 10),
            relief=tk.RAISED,
            bd=2,
        )
        self.cal_steering_btn.pack(side=tk.LEFT, padx=5)

        # Status da calibração
        self.cal_status_label = tk.Label(
            cal_inner,
            text="Nenhuma calibração em andamento",
            bg=self._BG_COLOR,
            fg=self._FG_TEXT,
            font=("Arial", 9),
            wraplength=600,
            justify=tk.LEFT,
        )
        self.cal_status_label.pack(pady=5, fill=tk.X)

        # Valor bruto do eixo
        self.cal_raw_value_label = tk.Label(
            cal_inner,
            text="Valor bruto: --",
            bg="#2c2c2c",
            fg="#00ff00",
            font=("Courier", 12, "bold"),
            relief=tk.SUNKEN,
            bd=2,
        )
        self.cal_raw_value_label.pack(pady=5)

        # Botões de ação de calibração
        cal_action_frame = tk.Frame(cal_inner, bg=self._BG_COLOR)
        cal_action_frame.pack(pady=5)

        self.cal_save_btn = tk.Button(
            cal_action_frame,
            text="✅ Salvar Calibração",
            command=self._save_calibration,
            bg="#2d8659",
            fg="white",
            font=("Arial", 10, "bold"),
            relief=tk.RAISED,
            bd=2,
            state=tk.DISABLED,
        )
        self.cal_save_btn.pack(side=tk.LEFT, padx=5)

        self.cal_cancel_btn = tk.Button(
            cal_action_frame,
            text="❌ Cancelar",
            command=self._cancel_calibration,
            bg="#c93030",
            fg="white",
            font=("Arial", 10),
            relief=tk.RAISED,
            bd=2,
            state=tk.DISABLED,
        )
        self.cal_cancel_btn.pack(side=tk.LEFT, padx=5)

        return control_frame

    def _g923_connected(self) -> bool:
        """Verifica se G923 está conectado (sliders viram só visuais)"""
        return self.g923_manager is not None and self.g923_manager.is_connected()

    def _on_throttle_change(self, value):
        """Callback para mudança no slider de acelerador"""
        try:
            self.throttle_value = float(value)
            self.throttle_label.config(
                text=f"🚀 Acelerador: {self.throttle_value:.0f}%"
            )

            # G923 conectado → slider é só visual, envio é pelo handle_g923_command
            if self._updating_from_g923 or self._g923_connected():
                return

            self._update_control_state()

        except Exception as e:
            self._log("ERROR", f"Erro ao processar mudança de acelerador: {e}")

    def _on_brake_change(self, value):
        """Callback para mudança no slider de freio"""
        try:
            self.brake_value = float(value)
            self.brake_label.config(text=f"🛑 Freio: {self.brake_value:.0f}%")

            # G923 conectado → slider é só visual
            if self._updating_from_g923 or self._g923_connected():
                return

            self._update_control_state()

        except Exception as e:
            self._log("ERROR", f"Erro ao processar mudança de freio: {e}")

    def _on_steering_change(self, value):
        """Callback para mudança no slider de direção"""
        try:
            self.steering_value = float(value)

            if self.steering_value == 0:
                direction_text = "🏎️ Direção: 0° (Centro)"
            elif self.steering_value < 0:
                direction_text = (
                    f"🏎️ Direção: {abs(self.steering_value):.0f}° ⬅️ Esquerda"
                )
            else:
                direction_text = f"🏎️ Direção: {self.steering_value:.0f}° ➡️ Direita"

            self.steering_label.config(text=direction_text)

            # G923 conectado → slider é só visual
            if self._updating_from_g923 or self._g923_connected():
                return

            self._update_control_state()

        except Exception as e:
            self._log("ERROR", f"Erro ao processar mudança de direção: {e}")

    def _update_control_state(self):
        """Atualiza estado de controle compartilhado via callback.
        O loop 100Hz do main.py envia STATE:steering,throttle,brake ao RPi."""
        if self.state_callback:
            self.state_callback(
                self.steering_value, self.throttle_value, self.brake_value
            )

    def start(self):
        """Inicia o controlador de sliders"""
        if self.is_active:
            return
        self.is_active = True
        self._log("INFO", "Controlador de sliders iniciado")

    def stop(self):
        """Para o controlador de sliders"""
        if not self.is_active:
            return
        self.is_active = False
        # Zera estado ao parar
        if self.state_callback:
            self.state_callback(0, 0, 0)
        self._log("INFO", "Controlador de sliders parado")

    # ===== G923 CALIBRATION METHODS =====

    def _get_raw_value(self, component: str) -> int:
        """Lê valor bruto atual do eixo G923"""
        if not self.g923_manager:
            return 0
        if component == "THROTTLE":
            return self.g923_manager._raw_throttle
        elif component == "BRAKE":
            return self.g923_manager._raw_brake
        elif component == "STEERING":
            return self.g923_manager._raw_steering
        return 0

    def _start_calibration(self, component: str):
        """Inicia calibração de um eixo do G923"""
        if self._cal_active:
            self._log("WARN", "Calibração já em andamento!")
            return

        if not self.g923_manager or not self.g923_manager.is_connected():
            self._log("WARN", "G923 não conectado! Conecte o volante antes de calibrar.")
            if self.cal_status_label:
                self.cal_status_label.config(
                    text="G923 não conectado! Conecte o volante primeiro.",
                    fg=self._FG_BRAKE,
                )
            return

        self._cal_active = True
        self._cal_component = component
        self._cal_raw_min = None
        self._cal_raw_max = None
        self._cal_raw_current = 0

        # Desativa endstop durante calibração de steering (senão trava no limite atual)
        if component == "STEERING" and self.g923_manager:
            self.g923_manager.disable_endstop()

        # Atualiza UI
        self._update_calibration_ui()

        # Desabilita botões de calibração
        self.cal_throttle_btn.config(state=tk.DISABLED)
        self.cal_brake_btn.config(state=tk.DISABLED)
        self.cal_steering_btn.config(state=tk.DISABLED)

        # Habilita botões de ação
        self.cal_save_btn.config(state=tk.NORMAL)
        self.cal_cancel_btn.config(state=tk.NORMAL)

        # Inicia polling de valores brutos
        self._schedule_calibration_update()

        self._log("INFO", f"Calibração G923 iniciada: {component}")

    def _save_calibration(self):
        """Salva calibração e aplica ao G923Manager"""
        if not self._cal_active:
            return

        component = self._cal_component

        # Valida dados
        if self._cal_raw_min is None or self._cal_raw_max is None:
            self._log("ERROR", "Dados incompletos! Mova o eixo pelo range completo.")
            return

        if self._cal_raw_min >= self._cal_raw_max:
            self._log(
                "ERROR",
                f"Calibração inválida! Min ({self._cal_raw_min}) >= Max ({self._cal_raw_max})",
            )
            return

        # Aplica ao G923Manager
        if self.g923_manager:
            if component == "THROTTLE":
                self.g923_manager._throttle_min = self._cal_raw_min
                self.g923_manager._throttle_max = self._cal_raw_max
            elif component == "BRAKE":
                self.g923_manager._brake_min = self._cal_raw_min
                self.g923_manager._brake_max = self._cal_raw_max
            elif component == "STEERING":
                self.g923_manager._steer_min = self._cal_raw_min
                self.g923_manager._steer_max = self._cal_raw_max

        # Salva em arquivo JSON
        self._save_calibration_file(component)

        self._log(
            "INFO",
            f"Calibração G923 salva: {component} = [{self._cal_raw_min}, {self._cal_raw_max}]",
        )

        self._finish_calibration()

    def _cancel_calibration(self):
        """Cancela calibração atual"""
        if self._cal_active:
            self._log("INFO", f"Calibração cancelada: {self._cal_component}")
        self._finish_calibration()

    def _finish_calibration(self):
        """Finaliza modo de calibração"""
        # Reativa endstop se foi desativado durante calibração de steering
        if self._cal_component == "STEERING" and self.g923_manager:
            self.g923_manager.enable_endstop()

        self._cal_active = False
        self._cal_component = None
        self._cal_raw_min = None
        self._cal_raw_max = None

        # Reabilita botões de calibração
        self.cal_throttle_btn.config(state=tk.NORMAL)
        self.cal_brake_btn.config(state=tk.NORMAL)
        self.cal_steering_btn.config(state=tk.NORMAL)

        # Desabilita botões de ação
        self.cal_save_btn.config(state=tk.DISABLED)
        self.cal_cancel_btn.config(state=tk.DISABLED)

        # Atualiza UI
        self.cal_status_label.config(
            text="Nenhuma calibração em andamento", fg=self._FG_TEXT
        )
        self.cal_raw_value_label.config(text="Valor bruto: --")

    def _schedule_calibration_update(self):
        """Agenda próxima atualização da UI de calibração"""
        if self._cal_active:
            self._update_calibration_ui()
            # Agenda próxima atualização (50ms = 20Hz)
            if (
                hasattr(self, "cal_status_label")
                and self.cal_status_label.winfo_exists()
            ):
                self.cal_status_label.after(50, self._schedule_calibration_update)

    def _update_calibration_ui(self):
        """Atualiza UI de calibração com status atual"""
        if not self._cal_active:
            return

        component = self._cal_component

        # Lê valor bruto atual do G923
        raw_value = self._get_raw_value(component)
        self._cal_raw_current = raw_value

        # Auto-detecta min/max
        if self._cal_raw_min is None or raw_value < self._cal_raw_min:
            self._cal_raw_min = raw_value
        if self._cal_raw_max is None or raw_value > self._cal_raw_max:
            self._cal_raw_max = raw_value

        # Instruções
        if component == "THROTTLE":
            instructions = (
                "Calibração do Acelerador G923:\n"
                "1. SOLTE completamente o pedal (posição 0%)\n"
                "2. PRESSIONE totalmente o pedal (posição 100%)\n"
                "3. Clique em 'Salvar' quando terminar"
            )
        elif component == "BRAKE":
            instructions = (
                "Calibração do Freio G923:\n"
                "1. SOLTE completamente o pedal (posição 0%)\n"
                "2. PRESSIONE totalmente o pedal (posição 100%)\n"
                "3. Clique em 'Salvar' quando terminar"
            )
        elif component == "STEERING":
            instructions = (
                "Calibração da Direção G923:\n"
                "1. Gire TOTALMENTE para a ESQUERDA\n"
                "2. Gire TOTALMENTE para a DIREITA\n"
                "3. Clique em 'Salvar' quando terminar"
            )
        else:
            instructions = ""

        self.cal_status_label.config(text=instructions, fg="#ffaa00")

        # Valor bruto com min/max
        value_text = f"Valor bruto: {raw_value}"
        if self._cal_raw_min is not None and self._cal_raw_max is not None:
            cal_range = self._cal_raw_max - self._cal_raw_min
            value_text += (
                f"  [Min: {self._cal_raw_min}, Max: {self._cal_raw_max}, "
                f"Range: {cal_range}]"
            )

        self.cal_raw_value_label.config(text=value_text)

    def _save_calibration_file(self, component: str):
        """Salva calibração em arquivo JSON"""
        try:
            # Carrega dados existentes
            cal_data = {}
            if os.path.exists(self._cal_config_file):
                with open(self._cal_config_file, "r") as f:
                    cal_data = json.load(f)

            # Atualiza componente
            if "calibration_data" not in cal_data:
                cal_data["calibration_data"] = {}

            cal_data["calibration_data"][component] = {
                "min": self._cal_raw_min,
                "max": self._cal_raw_max,
            }
            cal_data["last_updated"] = datetime.now().isoformat()
            cal_data["device"] = "G923"

            with open(self._cal_config_file, "w") as f:
                json.dump(cal_data, f, indent=4)

            self._log("INFO", f"Calibração salva em: {self._cal_config_file}")

        except Exception as e:
            self._log("ERROR", f"Erro ao salvar calibração: {e}")

    def _load_calibration(self):
        """Carrega calibração salva do arquivo JSON"""
        try:
            if not os.path.exists(self._cal_config_file):
                return

            with open(self._cal_config_file, "r") as f:
                cal_data = json.load(f)

            self._saved_cal_data = cal_data.get("calibration_data", {})
            last_updated = cal_data.get("last_updated", "desconhecido")
            self._log(
                "INFO",
                f"Calibração G923 carregada ({last_updated})",
            )

            # Aplica ao G923Manager se já estiver disponível
            self._apply_saved_calibration()

        except Exception as e:
            self._log("ERROR", f"Erro ao carregar calibração: {e}")
            self._saved_cal_data = {}

    def _apply_saved_calibration(self):
        """Aplica calibração salva ao G923Manager"""
        if not self.g923_manager or not hasattr(self, "_saved_cal_data"):
            return

        cal = self._saved_cal_data

        if "THROTTLE" in cal:
            self.g923_manager._throttle_min = cal["THROTTLE"]["min"]
            self.g923_manager._throttle_max = cal["THROTTLE"]["max"]

        if "BRAKE" in cal:
            self.g923_manager._brake_min = cal["BRAKE"]["min"]
            self.g923_manager._brake_max = cal["BRAKE"]["max"]

        if "STEERING" in cal:
            self.g923_manager._steer_min = cal["STEERING"]["min"]
            self.g923_manager._steer_max = cal["STEERING"]["max"]

        if cal:
            self._log("INFO", "Calibração aplicada ao G923")
