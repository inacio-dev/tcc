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
# Formato: marcha -> [(inicio, fim, zona), ...]
GEAR_ZONES = {
    1: [
        (0, 20, 'IDEAL'),
        (20, 30, 'SUBOPTIMAL'),
        (30, 40, 'POOR'),
    ],
    2: [
        (0, 10, 'POOR'),
        (10, 20, 'SUBOPTIMAL'),
        (20, 40, 'IDEAL'),
        (40, 50, 'SUBOPTIMAL'),
        (50, 60, 'POOR'),
    ],
    3: [
        (0, 30, 'POOR'),
        (30, 40, 'SUBOPTIMAL'),
        (40, 60, 'IDEAL'),
        (60, 70, 'SUBOPTIMAL'),
        (70, 80, 'POOR'),
    ],
    4: [
        (0, 50, 'POOR'),
        (50, 60, 'SUBOPTIMAL'),
        (60, 80, 'IDEAL'),
        (80, 90, 'SUBOPTIMAL'),
        (90, 100, 'POOR'),
    ],
    5: [
        (0, 70, 'POOR'),
        (70, 80, 'SUBOPTIMAL'),
        (80, 100, 'IDEAL'),
    ],
}

# Limitadores de PWM por marcha
GEAR_LIMITERS = {
    1: 40,
    2: 60,
    3: 80,
    4: 100,
    5: 100,
}

# Cores para cada zona
ZONE_COLORS = {
    'IDEAL': '#2ecc71',      # Verde
    'SUBOPTIMAL': '#f39c12', # Amarelo/Laranja
    'POOR': '#e74c3c',       # Vermelho
}

