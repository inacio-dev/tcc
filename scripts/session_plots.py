#!/usr/bin/env python3
"""
session_plots.py - Geração completa de gráficos de uma sessão F1 Car

Lê todos os sensors_*.pkl de um diretório e gera um conjunto de gráficos
PNG + um arquivo analise.md com observações automáticas.

Uso:
    python3 scripts/session_plots.py sessoes/01_indoor_20260413
"""

import glob
import pickle
import sys
from datetime import datetime
from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import numpy as np

# ── estilo ─────────────────────────────────────────────────────────────────────

plt.rcParams.update({
    "figure.facecolor":  "#1E1E1E",
    "axes.facecolor":    "#2A2A2A",
    "savefig.facecolor": "#1E1E1E",
    "axes.edgecolor":    "#555",
    "axes.labelcolor":   "white",
    "axes.titlecolor":   "white",
    "xtick.color":       "white",
    "ytick.color":       "white",
    "grid.color":        "#3C3C3C",
    "grid.linewidth":    0.5,
    "text.color":        "white",
    "font.size":         10,
})

COLORS = {
    "battery":   "#00D2BE",
    "motor":     "#FF8700",
    "power":     "#FF5555",
    "temp_body": "#55FF55",
    "temp_mot":  "#FFAA00",
    "temp_rpi":  "#5555FF",
    "rpm":       "#00FF00",
    "gear":      "#FFD700",
    "pwm":       "#FF00FF",
    "accel_x":   "#FF5555",
    "accel_y":   "#55FF55",
    "accel_z":   "#5555FF",
    "gyro_x":    "#FFAA00",
    "gyro_y":    "#00FFAA",
    "gyro_z":    "#AA00FF",
    "steering":  "#00D2BE",
    "brake":     "#FF0000",
    "latency":   "#AA00FF",
    "tx":        "#00D2BE",
    "cpu":       "#FF8700",
    "mem":       "#5555FF",
}

# ── carregamento ───────────────────────────────────────────────────────────────

def load_sensors(data_dir: Path) -> dict[str, np.ndarray]:
    files = sorted(glob.glob(str(data_dir / "sensors_*.pkl")))
    if not files:
        print(f"[ERRO] Nenhum sensors_*.pkl em {data_dir}")
        sys.exit(1)

    raw: dict[str, list] = {}
    for f in files:
        with open(f, "rb") as fh:
            d = pickle.load(fh)
        for k, v in d.items():
            vals = v if isinstance(v, list) else list(v)
            raw.setdefault(k, []).extend(vals)

    out: dict[str, np.ndarray] = {}
    for k, v in raw.items():
        try:
            out[k] = np.array(v, dtype=float)
        except (ValueError, TypeError):
            pass
    return out


def load_ff(data_dir: Path) -> dict[str, np.ndarray] | None:
    """Carrega todos os ff_*.pkl e retorna dict concatenado.

    Retorna None se não houver arquivos (sessões antigas).
    Campos string (ff_context, steering_feedback_direction) são mantidos como list.
    """
    files = sorted(glob.glob(str(data_dir / "ff_*.pkl")))
    if not files:
        return None

    raw: dict[str, list] = {}
    for f in files:
        with open(f, "rb") as fh:
            d = pickle.load(fh)
        for k, v in d.items():
            vals = v if isinstance(v, list) else list(v)
            raw.setdefault(k, []).extend(vals)

    out: dict = {}
    for k, v in raw.items():
        # Campos string ficam como list
        if any(isinstance(x, str) for x in v if x is not None):
            out[k] = list(v)
            continue
        try:
            out[k] = np.array([x if x is not None else np.nan for x in v], dtype=float)
        except (ValueError, TypeError):
            out[k] = list(v)
    return out


# ── helpers ────────────────────────────────────────────────────────────────────

def setup_ax(ax, title: str, ylabel: str):
    ax.set_title(title, fontweight="bold")
    ax.set_ylabel(ylabel)
    ax.grid(True, alpha=0.4)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.xaxis.set_major_locator(mdates.MinuteLocator(interval=3))
    for lbl in ax.get_xticklabels():
        lbl.set_rotation(30)
        lbl.set_horizontalalignment("right")


