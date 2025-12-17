"""
force_feedback.py - Frame com dados do force feedback da direção
"""

import tkinter as tk
from tkinter import ttk


def create_force_feedback_frame(console):
    """
    Cria frame com dados do force feedback da direção

    Args:
        console: Instância de ConsoleInterface
    """
    ff_frame = ttk.LabelFrame(
        console.left_column, text="Force Feedback - Direção", style="Dark.TLabelframe"
    )
    ff_frame.pack(fill=tk.X, padx=5, pady=5)

    # Frame interno para melhor organização
    inner_frame = tk.Frame(ff_frame, bg="#3c3c3c")
    inner_frame.pack(padx=10, pady=10, fill=tk.X)

    # === FORÇA NO VOLANTE ===
    steering_frame = tk.Frame(inner_frame, bg="#3c3c3c")
    steering_frame.pack(fill=tk.X, pady=5)

    ttk.Label(
        steering_frame,
        text="Força no Volante:",
        style="Dark.TLabel",
        font=("Arial", 10, "bold"),
    ).pack(side=tk.LEFT, padx=5)

    # LEDs de direção (esquerda/direita)
    console.ff_led_left = tk.Canvas(
        steering_frame, width=20, height=20, bg="#3c3c3c", highlightthickness=0
    )
    console.ff_led_left.pack(side=tk.LEFT, padx=5)
    console.ff_led_left_circle = console.ff_led_left.create_oval(
        2, 2, 18, 18, fill="#333333", outline="#666666"
    )

    ttk.Label(
        steering_frame, text="<-", style="Dark.TLabel", font=("Arial", 12, "bold")
    ).pack(side=tk.LEFT)

    # Valor da força (0-100%)
    console.steering_ff_intensity = ttk.Label(
        steering_frame,
        text="0",
        style="Dark.TLabel",
        font=("Arial", 14, "bold"),
        foreground="#00ff00",
    )
    console.steering_ff_intensity.pack(side=tk.LEFT, padx=5)

    ttk.Label(steering_frame, text="%", style="Dark.TLabel", font=("Arial", 10)).pack(
        side=tk.LEFT
    )

    ttk.Label(
        steering_frame, text="->", style="Dark.TLabel", font=("Arial", 12, "bold")
    ).pack(side=tk.LEFT, padx=(5, 0))

    console.ff_led_right = tk.Canvas(
        steering_frame, width=20, height=20, bg="#3c3c3c", highlightthickness=0
    )
    console.ff_led_right.pack(side=tk.LEFT, padx=5)
    console.ff_led_right_circle = console.ff_led_right.create_oval(
        2, 2, 18, 18, fill="#333333", outline="#666666"
    )

    # Descrição
    desc_label = tk.Label(
        inner_frame,
        text="Calculado com base em forças laterais (G) e rotação (gyro_z)",
        bg="#3c3c3c",
        fg="#888888",
        font=("Arial", 8),
        justify=tk.LEFT,
    )
    desc_label.pack(pady=(0, 5), anchor=tk.W)

    # === COMPONENTES DO CÁLCULO ===
    components_frame = ttk.LabelFrame(
        ff_frame, text="Componentes do Cálculo", style="Dark.TLabelframe"
    )
    components_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

    comp_inner = tk.Frame(components_frame, bg="#3c3c3c")
    comp_inner.pack(padx=10, pady=10, fill=tk.X)

    # Força Lateral (G)
    lateral_frame = tk.Frame(comp_inner, bg="#3c3c3c")
    lateral_frame.pack(fill=tk.X, pady=2)

    ttk.Label(lateral_frame, text="Força Lateral (G):", style="Dark.TLabel").pack(
        side=tk.LEFT, padx=5
    )
    ttk.Label(
        lateral_frame,
        textvariable=console.sensor_vars["g_force_lateral"],
        style="Dark.TLabel",
        font=("Arial", 10, "bold"),
    ).pack(side=tk.LEFT, padx=5)
    ttk.Label(lateral_frame, text="g", style="Dark.TLabel").pack(side=tk.LEFT)

    # Rotação (Yaw)
    yaw_frame = tk.Frame(comp_inner, bg="#3c3c3c")
    yaw_frame.pack(fill=tk.X, pady=2)

    ttk.Label(yaw_frame, text="Rotação (gyro_z):", style="Dark.TLabel").pack(
        side=tk.LEFT, padx=5
    )
    ttk.Label(
        yaw_frame,
        textvariable=console.sensor_vars["gyro_z"],
        style="Dark.TLabel",
        font=("Arial", 10, "bold"),
    ).pack(side=tk.LEFT, padx=5)
    ttk.Label(yaw_frame, text="°/s", style="Dark.TLabel").pack(side=tk.LEFT)

    # Fórmula (informativo)
    formula_label = tk.Label(
        comp_inner,
        text="Fórmula: (|G_lateral| x 50) + (|gyro_z| / 60 x 50)",
        bg="#3c3c3c",
        fg="#4488ff",
        font=("Arial", 8, "italic"),
        justify=tk.LEFT,
    )
    formula_label.pack(pady=(5, 0), anchor=tk.W)

    # === PARÂMETROS AJUSTÁVEIS ===
    params_frame = ttk.LabelFrame(
        ff_frame, text="Parâmetros de Force Feedback", style="Dark.TLabelframe"
    )
    params_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

    params_inner = tk.Frame(params_frame, bg="#3c3c3c")
    params_inner.pack(padx=10, pady=10, fill=tk.X)

    # Slider 1: Damping (Amortecimento)
    _create_ff_slider(
        params_inner,
        console,
        "Damping (Amortecimento):",
        "damping_value_label",
        console.ff_damping_var,
        console._on_ff_damping_change,
        "#4488ff",
        "Reduz oscilações e vibrações indesejadas no volante",
    )

    # Slider 2: Friction (Atrito)
    _create_ff_slider(
        params_inner,
        console,
        "Friction (Atrito):",
        "friction_value_label",
        console.ff_friction_var,
        console._on_ff_friction_change,
        "#ff8800",
        "Simula a resistência dos pneus (grip disponível)",
    )

    # Slider 3: Filter (Filtro)
    _create_ff_slider(
        params_inner,
        console,
        "Filter (Filtro):",
        "filter_value_label",
        console.ff_filter_var,
        console._on_ff_filter_change,
        "#00ff00",
        "Suaviza o sinal para uma experiência mais realista",
    )

    # Slider 4: Sensitivity (Sensibilidade)
    _create_ff_slider(
        params_inner,
        console,
        "Sensitivity (Sensibilidade):",
        "sensitivity_value_label",
        console.ff_sensitivity_var,
        console._on_ff_sensitivity_change,
        "#ff00ff",
        "Controla a intensidade da resposta aos eventos in-game",
    )


