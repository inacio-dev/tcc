"""
velocity_calc.py - Calculador de velocidade baseado no BMI160
"""

import time

from simple_logger import error
from ..utils.constants import (
    ACCEL_THRESHOLD,
    VELOCITY_DECAY_FACTOR,
    MIN_VELOCITY_THRESHOLD,
)


class VelocityCalculator:
    """Calcula velocidade integrando aceleração do BMI160"""

    def __init__(self, console):
        """
        Args:
            console: Instância de ConsoleInterface
        """
        self.console = console
        self.velocity_x = 0.0  # Velocidade em m/s no eixo X
        self.velocity_y = 0.0  # Velocidade em m/s no eixo Y
        self.velocity_total = 0.0  # Velocidade total em km/h
        self.last_accel_time = None  # Timestamp da última leitura

    def calculate_velocity(self, sensor_data):
        """
        Calcula velocidade baseada nos dados de aceleração do BMI160

        Args:
            sensor_data (dict): Dados dos sensores incluindo aceleração
        """
        try:
            # Obtém dados de aceleração em m/s²
            accel_x = sensor_data.get("bmi160_accel_x", 0.0)  # Longitudinal
            accel_y = sensor_data.get("bmi160_accel_y", 0.0)  # Lateral

            current_time = time.time()

            # Inicializa tempo se for a primeira leitura
            if self.last_accel_time is None:
                self.last_accel_time = current_time
                return

            # Calcula delta time
            dt = current_time - self.last_accel_time
            self.last_accel_time = current_time

            # Ignora se dt muito pequeno ou muito grande
            if dt <= 0 or dt > 0.1:  # Máximo 100ms entre leituras
                return

            # Filtra ruído
            if abs(accel_x) < ACCEL_THRESHOLD:
                accel_x = 0.0
            if abs(accel_y) < ACCEL_THRESHOLD:
                accel_y = 0.0

            # Integração da aceleração para obter velocidade
            # v = v0 + a*dt
            self.velocity_x += accel_x * dt
            self.velocity_y += accel_y * dt

            # Aplicar decay para simular atrito/resistência do ar
            self.velocity_x *= VELOCITY_DECAY_FACTOR
            self.velocity_y *= VELOCITY_DECAY_FACTOR

            # Zera velocidades muito pequenas (evita deriva)
            if abs(self.velocity_x) < MIN_VELOCITY_THRESHOLD:
                self.velocity_x = 0.0
            if abs(self.velocity_y) < MIN_VELOCITY_THRESHOLD:
                self.velocity_y = 0.0

            # Calcula velocidade total (magnitude do vetor)
            velocity_ms = (self.velocity_x**2 + self.velocity_y**2) ** 0.5

            # Converte m/s para km/h
            self.velocity_total = velocity_ms * 3.6

            # Atualiza display da velocidade na seção BMI160
            if hasattr(self.console, "velocity_label"):
                self.console.velocity_label.config(
                    text=f"{self.velocity_total:.1f} km/h"
                )

        except Exception as e:
            error(f"Erro ao calcular velocidade: {e}", "CONSOLE")

    def reset(self):
        """Reseta os valores de velocidade"""
        self.velocity_x = 0.0
        self.velocity_y = 0.0
        self.velocity_total = 0.0
        self.last_accel_time = None
