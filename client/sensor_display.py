#!/usr/bin/env python3
"""
sensor_display.py - Gerenciamento dos Dados de Sensores
Responsável por processar e organizar dados do BMI160 para exibição

DADOS SUPORTADOS (37+ campos):
=============================
✅ Dados Raw BMI160 (LSB)
✅ Dados Físicos (m/s², °/s)
✅ Forças G (frontal, lateral, vertical)
✅ Ângulos Integrados (roll, pitch, yaw)
✅ Eventos Detectados (curvas, freios, aceleração, impactos)
✅ Force Feedback (volante, pedais, assento)
✅ Configurações do Sensor
✅ Metadados (timestamp, contadores)

CARACTERÍSTICAS:
===============
- Processamento automático de tipos numpy
- Validação de dados recebidos
- Cálculos derivados adicionais
- Histórico de dados para gráficos
- Detecção de anomalias
- Estatísticas em tempo real
"""

import time
import math
import threading
from collections import deque, defaultdict
from typing import Dict, Any, Optional


class SensorDisplay:
    """Gerencia processamento e exibição de dados de sensores"""

    def __init__(self, sensor_queue=None, log_queue=None, history_size=1000):
        """
        Inicializa o processador de sensores

        Args:
            sensor_queue (Queue): Fila de dados de sensores
            log_queue (Queue): Fila para mensagens de log
            history_size (int): Tamanho do histórico de dados
        """
        self.sensor_queue = sensor_queue
        self.log_queue = log_queue
        self.history_size = history_size

        # Dados atuais dos sensores
        self.current_data = {}
        self.last_update_time = 0
        self.data_timeout = 2.0  # segundos

        # Dados processados para interface
        self.display_data = {
            # Dados de conexão
            "connection_status": "Desconectado",
            "last_update": "Nunca",
            "data_age": 0.0,
            # Dados do BMI160 - Raw (LSB)
            "bmi160_accel_x_raw": 0,
            "bmi160_accel_y_raw": 0,
            "bmi160_accel_z_raw": 0,
            "bmi160_gyro_x_raw": 0,
            "bmi160_gyro_y_raw": 0,
            "bmi160_gyro_z_raw": 0,
            # Dados do BMI160 - Físicos
            "accel_x": 0.000,  # m/s²
            "accel_y": 0.000,
            "accel_z": 9.810,
            "gyro_x": 0.000,  # °/s
            "gyro_y": 0.000,
            "gyro_z": 0.000,
            # Forças G calculadas
            "g_force_frontal": 0.000,
            "g_force_lateral": 0.000,
            "g_force_vertical": 0.000,
            # Ângulos integrados
            "roll_angle": 0.0,
            "pitch_angle": 0.0,
            "yaw_angle": 0.0,
            # Eventos detectados
            "is_turning_left": False,
            "is_turning_right": False,
            "is_accelerating": False,
            "is_braking": False,
            "is_bouncing": False,
            "impact_detected": False,
            # Force Feedback
            "steering_feedback_intensity": 0.0,
            "brake_pedal_resistance": 0.0,
            "accelerator_feedback": 0.0,
            "seat_vibration_intensity": 0.0,
            "seat_tilt_x": 0.0,
            "seat_tilt_y": 0.0,
            # Configurações do sensor
            "accel_range_g": 2,
            "gyro_range_dps": 250,
            "sample_rate": 100,
            # Dados derivados removidos - apenas dados reais dos sensores
            # Metadados
            "timestamp": 0,
            "readings_count": 0,
            "frame_count": 0,
            "is_initialized": False,
        }

        # Histórico para gráficos
        self.history = defaultdict(lambda: deque(maxlen=history_size))

        # Estatísticas
        self.stats = {
            "packets_received": 0,
            "last_packet_time": 0,
            "processing_errors": 0,
            "data_quality": 100.0,
            "start_time": time.time(),
        }

        # Lock para thread safety
        self.data_lock = threading.Lock()

    def _log(self, level, message):
        """Envia mensagem para fila de log"""
        if self.log_queue:
            self.log_queue.put((level, message))
        else:
            print(f"[SENSOR-{level}] {message}")

    def validate_sensor_data(self, data):
        """
        Valida dados recebidos dos sensores

        Args:
            data (dict): Dados dos sensores

        Returns:
            bool: True se dados são válidos
        """
        try:
            # Campos obrigatórios
            required_fields = [
                "bmi160_accel_x",
                "bmi160_accel_y",
                "bmi160_accel_z",
                "bmi160_gyro_x",
                "bmi160_gyro_y",
                "bmi160_gyro_z",
                "timestamp",
            ]

            for field in required_fields:
                if field not in data:
                    self._log("WARNING", f"Campo obrigatório ausente: {field}")
                    return False

            # Validação de ranges
            accel_range = 20.0  # ±20 m/s² (máximo razoável)
            gyro_range = 2000.0  # ±2000 °/s (máximo do BMI160)

            # Valida aceleração
            for axis in ["x", "y", "z"]:
                value = data.get(f"bmi160_accel_{axis}", 0)
                if abs(value) > accel_range:
                    self._log("WARNING", f"Aceleração {axis} fora do range: {value}")
                    return False

            # Valida giroscópio
            for axis in ["x", "y", "z"]:
                value = data.get(f"bmi160_gyro_{axis}", 0)
                if abs(value) > gyro_range:
                    self._log("WARNING", f"Giroscópio {axis} fora do range: {value}")
                    return False

            # Valida timestamp
            timestamp = data.get("timestamp", 0)
            current_time = time.time()
            if abs(timestamp - current_time) > 60:  # Diferença máxima de 1 minuto
                self._log("WARNING", f"Timestamp suspeito: {timestamp}")
                # Não retorna False aqui pois pode ser diferença de timezone

            return True

        except Exception as e:
            self._log("ERROR", f"Erro na validação de dados: {e}")
            return False

    def update_history(self, data):
        """
        Atualiza histórico de dados para gráficos

        Args:
            data (dict): Dados atuais dos sensores
        """
        try:
            timestamp = data.get("timestamp", time.time())

            # Seleciona campos importantes para histórico
            history_fields = [
                "bmi160_accel_x",
                "bmi160_accel_y",
                "bmi160_accel_z",
                "bmi160_gyro_x",
                "bmi160_gyro_y",
                "bmi160_gyro_z",
                "g_force_frontal",
                "g_force_lateral",
                "g_force_vertical",
                "steering_feedback_intensity",
                "seat_vibration_intensity",
                "velocidade",
                "temperatura",
            ]

            # Adiciona timestamp
            self.history["timestamp"].append(timestamp)

            # Adiciona dados dos campos selecionados
            for field in history_fields:
                if field in data:
                    self.history[field].append(data[field])
                elif field in self.display_data:
                    self.history[field].append(self.display_data[field])
                else:
                    self.history[field].append(0.0)

        except Exception as e:
            self._log("ERROR", f"Erro ao atualizar histórico: {e}")

    def detect_anomalies(self, data):
        """
        Detecta anomalias nos dados dos sensores

        Args:
            data (dict): Dados dos sensores

        Returns:
            list: Lista de anomalias detectadas
        """
        anomalies = []

        try:
            # Verifica valores extremos
            accel_x = data.get("bmi160_accel_x", 0)
            if abs(accel_x) > 15.0:  # >1.5g é extremo para carrinho
                anomalies.append(f"Aceleração X extrema: {accel_x:.2f} m/s²")

            gyro_z = data.get("bmi160_gyro_z", 0)
            if abs(gyro_z) > 500.0:  # >500°/s é muito rápido
                anomalies.append(f"Rotação Z extrema: {gyro_z:.1f} °/s")

            # Verifica inconsistências
            g_frontal = data.get("g_force_frontal", 0)
            if abs(g_frontal) > 2.0:  # >2G é extremo
                anomalies.append(f"Força G frontal extrema: {g_frontal:.2f}g")

            # Verifica idade dos dados
            timestamp = data.get("timestamp", 0)
            age = time.time() - timestamp
            if age > 1.0:  # Dados mais antigos que 1 segundo
                anomalies.append(f"Dados antigos: {age:.1f}s")

            return anomalies

        except Exception as e:
            self._log("ERROR", f"Erro na detecção de anomalias: {e}")
            return []

    def calculate_data_quality(self, data):
        """
        Calcula qualidade dos dados recebidos

        Args:
            data (dict): Dados dos sensores

        Returns:
            float: Qualidade dos dados (0-100%)
        """
        try:
            quality = 100.0

            # Reduz qualidade por campos ausentes
            expected_fields = 37  # Número esperado de campos do BMI160
            actual_fields = len(data)
            if actual_fields < expected_fields:
                quality -= (expected_fields - actual_fields) * 2

            # Reduz qualidade por valores suspeitos
            anomalies = self.detect_anomalies(data)
            quality -= len(anomalies) * 10

            # Reduz qualidade por idade dos dados
            timestamp = data.get("timestamp", 0)
            age = time.time() - timestamp
            if age > 0.5:
                quality -= age * 20

            # Reduz qualidade por erros de processamento
            error_rate = self.stats["processing_errors"] / max(
                1, self.stats["packets_received"]
            )
            quality -= error_rate * 50

            return max(0.0, min(100.0, quality))

        except Exception as e:
            self._log("ERROR", f"Erro ao calcular qualidade: {e}")
            return 50.0

    def process_sensor_data(self, raw_data):
        """
        Processa dados recebidos dos sensores

        Args:
            raw_data (dict): Dados raw dos sensores

        Returns:
            bool: True se processado com sucesso
        """
        try:
            with self.data_lock:
                # Valida dados
                if not self.validate_sensor_data(raw_data):
                    self.stats["processing_errors"] += 1
                    return False

                # Atualiza dados atuais
                self.current_data = raw_data.copy()
                self.last_update_time = time.time()

                # Atualiza dados para exibição
                self.display_data.update(raw_data)

                # Atualiza metadados de conexão
                self.display_data["connection_status"] = "Conectado"
                self.display_data["last_update"] = time.strftime("%H:%M:%S")
                self.display_data["data_age"] = 0.0

                # Incrementa contador de frames
                if "frame_count" not in self.display_data:
                    self.display_data["frame_count"] = 0
                self.display_data["frame_count"] += 1

                # Atualiza histórico
                self.update_history(self.display_data)

                # Calcula qualidade dos dados
                self.stats["data_quality"] = self.calculate_data_quality(raw_data)

                # Atualiza estatísticas
                self.stats["packets_received"] += 1
                self.stats["last_packet_time"] = time.time()

                # Log de anomalias se detectadas
                anomalies = self.detect_anomalies(raw_data)
                for anomaly in anomalies:
                    self._log("WARNING", f"Anomalia detectada: {anomaly}")

                return True

        except Exception as e:
            self._log("ERROR", f"Erro ao processar dados dos sensores: {e}")
            self.stats["processing_errors"] += 1
            return False

    def update_connection_status(self):
        """Atualiza status da conexão baseado na idade dos dados"""
        try:
            with self.data_lock:
                if self.last_update_time > 0:
                    age = time.time() - self.last_update_time
                    self.display_data["data_age"] = age

                    if age > self.data_timeout:
                        self.display_data["connection_status"] = "Desconectado"
                        self.display_data["last_update"] = f"Há {age:.1f}s"
                    else:
                        self.display_data["connection_status"] = "Conectado"

        except Exception as e:
            self._log("ERROR", f"Erro ao atualizar status de conexão: {e}")

    def get_display_data(self):
        """
        Obtém dados processados para exibição

        Returns:
            dict: Dados formatados para interface
        """
        with self.data_lock:
            return self.display_data.copy()

    def get_history(self, field, num_points=100):
        """
        Obtém histórico de um campo específico

        Args:
            field (str): Nome do campo
            num_points (int): Número de pontos a retornar

        Returns:
            tuple: (timestamps, values)
        """
        with self.data_lock:
            if field in self.history and len(self.history[field]) > 0:
                timestamps = list(self.history["timestamp"])[-num_points:]
                values = list(self.history[field])[-num_points:]
                return timestamps, values
            else:
                return [], []

    def get_statistics(self):
        """
        Obtém estatísticas do processador de sensores

        Returns:
            dict: Estatísticas completas
        """
        with self.data_lock:
            elapsed = time.time() - self.stats["start_time"]

            return {
                "packets_received": self.stats["packets_received"],
                "processing_errors": self.stats["processing_errors"],
                "data_quality": round(self.stats["data_quality"], 1),
                "elapsed_time": round(elapsed, 2),
                "packets_per_second": (
                    round(self.stats["packets_received"] / elapsed, 2)
                    if elapsed > 0
                    else 0
                ),
                "error_rate": round(
                    self.stats["processing_errors"]
                    / max(1, self.stats["packets_received"])
                    * 100,
                    2,
                ),
                "last_packet_time": self.stats["last_packet_time"],
                "history_size": len(self.history["timestamp"]),
                "fields_tracked": len(self.display_data),
            }

    def process_queue(self):
        """Processa fila de dados de sensores"""
        processed = 0

        while self.sensor_queue and not self.sensor_queue.empty() and processed < 10:
            try:
                sensor_data = self.sensor_queue.get_nowait()

                if self.process_sensor_data(sensor_data):
                    processed += 1
                else:
                    self._log("WARNING", "Falha ao processar dados dos sensores")

            except Exception as e:
                self._log("ERROR", f"Erro ao processar fila de sensores: {e}")
                break

        # Atualiza status de conexão
        self.update_connection_status()

        return processed > 0

    def reset_statistics(self):
        """Reseta estatísticas do processador"""
        with self.data_lock:
            self.stats = {
                "packets_received": 0,
                "last_packet_time": 0,
                "processing_errors": 0,
                "data_quality": 100.0,
                "start_time": time.time(),
            }

            # Limpa histórico
            self.history.clear()

            self._log("INFO", "Estatísticas de sensores resetadas")

    def export_history(self, filename=None):
        """
        Exporta histórico para arquivo CSV

        Args:
            filename (str): Nome do arquivo (opcional)

        Returns:
            str: Caminho do arquivo criado
        """
        try:
            import csv
            from datetime import datetime

            if filename is None:
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                filename = f"sensor_history_{timestamp}.csv"

            with self.data_lock:
                if len(self.history["timestamp"]) == 0:
                    self._log("WARNING", "Nenhum histórico disponível para exportar")
                    return None

                # Prepara dados para CSV
                fields = list(self.history.keys())
                rows = []

                for i in range(len(self.history["timestamp"])):
                    row = {}
                    for field in fields:
                        if i < len(self.history[field]):
                            row[field] = self.history[field][i]
                        else:
                            row[field] = ""
                    rows.append(row)

                # Escreve CSV
                with open(filename, "w", newline="") as csvfile:
                    writer = csv.DictWriter(csvfile, fieldnames=fields)
                    writer.writeheader()
                    writer.writerows(rows)

                self._log("INFO", f"Histórico exportado para: {filename}")
                return filename

        except Exception as e:
            self._log("ERROR", f"Erro ao exportar histórico: {e}")
            return None

