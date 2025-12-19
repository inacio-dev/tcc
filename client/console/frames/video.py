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
        filter_frame = ttk.LabelFrame(
            video_frame, text="Filtros PDI (combináveis)", style="Dark.TLabelframe"
        )
        filter_frame.pack(fill=tk.X, padx=5, pady=2)

        # Inicializa filtros
        console.image_filters = get_filters()
        console.filter_vars = {}  # Variáveis para cada checkbox

        # Frame para checkboxes (grid 2 colunas)
        checkbox_frame = tk.Frame(filter_frame, bg="#3c3c3c")
        checkbox_frame.pack(fill=tk.X, padx=5, pady=2)

        # Cria checkboxes para cada filtro (exceto "original")
        filter_keys = [k for k in ImageFilters.get_filter_keys() if k != "original"]

        for i, filter_key in enumerate(filter_keys):
            filter_info = ImageFilters.FILTERS[filter_key]
            var = tk.BooleanVar(value=False)
            console.filter_vars[filter_key] = var

            # Checkbox com nome do filtro
            cb = ttk.Checkbutton(
                checkbox_frame,
                text=filter_info["name"],
                variable=var,
                style="Dark.TCheckbutton",
                command=lambda k=filter_key: _on_filter_toggle(console, k),
            )
            row = i // 3
            col = i % 3
            cb.grid(row=row, column=col, sticky="w", padx=5, pady=1)

        # Botão para limpar todos os filtros
        clear_btn = ttk.Button(
            checkbox_frame,
            text="Limpar",
            style="Dark.TButton",
            width=8,
            command=lambda: _clear_all_filters(console),
        )
        clear_btn.grid(
            row=(len(filter_keys) // 3) + 1, column=0, padx=5, pady=3, sticky="w"
        )

        # Label para mostrar filtros ativos
        console.filter_desc_var = tk.StringVar(value="Nenhum filtro ativo")
        ttk.Label(
            filter_frame,
            textvariable=console.filter_desc_var,
            style="Dark.TLabel",
            foreground="#888888",
        ).pack(side=tk.LEFT, padx=10, pady=2)
    else:
        console.image_filters = None
        console.filter_vars = {}
        console.filter_desc_var = None


def _on_filter_toggle(console, filter_key: str):
    """Callback quando um checkbox de filtro é alterado"""
    if not FILTERS_AVAILABLE:
        return

    try:
        # Obtém estado do checkbox
        is_active = console.filter_vars[filter_key].get()

        # Atualiza filtro
        console.image_filters.set_filter_active(filter_key, is_active)

        # Atualiza descrição com filtros ativos
        active = console.image_filters.get_active_filters()
        if active:
            names = [ImageFilters.FILTERS[k]["name"] for k in active]
            console.filter_desc_var.set(f"Ativos: {' + '.join(names)}")
        else:
            console.filter_desc_var.set("Nenhum filtro ativo")

        # Notifica o video_display sobre a mudança
        if hasattr(console, "video_display") and console.video_display:
            console.video_display.set_image_filter(console.image_filters)

    except Exception as e:
        print(f"[FILTER] Erro ao mudar filtro: {e}")


def _clear_all_filters(console):
    """Limpa todos os filtros ativos"""
    if not FILTERS_AVAILABLE:
        return

    try:
        # Limpa filtros
        console.image_filters.clear_filters()

        # Desmarca todos os checkboxes
        for var in console.filter_vars.values():
            var.set(False)

        # Atualiza descrição
        console.filter_desc_var.set("Nenhum filtro ativo")

        # Notifica o video_display
        if hasattr(console, "video_display") and console.video_display:
            console.video_display.set_image_filter(console.image_filters)

    except Exception as e:
        print(f"[FILTER] Erro ao limpar filtros: {e}")


def _on_filter_change(console):
    """Callback quando o filtro é alterado (legado - dropdown)"""
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
