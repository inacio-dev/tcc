"""
g923_status.py - Frame de status do Logitech G923
"""

import tkinter as tk
from tkinter import ttk


def create_g923_status_frame(console):
    """
    Cria frame de status do G923

    Args:
        console: Instancia de ConsoleInterface
    """
    g923_frame = ttk.LabelFrame(
        console.left_column, text="Volante G923", style="Dark.TLabelframe"
    )
    g923_frame.pack(fill=tk.X, padx=5, pady=5)

    inner_frame = tk.Frame(g923_frame, bg="#3c3c3c")
    inner_frame.pack(fill=tk.X, padx=5, pady=5)

    # Status da conexao
    status_frame = tk.Frame(inner_frame, bg="#3c3c3c")
    status_frame.pack(fill=tk.X, pady=2)

    ttk.Label(status_frame, text="Status:", style="Dark.TLabel").pack(
        side=tk.LEFT, padx=5
    )

    console.g923_status_label = ttk.Label(
        status_frame, textvariable=console.g923_status_var, style="Dark.TLabel"
    )
    console.g923_status_label.pack(side=tk.LEFT)

    # Indicador visual (circulo colorido)
    console.g923_indicator = tk.Canvas(
        status_frame, width=14, height=14, bg="#3c3c3c", highlightthickness=0
    )
    console.g923_indicator.pack(side=tk.RIGHT, padx=5)
    console.g923_indicator_circle = console.g923_indicator.create_oval(
        2, 2, 12, 12, fill="#ff4444", outline="#cc3333"
    )

    # Atualiza indicador baseado no estado
    def update_indicator(*args):
        status = console.g923_status_var.get()
        if "Conectado" in status:
            console.g923_indicator.itemconfig(
                console.g923_indicator_circle, fill="#00ff88", outline="#00cc66"
            )
        else:
            console.g923_indicator.itemconfig(
                console.g923_indicator_circle, fill="#ff4444", outline="#cc3333"
            )

    console.g923_status_var.trace_add("write", update_indicator)
