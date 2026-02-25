#!/usr/bin/env python3
"""
g923_manager.py - Gerenciador do Volante Logitech G923

Lê inputs do volante G923 (steering, pedais, botões) via evdev e aplica
force feedback via efeitos FF_CONSTANT do Linux.

Substitui o ESP32 como dispositivo de entrada do simulador.

MAPEAMENTO DE EIXOS (Linux evdev - G923 versão Xbox):
======================================================
- ABS_X  → Steering (volante, 0-65535)
- ABS_Y  → Throttle (acelerador, 0-255, invertido)
- ABS_Z  → Brake (freio, 0-255, invertido)
- ABS_RZ → Não usado nesta versão (code=5, sem pedal físico)

MAPEAMENTO DE BOTÕES (G923 versão Xbox):
=========================================
- BTN_PINKIE (293) → Paddle esquerdo → GEAR_DOWN
- BTN_TOP2 (292)   → Paddle direito  → GEAR_UP

FORCE FEEDBACK:
===============
- FF_CONSTANT: Força direcional para simular G lateral, centering spring e damping
- Efeito uploaded uma vez, atualizado em tempo real via update()

DETECÇÃO:
=========
Busca em /dev/input/event* por dispositivo com nome contendo "G923" ou
"Driving Force" que possua capabilities EV_ABS + EV_FF.

@author F1 RC Car Project
@date 2026-02-18
"""

import struct
import threading
import time
from typing import Callable, Optional

try:
    import evdev
    from evdev import InputDevice, categorize, ecodes, ff

    EVDEV_AVAILABLE = True
except ImportError:
    EVDEV_AVAILABLE = False


