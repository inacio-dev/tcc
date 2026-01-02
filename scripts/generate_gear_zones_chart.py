#!/usr/bin/env python3
"""
generate_gear_zones_chart.py - Gera gráfico das zonas de eficiência F1 por marcha

Baseado no sistema de zonas implementado em raspberry/motor_manager.py

Zonas de Eficiência por Marcha:
- IDEAL (verde): Aceleração normal (1.0x)
- SUBOPTIMAL (amarelo): Aceleração 10x mais lenta (0.1x)
- POOR (vermelho): Aceleração 25x mais lenta (0.04x)

Uso:
    python scripts/generate_gear_zones_chart.py

Saída:
    monografia/figuras/zonas_eficiencia_marchas.png
"""

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np

# Configuração de estilo
plt.rcParams['font.family'] = 'DejaVu Sans'
plt.rcParams['font.size'] = 10

# Dados das zonas de eficiência por marcha (baseado em motor_manager.py)
# Distribuição: 1ª e 2ª dividem 0-30% | 3ª e 4ª dividem 30-90% | 5ª pega 70-100%
# Formato: marcha -> [(inicio, fim, zona), ...]
GEAR_ZONES = {
    1: [
        (0, 10, 'IDEAL'),
        (10, 13, 'SUBÓTIMA'),
        (13, 15, 'RUIM'),
    ],
    2: [
        (0, 5, 'RUIM'),
        (5, 10, 'SUBÓTIMA'),
        (10, 22, 'IDEAL'),
        (22, 27, 'SUBÓTIMA'),
        (27, 30, 'RUIM'),
    ],
    3: [
        (0, 22, 'RUIM'),
        (22, 30, 'SUBÓTIMA'),
        (30, 45, 'IDEAL'),
        (45, 52, 'SUBÓTIMA'),
        (52, 60, 'RUIM'),
    ],
    4: [
        (0, 35, 'RUIM'),
        (35, 45, 'SUBÓTIMA'),
        (45, 75, 'IDEAL'),
        (75, 85, 'SUBÓTIMA'),
        (85, 90, 'RUIM'),
    ],
    5: [
        (0, 55, 'RUIM'),
        (55, 70, 'SUBÓTIMA'),
        (70, 100, 'IDEAL'),
    ],
}

# Limitadores de PWM por marcha
# 1ª e 2ª dividem 0-30% | 3ª e 4ª dividem 30-90% | 5ª pega 70-100%
GEAR_LIMITERS = {
    1: 15,
    2: 30,
    3: 60,
    4: 90,
    5: 100,
}

# Cores para cada zona
ZONE_COLORS = {
    'IDEAL': '#2ecc71',      # Verde
    'SUBÓTIMA': '#f39c12',   # Amarelo/Laranja
    'RUIM': '#e74c3c',       # Vermelho
}

# Multiplicadores de aceleração
ZONE_RATES = {
    'IDEAL': '1.0x',
    'SUBÓTIMA': '0.1x (10x mais lento)',
    'RUIM': '0.04x (25x mais lento)',
}


def create_gear_zones_chart():
    """Cria gráfico de barras horizontais mostrando zonas por marcha"""

    fig, ax = plt.subplots(figsize=(12, 7))

    # Altura de cada barra
    bar_height = 0.6

    # Para cada marcha (de baixo para cima: 1ª embaixo, 5ª em cima)
    for gear in range(1, 6):
        y_pos = gear - 1
        zones = GEAR_ZONES[gear]
        limiter = GEAR_LIMITERS[gear]

        # Desenha cada zona
        for start, end, zone_type in zones:
            width = end - start
            color = ZONE_COLORS[zone_type]

            # Barra da zona
            rect = ax.barh(y_pos, width, left=start, height=bar_height,
                          color=color, edgecolor='white', linewidth=1)

        # Linha do limitador
        ax.axvline(x=limiter, ymin=(y_pos - 0.3) / 5, ymax=(y_pos + 0.9) / 5,
                   color='black', linestyle='--', linewidth=1.5, alpha=0.7)

        # Texto do limitador
        ax.text(limiter + 1, y_pos, f'Limite: {limiter}%',
                va='center', ha='left', fontsize=8, color='black', alpha=0.7)

    # Configurações do eixo
    ax.set_xlim(0, 105)
    ax.set_ylim(-0.5, 5)
    ax.set_yticks(range(5))
    ax.set_yticklabels([f'{i}ª Marcha' for i in range(1, 6)])
    ax.set_xlabel('PWM do Motor (%)')
    ax.set_ylabel('Marcha')
    ax.set_title('Zonas de Eficiência F1 por Marcha\n(Sistema de Transmissão Manual 5 Marchas)')

    # Grid
    ax.grid(axis='x', alpha=0.3, linestyle='-')
    ax.set_axisbelow(True)

    # Legenda
    legend_patches = [
        mpatches.Patch(color=ZONE_COLORS['IDEAL'], label=f'IDEAL - Aceleração {ZONE_RATES["IDEAL"]}'),
        mpatches.Patch(color=ZONE_COLORS['SUBÓTIMA'], label=f'SUBÓTIMA - Aceleração {ZONE_RATES["SUBÓTIMA"]}'),
        mpatches.Patch(color=ZONE_COLORS['RUIM'], label=f'RUIM - Aceleração {ZONE_RATES["RUIM"]}'),
    ]
    ax.legend(handles=legend_patches, loc='upper right', fontsize=9)

    # Anotações das zonas ideais
    ideal_ranges = {
        1: '0-10%',
        2: '10-22%',
        3: '30-45%',
        4: '45-75%',
        5: '70-100%',
    }

    for gear in range(1, 6):
        y_pos = gear - 1
        zones = GEAR_ZONES[gear]
        for start, end, zone_type in zones:
            if zone_type == 'IDEAL':
                mid = (start + end) / 2
                ax.text(mid, y_pos, f'{start}-{end}%',
                       va='center', ha='center', fontsize=9,
                       color='white', fontweight='bold')

    plt.tight_layout()

    # Salva figura
    output_path = 'monografia/figuras/zonas_eficiencia_marchas.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f'Gráfico salvo em: {output_path}')

    plt.close()