def plot_series(ax, times, key_data_pairs, xlabel=None):
    """key_data_pairs: list of (label, data_array, color)"""
    for label, data, color in key_data_pairs:
        if data is not None and len(data) == len(times):
            ax.plot(times, data, color=color, linewidth=0.8, alpha=0.9, label=label)
    if len(key_data_pairs) > 1:
        ax.legend(loc="upper right", framealpha=0.3, fontsize=8)
    if xlabel:
        ax.set_xlabel(xlabel)


def annotate_phases(ax, times, key: str, data: dict):
    """Marca transições importantes (fase parado/andando) verticalmente."""
    rpm = data.get("rpm_percent")
    if rpm is None:
        return
    moving = rpm > 10
    transitions = np.where(np.diff(moving.astype(int)) != 0)[0]
    for i, idx in enumerate(transitions):
        if i > 8:
            break
        ax.axvline(times[idx], color="#888", linestyle="--", alpha=0.4, linewidth=0.6)


# ── gráficos ───────────────────────────────────────────────────────────────────

def plot_bateria(data, times, out: Path):
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.suptitle("Bateria — Tensão e Percentual", fontweight="bold", fontsize=13)

    vb = data.get("voltage_battery")
    bp = data.get("battery_percentage")

    ax1.plot(times, vb, color=COLORS["battery"], linewidth=1.0)
    ax1.axhline(13.6, color="#00FF00", linestyle=":", linewidth=0.8, label="100% (13.6V)")
    ax1.axhline(11.0, color="#FF5555", linestyle=":", linewidth=0.8, label="0% (11.0V)")
    setup_ax(ax1, "Tensão da Bateria", "Tensão (V)")
    ax1.legend(loc="lower left", framealpha=0.3, fontsize=9)
    ax1.set_ylim(min(10.8, vb.min() - 0.1), max(13.7, vb.max() + 0.1))

    ax2.plot(times, bp, color=COLORS["battery"], linewidth=1.0)
    setup_ax(ax2, "Battery Percentage (%)", "Percentual")
    ax2.set_ylim(-5, 105)

    plt.tight_layout()
    plt.savefig(out / "01_bateria.png", dpi=130)
    plt.close()


def plot_potencia(data, times, out: Path):
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    fig.suptitle("Consumo Energético", fontweight="bold", fontsize=13)

    ax = axes[0]
    ax.plot(times, data.get("current_motor"), color=COLORS["motor"],    linewidth=0.8, label="Motor")
    ax.plot(times, data.get("current_servos"), color=COLORS["temp_body"], linewidth=0.8, label="Servos")
    ax.plot(times, data.get("current_rpi"),    color=COLORS["temp_rpi"],  linewidth=0.8, label="RPi (INA219)")
    setup_ax(ax, "Corrente por Subsistema", "Corrente (A)")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)

    ax = axes[1]
    ax.plot(times, data.get("power_motor"),  color=COLORS["motor"],   linewidth=0.8, label="Motor")
    ax.plot(times, data.get("power_servos"), color=COLORS["temp_body"], linewidth=0.8, label="Servos")
    ax.plot(times, data.get("power_rpi"),    color=COLORS["temp_rpi"],  linewidth=0.8, label="RPi")
    ax.plot(times, data.get("power_total"),  color=COLORS["power"],     linewidth=1.2, label="Total")
    setup_ax(ax, "Potência por Subsistema", "Potência (W)")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)

    ax = axes[2]
    pt = data.get("power_total")
    vb = data.get("voltage_battery")
    if pt is not None and vb is not None:
        energy_wh = np.cumsum(pt) / (100 * 3600)  # amostras ~100Hz → Wh
        ax.plot(times, energy_wh, color=COLORS["power"], linewidth=1.0)
        setup_ax(ax, "Energia Acumulada (∫ P dt)", "Energia (Wh)")

    plt.tight_layout()
    plt.savefig(out / "02_potencia.png", dpi=130)
    plt.close()


def plot_temperaturas(data, times, out: Path):
    fig, ax = plt.subplots(figsize=(14, 7))
    fig.suptitle("Temperaturas do Sistema", fontweight="bold", fontsize=13)

    tc  = data.get("temperature_c")         # DS18B20
    trc = data.get("rpi_cpu_temp_c")        # CPU RPi

    if tc  is not None: ax.plot(times, tc,  color=COLORS["temp_body"], linewidth=1.0, label="DS18B20 (carcaça)")
    if trc is not None: ax.plot(times, trc, color=COLORS["temp_rpi"],  linewidth=1.0, label="CPU RPi")

    setup_ax(ax, "", "Temperatura (°C)")
    ax.legend(loc="upper left", framealpha=0.3)
    plt.tight_layout()
    plt.savefig(out / "03_temperaturas.png", dpi=130)
    plt.close()


