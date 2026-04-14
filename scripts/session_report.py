#!/usr/bin/env python3
"""
session_report.py - Relatório detalhado de sessão de testes F1 Car

Lê todos os sensors_*.pkl de um diretório de sessão e gera:
  - Resumo geral da sessão
  - Tabela por blocos de tempo (padrão: 3 min)
  - Estatísticas de bateria, corrente, temperatura, motor, rede, RPi

Uso:
    python3 scripts/session_report.py sessoes/01_indoor_20260413/exports/auto
    python3 scripts/session_report.py sessoes/01_indoor_20260413/exports/auto --block 180
    python3 scripts/session_report.py sessoes/01_indoor_20260413/exports/auto --plot
"""

import argparse
import glob
import pickle
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

# ── helpers ────────────────────────────────────────────────────────────────────

def load_all_sensors(data_dir: str) -> dict[str, np.ndarray]:
    files = sorted(glob.glob(f"{data_dir}/sensors_*.pkl"))
    if not files:
        print(f"[ERRO] Nenhum sensors_*.pkl em: {data_dir}")
        sys.exit(1)

    raw: dict[str, list] = {}
    for f in files:
        with open(f, "rb") as fh:
            d = pickle.load(fh)
        for k, v in d.items():
            vals = v if isinstance(v, list) else list(v)
            raw.setdefault(k, []).extend(vals)

    # Converte apenas arrays numéricos
    result: dict[str, np.ndarray] = {}
    for k, v in raw.items():
        try:
            arr = np.array(v, dtype=float)
            result[k] = arr
        except (ValueError, TypeError):
            pass  # ignora campos não-numéricos (strings, bools)
    return result


def ts_to_str(ts: float) -> str:
    return datetime.fromtimestamp(ts).strftime("%H:%M:%S")


def fmt(val: float, dec: int = 2) -> str:
    return f"{val:.{dec}f}"


def stats(arr: np.ndarray) -> tuple[float, float, float]:
    """Retorna (min, avg, max) ignorando NaN."""
    valid = arr[~np.isnan(arr)]
    if len(valid) == 0:
        return 0.0, 0.0, 0.0
    return float(valid.min()), float(valid.mean()), float(valid.max())


# ── análise ────────────────────────────────────────────────────────────────────

