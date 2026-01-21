"""
camera_controls.py - Frame com controles de câmera (resolução, qualidade)
"""

import tkinter as tk
from tkinter import ttk

# Mapeamento de resolução para altura do display
RESOLUTION_HEIGHTS = {
    "480p": 360,   # 640x480 escalado
    "720p": 405,   # 1280x720 escalado (mantendo proporção 16:9)
    "1080p": 540,  # 1920x1080 escalado (mantendo proporção 16:9)
}


def create_camera_controls_frame(console):
    """
    Cria frame com controles de câmera (resolução, qualidade, etc.)

    Args:
        console: Instância de ConsoleInterface
    """
    camera_frame = ttk.LabelFrame(
        console.right_column, text="Câmera", style="Dark.TLabelframe"
    )
    camera_frame.pack(fill=tk.X, padx=5, pady=5)

    # Frame interno
    inner_frame = tk.Frame(camera_frame, bg="#3c3c3c")
    inner_frame.pack(fill=tk.X, padx=5, pady=5)

    # Label de resolução
    tk.Label(
        inner_frame,
        text="Resolução:",
        bg="#3c3c3c",
        fg="white",
        font=("Arial", 9, "bold"),
    ).pack(side=tk.LEFT, padx=(0, 10))

    # Variável para resolução atual
    console.camera_resolution_var = tk.StringVar(value="480p")

    # Botões de resolução
    resolutions = ["480p", "720p", "1080p"]
    console.resolution_buttons = {}

    for res in resolutions:
        btn = tk.Button(
            inner_frame,
            text=res,
            bg="#4c4c4c",
            fg="white",
            activebackground="#5c5c5c",
            activeforeground="white",
            font=("Arial", 9),
            relief=tk.RAISED,
            bd=1,
            padx=10,
            pady=2,
            command=lambda r=res: _on_resolution_change(console, r),
        )
        btn.pack(side=tk.LEFT, padx=2)
        console.resolution_buttons[res] = btn

    # Destacar resolução inicial
    _update_resolution_buttons(console, "480p")


def _on_resolution_change(console, resolution):
    """
    Callback quando um botão de resolução é clicado

    Args:
        console: Instância de ConsoleInterface
        resolution: Resolução selecionada ('480p', '720p', '1080p')
    """
    try:
        # Atualiza visual dos botões
        _update_resolution_buttons(console, resolution)

        # Atualiza variável
        console.camera_resolution_var.set(resolution)

        # Redimensiona o container de vídeo
        _resize_video_container(console, resolution)

        # Envia comando para o Raspberry Pi
        if hasattr(console, "network_client") and console.network_client:
            success = console.network_client.send_control_command(
                "CAMERA_RESOLUTION", resolution
            )
            if success:
                console.log("INFO", f"Resolução alterada para {resolution}")
            else:
                console.log("WARN", f"Falha ao enviar comando de resolução")
        else:
            console.log("WARN", "Cliente de rede não conectado")

    except Exception as e:
        console.log("ERROR", f"Erro ao alterar resolução: {e}")


def _resize_video_container(console, resolution):
    """
    Redimensiona o container de vídeo baseado na resolução

    Args:
        console: Instância de ConsoleInterface
        resolution: Resolução selecionada
    """
    try:
        if hasattr(console, "video_container") and console.video_container:
            new_height = RESOLUTION_HEIGHTS.get(resolution, 360)
            console.video_container.config(height=new_height)
            console.log("INFO", f"Display de vídeo redimensionado para {resolution}")
    except Exception as e:
        console.log("ERROR", f"Erro ao redimensionar vídeo: {e}")


def _update_resolution_buttons(console, selected_resolution):
    """
    Atualiza visual dos botões de resolução

    Args:
        console: Instância de ConsoleInterface
        selected_resolution: Resolução selecionada
    """
    if not hasattr(console, "resolution_buttons"):
        return

    for res, btn in console.resolution_buttons.items():
        if res == selected_resolution:
            btn.config(bg="#00aa44", fg="white", relief=tk.SUNKEN)
        else:
            btn.config(bg="#4c4c4c", fg="white", relief=tk.RAISED)
