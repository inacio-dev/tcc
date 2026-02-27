#!/usr/bin/env python3
"""
g923_manager.py - Gerenciador do Volante Logitech G923

Lê inputs do volante G923 (steering, pedais, botões) via evdev e aplica
force feedback via múltiplos efeitos FF do Linux.

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

FORCE FEEDBACK (Multi-efeito):
==============================
8 efeitos simultâneos no hardware (63 slots disponíveis):

Condition effects (kernel ~1kHz):
- FF_SPRING:   Centering spring — kernel calcula baseado na posição do volante
- FF_DAMPER:   Damping — resistência proporcional à velocidade do volante
- FF_FRICTION: Friction — resistência constante ao movimento (grip do pneu)
- FF_INERTIA:  Inertia — peso do volante (aumenta com velocidade)

Force effects (software):
- FF_CONSTANT: Forças dinâmicas do BMI160 — G lateral + yaw
- FF_CONSTANT: Batente virtual — trava nos limites calibrados da direção (~1kHz)

Vibration effects (hardware):
- FF_RUMBLE:   Vibração de impactos/estrada (strong + weak motor)
- FF_PERIODIC: Vibração senoidal do motor (frequência = RPM)

Controle global via FF_GAIN (limita todos os efeitos simultaneamente).
Força mínima sempre ativa (simula peso mecânico do volante).

DETECÇÃO:
=========
Busca em /dev/input/event* por dispositivo com nome contendo "G923" ou
"Driving Force" que possua capabilities EV_ABS + EV_FF.

@author F1 RC Car Project
@date 2026-02-18
"""

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
    # 25% já trava o volante no G923, então 15% é um bom padrão para uso real
    # Alterável via set_ff_max_percent() ou parâmetro ff_max_percent no construtor
    FF_MAX_PERCENT_DEFAULT = 15

    # Força mínima sempre ativa (simula peso mecânico do volante/eixo)
    # Mesmo com sliders em 0%, esses valores mínimos garantem realismo
    MIN_SPRING_PCT = 5.0    # Centering mínimo (peso do eixo de direção)
    MIN_FRICTION_PCT = 3.0  # Atrito mínimo (resistência mecânica)

    # Batente virtual da direção (endstop)
    # Margem em % do range calibrado onde o endstop começa a atuar
    ENDSTOP_MARGIN_PCT = 5.0

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
                            Default: 15%. Valores acima de 25% podem travar o volante.
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

        # Force feedback — 8 efeitos simultâneos
        self._ff_spring_id = -1
        self._ff_damper_id = -1
        self._ff_friction_id = -1
        self._ff_inertia_id = -1
        self._ff_constant_id = -1
        self._ff_rumble_id = -1
        self._ff_periodic_id = -1
        self._ff_endstop_id = -1
        self._endstop_active = False
        self._ff_lock = threading.Lock()

        # Cache de valores FF — evita upload_effect redundante (ioctl bloqueante)
        self._last_spring_coeff = -1
        self._last_damper_coeff = -1
        self._last_friction_coeff = -1
        self._last_inertia_coeff = -1
        self._last_periodic_key = None
        self._last_rumble_key = None

        # Rate limiting — envio contínuo a 60Hz (~16.7ms entre envios)
        self._SEND_INTERVAL = 1.0 / 60.0  # ~16.7ms = 60Hz
        self._last_state_send = 0.0  # Timestamp do último envio STATE

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
    # FORCE FEEDBACK (Multi-efeito)
    # ================================================================

    def _init_force_feedback(self):
        """Inicializa 8 efeitos FF simultâneos no hardware do G923"""
        try:
            # FF_GAIN controla o limite global (slider Max Force)
            gain = int(self.ff_max_percent / 100.0 * 0xFFFF)
            self.device.write(ecodes.EV_FF, ecodes.FF_GAIN, gain)

            # Efeito 1: FF_SPRING — centering spring (kernel calcula baseado na posição)
            self._ff_spring_id = self._upload_condition_effect(
                ecodes.FF_SPRING, coeff=16384, saturation=16384
            )

            # Efeito 2: FF_DAMPER — resistência proporcional à velocidade do volante
            self._ff_damper_id = self._upload_condition_effect(
                ecodes.FF_DAMPER, coeff=16384, saturation=16384
            )

            # Efeito 3: FF_FRICTION — resistência constante ao movimento (grip do pneu)
            self._ff_friction_id = self._upload_condition_effect(
                ecodes.FF_FRICTION, coeff=8000, saturation=8000
            )

            # Efeito 4: FF_INERTIA — peso do volante (aumenta com velocidade)
            self._ff_inertia_id = self._upload_condition_effect(
                ecodes.FF_INERTIA, coeff=4000, saturation=8000
            )

            # Efeito 5: FF_CONSTANT — forças dinâmicas do BMI160 (G lateral + yaw)
            self._ff_constant_id = self._upload_constant_effect()

            # Efeito 6: FF_RUMBLE — vibração de impactos/estrada (strong + weak motor)
            self._ff_rumble_id = self._upload_rumble_effect(0, 0)

            # Efeito 7: FF_PERIODIC — vibração senoidal do motor (engine RPM)
            self._ff_periodic_id = self._upload_periodic_effect(100, 0)

            # Efeito 8: FF_CONSTANT (endstop) — batente virtual da direção
            self._ff_endstop_id = self._upload_constant_effect()

            active = sum(1 for eid in [
                self._ff_spring_id, self._ff_damper_id,
                self._ff_friction_id, self._ff_inertia_id,
                self._ff_constant_id, self._ff_rumble_id,
                self._ff_periodic_id, self._ff_endstop_id,
            ] if eid >= 0)
            self._log(
                "INFO",
                f"Force feedback multi-efeito: {active}/8 ativos "
                f"(gain={self.ff_max_percent:.0f}%)",
            )

        except Exception as e:
            self._log("WARN", f"Erro ao inicializar force feedback: {e}")

    def _upload_condition_effect(self, effect_type: int, coeff: int, saturation: int) -> int:
        """
        Cria e ativa um efeito condicional (spring/damper/friction).

        Args:
            effect_type: ecodes.FF_SPRING, FF_DAMPER ou FF_FRICTION
            coeff: Coeficiente de força (0-32767)
            saturation: Saturação máxima (0-32767)

        Returns:
            Effect ID ou -1 se falhar
        """
        try:
            cond = (ff.Condition * 2)(
                ff.Condition(saturation, saturation, coeff, coeff, 0, 0),
                ff.Condition(0, 0, 0, 0, 0, 0),  # eixo Y ignorado para volante
            )
            effect = ff.Effect(
                effect_type, -1, 0,
                ff.Trigger(0, 0),
                ff.Replay(0xFFFF, 0),
                ff.EffectType(ff_condition_effect=cond),
            )
            eid = self.device.upload_effect(effect)
            self.device.write(ecodes.EV_FF, eid, 1)
            return eid
        except Exception as e:
            self._log("WARN", f"Erro ao criar efeito FF type={effect_type}: {e}")
            return -1

    def _upload_constant_effect(self) -> int:
        """Cria e ativa efeito FF_CONSTANT com força 0 (neutro)"""
        try:
            effect = ff.Effect(
                ecodes.FF_CONSTANT, -1, 0,
                ff.Trigger(0, 0),
                ff.Replay(0xFFFF, 0),
                ff.EffectType(
                    ff_constant_effect=ff.Constant(0, ff.Envelope(0, 0, 0, 0))
                ),
            )
            eid = self.device.upload_effect(effect)
            self.device.write(ecodes.EV_FF, eid, 1)
            return eid
        except Exception as e:
            self._log("WARN", f"Erro ao criar efeito FF_CONSTANT: {e}")
            return -1

    def _upload_rumble_effect(self, strong: int, weak: int) -> int:
        """
        Cria e ativa efeito FF_RUMBLE (vibração com dois motores).

        Args:
            strong: Magnitude do motor forte (0-65535) — impactos
            weak: Magnitude do motor fraco (0-65535) — vibração contínua
        """
        try:
            effect = ff.Effect(
                ecodes.FF_RUMBLE, -1, 0,
                ff.Trigger(0, 0),
                ff.Replay(0xFFFF, 0),
                ff.EffectType(ff_rumble_effect=ff.Rumble(strong, weak)),
            )
            eid = self.device.upload_effect(effect)
            self.device.write(ecodes.EV_FF, eid, 1)
            return eid
        except Exception as e:
            self._log("WARN", f"Erro ao criar efeito FF_RUMBLE: {e}")
            return -1

    def _upload_periodic_effect(self, period_ms: int, magnitude: int) -> int:
        """
        Cria e ativa efeito FF_PERIODIC (onda senoidal — engine RPM).

        Args:
            period_ms: Período da onda em ms (40=25Hz idle, 20=50Hz high RPM)
            magnitude: Magnitude da vibração (0-32767)
        """
        try:
            per = ff.Periodic(
                ecodes.FF_SINE, max(1, period_ms), magnitude, 0, 0,
                ff.Envelope(0, 0, 0, 0),
            )
            effect = ff.Effect(
                ecodes.FF_PERIODIC, -1, 0,
                ff.Trigger(0, 0),
                ff.Replay(0xFFFF, 0),
                ff.EffectType(ff_periodic_effect=per),
            )
            eid = self.device.upload_effect(effect)
            self.device.write(ecodes.EV_FF, eid, 1)
            return eid
        except Exception as e:
            self._log("WARN", f"Erro ao criar efeito FF_PERIODIC: {e}")
            return -1

    def _update_condition_effect(self, effect_id: int, effect_type: int,
                                  coeff: int, saturation: int):
        """Atualiza coeficientes de um efeito condicional existente"""
        if effect_id < 0 or not self.device:
            return
        try:
            cond = (ff.Condition * 2)(
                ff.Condition(saturation, saturation, coeff, coeff, 0, 0),
                ff.Condition(0, 0, 0, 0, 0, 0),
            )
            effect = ff.Effect(
                effect_type, effect_id, 0,
                ff.Trigger(0, 0),
                ff.Replay(0xFFFF, 0),
                ff.EffectType(ff_condition_effect=cond),
            )
            self.device.upload_effect(effect)
        except Exception:
            pass

    def update_spring(self, coefficient_pct: float):
        """
        Atualiza FF_SPRING (centering spring).
        Força mínima de MIN_SPRING_PCT para simular peso mecânico.
        """
        pct = max(self.MIN_SPRING_PCT, min(100, coefficient_pct))
        coeff = int(pct / 100.0 * 32767)
        if coeff == self._last_spring_coeff:
            return
        with self._ff_lock:
            self._update_condition_effect(
                self._ff_spring_id, ecodes.FF_SPRING, coeff, coeff
            )
            self._last_spring_coeff = coeff

    def update_damper(self, coefficient_pct: float):
        """Atualiza FF_DAMPER (amortecimento)."""
        coeff = int(max(0, min(100, coefficient_pct)) / 100.0 * 32767)
        if coeff == self._last_damper_coeff:
            return
        with self._ff_lock:
            self._update_condition_effect(
                self._ff_damper_id, ecodes.FF_DAMPER, coeff, coeff
            )
            self._last_damper_coeff = coeff

    def update_friction(self, coefficient_pct: float):
        """
        Atualiza FF_FRICTION (atrito/grip do pneu).
        Força mínima de MIN_FRICTION_PCT para simular resistência mecânica.
        """
        pct = max(self.MIN_FRICTION_PCT, min(100, coefficient_pct))
        coeff = int(pct / 100.0 * 32767)
        if coeff == self._last_friction_coeff:
            return
        with self._ff_lock:
            self._update_condition_effect(
                self._ff_friction_id, ecodes.FF_FRICTION, coeff, coeff
            )
            self._last_friction_coeff = coeff

    def update_inertia(self, coefficient_pct: float):
        """Atualiza FF_INERTIA (peso do volante — aumenta com velocidade)."""
        coeff = int(max(0, min(100, coefficient_pct)) / 100.0 * 32767)
        if coeff == self._last_inertia_coeff:
            return
        with self._ff_lock:
            self._update_condition_effect(
                self._ff_inertia_id, ecodes.FF_INERTIA, coeff, coeff
            )
            self._last_inertia_coeff = coeff

    def update_rumble(self, strong_pct: float, weak_pct: float):
        """Atualiza FF_RUMBLE (vibração de impactos/estrada)."""
        if self._ff_rumble_id < 0 or not self.device:
            return
        strong = int(max(0, min(100, strong_pct)) / 100.0 * 65535)
        weak = int(max(0, min(100, weak_pct)) / 100.0 * 65535)
        key = (strong, weak)
        if key == self._last_rumble_key:
            return
        with self._ff_lock:
            try:
                effect = ff.Effect(
                    ecodes.FF_RUMBLE, self._ff_rumble_id, 0,
                    ff.Trigger(0, 0),
                    ff.Replay(0xFFFF, 0),
                    ff.EffectType(ff_rumble_effect=ff.Rumble(strong, weak)),
                )
                self.device.upload_effect(effect)
                self._last_rumble_key = key
            except Exception:
                pass

    def update_periodic(self, period_ms: int, magnitude_pct: float):
        """Atualiza FF_PERIODIC (vibração senoidal — engine RPM)."""
        if self._ff_periodic_id < 0 or not self.device:
            return
        mag = int(max(0, min(100, magnitude_pct)) / 100.0 * 32767)
        key = (max(1, period_ms), mag)
        if key == self._last_periodic_key:
            return
        with self._ff_lock:
            try:
                per = ff.Periodic(
                    ecodes.FF_SINE, key[0], mag, 0, 0,
                    ff.Envelope(0, 0, 0, 0),
                )
                effect = ff.Effect(
                    ecodes.FF_PERIODIC, self._ff_periodic_id, 0,
                    ff.Trigger(0, 0),
                    ff.Replay(0xFFFF, 0),
                    ff.EffectType(ff_periodic_effect=per),
                )
                self.device.upload_effect(effect)
                self._last_periodic_key = key
            except Exception:
                pass

    def apply_constant_force(self, intensity: float, direction: str):
        """
        Atualiza FF_CONSTANT (forças dinâmicas do BMI160).

        Args:
            intensity: Intensidade da força (0-100%)
            direction: Direção ("left", "right", "neutral")
        """
        if self._ff_constant_id < 0 or not self.device:
            return

        with self._ff_lock:
            try:
                level = int(max(0, min(100, intensity)) / 100.0 * 32767)

                if direction == "neutral":
                    level = 0

                if direction == "left":
                    ff_direction = 0x4000
                elif direction == "right":
                    ff_direction = 0xC000
                else:
                    ff_direction = 0

                effect = ff.Effect(
                    ecodes.FF_CONSTANT,
                    self._ff_constant_id,
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
                pass

    def apply_force_feedback(self, intensity: float, direction: str):
        """Wrapper de compatibilidade — chama apply_constant_force"""
        self.apply_constant_force(intensity, direction)

    def _update_endstop(self):
        """
        Batente virtual da direção — trava o volante nos limites calibrados.

        Quando o volante chega perto do limite (dentro de ENDSTOP_MARGIN_PCT),
        uma força crescente empurra de volta ao centro. No limite ou além,
        aplica força máxima (32767).

        Chamado a cada evento de steering (~1000Hz).
        """
        if self._ff_endstop_id < 0 or not self.device:
            return

        raw = self._raw_steering
        total_range = self._steer_max - self._steer_min
        if total_range <= 0:
            return

        margin = total_range * (self.ENDSTOP_MARGIN_PCT / 100.0)
        in_zone = (raw < self._steer_min + margin) or (raw > self._steer_max - margin)

        # Só faz upload quando entra/sai da zona (evita spam de uploads)
        if not in_zone and not self._endstop_active:
            return

        level = 0
        ff_direction = 0

        if raw <= self._steer_min:
            # Além do limite esquerdo: força máxima empurrando para direita
            level = 32767
            ff_direction = 0xC000
        elif raw < self._steer_min + margin:
            # Zona de endstop esquerda: força proporcional à proximidade do limite
            proportion = 1.0 - ((raw - self._steer_min) / margin)
            level = int(proportion * 32767)
            ff_direction = 0xC000
        elif raw >= self._steer_max:
            # Além do limite direito: força máxima empurrando para esquerda
            level = 32767
            ff_direction = 0x4000
        elif raw > self._steer_max - margin:
            # Zona de endstop direita: força proporcional à proximidade do limite
            proportion = 1.0 - ((self._steer_max - raw) / margin)
            level = int(proportion * 32767)
            ff_direction = 0x4000

        self._endstop_active = level > 0

        with self._ff_lock:
            try:
                effect = ff.Effect(
                    ecodes.FF_CONSTANT,
                    self._ff_endstop_id,
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
                pass

    def disable_endstop(self):
        """Desativa endstop temporariamente (ex: durante calibração)"""
        if self._ff_endstop_id >= 0 and self.device:
            with self._ff_lock:
                try:
                    self.device.write(ecodes.EV_FF, self._ff_endstop_id, 0)
                    self.device.erase_effect(self._ff_endstop_id)
                except Exception:
                    pass
                self._ff_endstop_id = -1
                self._endstop_active = False
            self._log("INFO", "Endstop desativado")

    def enable_endstop(self):
        """Reativa endstop após calibração"""
        if self._ff_endstop_id >= 0 or not self.device:
            return
        try:
            eid = self._upload_constant_effect()
            if eid >= 0:
                self._ff_endstop_id = eid
                self._log("INFO", "Endstop reativado")
        except Exception as e:
            self._log("WARN", f"Falha ao reativar endstop: {e}")

    def _stop_force_feedback(self):
        """Para e remove todos os 8 efeitos de force feedback"""
        effect_ids = [
            ("spring", self._ff_spring_id),
            ("damper", self._ff_damper_id),
            ("friction", self._ff_friction_id),
            ("inertia", self._ff_inertia_id),
            ("constant", self._ff_constant_id),
            ("rumble", self._ff_rumble_id),
            ("periodic", self._ff_periodic_id),
            ("endstop", self._ff_endstop_id),
        ]
        for name, eid in effect_ids:
            if eid >= 0 and self.device:
                try:
                    self.device.write(ecodes.EV_FF, eid, 0)
                    self.device.erase_effect(eid)
                except Exception:
                    pass
        self._ff_spring_id = -1
        self._ff_damper_id = -1
        self._ff_friction_id = -1
        self._ff_inertia_id = -1
        self._ff_constant_id = -1
        self._ff_rumble_id = -1
        self._ff_periodic_id = -1
        self._ff_endstop_id = -1
        self._endstop_active = False

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
                # Lê todos os eventos pendentes (non-blocking)
                event = self.device.read_one()

                if event is None:
                    # Sem eventos — envia estado atual (rate limiter a 60Hz)
                    self._send_current_state()
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

    def _send_current_state(self):
        """Envia estado unificado (steering,throttle,brake) a 60Hz"""
        now = time.time()
        if now - self._last_state_send < self._SEND_INTERVAL:
            return
        self._last_state_send = now

        if self.command_callback:
            # Comando unificado: STATE:steering,throttle,brake
            self.command_callback(
                "STATE", f"{self._steering},{self._throttle},{self._brake}"
            )
        self.commands_sent += 1
        self.last_command_time = now

    def _handle_axis(self, code: int, value: int):
        """Processa evento de eixo — atualiza estado interno apenas.
        O envio contínuo a 60Hz é feito por _send_current_state()."""

        if code == self.ABS_STEERING:
            self._raw_steering = value
            # Mapeia range do volante para -100 a +100
            center = (self._steer_min + self._steer_max) / 2
            half_range = (self._steer_max - self._steer_min) / 2
            if half_range > 0:
                normalized = (value - center) / half_range * 100.0
                self._steering = max(-100, min(100, int(normalized)))

            # Batente virtual — trava nos limites calibrados
            self._update_endstop()

        elif code == self.ABS_THROTTLE:
            self._raw_throttle = value
            # Mapeia para 0-100 (invertido: 0=pressionado, max=solto)
            total_range = self._throttle_max - self._throttle_min
            if total_range > 0:
                normalized = (self._throttle_max - value) / total_range * 100.0
                self._throttle = max(0, min(100, int(normalized)))

        elif code == self.ABS_BRAKE:
            self._raw_brake = value
            # Mapeia para 0-100 (invertido: 0=pressionado, max=solto)
            total_range = self._brake_max - self._brake_min
            if total_range > 0:
                normalized = (self._brake_max - value) / total_range * 100.0
                self._brake = max(0, min(100, int(normalized)))

    def _handle_button(self, code: int, value: int):
        """Processa evento de botão (paddle shifters)"""
        if value != 1:  # Só no press (ignora release)
            return

        if code == self.BTN_PADDLE_UP:
            self._send_callback("GEAR_UP", "")
        elif code == self.BTN_PADDLE_DOWN:
            self._send_callback("GEAR_DOWN", "")

    def _send_callback(self, command_type: str, value: str):
        """Envia comando via callback (usado para GEAR_UP/GEAR_DOWN)"""
        if self.command_callback:
            self.command_callback(command_type, value)
        self.commands_sent += 1
        self.last_command_time = time.time()

    # ================================================================
    # STATUS E CONFIGURAÇÃO
    # ================================================================

    def set_ff_max_percent(self, percent: float):
        """
        Altera FF_GAIN global (limita todos os efeitos no hardware).

        Args:
            percent: 0-100%. Valores acima de 25% podem travar o volante.
        """
        self.ff_max_percent = max(0.0, min(100.0, percent))
        if self.device:
            try:
                gain = int(self.ff_max_percent / 100.0 * 0xFFFF)
                self.device.write(ecodes.EV_FF, ecodes.FF_GAIN, gain)
            except Exception:
                pass
        self._log("INFO", f"FF_GAIN alterado para {self.ff_max_percent:.0f}%")

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
            "ff_active": self._ff_constant_id >= 0,
            "ff_effects": {
                "spring": self._ff_spring_id >= 0,
                "damper": self._ff_damper_id >= 0,
                "friction": self._ff_friction_id >= 0,
                "inertia": self._ff_inertia_id >= 0,
                "constant": self._ff_constant_id >= 0,
                "rumble": self._ff_rumble_id >= 0,
                "periodic": self._ff_periodic_id >= 0,
                "endstop": self._ff_endstop_id >= 0,
            },
            "ff_max_percent": self.ff_max_percent,
            "steering": self._steering,
            "throttle": self._throttle,
            "brake": self._brake,
        }
