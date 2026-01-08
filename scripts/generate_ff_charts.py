#!/usr/bin/env python3
"""
generate_ff_charts.py - Gera gráficos dos cálculos de Force Feedback

Gera visualizações PNG para a monografia dos algoritmos de force feedback
implementados no sistema de teleoperação.
"""

import os
import numpy as np
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch
import matplotlib.patches as mpatches

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


def generate_ff_components_chart():
    """
    Gera gráfico dos três componentes de force feedback:
    - Componente lateral (curvas)
    - Componente yaw (rotação)
    - Componente de centralização (mola)
    """
    fig, axes = plt.subplots(1, 3, figsize=(12, 4))

    # Componente 1: Força Lateral
    ax1 = axes[0]
    g_lateral = np.linspace(0, 3, 100)
    lateral_component = np.minimum(np.abs(g_lateral) * 50, 100)
    ax1.plot(g_lateral, lateral_component, 'b-', linewidth=2, label='Componente Lateral')
    ax1.axhline(y=100, color='r', linestyle='--', alpha=0.5, label='Limite máximo')
    ax1.axvline(x=2.0, color='gray', linestyle=':', alpha=0.5)
    ax1.fill_between(g_lateral, 0, lateral_component, alpha=0.2)
    ax1.set_xlabel('Força G Lateral (g)')
    ax1.set_ylabel('Componente (%)')
    ax1.set_title('Componente Lateral\n$C_L = \\min(|G_{lat}| \\times 50, 100)$')
    ax1.set_xlim(0, 3)
    ax1.set_ylim(0, 110)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='lower right')

    # Componente 2: Rotação Yaw
    ax2 = axes[1]
    gyro_z = np.linspace(0, 120, 100)
    yaw_component = np.minimum(np.abs(gyro_z) / 60.0 * 50, 50)
    ax2.plot(gyro_z, yaw_component, 'g-', linewidth=2, label='Componente Yaw')
    ax2.axhline(y=50, color='r', linestyle='--', alpha=0.5, label='Limite máximo')
    ax2.axvline(x=60, color='gray', linestyle=':', alpha=0.5)
    ax2.fill_between(gyro_z, 0, yaw_component, alpha=0.2, color='green')
    ax2.set_xlabel('Velocidade Angular Z (°/s)')
    ax2.set_ylabel('Componente (%)')
    ax2.set_title('Componente Yaw\n$C_Y = \\min(|\\omega_z| / 60 \\times 50, 50)$')
    ax2.set_xlim(0, 120)
    ax2.set_ylim(0, 60)
    ax2.grid(True, alpha=0.3)
    ax2.legend(loc='lower right')

    # Componente 3: Centralização (Mola)
    ax3 = axes[2]
    steering_angle = np.linspace(0, 100, 100)
    centering_component = (np.abs(steering_angle) / 100.0) * 40
    ax3.plot(steering_angle, centering_component, 'orange', linewidth=2, label='Componente Centralização')
    ax3.axhline(y=40, color='r', linestyle='--', alpha=0.5, label='Limite máximo')
    ax3.fill_between(steering_angle, 0, centering_component, alpha=0.2, color='orange')
    ax3.set_xlabel('Ângulo de Direção (%)')
    ax3.set_ylabel('Componente (%)')
    ax3.set_title('Componente Centralização\n$C_C = |\\theta| / 100 \\times 40$')
    ax3.set_xlim(0, 100)
    ax3.set_ylim(0, 50)
    ax3.grid(True, alpha=0.3)
    ax3.legend(loc='lower right')

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_componentes.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_ff_combined_chart():
    """
    Gera gráfico mostrando a combinação dos três componentes em cenários típicos.
    """
    fig, ax = plt.subplots(figsize=(10, 6))

    # Cenários típicos de condução
    scenarios = [
        ('Reta (neutro)', 0.0, 0, 0),
        ('Curva suave', 0.3, 15, 20),
        ('Curva média', 0.6, 30, 40),
        ('Curva fechada', 1.0, 50, 60),
        ('Curva extrema', 1.5, 70, 80),
        ('Limite aderência', 2.0, 90, 100),
    ]

    x_labels = []
    lateral_vals = []
    yaw_vals = []
    centering_vals = []
    total_vals = []

    for name, g_lat, gyro, steering in scenarios:
        x_labels.append(name)
        lat = min(abs(g_lat) * 50, 100)
        yaw = min(abs(gyro) / 60.0 * 50, 50)
        cent = abs(steering) / 100.0 * 40
        total = min(lat + yaw + cent, 100)

        lateral_vals.append(lat)
        yaw_vals.append(yaw)
        centering_vals.append(cent)
        total_vals.append(total)

    x = np.arange(len(x_labels))
    width = 0.2

    bars1 = ax.bar(x - 1.5*width, lateral_vals, width, label='Lateral', color='#2196F3', alpha=0.8)
    bars2 = ax.bar(x - 0.5*width, yaw_vals, width, label='Yaw', color='#4CAF50', alpha=0.8)
    bars3 = ax.bar(x + 0.5*width, centering_vals, width, label='Centralização', color='#FF9800', alpha=0.8)
    bars4 = ax.bar(x + 1.5*width, total_vals, width, label='Total (limitado)', color='#9C27B0', alpha=0.8)

    ax.axhline(y=100, color='red', linestyle='--', alpha=0.7, label='Limite 100%')

    ax.set_xlabel('Cenário de Condução')
    ax.set_ylabel('Intensidade Force Feedback (%)')
    ax.set_title('Contribuição dos Componentes por Cenário')
    ax.set_xticks(x)
    ax.set_xticklabels(x_labels, rotation=15, ha='right')
    ax.legend(loc='upper left')
    ax.set_ylim(0, 120)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_cenarios.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_ff_parameters_chart():
    """
    Gera gráfico mostrando o efeito dos parâmetros ajustáveis:
    - Sensibilidade
    - Fricção
    - Filtro (suavização)
    - Damping
    """
    fig, axes = plt.subplots(2, 2, figsize=(10, 8))

    base_ff = 60  # Força base de 60%

    # Sensibilidade
    ax1 = axes[0, 0]
    sensitivity = np.linspace(0, 100, 100)
    adjusted = base_ff * (sensitivity / 100.0)
    ax1.plot(sensitivity, adjusted, 'b-', linewidth=2)
    ax1.axvline(x=75, color='red', linestyle='--', alpha=0.7, label='Padrão (75%)')
    ax1.fill_between(sensitivity, 0, adjusted, alpha=0.2)
    ax1.set_xlabel('Sensibilidade (%)')
    ax1.set_ylabel('FF Ajustado (%)')
    ax1.set_title('Efeito da Sensibilidade\n$FF_{adj} = FF_{base} \\times S$')
    ax1.set_xlim(0, 100)
    ax1.set_ylim(0, 70)
    ax1.grid(True, alpha=0.3)
    ax1.legend()

    # Fricção
    ax2 = axes[0, 1]
    gyro_z_values = [10, 30, 50, 70, 90]
    friction_range = np.linspace(0, 100, 100)
    colors = plt.cm.viridis(np.linspace(0, 1, len(gyro_z_values)))

    for gyro, color in zip(gyro_z_values, colors):
        friction_force = np.minimum(abs(gyro) / 100.0, 1.0) * (friction_range / 100.0) * 30
        ax2.plot(friction_range, friction_force, '-', linewidth=2, color=color,
                 label=f'ω_z = {gyro}°/s')

    ax2.axvline(x=30, color='red', linestyle='--', alpha=0.7, label='Padrão (30%)')
    ax2.set_xlabel('Fricção (%)')
    ax2.set_ylabel('Força de Fricção (%)')
    ax2.set_title('Efeito da Fricção por Rotação\n$F_f = \\min(|\\omega_z|/100, 1) \\times f \\times 30$')
    ax2.set_xlim(0, 100)
    ax2.set_ylim(0, 35)
    ax2.grid(True, alpha=0.3)
    ax2.legend(fontsize=8, loc='upper left')

    # Filtro (Suavização Exponencial)
    ax3 = axes[1, 0]
    t = np.arange(50)
    signal = np.zeros(50)
    signal[10:] = 80  # Step response

    filter_values = [0.0, 0.2, 0.4, 0.6, 0.8]
    colors = plt.cm.plasma(np.linspace(0.2, 0.8, len(filter_values)))

    for filt, color in zip(filter_values, colors):
        filtered = np.zeros(50)
        for i in range(1, 50):
            filtered[i] = signal[i] * (1.0 - filt) + filtered[i-1] * filt
        ax3.plot(t, filtered, '-', linewidth=2, color=color, label=f'Filtro = {int(filt*100)}%')

    ax3.axvline(x=10, color='gray', linestyle=':', alpha=0.5)
    ax3.set_xlabel('Amostras')
    ax3.set_ylabel('FF Filtrado (%)')
    ax3.set_title('Suavização Exponencial (Step Response)\n$FF_t = FF_{in} \\times (1-f) + FF_{t-1} \\times f$')
    ax3.set_xlim(0, 50)
    ax3.set_ylim(0, 90)
    ax3.grid(True, alpha=0.3)
    ax3.legend(fontsize=8)

    # Damping (Média Móvel)
    ax4 = axes[1, 1]
    np.random.seed(42)
    noisy_signal = 50 + 20 * np.sin(t * 0.3) + np.random.normal(0, 5, 50)

    damping_values = [0.0, 0.25, 0.5, 0.75]
    colors = plt.cm.cool(np.linspace(0.2, 0.8, len(damping_values)))

    for damp, color in zip(damping_values, colors):
        damped = np.zeros(50)
        damped[0] = noisy_signal[0]
        for i in range(1, 50):
            damped[i] = noisy_signal[i] * (1.0 - damp) + damped[i-1] * damp
        ax4.plot(t, damped, '-', linewidth=2, color=color, label=f'Damping = {int(damp*100)}%')

    ax4.plot(t, noisy_signal, 'k:', alpha=0.3, label='Sinal original')
    ax4.set_xlabel('Amostras')
    ax4.set_ylabel('FF com Damping (%)')
    ax4.set_title('Efeito do Damping\n$FF_t = FF_{in} \\times (1-d) + FF_{t-1} \\times d$')
    ax4.set_xlim(0, 50)
    ax4.set_ylim(20, 80)
    ax4.grid(True, alpha=0.3)
    ax4.legend(fontsize=8)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_parametros.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_direction_calculation_chart():
    """
    Gera gráfico mostrando o cálculo da direção do force feedback.
    """
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))

    # Gráfico 1: Contribuição de cada componente para direção
    ax1 = axes[0]

    steering = np.linspace(-100, 100, 200)
    g_lateral = 0.3  # Curva para direita
    gyro_z = 15  # Rotação positiva

    centering_dir = -steering
    lateral_dir = np.full_like(steering, g_lateral * 10)
    yaw_dir = np.full_like(steering, gyro_z)
    total_dir = centering_dir + lateral_dir + yaw_dir

    ax1.plot(steering, centering_dir, 'b-', linewidth=2, label='Centralização (-θ)')
    ax1.plot(steering, lateral_dir, 'g--', linewidth=2, label=f'Lateral (G×10 = {g_lateral*10:.1f})')
    ax1.plot(steering, yaw_dir, 'orange', linestyle='--', linewidth=2, label=f'Yaw (ω = {gyro_z})')
    ax1.plot(steering, total_dir, 'purple', linewidth=3, label='Total')

    ax1.axhline(y=5, color='red', linestyle=':', alpha=0.7)
    ax1.axhline(y=-5, color='red', linestyle=':', alpha=0.7)
    ax1.fill_between(steering, -5, 5, alpha=0.1, color='gray', label='Zona Neutra')

    ax1.set_xlabel('Ângulo de Direção (%)')
    ax1.set_ylabel('Valor de Direção')
    ax1.set_title('Cálculo da Direção do Force Feedback\n$D = -\\theta + G_{lat} \\times 10 + \\omega_z$')
    ax1.set_xlim(-100, 100)
    ax1.set_ylim(-120, 120)
    ax1.grid(True, alpha=0.3)
    ax1.legend(loc='upper right', fontsize=9)

    # Adiciona anotações de zona
    ax1.annotate('DIREITA', xy=(0, 60), fontsize=10, ha='center', color='green')
    ax1.annotate('ESQUERDA', xy=(0, -60), fontsize=10, ha='center', color='blue')
    ax1.annotate('NEUTRO', xy=(0, 0), fontsize=9, ha='center', color='gray')

    # Gráfico 2: Mapa de direção para diferentes combinações
    ax2 = axes[1]

    steering_range = np.linspace(-100, 100, 50)
    g_lateral_range = np.linspace(-1.5, 1.5, 50)

    S, G = np.meshgrid(steering_range, g_lateral_range)
    gyro_z = 0  # Sem rotação para simplificar

    direction_value = -S + G * 10 + gyro_z

    # Categoriza: >5 = direita (1), <-5 = esquerda (-1), neutro (0)
    direction_cat = np.where(direction_value > 5, 1, np.where(direction_value < -5, -1, 0))

    cmap = plt.cm.RdYlBu
    im = ax2.contourf(S, G, direction_cat, levels=[-1.5, -0.5, 0.5, 1.5],
                       colors=['#2196F3', '#FFEB3B', '#F44336'], alpha=0.7)
    ax2.contour(S, G, direction_value, levels=[-5, 5], colors='black', linewidths=2)

    ax2.set_xlabel('Ângulo de Direção (%)')
    ax2.set_ylabel('Força G Lateral (g)')
    ax2.set_title('Mapa de Direção do Force Feedback\n(ω_z = 0)')

    # Legenda manual
    from matplotlib.patches import Patch
    legend_elements = [
        Patch(facecolor='#2196F3', alpha=0.7, label='ESQUERDA (D < -5)'),
        Patch(facecolor='#FFEB3B', alpha=0.7, label='NEUTRO (-5 ≤ D ≤ 5)'),
        Patch(facecolor='#F44336', alpha=0.7, label='DIREITA (D > 5)'),
    ]
    ax2.legend(handles=legend_elements, loc='upper right', fontsize=9)
    ax2.grid(True, alpha=0.3)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_direcao.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_velocity_integration_chart():
    """
    Gera gráfico mostrando o cálculo de velocidade por integração.
    """
    fig, axes = plt.subplots(2, 2, figsize=(11, 8))

    # Parâmetros do código real
    ACCEL_THRESHOLD = 0.3
    VELOCITY_DECAY_FACTOR = 0.98
    MIN_VELOCITY_THRESHOLD = 0.1

    dt = 0.01  # 100Hz
    t = np.arange(0, 5, dt)  # 5 segundos

    # Simula aceleração: aceleração de 2 m/s² por 1s, depois zero
    accel = np.zeros_like(t)
    accel[(t >= 0.5) & (t < 1.5)] = 2.0
    accel[(t >= 3.0) & (t < 3.5)] = -1.5

    # Adiciona ruído
    accel_noisy = accel + np.random.normal(0, 0.2, len(t))

    # Filtra ruído
    accel_filtered = np.where(np.abs(accel_noisy) < ACCEL_THRESHOLD, 0, accel_noisy)

    # Integração com decay
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
    # Velocidade sem decay para comparação
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
    ax4.set_title('Velocidade Estimada Final\n$v_{km/h} = v_{m/s} \\times 3.6$')
    ax4.legend()
    ax4.grid(True, alpha=0.3)
    ax4.set_xlim(0, 5)
    ax4.set_ylim(bottom=0)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_velocidade.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_g_force_chart():
    """
    Gera gráfico mostrando o cálculo das forças G.
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

    # Faixas típicas
    ax1.axhspan(-0.5, 0.5, alpha=0.1, color='green', label='Faixa típica RC')

    ax1.fill_between(accel_x, 0, g_frontal, where=(g_frontal > 0), alpha=0.2, color='green')
    ax1.fill_between(accel_x, 0, g_frontal, where=(g_frontal < 0), alpha=0.2, color='red')

    ax1.set_xlabel('Aceleração X (m/s²)')
    ax1.set_ylabel('Força G Frontal')
    ax1.set_title('Cálculo Força G Frontal\n$G_{frontal} = a_x / 9.81$')
    ax1.legend(fontsize=9)
    ax1.grid(True, alpha=0.3)
    ax1.set_xlim(-20, 20)
    ax1.set_ylim(-2.5, 2.5)

    # Força G Lateral (código real usa accel_y)
    ax2 = axes[1]
    accel_y = np.linspace(-15, 15, 100)
    g_lateral = accel_y / 9.81

    ax2.plot(accel_y, g_lateral, 'orange', linewidth=2)
    ax2.axhline(y=0, color='gray', linestyle='-', alpha=0.3)
    ax2.axvline(x=0, color='gray', linestyle='-', alpha=0.3)
    ax2.axhline(y=1, color='blue', linestyle='--', alpha=0.5, label='1g (curva direita)')
    ax2.axhline(y=-1, color='purple', linestyle='--', alpha=0.5, label='-1g (curva esquerda)')

    # Faixas típicas
    ax2.axhspan(-0.3, 0.3, alpha=0.1, color='orange', label='Faixa típica RC')

    ax2.fill_between(accel_y, 0, g_lateral, where=(g_lateral > 0), alpha=0.2, color='blue')
    ax2.fill_between(accel_y, 0, g_lateral, where=(g_lateral < 0), alpha=0.2, color='purple')

    ax2.set_xlabel('Aceleração Y (m/s²)')
    ax2.set_ylabel('Força G Lateral')
    ax2.set_title('Cálculo Força G Lateral\n$G_{lateral} = a_y / 9.81$')
    ax2.legend(fontsize=9)
    ax2.grid(True, alpha=0.3)
    ax2.set_xlim(-15, 15)
    ax2.set_ylim(-2, 2)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_forcas_g.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_pwm_mapping_chart():
    """
    Gera gráfico mostrando o mapeamento de intensidade para PWM.
    """
    fig, ax = plt.subplots(figsize=(8, 5))

    intensity = np.linspace(0, 100, 100)
    pwm = intensity * 255 / 100  # map(0-100) -> (0-255)

    ax.plot(intensity, pwm, 'b-', linewidth=3, label='Mapeamento Linear')

    # Pontos de referência
    ref_points = [(0, 0), (25, 64), (50, 127), (75, 191), (100, 255)]
    for x, y in ref_points:
        ax.plot(x, y, 'ro', markersize=8)
        ax.annotate(f'({x}%, {y})', xy=(x, y), xytext=(x+5, y-15), fontsize=9)

    ax.axhline(y=127.5, color='gray', linestyle='--', alpha=0.5, label='50% duty cycle')
    ax.axhline(y=255, color='red', linestyle=':', alpha=0.5, label='Máximo (255)')

    ax.set_xlabel('Intensidade (%)')
    ax.set_ylabel('Valor PWM (0-255)')
    ax.set_title('Mapeamento de Intensidade para PWM\n$PWM = intensity \\times 255 / 100$')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 270)

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_pwm_mapping.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def generate_complete_pipeline_chart():
    """
    Gera diagrama simplificado do pipeline completo de force feedback.
    """
    fig, ax = plt.subplots(figsize=(14, 6))
    ax.set_xlim(0, 14)
    ax.set_ylim(0, 6)
    ax.axis('off')

    # Cores
    colors = {
        'sensor': '#4CAF50',
        'calc': '#2196F3',
        'param': '#FF9800',
        'output': '#9C27B0',
        'hardware': '#F44336'
    }

    # Função para criar caixa
    def draw_box(x, y, w, h, text, color, fontsize=9):
        box = FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.05",
                             facecolor=color, edgecolor='black', linewidth=2, alpha=0.8)
        ax.add_patch(box)
        ax.text(x + w/2, y + h/2, text, ha='center', va='center', fontsize=fontsize,
               fontweight='bold', wrap=True)

    # Função para desenhar seta
    def draw_arrow(x1, y1, x2, y2):
        ax.annotate('', xy=(x2, y2), xytext=(x1, y1),
                   arrowprops=dict(arrowstyle='->', lw=2, color='black'))

    # Nível 1: Sensores (topo)
    draw_box(0.5, 4.5, 2.5, 1, 'BMI160\n(accel_x, accel_y,\ngyro_z)', colors['sensor'])
    draw_box(3.5, 4.5, 2, 1, 'Encoder\n(steering)', colors['sensor'])

    # Nível 2: Cálculos intermediários
    draw_box(0.5, 2.8, 2, 1, 'Força G\nG = a / 9.81', colors['calc'])
    draw_box(3.0, 2.8, 2.5, 1, 'Componentes\nLateral + Yaw +\nCentralização', colors['calc'])

    # Nível 3: Parâmetros ajustáveis
    draw_box(6.0, 4.5, 2.5, 1, 'Parâmetros\nSensibilidade\nFricção', colors['param'])
    draw_box(6.0, 3.2, 2.5, 1, 'Filtros\nSuavização\nDamping', colors['param'])

    # Nível 4: Resultado final
    draw_box(6.0, 1.5, 2.5, 1.2, 'FF Final\nIntensidade (0-100%)\nDireção (L/R/N)', colors['output'])

    # Nível 5: Hardware
    draw_box(9.5, 2.8, 2, 1, 'Serial USB\nFF_MOTOR:\nDIR:INT', colors['hardware'])
    draw_box(12, 2.8, 1.8, 1, 'ESP32\nPWM', colors['hardware'])
    draw_box(12, 1.3, 1.8, 1, 'BTS7960\nMotor DC', colors['hardware'])

    # Setas
    draw_arrow(1.75, 4.5, 1.5, 3.8)  # BMI160 -> Força G
    draw_arrow(4.5, 4.5, 4.25, 3.8)  # Encoder -> Componentes
    draw_arrow(2.5, 3.3, 3.0, 3.3)   # Força G -> Componentes
    draw_arrow(5.5, 3.3, 6.0, 3.7)   # Componentes -> Filtros
    draw_arrow(7.25, 4.5, 7.25, 4.2) # Parâmetros -> Filtros
    draw_arrow(7.25, 3.2, 7.25, 2.7) # Filtros -> FF Final
    draw_arrow(8.5, 2.1, 9.5, 3.1)   # FF Final -> Serial
    draw_arrow(11.5, 3.3, 12, 3.3)   # Serial -> ESP32
    draw_arrow(12.9, 2.8, 12.9, 2.3) # ESP32 -> BTS7960

    # Título
    ax.text(7, 5.8, 'Pipeline de Force Feedback', ha='center', va='center',
           fontsize=14, fontweight='bold')

    # Legenda
    legend_items = [
        (colors['sensor'], 'Sensores'),
        (colors['calc'], 'Cálculos'),
        (colors['param'], 'Parâmetros'),
        (colors['output'], 'Saída'),
        (colors['hardware'], 'Hardware')
    ]
    for i, (color, label) in enumerate(legend_items):
        rect = FancyBboxPatch((0.3 + i*2.5, 0.2), 0.4, 0.4, boxstyle="round,pad=0.02",
                             facecolor=color, edgecolor='black', alpha=0.8)
        ax.add_patch(rect)
        ax.text(0.9 + i*2.5, 0.4, label, fontsize=9, va='center')

    plt.tight_layout()
    output_path = os.path.join(OUTPUT_DIR, 'ff_pipeline.png')
    plt.savefig(output_path)
    plt.close()
    print(f"Gerado: {output_path}")


def main():
    """Gera todos os gráficos de force feedback."""
    print(f"Gerando gráficos em: {OUTPUT_DIR}\n")

    generate_g_force_chart()
    generate_ff_components_chart()
    generate_ff_combined_chart()
    generate_ff_parameters_chart()
    generate_direction_calculation_chart()
    generate_velocity_integration_chart()
    generate_pwm_mapping_chart()
    generate_complete_pipeline_chart()

    print(f"\n✓ Todos os gráficos gerados com sucesso!")
    print(f"  Diretório: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
