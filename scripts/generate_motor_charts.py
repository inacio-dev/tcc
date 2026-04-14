#!/usr/bin/env python3
"""
Gera gráficos do sistema de transmissão F1 com modelo de 1ª ordem.

Visualiza:
1. Zonas de eficiência por marcha (IDEAL / SUBOPTIMAL / POOR)
2. τ efetivo por marcha e zona
3. Resposta ao degrau (throttle 0→100%) por marcha
4. Simulação de aceleração completa (1ª→5ª marcha)
5. Conta-giros (tachometer) por marcha
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np
import os

# ==================== PARÂMETROS DO MOTOR ====================
# Copiados de raspberry/managers/motor.py

GEAR_PARAMS = {
    # gear: (limiter, ideal_low, ideal_high, τ_base)
    # Teto absoluto de 50% de PWM para proteger o diferencial.
    1: (10,   0,   7,  2.0),
    2: (20,   6,  15,  4.0),
    3: (30,  12,  25,  6.0),
    4: (40,  22,  35,  8.0),
    5: (50,  32,  48, 10.0),
}

TAU_MULTIPLIER = {"IDEAL": 1.0, "SUBOPTIMAL": 10.0, "POOR": 25.0}

# Limite máximo do eixo X para gráficos de PWM. O motor é limitado a 50% de
# duty cycle (limiter da 5ª marcha), então não faz sentido estender o eixo
# até 100%. Mantém 55% como margem visual.
MAX_PWM_DISPLAY = 55

ZONE_COLORS = {"IDEAL": "#2ecc71", "SUBOPTIMAL": "#f39c12", "POOR": "#e74c3c"}
GEAR_COLORS = ["#3498db", "#2ecc71", "#f39c12", "#e67e22", "#e74c3c"]


def classify_zone(pwm, gear):
    limiter, ideal_low, ideal_high, _ = GEAR_PARAMS[gear]
    ideal_width = ideal_high - ideal_low
    sub_margin = max(ideal_width * 0.25, 2.0)
    sub_low = max(ideal_low - sub_margin, 0)
    sub_high = min(ideal_high + sub_margin, limiter)

    if ideal_low <= pwm <= ideal_high:
        return "IDEAL"
    elif sub_low <= pwm <= sub_high:
        return "SUBOPTIMAL"
    return "POOR"


def get_tau(pwm, gear):
    tau_base = GEAR_PARAMS[gear][3]
    zone = classify_zone(pwm, gear)
    return tau_base * TAU_MULTIPLIER[zone]


def tachometer_percent(pwm, gear):
    _, ideal_low, ideal_high, _ = GEAR_PARAMS[gear]
    if pwm <= ideal_low:
        return 0.0
    if pwm >= ideal_high:
        return 100.0
    return ((pwm - ideal_low) / (ideal_high - ideal_low)) * 100.0


# ==================== GRÁFICO 1: ZONAS POR MARCHA ====================

def plot_zones():
    fig, ax = plt.subplots(figsize=(14, 5))

    for g in range(1, 6):
        limiter, ideal_low, ideal_high, tau = GEAR_PARAMS[g]
        ideal_width = ideal_high - ideal_low
        sub_margin = max(ideal_width * 0.25, 2.0)
        sub_low = max(ideal_low - sub_margin, 0)
        sub_high = min(ideal_high + sub_margin, limiter)

        y = 6 - g  # Inverte para 1ª ficar em cima

        # POOR esquerda (de 0 até sub_low)
        if sub_low > 0:
            ax.barh(y, sub_low, left=0, height=0.6,
                    color=ZONE_COLORS["POOR"], alpha=0.7)

        # SUBOPTIMAL esquerda
        if ideal_low > sub_low:
            ax.barh(y, ideal_low - sub_low, left=sub_low, height=0.6,
                    color=ZONE_COLORS["SUBOPTIMAL"], alpha=0.7)

        # IDEAL
        ax.barh(y, ideal_high - ideal_low, left=ideal_low, height=0.6,
                color=ZONE_COLORS["IDEAL"], alpha=0.8)

        # SUBOPTIMAL direita
        if sub_high > ideal_high:
            ax.barh(y, sub_high - ideal_high, left=ideal_high, height=0.6,
                    color=ZONE_COLORS["SUBOPTIMAL"], alpha=0.7)

        # POOR direita
        if limiter > sub_high:
            ax.barh(y, limiter - sub_high, left=sub_high, height=0.6,
                    color=ZONE_COLORS["POOR"], alpha=0.7)

        # Labels
        ax.text(ideal_low + (ideal_high - ideal_low) / 2, y,
                f"IDEAL\n{ideal_low}-{ideal_high}%",
                ha='center', va='center', fontsize=7, fontweight='bold', color='white')
        ax.text(limiter + 1, y, f"τ={tau}s", va='center', fontsize=8, color='#555')

    ax.set_yticks([5, 4, 3, 2, 1])
    ax.set_yticklabels(["1ª", "2ª", "3ª", "4ª", "5ª"])
    ax.set_xlabel("PWM do Motor (%)")
    ax.set_title("Zonas de Eficiência por Marcha — Sistema de 1ª Ordem")
    ax.set_xlim(0, MAX_PWM_DISPLAY)

    legend_patches = [
        mpatches.Patch(color=ZONE_COLORS["POOR"], label="POOR (τ × 25)"),
        mpatches.Patch(color=ZONE_COLORS["SUBOPTIMAL"], label="SUBOPTIMAL (τ × 10)"),
        mpatches.Patch(color=ZONE_COLORS["IDEAL"], label="IDEAL (τ base)"),
    ]
    ax.legend(handles=legend_patches, loc='upper right', fontsize=8)
    ax.grid(axis='x', alpha=0.3)

    fig.tight_layout()
    return fig


# ==================== GRÁFICO 2: τ EFETIVO ====================

def plot_tau():
    fig, ax = plt.subplots(figsize=(14, 5))

    for g in range(1, 6):
        limiter = GEAR_PARAMS[g][0]
        pwm_range = np.linspace(0, limiter, 500)
        taus = [get_tau(p, g) for p in pwm_range]

        ax.plot(pwm_range, taus, color=GEAR_COLORS[g - 1], linewidth=2,
                label=f"{g}ª marcha (τ_base={GEAR_PARAMS[g][3]}s)")

    ax.set_xlabel("PWM do Motor (%)")
    ax.set_ylabel("τ efetivo (segundos)")
    ax.set_title("Constante de Tempo Efetiva por Posição do PWM")
    ax.legend(fontsize=8)
    ax.set_yscale('log')
    ax.set_ylim(1, 300)
    ax.set_xlim(0, MAX_PWM_DISPLAY)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return fig


# ==================== GRÁFICO 3: RESPOSTA AO DEGRAU ====================

def plot_step_response():
    fig, axes = plt.subplots(1, 5, figsize=(18, 4), sharey=True)

    for g in range(1, 6):
        ax = axes[g - 1]
        limiter, ideal_low, ideal_high, tau_base = GEAR_PARAMS[g]
        target = limiter  # Throttle 100%

        # Partida do ideal_low (como se tivesse acabado de trocar de marcha)
        # 1ª marcha parte de 0 (ideal_low da 1ª é 0)
        start_pwm = ideal_low

        # Simula resposta ao degrau
        dt = 0.01
        t_max = 30.0
        t_arr = np.arange(0, t_max, dt)
        pwm_arr = np.zeros_like(t_arr)
        zone_arr = []

        pwm = start_pwm
        for i, t in enumerate(t_arr):
            tau = get_tau(pwm, g)
            pwm += ((target - pwm) / tau) * dt

            pwm_arr[i] = pwm
            zone_arr.append(classify_zone(pwm, g))

        # Plot com cores por zona
        for zone_name, color in ZONE_COLORS.items():
            mask = np.array([z == zone_name for z in zone_arr])
            if mask.any():
                ax.scatter(t_arr[mask], pwm_arr[mask], c=color, s=0.5, alpha=0.8)

        # Linhas de referência
        ax.axhline(ideal_low, color=ZONE_COLORS["IDEAL"], linestyle='--', alpha=0.5, linewidth=0.8)
        ax.axhline(ideal_high, color=ZONE_COLORS["IDEAL"], linestyle='--', alpha=0.5, linewidth=0.8)
        ax.axhline(limiter, color='red', linestyle=':', alpha=0.5, linewidth=0.8)

        ax.set_title(f"{g}ª Marcha\n(ideal: {ideal_low}-{ideal_high}%, limiter: {limiter}%)", fontsize=9)
        ax.set_xlabel("Tempo (s)")
        if g == 1:
            ax.set_ylabel("PWM (%)")
        ax.set_xlim(0, t_max)
        ax.set_ylim(0, 105)
        ax.grid(True, alpha=0.3)

    fig.suptitle(r"Resposta ao Degrau: $y(t) = K(1 - e^{-t/\tau_{eff}})$ — partindo do ideal_low, throttle 100%",
                 fontsize=11, fontweight='bold')
    fig.tight_layout()
    return fig


# ==================== GRÁFICO 4: SIMULAÇÃO COMPLETA ====================

def plot_full_simulation():
    fig, (ax1, ax2) = plt.subplots(2, 1, figsize=(14, 8), sharex=True)

    dt = 0.01
    t_max = 60.0
    t_arr = np.arange(0, t_max, dt)

    pwm_arr = np.zeros_like(t_arr)
    gear_arr = np.ones_like(t_arr, dtype=int)
    tach_arr = np.zeros_like(t_arr)
    zone_arr = []

    pwm = 0.0
    gear = 1
    throttle = 100.0  # Acelerador a fundo o tempo todo

    for i, t in enumerate(t_arr):
        target = (throttle / 100.0) * GEAR_PARAMS[gear][0]

        tau = get_tau(pwm, gear)
        step = ((target - pwm) / tau) * dt
        pwm += step

        # Auto-shift: quando tachometer > 95% e não é 5ª
        tach = tachometer_percent(pwm, gear)
        if tach >= 95 and gear < 5:
            gear += 1
            target = (throttle / 100.0) * GEAR_PARAMS[gear][0]

        pwm_arr[i] = pwm
        gear_arr[i] = gear
        tach_arr[i] = tachometer_percent(pwm, gear)
        zone_arr.append(classify_zone(pwm, gear))

    # Plot PWM com cores por zona
    for zone_name, color in ZONE_COLORS.items():
        mask = np.array([z == zone_name for z in zone_arr])
        if mask.any():
            ax1.scatter(t_arr[mask], pwm_arr[mask], c=color, s=0.5, alpha=0.8)

    # Linhas de troca de marcha
    for g in range(2, 6):
        idx = np.where(np.diff(gear_arr) > 0)[0]
        for j in idx:
            if gear_arr[j + 1] == g:
                ax1.axvline(t_arr[j], color='gray', linestyle='--', alpha=0.4)
                ax1.text(t_arr[j], 102, f"→{g}ª", fontsize=7, ha='center', color='gray')

    ax1.set_ylabel("PWM do Motor (%)")
    ax1.set_title("Simulação Completa — Throttle 100% com Troca Automática")
    ax1.set_ylim(0, 105)
    ax1.grid(True, alpha=0.3)

    # Limiters
    for g in range(1, 6):
        limiter = GEAR_PARAMS[g][0]
        ax1.axhline(limiter, color=GEAR_COLORS[g - 1], linestyle=':', alpha=0.3, linewidth=0.8)

    # Plot conta-giros
    ax2.fill_between(t_arr, tach_arr, alpha=0.3, color='#3498db')
    ax2.plot(t_arr, tach_arr, color='#3498db', linewidth=1)
    ax2.axhline(100, color='red', linestyle=':', alpha=0.5)
    ax2.set_ylabel("Conta-giros (%)")
    ax2.set_xlabel("Tempo (s)")
    ax2.set_ylim(0, 110)
    ax2.grid(True, alpha=0.3)

    # Marcha no eixo secundário
    ax2_twin = ax2.twinx()
    ax2_twin.step(t_arr, gear_arr, color='orange', alpha=0.5, linewidth=1.5, where='post')
    ax2_twin.set_ylabel("Marcha", color='orange')
    ax2_twin.set_ylim(0.5, 5.5)
    ax2_twin.set_yticks([1, 2, 3, 4, 5])

    fig.tight_layout()
    return fig


# ==================== GRÁFICO 5: CONTA-GIROS POR MARCHA ====================

def plot_tachometer():
    fig, ax = plt.subplots(figsize=(14, 5))

    for g in range(1, 6):
        limiter = GEAR_PARAMS[g][0]
        pwm_range = np.linspace(0, limiter, 500)
        tach = [tachometer_percent(p, g) for p in pwm_range]

        ax.plot(pwm_range, tach, color=GEAR_COLORS[g - 1], linewidth=2,
                label=f"{g}ª marcha (0-{limiter}%)")

        # Marca zona ideal
        _, ideal_low, ideal_high, _ = GEAR_PARAMS[g]
        ax.axvspan(ideal_low, ideal_high, alpha=0.08, color=GEAR_COLORS[g - 1])

    ax.axhline(100, color='red', linestyle=':', alpha=0.5, label='Tachometer 100%')

    ax.set_xlabel("PWM do Motor (%)")
    ax.set_ylabel("Conta-giros (%)")
    ax.set_title("Mapeamento Conta-giros por Marcha (0% = ideal_low, 100% = ideal_high)")
    ax.legend(fontsize=8, loc='upper left')
    ax.set_xlim(0, MAX_PWM_DISPLAY)
    ax.set_ylim(-5, 110)
    ax.grid(True, alpha=0.3)

    fig.tight_layout()
    return fig


# ==================== GRÁFICO 6: τ DETALHADO COM CÁLCULOS ====================

def plot_tau_detailed():
    """
    Mostra τ efetivo por marcha com anotações dos cálculos.
    Cada subplot mostra uma marcha com as fronteiras de zona e os valores de τ.
    """
    fig, axes = plt.subplots(2, 3, figsize=(18, 10))
    axes = axes.flatten()

    for g in range(1, 6):
        ax = axes[g - 1]
        limiter, ideal_low, ideal_high, tau_base = GEAR_PARAMS[g]

        # Faixas de zona
        ideal_width = ideal_high - ideal_low
        sub_margin = max(ideal_width * 0.25, 2.0)
        sub_low = max(ideal_low - sub_margin, 0)
        sub_high = min(ideal_high + sub_margin, limiter)

        # PWM range completo
        pwm_range = np.linspace(0, min(limiter + 5, 105), 1000)
        taus = np.array([get_tau(p, g) for p in pwm_range])

        # Plot τ
        ax.plot(pwm_range, taus, color=GEAR_COLORS[g - 1], linewidth=2.5)

        # Colore fundo por zona
        if sub_low > 0:
            ax.axvspan(0, sub_low, alpha=0.1, color=ZONE_COLORS["POOR"])
        ax.axvspan(sub_low, ideal_low, alpha=0.1, color=ZONE_COLORS["SUBOPTIMAL"])
        ax.axvspan(ideal_low, ideal_high, alpha=0.15, color=ZONE_COLORS["IDEAL"])
        if sub_high > ideal_high:
            ax.axvspan(ideal_high, sub_high, alpha=0.1, color=ZONE_COLORS["SUBOPTIMAL"])
        if limiter > sub_high:
            ax.axvspan(sub_high, limiter, alpha=0.1, color=ZONE_COLORS["POOR"])

        # Valores de τ por zona com cálculos
        tau_ideal = tau_base * TAU_MULTIPLIER["IDEAL"]
        tau_sub = tau_base * TAU_MULTIPLIER["SUBOPTIMAL"]
        tau_poor = tau_base * TAU_MULTIPLIER["POOR"]

        # Anotações com cálculos
        mid_ideal = (ideal_low + ideal_high) / 2
        ax.annotate(
            f'IDEAL\nτ = {tau_base} × 1.0 = {tau_ideal:.0f}s',
            xy=(mid_ideal, tau_ideal), xytext=(mid_ideal, tau_ideal * 1.8),
            fontsize=8, ha='center', fontweight='bold', color=ZONE_COLORS["IDEAL"],
            arrowprops=dict(arrowstyle='->', color=ZONE_COLORS["IDEAL"], lw=1.5),
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor=ZONE_COLORS["IDEAL"], alpha=0.9)
        )

        # Anotação SUBOPTIMAL (no meio da zona sub esquerda ou direita)
        if ideal_low > sub_low + 1:
            mid_sub = (sub_low + ideal_low) / 2
        elif sub_high > ideal_high + 1:
            mid_sub = (ideal_high + sub_high) / 2
        else:
            mid_sub = ideal_low - 1
        ax.annotate(
            f'SUB\nτ = {tau_base} × 10 = {tau_sub:.0f}s',
            xy=(mid_sub, tau_sub), xytext=(mid_sub, tau_sub * 1.5),
            fontsize=7, ha='center', color=ZONE_COLORS["SUBOPTIMAL"],
            arrowprops=dict(arrowstyle='->', color=ZONE_COLORS["SUBOPTIMAL"], lw=1),
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor=ZONE_COLORS["SUBOPTIMAL"], alpha=0.9)
        )

        # Anotação POOR (se existir zona POOR visível)
        if sub_low > 2 or limiter > sub_high + 2:
            poor_pos = 1 if sub_low > 2 else limiter - 1
            ax.annotate(
                f'POOR\nτ = {tau_base} × 25 = {tau_poor:.0f}s',
                xy=(poor_pos, tau_poor), xytext=(poor_pos, tau_poor * 0.7),
                fontsize=7, ha='center', color=ZONE_COLORS["POOR"],
                arrowprops=dict(arrowstyle='->', color=ZONE_COLORS["POOR"], lw=1),
                bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor=ZONE_COLORS["POOR"], alpha=0.9)
            )

        # Linhas de fronteira
        ax.axvline(ideal_low, color=ZONE_COLORS["IDEAL"], linestyle='--', alpha=0.6, linewidth=1)
        ax.axvline(ideal_high, color=ZONE_COLORS["IDEAL"], linestyle='--', alpha=0.6, linewidth=1)
        ax.axvline(limiter, color='red', linestyle=':', alpha=0.6, linewidth=1)

        ax.set_title(f"{g}ª Marcha — τ_base = {tau_base}s\n"
                     f"(ideal: {ideal_low}-{ideal_high}%, limiter: {limiter}%)",
                     fontsize=10, fontweight='bold')
        ax.set_xlabel("PWM (%)")
        ax.set_ylabel("τ efetivo (s)")
        ax.set_yscale('log')
        ax.set_ylim(tau_ideal * 0.5, tau_poor * 2)
        ax.set_xlim(0, limiter + 5)
        ax.grid(True, alpha=0.2)

    # Subplot 6: tabela resumo dos cálculos
    ax_table = axes[5]
    ax_table.axis('off')

    # Função de transferência
    ax_table.text(0.5, 0.97,
                  r'Função de Transferência:  $G(s) = \frac{K}{\tau_{eff} \cdot s + 1}$',
                  fontsize=15, ha='center', va='top', fontweight='bold',
                  transform=ax_table.transAxes,
                  bbox=dict(boxstyle='round,pad=0.5', facecolor='#ecf0f1', edgecolor='#2c3e50'))

    # Resposta ao degrau + ODE
    ax_table.text(0.5, 0.80,
                  r'Resposta ao degrau:  $y(t) = K\left(1 - e^{-t/\tau_{eff}}\right)$'
                  '\n'
                  r'ODE:  $\tau_{eff} \cdot \dot{y} + y = K \cdot u(t)$'
                  '\n\n'
                  r'$K = target_{PWM}$,   $\tau_{eff} = \tau_{base}(g) \times M_{zona}$',
                  fontsize=11, ha='center', va='top',
                  transform=ax_table.transAxes,
                  linespacing=1.6)

    # Tabela de multiplicadores
    table_data = [
        ['Zona', 'Multiplicador', 'Significado'],
        ['IDEAL', '1.0×', 'Resposta rápida'],
        ['SUBOPTIMAL', '10.0×', 'Resposta lenta'],
        ['POOR', '25.0×', 'Resposta muito lenta'],
    ]

    table = ax_table.table(
        cellText=table_data[1:],
        colLabels=table_data[0],
        loc='center',
        cellLoc='center',
        bbox=[0.1, 0.25, 0.8, 0.35]
    )
    table.auto_set_font_size(False)
    table.set_fontsize(10)

    # Colore header
    for j in range(3):
        table[0, j].set_facecolor('#2c3e50')
        table[0, j].set_text_props(color='white', fontweight='bold')
    # Colore zonas
    table[1, 0].set_facecolor(ZONE_COLORS["IDEAL"] + '40')
    table[2, 0].set_facecolor(ZONE_COLORS["SUBOPTIMAL"] + '40')
    table[3, 0].set_facecolor(ZONE_COLORS["POOR"] + '40')

    # Tabela de τ_base por marcha
    tau_table_data = [['Marcha', 'τ_base', 'τ_IDEAL', 'τ_SUB', 'τ_POOR']]
    for g in range(1, 6):
        tb = GEAR_PARAMS[g][3]
        tau_table_data.append([
            f'{g}ª', f'{tb:.0f}s',
            f'{tb * 1:.0f}s', f'{tb * 10:.0f}s', f'{tb * 25:.0f}s'
        ])

    table2 = ax_table.table(
        cellText=tau_table_data[1:],
        colLabels=tau_table_data[0],
        loc='center',
        cellLoc='center',
        bbox=[0.05, -0.15, 0.9, 0.35]
    )
    table2.auto_set_font_size(False)
    table2.set_fontsize(9)
    for j in range(5):
        table2[0, j].set_facecolor('#2c3e50')
        table2[0, j].set_text_props(color='white', fontweight='bold')
    for i in range(1, 6):
        table2[i, 0].set_facecolor(GEAR_COLORS[i - 1] + '30')

    fig.suptitle("Constante de Tempo τ por Marcha — Detalhamento dos Cálculos",
                 fontsize=13, fontweight='bold', y=1.01)
    fig.tight_layout()
    return fig


# ==================== GRÁFICO 7: EVOLUÇÃO DE τ NA SIMULAÇÃO ====================

def plot_tau_evolution():
    """
    Simula aceleração 1ª→5ª e mostra como τ muda ao longo do tempo.
    3 subplots: PWM, τ efetivo, e marcha/zona.
    """
    fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(16, 10), sharex=True)

    dt = 0.01
    t_max = 60.0
    t_arr = np.arange(0, t_max, dt)

    pwm_arr = np.zeros_like(t_arr)
    tau_arr = np.zeros_like(t_arr)
    gear_arr = np.ones_like(t_arr, dtype=int)
    zone_arr = []

    pwm = 0.0
    gear = 1
    throttle = 100.0

    for i, t in enumerate(t_arr):
        target = (throttle / 100.0) * GEAR_PARAMS[gear][0]

        tau = get_tau(pwm, gear)
        step = ((target - pwm) / tau) * dt
        pwm += step

        tach = tachometer_percent(pwm, gear)
        if tach >= 95 and gear < 5:
            gear += 1

        pwm_arr[i] = pwm
        tau_arr[i] = tau
        gear_arr[i] = gear
        zone_arr.append(classify_zone(pwm, gear))

    zone_colors_arr = [ZONE_COLORS[z] for z in zone_arr]

    # --- Subplot 1: PWM ---
    for zone_name, color in ZONE_COLORS.items():
        mask = np.array([z == zone_name for z in zone_arr])
        if mask.any():
            ax1.scatter(t_arr[mask], pwm_arr[mask], c=color, s=0.5, alpha=0.8)

    # Linhas de troca de marcha
    shift_times = []
    idx = np.where(np.diff(gear_arr) > 0)[0]
    for j in idx:
        shift_times.append((t_arr[j], gear_arr[j + 1]))
        for ax in [ax1, ax2, ax3]:
            ax.axvline(t_arr[j], color='gray', linestyle='--', alpha=0.3)
        ax1.text(t_arr[j], 102, f"→{gear_arr[j+1]}ª", fontsize=7, ha='center', color='gray')

    ax1.set_ylabel("PWM do Motor (%)")
    ax1.set_title("Evolução do PWM")
    ax1.set_ylim(0, 105)
    ax1.grid(True, alpha=0.2)

    # --- Subplot 2: τ efetivo (log scale) ---
    # Plot τ colorido por zona
    for zone_name, color in ZONE_COLORS.items():
        mask = np.array([z == zone_name for z in zone_arr])
        if mask.any():
            ax2.scatter(t_arr[mask], tau_arr[mask], c=color, s=1, alpha=0.8)

    # Anotações nos pontos de troca de marcha
    for t_shift, new_gear in shift_times:
        j = np.searchsorted(t_arr, t_shift)
        tau_before = tau_arr[max(0, j - 1)]
        tau_after = tau_arr[min(len(tau_arr) - 1, j + 10)]
        tb_old = GEAR_PARAMS[new_gear - 1][3]
        tb_new = GEAR_PARAMS[new_gear][3]

        # Anotação mostrando a mudança de τ_base
        ax2.annotate(
            f'{new_gear - 1}ª→{new_gear}ª\n'
            f'τ_base: {tb_old}→{tb_new}s\n'
            f'τ_eff: {tau_before:.1f}→{tau_after:.1f}s',
            xy=(t_shift, tau_after),
            xytext=(t_shift + 2, tau_after * 3),
            fontsize=7, ha='left',
            arrowprops=dict(arrowstyle='->', color='gray', lw=1),
            bbox=dict(boxstyle='round,pad=0.3', facecolor='white', edgecolor='gray', alpha=0.9)
        )

    # Linhas horizontais para τ_base de cada marcha
    for g in range(1, 6):
        tb = GEAR_PARAMS[g][3]
        ax2.axhline(tb, color=GEAR_COLORS[g - 1], linestyle=':', alpha=0.3, linewidth=0.8)
        ax2.text(t_max + 0.5, tb, f'τ_base {g}ª={tb}s', fontsize=7,
                 va='center', color=GEAR_COLORS[g - 1])

    ax2.set_ylabel("τ efetivo (s)")
    ax2.set_title("Evolução de τ — Mostra como a constante de tempo muda com zona e marcha")
    ax2.set_yscale('log')
    ax2.set_ylim(0.1, 300)
    ax2.grid(True, alpha=0.2)

    # Legenda de zonas
    legend_patches = [
        mpatches.Patch(color=ZONE_COLORS["IDEAL"], label=f"IDEAL (τ × 1.0)"),
        mpatches.Patch(color=ZONE_COLORS["SUBOPTIMAL"], label=f"SUBOPTIMAL (τ × 10)"),
        mpatches.Patch(color=ZONE_COLORS["POOR"], label=f"POOR (τ × 25)"),
    ]
    ax2.legend(handles=legend_patches, loc='upper right', fontsize=8)

    # --- Subplot 3: Marcha + zona como heatmap ---
    zone_numeric = np.array([{"IDEAL": 1, "SUBOPTIMAL": 2, "POOR": 3}[z] for z in zone_arr])

    ax3.step(t_arr, gear_arr, color='#2c3e50', linewidth=2, where='post', label='Marcha')
    ax3.set_ylabel("Marcha")
    ax3.set_yticks([1, 2, 3, 4, 5])
    ax3.set_ylim(0.5, 5.5)
    ax3.set_xlabel("Tempo (s)")
    ax3.grid(True, alpha=0.2)

    # Barra de zona no fundo
    ax3_twin = ax3.twinx()
    for zone_name, color in ZONE_COLORS.items():
        zone_val = {"IDEAL": 1, "SUBOPTIMAL": 2, "POOR": 3}[zone_name]
        mask = zone_numeric == zone_val
        if mask.any():
            ax3_twin.fill_between(t_arr, 0, 1, where=mask, color=color, alpha=0.3, step='post')
    ax3_twin.set_yticks([])
    ax3_twin.set_ylim(0, 1)

    ax3.set_title("Marcha Atual + Zona de Eficiência")
    ax3.legend(loc='upper left', fontsize=8)

    fig.suptitle("Evolução de τ Durante Aceleração Completa (1ª→5ª, Throttle 100%)",
                 fontsize=13, fontweight='bold')
    fig.tight_layout()
    return fig


# ==================== GRÁFICO 8: ODE — EQUAÇÃO DIFERENCIAL EM AÇÃO ====================

def plot_ode_equation():
    """
    Mostra a ODE dPWM/dt = (target - PWM) / τ_eff em ação:
    - Subplot 1: PWM(t) e target(t)
    - Subplot 2: Erro = target - PWM (numerador da ODE)
    - Subplot 3: τ_eff (denominador da ODE)
    - Subplot 4: dPWM/dt = erro / τ_eff (a derivada — taxa de mudança)
    Tudo anotado com a equação e como cada componente muda.
    """
    fig, (ax1, ax2, ax3, ax4) = plt.subplots(4, 1, figsize=(16, 14), sharex=True)

    dt = 0.01
    t_max = 60.0
    t_arr = np.arange(0, t_max, dt)

    pwm_arr = np.zeros_like(t_arr)
    target_arr = np.zeros_like(t_arr)
    tau_arr = np.zeros_like(t_arr)
    error_arr = np.zeros_like(t_arr)
    dpwm_dt_arr = np.zeros_like(t_arr)
    gear_arr = np.ones_like(t_arr, dtype=int)
    zone_arr = []

    pwm = 0.0
    gear = 1
    throttle = 100.0

    for i, t in enumerate(t_arr):
        target = (throttle / 100.0) * GEAR_PARAMS[gear][0]

        tau = get_tau(pwm, gear)
        err = target - pwm
        dpwm_dt = err / tau
        pwm += dpwm_dt * dt

        tach = tachometer_percent(pwm, gear)
        if tach >= 95 and gear < 5:
            gear += 1

        pwm_arr[i] = pwm
        target_arr[i] = target
        tau_arr[i] = tau
        error_arr[i] = target - pwm
        dpwm_dt_arr[i] = dpwm_dt
        gear_arr[i] = gear
        zone_arr.append(classify_zone(pwm, gear))

    # Pontos de troca de marcha
    shift_idx = np.where(np.diff(gear_arr) > 0)[0]

    # === Subplot 1: PWM(t) e target(t) ===
    for zone_name, color in ZONE_COLORS.items():
        mask = np.array([z == zone_name for z in zone_arr])
        if mask.any():
            ax1.scatter(t_arr[mask], pwm_arr[mask], c=color, s=0.5, alpha=0.8)
    ax1.plot(t_arr, target_arr, color='#e74c3c', linewidth=1, linestyle='--', alpha=0.6, label='target(t)')
    ax1.set_ylabel("PWM (%)")
    ax1.set_title(r"$y(t) = K(1 - e^{-t/\tau_{eff}})$ onde $K = target$  —  Resposta do sistema", fontsize=11)
    ax1.legend(loc='lower right', fontsize=9)
    ax1.set_ylim(0, 105)
    ax1.grid(True, alpha=0.2)

    for j in shift_idx:
        ax1.axvline(t_arr[j], color='gray', linestyle='--', alpha=0.3)
        ax1.text(t_arr[j], 103, f"→{gear_arr[j+1]}ª", fontsize=7, ha='center', color='gray')

    # === Subplot 2: Erro = target - PWM (numerador) ===
    for zone_name, color in ZONE_COLORS.items():
        mask = np.array([z == zone_name for z in zone_arr])
        if mask.any():
            ax2.scatter(t_arr[mask], error_arr[mask], c=color, s=0.5, alpha=0.8)

    ax2.set_ylabel("target − PWM (%)")
    ax2.set_title(r"Erro $e(t) = K - y(t) = target - PWM$  —  Sinal de erro", fontsize=11)
    ax2.grid(True, alpha=0.2)
    ax2.axhline(0, color='black', linewidth=0.5)

    for j in shift_idx:
        ax2.axvline(t_arr[j], color='gray', linestyle='--', alpha=0.3)
        # Mostra salto no erro quando target muda
        err_before = error_arr[j]
        err_after = error_arr[min(j + 10, len(error_arr) - 1)]
        ax2.annotate(
            f'→{gear_arr[j+1]}ª\nerro: {err_before:.1f}→{err_after:.1f}%',
            xy=(t_arr[j], err_after), xytext=(t_arr[j] + 1.5, err_after + 8),
            fontsize=7, ha='left',
            arrowprops=dict(arrowstyle='->', color='gray', lw=0.8),
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='gray', alpha=0.9)
        )

    # === Subplot 3: τ_eff (denominador) ===
    for zone_name, color in ZONE_COLORS.items():
        mask = np.array([z == zone_name for z in zone_arr])
        if mask.any():
            ax3.scatter(t_arr[mask], tau_arr[mask], c=color, s=1, alpha=0.8)

    ax3.set_ylabel("τ_eff (s)")
    ax3.set_title(r"$\tau_{eff}(g, zona) = \tau_{base}(g) \times M_{zona}$  —  Constante de tempo em $G(s) = \frac{K}{\tau s + 1}$", fontsize=11)
    ax3.set_yscale('log')
    ax3.set_ylim(0.1, 300)
    ax3.grid(True, alpha=0.2)

    # τ_base de cada marcha como referência
    for g in range(1, 6):
        tb = GEAR_PARAMS[g][3]
        ax3.axhline(tb, color=GEAR_COLORS[g - 1], linestyle=':', alpha=0.3, linewidth=0.8)
        ax3.text(t_max + 0.3, tb, f'τ_base {g}ª = {tb}s', fontsize=7, va='center', color=GEAR_COLORS[g - 1])

    for j in shift_idx:
        ax3.axvline(t_arr[j], color='gray', linestyle='--', alpha=0.3)

    legend_patches = [
        mpatches.Patch(color=ZONE_COLORS["IDEAL"], label="IDEAL (×1)"),
        mpatches.Patch(color=ZONE_COLORS["SUBOPTIMAL"], label="SUBOPTIMAL (×10)"),
        mpatches.Patch(color=ZONE_COLORS["POOR"], label="POOR (×25)"),
    ]
    ax3.legend(handles=legend_patches, loc='upper right', fontsize=8)

    # === Subplot 4: dPWM/dt = erro / τ_eff (A DERIVADA!) ===
    for zone_name, color in ZONE_COLORS.items():
        mask = np.array([z == zone_name for z in zone_arr])
        if mask.any():
            ax4.scatter(t_arr[mask], dpwm_dt_arr[mask], c=color, s=1, alpha=0.8)

    ax4.set_ylabel("dPWM/dt (%/s)")
    ax4.set_xlabel("Tempo (s)")
    ax4.set_title(
        r"$\dot{y}(t) = \frac{K - y(t)}{\tau_{eff}}$  —  Taxa de variação (derivada da resposta ao degrau)",
        fontsize=11
    )
    ax4.grid(True, alpha=0.2)
    ax4.axhline(0, color='black', linewidth=0.5)

    for j in shift_idx:
        ax4.axvline(t_arr[j], color='gray', linestyle='--', alpha=0.3)
        rate_before = dpwm_dt_arr[max(0, j - 1)]
        rate_after = dpwm_dt_arr[min(j + 10, len(dpwm_dt_arr) - 1)]
        ax4.annotate(
            f'→{gear_arr[j+1]}ª\n'
            f'dPWM/dt: {rate_before:.2f}→{rate_after:.2f} %/s\n'
            f'(novo target, novo τ)',
            xy=(t_arr[j], rate_after), xytext=(t_arr[j] + 1.5, rate_after + 0.5),
            fontsize=7, ha='left',
            arrowprops=dict(arrowstyle='->', color='gray', lw=0.8),
            bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='gray', alpha=0.9)
        )

    # Anotação da equação no gráfico
    ax4.text(0.98, 0.95,
             r'$G(s) = \frac{K}{\tau_{eff} \cdot s + 1}$'
             '\n\n'
             r'$y(t) = K(1 - e^{-t/\tau_{eff}})$'
             '\n\n'
             r'$\dot{y} = \frac{K}{\tau_{eff}} \cdot e^{-t/\tau_{eff}} = \frac{K - y}{\tau_{eff}}$'
             '\n\n'
             r'$K = target,\ \ \tau_{eff} = \tau_{base} \times M_{zona}$',
             transform=ax4.transAxes, fontsize=9,
             va='top', ha='right',
             bbox=dict(boxstyle='round,pad=0.5', facecolor='#ecf0f1', edgecolor='#2c3e50', alpha=0.95))

    fig.suptitle(
        r"Sistema de 1ª Ordem: $G(s) = \frac{K}{\tau_{eff} s + 1}$  —  Decomposição dos Componentes",
        fontsize=14, fontweight='bold', y=1.01
    )
    fig.tight_layout()
    return fig


# ==================== GRÁFICO 9: ODE POR MARCHA (CAMPO DE DIREÇÕES) ====================

def plot_ode_per_gear():
    """
    Para cada marcha, mostra o campo de direções da ODE:
    dPWM/dt vs PWM para target fixo (throttle 100%).
    Mostra como a derivada varia conforme o PWM muda de zona.
    """
    fig, axes = plt.subplots(1, 5, figsize=(20, 5), sharey=True)

    for g in range(1, 6):
        ax = axes[g - 1]
        limiter, ideal_low, ideal_high, tau_base = GEAR_PARAMS[g]
        target = limiter  # throttle 100%

        # Zonas
        ideal_width = ideal_high - ideal_low
        sub_margin = max(ideal_width * 0.25, 2.0)
        sub_low = max(ideal_low - sub_margin, 0)
        sub_high = min(ideal_high + sub_margin, limiter)

        pwm_range = np.linspace(0, limiter, 500)

        # dPWM/dt = (target - PWM) / τ_eff(PWM, g)
        rates = []
        zones = []
        for p in pwm_range:
            tau = get_tau(p, g)
            rate = (target - p) / tau
            rates.append(rate)
            zones.append(classify_zone(p, g))

        rates = np.array(rates)

        # Plot colorido por zona
        for zone_name, color in ZONE_COLORS.items():
            mask = np.array([z == zone_name for z in zones])
            if mask.any():
                ax.plot(pwm_range[mask], rates[mask], color=color, linewidth=2.5)

        # Fundo das zonas
        if sub_low > 0:
            ax.axvspan(0, sub_low, alpha=0.05, color=ZONE_COLORS["POOR"])
        ax.axvspan(sub_low, ideal_low, alpha=0.05, color=ZONE_COLORS["SUBOPTIMAL"])
        ax.axvspan(ideal_low, ideal_high, alpha=0.1, color=ZONE_COLORS["IDEAL"])
        if sub_high > ideal_high:
            ax.axvspan(ideal_high, sub_high, alpha=0.05, color=ZONE_COLORS["SUBOPTIMAL"])
        if limiter > sub_high:
            ax.axvspan(sub_high, limiter, alpha=0.05, color=ZONE_COLORS["POOR"])

        # Fronteiras
        ax.axvline(ideal_low, color=ZONE_COLORS["IDEAL"], linestyle='--', alpha=0.5, linewidth=0.8)
        ax.axvline(ideal_high, color=ZONE_COLORS["IDEAL"], linestyle='--', alpha=0.5, linewidth=0.8)
        ax.axvline(limiter, color='red', linestyle=':', alpha=0.5, linewidth=0.8)
        ax.axhline(0, color='black', linewidth=0.5)

        # Anotações dos valores de dPWM/dt em pontos-chave
        key_points = [
            (0.5, "PWM=0%"),
            (ideal_low, f"PWM={ideal_low}%"),
            ((ideal_low + ideal_high) / 2, "centro ideal"),
            (ideal_high, f"PWM={ideal_high}%"),
        ]
        # Remove pontos duplicados (ex: 1ª marcha onde ideal_low == 0)
        seen = set()
        unique_key_points = []
        for pwm_pt, label in key_points:
            key = round(pwm_pt, 1)
            if key not in seen:
                seen.add(key)
                unique_key_points.append((pwm_pt, label))

        for pwm_pt, label in unique_key_points:
            if pwm_pt <= limiter:
                tau_pt = get_tau(pwm_pt, g)
                rate_pt = (target - pwm_pt) / tau_pt
                ax.plot(pwm_pt, rate_pt, 'ko', markersize=4)
                ax.annotate(
                    f'{label}\nτ_eff={tau_pt:.0f}s, K={target:.0f}\n'
                    f'ẏ = (K−y)/τ =\n  ({target:.0f}−{pwm_pt:.0f})/{tau_pt:.0f}\n  ={rate_pt:.2f}%/s',
                    xy=(pwm_pt, rate_pt),
                    xytext=(pwm_pt, rate_pt + 0.3),
                    fontsize=6, ha='center',
                    bbox=dict(boxstyle='round,pad=0.2', facecolor='white', edgecolor='gray', alpha=0.9)
                )

        ax.set_xlabel("PWM (%)")
        if g == 1:
            ax.set_ylabel("dPWM/dt (%/s)")
        ax.set_title(
            f"{g}ª Marcha\n"
            f"K={limiter}%, τ_base={tau_base}s",
            fontsize=9, fontweight='bold'
        )
        ax.grid(True, alpha=0.2)

    fig.suptitle(
        r"Campo de Direções: $\dot{y} = \frac{K - y}{\tau_{eff}}$ por Marcha — $G(s) = \frac{K}{\tau s + 1}$, throttle 100%",
        fontsize=13, fontweight='bold'
    )
    fig.tight_layout()
    return fig


# ==================== MAIN ====================

if __name__ == "__main__":
    output_dir = os.path.join(os.path.dirname(__file__), "..", "monografia", "figuras")
    os.makedirs(output_dir, exist_ok=True)

    charts = [
        ("zonas_eficiencia_marchas.png", plot_zones),
        ("tau_efetivo_marchas.png", plot_tau),
        ("resposta_degrau_marchas.png", plot_step_response),
        ("simulacao_completa_marchas.png", plot_full_simulation),
        ("contagiros_marchas.png", plot_tachometer),
        ("tau_detalhado_calculos.png", plot_tau_detailed),
        ("tau_evolucao_simulacao.png", plot_tau_evolution),
        ("ode_equacao_diferencial.png", plot_ode_equation),
        ("ode_campo_direcoes.png", plot_ode_per_gear),
    ]

    for filename, plot_fn in charts:
        fig = plot_fn()
        path = os.path.join(output_dir, filename)
        fig.savefig(path, dpi=150, bbox_inches='tight')
        plt.close(fig)
        print(f"  {filename}")

    print(f"\n{len(charts)} gráficos gerados em {output_dir}/")
