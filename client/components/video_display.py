#!/usr/bin/env python3
"""
video_display.py - Gerenciamento da Exibição de Vídeo (Tkinter apenas)
Responsável por exibir frames de vídeo recebidos do Raspberry Pi na interface integrada

CARACTERÍSTICAS:
===============
- Decodificação JPEG automática
- Redimensionamento automático
- Estatísticas de FPS em tempo real
- Tratamento de erros robusto
- Integração completa com Tkinter
"""

import cv2
import numpy as np
import time
import threading
import tkinter as tk
from PIL import Image, ImageTk


class VideoDisplay:
    """Gerencia a exibição de vídeo do carrinho F1 (Tkinter apenas)"""

    def __init__(
        self,
        video_queue=None,
        log_queue=None,
    ):
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

    def update_tkinter_frame(self, frame):
        """Atualiza frame no label Tkinter (otimizado para baixo delay)"""
        try:
            if not self.tkinter_label:
                return

            # Otimização 1: Redimensionar apenas se necessário
            height, width = frame.shape[:2]
            target_width = 320

            # Só redimensiona se for muito diferente do target
            if abs(width - target_width) > 50:
                aspect_ratio = height / width
                target_height = int(target_width * aspect_ratio)
                frame = cv2.resize(
                    frame,
                    (target_width, target_height),
                    interpolation=cv2.INTER_NEAREST,
                )

            # Otimização 2: Conversão BGR→RGB mais rápida
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Otimização 3: Usar modo direto do PIL (mais rápido)
            pil_image = Image.fromarray(rgb_frame, mode="RGB")

            # Otimização 4: PhotoImage direto sem cópia extra
            photo = ImageTk.PhotoImage(image=pil_image)

            # Atualizar label (try/except para evitar travamentos)
            try:
                self.tkinter_label.configure(image=photo)
                self.tkinter_label.image = photo  # Manter referência
            except tk.TclError:
                # Widget foi destruído, ignora
                return

            # Atualizar status se callback definido (assíncrono)
            if self.status_callback:
                status = {
                    "connected": True,
                    "resolution": f"{frame.shape[1]}x{frame.shape[0]}",
                    "fps": self.current_fps,
                }
                try:
                    self.status_callback(status)
                except:
                    pass  # Ignora erros de callback

        except Exception as e:
            self._log("ERROR", f"Erro ao atualizar frame Tkinter: {e}")

    def display_no_signal(self):
        """Exibe mensagem de 'Sem Sinal' no Tkinter"""
        try:
            if self.tkinter_label:
                # Atualizar texto do label para mostrar sem sinal
                self.tkinter_label.configure(
                    image="",
                    text="📡 Sem Sinal\n\nAguardando vídeo do Raspberry Pi...",
                    fg="red",
                    bg="#1a1a1a",
                    font=("Arial", 12),
                )
                self.tkinter_label.image = None

            # Atualizar status
            if self.status_callback:
                status = {"connected": False, "resolution": "N/A", "fps": 0}
                self.status_callback(status)

        except Exception as e:
            self._log("ERROR", f"Erro ao exibir 'sem sinal': {e}")

    def add_overlay_info(self, frame):
        """Adiciona informações overlay no frame (otimizado)"""
        try:
            # Otimização: Adiciona overlay apenas a cada 5 frames para economizar CPU
            if self.frame_count % 5 != 0:
                return frame

            # Informações para exibir (mais simples)
            fps_text = f"FPS: {self.current_fps:.1f}"
            resolution_text = f"{frame.shape[1]}x{frame.shape[0]}"

            # Configurações otimizadas
            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5  # Menor para ser mais rápido
            color = (0, 255, 0)
            thickness = 1  # Mais fino, mais rápido

            # Apenas informações essenciais
            cv2.putText(frame, fps_text, (10, 25), font, font_scale, color, thickness)
            cv2.putText(
                frame, resolution_text, (10, 50), font, font_scale, color, thickness
            )

            return frame
        except:
            # Ignora erros de overlay para não afetar performance
            return frame

    def display_frame(self, frame):
        """
        Exibe frame no Tkinter

        Args:
            frame (np.ndarray): Frame para exibir
        """
        try:
            with self.frame_lock:
                # Adiciona informações overlay
                frame_with_overlay = self.add_overlay_info(frame.copy())

                # Exibir no Tkinter
                if self.tkinter_label:
                    self.update_tkinter_frame(frame_with_overlay)

                # Armazena como último frame válido
                self.last_frame = frame.copy()
                self.last_frame_time = time.time()

                # Atualiza estatísticas
                self.update_statistics()

        except Exception as e:
            self._log("ERROR", f"Erro ao exibir frame: {e}")

    def update_statistics(self):
        """Atualiza estatísticas de FPS"""
        current_time = time.time()
        self.frame_count += 1

        # Calcula FPS a cada segundo
        if current_time - self.last_fps_time >= 1.0:
            elapsed = current_time - self.last_fps_time
            self.current_fps = self.frame_count / elapsed if elapsed > 0 else 0
            self.frame_count = 0
            self.last_fps_time = current_time

    def process_video_queue(self):
        """Processa frames da fila de vídeo (otimizado para baixo delay)"""
        try:
            # Otimização: Processa TODOS os frames disponíveis, descartando antigos
            frames_processed = 0
            latest_frame = None

            # Drena a fila e mantém apenas o frame mais recente
            while (
                not self.video_queue.empty()
                and self.is_running
                and frames_processed < 10
            ):
                frame_data = self.video_queue.get_nowait()
                frames_processed += 1

                if frame_data is None:
                    continue

                # Decodifica JPEG rapidamente
                if isinstance(frame_data, bytes):
                    nparr = np.frombuffer(frame_data, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                else:
                    frame = frame_data

                if frame is not None:
                    latest_frame = frame

            # Exibe apenas o frame mais recente para reduzir delay
            if latest_frame is not None:
                self.display_frame(latest_frame)

                # Se processamos muitos frames, significa que há delay acumulado
                if frames_processed > 3:
                    self._log(
                        "DEBUG",
                        f"Descartados {frames_processed-1} frames antigos para reduzir delay",
                    )

        except Exception as e:
            self._log("ERROR", f"Erro ao processar fila de vídeo: {e}")

    def run_display(self):
        """Loop principal de exibição de vídeo (modo Tkinter apenas)"""
        self._log("INFO", "Iniciando display de vídeo em modo Tkinter...")

        self.is_running = True
        no_signal_displayed = False
        last_frame_check = time.time()

        try:
            while self.is_running:
                current_time = time.time()

                # Processa fila de vídeo se disponível
                if self.video_queue and not self.video_queue.empty():
                    self.process_video_queue()
                    no_signal_displayed = False
                    last_frame_check = current_time

                else:
                    # Sem dados por mais de 2 segundos - mostra tela sem sinal
                    if (
                        current_time - last_frame_check > 2.0
                        and not no_signal_displayed
                    ):
                        self.display_no_signal()
                        no_signal_displayed = True

                    # Se tem último frame e não passou muito tempo, continua mostrando
                    elif (
                        self.last_frame is not None
                        and current_time - self.last_frame_time < 5.0
                    ):
                        self.display_frame(self.last_frame)

                # Sleep mais curto para menor delay
                time.sleep(0.016)  # ~60 FPS máximo

        except KeyboardInterrupt:
            self._log("INFO", "Display de vídeo interrompido pelo usuário")
        except Exception as e:
            self._log("ERROR", f"Erro no loop de exibição: {e}")
        finally:
            self.stop()

    def get_statistics(self):
        """
        Obtém estatísticas do display

        Returns:
            dict: Dicionário com estatísticas
        """
        runtime = time.time() - self.start_time

        return {
            "fps": self.current_fps,
            "total_frames": self.frame_count,
            "runtime_seconds": runtime,
            "avg_fps": self.frame_count / runtime if runtime > 0 else 0,
            "last_frame_time": self.last_frame_time,
            "is_running": self.is_running,
        }

    def stop(self):
        """Para o display de vídeo"""
        self._log("INFO", "Parando display de vídeo...")

        self.is_running = False

        # Estatísticas finais
        try:
            stats = self.get_statistics()
            self._log(
                "INFO",
                f"Estatísticas finais: {stats['total_frames']} frames, "
                f"{stats['avg_fps']:.1f} FPS médio, "
                f"{stats['runtime_seconds']:.1f}s de execução",
            )
        except:
            pass

        self._log("INFO", "Display de vídeo parado")