def plot_motor(data, times, out: Path):
    fig, axes = plt.subplots(3, 1, figsize=(14, 10), sharex=True)
    fig.suptitle("Motor e Transmissão", fontweight="bold", fontsize=13)

    ax = axes[0]
    ax.plot(times, data.get("rpm_percent"), color=COLORS["rpm"], linewidth=0.8)
    setup_ax(ax, "RPM (%)", "RPM %")
    ax.set_ylim(-5, 105)

    ax = axes[1]
    ax.plot(times, data.get("current_pwm"), color=COLORS["pwm"], linewidth=0.8, label="Atual")
    ax.plot(times, data.get("target_pwm"),  color="#FF00AA", linewidth=0.6, alpha=0.6, label="Target")
    setup_ax(ax, "PWM", "PWM (0-255)")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)

    ax = axes[2]
    ax.step(times, data.get("current_gear"), color=COLORS["gear"], linewidth=1.0, where="post")
    setup_ax(ax, "Marcha Atual", "Marcha")
    ax.set_ylim(0.5, 5.5)
    ax.set_yticks([1, 2, 3, 4, 5])

    plt.tight_layout()
    plt.savefig(out / "04_motor.png", dpi=130)
    plt.close()


def plot_imu(data, times, out: Path):
    fig, axes = plt.subplots(2, 1, figsize=(14, 9), sharex=True)
    fig.suptitle("BMI160 — Aceleração e Giroscópio", fontweight="bold", fontsize=13)

    ax = axes[0]
    ax.plot(times, data.get("bmi160_accel_x"), color=COLORS["accel_x"], linewidth=0.5, alpha=0.8, label="X")
    ax.plot(times, data.get("bmi160_accel_y"), color=COLORS["accel_y"], linewidth=0.5, alpha=0.8, label="Y")
    ax.plot(times, data.get("bmi160_accel_z"), color=COLORS["accel_z"], linewidth=0.5, alpha=0.8, label="Z")
    setup_ax(ax, "Aceleração (inclui gravidade)", "Aceleração (g ≈ m/s²)")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)

    ax = axes[1]
    ax.plot(times, data.get("bmi160_gyro_x"), color=COLORS["gyro_x"], linewidth=0.5, alpha=0.8, label="X")
    ax.plot(times, data.get("bmi160_gyro_y"), color=COLORS["gyro_y"], linewidth=0.5, alpha=0.8, label="Y")
    ax.plot(times, data.get("bmi160_gyro_z"), color=COLORS["gyro_z"], linewidth=0.5, alpha=0.8, label="Z")
    setup_ax(ax, "Velocidade Angular", "Gyro (°/s)")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)

    plt.tight_layout()
    plt.savefig(out / "05_imu.png", dpi=130)
    plt.close()


def plot_direcao_freio(data, times, out: Path):
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.suptitle("Direção e Freio", fontweight="bold", fontsize=13)

    ax = axes[0]
    ax.plot(times, data.get("steering_input"), color=COLORS["steering"], linewidth=0.6, alpha=0.9)
    ax.axhline(0, color="#666", linestyle="-", linewidth=0.4)
    setup_ax(ax, "Input de Direção", "Ângulo (°)")
    ax.set_ylim(-95, 95)

    ax = axes[1]
    ax.plot(times, data.get("total_brake_input"), color=COLORS["brake"], linewidth=0.6, alpha=0.9)
    setup_ax(ax, "Input de Freio", "Freio (%)")
    ax.set_ylim(-5, 105)

    plt.tight_layout()
    plt.savefig(out / "06_direcao_freio.png", dpi=130)
    plt.close()


def plot_rede(data, times, out: Path):
    fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
    fig.suptitle("Rede UDP", fontweight="bold", fontsize=13)

    ax = axes[0]
    lat = data.get("net_latency_ms")
    if lat is not None:
        valid_mask = lat > 0
        ax.scatter(np.array(times)[valid_mask], lat[valid_mask],
                   c=COLORS["latency"], s=1.0, alpha=0.4)
    setup_ax(ax, "Latência UDP (pontos ≥ 0ms)", "ms")
    ax.set_ylim(0, 250)

    ax = axes[1]
    ax.plot(times, data.get("rpi_net_tx_rate_kbps"), color=COLORS["tx"], linewidth=0.8, label="TX (vídeo+sensores)")
    ax.plot(times, data.get("rpi_net_rx_rate_kbps"), color=COLORS["brake"], linewidth=0.8, label="RX (comandos)")
    setup_ax(ax, "Taxa de Rede (kbps)", "kbps")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)

    plt.tight_layout()
    plt.savefig(out / "07_rede.png", dpi=130)
    plt.close()