def create_acceleration_rate_chart():
    """Cria gráfico da taxa de aceleração por zona de eficiência"""

    fig, ax = plt.subplots(figsize=(10, 6))

    # Dados das zonas de eficiência
    # Do motor_manager.py: base_acceleration_time = 5.0s
    # Taxa = (100 / tempo_base) × multiplicador_zona
    zones = ['IDEAL', 'SUBÓTIMA', 'RUIM']
    multipliers = [1.0, 0.1, 0.04]
    base_time = 5.0  # segundos

    # Taxa de aceleração (%PWM por segundo)
    rates = [(100 / base_time) * m for m in multipliers]  # [20.0, 2.0, 0.8]

    # Tempo para atingir 100% PWM
    times = [base_time / m for m in multipliers]  # [5.0, 50.0, 125.0]

    # Configuração de barras
    x = np.arange(len(zones))
    width = 0.35

    # Barras da taxa de aceleração
    bars1 = ax.bar(x - width/2, rates, width, label='Taxa de Aceleração (%/s)',
                   color=[ZONE_COLORS[z] for z in zones], edgecolor='black', linewidth=1)

    # Eixo secundário para tempo
    ax2 = ax.twinx()
    bars2 = ax2.bar(x + width/2, times, width, label='Tempo para 100% (s)',
                    color=[ZONE_COLORS[z] for z in zones], alpha=0.4,
                    edgecolor='black', linewidth=1, hatch='//')

    # Valores nas barras
    for bar, val in zip(bars1, rates):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'{val:.1f}%/s', ha='center', va='bottom', fontsize=10, fontweight='bold')

    for bar, val in zip(bars2, times):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 3,
                f'{val:.0f}s', ha='center', va='bottom', fontsize=10, fontweight='bold')

    # Configurações
    ax.set_xlabel('Zona de Eficiência', fontsize=11)
    ax.set_ylabel('Taxa de Aceleração (%PWM/s)', fontsize=11)
    ax2.set_ylabel('Tempo para 100% PWM (s)', fontsize=11)
    ax.set_title('Taxa de Aceleração por Zona de Eficiência\n(Tempo base: 5 segundos)', fontsize=12)
    ax.set_xticks(x)
    ax.set_xticklabels(zones, fontsize=11)
    ax.set_ylim(0, 25)
    ax2.set_ylim(0, 150)
    ax.grid(axis='y', alpha=0.3)

    # Legenda combinada
    lines1, labels1 = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    # Equação
    ax.text(0.5, -0.15, r'$Taxa_{acel} = \frac{100\%}{T_{base}} \times M_{zona}$ onde $M_{IDEAL}=1.0$, $M_{SUB}=0.1$, $M_{RUIM}=0.04$',
            transform=ax.transAxes, fontsize=11, ha='center',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    plt.tight_layout()
    plt.subplots_adjust(bottom=0.18)

    # Salva
    output_path = 'monografia/figuras/taxa_aceleracao_zonas.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f'Gráfico salvo em: {output_path}')

    plt.close()


def create_combined_chart():
    """Cria figura combinada com zonas e equação"""

    fig, axes = plt.subplots(2, 1, figsize=(12, 10), height_ratios=[1.2, 1])

    # ===== SUBPLOT 1: Zonas de Eficiência =====
    ax1 = axes[0]
    bar_height = 0.6

    for gear in range(1, 6):
        y_pos = gear - 1
        zones = GEAR_ZONES[gear]
        limiter = GEAR_LIMITERS[gear]

        for start, end, zone_type in zones:
            width = end - start
            color = ZONE_COLORS[zone_type]
            ax1.barh(y_pos, width, left=start, height=bar_height,
                    color=color, edgecolor='white', linewidth=1)

        # Linha do limitador
        ax1.axvline(x=limiter, ymin=(y_pos - 0.3 + 0.5) / 5.5,
                   ymax=(y_pos + 0.9 + 0.5) / 5.5,
                   color='black', linestyle='--', linewidth=1.5, alpha=0.7)
        ax1.text(limiter + 1, y_pos, f'Lim: {limiter}%',
                va='center', ha='left', fontsize=8, alpha=0.7)

        # Texto da zona ideal
        for start, end, zone_type in zones:
            if zone_type == 'IDEAL':
                mid = (start + end) / 2
                ax1.text(mid, y_pos, f'{start}-{end}%',
                        va='center', ha='center', fontsize=9,
                        color='white', fontweight='bold')

    ax1.set_xlim(0, 105)
    ax1.set_ylim(-0.5, 5)
    ax1.set_yticks(range(5))
    ax1.set_yticklabels([f'{i}ª Marcha' for i in range(1, 6)])
    ax1.set_xlabel('PWM do Motor (%)')
    ax1.set_title('(a) Zonas de Eficiência F1 por Marcha', fontweight='bold')
    ax1.grid(axis='x', alpha=0.3)

    legend_patches = [
        mpatches.Patch(color=ZONE_COLORS['IDEAL'], label='IDEAL (1.0x)'),
        mpatches.Patch(color=ZONE_COLORS['SUBÓTIMA'], label='SUBÓTIMA (0.1x)'),
        mpatches.Patch(color=ZONE_COLORS['RUIM'], label='RUIM (0.04x)'),
    ]
    ax1.legend(handles=legend_patches, loc='upper right', fontsize=9)

    # ===== SUBPLOT 2: Taxa de Aceleração por Zona =====
    ax2 = axes[1]

    # Dados das zonas de eficiência
    # Do motor_manager.py: base_acceleration_time = 5.0s
    # Taxa = (100 / tempo_base) × multiplicador_zona
    zones = ['IDEAL', 'SUBÓTIMA', 'RUIM']
    multipliers = [1.0, 0.1, 0.04]
    base_time = 5.0  # segundos

    # Taxa de aceleração (%PWM por segundo)
    rates = [(100 / base_time) * m for m in multipliers]  # [20.0, 2.0, 0.8]

    # Tempo para atingir 100% PWM
    times = [base_time / m for m in multipliers]  # [5.0, 50.0, 125.0]

    # Configuração de barras
    x = np.arange(len(zones))
    width = 0.35

    # Barras da taxa de aceleração
    bars1 = ax2.bar(x - width/2, rates, width, label='Taxa (%/s)',
                   color=[ZONE_COLORS[z] for z in zones], edgecolor='black', linewidth=1)

    # Eixo secundário para tempo
    ax2_twin = ax2.twinx()
    bars2 = ax2_twin.bar(x + width/2, times, width, label='Tempo (s)',
                    color=[ZONE_COLORS[z] for z in zones], alpha=0.4,
                    edgecolor='black', linewidth=1, hatch='//')

    # Valores nas barras
    for bar, val in zip(bars1, rates):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.5,
                f'{val:.1f}%/s', ha='center', va='bottom', fontsize=9, fontweight='bold')

    for bar, val in zip(bars2, times):
        ax2_twin.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 3,
                f'{val:.0f}s', ha='center', va='bottom', fontsize=9, fontweight='bold')

    # Equação
    ax2.text(0.5, -0.18, r'$Taxa_{acel} = \frac{100\%}{5s} \times M_{zona}$ onde $M_{IDEAL}=1.0$, $M_{SUB}=0.1$, $M_{RUIM}=0.04$',
            transform=ax2.transAxes, fontsize=10, ha='center',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax2.set_xlabel('Zona de Eficiência')
    ax2.set_ylabel('Taxa de Aceleração (%/s)')
    ax2_twin.set_ylabel('Tempo para 100% (s)')
    ax2.set_title('(b) Taxa de Aceleração por Zona de Eficiência', fontweight='bold')
    ax2.set_xticks(x)
    ax2.set_xticklabels(zones)
    ax2.set_ylim(0, 25)
    ax2_twin.set_ylim(0, 150)
    ax2.grid(axis='y', alpha=0.3)

    # Legenda combinada
    lines1, labels1 = ax2.get_legend_handles_labels()
    lines2, labels2 = ax2_twin.get_legend_handles_labels()
    ax2.legend(lines1 + lines2, labels1 + labels2, loc='upper right')

    plt.tight_layout()
    plt.subplots_adjust(hspace=0.35)

    # Salva
    output_path = 'monografia/figuras/sistema_transmissao_f1.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f'Gráfico combinado salvo em: {output_path}')

    plt.close()


if __name__ == '__main__':
    print('Gerando gráficos do sistema de transmissão F1...\n')

    # Gráfico 1: Zonas de eficiência
    create_gear_zones_chart()

    # Gráfico 2: Taxa de aceleração por zona
    create_acceleration_rate_chart()

    # Gráfico 3: Figura combinada
    create_combined_chart()

    print('\nTodos os gráficos gerados com sucesso!')
