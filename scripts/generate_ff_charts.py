#!/usr/bin/env python3
"""
generate_ff_charts.py - Gera gráficos dos cálculos de Force Feedback

Gera visualizações PNG para a monografia dos algoritmos de force feedback
implementados no sistema de teleoperação.

Baseado no código real:
  - client/console/logic/force_feedback_calc.py (cálculos)
  - client/g923_manager.py (upload de efeitos evdev)
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Patch

# Configuração para fonte similar ao LaTeX
plt.rcParams.update({
    'font.family': 'serif',
    'font.size': 11,
    'axes.labelsize': 12,
    'axes.titlesize': 13,
    'legend.fontsize': 10,
    'xtick.labelsize': 10,
    'ytick.labelsize': 10,
    'figure.dpi': 150,
    'savefig.dpi': 300,
    'savefig.bbox': 'tight',
    'savefig.pad_inches': 0.1,
})

# Diretório de saída
OUTPUT_DIR = os.path.join(os.path.dirname(__file__), '..', 'monografia', 'figuras', 'ff_charts')
os.makedirs(OUTPUT_DIR, exist_ok=True)


# ============================================================================
# Constantes extraídas do código real
# ============================================================================

# force_feedback_calc.py
IDLE_PERIODIC_PERIOD_MS = 200   # 5Hz
IDLE_PERIODIC_MAGNITUDE = 15.0  # 15% raw
IDLE_INERTIA_PCT = 5.0
MAX_INERTIA_PCT = 80.0

# g923_manager.py
MIN_SPRING_PCT = 5.0
MIN_FRICTION_PCT = 3.0
FF_MAX_PERCENT_DEFAULT = 15  # FF_GAIN padrão
EVDEV_MAX_COEFF = 32767      # 16-bit signed max
EVDEV_MAX_RUMBLE = 65535     # 16-bit unsigned max


def generate_g_force_chart():
    """
    Gráfico 1: Cálculo das forças G frontal e lateral.
    Código: force_feedback_calc.py linhas 143-150
      g_force_frontal = accel_x / 9.81
      g_force_lateral = accel_y / 9.81
    """
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    # Força G Frontal
    ax1 = axes[0]
    accel_x = np.linspace(-20, 20, 100)
    g_frontal = accel_x / 9.81

    ax1.plot(accel_x, g_frontal, 'b-', linewidth=2)
    ax1.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    ax1.axvline(x=0, color='gray', linestyle='-', alpha=0.3)
    ax1.axhline(y=1, color='green', linestyle='--', alpha=0.5, label='1g (aceleração)')
    ax1.axhline(y=-1, color='red', linestyle='--', alpha=0.5, label='-1g (frenagem)')
    ax1.axhspan(-0.5, 0.5, alpha=0.1, color='green', label='Faixa típica RC')
    ax1.fill_between(accel_x, 0, g_frontal, where=(g_frontal > 0), alpha=0.2, color='green')
    ax1.fill_between(accel_x, 0, g_frontal, where=(g_frontal < 0), alpha=0.2, color='red')
    ax1.set_xlabel('Aceleração X (m/s²)')
    ax1.set_ylabel('Força G Frontal')
    ax1.set_title('Cálculo Força G Frontal\n$G_{frontal} = a_x / 9{,}81$')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(-20, 20)
    ax1.set_ylim(-2.5, 2.5)

    # Força G Lateral
    ax2 = axes[1]
    accel_y = np.linspace(-15, 15, 100)
    g_lateral = accel_y / 9.81

    ax2.plot(accel_y, g_lateral, 'orange', linewidth=2)
    ax2.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    ax2.axvline(x=0, color='gray', linestyle='-', alpha=0.3)
    ax2.axhline(y=1, color='blue', linestyle='--', alpha=0.5, label='1g (curva direita)')
    ax2.axhline(y=-1, color='purple', linestyle='--', alpha=0.5, label='-1g (curva esquerda)')
    ax2.axhspan(-0.3, 0.3, alpha=0.1, color='orange', label='Faixa típica RC')
    ax2.fill_between(accel_y, 0, g_lateral, where=(g_lateral > 0), alpha=0.2, color='blue')
    ax2.fill_between(accel_y, 0, g_lateral, where=(g_lateral < 0), alpha=0.2, color='purple')
    ax2.set_xlabel('Aceleração Y (m/s²)')
    ax2.set_ylabel('Força G Lateral')
    ax2.set_title('Cálculo Força G Lateral\n$G_{lateral} = a_y / 9{,}81$')
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(-15, 15)
    ax2.set_ylim(-2, 2)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_forcas_g.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_ff_constant_chart():
    """
    Gráfico 2: Componentes do FF_CONSTANT (puxão lateral).
    Código: force_feedback_calc.py linhas 221-257

    Apenas 2 componentes (centralização é FF_SPRING, não FF_CONSTANT):
      lateral_component = min(|g_lateral| * 50, 100)
      yaw_component = min(|gyro_z| / 60 * 50, 50)
      base_ff = min(lateral + yaw, 100)
      adjusted_ff = base_ff * sensitivity
      EMA filter aplicado
    """
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    # Componente 1: Força Lateral
    ax1 = axes[0]
    g_lateral = np.linspace(0, 3, 100)
    lateral_component = np.minimum(np.abs(g_lateral) * 50, 100)
    ax1.plot(g_lateral, lateral_component, 'b-', linewidth=2, label='Componente Lateral')
    ax1.axhline(y=100, color='r', linestyle='--', alpha=0.5, label='Limite (100%)')
    ax1.axvline(x=2.0, color='gray', linestyle=':', alpha=0.5, label='Saturação (2g)')
    ax1.fill_between(g_lateral, 0, lateral_component, alpha=0.2)
    ax1.set_xlabel('Força G Lateral (g)')
    ax1.set_ylabel('Componente (%)')
    ax1.set_title('Componente Lateral\n$C_L = \\min(|G_{lat}| \\times 50,\\ 100)$')
    ax1.set_xlim(0, 3)
    ax1.set_ylim(0, 110)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='lower right', fontsize=9)

    # Componente 2: Rotação Yaw
    ax2 = axes[1]
    gyro_z = np.linspace(0, 120, 100)
    yaw_component = np.minimum(np.abs(gyro_z) / 60.0 * 50, 50)
    ax2.plot(gyro_z, yaw_component, 'g-', linewidth=2, label='Componente Yaw')
    ax2.axhline(y=50, color='r', linestyle='--', alpha=0.5, label='Limite (50%)')
    ax2.axvline(x=60, color='gray', linestyle=':', alpha=0.5, label='Saturação (60°/s)')
    ax2.fill_between(gyro_z, 0, yaw_component, alpha=0.2, color='green')
    ax2.set_xlabel('Velocidade Angular Z (°/s)')
    ax2.set_ylabel('Componente (%)')
    ax2.set_title('Componente Yaw\n$C_Y = \\min(|\\omega_z| / 60 \\times 50,\\ 50)$')
    ax2.set_xlim(0, 120)
    ax2.set_ylim(0, 60)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='lower right', fontsize=9)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_componentes.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_ff_constant_scenarios_chart():
    """
    Gráfico 3: Cenários de FF_CONSTANT com 2 componentes + sensibilidade.
    Código: force_feedback_calc.py linhas 226-236
    """
    fig, ax = plt.subplots(figsize=(10, 5.5))

    # Cenários típicos: (nome, g_lateral, gyro_z)
    scenarios = [
        ('Reta\n(neutro)', 0.0, 0),
        ('Curva\nsuave', 0.3, 15),
        ('Curva\nmédia', 0.6, 30),
        ('Curva\nfechada', 1.0, 50),
        ('Curva\nextrema', 1.5, 70),
        ('Limite\naderência', 2.0, 90),
    ]

    x_labels = []
    lateral_vals = []
    yaw_vals = []
    base_vals = []
    adjusted_vals = []

    sensitivity = 0.75  # padrão 75%

    for name, g_lat, gyro in scenarios:
        x_labels.append(name)
        lat = min(abs(g_lat) * 50, 100)
        yaw = min(abs(gyro) / 60.0 * 50, 50)
        base = min(lat + yaw, 100)
        adj = base * sensitivity

        lateral_vals.append(lat)
        yaw_vals.append(yaw)
        base_vals.append(base)
        adjusted_vals.append(adj)

    x = np.arange(len(x_labels))
    width = 0.2

    ax.bar(x - 1.5*width, lateral_vals, width, label='Lateral', color='#2196F3', alpha=0.8)
    ax.bar(x - 0.5*width, yaw_vals, width, label='Yaw', color='#4CAF50', alpha=0.8)
    ax.bar(x + 0.5*width, base_vals, width, label='Base (lat+yaw)', color='#FF9800', alpha=0.8)
    ax.bar(x + 1.5*width, adjusted_vals, width, label=f'Ajustado (×{sensitivity})', color='#9C27B0', alpha=0.8)

    ax.axhline(y=100, color='red', linestyle='--', alpha=0.7, label='Limite 100%')

    ax.set_xlabel('Cenário de Condução')
    ax.set_ylabel('Intensidade FF_CONSTANT (%)')
    ax.set_title('Contribuição dos Componentes do FF\\_CONSTANT por Cenário\n'
                 f'(sensibilidade = {int(sensitivity*100)}%)')
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels)
    ax.legend(loc='upper left', fontsize=9)
    ax.set_ylim(0, 120)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_cenarios.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_ff_direction_chart():
    """
    Gráfico 4: Direção do FF_CONSTANT.
    Código: force_feedback_calc.py linhas 238-249

    Fórmula real (sem centralização!):
      lateral_dir = g_force_lateral * 10
      yaw_dir = gyro_z
      total_dir = lateral_dir + yaw_dir
      if total_dir > 1.5: "right"
      elif total_dir < -1.5: "left"
      else: "neutral"
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Painel 1: Componentes direcionais para g_lateral variável
    ax1 = axes[0]
    g_lateral = np.linspace(-2, 2, 200)
    gyro_z_fixed = 10  # rotação moderada fixa

    lateral_dir = g_lateral * 10
    yaw_dir = np.full_like(g_lateral, gyro_z_fixed)
    total_dir = lateral_dir + yaw_dir

    ax1.plot(g_lateral, lateral_dir, 'b-', linewidth=2, label='$G_{lat} \\times 10$')
    ax1.plot(g_lateral, yaw_dir, 'g--', linewidth=2, label=f'$\\omega_z$ = {gyro_z_fixed}°/s')
    ax1.plot(g_lateral, total_dir, 'purple', linewidth=3, label='Total')

    ax1.axhline(y=1.5, color='red', linestyle=':', alpha=0.7)
    ax1.axhline(y=-1.5, color='red', linestyle=':', alpha=0.7)
    ax1.fill_between(g_lateral, -1.5, 1.5, alpha=0.1, color='gray', label='Zona Neutra (±1,5)')

    ax1.set_xlabel('Força G Lateral (g)')
    ax1.set_ylabel('Valor de Direção')
    ax1.set_title('Cálculo da Direção do FF\\_CONSTANT\n'
                  '$D = G_{lat} \\times 10 + \\omega_z$')
    ax1.set_xlim(-2, 2)
    ax1.set_ylim(-25, 25)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper left', fontsize=9)

    ax1.annotate('DIREITA (0xC000)', xy=(1.2, 18), fontsize=10, ha='center',
                 color='#F44336', fontweight='bold')
    ax1.annotate('ESQUERDA (0x4000)', xy=(-1.2, -18), fontsize=10, ha='center',
                 color='#2196F3', fontweight='bold')

    # Painel 2: Mapa de direção (g_lateral vs gyro_z)
    ax2 = axes[1]
    g_range = np.linspace(-1.5, 1.5, 100)
    gyro_range = np.linspace(-60, 60, 100)
    G, W = np.meshgrid(g_range, gyro_range)

    direction_value = G * 10 + W

    direction_cat = np.where(direction_value > 1.5, 1,
                    np.where(direction_value < -1.5, -1, 0))

    ax2.contourf(G, W, direction_cat, levels=[-1.5, -0.5, 0.5, 1.5],
                 colors=['#2196F3', '#FFEB3B', '#F44336'], alpha=0.7)
    ax2.contour(G, W, direction_value, levels=[-1.5, 1.5], colors='black', linewidths=2)

    ax2.set_xlabel('Força G Lateral (g)')
    ax2.set_ylabel('Velocidade Angular Z (°/s)')
    ax2.set_title('Mapa de Direção do FF\\_CONSTANT\n'
                  '$D = G_{lat} \\times 10 + \\omega_z$')

    legend_elements = [
        Patch(facecolor='#2196F3', alpha=0.7, label='ESQUERDA (D < -1,5)'),
        Patch(facecolor='#FFEB3B', alpha=0.7, label='NEUTRO (-1,5 ≤ D ≤ 1,5)'),
        Patch(facecolor='#F44336', alpha=0.7, label='DIREITA (D > 1,5)'),
    ]
    ax2.legend(handles=legend_elements, loc='upper right', fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_direcao.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_ff_condition_effects_chart():
    """
    Gráfico 5: Efeitos condicionais (sliders → coeficientes evdev).
    Código: g923_manager.py linhas 462-512

    Mapeamento: slider % → coeficiente 16-bit (0-32767)
      coeff = int(pct / 100.0 * 32767)
    """
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))

    pct = np.linspace(0, 100, 100)
    coeff = pct / 100.0 * EVDEV_MAX_COEFF

    # FF_SPRING (sensibilidade, mín 5%)
    ax1 = axes[0, 0]
    spring_pct = np.maximum(pct, MIN_SPRING_PCT)
    spring_coeff = spring_pct / 100.0 * EVDEV_MAX_COEFF
    ax1.plot(pct, spring_coeff, 'b-', linewidth=2)
    ax1.axvline(x=75, color='red', linestyle='--', alpha=0.7, label='Padrão (75%)')
    ax1.axhline(y=MIN_SPRING_PCT / 100 * EVDEV_MAX_COEFF, color='orange', linestyle=':',
                alpha=0.7, label=f'Mín. {int(MIN_SPRING_PCT)}%')
    ax1.fill_between(pct, 0, spring_coeff, alpha=0.15)
    ax1.set_xlabel('Slider Sensibilidade (%)')
    ax1.set_ylabel('Coeficiente evdev')
    ax1.set_title('FF\\_SPRING (centralização)\n'
                  f'$coeff = \\max(slider, {int(MIN_SPRING_PCT)}\\%) \\times 32767$')
    ax1.set_xlim(0, 100)
    ax1.set_ylim(0, 35000)
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=9)

    # FF_FRICTION (fricção, mín 3%)
    ax2 = axes[0, 1]
    friction_pct = np.maximum(pct, MIN_FRICTION_PCT)
    friction_coeff = friction_pct / 100.0 * EVDEV_MAX_COEFF
    ax2.plot(pct, friction_coeff, 'orange', linewidth=2)
    ax2.axvline(x=30, color='red', linestyle='--', alpha=0.7, label='Padrão (30%)')
    ax2.axhline(y=MIN_FRICTION_PCT / 100 * EVDEV_MAX_COEFF, color='orange', linestyle=':',
                alpha=0.7, label=f'Mín. {int(MIN_FRICTION_PCT)}%')
    ax2.fill_between(pct, 0, friction_coeff, alpha=0.15, color='orange')
    ax2.set_xlabel('Slider Fricção (%)')
    ax2.set_ylabel('Coeficiente evdev')
    ax2.set_title('FF\\_FRICTION (grip do pneu)\n'
                  f'$coeff = \\max(slider, {int(MIN_FRICTION_PCT)}\\%) \\times 32767$')
    ax2.set_xlim(0, 100)
    ax2.set_ylim(0, 35000)
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=9)

    # FF_DAMPER (damping, sem mínimo)
    ax3 = axes[1, 0]
    ax3.plot(pct, coeff, 'g-', linewidth=2)
    ax3.axvline(x=50, color='red', linestyle='--', alpha=0.7, label='Padrão (50%)')
    ax3.fill_between(pct, 0, coeff, alpha=0.15, color='green')
    ax3.set_xlabel('Slider Damping (%)')
    ax3.set_ylabel('Coeficiente evdev')
    ax3.set_title('FF\\_DAMPER (amortecimento)\n'
                  '$coeff = slider \\times 32767$')
    ax3.set_xlim(0, 100)
    ax3.set_ylim(0, 35000)
    ax3.grid(True, alpha=0.3)
    ax3.legend(fontsize=9)

    # FF_GAIN (força máxima, escala global)
    ax4 = axes[1, 1]
    gain = pct / 100.0 * 0xFFFF
    ax4.plot(pct, gain, 'purple', linewidth=2)
    ax4.axvline(x=FF_MAX_PERCENT_DEFAULT, color='red', linestyle='--', alpha=0.7,
                label=f'Padrão ({FF_MAX_PERCENT_DEFAULT}%)')
    ax4.axvline(x=25, color='orange', linestyle=':', alpha=0.7, label='Alerta (>25% trava)')
    ax4.fill_between(pct, 0, gain, alpha=0.15, color='purple')
    ax4.axvspan(25, 100, alpha=0.05, color='red')
    ax4.set_xlabel('Slider Força Máxima (%)')
    ax4.set_ylabel('FF\\_GAIN (0-65535)')
    ax4.set_title('FF\\_GAIN (limite global)\n'
                  '$gain = slider \\times 65535$')
    ax4.set_xlim(0, 100)
    ax4.set_ylim(0, 70000)
    ax4.grid(True, alpha=0.3)
    ax4.legend(fontsize=9)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_parametros.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_ff_filter_chart():
    """
    Gráfico 6: Efeito do filtro EMA no FF_CONSTANT.
    Código: force_feedback_calc.py linhas 231-234

      adjusted_ff = adjusted_ff * (1 - filter_strength) + prev * filter_strength
    """
    fig, ax = plt.subplots(figsize=(8, 4.5))

    t = np.arange(60)
    # Simula step response: força sobe de 0 para 80% no instante 10
    signal = np.zeros(60)
    signal[10:] = 80

    filter_values = [0.0, 0.2, 0.4, 0.6, 0.8]
    colors = plt.cm.plasma(np.linspace(0.2, 0.8, len(filter_values)))

    for filt, color in zip(filter_values, colors):
        filtered = np.zeros(60)
        for i in range(1, 60):
            filtered[i] = signal[i] * (1.0 - filt) + filtered[i-1] * filt
        ax.plot(t, filtered, '-', linewidth=2, color=color, label=f'Filtro = {int(filt*100)}%')

    ax.axvline(x=10, color='gray', linestyle=':', alpha=0.5, label='Início do evento')
    ax.plot(t, signal, 'k:', alpha=0.3, linewidth=1, label='Sinal original')
    ax.axvline(x=10, color='gray', linestyle=':', alpha=0.5)
    ax.set_xlabel('Amostras (pacotes BMI160)')
    ax.set_ylabel('Intensidade FF\\_CONSTANT (%)')
    ax.set_title('Suavização EMA do FF\\_CONSTANT (Step Response)\n'
                 '$FF_t = FF_{in} \\times (1 - f) + FF_{t-1} \\times f$')
    ax.set_xlim(0, 60)
    ax.set_ylim(0, 90)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=9)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_filtro_ema.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_ff_rumble_chart():
    """
    Gráfico 7: Componentes do FF_RUMBLE e blending dos 2 motores.
    Código: force_feedback_calc.py linhas 259-332
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Painel 1: Componentes individuais vs variável principal
    ax1 = axes[0]
    x = np.linspace(0, 100, 100)

    # Componentes que variam com throttle/brake/g_lat
    engine_vib = x / 100 * 60  # throttle → 0-60%
    bump_vib = np.minimum(np.abs(x / 100 * 2 - 1) / 1.0 * 400, 100)  # accel_z desvio
    frontal_impact = np.minimum(x / 100 * 2 * 200, 100)  # |g_frontal| → impacto
    brake_rumble = np.where(x > 10, np.minimum(x / 100 * 70, 70), 0)  # brake → rumble
    turn_vib = np.minimum(x / 100 * 1.5 * 150, 80)  # |g_lateral| em curva

    ax1.plot(x, engine_vib, 'b-', linewidth=2, label='Motor (throttle×0.6)')
    ax1.plot(x, brake_rumble, 'r-', linewidth=2, label='Frenagem (brake×0.7)')
    ax1.plot(x, turn_vib, 'g-', linewidth=2, label='Curva (G_lat×150)')
    ax1.plot(x, np.minimum(x * 0.8, 80), 'orange', linewidth=2, label='Jerk (×8, máx 80)')
    roughness_x = np.linspace(0, 2, 100)
    roughness_vib = np.minimum(roughness_x * 80, 70)

    ax1.set_xlabel('Variável de Entrada (%)')
    ax1.set_ylabel('Componente de Vibração (%)')
    ax1.set_title('Componentes do FF\\_RUMBLE\n(8 fontes sensoriais)')
    ax1.set_xlim(0, 100)
    ax1.set_ylim(0, 110)
    ax1.grid(True, alpha=0.3)
    ax1.legend(fontsize=8, loc='upper left')

    # Painel 2: Blending strong vs weak motor por cenário
    ax2 = axes[1]
    scenarios = ['Idle', 'Acelerando\n50%', 'Freando\n80%', 'Curva\n0.5g', 'Buraco\n(jerk)', 'Pista\nrugosa']

    # Valores calculados manualmente seguindo o código real
    strong_vals = [
        0,   # idle
        min(30*0.5 + 0, 100),  # acelerando 50%: engine*0.5
        min(0 + 56*0.5, 100),  # freando 80%: brake_rumble*0.5
        min(0 + 75*0.3 + 0, 100),  # curva 0.5g: frontal*0.3 + turn*0.3
        min(0 + 60*0.2 + 60*0.2, 100),  # buraco: jerk_impact + jerk_bump
        min(0 + 0 + 0, 100),  # rugosa: forte pouco afetado
    ]
    weak_vals = [
        0,   # idle
        min(30*0.7, 100),  # acelerando: engine*0.7
        min(0 + 56*0.3, 100),  # freando: brake_rumble*0.3
        min(0 + 75*0.4, 100),  # curva: turn*0.4
        0,  # buraco: fraco pouco afetado
        min(56, 100),  # rugosa: roughness * 80
    ]

    x_pos = np.arange(len(scenarios))
    width = 0.35
    ax2.bar(x_pos - width/2, strong_vals, width, label='Motor Forte', color='#F44336', alpha=0.8)
    ax2.bar(x_pos + width/2, weak_vals, width, label='Motor Fraco', color='#FF9800', alpha=0.8)

    ax2.set_xlabel('Cenário')
    ax2.set_ylabel('Intensidade (%)')
    ax2.set_title('Blending dos Motores de Vibração\n'
                  '(forte = impactos, fraco = textura)')
    ax2.set_xticks(x_pos)
    ax2.set_xticklabels(scenarios, fontsize=9)
    ax2.set_ylim(0, 60)
    ax2.grid(True, alpha=0.3, axis='y')
    ax2.legend(fontsize=9)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_rumble.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_ff_periodic_inertia_chart():
    """
    Gráfico 8: FF_PERIODIC (RPM do motor) e FF_INERTIA (peso do volante).
    Código: force_feedback_calc.py linhas 334-373
    """
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.5))

    # FF_PERIODIC: frequência e magnitude vs throttle
    ax1 = axes[0]
    throttle = np.linspace(0, 100, 100)

    # period_ms = 200 - (throttle/100 * 120) → 200ms a 80ms
    period_ms = np.where(throttle > 5, 200 - (throttle / 100 * 120), IDLE_PERIODIC_PERIOD_MS)
    freq_hz = 1000.0 / period_ms

    # magnitude = min(15 + throttle * 0.75, 90)
    magnitude = np.where(throttle > 5, np.minimum(15 + throttle * 0.75, 90), IDLE_PERIODIC_MAGNITUDE)

    ax1_twin = ax1.twinx()
    line1, = ax1.plot(throttle, freq_hz, 'b-', linewidth=2, label='Frequência')
    line2, = ax1_twin.plot(throttle, magnitude, 'r-', linewidth=2, label='Magnitude')

    ax1.set_xlabel('Posição do Acelerador (%)')
    ax1.set_ylabel('Frequência (Hz)', color='b')
    ax1_twin.set_ylabel('Magnitude (%)', color='r')
    ax1.set_title('FF\\_PERIODIC (vibração do motor)\n'
                  '$f = 1000 / (200 - throttle \\times 1{,}2)$')
    ax1.set_xlim(0, 100)
    ax1.set_ylim(0, 15)
    ax1_twin.set_ylim(0, 100)
    ax1.tick_params(axis='y', labelcolor='b')
    ax1_twin.tick_params(axis='y', labelcolor='r')
    ax1.grid(True, alpha=0.3)

    # Anotações
    ax1.annotate(f'Idle: {1000/IDLE_PERIODIC_PERIOD_MS:.0f}Hz, {IDLE_PERIODIC_MAGNITUDE:.0f}%',
                xy=(2, 1000/IDLE_PERIODIC_PERIOD_MS), fontsize=9, color='gray')
    ax1.annotate('Full: 12,5Hz, 90%', xy=(85, 12.5), fontsize=9, color='gray')

    lines = [line1, line2]
    labels = [l.get_label() for l in lines]
    ax1.legend(lines, labels, loc='center right', fontsize=9)

    # FF_INERTIA: coeficiente vs velocidade e throttle
    ax2 = axes[1]
    speed = np.linspace(0, 100, 100)

    # inertia_speed = min(|speed| / 100 * 50, 50)
    inertia_speed = np.minimum(np.abs(speed) / 100.0 * 50, 50)

    # Para diferentes throttle
    throttle_vals = [0, 25, 50, 75, 100]
    colors = plt.cm.viridis(np.linspace(0, 1, len(throttle_vals)))

    for thr, color in zip(throttle_vals, colors):
        inertia_throttle = thr / 100.0 * 25
        inertia_raw = np.maximum(IDLE_INERTIA_PCT, np.minimum(inertia_speed + inertia_throttle, MAX_INERTIA_PCT))
        ax2.plot(speed, inertia_raw, '-', linewidth=2, color=color, label=f'Throttle = {thr}%')

    ax2.axhline(y=IDLE_INERTIA_PCT, color='gray', linestyle=':', alpha=0.5, label=f'Mín. ({IDLE_INERTIA_PCT}%)')
    ax2.axhline(y=MAX_INERTIA_PCT, color='red', linestyle=':', alpha=0.5, label=f'Máx. ({MAX_INERTIA_PCT}%)')
    ax2.set_xlabel('Velocidade Estimada (km/h)')
    ax2.set_ylabel('Coeficiente FF\\_INERTIA (%)')
    ax2.set_title('FF\\_INERTIA (peso do volante)\n'
                  '$I = \\max(5,\\ \\min(v/100 \\times 50 + thr/100 \\times 25,\\ 80))$')
    ax2.set_xlim(0, 100)
    ax2.set_ylim(0, 90)
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=8, loc='upper left')

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_periodic_inertia.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_velocity_integration_chart():
    """
    Gráfico 9: Cálculo de velocidade por integração (sem mudanças).
    Código: client/console/logic/velocity_calculator.py
    """
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))

    ACCEL_THRESHOLD = 0.3
    VELOCITY_DECAY_FACTOR = 0.98
    MIN_VELOCITY_THRESHOLD = 0.1

    dt = 0.01  # 100Hz
    t = np.arange(0, 5, dt)

    accel = np.zeros_like(t)
    accel[(t >= 0.5) & (t < 1.5)] = 2.0
    accel[(t >= 3.0) & (t < 3.5)] = -1.5

    np.random.seed(42)
    accel_noisy = accel + np.random.normal(0, 0.2, len(t))
    accel_filtered = np.where(np.abs(accel_noisy) < ACCEL_THRESHOLD, 0, accel_noisy)

    velocity = np.zeros_like(t)
    for i in range(1, len(t)):
        velocity[i] = velocity[i-1] + accel_filtered[i] * dt
        velocity[i] *= VELOCITY_DECAY_FACTOR
        if abs(velocity[i]) < MIN_VELOCITY_THRESHOLD:
            velocity[i] = 0

    # Gráfico 1: Aceleração original vs filtrada
    ax1 = axes[0, 0]
    ax1.plot(t, accel_noisy, 'b-', alpha=0.5, linewidth=1, label='Aceleração com ruído')
    ax1.plot(t, accel_filtered, 'r-', linewidth=2, label='Aceleração filtrada')
    ax1.axhline(y=ACCEL_THRESHOLD, color='gray', linestyle='--', alpha=0.5)
    ax1.axhline(y=-ACCEL_THRESHOLD, color='gray', linestyle='--', alpha=0.5)
    ax1.fill_between(t, -ACCEL_THRESHOLD, ACCEL_THRESHOLD, alpha=0.1, color='gray',
                     label=f'Zona morta (±{ACCEL_THRESHOLD} m/s²)')
    ax1.set_xlabel('Tempo (s)')
    ax1.set_ylabel('Aceleração (m/s²)')
    ax1.set_title('Filtragem de Ruído da Aceleração')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(0, 5)

    # Gráfico 2: Integração para velocidade
    ax2 = axes[0, 1]
    velocity_no_decay = np.zeros_like(t)
    for i in range(1, len(t)):
        velocity_no_decay[i] = velocity_no_decay[i-1] + accel_filtered[i] * dt

    ax2.plot(t, velocity_no_decay, 'b--', linewidth=2, alpha=0.7, label='Sem decaimento')
    ax2.plot(t, velocity, 'r-', linewidth=2, label=f'Com decaimento ({VELOCITY_DECAY_FACTOR})')
    ax2.set_xlabel('Tempo (s)')
    ax2.set_ylabel('Velocidade (m/s)')
    ax2.set_title('Integração: $v(t) = v(t-1) + a \\times \\Delta t$')
    ax2.legend()
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(0, 5)

    # Gráfico 3: Efeito do fator de decaimento
    ax3 = axes[1, 0]
    decay_factors = [1.0, 0.995, 0.98, 0.95, 0.90]
    colors = plt.cm.viridis(np.linspace(0, 1, len(decay_factors)))

    for decay, color in zip(decay_factors, colors):
        v = np.zeros_like(t)
        for i in range(1, len(t)):
            v[i] = v[i-1] + accel_filtered[i] * dt
            v[i] *= decay
        ax3.plot(t, v, '-', linewidth=2, color=color, label=f'Decay = {decay}')

    ax3.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    ax3.set_xlabel('Tempo (s)')
    ax3.set_ylabel('Velocidade (m/s)')
    ax3.set_title('Efeito do Fator de Decaimento\n$v_{final} = v \\times f_{decay}$')
    ax3.legend(fontsize=9)
    ax3.grid(True, alpha=0.3)
    ax3.set_xlim(0, 5)

    # Gráfico 4: Velocidade final em km/h
    ax4 = axes[1, 1]
    velocity_kmh = velocity * 3.6
    velocity_no_decay_kmh = velocity_no_decay * 3.6

    ax4.plot(t, velocity_no_decay_kmh, 'b--', linewidth=2, alpha=0.7, label='Sem decaimento')
    ax4.plot(t, velocity_kmh, 'r-', linewidth=2, label='Com decaimento')
    ax4.axhline(y=MIN_VELOCITY_THRESHOLD * 3.6, color='gray', linestyle=':', alpha=0.5)
    ax4.set_xlabel('Tempo (s)')
    ax4.set_ylabel('Velocidade (km/h)')
    ax4.set_title('Velocidade Estimada Final\n$v_{km/h} = v_{m/s} \\times 3{,}6$')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim(0, 5)
    ax4.set_ylim(bottom=0)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_velocidade.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_ff_pipeline_chart():
    """
    Gráfico 10: Pipeline completo de force feedback.
    Corrigido: sem ESP32/BTS7960, o FF vai via evdev para o G923.
    """
    fig, ax = plt.subplots(figsize=(14, 7))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 7)
    ax.axis('off')

    colors = {
        'sensor': '#4CAF50',
        'network': '#00BCD4',
        'calc': '#2196F3',
        'param': '#FF9800',
        'evdev': '#9C27B0',
        'hardware': '#F44336'
    }

    def draw_box(x, y, w, h, text, color, fontsize=9):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                             facecolor=color, edgecolor='black', linewidth=2, alpha=0.8)
        ax.add_patch(box)
        ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=fontsize,
               fontweight='bold', wrap=True)

    def draw_arrow(x1, y1, x2, y2, style='->', color='black'):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                   arrowprops=dict(arrowstyle=style, lw=2, color=color))

    # Nível 1: Sensores no veículo (Raspberry Pi)
    draw_box(0.3, 5.5, 2.5, 1, 'BMI160 (RPi)\naccel_x, accel_y,\naccel_z, gyro_z', colors['sensor'])
    draw_box(3.3, 5.5, 2, 1, 'G923\nVolante/Pedais', colors['sensor'])

    # Nível 2: Rede
    draw_box(0.3, 4.0, 2.5, 0.9, 'UDP 9997\n100Hz sensores', colors['network'])

    # Nível 3: Calculadora FF (cliente)
    draw_box(0.3, 2.5, 2.8, 1, 'Forças G\n$G = a / 9{,}81$', colors['calc'])
    draw_box(3.5, 2.5, 3, 1, 'FF Calculator\nFF_CONSTANT\nFF_RUMBLE', colors['calc'])

    # Nível 3b: Efeitos dinâmicos adicionais
    draw_box(7.0, 4.0, 2.5, 0.9, 'Sliders UI\nSens./Fric./Damp.\nFiltro/Max Force', colors['param'])

    # Nível 4: Efeitos evdev
    draw_box(7.0, 2.5, 2.5, 1, 'evdev ioctl\n8 efeitos\n(upload_effect)', colors['evdev'])

    # Efeitos individuais
    draw_box(10.0, 5.0, 3.5, 0.7, 'Condicionais (~1kHz kernel)\nSPRING  DAMPER  FRICTION  INERTIA', colors['evdev'])
    draw_box(10.0, 4.0, 3.5, 0.7, 'Força + Vibração (60Hz SW)\nCONSTANT×2  RUMBLE  PERIODIC', colors['evdev'])

    # Nível 5: Hardware G923
    draw_box(10.5, 2.5, 2.5, 1, 'G923 Motor\nFF TRUEFORCE\n(volante)', colors['hardware'])

    # Setas
    draw_arrow(1.55, 5.5, 1.55, 4.9)    # BMI160 → UDP
    draw_arrow(1.55, 4.0, 1.55, 3.5)     # UDP → Forças G
    draw_arrow(3.1, 3.0, 3.5, 3.0)       # Forças G → FF Calc
    draw_arrow(4.3, 5.5, 4.3, 3.5)       # G923 input → FF Calc (steering etc)
    draw_arrow(6.5, 3.0, 7.0, 3.0)       # FF Calc → evdev
    draw_arrow(8.25, 4.0, 8.25, 3.5)     # Sliders → evdev
    draw_arrow(9.5, 3.3, 10.0, 5.2)      # evdev → condicionais
    draw_arrow(9.5, 2.9, 10.0, 4.3)      # evdev → força+vibração
    draw_arrow(11.75, 4.0, 11.75, 3.5)   # efeitos → motor

    # Título
    ax.text(7, 6.8, 'Pipeline de Force Feedback', ha='center', va='center',
           fontsize=14, fontweight='bold')

    # Separador RPi / Cliente
    ax.axhline(y=4.7, xmin=0.02, xmax=0.42, color='gray', linestyle='--', alpha=0.4)
    ax.text(0.3, 4.75, 'Raspberry Pi', fontsize=8, color='gray', style='italic')
    ax.text(0.3, 2.2, 'Cliente PC', fontsize=8, color='gray', style='italic')

    # Legenda
    legend_items = [
        (colors['sensor'], 'Sensores/Input'),
        (colors['network'], 'Rede UDP'),
        (colors['calc'], 'Cálculos'),
        (colors['param'], 'Parâmetros'),
        (colors['evdev'], 'evdev/Efeitos'),
        (colors['hardware'], 'Hardware G923'),
    ]
    for i, (color, label) in enumerate(legend_items):
        rect = FancyBboxPatch((0.2 + i*2.2, 0.2), 0.4, 0.4, boxstyle="round,pad=0.02",
                             facecolor=color, edgecolor='black', alpha=0.8)
        ax.add_patch(rect)
        ax.text(0.7 + i*2.2, 0.4, label, fontsize=8, va='center')

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_pipeline.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def main():
    """Gera todos os gráficos de force feedback."""
    print(f"Gerando gráficos em: {OUTPUT_DIR}\n")

    generate_g_force_chart()                  # ff_forcas_g.png
    generate_ff_constant_chart()              # ff_componentes.png
    generate_ff_constant_scenarios_chart()     # ff_cenarios.png
    generate_ff_direction_chart()              # ff_direcao.png
    generate_ff_condition_effects_chart()      # ff_parametros.png
    generate_ff_filter_chart()                 # ff_filtro_ema.png (NOVO)
    generate_ff_rumble_chart()                 # ff_rumble.png (NOVO)
    generate_ff_periodic_inertia_chart()       # ff_periodic_inertia.png (NOVO)
    generate_velocity_integration_chart()      # ff_velocidade.png
    generate_ff_pipeline_chart()               # ff_pipeline.png

    print(f"\nTodos os gráficos gerados com sucesso!")
    print(f"  Diretório: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