def plot_rpi(data, times, out: Path):
    fig, axes = plt.subplots(2, 2, figsize=(14, 8), sharex=True)
    fig.suptitle("Raspberry Pi — Sistema", fontweight="bold", fontsize=13)

    ax = axes[0, 0]
    ax.plot(times, data.get("rpi_cpu_usage_percent"), color=COLORS["cpu"], linewidth=0.8)
    setup_ax(ax, "CPU (%)", "%")
    ax.set_ylim(0, 100)

    ax = axes[0, 1]
    ax.plot(times, data.get("rpi_cpu_freq_mhz"), color=COLORS["motor"], linewidth=0.8)
    setup_ax(ax, "CPU Freq (MHz)", "MHz")

    ax = axes[1, 0]
    ax.plot(times, data.get("rpi_mem_used_mb"), color=COLORS["mem"], linewidth=0.8)
    setup_ax(ax, "RAM Usada (MB)", "MB")

    ax = axes[1, 1]
    ax.plot(times, data.get("rpi_load_1min"),  color=COLORS["accel_x"], linewidth=0.8, label="1 min")
    ax.plot(times, data.get("rpi_load_5min"),  color=COLORS["accel_y"], linewidth=0.8, label="5 min")
    ax.plot(times, data.get("rpi_load_15min"), color=COLORS["accel_z"], linewidth=0.8, label="15 min")
    setup_ax(ax, "Load Average", "Load")
    ax.legend(loc="upper left", framealpha=0.3, fontsize=8)

    plt.tight_layout()
    plt.savefig(out / "08_rpi.png", dpi=130)
    plt.close()


