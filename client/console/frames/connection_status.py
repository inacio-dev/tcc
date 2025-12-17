"""
connection_status.py - Frame de status da conexão
"""

import tkinter as tk
from tkinter import ttk


def create_connection_status_frame(console):
    """
    Cria frame de status da conexão

    Args:
        console: Instância de ConsoleInterface
    """
    status_frame = ttk.LabelFrame(
        console.left_column, text="Status da Conexão", style="Dark.TLabelframe"
    )
    status_frame.pack(fill=tk.X, padx=5, pady=5)

    # Linha 1: Status e FPS
    ttk.Label(status_frame, text="Status:", style="Dark.TLabel").grid(
        row=0, column=0, sticky=tk.W, padx=5, pady=2
    )
    ttk.Label(
        status_frame, textvariable=console.connection_var, style="Dark.TLabel"
    ).grid(row=0, column=1, sticky=tk.W, padx=5, pady=2)

    ttk.Label(status_frame, text="FPS:", style="Dark.TLabel").grid(
        row=0, column=2, sticky=tk.W, padx=5, pady=2
    )
    ttk.Label(status_frame, textvariable=console.fps_var, style="Dark.TLabel").grid(
        row=0, column=3, sticky=tk.W, padx=5, pady=2
    )

    # Linha 2: Frame e Pacotes
    ttk.Label(status_frame, text="Frame:", style="Dark.TLabel").grid(
        row=1, column=0, sticky=tk.W, padx=5, pady=2
    )
    ttk.Label(
        status_frame, textvariable=console.frame_size_var, style="Dark.TLabel"
    ).grid(row=1, column=1, sticky=tk.W, padx=5, pady=2)

    ttk.Label(status_frame, text="Pacotes:", style="Dark.TLabel").grid(
        row=1, column=2, sticky=tk.W, padx=5, pady=2
    )
    ttk.Label(
        status_frame, textvariable=console.packets_var, style="Dark.TLabel"
    ).grid(row=1, column=3, sticky=tk.W, padx=5, pady=2)

    # Linha 3: Dados e Qualidade
    ttk.Label(status_frame, text="Dados:", style="Dark.TLabel").grid(
        row=2, column=0, sticky=tk.W, padx=5, pady=2
    )
    ttk.Label(status_frame, textvariable=console.data_var, style="Dark.TLabel").grid(
        row=2, column=1, sticky=tk.W, padx=5, pady=2
    )

    ttk.Label(status_frame, text="Qualidade:", style="Dark.TLabel").grid(
        row=2, column=2, sticky=tk.W, padx=5, pady=2
    )
    ttk.Label(
        status_frame, textvariable=console.quality_var, style="Dark.TLabel"
    ).grid(row=2, column=3, sticky=tk.W, padx=5, pady=2)
