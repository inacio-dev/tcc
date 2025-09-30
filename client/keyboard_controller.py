#!/usr/bin/env python3
"""
keyboard_controller.py - Controlador de Teclado para F1 Car
Gerencia comandos de teclado para controle do carrinho F1

MAPEAMENTO DE TECLAS:
====================
⬆️ Tecla M        → Subir marcha (GEAR_UP)
⬇️ Tecla N        → Descer marcha (GEAR_DOWN)
⬆️ Tecla M        → Subir marcha (GEAR_UP)
⬇️ Tecla N        → Descer marcha (GEAR_DOWN)

FUNCIONALIDADES:
===============
- Controle em tempo real com feedback visual
- Comandos enviados via UDP para Raspberry Pi
- Interface intuitiva como videogame
- Indicadores visuais de estado ativo
- Thread-safe e tolerante a falhas
"""

import tkinter as tk
import time
import threading
from typing import Optional, Callable, Dict, Any
from simple_logger import info, debug, warn, error


class KeyboardController:
    """Gerenciador de controles de teclado para o F1 Car"""

    # Mapeamento de teclas para comandos
    KEY_MAPPINGS = {
        # Controle de marcha (comandos instantâneos)
        "m": {
            "command": "GEAR_UP",
            "value": 1.0,
            "name": "⬆️ Subir Marcha (M)",
            "type": "instant",
        },
        "n": {
            "command": "GEAR_DOWN",
            "value": 1.0,
            "name": "⬇️ Descer Marcha (N)",
            "type": "instant",
        },
        "M": {
            "command": "GEAR_UP",
            "value": 1.0,
            "name": "⬆️ Subir Marcha (M)",
            "type": "instant",
        },
        "N": {
            "command": "GEAR_DOWN",
            "value": 1.0,
            "name": "⬇️ Descer Marcha (N)",
            "type": "instant",
        },
    }

    def __init__(self, network_client=None, log_callback=None):
        """
        Inicializa o controlador de teclado

        Args:
            network_client: Cliente de rede para enviar comandos
            log_callback: Função de callback para logging na interface
        """
        self.network_client = network_client
        self.log_callback = log_callback

        # Estado das teclas
        self.pressed_keys = set()  # Teclas atualmente pressionadas
        self.active_commands = {}  # Comandos ativos: {command_type: value}

        # Controle de threads
        self.is_active = False
        self.command_thread = None
        self.lock = threading.Lock()

        # Widgets visuais (para feedback)
        self.status_widgets = {}  # {command_type: widget}
        self.root = None  # Será definido quando vincular controles

        # Configurações
        self.command_rate = 20  # Comandos por segundo (50ms)
        self.key_repeat_delay = 100  # ms entre repetições

        # Estatísticas
        self.commands_sent = 0
        self.start_time = time.time()

    def set_network_client(self, network_client):
        """Define o cliente de rede para envio de comandos"""
        self.network_client = network_client
        debug("Network client configurado no KeyboardController", "KEYBOARD")

    def set_log_callback(self, log_callback):
        """Define callback para logging na interface"""
        self.log_callback = log_callback

    def _log(self, level: str, message: str):
        """Log com fallback"""
        if self.log_callback:
            self.log_callback(level, message)
        else:
            if level == "INFO":
                info(message, "KEYBOARD")
            elif level == "DEBUG":
                debug(message, "KEYBOARD")
            elif level == "WARN":
                warn(message, "KEYBOARD")
            elif level == "ERROR":
                error(message, "KEYBOARD")

    def bind_to_widget(self, widget):
        """
        Vincula eventos de teclado a um widget Tkinter

        Args:
            widget: Widget Tkinter para receber eventos de teclado
        """
        # Armazena referência ao root para after_idle
        self.root = widget.winfo_toplevel()

        # Garante que o widget pode receber foco
        widget.focus_set()

        # Vincula eventos de tecla
        widget.bind("<KeyPress>", self._on_key_press)
        widget.bind("<KeyRelease>", self._on_key_release)

        # Garante foco quando clicado
        widget.bind("<Button-1>", lambda e: widget.focus_set())

        self._log("INFO", "Controles de teclado vinculados à interface")

    def _on_key_press(self, event):
        """Callback para tecla pressionada - otimizado para não travar"""
        key = event.keysym

        # Processamento rápido sem locks demorados
        if key in self.KEY_MAPPINGS and key not in self.pressed_keys:
            # Processa em thread separada para não bloquear interface
            threading.Thread(
                target=self._process_key_press, args=(key,), daemon=True
            ).start()

    def _process_key_press(self, key):
        """Processa key press em thread separada"""
        try:
            with self.lock:
                if key not in self.pressed_keys:  # Recheck após lock
                    self.pressed_keys.add(key)
                    mapping = self.KEY_MAPPINGS[key]

                    if mapping["type"] == "continuous":
                        # Comando contínuo - ativa comando
                        self.active_commands[mapping["command"]] = mapping["value"]
                        self._log("DEBUG", f"Tecla pressionada: {mapping['name']}")

                    elif mapping["type"] == "instant":
                        # Comando instantâneo - envia imediatamente
                        self._send_command(mapping["command"], mapping["value"])
                        self._log("INFO", f"Comando enviado: {mapping['name']}")
                        # Flash visual para comando instantâneo
                        self._flash_instant_command(mapping["command"])

                    # Atualiza feedback visual de forma assíncrona
                    if hasattr(self, "root") and self.root:
                        self.root.after_idle(self._update_visual_feedback)
        except Exception as e:
            self._log("ERROR", f"Erro ao processar key press: {e}")

    def _on_key_release(self, event):
        """Callback para tecla liberada - otimizado para não travar"""
        key = event.keysym

        # Processamento rápido sem locks demorados
        if key in self.pressed_keys:
            # Processa em thread separada para não bloquear interface
            threading.Thread(
                target=self._process_key_release, args=(key,), daemon=True
            ).start()

    def _process_key_release(self, key):
        """Processa key release em thread separada"""
        try:
            with self.lock:
                if key in self.pressed_keys:  # Recheck após lock
                    self.pressed_keys.remove(key)
                    mapping = self.KEY_MAPPINGS[key]

                    if mapping["type"] == "continuous":
                        # Comando contínuo - desativa comando
                        if mapping["command"] in self.active_commands:
                            del self.active_commands[mapping["command"]]

                        self._log("DEBUG", f"Tecla liberada: {mapping['name']}")

                    elif mapping["type"] == "instant":
                        # Comando instantâneo - apenas log de liberação
                        self._log("DEBUG", f"Tecla liberada: {mapping['name']}")

                    # Atualiza feedback visual de forma assíncrona
                    if hasattr(self, "root") and self.root:
                        self.root.after_idle(self._update_visual_feedback)
        except Exception as e:
            self._log("ERROR", f"Erro ao processar key release: {e}")

    def _send_command(self, command_type: str, value: float):
        """Envia comando para o Raspberry Pi"""
        try:
            if self.network_client:
                success = self.network_client.send_control_command(command_type, value)
                if success:
                    self.commands_sent += 1
                    self._log("INFO", f"🚀 Comando enviado: {command_type}:{value}")
                else:
                    self._log(
                        "WARN", f"Falha ao enviar comando: {command_type}:{value}"
                    )
            else:
                self._log("WARN", "Network client não disponível")

        except Exception as e:
            self._log("ERROR", f"Erro ao enviar comando {command_type}: {e}")

    def start(self):
        """Inicia o controlador de teclado"""
        if self.is_active:
            return

        self.is_active = True
        self.command_thread = threading.Thread(target=self._command_loop, daemon=True)
        self.command_thread.start()

        self._log("INFO", "Controlador de teclado iniciado")
        self._log("INFO", "Use M/N para marchas e sliders para controles")

    def stop(self):
        """Para o controlador de teclado"""
        if not self.is_active:
            return

        self.is_active = False

        try:
            # Para todos os comandos ativos
            with self.lock:
                self.active_commands.clear()
                self.pressed_keys.clear()
        except:
            pass

        # Aguarda thread de comando parar
        try:
            if self.command_thread and self.command_thread.is_alive():
                self.command_thread.join(timeout=1.0)
                if self.command_thread.is_alive():
                    self._log("WARN", "Thread de comando não finalizou no timeout")
        except Exception as e:
            self._log("ERROR", f"Erro ao parar thread de comando: {e}")

        try:
            # Limpa widgets de status
            if hasattr(self, "status_widgets"):
                self.status_widgets.clear()
                self.status_widgets = {}
        except:
            pass

        # Limpa referências
        try:
            self.network_client = None
            self.log_callback = None
            self.root = None
        except:
            pass

        try:
            self._log("INFO", "Controlador de teclado parado")
        except:
            pass

    def _command_loop(self):
        """Loop principal para envio contínuo de comandos"""
        while self.is_active:
            try:
                with self.lock:
                    # Envia comandos ativos
                    for command_type, value in self.active_commands.items():
                        self._send_command(command_type, value)

                # Aguarda próximo ciclo
                time.sleep(1.0 / self.command_rate)

            except Exception as e:
                self._log("ERROR", f"Erro no loop de comandos: {e}")
                time.sleep(0.1)

    def _flash_instant_command(self, command_type: str):
        """Cria feedback visual flash para comandos instantâneos"""
        if command_type in self.status_widgets:
            widget = self.status_widgets[command_type]

            # Flash para verde por 200ms
            widget.config(bg="#00d477", fg="white")

            # Volta ao normal após 200ms
            def reset_color():
                widget.config(bg="#3c3c3c", fg="white")

            # Usa after do tkinter para agendar reset
            try:
                widget.after(200, reset_color)
            except:
                # Fallback se widget não está disponível
                pass

    def _update_visual_feedback(self):
        """Atualiza feedback visual dos controles ativos"""
        for command_type, widget in self.status_widgets.items():
            # Skip widgets de comando instantâneo que estão em flash
            if command_type in ["GEAR_UP", "GEAR_DOWN"]:
                continue

            if command_type in self.active_commands:
                # Comando ativo - destaca widget
                widget.config(bg="#0078d4", fg="white")
            else:
                # Comando inativo - cor normal
                widget.config(bg="#3c3c3c", fg="white")

    def create_status_frame(self, parent):
        """
        Cria frame com status visual dos controles

        Args:
            parent: Widget pai para criar o frame

        Returns:
            Frame criado com indicadores de status
        """
        import tkinter.ttk as ttk

        status_frame = ttk.LabelFrame(
            parent,
            text="⌨️ Controles de Teclado (Apenas Marchas)",
            style="Dark.TLabelframe",
        )

        # Grid para organizar os indicadores
        controls_grid = tk.Frame(status_frame, bg="#3c3c3c")
        controls_grid.pack(padx=10, pady=5)

        # Indicadores de marcha
        self.status_widgets["GEAR_DOWN"] = tk.Label(
            controls_grid,
            text="⬇️\nMarcha -\n(N)",
            bg="#3c3c3c",
            fg="white",
            font=("Arial", 9),
            width=12,
            height=3,
        )
        self.status_widgets["GEAR_DOWN"].grid(row=0, column=0, padx=5, pady=2)

        self.status_widgets["GEAR_UP"] = tk.Label(
            controls_grid,
            text="⬆️\nMarcha +\n(M)",
            bg="#3c3c3c",
            fg="white",
            font=("Arial", 9),
            width=12,
            height=3,
        )
        self.status_widgets["GEAR_UP"].grid(row=0, column=1, padx=5, pady=2)

        # Instruções
        instructions = tk.Label(
            status_frame,
            text="Clique na interface e use: M/N para marchas • Sliders para throttle/brake/direção",
            bg="#3c3c3c",
            fg="#cccccc",
            font=("Arial", 9),
        )
        instructions.pack(pady=5)

        return status_frame

    def get_statistics(self) -> Dict[str, Any]:
        """Retorna estatísticas do controlador"""
        elapsed = time.time() - self.start_time

        return {
            "commands_sent": self.commands_sent,
            "active_commands": len(self.active_commands),
            "pressed_keys": len(self.pressed_keys),
            "is_active": self.is_active,
            "elapsed_time": round(elapsed, 2),
            "commands_per_second": (
                round(self.commands_sent / elapsed, 2) if elapsed > 0 else 0
            ),
        }