def plot_timings(data, times, out: Path):
    """Gráfico dedicado para todos os timings do pipeline."""
    # NÃO usar sharex=True — o histograma de latência (axes[2,1]) tem eixo x em ms,
    # não em datetime. Compartilhar x com subplots de série temporal causa o
    # matplotlib a tentar gerar milhões de ticks no histograma (loop infinito).
    fig, axes = plt.subplots(3, 2, figsize=(15, 11))
    fig.suptitle("Timings do Pipeline — RPi e Cliente", fontweight="bold", fontsize=13)

    ts = data["timestamp"]

    # RPi timings (alta amostragem)
    ax = axes[0, 0]
    ax.plot(times, data.get("timing_bmi160_read_ms"), color=COLORS["accel_x"], linewidth=0.4, alpha=0.7, label="BMI160 read")
    ax.plot(times, data.get("timing_power_ms"),       color=COLORS["motor"],   linewidth=0.4, alpha=0.7, label="Power read")
    setup_ax(ax, "RPi — leituras de sensor", "ms")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)
    ax.set_ylim(0, 10)
    ax.axhline(10, color="#FF5555", linestyle=":", linewidth=0.6, alpha=0.5, label="budget 100Hz")

    ax = axes[0, 1]
    ax.plot(times, data.get("timing_total_pre_send_ms"), color=COLORS["power"], linewidth=0.4, alpha=0.8, label="total pre-send")
    ax.plot(times, data.get("timing_state_cmd_ms"),      color=COLORS["temp_body"], linewidth=0.4, alpha=0.7, label="state cmd")
    ax.plot(times, data.get("timing_status_ms"),         color=COLORS["temp_rpi"], linewidth=0.4, alpha=0.7, label="status collect")
    setup_ax(ax, "RPi — caminho crítico", "ms")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)
    ax.set_ylim(0, 5)

    # Cliente timings — só os que têm n=102046
    ax = axes[1, 0]
    ax.plot(times, data.get("client_timing_json_decode_ms"), color=COLORS["temp_mot"], linewidth=0.4, alpha=0.7)
    setup_ax(ax, "Cliente — JSON decode", "ms")
    ax.set_ylim(0, 0.3)

    # Cliente timings — scatter dos esparsos (n não alinha com ts principal)
    # Distribui uniformemente ao longo do eixo temporal da sessão
    from datetime import datetime as _dt
    ax = axes[1, 1]
    sparse_fields = [
        ("client_timing_total_ms",        COLORS["power"],     "total"),
        ("client_timing_calc_ms",         COLORS["motor"],     "calc"),
        ("client_timing_video_decode_ms", COLORS["temp_body"], "video decode"),
    ]
    t_start = ts[0]
    t_end   = ts[-1]
    for key, color, label in sparse_fields:
        arr = data.get(key)
        if arr is None or len(arr) == 0:
            continue
        valid = arr[~np.isnan(arr) & (arr > 0)]
        if len(valid) == 0:
            continue
        # Distribui uniformemente no tempo (os originais não têm timestamp próprio)
        t_synthetic = np.linspace(t_start, t_end, len(valid))
        t_synthetic_dt = [_dt.fromtimestamp(t) for t in t_synthetic]
        ax.scatter(t_synthetic_dt, valid, c=color, s=8, alpha=0.8, label=f"{label} (n={len(valid)})")
    ax.axhline(16.67, color="#FF5555", linestyle=":", linewidth=0.6, alpha=0.5, label="budget 60Hz")
    setup_ax(ax, "Cliente — amostras esparsas", "ms")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=7)
    ax.set_ylim(0, 35)

    # Latência de rede com distribuição
    ax = axes[2, 0]
    lat = data.get("net_latency_ms")
    if lat is not None:
        valid = lat > 0
        ax.scatter(np.array(times)[valid], lat[valid], c=COLORS["latency"], s=0.8, alpha=0.4)
    setup_ax(ax, "Rede UDP — latência (pontos ≥ 0)", "ms")
    ax.set_ylim(0, 250)

    # Histograma de latência
    ax = axes[2, 1]
    if lat is not None:
        valid_lat = lat[lat > 0]
        ax.hist(valid_lat, bins=60, range=(0, 200), color=COLORS["latency"], alpha=0.8, edgecolor="#555", linewidth=0.3)
        p50 = np.percentile(valid_lat, 50)
        p99 = np.percentile(valid_lat, 99)
        ax.axvline(p50, color="#00FF00", linestyle="--", linewidth=1, label=f"p50={p50:.0f}ms")
        ax.axvline(p99, color="#FF5555", linestyle="--", linewidth=1, label=f"p99={p99:.0f}ms")
        ax.legend(loc="upper right", framealpha=0.3, fontsize=8)
    ax.set_title("Distribuição da latência UDP", color="white", fontweight="bold")
    ax.set_xlabel("Latência (ms)")
    ax.set_ylabel("Frequência")
    ax.grid(True, alpha=0.4)

    plt.tight_layout()
    plt.savefig(out / "09_timings.png", dpi=130)
    plt.close()