# Multiplicadores de aceleração
ZONE_RATES = {
    'IDEAL': '1.0x',
    'SUBOPTIMAL': '0.1x (10x mais lento)',
    'POOR': '0.04x (25x mais lento)',
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
        mpatches.Patch(color=ZONE_COLORS['SUBOPTIMAL'], label=f'SUBOPTIMAL - Aceleração {ZONE_RATES["SUBOPTIMAL"]}'),
        mpatches.Patch(color=ZONE_COLORS['POOR'], label=f'POOR - Aceleração {ZONE_RATES["POOR"]}'),
    ]
    ax.legend(handles=legend_patches, loc='upper right', fontsize=9)

    # Anotações das zonas ideais
    ideal_ranges = {
        1: '0-20%',
        2: '20-40%',
        3: '40-60%',
        4: '60-80%',
        5: '80-100%',
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

    # Também salva em PDF para LaTeX
    output_pdf = 'monografia/figuras/zonas_eficiencia_marchas.pdf'
    plt.savefig(output_pdf, bbox_inches='tight', facecolor='white', edgecolor='none')
    print(f'PDF salvo em: {output_pdf}')

    plt.close()


def create_torque_factor_chart():
    """Cria gráfico do fator de torque por marcha"""

    fig, ax = plt.subplots(figsize=(10, 6))

    # Dados
    gears = [1, 2, 3, 4, 5]
    max_gear = 5

    # Fator de torque: 1.0 + 0.2 × (Marcha_max - Marcha_atual)
    torque_factors = [1.0 + 0.2 * (max_gear - g) for g in gears]

    # Relações de transmissão (do código)
    gear_ratios = [3.5, 2.2, 1.4, 0.9, 0.7]

    # Limitadores de PWM
    limiters = [40, 60, 80, 100, 100]

    # Configuração de barras agrupadas
    x = np.arange(len(gears))
    width = 0.25

    # Barras
    bars1 = ax.bar(x - width, torque_factors, width, label='Fator de Torque', color='#3498db')
    bars2 = ax.bar(x, gear_ratios, width, label='Relação de Transmissão', color='#9b59b6')
    bars3 = ax.bar(x + width, [l/100 * 1.8 for l in limiters], width,
                   label='Limitador PWM (escala /100×1.8)', color='#e67e22')

    # Valores nas barras
    for bar, val in zip(bars1, torque_factors):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f'{val:.1f}', ha='center', va='bottom', fontsize=8)

    for bar, val in zip(bars2, gear_ratios):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f'{val:.1f}', ha='center', va='bottom', fontsize=8)

    for bar, val in zip(bars3, limiters):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.05,
                f'{val}%', ha='center', va='bottom', fontsize=8)

    # Configurações
    ax.set_xlabel('Marcha')
    ax.set_ylabel('Valor')
    ax.set_title('Características do Sistema de Transmissão por Marcha')
    ax.set_xticks(x)
    ax.set_xticklabels([f'{g}ª' for g in gears])
    ax.legend(loc='upper right')
    ax.grid(axis='y', alpha=0.3)
    ax.set_ylim(0, 2.2)

    plt.tight_layout()

    # Salva
    output_path = 'monografia/figuras/caracteristicas_transmissao.png'
    plt.savefig(output_path, dpi=150, bbox_inches='tight',
                facecolor='white', edgecolor='none')
    print(f'Gráfico salvo em: {output_path}')

    output_pdf = 'monografia/figuras/caracteristicas_transmissao.pdf'
    plt.savefig(output_pdf, bbox_inches='tight', facecolor='white', edgecolor='none')
    print(f'PDF salvo em: {output_pdf}')

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
        mpatches.Patch(color=ZONE_COLORS['SUBOPTIMAL'], label='SUBOPTIMAL (0.1x)'),
        mpatches.Patch(color=ZONE_COLORS['POOR'], label='POOR (0.04x)'),
    ]
    ax1.legend(handles=legend_patches, loc='upper right', fontsize=9)

    # ===== SUBPLOT 2: Fator de Torque e PWM Máximo =====
    ax2 = axes[1]

    gears = np.array([1, 2, 3, 4, 5])
    max_gear = 5

    # Fator de torque
    torque_factors = 1.0 + 0.2 * (max_gear - gears)

    # PWM máximo (limitador)
    pwm_max = np.array([40, 60, 80, 100, 100])

    # Eixo duplo
    ax2_twin = ax2.twinx()

    # Barras do PWM máximo
    bars = ax2.bar(gears, pwm_max, color='#3498db', alpha=0.7,
                   label='PWM Máximo (%)', width=0.6)

    # Linha do fator de torque
    line = ax2_twin.plot(gears, torque_factors, 'o-', color='#e74c3c',
                        linewidth=2, markersize=10, label='Fator de Torque')

    # Valores
    for bar, val in zip(bars, pwm_max):
        ax2.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 2,
                f'{val}%', ha='center', fontsize=10, fontweight='bold')

    for x, y in zip(gears, torque_factors):
        ax2_twin.text(x, y + 0.08, f'{y:.1f}', ha='center', fontsize=10,
                     color='#e74c3c', fontweight='bold')

    # Equação
    ax2.text(0.5, -0.18, r'$Fator_{torque} = 1.0 + 0.2 \times (Marcha_{max} - Marcha_{atual})$',
            transform=ax2.transAxes, fontsize=11, ha='center',
            bbox=dict(boxstyle='round', facecolor='wheat', alpha=0.5))

    ax2.set_xlabel('Marcha')
    ax2.set_ylabel('PWM Máximo (%)', color='#3498db')
    ax2_twin.set_ylabel('Fator de Torque', color='#e74c3c')
    ax2.set_title('(b) Limitadores de PWM e Fator de Torque por Marcha', fontweight='bold')
    ax2.set_xticks(gears)
    ax2.set_xticklabels([f'{g}ª' for g in gears])
    ax2.set_ylim(0, 120)
    ax2_twin.set_ylim(0.8, 2.2)
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

    output_pdf = 'monografia/figuras/sistema_transmissao_f1.pdf'
    plt.savefig(output_pdf, bbox_inches='tight', facecolor='white', edgecolor='none')
    print(f'PDF salvo em: {output_pdf}')

    plt.close()


if __name__ == '__main__':
    print('Gerando gráficos do sistema de transmissão F1...\n')

    # Gráfico 1: Zonas de eficiência
    create_gear_zones_chart()

    # Gráfico 2: Características da transmissão
    create_torque_factor_chart()

    # Gráfico 3: Figura combinada
    create_combined_chart()

    print('\nTodos os gráficos gerados com sucesso!')