def print_summary(d: dict[str, np.ndarray]) -> None:
    ts = d["timestamp"]
    duration = ts[-1] - ts[0]
    start = ts_to_str(ts[0])
    end   = ts_to_str(ts[-1])
    total_samples = len(ts)

    print("=" * 70)
    print("  RELATÓRIO DE SESSÃO — F1 CAR")
    print("=" * 70)
    print(f"  Início    : {start}")
    print(f"  Fim       : {end}")
    print(f"  Duração   : {duration/60:.1f} min ({duration:.0f}s)")
    print(f"  Amostras  : {total_samples:,} ({total_samples/duration:.0f} Hz estimado)")
    print()

    # Bateria
    vb = d.get("voltage_battery", np.array([]))
    bp = d.get("battery_percentage", np.array([]))
    if len(vb):
        mn, av, mx = stats(vb)
        print(f"  BATERIA")
        print(f"    Tensão     : {fmt(mn)} V  →  {fmt(mx)} V  (avg {fmt(av)} V)")
        print(f"    Percentual : {fmt(bp[0],1)}% → {fmt(bp[-1],1)}%  (queda: {fmt(bp[0]-bp[-1],1)}%)")
        print()

    # Corrente e potência
    cm = d.get("current_motor", np.array([]))
    cs = d.get("current_servos", np.array([]))
    cr = d.get("current_rpi", np.array([]))
    pt = d.get("power_total", np.array([]))
    pm = d.get("power_motor", np.array([]))
    if len(cm):
        mn, av, mx = stats(cm)
        print(f"  CORRENTE MOTOR")
        print(f"    Min/Avg/Max : {fmt(mn)} / {fmt(av)} / {fmt(mx)} A")
        print(f"    Potência motor  : avg {fmt(stats(pm)[1])} W  |  pico {fmt(stats(pm)[2])} W")
        print(f"    Potência total  : avg {fmt(stats(pt)[1])} W  |  pico {fmt(stats(pt)[2])} W")
        print(f"    Corrente servos : avg {fmt(stats(cs)[1],3)} A  |  pico {fmt(stats(cs)[2],3)} A")
        print(f"    Corrente RPi    : avg {fmt(stats(cr)[1],3)} A  |  pico {fmt(stats(cr)[2],3)} A")
        print()

    # Temperatura
    tc  = d.get("temperature_c", np.array([]))   # DS18B20 (carcaça/ambiente)
    trc = d.get("rpi_cpu_temp_c", np.array([]))
    if len(tc):
        print(f"  TEMPERATURA")
        print(f"    DS18B20 (body) : {fmt(stats(tc)[0])} → {fmt(stats(tc)[2])} °C  (avg {fmt(stats(tc)[1])} °C)")
    if len(trc):
        print(f"    RPi CPU        : {fmt(stats(trc)[0])} → {fmt(stats(trc)[2])} °C  (avg {fmt(stats(trc)[1])} °C)")
    print()

    # Motor / marcha
    cg  = d.get("current_gear", np.array([]))
    rpm = d.get("rpm_percent", np.array([]))
    pwm = d.get("current_pwm", np.array([]))
    gc  = d.get("gear_changes", np.array([]))
    if len(cg):
        print(f"  MOTOR / TRANSMISSÃO")
        print(f"    Marcha usada   : {int(cg.min())}ª a {int(cg.max())}ª  (avg {fmt(cg.mean(),1)})")
        print(f"    RPM display    : avg {fmt(stats(rpm)[1],1)}%  |  max {fmt(stats(rpm)[2],1)}%")
        print(f"    PWM            : avg {fmt(stats(pwm)[1],1)}  |  max {fmt(stats(pwm)[2],1)}")
        print(f"    Trocas de marcha: {int(gc.max())}")
        print()

    # Direção
    sa  = d.get("steering_input", np.array([]))
    mar = d.get("max_angle_reached", np.array([]))
    tm  = d.get("total_movements", np.array([]))
    if len(sa):
        print(f"  DIREÇÃO")
        print(f"    Range usado    : {fmt(sa.min(),0)}° a {fmt(sa.max(),0)}°")
        print(f"    Máx ângulo (run): {fmt(stats(mar)[2],1)}°")
        print(f"    Movimentos total: {int(tm.max()) if len(tm) else 'n/a'}")
        print()

    # Freio
    tbi = d.get("total_brake_input", np.array([]))
    ba  = d.get("brake_applications", np.array([]))
    if len(tbi):
        braking_pct = float(np.mean(tbi > 0) * 100)
        print(f"  FREIO")
        print(f"    Tempo com freio: {fmt(braking_pct,1)}% da sessão")
        print(f"    Aplicações     : {int(ba.max()) if len(ba) else 'n/a'}")
        print(f"    Intensidade max: {fmt(stats(tbi)[2],1)}%")
        print()

    # Rede
    lat = d.get("net_latency_ms", np.array([]))
    txr = d.get("rpi_net_tx_rate_kbps", np.array([]))
    if len(lat):
        valid_lat = lat[lat > 0]  # remove negativas (drift de relógio)
        if len(valid_lat):
            print(f"  REDE UDP")
            print(f"    Latência (válida): avg {fmt(stats(valid_lat)[1])} ms  |  max {fmt(stats(valid_lat)[2])} ms")
            print(f"    TX rate (RPi→PC) : avg {fmt(stats(txr)[1],0)} kbps  |  {fmt(stats(txr)[1]/1024,2)} Mbps")
            print()

    # RPi sistema
    cpu  = d.get("rpi_cpu_usage_percent", np.array([]))
    mem  = d.get("rpi_mem_used_mb", np.array([]))
    freq = d.get("rpi_cpu_freq_mhz", np.array([]))
    if len(cpu):
        print(f"  RASPBERRY PI")
        print(f"    CPU uso        : avg {fmt(stats(cpu)[1],1)}%  |  max {fmt(stats(cpu)[2],1)}%")
        print(f"    CPU freq       : avg {fmt(stats(freq)[1],0)} MHz  |  max {fmt(stats(freq)[2],0)} MHz")
        print(f"    RAM usada      : avg {fmt(stats(mem)[1],0)} MB  (total {int(d.get('rpi_mem_total_mb', np.array([3797]))[0])} MB)")
        print()

    print("=" * 70)


