"""
client_system.py - Frame com métricas do sistema Cliente (Notebook/PC)
"""

import tkinter as tk
from tkinter import ttk


def create_client_system_frame(console, parent=None):
    """
    Cria frame com métricas do sistema cliente (notebook/PC)

    Args:
        console: Instância de ConsoleInterface
        parent: Widget pai (opcional, default: console.right_column)
    """
    if parent is None:
        parent = console.right_column

    system_frame = ttk.LabelFrame(
        parent, text="Sistema Cliente", style="Dark.TLabelframe"
    )
    system_frame.pack(fill=tk.X, padx=5, pady=5)

    # Frame interno com grid horizontal
    inner_frame = tk.Frame(system_frame, bg="#3c3c3c")
    inner_frame.pack(fill=tk.X, padx=5, pady=5)

    # Configurar colunas (6 métricas em linha)
    for i in range(6):
        inner_frame.grid_columnconfigure(i, weight=1)

    # CPU Usage
    cpu_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    cpu_frame.grid(row=0, column=0, padx=2, pady=2, sticky="nsew")

    tk.Label(
        cpu_frame, text="CPU", bg="#2c2c2c", fg="white", font=("Arial", 8, "bold")
    ).pack(pady=1)

    console.client_cpu_display = tk.Label(
        cpu_frame,
        textvariable=console.client_vars["cpu_usage"],
        bg="#2c2c2c",
        fg="#00ff88",
        font=("Arial", 12, "bold"),
    )
    console.client_cpu_display.pack()

    tk.Label(
        cpu_frame, text="%", bg="#2c2c2c", fg="#888888", font=("Arial", 7)
    ).pack()

    # CPU Temp (se disponível)
    temp_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    temp_frame.grid(row=0, column=1, padx=2, pady=2, sticky="nsew")

    tk.Label(
        temp_frame, text="Temp", bg="#2c2c2c", fg="white", font=("Arial", 8, "bold")
    ).pack(pady=1)

    console.client_temp_display = tk.Label(
        temp_frame,
        textvariable=console.client_vars["cpu_temp"],
        bg="#2c2c2c",
        fg="#00ff88",
        font=("Arial", 12, "bold"),
    )
    console.client_temp_display.pack()

    tk.Label(
        temp_frame, text="°C", bg="#2c2c2c", fg="#888888", font=("Arial", 7)
    ).pack()

    # RAM
    mem_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    mem_frame.grid(row=0, column=2, padx=2, pady=2, sticky="nsew")

    tk.Label(
        mem_frame, text="RAM", bg="#2c2c2c", fg="white", font=("Arial", 8, "bold")
    ).pack(pady=1)

    console.client_mem_display = tk.Label(
        mem_frame,
        textvariable=console.client_vars["mem_usage"],
        bg="#2c2c2c",
        fg="#00ff88",
        font=("Arial", 12, "bold"),
    )
    console.client_mem_display.pack()

    tk.Label(
        mem_frame, text="%", bg="#2c2c2c", fg="#888888", font=("Arial", 7)
    ).pack()

    # Net RX
    rx_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    rx_frame.grid(row=0, column=3, padx=2, pady=2, sticky="nsew")

    tk.Label(
        rx_frame, text="Net RX", bg="#2c2c2c", fg="white", font=("Arial", 8, "bold")
    ).pack(pady=1)

    console.client_rx_display = tk.Label(
        rx_frame,
        textvariable=console.client_vars["net_rx"],
        bg="#2c2c2c",
        fg="#66ccff",
        font=("Arial", 11, "bold"),
    )
    console.client_rx_display.pack()

    tk.Label(
        rx_frame, text="KB/s", bg="#2c2c2c", fg="#888888", font=("Arial", 7)
    ).pack()

    # Net TX
    tx_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    tx_frame.grid(row=0, column=4, padx=2, pady=2, sticky="nsew")

    tk.Label(
        tx_frame, text="Net TX", bg="#2c2c2c", fg="white", font=("Arial", 8, "bold")
    ).pack(pady=1)

    console.client_tx_display = tk.Label(
        tx_frame,
        textvariable=console.client_vars["net_tx"],
        bg="#2c2c2c",
        fg="#ffcc66",
        font=("Arial", 11, "bold"),
    )
    console.client_tx_display.pack()

    tk.Label(
        tx_frame, text="KB/s", bg="#2c2c2c", fg="#888888", font=("Arial", 7)
    ).pack()

    # Freq CPU
    freq_frame = tk.Frame(inner_frame, bg="#2c2c2c", relief=tk.RAISED, bd=1)
    freq_frame.grid(row=0, column=5, padx=2, pady=2, sticky="nsew")

    tk.Label(
        freq_frame, text="Freq", bg="#2c2c2c", fg="white", font=("Arial", 8, "bold")
    ).pack(pady=1)

    console.client_freq_display = tk.Label(
        freq_frame,
        textvariable=console.client_vars["cpu_freq"],
        bg="#2c2c2c",
        fg="#99ff99",
        font=("Arial", 11, "bold"),
    )
    console.client_freq_display.pack()

    tk.Label(
        freq_frame, text="MHz", bg="#2c2c2c", fg="#888888", font=("Arial", 7)
    ).pack()
