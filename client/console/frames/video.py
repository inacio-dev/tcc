"""
video.py - Frame para exibição do vídeo
"""

import tkinter as tk
from tkinter import ttk


def create_video_frame(console):
    """
    Cria frame para exibição do vídeo

    Args:
        console: Instância de ConsoleInterface
    """
    video_frame = ttk.LabelFrame(
        console.right_column, text="Vídeo da Câmera", style="Dark.TLabelframe"
    )
    video_frame.pack(fill=tk.X, padx=5, pady=5)

    # Frame interno para o vídeo (altura aumentada para resolução original da câmera)
    console.video_container = tk.Frame(video_frame, bg="#1a1a1a", height=480)
    console.video_container.pack(fill=tk.X, padx=5, pady=5)
    console.video_container.pack_propagate(False)  # Manter altura fixa

    # Label para exibir o vídeo (será atualizado pelo video_display)
    console.video_label = tk.Label(
        console.video_container,
        text="Aguardando vídeo...\nVídeo será exibido aqui quando conectado",
        bg="#1a1a1a",
        fg="white",
        font=("Arial", 10),
        justify=tk.CENTER,
    )
    console.video_label.pack(expand=True)

    # Frame para controles do vídeo
    video_controls = tk.Frame(video_frame, bg="#3c3c3c")
    video_controls.pack(fill=tk.X, padx=5, pady=2)

    # Status do vídeo
    console.video_status_var = tk.StringVar(value="Sem vídeo")
    ttk.Label(video_controls, text="Status:", style="Dark.TLabel").pack(
        side=tk.LEFT, padx=5
    )
    ttk.Label(
        video_controls, textvariable=console.video_status_var, style="Dark.TLabel"
    ).pack(side=tk.LEFT)

    # Resolução
    console.video_resolution_var = tk.StringVar(value="N/A")
    ttk.Label(video_controls, text="Resolução:", style="Dark.TLabel").pack(
        side=tk.LEFT, padx=(20, 5)
    )
    ttk.Label(
        video_controls, textvariable=console.video_resolution_var, style="Dark.TLabel"
    ).pack(side=tk.LEFT)
