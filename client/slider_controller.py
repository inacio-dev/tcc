#!/usr/bin/env python3
"""
slider_controller.py - Controlador de Sliders para F1 Car
Gerencia controles analógicos de acelerador, freio e direção via sliders
Inclui sistema de calibração para encoders incrementais ESP32
"""

import threading
import time
import tkinter as tk
import tkinter.ttk as ttk
from typing import Callable

from calibration_manager import CalibrationManager
from simple_logger import debug, error, info, warn


class SliderController:
    """Gerenciador de controles analógicos (sliders) para acelerador, freio e direção"""

    def __init__(self, network_client=None, log_callback=None, serial_sender=None):
        """
        Inicializa o controlador de sliders

        Args:
            network_client: Cliente de rede para enviar comandos
            log_callback: Função de callback para logging na interface
            serial_sender: Função para enviar comandos seriais ao ESP32
        """
        self.network_client = network_client
        self.log_callback = log_callback
        self.serial_sender = serial_sender

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

        # Calibration manager
        self.calibration_manager = CalibrationManager(
            serial_sender=self._send_serial_command, log_callback=log_callback
        )

        # Widgets de calibração
        self.cal_throttle_btn = None
        self.cal_brake_btn = None
        self.cal_steering_btn = None
        self.cal_status_label = None
        self.cal_raw_value_label = None
        self.cal_save_btn = None
        self.cal_cancel_btn = None

        # Controle de envio
        self.is_active = False
        self.send_thread = None
        self.lock = threading.Lock()

        # Configurações
        self.send_rate = 100  # Comandos por segundo (10ms)
        self.min_change_threshold = 1.0  # Mínimo 1% de mudança para enviar

        # Últimos valores enviados (para evitar spam)
        self.last_sent_throttle = -1.0
        self.last_sent_brake = -1.0
        self.last_sent_steering = -999.0  # Valor impossível para forçar primeiro envio

        # Estatísticas
        self.commands_sent = 0
        self.start_time = time.time()

    def set_network_client(self, network_client):
        """Define o cliente de rede para envio de comandos"""
        self.network_client = network_client
        debug("Network client configurado no SliderController", "SLIDERS")

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
        inner_frame = tk.Frame(control_frame, bg="#3c3c3c")
        inner_frame.pack(padx=10, pady=10, fill=tk.BOTH, expand=True)

        # === THROTTLE SLIDER ===
        throttle_frame = tk.Frame(inner_frame, bg="#3c3c3c")
        throttle_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=10)

        # Label do acelerador
        self.throttle_label = tk.Label(
            throttle_frame,
            text="🚀 Acelerador: 0%",
            bg="#3c3c3c",
            fg="#00d477",
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
            bg="#2d2d2d",
            fg="white",
            activebackground="#00d477",
            highlightthickness=0,
            troughcolor="#1a1a1a",
            sliderrelief=tk.FLAT,
            command=self._on_throttle_change,
        )
        self.throttle_slider.pack()

        # Marcações do throttle
        throttle_marks = tk.Frame(throttle_frame, bg="#3c3c3c")
        throttle_marks.pack(pady=(5, 0))

        for i, mark in enumerate(["100%", "75%", "50%", "25%", "0%"]):
            label = tk.Label(
                throttle_marks, text=mark, bg="#3c3c3c", fg="#888888", font=("Arial", 8)
            )
            label.pack()

        # === BRAKE SLIDER ===
        brake_frame = tk.Frame(inner_frame, bg="#3c3c3c")
        brake_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)

        # Label do freio
        self.brake_label = tk.Label(
            brake_frame,
            text="🛑 Freio: 0%",
            bg="#3c3c3c",
            fg="#ff4444",
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
            bg="#2d2d2d",
            fg="white",
            activebackground="#ff4444",
            highlightthickness=0,
            troughcolor="#1a1a1a",
            sliderrelief=tk.FLAT,
            command=self._on_brake_change,
        )
        self.brake_slider.pack()

        # Marcações do brake
        brake_marks = tk.Frame(brake_frame, bg="#3c3c3c")
        brake_marks.pack(pady=(5, 0))

        for i, mark in enumerate(["100%", "75%", "50%", "25%", "0%"]):
            label = tk.Label(
                brake_marks, text=mark, bg="#3c3c3c", fg="#888888", font=("Arial", 8)
            )
            label.pack()

        # === STEERING SLIDER ===
        steering_container = tk.Frame(control_frame, bg="#3c3c3c")
        steering_container.pack(pady=(20, 10), fill=tk.X, padx=10)

        # Label do steering
        self.steering_label = tk.Label(
            steering_container,
            text="🏎️ Direção: 0° (Centro)",
            bg="#3c3c3c",
            fg="#4488ff",
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
            bg="#2d2d2d",
            fg="white",
            activebackground="#4488ff",
            highlightthickness=0,
            troughcolor="#1a1a1a",
            sliderrelief=tk.FLAT,
            command=self._on_steering_change,
        )
        self.steering_slider.set(0)  # Inicia no centro
        self.steering_slider.pack()

        # Marcações do steering
        steering_marks = tk.Frame(steering_container, bg="#3c3c3c")
        steering_marks.pack(pady=(5, 0))

        marks_frame = tk.Frame(steering_marks, bg="#3c3c3c")
        marks_frame.pack()

        for mark in ["⬅️ ESQ", "⬅️", "🎯 CENTRO", "➡️", "➡️ DIR"]:
            label = tk.Label(
                marks_frame, text=mark, bg="#3c3c3c", fg="#888888", font=("Arial", 8)
            )
            label.pack(side=tk.LEFT, padx=15)

        # === INSTRUÇÕES ===
        instructions = tk.Label(
            control_frame,
            text="Arraste os sliders para controlar acelerador, freio e direção de forma suave",
            bg="#3c3c3c",
            fg="#cccccc",
            font=("Arial", 9),
        )
        instructions.pack(pady=5)

        # === CALIBRAÇÃO DE ENCODERS ===
        calibration_frame = ttk.LabelFrame(
            control_frame, text="🎯 Calibração de Encoders", style="Dark.TLabelframe"
        )
        calibration_frame.pack(fill=tk.X, padx=10, pady=10)

        # Frame interno para layout
        cal_inner = tk.Frame(calibration_frame, bg="#3c3c3c")
        cal_inner.pack(padx=10, pady=10, fill=tk.X)

        # Botões de calibração para cada componente
        cal_buttons_frame = tk.Frame(cal_inner, bg="#3c3c3c")
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
            bg="#3c3c3c",
            fg="#cccccc",
            font=("Arial", 9),
            wraplength=600,
            justify=tk.LEFT,
        )
        self.cal_status_label.pack(pady=5, fill=tk.X)

        # Valor bruto do encoder
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
        cal_action_frame = tk.Frame(cal_inner, bg="#3c3c3c")
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

    def _on_throttle_change(self, value):
        """Callback para mudança no slider de acelerador"""
        try:
            old_throttle = self.throttle_value
            self.throttle_value = float(value)
            self.throttle_label.config(
                text=f"🚀 Acelerador: {self.throttle_value:.0f}%"
            )

            # CORREÇÃO: Envia comando em thread separada para não travar UI
            if self.network_client:
                self._log(
                    "DEBUG",
                    f"🚀 Acelerador: {old_throttle:.0f}% → {self.throttle_value:.0f}%",
                )
                # Thread separada para envio de rede (não bloqueia UI)
                threading.Thread(
                    target=self._send_command_async,
                    args=("THROTTLE", self.throttle_value),
                    daemon=True,
                ).start()

        except Exception as e:
            self._log("ERROR", f"Erro ao processar mudança de acelerador: {e}")

    def _on_brake_change(self, value):
        """Callback para mudança no slider de freio"""
        try:
            old_brake = self.brake_value
            self.brake_value = float(value)
            self.brake_label.config(text=f"🛑 Freio: {self.brake_value:.0f}%")

            # CORREÇÃO: Envia comando em thread separada para não travar UI
            if self.network_client:
                self._log(
                    "DEBUG", f"🛑 Freio: {old_brake:.0f}% → {self.brake_value:.0f}%"
                )
                # Thread separada para envio de rede (não bloqueia UI)
                threading.Thread(
                    target=self._send_command_async,
                    args=("BRAKE", self.brake_value),
                    daemon=True,
                ).start()

        except Exception as e:
            self._log("ERROR", f"Erro ao processar mudança de freio: {e}")

    def _on_steering_change(self, value):
        """Callback para mudança no slider de direção"""
        try:
            old_steering = self.steering_value
            self.steering_value = float(value)

            # Atualiza label com direção
            if self.steering_value == 0:
                direction_text = "🏎️ Direção: 0° (Centro)"
            elif self.steering_value < 0:
                direction_text = (
                    f"🏎️ Direção: {abs(self.steering_value):.0f}° ⬅️ Esquerda"
                )
            else:
                direction_text = f"🏎️ Direção: {self.steering_value:.0f}° ➡️ Direita"

            self.steering_label.config(text=direction_text)

            # CORREÇÃO: Envia comando imediatamente quando muda
            if self.network_client:
                self._log(
                    "DEBUG",
                    f"🏎️ Direção: {old_steering:.0f}° → {self.steering_value:.0f}°",
                )
                # Thread separada para envio de rede (não bloqueia UI)
                threading.Thread(
                    target=self._send_command_async,
                    args=("STEERING", self.steering_value),
                    daemon=True,
                ).start()

        except Exception as e:
            self._log("ERROR", f"Erro ao processar mudança de direção: {e}")

    def _send_command_async(self, command_type: str, value: float):
        """Envia comando em thread separada para não travar UI"""
        try:
            self._send_command(command_type, value)
        except Exception as e:
            self._log("ERROR", f"Erro no envio assíncrono: {e}")

    def _send_command(self, command_type: str, value: float):
        """Envia comando para o Raspberry Pi"""
        try:
            if self.network_client:
                success = self.network_client.send_control_command(command_type, value)
                if success:
                    self.commands_sent += 1
                    return True
                else:
                    self._log(
                        "WARN", f"Falha ao enviar comando: {command_type}:{value}"
                    )
                    return False
            else:
                self._log("WARN", "Network client não disponível")
                return False

        except Exception as e:
            self._log("ERROR", f"Erro ao enviar comando {command_type}: {e}")
            return False

    def start(self):
        """Inicia o controlador de sliders"""
        if self.is_active:
            return

        self.is_active = True
        self.send_thread = threading.Thread(target=self._send_loop, daemon=True)
        self.send_thread.start()

        self._log("INFO", "Controlador de sliders iniciado")

    def stop(self):
        """Para o controlador de sliders"""
        if not self.is_active:
            return

        self.is_active = False

        try:
            # Envia comandos de parada
            self._send_command("THROTTLE", 0.0)
            self._send_command("BRAKE", 0.0)
        except Exception:
            pass

        # Aguarda thread de envio parar
        try:
            if self.send_thread and self.send_thread.is_alive():
                self.send_thread.join(timeout=1.0)
                if self.send_thread.is_alive():
                    self._log("WARN", "Thread de envio não finalizou no timeout")
        except Exception as e:
            self._log("ERROR", f"Erro ao parar thread de envio: {e}")

        # Limpa referências
        try:
            self.network_client = None
            self.log_callback = None
        except Exception:
            pass

        try:
            self._log("INFO", "Controlador de sliders parado")
        except Exception:
            pass

    def _send_loop(self):
        """Loop principal para envio contínuo de comandos"""
        while self.is_active:
            try:
                with self.lock:
                    # Envia throttle se mudou significativamente
                    if (
                        abs(self.throttle_value - self.last_sent_throttle)
                        >= self.min_change_threshold
                    ):
                        if self._send_command("THROTTLE", self.throttle_value):
                            self.last_sent_throttle = self.throttle_value

                    # Envia brake se mudou significativamente
                    if (
                        abs(self.brake_value - self.last_sent_brake)
                        >= self.min_change_threshold
                    ):
                        if self._send_command("BRAKE", self.brake_value):
                            self.last_sent_brake = self.brake_value

                # Aguarda próximo ciclo
                time.sleep(1.0 / self.send_rate)

            except Exception as e:
                self._log("ERROR", f"Erro no loop de envio: {e}")
                time.sleep(0.1)

    # ===== CALIBRATION METHODS =====

    def _send_serial_command(self, command: str) -> bool:
        """
        Envia comando serial para o ESP32

        Args:
            command: Comando a ser enviado

        Returns:
            bool: True se enviado com sucesso
        """
        if self.serial_sender:
            return self.serial_sender(command)
        else:
            self._log("WARN", "Serial sender não disponível para calibração")
            return False

    def _start_calibration(self, component: str):
        """Inicia calibração de um componente"""
        success = self.calibration_manager.start_calibration(component)

        if success:
            # Atualiza UI
            self._update_calibration_ui()

            # Desabilita botões de calibração
            self.cal_throttle_btn.config(state=tk.DISABLED)
            self.cal_brake_btn.config(state=tk.DISABLED)
            self.cal_steering_btn.config(state=tk.DISABLED)

            # Habilita botões de ação
            self.cal_save_btn.config(state=tk.NORMAL)
            self.cal_cancel_btn.config(state=tk.NORMAL)

            # Inicia atualização contínua
            self._schedule_calibration_update()

    def _save_calibration(self):
        """Salva calibração atual"""
        success = self.calibration_manager.save_calibration()

        if success:
            self._finish_calibration()

    def _cancel_calibration(self):
        """Cancela calibração atual"""
        self.calibration_manager.cancel_calibration()
        self._finish_calibration()

    def _finish_calibration(self):
        """Finaliza modo de calibração"""
        # Reabilita botões de calibração
        self.cal_throttle_btn.config(state=tk.NORMAL)
        self.cal_brake_btn.config(state=tk.NORMAL)
        self.cal_steering_btn.config(state=tk.NORMAL)

        # Desabilita botões de ação
        self.cal_save_btn.config(state=tk.DISABLED)
        self.cal_cancel_btn.config(state=tk.DISABLED)

        # Atualiza UI
        self.cal_status_label.config(text="Nenhuma calibração em andamento")
        self.cal_raw_value_label.config(text="Valor bruto: --")

    def _schedule_calibration_update(self):
        """Agenda próxima atualização da UI de calibração"""
        if self.calibration_manager.is_calibrating:
            self._update_calibration_ui()
            # Agenda próxima atualização (50ms = 20Hz)
            if (
                hasattr(self, "cal_status_label")
                and self.cal_status_label.winfo_exists()
            ):
                self.cal_status_label.after(50, self._schedule_calibration_update)

    def _update_calibration_ui(self):
        """Atualiza UI de calibração com status atual"""
        status = self.calibration_manager.get_calibration_status()

        if status["is_calibrating"]:
            # Atualiza instruções
            instructions = status["instructions"]
            self.cal_status_label.config(text=instructions, fg="#ffaa00")

            # Atualiza valor bruto
            raw_current = status["raw_current"]
            raw_min = status["raw_min"]
            raw_max = status["raw_max"]

            value_text = f"Valor bruto: {raw_current}"
            if raw_min is not None and raw_max is not None:
                value_text += (
                    f"  [Min: {raw_min}, Max: {raw_max}, Range: {raw_max - raw_min}]"
                )

            self.cal_raw_value_label.config(text=value_text)

    def update_calibration_raw_value(self, component: str, raw_value: int):
        """
        Atualiza valor bruto do encoder durante calibração

        Args:
            component: Componente sendo calibrado (THROTTLE, BRAKE, STEERING)
            raw_value: Valor bruto do encoder
        """
        self.calibration_manager.update_raw_value(component, raw_value)

    def set_serial_sender(self, serial_sender: Callable[[str], bool]):
        """Define função para enviar comandos seriais"""
        self.serial_sender = serial_sender
        if hasattr(self, "calibration_manager"):
            self.calibration_manager.serial_sender = self._send_serial_command
