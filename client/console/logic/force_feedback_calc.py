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

Efeitos de hardware são atualizados via update_hardware_effects() quando
os sliders mudam. Efeitos dinâmicos são calculados a cada pacote do RPi.

Seleção inteligente de contexto:
- Idle: periodic leve (motor ligado), inertia base, spring + friction mínimos
- Acelerando: periodic aumenta com throttle, inertia sobe
- Curva: FF_CONSTANT empurra volante, spring mantém resistência
- Frenagem: rumble de impacto frontal, friction aumenta
- Impacto/bump: rumble forte de accel_z
"""

from simple_logger import error


class ForceFeedbackCalculator:
    """Calcula forças G e 7 efeitos de force feedback baseado em dados do BMI160"""

    # Vibração idle do motor (sempre ligado)
    IDLE_PERIODIC_PERIOD_MS = 40     # 25Hz — idle engine
    IDLE_PERIODIC_MAGNITUDE = 3.0    # 3% — vibração sutil

    # Limites de inertia
    IDLE_INERTIA_PCT = 5.0           # Inertia mínima (peso do volante parado)
    MAX_INERTIA_PCT = 80.0           # Inertia máxima em alta velocidade

    def __init__(self, console):
        """
        Args:
            console: Instância de ConsoleInterface
        """
        self.console = console

        # EMA filters para suavização
        self._filtered_constant_ff = 0.0
        self._filtered_rumble_strong = 0.0
        self._filtered_rumble_weak = 0.0
        self._filtered_inertia = self.IDLE_INERTIA_PCT

    def calculate_g_forces_and_ff(self, sensor_data):
        """
        Calcula forças G e todos os efeitos dinâmicos baseado em dados do BMI160.

        Efeitos calculados:
        - FF_CONSTANT: G lateral + yaw → direção do volante
        - FF_RUMBLE: accel_z (bumps) + accel_x (frenagem) → vibração
        - FF_PERIODIC: throttle → RPM do motor → vibração senoidal
        - FF_INERTIA: velocidade estimada → peso do volante

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

            # Obtém estado atual do G923 (throttle/brake para contexto)
            throttle = 0
            brake = 0
            g923 = self.console.g923_manager
            if g923 and g923.is_connected():
                throttle = g923._throttle
                brake = g923._brake

            # === 1. FF_CONSTANT: Forças dinâmicas (G lateral + yaw) ===
            lateral_component = min(abs(g_force_lateral) * 50, 100)
            yaw_component = min(abs(gyro_z) / 60.0 * 50, 50)
            base_ff = min(lateral_component + yaw_component, 100)

            sensitivity = self.console.ff_sensitivity_var.get() / 100.0
            adjusted_ff = base_ff * sensitivity

            filter_strength = self.console.ff_filter_var.get() / 100.0
            adjusted_ff = (
                adjusted_ff * (1.0 - filter_strength)
                + self._filtered_constant_ff * filter_strength
            )
            self._filtered_constant_ff = adjusted_ff
            final_ff = max(0.0, min(100.0, adjusted_ff))

            # Direção do FF_CONSTANT
            lateral_direction = g_force_lateral * 10
            yaw_direction = gyro_z
            total_direction = lateral_direction + yaw_direction
            if total_direction > 5:
                direction = "right"
            elif total_direction < -5:
                direction = "left"
            else:
                direction = "neutral"
            if final_ff < 5.0:
                direction = "neutral"

            sensor_data["steering_feedback_intensity"] = final_ff
            sensor_data["steering_feedback_direction"] = direction

            # === 2. FF_RUMBLE: Vibração de impactos + estrada ===
            # Desvio vertical (bumps): |accel_z - 9.81| normalizado
            vertical_deviation = abs(accel_z - 9.81) / 9.81
            road_vibration = min(vertical_deviation * 80, 100)

            # Impacto frontal (frenagem/aceleração brusca)
            frontal_impact = min(abs(g_force_frontal) * 40, 60)

            # Frenagem forte: adiciona rumble extra
            brake_rumble = min(brake / 100.0 * 20, 20) if brake > 30 else 0

            # Strong motor: impactos bruscos + frenagem
            strong_raw = min(road_vibration * 0.6 + frontal_impact * 0.3 + brake_rumble, 100)
            # Weak motor: vibração contínua leve (textura da estrada)
            weak_raw = min(road_vibration * 0.4, 40)

            # EMA para suavizar rumble
            self._filtered_rumble_strong = (
                strong_raw * 0.4 + self._filtered_rumble_strong * 0.6
            )
            self._filtered_rumble_weak = (
                weak_raw * 0.4 + self._filtered_rumble_weak * 0.6
            )

            sensor_data["rumble_strong"] = self._filtered_rumble_strong
            sensor_data["rumble_weak"] = self._filtered_rumble_weak

            # === 3. FF_PERIODIC: Motor (RPM simulado via throttle) ===
            # Frequência: idle 25Hz (40ms) → 50Hz (20ms) em throttle 100%
            # Magnitude: idle 3% → 30% em throttle 100%
            if throttle > 5:
                period_ms = int(40 - (throttle / 100.0 * 20))  # 40ms → 20ms
                periodic_magnitude = min(5 + throttle * 0.25, 30)
            else:
                period_ms = self.IDLE_PERIODIC_PERIOD_MS
                periodic_magnitude = self.IDLE_PERIODIC_MAGNITUDE

            sensor_data["periodic_period_ms"] = period_ms
            sensor_data["periodic_magnitude"] = periodic_magnitude

            # === 4. FF_INERTIA: Peso do volante (velocidade/throttle) ===
            # Em baixa velocidade: leve (fácil de girar)
            # Em alta velocidade: pesado (difícil de girar — realismo)
            speed_kmh = sensor_data.get("speed_kmh", 0)
            inertia_speed = min(abs(speed_kmh) / 100.0 * 50, 50)
            inertia_throttle = throttle / 100.0 * 25
            inertia_raw = max(
                self.IDLE_INERTIA_PCT,
                min(inertia_speed + inertia_throttle, self.MAX_INERTIA_PCT),
            )

            # EMA para suavizar transição de inertia
            self._filtered_inertia = (
                inertia_raw * 0.3 + self._filtered_inertia * 0.7
            )

            sensor_data["inertia"] = self._filtered_inertia

            # Placeholders para futura expansão
            sensor_data["brake_pedal_resistance"] = 0.0
            sensor_data["seat_vibration_intensity"] = self._filtered_rumble_strong
            sensor_data["seat_tilt_x"] = 0.0
            sensor_data["seat_tilt_y"] = 0.0

        except Exception as e:
            error(f"Erro ao calcular forças G e force feedback: {e}", "CONSOLE")

    def update_hardware_effects(self):
        """
        Atualiza efeitos de hardware baseado nos valores atuais dos sliders.
        Também aplica vibração idle e inertia base quando sem dados do RPi.

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

            # Inertia base (peso mínimo do volante)
            g923.update_inertia(self._filtered_inertia)

            # Vibração idle do motor (sempre ligada)
            g923.update_periodic(
                self.IDLE_PERIODIC_PERIOD_MS,
                self.IDLE_PERIODIC_MAGNITUDE,
            )

        except Exception as e:
            error(f"Erro ao atualizar efeitos hardware: {e}", "FF")

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
