"""
instrument_panel.py - Painel de instrumentos (RPM, marcha, velocidade, temperatura)
"""

import tkinter as tk
from tkinter import ttk


def create_instrument_panel(console):
    """
    Cria painel de instrumentos (RPM, marcha, velocidade)

    Args:
        console: Instância de ConsoleInterface
    """
    instrument_frame = ttk.LabelFrame(
        console.left_column, text="Painel de Instrumentos", style="Dark.TLabelframe"
    )
    instrument_frame.pack(fill=tk.X, padx=5, pady=5)

    # Frame interno para organizar os instrumentos
    instruments_inner = tk.Frame(instrument_frame, bg="#3c3c3c")
    instruments_inner.pack(fill=tk.X, padx=10, pady=10)

    # Conta-giros (RPM) - Lado esquerdo
    rpm_frame = tk.Frame(instruments_inner, bg="#2c2c2c", relief=tk.RAISED, bd=2)
    rpm_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    tk.Label(
        rpm_frame,
        text="ZONA DE EFICIÊNCIA",
        bg="#2c2c2c",
        fg="white",
        font=("Arial", 10, "bold"),
    ).pack(pady=5)

    # RPM em fonte grande
    console.rpm_display = tk.Label(
        rpm_frame,
        textvariable=console.rpm_var,
        bg="#2c2c2c",
        fg="#00ff00",
        font=("Digital-7", 24, "bold"),
    )
    console.rpm_display.pack(pady=5)

    tk.Label(
        rpm_frame, text="% IDEAL", bg="#2c2c2c", fg="#cccccc", font=("Arial", 8)
    ).pack()

    # Marcha - Centro
    gear_frame = tk.Frame(instruments_inner, bg="#2c2c2c", relief=tk.RAISED, bd=2)
    gear_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    tk.Label(
        gear_frame,
        text="MARCHA",
        bg="#2c2c2c",
        fg="white",
        font=("Arial", 10, "bold"),
    ).pack(pady=5)

    # Marcha em fonte muito grande
    console.gear_display = tk.Label(
        gear_frame,
        textvariable=console.gear_var,
        bg="#2c2c2c",
        fg="#ffaa00",
        font=("Arial", 36, "bold"),
    )
    console.gear_display.pack(pady=10)

    tk.Label(
        gear_frame, text="ª", bg="#2c2c2c", fg="#cccccc", font=("Arial", 12)
    ).pack()

    # Motor e Velocidade - Lado direito
    speed_frame = tk.Frame(instruments_inner, bg="#2c2c2c", relief=tk.RAISED, bd=2)
    speed_frame.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=5)

    tk.Label(
        speed_frame,
        text="MOTOR",
        bg="#2c2c2c",
        fg="white",
        font=("Arial", 10, "bold"),
    ).pack(pady=5)

    # Throttle
    throttle_inner = tk.Frame(speed_frame, bg="#2c2c2c")
    throttle_inner.pack(fill=tk.X, pady=2)

    tk.Label(
        throttle_inner,
        text="Acelerador:",
        bg="#2c2c2c",
        fg="#cccccc",
        font=("Arial", 8),
    ).pack(side=tk.LEFT)
    tk.Label(
        throttle_inner,
        textvariable=console.throttle_var,
        bg="#2c2c2c",
        fg="#ff6600",
        font=("Arial", 14, "bold"),
    ).pack(side=tk.RIGHT)

    # Temperatura DS18B20 - Painel adicional na linha inferior
    temp_frame = tk.Frame(instruments_inner, bg="#2c2c2c", relief=tk.RAISED, bd=2)
    temp_frame.pack(side=tk.RIGHT, fill=tk.X, expand=True, padx=5)

    tk.Label(
        temp_frame,
        text="TEMP DS18B20",
        bg="#2c2c2c",
        fg="white",
        font=("Arial", 10, "bold"),
    ).pack(pady=5)

    # Display de temperatura com cor baseada na faixa
    console.temp_display = tk.Label(
        temp_frame,
        textvariable=console.sensor_vars["temperature_c"],
        bg="#2c2c2c",
        fg="#00ff88",
        font=("Digital-7", 20, "bold"),
    )
    console.temp_display.pack(pady=5)

    tk.Label(
        temp_frame, text="°C", bg="#2c2c2c", fg="#cccccc", font=("Arial", 10)
    ).pack()