def _create_ff_slider(
    parent, console, label_text, label_attr, variable, callback, color, description
):
    """
    Cria um slider de force feedback

    Args:
        parent: Widget pai
        console: Instância de ConsoleInterface
        label_text: Texto do label
        label_attr: Nome do atributo para o label de valor
        variable: Variável Tkinter
        callback: Callback de mudança
        color: Cor do slider
        description: Descrição do parâmetro
    """
    frame = tk.Frame(parent, bg="#3c3c3c")
    frame.pack(fill=tk.X, pady=5)

    ttk.Label(
        frame,
        text=label_text,
        style="Dark.TLabel",
        font=("Arial", 9, "bold"),
    ).pack(side=tk.LEFT, padx=5)

    value_label = ttk.Label(
        frame,
        text=f"{int(variable.get())}%",
        style="Dark.TLabel",
        font=("Arial", 9),
    )
    value_label.pack(side=tk.RIGHT, padx=5)
    setattr(console, label_attr, value_label)

    slider = tk.Scale(
        parent,
        from_=0,
        to=100,
        resolution=5,
        orient=tk.HORIZONTAL,
        variable=variable,
        command=callback,
        bg="#3c3c3c",
        fg="white",
        highlightbackground="#3c3c3c",
        troughcolor="#2c2c2c",
        activebackground=color,
        showvalue=0,
    )
    slider.pack(fill=tk.X, pady=(0, 2))

    desc_label = tk.Label(
        parent,
        text=description,
        bg="#3c3c3c",
        fg="#888888",
        font=("Arial", 7),
        justify=tk.LEFT,
    )
    desc_label.pack(anchor=tk.W, pady=(0, 10))
