"""
bmi160.py - Frame com dados do sensor BMI160
"""

import tkinter as tk
from tkinter import ttk


def create_bmi160_frame(console):
    """
    Cria frame com dados do BMI160

    Args:
        console: Instância de ConsoleInterface
    """
    sensor_frame = ttk.LabelFrame(
        console.left_column, text="Dados do BMI160", style="Dark.TLabelframe"
    )
    sensor_frame.pack(fill=tk.X, padx=5, pady=5)

    # Sub-frame para dados raw
    raw_frame = ttk.LabelFrame(
        sensor_frame, text="Raw (LSB)", style="Dark.TLabelframe"
    )
    raw_frame.pack(fill=tk.X, padx=5, pady=2)

    # Raw Acelerômetro
    ttk.Label(raw_frame, text="Accel:", style="Dark.TLabel").grid(
        row=0, column=0, padx=2
    )
    ttk.Label(raw_frame, text="X:", style="Dark.TLabel").grid(
        row=0, column=1, padx=2
    )
    ttk.Label(
        raw_frame,
        textvariable=console.sensor_vars["bmi160_accel_x_raw"],
        style="Dark.TLabel",
    ).grid(row=0, column=2, padx=2)
    ttk.Label(raw_frame, text="Y:", style="Dark.TLabel").grid(
        row=0, column=3, padx=2
    )
    ttk.Label(
        raw_frame,
        textvariable=console.sensor_vars["bmi160_accel_y_raw"],
        style="Dark.TLabel",
    ).grid(row=0, column=4, padx=2)
    ttk.Label(raw_frame, text="Z:", style="Dark.TLabel").grid(
        row=0, column=5, padx=2
    )
    ttk.Label(
        raw_frame,
        textvariable=console.sensor_vars["bmi160_accel_z_raw"],
        style="Dark.TLabel",
    ).grid(row=0, column=6, padx=2)

    # Raw Giroscópio
    ttk.Label(raw_frame, text="Gyro:", style="Dark.TLabel").grid(
        row=1, column=0, padx=2
    )
    ttk.Label(raw_frame, text="X:", style="Dark.TLabel").grid(
        row=1, column=1, padx=2
    )
    ttk.Label(
        raw_frame,
        textvariable=console.sensor_vars["bmi160_gyro_x_raw"],
        style="Dark.TLabel",
    ).grid(row=1, column=2, padx=2)
    ttk.Label(raw_frame, text="Y:", style="Dark.TLabel").grid(
        row=1, column=3, padx=2
    )
    ttk.Label(
        raw_frame,
        textvariable=console.sensor_vars["bmi160_gyro_y_raw"],
        style="Dark.TLabel",
    ).grid(row=1, column=4, padx=2)
    ttk.Label(raw_frame, text="Z:", style="Dark.TLabel").grid(
        row=1, column=5, padx=2
    )
    ttk.Label(
        raw_frame,
        textvariable=console.sensor_vars["bmi160_gyro_z_raw"],
        style="Dark.TLabel",
    ).grid(row=1, column=6, padx=2)

    # Sub-frame para dados físicos
    physical_frame = ttk.LabelFrame(
        sensor_frame, text="Físicos", style="Dark.TLabelframe"
    )
    physical_frame.pack(fill=tk.X, padx=5, pady=2)

    # Acelerômetro físico (m/s²)
    ttk.Label(physical_frame, text="Accel (m/s²):", style="Dark.TLabel").grid(
        row=0, column=0, padx=2
    )
    ttk.Label(physical_frame, text="X:", style="Dark.TLabel").grid(
        row=0, column=1, padx=2
    )
    ttk.Label(
        physical_frame,
        textvariable=console.sensor_vars["accel_x"],
        style="Dark.TLabel",
    ).grid(row=0, column=2, padx=2)
    ttk.Label(physical_frame, text="Y:", style="Dark.TLabel").grid(
        row=0, column=3, padx=2
    )
    ttk.Label(
        physical_frame,
        textvariable=console.sensor_vars["accel_y"],
        style="Dark.TLabel",
    ).grid(row=0, column=4, padx=2)
    ttk.Label(physical_frame, text="Z:", style="Dark.TLabel").grid(
        row=0, column=5, padx=2
    )
    ttk.Label(
        physical_frame,
        textvariable=console.sensor_vars["accel_z"],
        style="Dark.TLabel",
    ).grid(row=0, column=6, padx=2)

    # Giroscópio físico (°/s)
    ttk.Label(physical_frame, text="Gyro (°/s):", style="Dark.TLabel").grid(
        row=1, column=0, padx=2
    )
    ttk.Label(physical_frame, text="X:", style="Dark.TLabel").grid(
        row=1, column=1, padx=2
    )
    ttk.Label(
        physical_frame, textvariable=console.sensor_vars["gyro_x"], style="Dark.TLabel"
    ).grid(row=1, column=2, padx=2)
    ttk.Label(physical_frame, text="Y:", style="Dark.TLabel").grid(
        row=1, column=3, padx=2
    )
    ttk.Label(
        physical_frame, textvariable=console.sensor_vars["gyro_y"], style="Dark.TLabel"
    ).grid(row=1, column=4, padx=2)
    ttk.Label(physical_frame, text="Z:", style="Dark.TLabel").grid(
        row=1, column=5, padx=2
    )
    ttk.Label(
        physical_frame, textvariable=console.sensor_vars["gyro_z"], style="Dark.TLabel"
    ).grid(row=1, column=6, padx=2)

    # Sub-frame para forças G
    gforce_frame = ttk.LabelFrame(
        sensor_frame, text="Forças G", style="Dark.TLabelframe"
    )
    gforce_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(gforce_frame, text="Frontal:", style="Dark.TLabel").grid(
        row=0, column=0, padx=2
    )
    ttk.Label(
        gforce_frame,
        textvariable=console.sensor_vars["g_force_frontal"],
        style="Dark.TLabel",
    ).grid(row=0, column=1, padx=2)
    ttk.Label(gforce_frame, text="g", style="Dark.TLabel").grid(
        row=0, column=2, padx=2
    )

    ttk.Label(gforce_frame, text="Lateral:", style="Dark.TLabel").grid(
        row=0, column=3, padx=2
    )
    ttk.Label(
        gforce_frame,
        textvariable=console.sensor_vars["g_force_lateral"],
        style="Dark.TLabel",
    ).grid(row=0, column=4, padx=2)
    ttk.Label(gforce_frame, text="g", style="Dark.TLabel").grid(
        row=0, column=5, padx=2
    )

    ttk.Label(gforce_frame, text="Vertical:", style="Dark.TLabel").grid(
        row=0, column=6, padx=2
    )
    ttk.Label(
        gforce_frame,
        textvariable=console.sensor_vars["g_force_vertical"],
        style="Dark.TLabel",
    ).grid(row=0, column=7, padx=2)
    ttk.Label(gforce_frame, text="g", style="Dark.TLabel").grid(
        row=0, column=8, padx=2
    )

    # Velocidade calculada pelo BMI160
    velocity_frame = tk.LabelFrame(
        sensor_frame,
        text="Velocidade (Calculada)",
        bg="#3c3c3c",
        fg="white",
        font=("Arial", 9, "bold"),
    )
    velocity_frame.pack(fill=tk.X, padx=5, pady=2)

    ttk.Label(velocity_frame, text="Velocidade:", style="Dark.TLabel").grid(
        row=0, column=0, padx=5, sticky=tk.W
    )
    console.velocity_label = ttk.Label(
        velocity_frame, text="0.0 km/h", style="Dark.TLabel"
    )
    console.velocity_label.grid(row=0, column=1, padx=5, sticky=tk.W)
