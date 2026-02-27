"""
force_feedback_calc.py - Calculador de Force Feedback e Forças G

Arquitetura multi-efeito (7 efeitos simultâneos):

Condition effects (kernel ~1kHz):
- FF_SPRING:   Centering spring (slider Sensitivity)
- FF_DAMPER:   Damping (slider Damping)
- FF_FRICTION: Grip do pneu (slider Friction)
- FF_INERTIA:  Peso do volante (calculado pela velocidade)

Force effects (software, a cada pacote):
- FF_CONSTANT: Forças dinâmicas do BMI160 (G lateral + yaw)

Vibration effects:
- FF_RUMBLE:   Vibração de impactos/estrada (accel_z + accel_x)
- FF_PERIODIC: Vibração senoidal do motor (frequência via throttle)

Detecção de eventos via histórico do BMI160 (~333ms de buffer a 60Hz):
- Jerk frontal (derivada de accel_x): partida/frenagem brusca
- Jerk vertical (derivada de accel_z): bumps na pista
- Rugosidade (desvio padrão de accel_z): qualidade do asfalto
- Contexto combinado: curva + aceleração = vibrar + puxar simultaneamente
"""

import time
from collections import deque

from simple_logger import error


class ForceFeedbackCalculator:
    """Calcula forças G e 7 efeitos de force feedback baseado em dados do BMI160"""

    # Vibração idle do motor (sempre ligado)
    # NOTA: FF_GAIN a 15% escala tudo ×0.15, então magnitudes altas são necessárias
    # para compensar. Ex: 60% raw × 0.15 gain = 9% real no motor.
    IDLE_PERIODIC_PERIOD_MS = 200    # 5Hz — idle engine (motor perceptível)
    IDLE_PERIODIC_MAGNITUDE = 15.0   # 15% raw → ~2% real com gain 15%

    # Limites de inertia
    IDLE_INERTIA_PCT = 5.0           # Inertia mínima (peso do volante parado)
    MAX_INERTIA_PCT = 80.0           # Inertia máxima em alta velocidade

    # Histórico do BMI160 para detecção de eventos
    HISTORY_SIZE = 20                # ~333ms a 60Hz

    def __init__(self, console):
        """
        Args:
            console: Instância de ConsoleInterface
        """
        self.console = console

        # Histórico de leituras do BMI160 para derivadas e detecção de eventos
        self._history = deque(maxlen=self.HISTORY_SIZE)

        # EMA filters para suavização
        self._filtered_constant_ff = 0.0
        self._filtered_rumble_strong = 0.0
        self._filtered_rumble_weak = 0.0
        self._filtered_inertia = self.IDLE_INERTIA_PCT

    # ================================================================
    # HISTÓRICO E DETECÇÃO DE EVENTOS
    # ================================================================

    def _add_to_history(self, accel_x, accel_y, accel_z, gyro_z,
                        throttle, brake, steering):
        """Armazena leitura no buffer circular para análise temporal"""
        self._history.append({
            'ax': accel_x, 'ay': accel_y, 'az': accel_z,
            'gz': gyro_z, 'thr': throttle, 'brk': brake,
            'steer': steering, 't': time.monotonic(),
        })

    def _calc_jerk(self, key):
        """
        Calcula taxa de variação (jerk) de um sensor a partir do histórico.
        Jerk alto = evento brusco (partida, frenagem, bump).

        Returns:
            float: Derivada em unidades/segundo
        """
        if len(self._history) < 3:
            return 0.0
        h = list(self._history)
        n = min(5, len(h))
        samples = h[-n:]
        dt = samples[-1]['t'] - samples[0]['t']
        if dt < 0.001:
            return 0.0
        return (samples[-1][key] - samples[0][key]) / dt

    def _road_roughness(self):
        """
        Desvio padrão de accel_z no histórico → indicador de rugosidade da pista.
        Pista lisa ~0.1, pista irregular ~1.0+

        Returns:
            float: Desvio padrão de accel_z (m/s²)
        """
        if len(self._history) < 5:
            return 0.0
        samples = [s['az'] for s in list(self._history)[-10:]]
        mean = sum(samples) / len(samples)
        variance = sum((x - mean) ** 2 for x in samples) / len(samples)
        return variance ** 0.5

    # ================================================================
    # CÁLCULO PRINCIPAL
    # ================================================================

    def calculate_g_forces_and_ff(self, sensor_data):
        """
        Calcula forças G e todos os efeitos dinâmicos baseado em dados do BMI160.

        Usa histórico para detectar eventos (jerk, rugosidade) e combinar efeitos:
        - Curva: FF_CONSTANT puxa + rumble de stress nos pneus
        - Aceleração: periodic do motor + rumble contínuo
        - Frenagem: rumble forte + constant frontal
        - Bumps: rumble forte instantâneo

        Args:
            sensor_data (dict): Dados dos sensores incluindo aceleração e giroscópio
        """
        try:
            # Obtém dados de aceleração em m/s² (já convertidos pelo Raspberry Pi)
            accel_x = sensor_data.get("bmi160_accel_x", 0.0)  # Frontal
            accel_y = sensor_data.get("bmi160_accel_y", 0.0)  # Lateral
            accel_z = sensor_data.get("bmi160_accel_z", 9.81)  # Vertical

            # Obtém dados de giroscópio em °/s
            gyro_z = sensor_data.get("bmi160_gyro_z", 0.0)  # Rotação (yaw)

            # === CALCULA FORÇAS G ===
            g_force_frontal = accel_x / 9.81
            g_force_lateral = accel_y / 9.81
            g_force_vertical = (accel_z - 9.81) / 9.81

            sensor_data["g_force_frontal"] = g_force_frontal
            sensor_data["g_force_lateral"] = g_force_lateral
            sensor_data["g_force_vertical"] = g_force_vertical

            # Obtém estado atual do G923 (throttle/brake/steering para contexto)
            throttle = 0
            brake = 0
            steering = 0
            g923 = self.console.g923_manager
            if g923 and g923.is_connected():
                throttle = g923._throttle
                brake = g923._brake
                steering = g923._steering

            # Armazena no histórico para detecção de eventos
            self._add_to_history(
                accel_x, accel_y, accel_z, gyro_z, throttle, brake, steering
            )

            # === DETECÇÃO DE CONTEXTO ===
            is_accelerating = throttle > 10
            is_braking = brake > 10
            is_turning = abs(g_force_lateral) > 0.08 or abs(gyro_z) > 3

            # Jerk do BMI160: taxa de variação (detecta eventos bruscos)
            jerk_frontal = self._calc_jerk('ax')   # Partida/frenagem brusca
            jerk_vertical = self._calc_jerk('az')   # Bumps na pista

            # Jerk dos controles: mudanças bruscas nos inputs
            jerk_throttle = self._calc_jerk('thr')   # Aceleração repentina
            jerk_brake = self._calc_jerk('brk')      # Frenagem repentina
            jerk_steering = self._calc_jerk('steer')  # Virada brusca

            # Rugosidade da pista (histórico de accel_z)
            roughness = self._road_roughness()

            # === 1. FF_CONSTANT: Puxão lateral (G lateral + yaw) ===
            sensitivity = self.console.ff_sensitivity_var.get() / 100.0
            filter_strength = self.console.ff_filter_var.get() / 100.0

            lateral_component = min(abs(g_force_lateral) * 50, 100)
            yaw_component = min(abs(gyro_z) / 60.0 * 50, 50)
            base_ff = min(lateral_component + yaw_component, 100)

            adjusted_ff = base_ff * sensitivity
            adjusted_ff = (
                adjusted_ff * (1.0 - filter_strength)
                + self._filtered_constant_ff * filter_strength
            )
            self._filtered_constant_ff = adjusted_ff
            final_ff = max(0.0, min(100.0, adjusted_ff))

            # Direção do puxão
            lateral_dir = g_force_lateral * 10
            yaw_dir = gyro_z
            total_dir = lateral_dir + yaw_dir
            if total_dir > 1.5:
                direction = "right"
            elif total_dir < -1.5:
                direction = "left"
            else:
                direction = "neutral"
            if final_ff < 2.0:
                direction = "neutral"

            sensor_data["steering_feedback_intensity"] = final_ff
            sensor_data["steering_feedback_direction"] = direction

            # === 2. FF_RUMBLE: Vibração combinada ===
            # NOTA: FF_GAIN a 15% escala ×0.15, então raw 60% → 9% real.
            # Magnitudes altas (50-100%) são necessárias para sentir no volante.

            # Componente 1: Vibração do motor (proporcional ao throttle)
            # Principal fonte de vibração contínua — motor DC 775 vibra o chassi
            engine_vibration = throttle / 100.0 * 60  # 0-60% raw

            # Componente 2: Bumps verticais (desvio de accel_z da gravidade)
            vertical_dev = abs(accel_z - 9.81) / 9.81
            bump_vibration = min(vertical_dev * 400, 100)

            # Componente 3: Impacto frontal (frenagem/aceleração forte)
            frontal_impact = min(abs(g_force_frontal) * 200, 100)

            # Componente 4: Jerk BMI160 (eventos bruscos — partida, freada, bump)
            jerk_impact = min(abs(jerk_frontal) * 8, 80)
            jerk_bump = min(abs(jerk_vertical) * 8, 80)

            # Componente 5: Jerk controles (mudanças bruscas nos inputs)
            throttle_burst = min(abs(jerk_throttle) * 0.8, 60) if jerk_throttle > 30 else 0
            brake_burst = min(abs(jerk_brake) * 1.0, 80) if jerk_brake > 30 else 0
            steering_burst = min(abs(jerk_steering) * 0.6, 50) if abs(jerk_steering) > 20 else 0

            # Componente 6: Rugosidade da pista (histórico)
            roughness_vibration = min(roughness * 80, 70)

            # Componente 7: Stress lateral nos pneus (curva = vibração)
            turn_vibration = min(abs(g_force_lateral) * 150, 80) if is_turning else 0

            # Componente 8: Frenagem contínua
            brake_rumble = min(brake / 100.0 * 70, 70) if brake > 10 else 0

            # Strong motor: impactos + motor + frenagem + virada
            strong_raw = min(
                engine_vibration * 0.5
                + bump_vibration * 0.3
                + frontal_impact * 0.3
                + jerk_impact * 0.2
                + jerk_bump * 0.2
                + throttle_burst
                + brake_burst
                + steering_burst
                + brake_rumble * 0.5
                + turn_vibration * 0.3,
                100,
            )

            # Weak motor: vibração contínua (motor + rugosidade + curva)
            weak_raw = min(
                engine_vibration * 0.7
                + roughness_vibration
                + bump_vibration * 0.3
                + turn_vibration * 0.4
                + brake_rumble * 0.3,
                100,
            )

            # EMA para suavizar (mais responsivo: 60% novo, 40% antigo)
            self._filtered_rumble_strong = (
                strong_raw * 0.6 + self._filtered_rumble_strong * 0.4
            )
            self._filtered_rumble_weak = (
                weak_raw * 0.6 + self._filtered_rumble_weak * 0.4
            )

            sensor_data["rumble_strong"] = self._filtered_rumble_strong
            sensor_data["rumble_weak"] = self._filtered_rumble_weak

            # === 3. FF_PERIODIC: Vibração do motor ===
            # Frequência perceptível: 5Hz (200ms) idle → 12Hz (80ms) full throttle
            # Magnitude alta para compensar FF_GAIN 15%: 15% idle → 90% full
            if throttle > 5:
                period_ms = int(200 - (throttle / 100.0 * 120))  # 200ms → 80ms
                periodic_magnitude = min(15 + throttle * 0.75, 90)
            else:
                period_ms = self.IDLE_PERIODIC_PERIOD_MS
                periodic_magnitude = self.IDLE_PERIODIC_MAGNITUDE

            # Curva aumenta vibração (stress nos pneus transmite para direção)
            if is_turning:
                periodic_magnitude = min(periodic_magnitude + abs(g_force_lateral) * 40, 100)

            sensor_data["periodic_period_ms"] = period_ms
            sensor_data["periodic_magnitude"] = periodic_magnitude

            # === 4. FF_INERTIA: Peso do volante ===
            # Em baixa velocidade: leve (fácil de girar)
            # Em alta velocidade: pesado (difícil de girar — realismo)
            speed_kmh = sensor_data.get("speed_kmh", 0)
            inertia_speed = min(abs(speed_kmh) / 100.0 * 50, 50)
            inertia_throttle = throttle / 100.0 * 25
            inertia_raw = max(
                self.IDLE_INERTIA_PCT,
                min(inertia_speed + inertia_throttle, self.MAX_INERTIA_PCT),
            )

            # EMA para suavizar transição
            self._filtered_inertia = (
                inertia_raw * 0.3 + self._filtered_inertia * 0.7
            )

            sensor_data["inertia"] = self._filtered_inertia

            # === DIAGNÓSTICO: dados para UI de monitoramento ===
            # Contexto de condução
            ctx_parts = []
            if is_accelerating:
                ctx_parts.append("Acelerando")
            if is_braking:
                ctx_parts.append("Freando")
            if is_turning:
                ctx_parts.append("Curva")
            sensor_data["ff_context"] = " + ".join(ctx_parts) if ctx_parts else "Idle"

            # Jerks calculados
            sensor_data["ff_jerk_frontal"] = jerk_frontal
            sensor_data["ff_jerk_vertical"] = jerk_vertical
            sensor_data["ff_jerk_throttle"] = jerk_throttle
            sensor_data["ff_jerk_brake"] = jerk_brake
            sensor_data["ff_jerk_steering"] = jerk_steering
            sensor_data["ff_roughness"] = roughness

            # Placeholders para futura expansão
            sensor_data["brake_pedal_resistance"] = 0.0
            sensor_data["seat_vibration_intensity"] = self._filtered_rumble_strong
            sensor_data["seat_tilt_x"] = 0.0
            sensor_data["seat_tilt_y"] = 0.0

        except Exception as e:
            error(f"Erro ao calcular forças G e force feedback: {e}", "CONSOLE")

    # ================================================================
    # EFEITOS DE HARDWARE (sliders)
    # ================================================================

    def update_hardware_effects(self):
        """
        Atualiza efeitos condicionais (spring/damper/friction) dos sliders.
        Periodic e inertia NÃO são tocados aqui — são atualizados por
        send_dynamic_effects() quando dados do RPi chegam, ou definidos
        como idle na inicialização.

        Chamado periodicamente pelo process_queues() e quando sliders mudam.
        """
        try:
            g923 = self.console.g923_manager
            if not g923 or not g923.is_connected():
                return

            # Condition effects dos sliders
            sensitivity = self.console.ff_sensitivity_var.get()
            friction = self.console.ff_friction_var.get()
            damping = self.console.ff_damping_var.get()

            g923.update_spring(sensitivity)
            g923.update_damper(damping)
            g923.update_friction(friction)

        except Exception as e:
            error(f"Erro ao atualizar efeitos hardware: {e}", "FF")

    # ================================================================
    # EFEITOS DINÂMICOS (sensores BMI160)
    # ================================================================

    def send_dynamic_effects(self, sensor_data):
        """
        Envia efeitos dinâmicos (rumble, periodic, inertia) calculados
        por calculate_g_forces_and_ff() para o G923.

        Chamado após calculate_g_forces_and_ff() no update_sensor_data().
        """
        try:
            g923 = self.console.g923_manager
            if not g923 or not g923.is_connected():
                return

            # FF_RUMBLE: vibração de impactos + estrada
            strong = sensor_data.get("rumble_strong", 0)
            weak = sensor_data.get("rumble_weak", 0)
            g923.update_rumble(strong, weak)

            # FF_PERIODIC: vibração do motor (RPM)
            period = sensor_data.get("periodic_period_ms", self.IDLE_PERIODIC_PERIOD_MS)
            magnitude = sensor_data.get("periodic_magnitude", self.IDLE_PERIODIC_MAGNITUDE)
            g923.update_periodic(period, magnitude)

            # FF_INERTIA: peso do volante
            inertia = sensor_data.get("inertia", self.IDLE_INERTIA_PCT)
            g923.update_inertia(inertia)

        except Exception:
            pass

    # ================================================================
    # UI (LEDs + comando FF)
    # ================================================================

    def update_ff_leds(self, intensity: float, direction: str):
        """
        Atualiza LEDs de direção do force feedback

        Args:
            intensity: Intensidade da força (0-100%)
            direction: Direção da força ("left", "right", "neutral")
        """
        try:
            self.console.steering_ff_intensity.config(text=f"{int(intensity)}")

            if intensity < 30:
                color = "#00ff00"
            elif intensity < 70:
                color = "#ffaa00"
            else:
                color = "#ff0000"

            self.console.steering_ff_intensity.config(foreground=color)

            if direction == "left":
                self.console.ff_led_left.itemconfig(
                    self.console.ff_led_left_circle, fill="#ffaa00", outline="#ff8800"
                )
                self.console.ff_led_right.itemconfig(
                    self.console.ff_led_right_circle, fill="#333333", outline="#666666"
                )
            elif direction == "right":
                self.console.ff_led_left.itemconfig(
                    self.console.ff_led_left_circle, fill="#333333", outline="#666666"
                )
                self.console.ff_led_right.itemconfig(
                    self.console.ff_led_right_circle, fill="#00aaff", outline="#0088ff"
                )
            else:
                self.console.ff_led_left.itemconfig(
                    self.console.ff_led_left_circle, fill="#333333", outline="#666666"
                )
                self.console.ff_led_right.itemconfig(
                    self.console.ff_led_right_circle, fill="#333333", outline="#666666"
                )

        except Exception as e:
            error(f"Erro ao atualizar LEDs de FF: {e}", "CONSOLE")

    def send_ff_command(self, intensity: float, direction: str):
        """
        Envia FF_CONSTANT (forças dinâmicas) para o G923 via evdev

        Args:
            intensity: Intensidade da força (0-100%)
            direction: Direção da força ("left", "right", "neutral")
        """
        try:
            if hasattr(self.console, "g923_manager") and self.console.g923_manager:
                self.console.g923_manager.apply_constant_force(intensity, direction)
        except Exception:
            pass
