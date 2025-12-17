"""
video.py - Frame para exibição do vídeo
"""

import tkinter as tk
from tkinter import ttk

# Importação do módulo de filtros PDI
try:
    from image_filters import ImageFilters, get_filters
    FILTERS_AVAILABLE = True
except ImportError:
    FILTERS_AVAILABLE = False


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

    # Frame para filtros PDI (apenas se disponível)
    if FILTERS_AVAILABLE:
        filter_frame = tk.Frame(video_frame, bg="#3c3c3c")
        filter_frame.pack(fill=tk.X, padx=5, pady=2)

        # Label do filtro
        ttk.Label(filter_frame, text="Filtro PDI:", style="Dark.TLabel").pack(
            side=tk.LEFT, padx=5
        )

        # Dropdown de filtros
        console.image_filters = get_filters()
        filter_names = ImageFilters.get_filter_names()
        console.filter_var = tk.StringVar(value=filter_names[0])  # "Original"

        filter_combo = ttk.Combobox(
            filter_frame,
            textvariable=console.filter_var,
            values=filter_names,
            state="readonly",
            width=20,
        )
        filter_combo.pack(side=tk.LEFT, padx=5)
        filter_combo.bind("<<ComboboxSelected>>", lambda e: _on_filter_change(console))

        # Descrição do filtro
        console.filter_desc_var = tk.StringVar(value="Sem filtro aplicado")
        ttk.Label(
            filter_frame,
            textvariable=console.filter_desc_var,
            style="Dark.TLabel",
            foreground="#888888",
        ).pack(side=tk.LEFT, padx=10)
    else:
        console.image_filters = None
        console.filter_var = None
        console.filter_desc_var = None


def _on_filter_change(console):
    """Callback quando o filtro é alterado"""
    if not FILTERS_AVAILABLE:
        return

    try:
        filter_name = console.filter_var.get()
        filter_key = ImageFilters.get_filter_by_name(filter_name)

        if filter_key:
            console.image_filters.set_filter(filter_key)
            info = console.image_filters.get_current_filter_info()
            console.filter_desc_var.set(info.get("description", ""))

            # Notifica o video_display sobre a mudança
            if hasattr(console, "video_display") and console.video_display:
                console.video_display.set_image_filter(console.image_filters)

    except Exception as e:
        print(f"[FILTER] Erro ao mudar filtro: {e}")
