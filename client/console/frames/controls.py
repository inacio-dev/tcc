"""
controls.py - Frame de controles do veículo
"""

import tkinter as tk
from tkinter import ttk


def create_controls_frame(console):
    """
    Cria frame de controles do veículo

    Args:
        console: Instância de ConsoleInterface
    """
    control_frame = ttk.LabelFrame(
        console.right_column, text="Controles do Veículo", style="Dark.TLabelframe"
    )
    control_frame.pack(fill=tk.X, padx=5, pady=5)

    # Frame superior para botões
    btn_frame = tk.Frame(control_frame, bg="#3c3c3c")
    btn_frame.pack(fill=tk.X, padx=5, pady=2)

    # Status das configurações
    ttk.Label(btn_frame, text="Config:", style="Dark.TLabel").pack(
        side=tk.LEFT, padx=5
    )
    ttk.Label(
        btn_frame,
        textvariable=console.sensor_vars["accel_range"],
        style="Dark.TLabel",
    ).pack(side=tk.LEFT, padx=2)
    ttk.Label(
        btn_frame,
        textvariable=console.sensor_vars["gyro_range"],
        style="Dark.TLabel",
    ).pack(side=tk.LEFT, padx=2)

    # Frame para controle de freio
    brake_frame = tk.Frame(control_frame, bg="#3c3c3c")
    brake_frame.pack(fill=tk.X, padx=5, pady=5)

    ttk.Label(brake_frame, text="Balanço de Freio:", style="Dark.TLabel").pack(
        side=tk.LEFT, padx=5
    )

    # Slider para balanço de freio (0% = mais traseiro, 100% = mais dianteiro)
    console.brake_balance_scale = tk.Scale(
        brake_frame,
        from_=0,
        to=100,
        resolution=5,
        orient=tk.HORIZONTAL,
        length=200,
        variable=console.brake_balance_var,
        command=console._on_brake_balance_change,
        bg="#3c3c3c",
        fg="white",
        highlightbackground="#3c3c3c",
        troughcolor="#2c2c2c",
        activebackground="#0078d4",
    )
    console.brake_balance_scale.pack(side=tk.LEFT, padx=10)

    # Labels informativos
    ttk.Label(brake_frame, text="Traseiro", style="Dark.TLabel").pack(
        side=tk.LEFT, padx=2
    )
    ttk.Label(brake_frame, text="<-", style="Dark.TLabel").pack(side=tk.LEFT)
    ttk.Label(brake_frame, text="->", style="Dark.TLabel").pack(side=tk.LEFT)
    ttk.Label(brake_frame, text="Dianteiro", style="Dark.TLabel").pack(
        side=tk.LEFT, padx=2
    )

    # Label com valor atual
    console.brake_balance_label = ttk.Label(
        brake_frame, text="60% Dianteiro / 40% Traseiro", style="Dark.TLabel"
    )
    console.brake_balance_label.pack(side=tk.LEFT, padx=10)