def plot_force_feedback(ff_data: dict, out: Path):
    """Gráfico dedicado para todos os efeitos calculados de Force Feedback.

    Produz um painel 4×2 cobrindo:
      - Inputs do G923 (steering/throttle/brake)
      - Forças G calculadas (lateral/frontal/vertical)
      - Ângulos integrados (roll/pitch/yaw)
      - FF_CONSTANT (steering_feedback_intensity)
      - FF_RUMBLE (strong/weak)
      - FF_PERIODIC (magnitude + period)
      - FF_INERTIA
      - Jerks detectados (derivadas)
    """
    ts = ff_data.get("timestamp")
    if ts is None or len(ts) == 0:
        print("    (sem dados de FF para plotar)")
        return

    times = [datetime.fromtimestamp(t) for t in ts]

    fig, axes = plt.subplots(4, 2, figsize=(16, 13), sharex=True)
    fig.suptitle("Force Feedback — Efeitos calculados no cliente", fontweight="bold", fontsize=14)

    # 1. Inputs do G923
    ax = axes[0, 0]
    ax.plot(times, ff_data.get("g923_steering"), color=COLORS["steering"], linewidth=0.6, label="Steering (°)")
    ax.set_ylabel("Steering (°)", color=COLORS["steering"])
    ax.set_title("G923 — Input de direção", color="white", fontweight="bold")
    ax.grid(True, alpha=0.4)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.tick_params(axis='y', labelcolor=COLORS["steering"])
    ax2 = ax.twinx()
    ax2.plot(times, ff_data.get("g923_throttle"), color=COLORS["motor"], linewidth=0.5, alpha=0.6, label="Throttle (%)")
    ax2.plot(times, ff_data.get("g923_brake"), color=COLORS["brake"], linewidth=0.5, alpha=0.6, label="Brake (%)")
    ax2.set_ylabel("Throttle/Brake (%)", color="white")
    ax2.tick_params(axis='y', labelcolor="white")
    ax2.set_ylim(-5, 105)
    ax.set_xlabel("")

    # 2. Forças G (BMI160 → g_force_*)
    ax = axes[0, 1]
    ax.plot(times, ff_data.get("g_force_lateral"),  color=COLORS["accel_y"], linewidth=0.6, alpha=0.9, label="Lateral")
    ax.plot(times, ff_data.get("g_force_frontal"),  color=COLORS["accel_x"], linewidth=0.6, alpha=0.9, label="Frontal")
    ax.plot(times, ff_data.get("g_force_vertical"), color=COLORS["accel_z"], linewidth=0.6, alpha=0.9, label="Vertical")
    setup_ax(ax, "Forças G calculadas", "g")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)

    # 3. Ângulos integrados
    ax = axes[1, 0]
    ax.plot(times, ff_data.get("roll_angle"),  color=COLORS["accel_x"], linewidth=0.6, label="Roll")
    ax.plot(times, ff_data.get("pitch_angle"), color=COLORS["accel_y"], linewidth=0.6, label="Pitch")
    ax.plot(times, ff_data.get("yaw_angle"),   color=COLORS["accel_z"], linewidth=0.6, label="Yaw (drift)")
    setup_ax(ax, "Ângulos (roll/pitch static, yaw integrado)", "°")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)

    # 4. FF_CONSTANT
    ax = axes[1, 1]
    ax.plot(times, ff_data.get("steering_feedback_intensity"), color=COLORS["power"], linewidth=0.8)
    setup_ax(ax, "FF_CONSTANT — intensidade do puxão lateral", "%")
    ax.set_ylim(-5, 105)

    # 5. FF_RUMBLE
    ax = axes[2, 0]
    ax.plot(times, ff_data.get("rumble_strong"), color=COLORS["brake"],  linewidth=0.6, alpha=0.9, label="Strong")
    ax.plot(times, ff_data.get("rumble_weak"),   color=COLORS["motor"],  linewidth=0.6, alpha=0.9, label="Weak")
    setup_ax(ax, "FF_RUMBLE — vibrações (motor + bump + jerk)", "%")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)
    ax.set_ylim(-5, 105)

    # 6. FF_PERIODIC
    ax = axes[2, 1]
    ax.plot(times, ff_data.get("periodic_magnitude"), color=COLORS["rpm"], linewidth=0.6, label="Magnitude")
    ax.set_ylabel("Magnitude (%)", color=COLORS["rpm"])
    ax.set_ylim(-5, 105)
    ax.set_title("FF_PERIODIC — vibração do motor (senoidal)", color="white", fontweight="bold")
    ax.grid(True, alpha=0.4)
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M:%S"))
    ax.tick_params(axis='y', labelcolor=COLORS["rpm"])
    ax2 = ax.twinx()
    ax2.plot(times, ff_data.get("periodic_period_ms"), color=COLORS["temp_rpi"], linewidth=0.6, alpha=0.7, label="Period")
    ax2.set_ylabel("Period (ms)", color=COLORS["temp_rpi"])
    ax2.tick_params(axis='y', labelcolor=COLORS["temp_rpi"])

    # 7. FF_INERTIA
    ax = axes[3, 0]
    ax.plot(times, ff_data.get("inertia"), color=COLORS["gear"], linewidth=0.8)
    setup_ax(ax, "FF_INERTIA — peso do volante", "%")
    ax.set_ylim(0, 85)

    # 8. Jerks detectados (derivadas)
    ax = axes[3, 1]
    ax.plot(times, ff_data.get("ff_jerk_steering"), color=COLORS["steering"], linewidth=0.5, alpha=0.8, label="Steering")
    ax.plot(times, ff_data.get("ff_jerk_frontal"),  color=COLORS["accel_x"],  linewidth=0.5, alpha=0.8, label="Frontal")
    ax.plot(times, ff_data.get("ff_jerk_vertical"), color=COLORS["accel_z"],  linewidth=0.5, alpha=0.8, label="Vertical")
    setup_ax(ax, "Jerks (derivadas para detecção de eventos bruscos)", "unidade/s")
    ax.legend(loc="upper right", framealpha=0.3, fontsize=8)

    plt.tight_layout()
    plt.savefig(out / "10_force_feedback.png", dpi=130)
    plt.close()


