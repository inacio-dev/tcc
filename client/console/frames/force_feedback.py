"""
force_feedback.py - Frame com dados do force feedback da direção
"""

import threading
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
        text="7 efeitos: spring/damper/friction/inertia + constant + rumble + periodic (×FF_GAIN)",
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
        text="FF_CONSTANT: (|G_lateral| x 50) + (|gyro_z| / 60 x 50) x sensitivity",
        bg="#3c3c3c",
        fg="#4488ff",
        font=("Arial", 8, "italic"),
        justify=tk.LEFT,
    )
    formula_label.pack(pady=(5, 0), anchor=tk.W)

    # === MONITOR DE EFEITOS ATIVOS ===
    monitor_frame = ttk.LabelFrame(
        ff_frame, text="Efeitos Ativos (tempo real)", style="Dark.TLabelframe"
    )
    monitor_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

    monitor_inner = tk.Frame(monitor_frame, bg="#3c3c3c")
    monitor_inner.pack(padx=10, pady=8, fill=tk.X)

    ff_vars = console.ff_monitor_vars

    # Contexto de condução (linha destaque)
    ctx_frame = tk.Frame(monitor_inner, bg="#3c3c3c")
    ctx_frame.pack(fill=tk.X, pady=(0, 5))
    tk.Label(ctx_frame, text="Contexto:", bg="#3c3c3c", fg="#aaaaaa",
             font=("Consolas", 8)).pack(side=tk.LEFT)
    tk.Label(ctx_frame, textvariable=ff_vars["ff_context"], bg="#3c3c3c",
             fg="#ffcc00", font=("Consolas", 9, "bold")).pack(side=tk.LEFT, padx=5)

    # Efeitos dinâmicos (atualizados por pacote BMI160)
    _create_monitor_row(monitor_inner, "FF_CONSTANT", ff_vars["ff_constant"], "#ff8800")
    _create_monitor_row(monitor_inner, "FF_RUMBLE  ", ff_vars["ff_rumble"], "#ff4444")
    _create_monitor_row(monitor_inner, "FF_PERIODIC", ff_vars["ff_periodic"], "#44ff44")
    _create_monitor_row(monitor_inner, "FF_INERTIA ", ff_vars["ff_inertia"], "#8888ff")

    # Separador
    tk.Frame(monitor_inner, bg="#555555", height=1).pack(fill=tk.X, pady=3)

    # Efeitos condicionais (sliders)
    _create_monitor_row(monitor_inner, "FF_SPRING  ", ff_vars["ff_spring"], "#ff00ff")
    _create_monitor_row(monitor_inner, "FF_DAMPER  ", ff_vars["ff_damper"], "#4488ff")
    _create_monitor_row(monitor_inner, "FF_FRICTION", ff_vars["ff_friction"], "#ff8800")

    # === DETECÇÃO DE EVENTOS (jerk) ===
    events_frame = ttk.LabelFrame(
        ff_frame, text="Detecção de Eventos (histórico BMI160)", style="Dark.TLabelframe"
    )
    events_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

    events_inner = tk.Frame(events_frame, bg="#3c3c3c")
    events_inner.pack(padx=10, pady=8, fill=tk.X)

    _create_monitor_row(events_inner, "Jerk frontal ", ff_vars["ff_jerk_frontal"], "#cccccc")
    _create_monitor_row(events_inner, "Jerk vertical", ff_vars["ff_jerk_vertical"], "#cccccc")
    _create_monitor_row(events_inner, "Jerk throttle", ff_vars["ff_jerk_throttle"], "#44ff44")
    _create_monitor_row(events_inner, "Jerk brake   ", ff_vars["ff_jerk_brake"], "#ff4444")
    _create_monitor_row(events_inner, "Jerk steering", ff_vars["ff_jerk_steering"], "#ffcc00")
    _create_monitor_row(events_inner, "Rugosidade   ", ff_vars["ff_roughness"], "#8888ff")

    # === PARÂMETROS AJUSTÁVEIS ===
    params_frame = ttk.LabelFrame(
        ff_frame, text="Parâmetros FF (7 efeitos hardware)", style="Dark.TLabelframe"
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
        "FF_DAMPER: resistência proporcional à velocidade do volante (hardware ~1kHz)",
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
        "FF_FRICTION: resistência constante ao movimento, simula grip do pneu (hardware ~1kHz)",
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
        "Suavização EMA no FF_CONSTANT (remove ruído dos sensores BMI160)",
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
        "FF_SPRING centering + FF_CONSTANT multiplier + FF_INERTIA base (~1kHz)",
    )

    # Slider 5: Max Force (Limite do motor)
    _create_ff_slider(
        params_inner,
        console,
        "Max Force (Limite Motor):",
        "max_force_value_label",
        console.ff_max_force_var,
        console._on_ff_max_force_change,
        "#ff4444",
        "FF_GAIN: limite global dos 7 efeitos no hardware (25%+ TRAVA!)",
    )

    # === BOTÃO DE TESTE FF ===
    test_frame = tk.Frame(ff_frame, bg="#3c3c3c")
    test_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

    console.ff_test_btn = tk.Button(
        test_frame,
        text="Testar FF (direita → esquerda → vibrar)",
        bg="#555555",
        fg="white",
        activebackground="#777777",
        activeforeground="white",
        font=("Arial", 9, "bold"),
        command=lambda: _run_ff_test(console),
    )
    console.ff_test_btn.pack(fill=tk.X, padx=5, pady=5)

    console.ff_test_status = tk.Label(
        test_frame, text="", bg="#3c3c3c", fg="#888888", font=("Arial", 8)
    )
    console.ff_test_status.pack(anchor=tk.W, padx=5)


