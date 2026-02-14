"""
energy_panel.py - Painel dedicado de monitoramento de energia
Bateria 3S LiPo, correntes (ACS758), potências e INA219 (RPi)
"""

import tkinter as tk
from tkinter import ttk


def create_energy_panel(console):
    """
    Cria painel de monitoramento de energia completo

    Layout:
    ┌──────────────────────────────────────────────────────────────┐
    │ Monitoramento de Energia                                     │
    │ ┌─────────────┐ ┌──────────────┐ ┌──────────────┐ ┌───────┐ │
    │ │ BATERIA 3S  │ │ MOTOR DC 775 │ │ SERVOS/UBEC  │ │  RPi  │ │
    │ │  11.85V     │ │  5.20A       │ │  1.30A       │ │ 0.85A │ │
    │ │  79.2%      │ │  57.7W       │ │  6.8W        │ │ 4.3W  │ │
    │ └─────────────┘ └──────────────┘ └──────────────┘ └───────┘ │
    │                          Potência Total: 68.8W               │
    └──────────────────────────────────────────────────────────────┘

    Args:
        console: Instancia de ConsoleInterface
    """
    energy_frame = ttk.LabelFrame(
        console.left_column,
        text="Monitoramento de Energia",
        style="Dark.TLabelframe",
    )
    energy_frame.pack(fill=tk.X, padx=5, pady=5)

    # Frame interno
    energy_inner = tk.Frame(energy_frame, bg="#3c3c3c")
    energy_inner.pack(fill=tk.X, padx=10, pady=10)

    # === Linha superior: 4 blocos lado a lado ===
    blocks_row = tk.Frame(energy_inner, bg="#3c3c3c")
    blocks_row.pack(fill=tk.X)

    # -- Bateria 3S LiPo --
    bat_block = tk.Frame(blocks_row, bg="#2c2c2c", relief=tk.RAISED, bd=2)
    bat_block.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=3)

    tk.Label(
        bat_block,
        text="BATERIA 3S",
        bg="#2c2c2c",
        fg="#ffcc00",
        font=("Arial", 9, "bold"),
    ).pack(pady=(5, 2))

    console.battery_voltage_display = tk.Label(
        bat_block,
        textvariable=console.sensor_vars["voltage_battery"],
        bg="#2c2c2c",
        fg="#00ff88",
        font=("Digital-7", 22, "bold"),
    )
    console.battery_voltage_display.pack()

    console.battery_pct_display = tk.Label(
        bat_block,
        textvariable=console.sensor_vars["battery_percentage"],
        bg="#2c2c2c",
        fg="#00ff88",
        font=("Arial", 11, "bold"),
    )
    console.battery_pct_display.pack(pady=(0, 5))

    # -- Motor DC 775 --
    motor_block = tk.Frame(blocks_row, bg="#2c2c2c", relief=tk.RAISED, bd=2)
    motor_block.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=3)

    tk.Label(
        motor_block,
        text="MOTOR DC 775",
        bg="#2c2c2c",
        fg="#ff6666",
        font=("Arial", 9, "bold"),
    ).pack(pady=(5, 2))

    motor_grid = tk.Frame(motor_block, bg="#2c2c2c")
    motor_grid.pack(pady=(0, 5))

    tk.Label(
        motor_grid, text="Corrente:", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).grid(row=0, column=0, sticky="e", padx=2)
    tk.Label(
        motor_grid,
        textvariable=console.sensor_vars["current_motor"],
        bg="#2c2c2c",
        fg="#ff6666",
        font=("Arial", 11, "bold"),
    ).grid(row=0, column=1, sticky="w", padx=2)

    tk.Label(
        motor_grid, text="Potência:", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).grid(row=1, column=0, sticky="e", padx=2)
    tk.Label(
        motor_grid,
        textvariable=console.sensor_vars["power_motor"],
        bg="#2c2c2c",
        fg="#ff9999",
        font=("Arial", 10),
    ).grid(row=1, column=1, sticky="w", padx=2)

    # -- Servos / UBEC --
    servos_block = tk.Frame(blocks_row, bg="#2c2c2c", relief=tk.RAISED, bd=2)
    servos_block.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=3)

    tk.Label(
        servos_block,
        text="SERVOS / UBEC",
        bg="#2c2c2c",
        fg="#66ff66",
        font=("Arial", 9, "bold"),
    ).pack(pady=(5, 2))

    servos_grid = tk.Frame(servos_block, bg="#2c2c2c")
    servos_grid.pack(pady=(0, 5))

    tk.Label(
        servos_grid, text="Corrente:", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).grid(row=0, column=0, sticky="e", padx=2)
    tk.Label(
        servos_grid,
        textvariable=console.sensor_vars["current_servos"],
        bg="#2c2c2c",
        fg="#66ff66",
        font=("Arial", 11, "bold"),
    ).grid(row=0, column=1, sticky="w", padx=2)

    tk.Label(
        servos_grid, text="Potência:", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).grid(row=1, column=0, sticky="e", padx=2)
    tk.Label(
        servos_grid,
        textvariable=console.sensor_vars["power_servos"],
        bg="#2c2c2c",
        fg="#99ff99",
        font=("Arial", 10),
    ).grid(row=1, column=1, sticky="w", padx=2)

    # -- Raspberry Pi (INA219) --
    rpi_block = tk.Frame(blocks_row, bg="#2c2c2c", relief=tk.RAISED, bd=2)
    rpi_block.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=3, pady=3)

    tk.Label(
        rpi_block,
        text="RPi (INA219)",
        bg="#2c2c2c",
        fg="#6699ff",
        font=("Arial", 9, "bold"),
    ).pack(pady=(5, 2))

    rpi_grid = tk.Frame(rpi_block, bg="#2c2c2c")
    rpi_grid.pack(pady=(0, 5))

    tk.Label(
        rpi_grid, text="Tensão:", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).grid(row=0, column=0, sticky="e", padx=2)
    tk.Label(
        rpi_grid,
        textvariable=console.sensor_vars["voltage_rpi"],
        bg="#2c2c2c",
        fg="#6699ff",
        font=("Arial", 11, "bold"),
    ).grid(row=0, column=1, sticky="w", padx=2)

    tk.Label(
        rpi_grid, text="Corrente:", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).grid(row=1, column=0, sticky="e", padx=2)
    tk.Label(
        rpi_grid,
        textvariable=console.sensor_vars["current_rpi"],
        bg="#2c2c2c",
        fg="#99bbff",
        font=("Arial", 10),
    ).grid(row=1, column=1, sticky="w", padx=2)

    tk.Label(
        rpi_grid, text="Potência:", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).grid(row=2, column=0, sticky="e", padx=2)
    tk.Label(
        rpi_grid,
        textvariable=console.sensor_vars["power_rpi"],
        bg="#2c2c2c",
        fg="#99bbff",
        font=("Arial", 10),
    ).grid(row=2, column=1, sticky="w", padx=2)

    # === Linha inferior: Potência total em destaque ===
    total_row = tk.Frame(energy_inner, bg="#2c2c2c", relief=tk.GROOVE, bd=1)
    total_row.pack(fill=tk.X, padx=3, pady=(5, 3))

    tk.Label(
        total_row,
        text="POTÊNCIA TOTAL:",
        bg="#2c2c2c",
        fg="#cccccc",
        font=("Arial", 10, "bold"),
    ).pack(side=tk.LEFT, padx=(10, 5), pady=5)

    console.power_total_display = tk.Label(
        total_row,
        textvariable=console.sensor_vars["power_total"],
        bg="#2c2c2c",
        fg="#ffcc00",
        font=("Arial", 16, "bold"),
    )
    console.power_total_display.pack(side=tk.LEFT, pady=5)
