#!/usr/bin/env python3
"""
video_display.py - Gerenciamento da Exibição de Vídeo (MJPEG + Tkinter)
Responsável por decodificar vídeo MJPEG e exibir frames na interface integrada

CARACTERÍSTICAS:
===============
- Decodificação MJPEG (cada frame é JPEG independente)
- Redimensionamento automático
- Estatísticas de FPS em tempo real
- Tratamento de erros robusto
- Integração completa com Tkinter

NOTA: H.264 foi removido devido a problemas de distorção causados por
perda de pacotes UDP (P-frames dependem de frames anteriores).
MJPEG transmite frames independentes, eliminando este problema.
Ver: docs/CAMERA_VIDEO_ISSUES.md
"""

import threading
import time
import tkinter as tk
from typing import Optional

import cv2
import numpy as np
from PIL import Image, ImageTk


class VideoDisplay:
    """Gerencia a exibição de vídeo do veículo F1 (MJPEG + Tkinter)"""

    def __init__(self, video_queue=None, log_queue=None):
        """
        Inicializa o display de vídeo

        Args:
            video_queue (Queue): Fila de frames de vídeo
            log_queue (Queue): Fila para mensagens de log
        """
        self.video_queue = video_queue
        self.log_queue = log_queue

        # Estatísticas
        self.start_time = time.time()
        self.frame_count = 0
        self.last_fps_time = time.time()
        self.current_fps = 0

        # Controle de execução
        self.is_running = False

        # Frame atual
        self.last_frame = None
        self.last_frame_time = time.time()

        # Lock para thread safety
        self.frame_lock = threading.Lock()

        # Integração com Tkinter
        self.tkinter_label = None
        self.status_callback = None

        # Filtro de imagem PDI (None = sem filtro)
        self.image_filter = None

        self._log("INFO", "VideoDisplay inicializado (MJPEG)")

    def _log(self, level, message):
        """Envia mensagem para fila de log"""
        if self.log_queue:
            self.log_queue.put((level, message))
        else:
            print(f"[VIDEO-{level}] {message}")

    def set_tkinter_label(self, label):
        """Define o label Tkinter para exibir vídeo"""
        self.tkinter_label = label
        self._log("INFO", "Label Tkinter configurado")

    def set_status_callback(self, callback):
        """Define callback para atualizar status do vídeo"""
        self.status_callback = callback

    def set_image_filter(self, image_filter):
        """
        Define o filtro de imagem PDI a ser aplicado nos frames

        Args:
            image_filter: Instância de ImageFilters ou None para desativar
        """
        self.image_filter = image_filter
        if image_filter:
            info = image_filter.get_current_filter_info()
            self._log("INFO", f"Filtro PDI: {info.get('name', 'Desconhecido')}")

    def update_tkinter_frame(self, frame):
        """Atualiza frame no label Tkinter (otimizado para baixo delay)"""
        try:
            # Verifica se ainda está rodando e se o label existe
            if not self.is_running or not self.tkinter_label:
                return

            # Verifica se o widget Tkinter ainda é válido
            try:
                if not self.tkinter_label.winfo_exists():
                    return
            except Exception:
                return

            height, width = frame.shape[:2]

            # Conversão BGR→RGB
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # PIL Image
            pil_image = Image.fromarray(rgb_frame, mode="RGB")

            # PhotoImage
            photo = ImageTk.PhotoImage(image=pil_image)

            # Atualizar label
            try:
                self.tkinter_label.configure(image=photo)
                self.tkinter_label.image = photo
            except (tk.TclError, RuntimeError):
                # Tkinter foi destruído
                return

            # Atualizar status
            if self.status_callback and self.is_running:
                status = {
                    "connected": True,
                    "resolution": f"{width}x{height}",
                    "fps": self.current_fps,
                    "codec": "MJPEG",
                }
                try:
                    self.status_callback(status)
                except Exception:
                    pass

        except Exception:
            # Ignora erros durante shutdown
            pass

    def display_no_signal(self):
        """Exibe mensagem de 'Sem Sinal' no Tkinter"""
        try:
            # Verifica se ainda está rodando e se o label existe
            if not self.is_running or not self.tkinter_label:
                return

            # Verifica se o widget Tkinter ainda é válido
            try:
                if not self.tkinter_label.winfo_exists():
                    return
            except Exception:
                return

            self.tkinter_label.configure(
                image="",
                text="Sem Sinal\n\nAguardando vídeo do Raspberry Pi...",
                fg="red",
                bg="#1a1a1a",
                font=("Arial", 12),
            )
            self.tkinter_label.image = None

            if self.status_callback and self.is_running:
                status = {
                    "connected": False,
                    "resolution": "N/A",
                    "fps": 0,
                    "codec": "N/A",
                }
                try:
                    self.status_callback(status)
                except Exception:
                    pass

        except Exception:
            # Ignora erros durante shutdown
            pass

    def add_overlay_info(self, frame):
        """Adiciona informações overlay no frame"""
        try:
            if self.frame_count % 5 != 0:
                return frame

            fps_text = f"MJPEG | FPS: {self.current_fps:.1f}"
            resolution_text = f"{frame.shape[1]}x{frame.shape[0]}"

            # Adiciona info do filtro se ativo
            filter_text = ""
            if self.image_filter:
                info = self.image_filter.get_current_filter_info()
                if info.get("key") != "original":
                    gpu_tag = " [GPU]" if info.get("gpu") else ""
                    filter_text = f"Filtro: {info.get('name', '')}{gpu_tag}"

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            color = (0, 255, 0)
            thickness = 1

            cv2.putText(frame, fps_text, (10, 25), font, font_scale, color, thickness)
            cv2.putText(
                frame, resolution_text, (10, 50), font, font_scale, color, thickness
            )

            if filter_text:
                cv2.putText(
                    frame,
                    filter_text,
                    (10, 75),
                    font,
                    font_scale,
                    (255, 255, 0),
                    thickness,
                )

            return frame
        except Exception:
            return frame

    def display_frame(self, frame):
        """
        Exibe frame no Tkinter

        Args:
            frame (np.ndarray): Frame para exibir
        """
        try:
            with self.frame_lock:
                # Aplica filtro PDI se configurado
                if self.image_filter:
                    frame = self.image_filter.apply(frame)

                frame_with_overlay = self.add_overlay_info(frame.copy())

                if self.tkinter_label:
                    self.update_tkinter_frame(frame_with_overlay)

                self.last_frame = frame.copy()
                self.last_frame_time = time.time()
                self.update_statistics()

        except Exception as e:
            self._log("ERROR", f"Erro ao exibir frame: {e}")

    def update_statistics(self):
        """Atualiza estatísticas de FPS"""
        current_time = time.time()
        self.frame_count += 1

        if current_time - self.last_fps_time >= 1.0:
            elapsed = current_time - self.last_fps_time
            self.current_fps = self.frame_count / elapsed if elapsed > 0 else 0
            self.frame_count = 0
            self.last_fps_time = current_time

    def _decode_frame(self, frame_data: bytes) -> Optional[np.ndarray]:
        """
        Decodifica frame MJPEG

        Args:
            frame_data: Bytes do frame JPEG

        Returns:
            np.ndarray em formato BGR ou None
        """
        if not frame_data:
            return None

        try:
            # Decodifica JPEG
            nparr = np.frombuffer(frame_data, dtype=np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return frame
        except Exception:
            return None

    def process_video_queue(self):
        """Processa frames da fila de vídeo (MJPEG)"""
        try:
            latest_frame = None
            frames_decoded = 0
            max_frames = 10  # Limita para não travar se fila acumular muito

            while not self.video_queue.empty() and frames_decoded < max_frames:
                frame_data = self.video_queue.get_nowait()
                frames_decoded += 1

                if frame_data is None:
                    continue

                if isinstance(frame_data, bytes):
                    frame = self._decode_frame(frame_data)
                else:
                    frame = frame_data

                # Mantém sempre o frame mais recente decodificado com sucesso
                if frame is not None:
                    latest_frame = frame

            # Exibe apenas o frame mais recente
            if latest_frame is not None:
                self.display_frame(latest_frame)

        except Exception as e:
            self._log("ERROR", f"Erro ao processar fila de vídeo: {e}")

    def run_display(self):
        """Loop principal de exibição de vídeo"""
        self._log("INFO", "Iniciando display de vídeo (MJPEG)...")

        self.is_running = True
        no_signal_displayed = False
        last_frame_time = time.time()

        try:
            while self.is_running:
                try:
                    # Aguarda frame com timeout de 100ms (bloqueia até chegar frame)
                    frame_data = self.video_queue.get(timeout=0.1)
                    latest_frame = None

                    # Processa o frame recebido
                    if frame_data is not None:
                        if isinstance(frame_data, bytes):
                            frame = self._decode_frame(frame_data)
                        else:
                            frame = frame_data
                        if frame is not None:
                            latest_frame = frame

                    # Se há mais frames na fila, processa todos
                    # (mas só exibe o último para não travar)
                    frames_extra = 0
                    while not self.video_queue.empty() and frames_extra < 5:
                        try:
                            extra_data = self.video_queue.get_nowait()
                            frames_extra += 1
                            if extra_data is not None:
                                if isinstance(extra_data, bytes):
                                    frame = self._decode_frame(extra_data)
                                else:
                                    frame = extra_data
                                if frame is not None:
                                    latest_frame = frame
                        except Exception:
                            break

                    # Exibe o frame mais recente
                    if latest_frame is not None:
                        self.display_frame(latest_frame)
                        last_frame_time = time.time()
                        no_signal_displayed = False

                except Exception:
                    # Timeout ou fila vazia - verifica se precisa mostrar "sem sinal"
                    current_time = time.time()
                    if current_time - last_frame_time > 2.0 and not no_signal_displayed:
                        self.display_no_signal()
                        no_signal_displayed = True

        except KeyboardInterrupt:
            self._log("INFO", "Display de vídeo interrompido pelo usuário")
        except Exception as e:
            self._log("ERROR", f"Erro no loop de exibição: {e}")
        finally:
            self.stop()

    def get_statistics(self):
        """Obtém estatísticas do display"""
        runtime = time.time() - self.start_time

        stats = {
            "fps": self.current_fps,
            "total_frames": self.frame_count,
            "runtime_seconds": runtime,
            "avg_fps": self.frame_count / runtime if runtime > 0 else 0,
            "last_frame_time": self.last_frame_time,
            "is_running": self.is_running,
            "codec": "MJPEG",
        }

        return stats

    def stop(self):
        """Para o display de vídeo"""
        if not self.is_running:
            return

        self.is_running = False

        # Não limpa tkinter_label aqui - será limpo pelo main thread
        # Isso evita o erro "Tcl_AsyncDelete: async handler deleted by the wrong thread"

        try:
            stats = self.get_statistics()
            self._log(
                "INFO",
                f"Display parado: {stats['total_frames']} frames, "
                f"{stats['avg_fps']:.1f} FPS médio",
            )
        except Exception:
            pass