def _create_monitor_row(parent, label, var, color):
    """Cria uma linha de monitoramento: label + valor colorido"""
    row = tk.Frame(parent, bg="#3c3c3c")
    row.pack(fill=tk.X, pady=1)
    tk.Label(row, text=label, bg="#3c3c3c", fg="#aaaaaa",
             font=("Consolas", 8), width=14, anchor=tk.W).pack(side=tk.LEFT)
    tk.Label(row, textvariable=var, bg="#3c3c3c", fg=color,
             font=("Consolas", 9, "bold"), anchor=tk.W).pack(side=tk.LEFT, padx=5)


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


def _run_ff_test(console):
    """
    Teste de FF criando efeitos do ZERO (como test_g923.py).
    Não usa g923_manager — acessa o device diretamente para diagnóstico.
    """
    import time

    g923 = getattr(console, "g923_manager", None)
    if not g923 or not g923.is_connected():
        console.ff_test_status.config(text="G923 não conectado!", fg="#ff4444")
        return

    dev = g923.device
    if not dev:
        console.ff_test_status.config(text="Device evdev não disponível!", fg="#ff4444")
        return

    console.ff_test_btn.config(state=tk.DISABLED, text="Testando...")
    log_lines = []

    def _log(msg):
        log_lines.append(msg)
        console.root.after(0, lambda m=msg: console.ff_test_status.config(
            text=m, fg="#ffcc00"))

    def _test_sequence():
        from evdev import ecodes, ff as evff

        test_ids = []
        try:
            # FF_GAIN 100% para o teste
            _log("Gain → 100%")
            original_gain = g923.ff_max_percent
            dev.write(ecodes.EV_FF, ecodes.FF_GAIN, 0xFFFF)
            time.sleep(0.1)

            # --- TESTE 1: FF_CONSTANT DIREITA (novo efeito, id=-1) ---
            _log("1/4: CONSTANT direita 15% (novo efeito)...")
            try:
                level = int(32767 * 0.15)
                eff = evff.Effect(
                    ecodes.FF_CONSTANT, -1, 0xC000,
                    evff.Trigger(0, 0), evff.Replay(0, 0),
                    evff.EffectType(ff_constant_effect=evff.Constant(
                        level, evff.Envelope(0, 0, 0, 0))),
                )
                eid = dev.upload_effect(eff)
                dev.write(ecodes.EV_FF, eid, 1)
                test_ids.append(eid)
                _log(f"1/4: DIREITA ativo (id={eid}, level={level})")
            except Exception as e:
                _log(f"1/4: ERRO - {e}")
            time.sleep(1.5)

            # Para efeito anterior
            if test_ids:
                dev.write(ecodes.EV_FF, test_ids[-1], 0)
                dev.erase_effect(test_ids.pop())

            # --- TESTE 2: FF_CONSTANT ESQUERDA ---
            _log("2/4: CONSTANT esquerda 15%...")
            try:
                eff = evff.Effect(
                    ecodes.FF_CONSTANT, -1, 0x4000,
                    evff.Trigger(0, 0), evff.Replay(0, 0),
                    evff.EffectType(ff_constant_effect=evff.Constant(
                        level, evff.Envelope(0, 0, 0, 0))),
                )
                eid = dev.upload_effect(eff)
                dev.write(ecodes.EV_FF, eid, 1)
                test_ids.append(eid)
                _log(f"2/4: ESQUERDA ativo (id={eid})")
            except Exception as e:
                _log(f"2/4: ERRO - {e}")
            time.sleep(1.5)

            if test_ids:
                dev.write(ecodes.EV_FF, test_ids[-1], 0)
                dev.erase_effect(test_ids.pop())

            # --- TESTE 3: FF_PERIODIC (vibração senoidal 8Hz) ---
            _log("3/4: PERIODIC sine 8Hz magnitude 80%...")
            try:
                mag = int(32767 * 0.80)
                per = evff.Periodic(
                    ecodes.FF_SINE, 125, mag, 0, 0,
                    evff.Envelope(0, 0, 0, 0),
                )
                eff = evff.Effect(
                    ecodes.FF_PERIODIC, -1, 0,
                    evff.Trigger(0, 0), evff.Replay(0, 0),
                    evff.EffectType(ff_periodic_effect=per),
                )
                eid = dev.upload_effect(eff)
                dev.write(ecodes.EV_FF, eid, 1)
                test_ids.append(eid)
                _log(f"3/4: PERIODIC ativo (id={eid}, mag={mag})")
            except Exception as e:
                _log(f"3/4: ERRO - {e}")
            time.sleep(2.0)

            # --- TESTE 4: FF_RUMBLE ---
            # Para periodic primeiro
            if test_ids:
                dev.write(ecodes.EV_FF, test_ids[-1], 0)
                dev.erase_effect(test_ids.pop())

            _log("4/4: RUMBLE strong=100% weak=100%...")
            try:
                eff = evff.Effect(
                    ecodes.FF_RUMBLE, -1, 0,
                    evff.Trigger(0, 0), evff.Replay(0, 0),
                    evff.EffectType(ff_rumble_effect=evff.Rumble(65535, 65535)),
                )
                eid = dev.upload_effect(eff)
                dev.write(ecodes.EV_FF, eid, 1)
                test_ids.append(eid)
                _log(f"4/4: RUMBLE ativo (id={eid})")
            except Exception as e:
                _log(f"4/4: RUMBLE ERRO - {e}")
            time.sleep(2.0)

        except Exception as e:
            _log(f"Erro geral: {e}")
        finally:
            # Limpa todos os efeitos de teste
            for eid in test_ids:
                try:
                    dev.write(ecodes.EV_FF, eid, 0)
                    dev.erase_effect(eid)
                except Exception:
                    pass

            # Restaura FF_GAIN
            try:
                gain = int(original_gain / 100.0 * 0xFFFF)
                dev.write(ecodes.EV_FF, ecodes.FF_GAIN, gain)
            except Exception:
                pass

            # Mostra resumo
            summary = " | ".join(log_lines)
            console.root.after(0, lambda: console.ff_test_status.config(
                text=summary, fg="#44ff44"))
            console.root.after(0, lambda: console.ff_test_btn.config(
                state=tk.NORMAL, text="Testar FF (direita → esquerda → vibrar)"))

    threading.Thread(target=_test_sequence, daemon=True, name="FF-Test").start()