class G923Manager:
    """Gerenciador de controle do Logitech G923 via evdev"""

    # Nomes conhecidos do G923 no Linux
    DEVICE_NAMES = ["G923", "Driving Force", "Logitech G923"]

    # Mapeamento de eixos (G923 versão Xbox)
    # ATENÇÃO: ABS_Y é o acelerador, NÃO embreagem nesta versão
    ABS_STEERING = ecodes.ABS_X if EVDEV_AVAILABLE else 0
    ABS_THROTTLE = ecodes.ABS_Y if EVDEV_AVAILABLE else 1
    ABS_BRAKE = ecodes.ABS_Z if EVDEV_AVAILABLE else 2

    # Botões dos paddle shifters (G923 versão Xbox)
    BTN_PADDLE_DOWN = 293  # BTN_PINKIE - paddle esquerdo
    BTN_PADDLE_UP = 292  # BTN_TOP2 - paddle direito

    # Deadzone para evitar ruído nos pedais
    PEDAL_DEADZONE = 3  # Percentual (0-100)
    STEERING_DEADZONE = 1  # Percentual (-100 a +100)

    # Limite padrão de force feedback (% do max do motor)
    # 30% já trava o volante no G923, então 15% é um bom padrão para uso real
    # Alterável via set_ff_max_percent() ou parâmetro ff_max_percent no construtor
    FF_MAX_PERCENT_DEFAULT = 15

    def __init__(
        self,
        command_callback: Optional[Callable[[str, str], None]] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
        ff_max_percent: Optional[float] = None,
    ):
        """
        Inicializa gerenciador do G923

        Args:
            command_callback: Função callback(tipo_comando, valor) — mesmo
                              formato do SerialReceiverManager
            log_callback: Função callback(nível, mensagem) para logs
            ff_max_percent: Limite máximo do force feedback (0-100%).
                            Default: 15%. Valores acima de 30% podem travar o volante.
        """
        self.command_callback = command_callback
        self.log_callback = log_callback
        self.ff_max_percent = ff_max_percent if ff_max_percent is not None else self.FF_MAX_PERCENT_DEFAULT

        # Dispositivo evdev
        self.device: Optional[InputDevice] = None
        self.device_name = ""
        self.device_path = ""

        # Thread de leitura
        self._running = False
        self._input_thread: Optional[threading.Thread] = None

        # Estado atual dos eixos (normalizado)
        self._steering = 0  # -100 a +100
        self._throttle = 0  # 0 a 100
        self._brake = 0  # 0 a 100

        # Valores brutos do evdev (para calibração)
        self._raw_steering = 0
        self._raw_throttle = 0
        self._raw_brake = 0

        # Últimos valores enviados (detecção de mudança)
        self._last_steering = -999
        self._last_throttle = -1
        self._last_brake = -1

        # Ranges dos eixos (preenchidos na detecção)
        self._steer_min = 0
        self._steer_max = 65535
        self._throttle_min = 0
        self._throttle_max = 255
        self._brake_min = 0
        self._brake_max = 255

        # Force feedback
        self._ff_effect_id = -1
        self._ff_lock = threading.Lock()

        # Estatísticas
        self.commands_sent = 0
        self.last_command_time = 0.0
        self.errors = 0

    def _log(self, level: str, message: str):
        """Envia mensagem de log"""
        if self.log_callback:
            self.log_callback(level, message)
        else:
            print(f"[{level}] G923: {message}")

    # ================================================================
    # DETECÇÃO E CONEXÃO
    # ================================================================

    def find_device(self) -> bool:
        """
        Busca o G923 nos dispositivos de input do sistema

        Returns:
            bool: True se encontrado e conectado
        """
        if not EVDEV_AVAILABLE:
            self._log("ERROR", "Módulo evdev não instalado (pip install evdev)")
            return False

        try:
            devices = [InputDevice(path) for path in evdev.list_devices()]
        except Exception as e:
            self._log("ERROR", f"Erro ao listar dispositivos: {e}")
            return False

        if not devices:
            self._log(
                "WARN",
                "Nenhum dispositivo de input encontrado. "
                "Verifique permissões (grupo 'input')",
            )
            return False

        for dev in devices:
            name_lower = dev.name.lower()
            is_g923 = any(n.lower() in name_lower for n in self.DEVICE_NAMES)

            if not is_g923:
                dev.close()
                continue

            # Verifica se tem eixos (EV_ABS) e force feedback (EV_FF)
            caps = dev.capabilities()
            has_abs = ecodes.EV_ABS in caps
            has_ff = ecodes.EV_FF in caps

            if not has_abs:
                self._log("WARN", f"G923 '{dev.name}' sem eixos (EV_ABS), pulando")
                dev.close()
                continue

            # Encontrou o dispositivo correto
            self.device = dev
            self.device_name = dev.name
            self.device_path = dev.path

            # Lê ranges dos eixos
            self._read_axis_ranges(caps)

            ff_status = "com FF" if has_ff else "sem FF"
            self._log(
                "INFO",
                f"G923 encontrado: {dev.name} ({dev.path}) [{ff_status}]",
            )

            # Inicializa force feedback se disponível
            if has_ff:
                self._init_force_feedback()

            return True

        self._log("WARN", "G923 não encontrado nos dispositivos de input")
        return False

    def _read_axis_ranges(self, caps: dict):
        """Lê os ranges min/max dos eixos do dispositivo"""
        abs_caps = caps.get(ecodes.EV_ABS, [])
        for abs_code, abs_info in abs_caps:
            if abs_code == self.ABS_STEERING:
                self._steer_min = abs_info.min
                self._steer_max = abs_info.max
                self._log(
                    "DEBUG",
                    f"Steering range: {abs_info.min} a {abs_info.max}",
                )
            elif abs_code == self.ABS_THROTTLE:
                self._throttle_min = abs_info.min
                self._throttle_max = abs_info.max
                self._log(
                    "DEBUG",
                    f"Throttle range: {abs_info.min} a {abs_info.max}",
                )
            elif abs_code == self.ABS_BRAKE:
                self._brake_min = abs_info.min
                self._brake_max = abs_info.max
                self._log(
                    "DEBUG",
                    f"Brake range: {abs_info.min} a {abs_info.max}",
                )

    # ================================================================
    # FORCE FEEDBACK
    # ================================================================

    def _init_force_feedback(self):
        """Inicializa efeito de force feedback FF_CONSTANT"""
        try:
            # Define ganho global FF no máximo
            self.device.write(ecodes.EV_FF, ecodes.FF_GAIN, 0xFFFF)

            # Cria efeito FF_CONSTANT com força 0 (neutro)
            effect = ff.Effect(
                ecodes.FF_CONSTANT,
                -1,  # id = -1 para novo efeito
                0,  # direction (será atualizado)
                ff.Trigger(0, 0),
                ff.Replay(0xFFFF, 0),  # duração infinita, sem delay
                ff.EffectType(ff_constant_effect=ff.Constant(0, ff.Envelope(0, 0, 0, 0))),
            )

            self._ff_effect_id = self.device.upload_effect(effect)

            # Inicia o efeito (roda continuamente)
            self.device.write(ecodes.EV_FF, self._ff_effect_id, 1)

            self._log("INFO", f"Force feedback inicializado (effect_id={self._ff_effect_id})")

        except Exception as e:
            self._log("WARN", f"Erro ao inicializar force feedback: {e}")
            self._ff_effect_id = -1

    def apply_force_feedback(self, intensity: float, direction: str):
        """
        Aplica force feedback no volante G923

        Args:
            intensity: Intensidade da força (0-100%)
            direction: Direção ("left", "right", "neutral")
        """
        if self._ff_effect_id < 0 or not self.device:
            return

        with self._ff_lock:
            try:
                # Converte intensidade 0-100% para level do evdev
                # Limita ao ff_max_percent para proteger o volante
                clamped = min(intensity, 100.0) * (self.ff_max_percent / 100.0)
                level = int((clamped / 100.0) * 32767)

                if direction == "neutral":
                    level = 0

                # direction em unidades evdev
                if direction == "left":
                    ff_direction = 0x4000
                elif direction == "right":
                    ff_direction = 0xC000
                else:
                    ff_direction = 0

                # Atualiza efeito existente (level sempre positivo, direction controla o lado)
                effect = ff.Effect(
                    ecodes.FF_CONSTANT,
                    self._ff_effect_id,
                    ff_direction,
                    ff.Trigger(0, 0),
                    ff.Replay(0xFFFF, 0),
                    ff.EffectType(
                        ff_constant_effect=ff.Constant(
                            level, ff.Envelope(0, 0, 0, 0)
                        )
                    ),
                )

                self.device.upload_effect(effect)

            except Exception:
                pass  # Não loga em alta frequência

    def _stop_force_feedback(self):
        """Para e remove efeito de force feedback"""
        if self._ff_effect_id >= 0 and self.device:
            try:
                self.device.write(ecodes.EV_FF, self._ff_effect_id, 0)
                self.device.erase_effect(self._ff_effect_id)
            except Exception:
                pass
            self._ff_effect_id = -1

    # ================================================================
    # LEITURA DE INPUTS
    # ================================================================

    def start(self) -> bool:
        """
        Inicia thread de leitura do G923

        Returns:
            bool: True se iniciado com sucesso
        """
        if self._running:
            self._log("WARN", "G923 já está em execução")
            return False

        if not self.device:
            if not self.find_device():
                return False

        self._running = True
        self._input_thread = threading.Thread(
            target=self._input_loop, daemon=True, name="G923-Input"
        )
        self._input_thread.start()

        self._log("INFO", "G923 leitura iniciada")
        return True

    def stop(self):
        """Para leitura e libera recursos"""
        self._log("INFO", "Parando G923...")
        self._running = False

        # Para force feedback
        self._stop_force_feedback()

        # Aguarda thread
        if self._input_thread and self._input_thread.is_alive():
            self._input_thread.join(timeout=2.0)

        # Fecha dispositivo
        if self.device:
            try:
                self.device.close()
            except Exception:
                pass
            self.device = None

        self._log("INFO", f"G923 parado - {self.commands_sent} comandos enviados")

    def _input_loop(self):
        """Loop principal de leitura de eventos do G923"""
        self._log("INFO", "Loop de input G923 iniciado")

        while self._running:
            try:
                # Lê evento com timeout para permitir checagem de _running
                event = self.device.read_one()

                if event is None:
                    time.sleep(0.001)  # 1ms - evita busy loop
                    continue

                if event.type == ecodes.EV_ABS:
                    self._handle_axis(event.code, event.value)
                elif event.type == ecodes.EV_KEY:
                    self._handle_button(event.code, event.value)

            except OSError:
                # Dispositivo desconectado
                self._log("ERROR", "G923 desconectado!")
                self._running = False
                break
            except Exception as e:
                self.errors += 1
                if self.errors % 100 == 1:
                    self._log("ERROR", f"Erro no loop de input: {e}")
                time.sleep(0.01)

        self._log("INFO", "Loop de input G923 parado")

    def _handle_axis(self, code: int, value: int):
        """Processa evento de eixo (steering, throttle, brake)"""

        if code == self.ABS_STEERING:
            self._raw_steering = value
            # Mapeia range do volante para -100 a +100
            center = (self._steer_min + self._steer_max) / 2
            half_range = (self._steer_max - self._steer_min) / 2
            if half_range > 0:
                normalized = (value - center) / half_range * 100.0
                self._steering = max(-100, min(100, int(normalized)))

            if abs(self._steering - self._last_steering) >= self.STEERING_DEADZONE:
                self._last_steering = self._steering
                self._send_callback("STEERING", str(self._steering))

        elif code == self.ABS_THROTTLE:
            self._raw_throttle = value
            # Mapeia para 0-100 (invertido: 0=pressionado, max=solto)
            total_range = self._throttle_max - self._throttle_min
            if total_range > 0:
                normalized = (self._throttle_max - value) / total_range * 100.0
                self._throttle = max(0, min(100, int(normalized)))

            if abs(self._throttle - self._last_throttle) >= self.PEDAL_DEADZONE:
                self._last_throttle = self._throttle
                self._send_callback("THROTTLE", str(self._throttle))

        elif code == self.ABS_BRAKE:
            self._raw_brake = value
            # Mapeia para 0-100 (invertido: 0=pressionado, max=solto)
            total_range = self._brake_max - self._brake_min
            if total_range > 0:
                normalized = (self._brake_max - value) / total_range * 100.0
                self._brake = max(0, min(100, int(normalized)))

            if abs(self._brake - self._last_brake) >= self.PEDAL_DEADZONE:
                self._last_brake = self._brake
                self._send_callback("BRAKE", str(self._brake))

    def _handle_button(self, code: int, value: int):
        """Processa evento de botão (paddle shifters)"""
        if value != 1:  # Só no press (ignora release)
            return

        if code == self.BTN_PADDLE_UP:
            self._send_callback("GEAR_UP", "")
        elif code == self.BTN_PADDLE_DOWN:
            self._send_callback("GEAR_DOWN", "")

    def _send_callback(self, command_type: str, value: str):
        """Envia comando via callback"""
        if self.command_callback:
            self.command_callback(command_type, value)
        self.commands_sent += 1
        self.last_command_time = time.time()

    # ================================================================
    # STATUS E CONFIGURAÇÃO
    # ================================================================

    def set_ff_max_percent(self, percent: float):
        """
        Altera o limite máximo do force feedback em tempo real

        Args:
            percent: 0-100%. Valores acima de 30% podem travar o volante.
        """
        self.ff_max_percent = max(0.0, min(100.0, percent))
        self._log("INFO", f"FF max alterado para {self.ff_max_percent:.0f}%")

    def is_connected(self) -> bool:
        """Verifica se o G923 está conectado e ativo"""
        return self.device is not None and self._running

    def get_statistics(self) -> dict:
        """Retorna estatísticas do G923"""
        return {
            "connected": self.is_connected(),
            "device_name": self.device_name,
            "device_path": self.device_path,
            "running": self._running,
            "commands_sent": self.commands_sent,
            "errors": self.errors,
            "last_command_time": self.last_command_time,
            "ff_active": self._ff_effect_id >= 0,
            "ff_max_percent": self.ff_max_percent,
            "steering": self._steering,
            "throttle": self._throttle,
            "brake": self._brake,
        }
