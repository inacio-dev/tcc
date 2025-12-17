#!/usr/bin/env python3
"""
analyze_session.py - Analisador de Sessões F1 Car

Analisa dados salvos pelo auto-save:
- sensors_*.pkl - Dados brutos dos sensores BMI160
- telemetry_*.pkl - Dados dos gráficos de telemetria
- logs_*.txt - Logs do console

Uso:
    python analyze_session.py                     # Analisa arquivos mais recentes
    python analyze_session.py --dir exports/auto  # Especifica diretório
    python analyze_session.py --file telemetry_20241217_143000.pkl  # Arquivo específico
    python analyze_session.py --all               # Analisa todos os arquivos
    python analyze_session.py --export report.html  # Exporta relatório HTML

Autor: F1 Car TCC Project
"""

import os
import sys
import pickle
import argparse
import re
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

# Adiciona diretório pai ao path para imports
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False
    print("[WARN] NumPy não instalado. Estatísticas limitadas.")

try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    from matplotlib.gridspec import GridSpec
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    print("[WARN] Matplotlib não instalado. Gráficos desabilitados.")


# Cores estilo F1
COLORS = {
    'speed': '#00D2BE',
    'throttle': '#00FF00',
    'brake': '#FF0000',
    'g_lateral': '#FF8700',
    'g_frontal': '#0090FF',
    'accel_x': '#FF5555',
    'accel_y': '#55FF55',
    'accel_z': '#5555FF',
    'gyro_x': '#FFAA00',
    'gyro_y': '#00FFAA',
    'gyro_z': '#AA00FF',
    'background': '#1E1E1E',
    'grid': '#3C3C3C',
    'text': '#FFFFFF',
}


@dataclass
class SessionStats:
    """Estatísticas de uma sessão"""
    duration_seconds: float = 0.0
    total_points: int = 0

    # Velocidade
    speed_max: float = 0.0
    speed_avg: float = 0.0
    speed_min: float = 0.0

    # Pedais
    throttle_avg: float = 0.0
    brake_avg: float = 0.0
    full_throttle_percent: float = 0.0
    braking_percent: float = 0.0

    # G-Forces
    g_lateral_max: float = 0.0
    g_lateral_min: float = 0.0
    g_frontal_max: float = 0.0
    g_frontal_min: float = 0.0

    # Aceleração
    accel_x_max: float = 0.0
    accel_y_max: float = 0.0
    accel_z_max: float = 0.0

    # Giroscópio
    gyro_z_max: float = 0.0  # Rotação máxima (curvas)

    # Power Monitor
    current_motor_max: float = 0.0
    current_motor_avg: float = 0.0
    power_total_max: float = 0.0
    power_total_avg: float = 0.0
    voltage_rpi_avg: float = 0.0


