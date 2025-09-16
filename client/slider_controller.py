#!/usr/bin/env python3
"""
slider_controller.py - Controlador de Sliders para F1 Car
Gerencia controles analógicos de throttle e brake via sliders
"""

import tkinter as tk
import tkinter.ttk as ttk
import time
import threading
from typing import Optional, Callable, Dict, Any
from simple_logger import info, debug, warn, error


class SliderController:
    """Gerenciador de controles analógicos (sliders) para throttle e brake"""

    def __init__(self, network_client=None, log_callback=None):
        """
        Inicializa o controlador de sliders

        Args:
            network_client: Cliente de rede para enviar comandos
            log_callback: Função de callback para logging na interface
        """
        self.network_client = network_client
        self.log_callback = log_callback

        # Estado dos controles
        self.throttle_value = 0.0  # 0-100%
        self.brake_value = 0.0     # 0-100%

        # Widgets dos sliders
        self.throttle_slider = None
        self.brake_slider = None
        self.throttle_label = None
        self.brake_label = None

        # Controle de envio
        self.is_active = False
        self.send_thread = None
        self.lock = threading.Lock()

        # Configurações
        self.send_rate = 20  # Comandos por segundo (50ms)
        self.min_change_threshold = 1.0  # Mínimo 1% de mudança para enviar

        # Últimos valores enviados (para evitar spam)
        self.last_sent_throttle = -1.0
        self.last_sent_brake = -1.0

        # Estatísticas
        self.commands_sent = 0
        self.start_time = time.time()

    def set_network_client(self, network_client):
        """Define o cliente de rede para envio de comandos"""
        self.network_client = network_client
        debug("Network client configurado no SliderController", "SLIDERS")

    def set_log_callback(self, log_callback):
        """Define callback para logging na interface"""
        self.log_callback = log_callback

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

        # Label do throttle
        self.throttle_label = tk.Label(
            throttle_frame,
            text="🚀 Throttle: 0%",
            bg="#3c3c3c",
            fg="#00d477",
            font=("Arial", 12, "bold")
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
            command=self._on_throttle_change
        )
        self.throttle_slider.pack()

        # Marcações do throttle
        throttle_marks = tk.Frame(throttle_frame, bg="#3c3c3c")
        throttle_marks.pack(pady=(5, 0))

        for i, mark in enumerate(["100%", "75%", "50%", "25%", "0%"]):
            label = tk.Label(
                throttle_marks,
                text=mark,
                bg="#3c3c3c",
                fg="#888888",
                font=("Arial", 8)
            )
            label.pack()

        # === BRAKE SLIDER ===
        brake_frame = tk.Frame(inner_frame, bg="#3c3c3c")
        brake_frame.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True, padx=10)

        # Label do brake
        self.brake_label = tk.Label(
            brake_frame,
            text="🛑 Brake: 0%",
            bg="#3c3c3c",
            fg="#ff4444",
            font=("Arial", 12, "bold")
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
            command=self._on_brake_change
        )
        self.brake_slider.pack()

        # Marcações do brake
        brake_marks = tk.Frame(brake_frame, bg="#3c3c3c")
        brake_marks.pack(pady=(5, 0))

        for i, mark in enumerate(["100%", "75%", "50%", "25%", "0%"]):
            label = tk.Label(
                brake_marks,
                text=mark,
                bg="#3c3c3c",
                fg="#888888",
                font=("Arial", 8)
            )
            label.pack()

        # === INSTRUÇÕES ===
        instructions = tk.Label(
            control_frame,
            text="Arraste os sliders para controlar throttle e brake de forma suave",
            bg="#3c3c3c",
            fg="#cccccc",
            font=("Arial", 9)
        )
        instructions.pack(pady=5)

        return control_frame

    def _on_throttle_change(self, value):
        """Callback para mudança no slider de throttle"""
        try:
            self.throttle_value = float(value)
            self.throttle_label.config(text=f"🚀 Throttle: {self.throttle_value:.0f}%")

            # Log apenas para mudanças significativas
            if abs(self.throttle_value - self.last_sent_throttle) >= 5.0:
                self._log("DEBUG", f"Throttle alterado para {self.throttle_value:.0f}%")

        except Exception as e:
            self._log("ERROR", f"Erro ao processar mudança de throttle: {e}")

    def _on_brake_change(self, value):
        """Callback para mudança no slider de brake"""
        try:
            self.brake_value = float(value)
            self.brake_label.config(text=f"🛑 Brake: {self.brake_value:.0f}%")

            # Log apenas para mudanças significativas
            if abs(self.brake_value - self.last_sent_brake) >= 5.0:
                self._log("DEBUG", f"Brake alterado para {self.brake_value:.0f}%")

        except Exception as e:
            self._log("ERROR", f"Erro ao processar mudança de brake: {e}")

    def _send_command(self, command_type: str, value: float):
        """Envia comando para o Raspberry Pi"""
        try:
            if self.network_client:
                success = self.network_client.send_control_command(command_type, value)
                if success:
                    self.commands_sent += 1
                    return True
                else:
                    self._log("WARN", f"Falha ao enviar comando: {command_type}:{value}")
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
            self._send_command('THROTTLE', 0.0)
            self._send_command('BRAKE', 0.0)
        except:
            pass

        try:
            if self.send_thread and self.send_thread.is_alive():
                self.send_thread.join(timeout=0.5)
        except:
            pass

        try:
            self._log("INFO", "Controlador de sliders parado")
        except:
            pass

    def _send_loop(self):
        """Loop principal para envio contínuo de comandos"""
        while self.is_active:
            try:
                with self.lock:
                    # Envia throttle se mudou significativamente
                    if abs(self.throttle_value - self.last_sent_throttle) >= self.min_change_threshold:
                        if self._send_command('THROTTLE', self.throttle_value):
                            self.last_sent_throttle = self.throttle_value

                    # Envia brake se mudou significativamente
                    if abs(self.brake_value - self.last_sent_brake) >= self.min_change_threshold:
                        if self._send_command('BRAKE', self.brake_value):
                            self.last_sent_brake = self.brake_value

                # Aguarda próximo ciclo
                time.sleep(1.0 / self.send_rate)

            except Exception as e:
                self._log("ERROR", f"Erro no loop de envio: {e}")
                time.sleep(0.1)

    def get_values(self) -> Dict[str, float]:
        """Retorna valores atuais dos sliders"""
        return {
            "throttle": self.throttle_value,
            "brake": self.brake_value
        }

    def set_values(self, throttle: Optional[float] = None, brake: Optional[float] = None):
        """Define valores dos sliders programaticamente"""
        try:
            if throttle is not None and self.throttle_slider:
                self.throttle_slider.set(throttle)

            if brake is not None and self.brake_slider:
                self.brake_slider.set(brake)
        except Exception as e:
            self._log("ERROR", f"Erro ao definir valores: {e}")

    def reset_controls(self):
        """Reseta todos os controles para zero"""
        self.set_values(throttle=0.0, brake=0.0)

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do controlador"""
        elapsed = time.time() - self.start_time

        return {
            "commands_sent": self.commands_sent,
            "throttle_value": self.throttle_value,
            "brake_value": self.brake_value,
            "is_active": self.is_active,
            "elapsed_time": round(elapsed, 2),
            "commands_per_second": round(self.commands_sent / elapsed, 2) if elapsed > 0 else 0,
        }


# Teste independente
if __name__ == "__main__":
    print("=== TESTE DO SLIDER CONTROLLER ===")

    # Simulação de network client
    class MockNetworkClient:
        def send_control_command(self, command_type, value):
            print(f"📡 COMANDO: {command_type} = {value:.1f}%")
            return True

    # Cria controlador
    mock_client = MockNetworkClient()
    controller = SliderController(network_client=mock_client)

    # Simula interface Tkinter básica
    root = tk.Tk()
    root.title("Teste Slider Controller")
    root.geometry("500x400")
    root.configure(bg="#3c3c3c")

    # Cria frame de controle
    control_frame = controller.create_control_frame(root)
    control_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

    # Inicia controlador
    controller.start()

    print("Interface iniciada - use os sliders para testar")
    print("Feche a janela para parar")

    try:
        root.mainloop()
    except KeyboardInterrupt:
        pass
    finally:
        controller.stop()
        print("Teste concluído")