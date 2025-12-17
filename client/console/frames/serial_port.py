"""
serial_port.py - Frame para seleção de porta serial ESP32
"""

import tkinter as tk
from tkinter import ttk


def create_serial_port_selector_frame(console):
    """
    Cria frame para seleção de porta serial ESP32

    Args:
        console: Instância de ConsoleInterface
    """
    serial_frame = ttk.LabelFrame(
        console.left_column, text="Conexão ESP32 Cockpit", style="Dark.TLabelframe"
    )
    serial_frame.pack(fill=tk.X, padx=5, pady=5)

    # Frame interno para organizar os controles
    inner_frame = tk.Frame(serial_frame, bg="#3c3c3c")
    inner_frame.pack(fill=tk.X, padx=5, pady=5)

    # Status da conexão serial
    status_frame = tk.Frame(inner_frame, bg="#3c3c3c")
    status_frame.pack(fill=tk.X, pady=2)

    ttk.Label(status_frame, text="Status:", style="Dark.TLabel").pack(
        side=tk.LEFT, padx=5
    )
    ttk.Label(
        status_frame, textvariable=console.serial_status_var, style="Dark.TLabel"
    ).pack(side=tk.LEFT)

    # Frame para seleção de porta
    port_frame = tk.Frame(inner_frame, bg="#3c3c3c")
    port_frame.pack(fill=tk.X, pady=5)

    ttk.Label(port_frame, text="Porta Serial:", style="Dark.TLabel").pack(
        side=tk.LEFT, padx=5
    )

    # Combobox para seleção de porta
    console.port_combobox = ttk.Combobox(
        port_frame,
        textvariable=console.serial_port_var,
        state="readonly",
        width=40,
    )
    console.port_combobox.pack(side=tk.LEFT, padx=5)

    # Botão para atualizar lista de portas
    ttk.Button(
        port_frame,
        text="Atualizar",
        command=console._refresh_serial_ports,
        style="Dark.TButton",
    ).pack(side=tk.LEFT, padx=2)

    # Frame para botões de conexão
    button_frame = tk.Frame(inner_frame, bg="#3c3c3c")
    button_frame.pack(fill=tk.X, pady=2)

    # Botão conectar
    console.connect_btn = ttk.Button(
        button_frame,
        text="Conectar",
        command=console._connect_serial,
        style="Dark.TButton",
    )
    console.connect_btn.pack(side=tk.LEFT, padx=5)

    # Botão desconectar
    console.disconnect_btn = ttk.Button(
        button_frame,
        text="Desconectar",
        command=console._disconnect_serial,
        style="Dark.TButton",
        state=tk.DISABLED,
    )
    console.disconnect_btn.pack(side=tk.LEFT, padx=5)

    # Atualizar lista de portas ao iniciar
    console._refresh_serial_ports()
