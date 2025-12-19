"""
force_feedback_calc.py - Calculador de Force Feedback e Forças G
"""

from simple_logger import error


class ForceFeedbackCalculator:
    """Calcula forças G e force feedback baseado em dados do BMI160"""

    def __init__(self, console):
        """
        Args:
            console: Instância de ConsoleInterface
        """
        self.console = console
        self._filtered_steering_ff = 0.0
        self._last_steering_ff = 0.0

    def calculate_g_forces_and_ff(self, sensor_data):
        """
        Calcula forças G e force feedback baseado em dados raw do BMI160

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

            # Armazena forças G calculadas
            sensor_data["g_force_frontal"] = g_force_frontal
            sensor_data["g_force_lateral"] = g_force_lateral
            sensor_data["g_force_vertical"] = g_force_vertical

            # === CALCULA FORCE FEEDBACK DA DIREÇÃO ===
            # Componente 1: Força lateral (curvas)
            lateral_component = min(abs(g_force_lateral) * 50, 100)

            # Componente 2: Rotação (yaw)
            yaw_component = min(abs(gyro_z) / 60.0 * 50, 50)

            # Componente 3: Ângulo da direção (centering spring)
            steering_value = sensor_data.get("steering", 0)
            steering_angle_ratio = abs(steering_value) / 100.0
            centering_component = steering_angle_ratio * 40

            # Força base combinada (0-100%)
            base_steering_ff = min(
                lateral_component + yaw_component + centering_component, 100
            )

            # === APLICA PARÂMETROS DE FF (SLIDERS) ===
            damping = self.console.ff_damping_var.get() / 100.0
            friction = self.console.ff_friction_var.get() / 100.0
            filter_strength = self.console.ff_filter_var.get() / 100.0
            sensitivity = self.console.ff_sensitivity_var.get() / 100.0

            # PASSO 1: Aplica sensibilidade
            adjusted_ff = base_steering_ff * sensitivity

            # PASSO 2: Aplica friction
            friction_force = min(abs(gyro_z) / 100.0, 1.0) * friction * 30
            adjusted_ff = min(adjusted_ff + friction_force, 100.0)

            # PASSO 3: Aplica filter (suavização exponencial)
            adjusted_ff = (
                adjusted_ff * (1.0 - filter_strength)
                + self._filtered_steering_ff * filter_strength
            )
            self._filtered_steering_ff = adjusted_ff

            # PASSO 4: Aplica damping (média móvel)
            adjusted_ff = (
                adjusted_ff * (1.0 - damping) + self._last_steering_ff * damping
            )
            self._last_steering_ff = adjusted_ff

            # Limita ao intervalo 0-100%
            final_steering_ff = max(0.0, min(100.0, adjusted_ff))

            # Determina direção do force feedback
            centering_direction_value = -steering_value
            lateral_direction_value = g_force_lateral * 10
            yaw_direction_value = gyro_z

            total_direction_value = (
                centering_direction_value
                + lateral_direction_value
                + yaw_direction_value
            )

            if total_direction_value > 5:
                direction = "right"
            elif total_direction_value < -5:
                direction = "left"
            else:
                direction = "neutral"

            # Se a força for muito pequena, considera neutro
            if final_steering_ff < 5.0:
                direction = "neutral"

            # Armazena force feedback calculado
            sensor_data["steering_feedback_intensity"] = final_steering_ff
            sensor_data["steering_feedback_direction"] = direction

            # Outros force feedbacks (placeholders)
            sensor_data["brake_pedal_resistance"] = 0.0
            sensor_data["seat_vibration_intensity"] = 0.0
            sensor_data["seat_tilt_x"] = 0.0
            sensor_data["seat_tilt_y"] = 0.0

        except Exception as e:
            error(f"Erro ao calcular forças G e force feedback: {e}", "CONSOLE")

    def update_ff_leds(self, intensity: float, direction: str):
        """
        Atualiza LEDs de direção do force feedback

        Args:
            intensity: Intensidade da força (0-100%)
            direction: Direção da força ("left", "right", "neutral")
        """
        try:
            # Atualiza valor numérico
            self.console.steering_ff_intensity.config(text=f"{int(intensity)}")

            # Cor baseada na intensidade
            if intensity < 30:
                color = "#00ff00"  # Verde (baixo)
            elif intensity < 70:
                color = "#ffaa00"  # Laranja (médio)
            else:
                color = "#ff0000"  # Vermelho (alto)

            self.console.steering_ff_intensity.config(foreground=color)

            # Atualiza LEDs
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
            else:  # neutral
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
        Envia comando de Force Feedback para o ESP32 via serial

        Args:
            intensity: Intensidade da força (0-100%)
            direction: Direção da força ("left", "right", "neutral")

        Formato: FF_MOTOR:direction:intensity
        """
        try:
            direction_upper = direction.upper()
            intensity_int = int(intensity)
            command = f"FF_MOTOR:{direction_upper}:{intensity_int}"

            if hasattr(self.console, "serial_manager") and self.console.serial_manager:
                self.console.serial_manager.send_command(command)

        except Exception:
            # Não loga erro para não poluir o console (alta frequência)
            pass
