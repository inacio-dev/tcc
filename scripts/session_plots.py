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
    print(f"  {len(data)} campos | {len(data['timestamp'])} amostras")

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

    print(f"\n  Salvos em: {out_dir}")


if __name__ == "__main__":
    main()