def plot_dashboard(data, times, out: Path):
    fig = plt.figure(figsize=(16, 10))
    fig.suptitle("Dashboard — Sessão F1 Car", fontweight="bold", fontsize=14)

    gs = fig.add_gridspec(3, 2, hspace=0.45, wspace=0.2)

    ax = fig.add_subplot(gs[0, 0])
    ax.plot(times, data.get("voltage_battery"), color=COLORS["battery"], linewidth=1.0)
    setup_ax(ax, "Tensão Bateria", "V")

    ax = fig.add_subplot(gs[0, 1])
    ax.plot(times, data.get("current_motor"), color=COLORS["motor"], linewidth=0.8)
    setup_ax(ax, "Corrente Motor", "A")

    ax = fig.add_subplot(gs[1, 0])
    ax.plot(times, data.get("power_total"), color=COLORS["power"], linewidth=0.8)
    setup_ax(ax, "Potência Total", "W")

    ax = fig.add_subplot(gs[1, 1])
    ax.plot(times, data.get("temperature_c"),     color=COLORS["temp_body"], linewidth=0.8, label="DS18B20")
    ax.plot(times, data.get("rpi_cpu_temp_c"),    color=COLORS["temp_rpi"],  linewidth=0.8, label="RPi")
    setup_ax(ax, "Temperaturas", "°C")
    ax.legend(loc="upper left", framealpha=0.3, fontsize=8)

    ax = fig.add_subplot(gs[2, 0])
    ax.plot(times, data.get("rpm_percent"), color=COLORS["rpm"], linewidth=0.8)
    setup_ax(ax, "RPM (%)", "%")
    ax.set_ylim(-5, 105)

    ax = fig.add_subplot(gs[2, 1])
    lat = data.get("net_latency_ms")
    if lat is not None:
        mask = lat > 0
        ax.scatter(np.array(times)[mask], lat[mask], c=COLORS["latency"], s=0.8, alpha=0.5)
    setup_ax(ax, "Latência UDP", "ms")
    ax.set_ylim(0, 250)

    plt.savefig(out / "00_dashboard.png", dpi=130)
    plt.close()


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    if len(sys.argv) < 2:
        print("Uso: python3 scripts/session_plots.py <sessao_dir>")
        sys.exit(1)

    session_dir = Path(sys.argv[1]).resolve()
    exports_dir = session_dir / "exports" / "auto"
    out_dir = session_dir / "analise"
    out_dir.mkdir(exist_ok=True)

    print(f"  Sessão: {session_dir.name}")
    print(f"  Lendo : {exports_dir}")
    data = load_sensors(exports_dir)
    print(f"  sensors: {len(data)} campos | {len(data['timestamp'])} amostras")

    ff_data = load_ff(exports_dir)
    if ff_data is not None:
        ff_n = len(ff_data.get("timestamp", []))
        print(f"  ff     : {len(ff_data)} campos | {ff_n} amostras")
    else:
        print(f"  ff     : (nenhum ff_*.pkl encontrado — sessão antiga)")

    ts = data["timestamp"]
    times = [datetime.fromtimestamp(t) for t in ts]

    print("  Gerando gráficos...")
    plot_dashboard(data, times, out_dir)       ; print("    ✓ 00_dashboard.png")
    plot_bateria(data, times, out_dir)         ; print("    ✓ 01_bateria.png")
    plot_potencia(data, times, out_dir)        ; print("    ✓ 02_potencia.png")
    plot_temperaturas(data, times, out_dir)    ; print("    ✓ 03_temperaturas.png")
    plot_motor(data, times, out_dir)           ; print("    ✓ 04_motor.png")
    plot_imu(data, times, out_dir)             ; print("    ✓ 05_imu.png")
    plot_direcao_freio(data, times, out_dir)   ; print("    ✓ 06_direcao_freio.png")
    plot_rede(data, times, out_dir)            ; print("    ✓ 07_rede.png")
    plot_rpi(data, times, out_dir)             ; print("    ✓ 08_rpi.png")
    plot_timings(data, times, out_dir)         ; print("    ✓ 09_timings.png")
    if ff_data is not None:
        plot_force_feedback(ff_data, out_dir)  ; print("    ✓ 10_force_feedback.png")

    print(f"\n  Salvos em: {out_dir}")


if __name__ == "__main__":
    main()
