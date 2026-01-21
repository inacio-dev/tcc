"""
rpi_system.py - Frame com métricas do sistema Raspberry Pi
"""

import tkinter as tk
from tkinter import ttk


def create_rpi_system_frame(console):
    """
    Cria frame com métricas do sistema Raspberry Pi (CPU, memória, disco, rede)

    Args:
        console: Instância de ConsoleInterface
    """
    system_frame = ttk.LabelFrame(
        console.left_column, text="Sistema RPi", style="Dark.TLabelframe"
    )
    system_frame.pack(fill=tk.X, padx=5, pady=5)

    # Frame interno com grid
    inner_frame = tk.Frame(system_frame, bg="#3c3c3c")
    inner_frame.pack(fill=tk.X, padx=5, pady=5)

    # Configurar colunas
    for i in range(4):
        inner_frame.grid_columnconfigure(i, weight=1)

    # === LINHA 1: CPU ===
    # CPU Usage
    cpu_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    cpu_frame.grid(row=0, column=0, padx=3, pady=3, sticky="nsew")

    tk.Label(
        cpu_frame, text="CPU", bg="#2c2c2c", fg="white", font=("Arial", 9, "bold")
    ).pack(pady=2)

    console.rpi_cpu_usage_display = tk.Label(
        cpu_frame,
        textvariable=console.sensor_vars["rpi_cpu_usage_percent"],
        bg="#2c2c2c",
        fg="#00ff88",
        font=("Arial", 14, "bold"),
    )
    console.rpi_cpu_usage_display.pack()

    tk.Label(
        cpu_frame, text="%", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).pack()

    # CPU Temp
    temp_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    temp_frame.grid(row=0, column=1, padx=3, pady=3, sticky="nsew")

    tk.Label(
        temp_frame, text="Temp", bg="#2c2c2c", fg="white", font=("Arial", 9, "bold")
    ).pack(pady=2)

    console.rpi_cpu_temp_display = tk.Label(
        temp_frame,
        textvariable=console.sensor_vars["rpi_cpu_temp_c"],
        bg="#2c2c2c",
        fg="#00ff88",
        font=("Arial", 14, "bold"),
    )
    console.rpi_cpu_temp_display.pack()

    tk.Label(
        temp_frame, text="°C", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).pack()

    # Memória
    mem_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    mem_frame.grid(row=0, column=2, padx=3, pady=3, sticky="nsew")

    tk.Label(
        mem_frame, text="RAM", bg="#2c2c2c", fg="white", font=("Arial", 9, "bold")
    ).pack(pady=2)

    console.rpi_mem_display = tk.Label(
        mem_frame,
        textvariable=console.sensor_vars["rpi_mem_usage_percent"],
        bg="#2c2c2c",
        fg="#00ff88",
        font=("Arial", 14, "bold"),
    )
    console.rpi_mem_display.pack()

    tk.Label(
        mem_frame, text="%", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).pack()

    # Disco
    disk_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    disk_frame.grid(row=0, column=3, padx=3, pady=3, sticky="nsew")

    tk.Label(
        disk_frame, text="Disco", bg="#2c2c2c", fg="white", font=("Arial", 9, "bold")
    ).pack(pady=2)

    console.rpi_disk_display = tk.Label(
        disk_frame,
        textvariable=console.sensor_vars["rpi_disk_usage_percent"],
        bg="#2c2c2c",
        fg="#00ff88",
        font=("Arial", 14, "bold"),
    )
    console.rpi_disk_display.pack()

    tk.Label(
        disk_frame, text="%", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).pack()

    # === LINHA 2: Rede e Sistema ===
    # Rede RX
    net_rx_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    net_rx_frame.grid(row=1, column=0, padx=3, pady=3, sticky="nsew")

    tk.Label(
        net_rx_frame, text="Net RX", bg="#2c2c2c", fg="white", font=("Arial", 9, "bold")
    ).pack(pady=2)

    console.rpi_net_rx_display = tk.Label(
        net_rx_frame,
        textvariable=console.sensor_vars["rpi_net_rx_rate_kbps"],
        bg="#2c2c2c",
        fg="#66ccff",
        font=("Arial", 12, "bold"),
    )
    console.rpi_net_rx_display.pack()

    tk.Label(
        net_rx_frame, text="KB/s", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).pack()

    # Rede TX
    net_tx_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    net_tx_frame.grid(row=1, column=1, padx=3, pady=3, sticky="nsew")

    tk.Label(
        net_tx_frame, text="Net TX", bg="#2c2c2c", fg="white", font=("Arial", 9, "bold")
    ).pack(pady=2)

    console.rpi_net_tx_display = tk.Label(
        net_tx_frame,
        textvariable=console.sensor_vars["rpi_net_tx_rate_kbps"],
        bg="#2c2c2c",
        fg="#ffcc66",
        font=("Arial", 12, "bold"),
    )
    console.rpi_net_tx_display.pack()

    tk.Label(
        net_tx_frame, text="KB/s", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).pack()

    # Load Average
    load_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    load_frame.grid(row=1, column=2, padx=3, pady=3, sticky="nsew")

    tk.Label(
        load_frame, text="Load", bg="#2c2c2c", fg="white", font=("Arial", 9, "bold")
    ).pack(pady=2)

    console.rpi_load_display = tk.Label(
        load_frame,
        textvariable=console.sensor_vars["rpi_load_1min"],
        bg="#2c2c2c",
        fg="#ff9966",
        font=("Arial", 12, "bold"),
    )
    console.rpi_load_display.pack()

    tk.Label(
        load_frame, text="1min", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).pack()

    # Uptime
    uptime_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    uptime_frame.grid(row=1, column=3, padx=3, pady=3, sticky="nsew")

    tk.Label(
        uptime_frame, text="Uptime", bg="#2c2c2c", fg="white", font=("Arial", 9, "bold")
    ).pack(pady=2)

    console.rpi_uptime_display = tk.Label(
        uptime_frame,
        textvariable=console.sensor_vars["rpi_uptime_formatted"],
        bg="#2c2c2c",
        fg="#99ff99",
        font=("Arial", 11, "bold"),
    )
    console.rpi_uptime_display.pack()

    tk.Label(
        uptime_frame, text="", bg="#2c2c2c", fg="#aaaaaa", font=("Arial", 8)
    ).pack()