class SessionAnalyzer:
    """Analisador de sessões do F1 Car"""

    def __init__(self, data_dir: str = "exports/auto"):
        self.data_dir = Path(data_dir)
        self.telemetry_data: Optional[Dict] = None
        self.sensor_data: Optional[Dict] = None
        self.log_content: Optional[str] = None
        self.stats = SessionStats()

    def find_latest_files(self) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
        """Encontra os arquivos mais recentes de cada tipo"""
        telemetry_files = sorted(self.data_dir.glob("telemetry_*.pkl"), reverse=True)
        sensor_files = sorted(self.data_dir.glob("sensors_*.pkl"), reverse=True)
        log_files = sorted(self.data_dir.glob("logs_*.txt"), reverse=True)

        return (
            telemetry_files[0] if telemetry_files else None,
            sensor_files[0] if sensor_files else None,
            log_files[0] if log_files else None
        )

    def find_matching_files(self, timestamp: str) -> Tuple[Optional[Path], Optional[Path], Optional[Path]]:
        """Encontra arquivos com o mesmo timestamp"""
        telemetry = self.data_dir / f"telemetry_{timestamp}.pkl"
        sensors = self.data_dir / f"sensors_{timestamp}.pkl"
        logs = self.data_dir / f"logs_{timestamp}.txt"

        return (
            telemetry if telemetry.exists() else None,
            sensors if sensors.exists() else None,
            logs if logs.exists() else None
        )

    def load_telemetry(self, filepath: Path) -> bool:
        """Carrega dados de telemetria"""
        try:
            with open(filepath, "rb") as f:
                self.telemetry_data = pickle.load(f)
            print(f"[OK] Telemetria carregada: {filepath.name}")
            print(f"     Pontos: {self.telemetry_data.get('points_count', len(self.telemetry_data.get('time', [])))}")
            return True
        except Exception as e:
            print(f"[ERRO] Falha ao carregar telemetria: {e}")
            return False

    def load_sensors(self, filepath: Path) -> bool:
        """Carrega dados de sensores"""
        try:
            with open(filepath, "rb") as f:
                self.sensor_data = pickle.load(f)
            print(f"[OK] Sensores carregados: {filepath.name}")

            # Conta pontos
            if "timestamp" in self.sensor_data:
                print(f"     Pontos: {len(self.sensor_data['timestamp'])}")
            return True
        except Exception as e:
            print(f"[ERRO] Falha ao carregar sensores: {e}")
            return False

    def load_logs(self, filepath: Path) -> bool:
        """Carrega arquivo de logs"""
        try:
            with open(filepath, "r", encoding="utf-8") as f:
                self.log_content = f.read()
            lines = self.log_content.count('\n')
            print(f"[OK] Logs carregados: {filepath.name}")
            print(f"     Linhas: {lines}")
            return True
        except Exception as e:
            print(f"[ERRO] Falha ao carregar logs: {e}")
            return False

    def load_all_files(self) -> Tuple[int, int, int]:
        """
        Carrega e combina TODOS os arquivos da pasta exports

        Returns:
            Tuple com contagem de arquivos carregados (telemetry, sensors, logs)
        """
        telemetry_count = self._load_all_telemetry()
        sensor_count = self._load_all_sensors()
        log_count = self._load_all_logs()

        return telemetry_count, sensor_count, log_count

    def _load_all_telemetry(self) -> int:
        """Carrega e combina todos os arquivos de telemetria"""
        telemetry_files = sorted(self.data_dir.glob("telemetry_*.pkl"))

        if not telemetry_files:
            print("[INFO] Nenhum arquivo de telemetria encontrado")
            return 0

        print(f"\n--- Carregando {len(telemetry_files)} arquivos de telemetria ---")

        combined_data = {}
        total_points = 0

        for filepath in telemetry_files:
            try:
                with open(filepath, "rb") as f:
                    data = pickle.load(f)

                # Combina os dados
                for key, values in data.items():
                    if key in ["start_time", "max_points", "export_time", "points_count"]:
                        continue  # Pula metadados

                    if isinstance(values, list):
                        if key not in combined_data:
                            combined_data[key] = []
                        combined_data[key].extend(values)

                points = data.get("points_count", len(data.get("time", [])))
                total_points += points
                print(f"  [+] {filepath.name}: {points} pontos")

            except Exception as e:
                print(f"  [!] Erro em {filepath.name}: {e}")

        if combined_data:
            self.telemetry_data = combined_data
            self.telemetry_data["points_count"] = total_points
            print(f"[OK] Total telemetria: {total_points} pontos de {len(telemetry_files)} arquivos")

        return len(telemetry_files)

    def _load_all_sensors(self) -> int:
        """Carrega e combina todos os arquivos de sensores"""
        sensor_files = sorted(self.data_dir.glob("sensors_*.pkl"))

        if not sensor_files:
            print("[INFO] Nenhum arquivo de sensores encontrado")
            return 0

        print(f"\n--- Carregando {len(sensor_files)} arquivos de sensores ---")

        combined_data = {}
        total_points = 0

        for filepath in sensor_files:
            try:
                with open(filepath, "rb") as f:
                    data = pickle.load(f)

                # Combina os dados
                for key, values in data.items():
                    if isinstance(values, (list, tuple)):
                        if key not in combined_data:
                            combined_data[key] = []
                        combined_data[key].extend(list(values))

                points = len(data.get("timestamp", []))
                total_points += points
                print(f"  [+] {filepath.name}: {points} pontos")

            except Exception as e:
                print(f"  [!] Erro em {filepath.name}: {e}")

        if combined_data:
            self.sensor_data = combined_data
            print(f"[OK] Total sensores: {total_points} pontos de {len(sensor_files)} arquivos")

        return len(sensor_files)

    def _load_all_logs(self) -> int:
        """Carrega e concatena todos os arquivos de logs"""
        log_files = sorted(self.data_dir.glob("logs_*.txt"))

        if not log_files:
            print("[INFO] Nenhum arquivo de logs encontrado")
            return 0

        print(f"\n--- Carregando {len(log_files)} arquivos de logs ---")

        combined_logs = []
        total_lines = 0

        for filepath in log_files:
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    content = f.read()

                lines = content.count('\n')
                total_lines += lines
                combined_logs.append(f"\n{'='*60}\n# Arquivo: {filepath.name}\n{'='*60}\n")
                combined_logs.append(content)
                print(f"  [+] {filepath.name}: {lines} linhas")

            except Exception as e:
                print(f"  [!] Erro em {filepath.name}: {e}")

        if combined_logs:
            self.log_content = "\n".join(combined_logs)
            print(f"[OK] Total logs: {total_lines} linhas de {len(log_files)} arquivos")

        return len(log_files)

    def calculate_stats(self):
        """Calcula estatísticas da sessão"""
        if not NUMPY_AVAILABLE:
            print("[WARN] NumPy necessário para estatísticas completas")
            return

        # Estatísticas de telemetria
        if self.telemetry_data:
            time_data = self.telemetry_data.get("time", [])
            if time_data:
                self.stats.duration_seconds = max(time_data) - min(time_data)
                self.stats.total_points = len(time_data)

            speed = np.array(self.telemetry_data.get("speed", []))
            if len(speed) > 0:
                self.stats.speed_max = float(np.max(speed))
                self.stats.speed_avg = float(np.mean(speed))
                self.stats.speed_min = float(np.min(speed))

            throttle = np.array(self.telemetry_data.get("throttle", []))
            if len(throttle) > 0:
                self.stats.throttle_avg = float(np.mean(throttle))
                self.stats.full_throttle_percent = float(np.sum(throttle >= 95) / len(throttle) * 100)

            brake = np.array(self.telemetry_data.get("brake", []))
            if len(brake) > 0:
                self.stats.brake_avg = float(np.mean(brake))
                self.stats.braking_percent = float(np.sum(brake > 10) / len(brake) * 100)

            g_lat = np.array(self.telemetry_data.get("g_lateral", []))
            if len(g_lat) > 0:
                self.stats.g_lateral_max = float(np.max(g_lat))
                self.stats.g_lateral_min = float(np.min(g_lat))

            g_front = np.array(self.telemetry_data.get("g_frontal", []))
            if len(g_front) > 0:
                self.stats.g_frontal_max = float(np.max(g_front))
                self.stats.g_frontal_min = float(np.min(g_front))

        # Estatísticas de sensores (suporta prefixo bmi160_ ou sem prefixo)
        if self.sensor_data:
            # Tenta com prefixo bmi160_ primeiro, depois sem
            accel_x = np.array(self.sensor_data.get("bmi160_accel_x",
                              self.sensor_data.get("accel_x", [])))
            accel_y = np.array(self.sensor_data.get("bmi160_accel_y",
                              self.sensor_data.get("accel_y", [])))
            accel_z = np.array(self.sensor_data.get("bmi160_accel_z",
                              self.sensor_data.get("accel_z", [])))

            if len(accel_x) > 0:
                self.stats.accel_x_max = float(np.max(np.abs(accel_x)))
            if len(accel_y) > 0:
                self.stats.accel_y_max = float(np.max(np.abs(accel_y)))
            if len(accel_z) > 0:
                self.stats.accel_z_max = float(np.max(np.abs(accel_z)))

            gyro_z = np.array(self.sensor_data.get("bmi160_gyro_z",
                             self.sensor_data.get("gyro_z", [])))
            if len(gyro_z) > 0:
                self.stats.gyro_z_max = float(np.max(np.abs(gyro_z)))

            # Power Monitor data
            current_motor = np.array(self.sensor_data.get("current_motor", []))
            if len(current_motor) > 0:
                self.stats.current_motor_max = float(np.max(np.abs(current_motor)))
                self.stats.current_motor_avg = float(np.mean(np.abs(current_motor)))

            power_total = np.array(self.sensor_data.get("power_total", []))
            if len(power_total) > 0:
                self.stats.power_total_max = float(np.max(power_total))
                self.stats.power_total_avg = float(np.mean(power_total))

            voltage_rpi = np.array(self.sensor_data.get("voltage_rpi", []))
            if len(voltage_rpi) > 0:
                self.stats.voltage_rpi_avg = float(np.mean(voltage_rpi))

    def print_stats(self):
        """Imprime estatísticas formatadas"""
        print("\n" + "=" * 60)
        print("                    ESTATÍSTICAS DA SESSÃO")
        print("=" * 60)

        print(f"\n{'Duração:':<25} {self.stats.duration_seconds:.1f} segundos")
        print(f"{'Total de pontos:':<25} {self.stats.total_points}")

        print(f"\n--- Velocidade ---")
        print(f"{'  Máxima:':<25} {self.stats.speed_max:.1f} km/h")
        print(f"{'  Média:':<25} {self.stats.speed_avg:.1f} km/h")
        print(f"{'  Mínima:':<25} {self.stats.speed_min:.1f} km/h")

        print(f"\n--- Pedais ---")
        print(f"{'  Acelerador médio:':<25} {self.stats.throttle_avg:.1f}%")
        print(f"{'  Tempo full throttle:':<25} {self.stats.full_throttle_percent:.1f}%")
        print(f"{'  Freio médio:':<25} {self.stats.brake_avg:.1f}%")
        print(f"{'  Tempo frenando:':<25} {self.stats.braking_percent:.1f}%")

        print(f"\n--- Forças G ---")
        print(f"{'  G Lateral máx:':<25} {self.stats.g_lateral_max:.2f} G")
        print(f"{'  G Lateral mín:':<25} {self.stats.g_lateral_min:.2f} G")
        print(f"{'  G Frontal máx:':<25} {self.stats.g_frontal_max:.2f} G (aceleração)")
        print(f"{'  G Frontal mín:':<25} {self.stats.g_frontal_min:.2f} G (frenagem)")

        if self.sensor_data:
            print(f"\n--- Sensores BMI160 ---")
            print(f"{'  Accel X máx:':<25} {self.stats.accel_x_max:.2f} m/s²")
            print(f"{'  Accel Y máx:':<25} {self.stats.accel_y_max:.2f} m/s²")
            print(f"{'  Accel Z máx:':<25} {self.stats.accel_z_max:.2f} m/s²")
            print(f"{'  Gyro Z máx:':<25} {self.stats.gyro_z_max:.1f} °/s")

            # Power Monitor (se disponível)
            if self.stats.power_total_max > 0 or self.stats.current_motor_max > 0:
                print(f"\n--- Power Monitor ---")
                print(f"{'  Corrente Motor máx:':<25} {self.stats.current_motor_max:.2f} A")
                print(f"{'  Corrente Motor média:':<25} {self.stats.current_motor_avg:.2f} A")
                print(f"{'  Potência Total máx:':<25} {self.stats.power_total_max:.1f} W")
                print(f"{'  Potência Total média:':<25} {self.stats.power_total_avg:.1f} W")
                print(f"{'  Tensão RPi média:':<25} {self.stats.voltage_rpi_avg:.2f} V")

        print("\n" + "=" * 60)

    def plot_telemetry(self, save_path: Optional[str] = None):
        """Gera gráficos de telemetria estilo F1"""
        if not MATPLOTLIB_AVAILABLE:
            print("[ERRO] Matplotlib necessário para gráficos")
            return

        if not self.telemetry_data:
            print("[ERRO] Dados de telemetria não carregados")
            return

        time_data = self.telemetry_data.get("time", [])
        if not time_data:
            print("[ERRO] Sem dados de tempo")
            return

        # Configura estilo escuro
        plt.style.use('dark_background')

        fig = plt.figure(figsize=(14, 10), facecolor=COLORS['background'])
        fig.suptitle('Telemetria F1 Car - Análise de Sessão',
                     color=COLORS['text'], fontsize=14, fontweight='bold')

        gs = GridSpec(4, 2, figure=fig, hspace=0.3, wspace=0.25)

        # 1. Velocidade
        ax1 = fig.add_subplot(gs[0, :])
        ax1.set_facecolor(COLORS['background'])
        speed = self.telemetry_data.get("speed", [])
        ax1.plot(time_data, speed, color=COLORS['speed'], linewidth=1.5)
        ax1.fill_between(time_data, speed, alpha=0.3, color=COLORS['speed'])
        ax1.set_ylabel('Velocidade (km/h)', color=COLORS['text'])
        ax1.set_title('Trace de Velocidade', color=COLORS['text'], fontsize=10)
        ax1.grid(True, color=COLORS['grid'], alpha=0.3)
        ax1.set_xlim(min(time_data), max(time_data))

        # 2. Acelerador e Freio
        ax2 = fig.add_subplot(gs[1, :])
        ax2.set_facecolor(COLORS['background'])
        throttle = self.telemetry_data.get("throttle", [])
        brake = self.telemetry_data.get("brake", [])
        ax2.plot(time_data, throttle, color=COLORS['throttle'], linewidth=1.5, label='Acelerador')
        ax2.plot(time_data, brake, color=COLORS['brake'], linewidth=1.5, label='Freio')
        ax2.set_ylabel('Pedais (%)', color=COLORS['text'])
        ax2.set_title('Acelerador e Freio', color=COLORS['text'], fontsize=10)
        ax2.legend(loc='upper right', facecolor=COLORS['background'])
        ax2.grid(True, color=COLORS['grid'], alpha=0.3)
        ax2.set_ylim(0, 105)
        ax2.set_xlim(min(time_data), max(time_data))

        # 3. Forças G
        ax3 = fig.add_subplot(gs[2, :])
        ax3.set_facecolor(COLORS['background'])
        g_lat = self.telemetry_data.get("g_lateral", [])
        g_front = self.telemetry_data.get("g_frontal", [])
        ax3.plot(time_data, g_lat, color=COLORS['g_lateral'], linewidth=1.5, label='G Lateral')
        ax3.plot(time_data, g_front, color=COLORS['g_frontal'], linewidth=1.5, label='G Frontal')
        ax3.axhline(y=0, color=COLORS['grid'], linestyle='--', alpha=0.5)
        ax3.set_ylabel('Força G', color=COLORS['text'])
        ax3.set_xlabel('Tempo (s)', color=COLORS['text'])
        ax3.set_title('Forças G', color=COLORS['text'], fontsize=10)
        ax3.legend(loc='upper right', facecolor=COLORS['background'])
        ax3.grid(True, color=COLORS['grid'], alpha=0.3)
        ax3.set_xlim(min(time_data), max(time_data))

        # 4. Distribuição de velocidade (histograma)
        ax4 = fig.add_subplot(gs[3, 0])
        ax4.set_facecolor(COLORS['background'])
        if NUMPY_AVAILABLE and speed:
            ax4.hist(speed, bins=30, color=COLORS['speed'], alpha=0.7, edgecolor='white')
        ax4.set_xlabel('Velocidade (km/h)', color=COLORS['text'])
        ax4.set_ylabel('Frequência', color=COLORS['text'])
        ax4.set_title('Distribuição de Velocidade', color=COLORS['text'], fontsize=10)
        ax4.grid(True, color=COLORS['grid'], alpha=0.3)

        # 5. G-G Diagram (scatter)
        ax5 = fig.add_subplot(gs[3, 1])
        ax5.set_facecolor(COLORS['background'])
        if g_lat and g_front:
            scatter = ax5.scatter(g_lat, g_front, c=time_data, cmap='plasma',
                                 alpha=0.6, s=10, edgecolors='none')
            plt.colorbar(scatter, ax=ax5, label='Tempo (s)')
        ax5.axhline(y=0, color=COLORS['grid'], linestyle='--', alpha=0.5)
        ax5.axvline(x=0, color=COLORS['grid'], linestyle='--', alpha=0.5)
        ax5.set_xlabel('G Lateral', color=COLORS['text'])
        ax5.set_ylabel('G Frontal', color=COLORS['text'])
        ax5.set_title('Diagrama G-G', color=COLORS['text'], fontsize=10)
        ax5.grid(True, color=COLORS['grid'], alpha=0.3)
        ax5.set_aspect('equal', adjustable='box')

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, facecolor=COLORS['background'],
                       bbox_inches='tight')
            print(f"[OK] Gráfico salvo: {save_path}")
        else:
            plt.show()

    def plot_sensors(self, save_path: Optional[str] = None):
        """Gera gráficos de dados brutos dos sensores"""
        if not MATPLOTLIB_AVAILABLE:
            print("[ERRO] Matplotlib necessário para gráficos")
            return

        if not self.sensor_data:
            print("[ERRO] Dados de sensores não carregados")
            return

        timestamps = self.sensor_data.get("timestamp", [])
        if not timestamps:
            print("[ERRO] Sem timestamps nos dados")
            return

        # Converte para tempo relativo
        if NUMPY_AVAILABLE:
            time_data = np.array(timestamps) - timestamps[0]
        else:
            time_data = [t - timestamps[0] for t in timestamps]

        plt.style.use('dark_background')

        fig, axes = plt.subplots(3, 2, figsize=(14, 10), facecolor=COLORS['background'])
        fig.suptitle('Dados Brutos BMI160 - Análise de Sessão',
                     color=COLORS['text'], fontsize=14, fontweight='bold')

        # Acelerômetro X, Y, Z (suporta prefixo bmi160_)
        accel_x = self.sensor_data.get("bmi160_accel_x", self.sensor_data.get("accel_x", []))
        accel_y = self.sensor_data.get("bmi160_accel_y", self.sensor_data.get("accel_y", []))
        accel_z = self.sensor_data.get("bmi160_accel_z", self.sensor_data.get("accel_z", []))

        ax = axes[0, 0]
        ax.set_facecolor(COLORS['background'])
        if accel_x:
            ax.plot(time_data, accel_x, color=COLORS['accel_x'], linewidth=0.8, label='X')
        if accel_y:
            ax.plot(time_data, accel_y, color=COLORS['accel_y'], linewidth=0.8, label='Y')
        if accel_z:
            ax.plot(time_data, accel_z, color=COLORS['accel_z'], linewidth=0.8, label='Z')
        ax.set_ylabel('Aceleração (m/s²)', color=COLORS['text'])
        ax.set_title('Acelerômetro', color=COLORS['text'])
        ax.legend(loc='upper right', facecolor=COLORS['background'])
        ax.grid(True, color=COLORS['grid'], alpha=0.3)

        # Giroscópio X, Y, Z (suporta prefixo bmi160_)
        gyro_x = self.sensor_data.get("bmi160_gyro_x", self.sensor_data.get("gyro_x", []))
        gyro_y = self.sensor_data.get("bmi160_gyro_y", self.sensor_data.get("gyro_y", []))
        gyro_z = self.sensor_data.get("bmi160_gyro_z", self.sensor_data.get("gyro_z", []))

        ax = axes[0, 1]
        ax.set_facecolor(COLORS['background'])
        if gyro_x:
            ax.plot(time_data, gyro_x, color=COLORS['gyro_x'], linewidth=0.8, label='X')
        if gyro_y:
            ax.plot(time_data, gyro_y, color=COLORS['gyro_y'], linewidth=0.8, label='Y')
        if gyro_z:
            ax.plot(time_data, gyro_z, color=COLORS['gyro_z'], linewidth=0.8, label='Z')
        ax.set_ylabel('Velocidade Angular (°/s)', color=COLORS['text'])
        ax.set_title('Giroscópio', color=COLORS['text'])
        ax.legend(loc='upper right', facecolor=COLORS['background'])
        ax.grid(True, color=COLORS['grid'], alpha=0.3)

        # G-Forces calculadas
        g_lat = self.sensor_data.get("g_force_lateral", [])
        g_front = self.sensor_data.get("g_force_frontal", [])

        ax = axes[1, 0]
        ax.set_facecolor(COLORS['background'])
        if g_lat:
            ax.plot(time_data, g_lat, color=COLORS['g_lateral'], linewidth=0.8)
        ax.axhline(y=0, color=COLORS['grid'], linestyle='--', alpha=0.5)
        ax.set_ylabel('G Lateral', color=COLORS['text'])
        ax.set_title('Força G Lateral (curvas)', color=COLORS['text'])
        ax.grid(True, color=COLORS['grid'], alpha=0.3)

        ax = axes[1, 1]
        ax.set_facecolor(COLORS['background'])
        if g_front:
            ax.plot(time_data, g_front, color=COLORS['g_frontal'], linewidth=0.8)
        ax.axhline(y=0, color=COLORS['grid'], linestyle='--', alpha=0.5)
        ax.set_ylabel('G Frontal', color=COLORS['text'])
        ax.set_title('Força G Frontal (acel/frenagem)', color=COLORS['text'])
        ax.grid(True, color=COLORS['grid'], alpha=0.3)

        # Power Monitor - Correntes (se disponível)
        current_motor = self.sensor_data.get("current_motor", [])
        current_servos = self.sensor_data.get("current_servos", [])
        current_rpi = self.sensor_data.get("current_rpi", [])

        ax = axes[2, 0]
        ax.set_facecolor(COLORS['background'])
        if current_motor or current_servos or current_rpi:
            if current_motor:
                ax.plot(time_data[:len(current_motor)], current_motor,
                       color='#FF5555', linewidth=0.8, label='Motor')
            if current_servos:
                ax.plot(time_data[:len(current_servos)], current_servos,
                       color='#55FF55', linewidth=0.8, label='Servos')
            if current_rpi:
                ax.plot(time_data[:len(current_rpi)], current_rpi,
                       color='#5555FF', linewidth=0.8, label='RPi')
            ax.set_ylabel('Corrente (A)', color=COLORS['text'])
            ax.legend(loc='upper right', facecolor=COLORS['background'])
            ax.set_title('Consumo de Corrente', color=COLORS['text'])
        else:
            # Fallback: Temperatura (se disponível)
            temp = self.sensor_data.get("temperature", [])
            if temp:
                ax.plot(time_data, temp, color='#FF6B6B', linewidth=1)
                ax.set_ylabel('Temperatura (°C)', color=COLORS['text'])
            ax.set_title('Temperatura do Sensor', color=COLORS['text'])
        ax.set_xlabel('Tempo (s)', color=COLORS['text'])
        ax.grid(True, color=COLORS['grid'], alpha=0.3)

        # FFT do Gyro Z (análise de frequência)
        ax = axes[2, 1]
        ax.set_facecolor(COLORS['background'])
        if NUMPY_AVAILABLE and gyro_z and len(gyro_z) > 10:
            gyro_z_arr = np.array(gyro_z)
            # Calcula FFT
            n = len(gyro_z_arr)
            dt = (time_data[-1] - time_data[0]) / n if n > 1 else 0.01
            freq = np.fft.rfftfreq(n, dt)
            fft_vals = np.abs(np.fft.rfft(gyro_z_arr - np.mean(gyro_z_arr)))

            ax.plot(freq[:len(freq)//2], fft_vals[:len(freq)//2],
                   color=COLORS['gyro_z'], linewidth=0.8)
            ax.set_xlabel('Frequência (Hz)', color=COLORS['text'])
            ax.set_ylabel('Amplitude', color=COLORS['text'])
        ax.set_title('FFT Gyro Z (Análise de Vibração)', color=COLORS['text'])
        ax.grid(True, color=COLORS['grid'], alpha=0.3)

        plt.tight_layout()

        if save_path:
            plt.savefig(save_path, dpi=150, facecolor=COLORS['background'],
                       bbox_inches='tight')
            print(f"[OK] Gráfico salvo: {save_path}")
        else:
            plt.show()

    def analyze_logs(self) -> Dict:
        """Analisa conteúdo dos logs"""
        if not self.log_content:
            return {}

        analysis = {
            "total_lines": self.log_content.count('\n'),
            "errors": 0,
            "warnings": 0,
            "connections": 0,
            "disconnections": 0,
        }

        # Conta ocorrências
        analysis["errors"] = len(re.findall(r'\[ERROR\]|\[ERRO\]', self.log_content, re.IGNORECASE))
        analysis["warnings"] = len(re.findall(r'\[WARN\]|\[WARNING\]', self.log_content, re.IGNORECASE))
        analysis["connections"] = len(re.findall(r'CONNECT|conectado', self.log_content, re.IGNORECASE))
        analysis["disconnections"] = len(re.findall(r'DISCONNECT|desconectado|perdida', self.log_content, re.IGNORECASE))

        return analysis

    def export_html_report(self, filepath: str):
        """Exporta relatório em HTML"""
        self.calculate_stats()
        log_analysis = self.analyze_logs()

        html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Relatório de Sessão - F1 Car</title>
    <style>
        body {{
            font-family: 'Segoe UI', Arial, sans-serif;
            background: #1a1a1a;
            color: #fff;
            padding: 20px;
            max-width: 1200px;
            margin: 0 auto;
        }}
        h1 {{ color: #00D2BE; border-bottom: 2px solid #00D2BE; padding-bottom: 10px; }}
        h2 {{ color: #FF8700; margin-top: 30px; }}
        .stats-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin: 20px 0;
        }}
        .stat-card {{
            background: #2b2b2b;
            border-radius: 8px;
            padding: 15px;
            border-left: 4px solid #00D2BE;
        }}
        .stat-card h3 {{ margin: 0 0 10px 0; color: #888; font-size: 12px; text-transform: uppercase; }}
        .stat-card .value {{ font-size: 24px; font-weight: bold; color: #00D2BE; }}
        .stat-card .unit {{ font-size: 12px; color: #666; }}
        table {{ width: 100%; border-collapse: collapse; margin: 20px 0; }}
        th, td {{ padding: 10px; text-align: left; border-bottom: 1px solid #333; }}
        th {{ background: #2b2b2b; color: #00D2BE; }}
        .warning {{ color: #FF8700; }}
        .error {{ color: #FF4444; }}
        .success {{ color: #00FF00; }}
    </style>
</head>
<body>
    <h1>Relatório de Análise - F1 Car TCC</h1>
    <p>Gerado em: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>

    <h2>Resumo da Sessão</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <h3>Duração</h3>
            <div class="value">{self.stats.duration_seconds:.1f}</div>
            <div class="unit">segundos</div>
        </div>
        <div class="stat-card">
            <h3>Pontos de Dados</h3>
            <div class="value">{self.stats.total_points:,}</div>
            <div class="unit">amostras</div>
        </div>
        <div class="stat-card">
            <h3>Velocidade Máxima</h3>
            <div class="value">{self.stats.speed_max:.1f}</div>
            <div class="unit">km/h</div>
        </div>
        <div class="stat-card">
            <h3>Velocidade Média</h3>
            <div class="value">{self.stats.speed_avg:.1f}</div>
            <div class="unit">km/h</div>
        </div>
    </div>

    <h2>Análise de Pedais</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <h3>Acelerador Médio</h3>
            <div class="value">{self.stats.throttle_avg:.1f}%</div>
        </div>
        <div class="stat-card">
            <h3>Tempo Full Throttle</h3>
            <div class="value">{self.stats.full_throttle_percent:.1f}%</div>
        </div>
        <div class="stat-card">
            <h3>Freio Médio</h3>
            <div class="value">{self.stats.brake_avg:.1f}%</div>
        </div>
        <div class="stat-card">
            <h3>Tempo Frenando</h3>
            <div class="value">{self.stats.braking_percent:.1f}%</div>
        </div>
    </div>

    <h2>Forças G</h2>
    <table>
        <tr>
            <th>Métrica</th>
            <th>Valor</th>
            <th>Descrição</th>
        </tr>
        <tr>
            <td>G Lateral Máximo</td>
            <td class="success">{self.stats.g_lateral_max:.2f} G</td>
            <td>Curva para direita</td>
        </tr>
        <tr>
            <td>G Lateral Mínimo</td>
            <td class="warning">{self.stats.g_lateral_min:.2f} G</td>
            <td>Curva para esquerda</td>
        </tr>
        <tr>
            <td>G Frontal Máximo</td>
            <td class="success">{self.stats.g_frontal_max:.2f} G</td>
            <td>Aceleração</td>
        </tr>
        <tr>
            <td>G Frontal Mínimo</td>
            <td class="error">{self.stats.g_frontal_min:.2f} G</td>
            <td>Frenagem</td>
        </tr>
    </table>

    <h2>Análise de Logs</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <h3>Total de Linhas</h3>
            <div class="value">{log_analysis.get('total_lines', 0):,}</div>
        </div>
        <div class="stat-card">
            <h3>Erros</h3>
            <div class="value error">{log_analysis.get('errors', 0)}</div>
        </div>
        <div class="stat-card">
            <h3>Avisos</h3>
            <div class="value warning">{log_analysis.get('warnings', 0)}</div>
        </div>
        <div class="stat-card">
            <h3>Conexões</h3>
            <div class="value success">{log_analysis.get('connections', 0)}</div>
        </div>
    </div>

    <h2>Dados Brutos do Sensor BMI160</h2>
    <table>
        <tr>
            <th>Eixo</th>
            <th>Aceleração Máx (m/s²)</th>
            <th>Rotação Máx (°/s)</th>
        </tr>
        <tr>
            <td>X</td>
            <td>{self.stats.accel_x_max:.2f}</td>
            <td>-</td>
        </tr>
        <tr>
            <td>Y</td>
            <td>{self.stats.accel_y_max:.2f}</td>
            <td>-</td>
        </tr>
        <tr>
            <td>Z</td>
            <td>{self.stats.accel_z_max:.2f}</td>
            <td>{self.stats.gyro_z_max:.1f}</td>
        </tr>
    </table>

    <h2>Monitoramento de Energia</h2>
    <div class="stats-grid">
        <div class="stat-card">
            <h3>Corrente Motor Máx</h3>
            <div class="value">{self.stats.current_motor_max:.2f}</div>
            <div class="unit">A</div>
        </div>
        <div class="stat-card">
            <h3>Corrente Motor Média</h3>
            <div class="value">{self.stats.current_motor_avg:.2f}</div>
            <div class="unit">A</div>
        </div>
        <div class="stat-card">
            <h3>Potência Total Máx</h3>
            <div class="value">{self.stats.power_total_max:.1f}</div>
            <div class="unit">W</div>
        </div>
        <div class="stat-card">
            <h3>Potência Total Média</h3>
            <div class="value">{self.stats.power_total_avg:.1f}</div>
            <div class="unit">W</div>
        </div>
    </div>

    <footer style="margin-top: 40px; padding-top: 20px; border-top: 1px solid #333; color: #666;">
        <p>F1 Car TCC Project - Análise gerada automaticamente</p>
    </footer>
</body>
</html>"""

        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)

        print(f"[OK] Relatório HTML exportado: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Analisador de Sessões F1 Car",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  python analyze_session.py                          # Combina TODOS os arquivos (padrão)
  python analyze_session.py --latest                 # Analisa apenas os mais recentes
  python analyze_session.py --dir exports/auto      # Diretório específico
  python analyze_session.py --timestamp 20241217_143000  # Timestamp específico
  python analyze_session.py --export report.html    # Exporta relatório HTML
  python analyze_session.py --save-plots            # Salva gráficos como PNG
        """
    )

    parser.add_argument("--dir", "-d", default="exports/auto",
                       help="Diretório com arquivos de dados")
    parser.add_argument("--timestamp", "-t",
                       help="Timestamp específico (YYYYMMDD_HHMMSS)")
    parser.add_argument("--latest", "-l", action="store_true",
                       help="Analisa apenas os arquivos mais recentes (não combina)")
    parser.add_argument("--export", "-e",
                       help="Exporta relatório HTML")
    parser.add_argument("--save-plots", "-s", action="store_true",
                       help="Salva gráficos como PNG")
    parser.add_argument("--no-plots", action="store_true",
                       help="Não exibe gráficos")

    args = parser.parse_args()

    # Ajusta caminho relativo
    if not os.path.isabs(args.dir):
        # Procura a partir do diretório do projeto
        project_root = Path(__file__).parent.parent
        args.dir = project_root / args.dir

    print("=" * 60)
    print("        F1 CAR - ANALISADOR DE SESSÕES")
    print("=" * 60)
    print(f"Diretório: {args.dir}")

    analyzer = SessionAnalyzer(str(args.dir))

    # Modo de carregamento
    if args.timestamp:
        # Timestamp específico
        print(f"Modo: Timestamp específico ({args.timestamp})")
        telemetry_file, sensor_file, log_file = analyzer.find_matching_files(args.timestamp)

        if not any([telemetry_file, sensor_file, log_file]):
            print("[ERRO] Nenhum arquivo encontrado!")
            sys.exit(1)

        print("\n--- Carregando Dados ---")
        if telemetry_file:
            analyzer.load_telemetry(telemetry_file)
        if sensor_file:
            analyzer.load_sensors(sensor_file)
        if log_file:
            analyzer.load_logs(log_file)

    elif args.latest:
        # Apenas mais recentes
        print("Modo: Arquivos mais recentes")
        telemetry_file, sensor_file, log_file = analyzer.find_latest_files()

        if not any([telemetry_file, sensor_file, log_file]):
            print("[ERRO] Nenhum arquivo encontrado!")
            sys.exit(1)

        print("\n--- Carregando Dados ---")
        if telemetry_file:
            analyzer.load_telemetry(telemetry_file)
        if sensor_file:
            analyzer.load_sensors(sensor_file)
        if log_file:
            analyzer.load_logs(log_file)

    else:
        # Padrão: combina TODOS os arquivos
        print("Modo: Combinando TODOS os arquivos")
        telemetry_count, sensor_count, log_count = analyzer.load_all_files()

        if telemetry_count == 0 and sensor_count == 0 and log_count == 0:
            print("[ERRO] Nenhum arquivo encontrado!")
            print(f"Verifique se existem arquivos em: {args.dir}")
            sys.exit(1)

    # Calcula e exibe estatísticas
    analyzer.calculate_stats()
    analyzer.print_stats()

    # Análise de logs
    if analyzer.log_content:
        log_analysis = analyzer.analyze_logs()
        print("\n--- Análise de Logs ---")
        print(f"{'Erros:':<20} {log_analysis.get('errors', 0)}")
        print(f"{'Avisos:':<20} {log_analysis.get('warnings', 0)}")
        print(f"{'Conexões:':<20} {log_analysis.get('connections', 0)}")
        print(f"{'Desconexões:':<20} {log_analysis.get('disconnections', 0)}")

    # Exporta HTML se solicitado
    if args.export:
        analyzer.export_html_report(args.export)

    # Gera gráficos
    if not args.no_plots and MATPLOTLIB_AVAILABLE:
        print("\n--- Gerando Gráficos ---")

        if args.save_plots:
            output_dir = Path(args.dir) / "analysis"
            output_dir.mkdir(exist_ok=True)

            timestamp = args.timestamp or datetime.now().strftime("%Y%m%d_%H%M%S")

            if analyzer.telemetry_data:
                analyzer.plot_telemetry(str(output_dir / f"telemetry_{timestamp}.png"))
            if analyzer.sensor_data:
                analyzer.plot_sensors(str(output_dir / f"sensors_{timestamp}.png"))
        else:
            if analyzer.telemetry_data:
                analyzer.plot_telemetry()
            if analyzer.sensor_data:
                analyzer.plot_sensors()

    print("\n[OK] Análise concluída!")


if __name__ == "__main__":
    main()
