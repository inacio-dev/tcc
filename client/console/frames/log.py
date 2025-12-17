"""
log.py - Frame do console de log
"""

import tkinter as tk
from tkinter import scrolledtext, ttk


def create_log_frame(console):
    """
    Cria frame do console de log

    Args:
        console: Instância de ConsoleInterface
    """
    log_frame = ttk.LabelFrame(
        console.left_column, text="Console de Log", style="Dark.TLabelframe"
    )
    log_frame.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Botões de controle do log
    btn_frame = tk.Frame(log_frame, bg="#3c3c3c")
    btn_frame.pack(fill=tk.X, padx=5, pady=2)

    console.pause_btn = ttk.Button(
        btn_frame, text="Pausar", command=console.toggle_pause, style="Dark.TButton"
    )
    console.pause_btn.pack(side=tk.LEFT, padx=5)

    ttk.Button(
        btn_frame, text="Limpar", command=console.clear_log, style="Dark.TButton"
    ).pack(side=tk.LEFT, padx=5)

    console.autoscroll_var = tk.BooleanVar(value=True)
    ttk.Checkbutton(
        btn_frame,
        text="Auto-rolagem",
        variable=console.autoscroll_var,
        command=console.toggle_autoscroll,
        style="Dark.TCheckbutton",
    ).pack(side=tk.LEFT, padx=5)

    # Área de texto do log
    console.log_text = scrolledtext.ScrolledText(
        log_frame,
        wrap=tk.WORD,
        bg="#1e1e1e",
        fg="#ffffff",
        insertbackground="#ffffff",
        selectbackground="#0078d4",
        selectforeground="#ffffff",
        font=("Consolas", 10),
    )
    console.log_text.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)

    # Configurar tags para cores
    console.log_text.tag_configure("INFO", foreground="#00ff00")
    console.log_text.tag_configure("ERROR", foreground="#ff0000")
    console.log_text.tag_configure("WARNING", foreground="#ffff00")
    console.log_text.tag_configure("TIMESTAMP", foreground="#808080")