def print_blocks(d: dict[str, np.ndarray], block_sec: int = 180) -> None:
    ts = d["timestamp"]
    t0 = ts[0]
    duration = ts[-1] - t0
    n_blocks = int(np.ceil(duration / block_sec))

    header = f"{'Bloco':>6}  {'Horário':>8}  {'Vbat(V)':>8}  {'Imot(A)':>8}  {'Ptot(W)':>8}  {'TBody°C':>8}  {'Marcha':>7}  {'RPM%':>6}  {'Lat(ms)':>8}"
    print()
    print(f"  BLOCOS DE {block_sec}s ({block_sec//60} min)")
    print("-" * len(header))
    print(header)
    print("-" * len(header))

    keys = {
        "vb":  "voltage_battery",
        "cm":  "current_motor",
        "pt":  "power_total",
        "tc":  "temperature_c",
        "cg":  "current_gear",
        "rpm": "rpm_percent",
        "lat": "net_latency_ms",
    }

    for i in range(n_blocks):
        t_start = t0 + i * block_sec
        t_end   = t0 + (i + 1) * block_sec
        mask = (ts >= t_start) & (ts < t_end)
        if not np.any(mask):
            continue

        label   = f"B{i+1:02d}"
        horario = ts_to_str(t_start)

        def blk(key: str, fallback: float = float("nan")) -> float:
            arr = d.get(keys[key])
            if arr is None or len(arr) == 0:
                return fallback
            sub = arr[mask]
            valid = sub[~np.isnan(sub)]
            if len(valid) == 0:
                return fallback
            return float(valid.mean())

        def blk_max(key: str, fallback: float = float("nan")) -> float:
            arr = d.get(keys[key])
            if arr is None or len(arr) == 0:
                return fallback
            sub = arr[mask]
            valid = sub[~np.isnan(sub)]
            if len(valid) == 0:
                return fallback
            return float(valid.max())

        vb  = blk("vb")
        cm  = blk("cm")
        pt  = blk("pt")
        tc  = blk("tc")
        cg  = blk("cg")
        rpm = blk("rpm")
        # Latência: ignora negativos (drift)
        lat_arr = d.get("net_latency_ms", np.array([]))
        if len(lat_arr):
            sub = lat_arr[mask]
            sub = sub[sub > 0]
            lat = float(sub.mean()) if len(sub) else float("nan")
        else:
            lat = float("nan")

        def f(v: float, dec: int = 2) -> str:
            return f"{v:.{dec}f}" if not np.isnan(v) else "  n/a"

        print(f"  {label:>4}  {horario:>8}  {f(vb):>8}  {f(cm):>8}  {f(pt):>8}  {f(tc):>8}  {f(cg,1):>7}  {f(rpm,1):>6}  {f(lat,1):>8}")

    print("-" * len(header))
    print()


def plot_session(d: dict[str, np.ndarray]) -> None:
    try:
        import matplotlib.pyplot as plt
        import matplotlib.dates as mdates
        from datetime import datetime as dt
    except ImportError:
        print("[AVISO] matplotlib não instalado. Instale com: pip install matplotlib")
        return

    ts = d["timestamp"]
    times = [dt.fromtimestamp(t) for t in ts]

    fig, axes = plt.subplots(4, 2, figsize=(16, 14))
    fig.suptitle("Sessão F1 Car — Análise Completa", fontsize=14, fontweight="bold")
    fig.patch.set_facecolor("#1E1E1E")
    for ax in axes.flat:
        ax.set_facecolor("#2A2A2A")
        ax.tick_params(colors="white")
        ax.xaxis.label.set_color("white")
        ax.yaxis.label.set_color("white")
        ax.title.set_color("white")
        for spine in ax.spines.values():
            spine.set_edgecolor("#555")

    def plot(ax, key, label, color, ylabel, title):
        arr = d.get(key)
        if arr is not None and len(arr) == len(ts):
            ax.plot(times, arr, color=color, linewidth=0.6, alpha=0.9)
        ax.set_ylabel(ylabel, color="white")
        ax.set_title(title, color="white")
        ax.xaxis.set_major_formatter(mdates.DateFormatter("%H:%M"))
        ax.grid(True, color="#3C3C3C", linewidth=0.5)

    plot(axes[0,0], "voltage_battery",    "Vbat",    "#00D2BE", "V",    "Tensão da Bateria")
    plot(axes[0,1], "current_motor",      "Imot",    "#FF8700", "A",    "Corrente do Motor")
    plot(axes[1,0], "power_total",        "Ptot",    "#FF5555", "W",    "Potência Total")
    plot(axes[1,1], "temperature_c",      "TBody",   "#55FF55", "°C",   "Temperatura DS18B20")
    plot(axes[2,0], "motor_temperature",  "Tmot",    "#FFAA00", "°C",   "Temperatura do Motor (modelo)")
    plot(axes[2,1], "rpi_cpu_temp_c",     "TRPI",    "#5555FF", "°C",   "Temperatura CPU RPi")
    plot(axes[3,0], "rpm_percent",        "RPM%",    "#00FF00", "%",    "RPM Display (%)")
    plot(axes[3,1], "net_latency_ms",     "Lat",     "#AA00FF", "ms",   "Latência UDP (ms)")

    for ax in axes.flat:
        fig.autofmt_xdate()

    plt.tight_layout()
    out = Path(sys.argv[1]) / "session_plot.png"
    plt.savefig(out, dpi=150, facecolor=fig.get_facecolor())
    print(f"  Gráfico salvo: {out}")
    plt.show()


# ── main ───────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Relatório de sessão F1 Car")
    parser.add_argument("data_dir", help="Diretório com sensors_*.pkl")
    parser.add_argument("--block", type=int, default=180,
                        help="Duração dos blocos em segundos (padrão: 180 = 3 min)")
    parser.add_argument("--plot", action="store_true",
                        help="Gera gráficos matplotlib")
    args = parser.parse_args()

    print(f"\n  Carregando dados de: {args.data_dir}")
    d = load_all_sensors(args.data_dir)
    print(f"  {len(d)} campos numéricos  |  {len(d.get('timestamp', []))} amostras\n")

    print_summary(d)
    print_blocks(d, block_sec=args.block)

    if args.plot:
        plot_session(d)


if __name__ == "__main__":
    main()
