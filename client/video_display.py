#!/usr/bin/env python3
"""
video_display.py - Gerenciamento da Exibição de Vídeo (H.264 + Tkinter)
Responsável por decodificar H.264 e exibir frames na interface integrada

CARACTERÍSTICAS:
===============
- Decodificação H.264 via PyAV (FFmpeg)
- Buffer de NAL units para stream contínuo
- Redimensionamento automático
- Estatísticas de FPS em tempo real
- Tratamento de erros robusto
- Integração completa com Tkinter
"""

import cv2
import numpy as np
import time
import threading
from typing import Optional
import tkinter as tk
from PIL import Image, ImageTk

# Tenta importar av (PyAV) para decodificação H.264
try:
    import av
    H264_AVAILABLE = True
except ImportError:
    H264_AVAILABLE = False
    print("⚠ PyAV não instalado. Execute: pip install av")
    print("  Fallback para decodificação JPEG")


class H264Decoder:
    """Decodificador H.264 usando PyAV (FFmpeg)"""

    def __init__(self):
        self.codec = None
        self.context = None
        self.is_initialized = False
        self.frames_decoded = 0
        self.errors = 0

    def initialize(self):
        """Inicializa o decoder H.264"""
        try:
            if not H264_AVAILABLE:
                return False

            self.codec = av.CodecContext.create('h264', 'r')
            self.codec.options = {
                'flags': 'low_delay',
                'flags2': 'fast',
            }
            self.is_initialized = True
            return True

        except Exception as e:
            print(f"Erro ao inicializar decoder H.264: {e}")
            self.is_initialized = False
            return False

    def decode(self, nal_data: bytes) -> Optional[np.ndarray]:
        """
        Decodifica NAL units H.264 para frame numpy

        Args:
            nal_data: Bytes contendo NAL units H.264

        Returns:
            np.ndarray em formato BGR (OpenCV) ou None
        """
        if not self.is_initialized or not nal_data:
            return None

        try:
            # Cria packet com os dados H.264
            packet = av.Packet(nal_data)

            # Decodifica
            frames = self.codec.decode(packet)

            for frame in frames:
                # Converte para numpy array (formato YUV → BGR)
                img = frame.to_ndarray(format='bgr24')
                self.frames_decoded += 1
                return img

            return None

        except Exception as e:
            self.errors += 1
            if self.errors <= 5:
                print(f"Erro decodificando H.264: {e}")
            return None

    def cleanup(self):
        """Libera recursos do decoder"""
        # PyAV codec context não tem método close(), apenas libera referência
        self.codec = None
        self.is_initialized = False


class VideoDisplay:
    """Gerencia a exibição de vídeo do carrinho F1 (H.264 + Tkinter)"""

    def __init__(self, video_queue=None, log_queue=None):
        """
        Inicializa o display de vídeo

        Args:
            video_queue (Queue): Fila de frames de vídeo
            log_queue (Queue): Fila para mensagens de log
        """
        self.video_queue = video_queue
        self.log_queue = log_queue

        # Decoder H.264
        self.h264_decoder = H264Decoder()
        self.use_h264 = False

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

        # Inicializa decoder H.264
        if H264_AVAILABLE:
            if self.h264_decoder.initialize():
                self.use_h264 = True
                self._log("INFO", "Decoder H.264 (PyAV/FFmpeg) inicializado")
            else:
                self._log("WARN", "Fallback para JPEG - decoder H.264 falhou")
        else:
            self._log("WARN", "PyAV não disponível - usando JPEG")

        self._log("INFO", "VideoDisplay inicializado")

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
                    "codec": "H.264" if self.use_h264 else "JPEG",
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
                status = {"connected": False, "resolution": "N/A", "fps": 0, "codec": "N/A"}
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

            codec_text = "H.264" if self.use_h264 else "JPEG"
            fps_text = f"{codec_text} | FPS: {self.current_fps:.1f}"
            resolution_text = f"{frame.shape[1]}x{frame.shape[0]}"

            font = cv2.FONT_HERSHEY_SIMPLEX
            font_scale = 0.5
            color = (0, 255, 0)
            thickness = 1

            cv2.putText(frame, fps_text, (10, 25), font, font_scale, color, thickness)
            cv2.putText(frame, resolution_text, (10, 50), font, font_scale, color, thickness)

            return frame
        except:
            return frame

    def display_frame(self, frame):
        """
        Exibe frame no Tkinter

        Args:
            frame (np.ndarray): Frame para exibir
        """
        try:
            with self.frame_lock:
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

    def _is_h264_data(self, data: bytes) -> bool:
        """Detecta se dados são H.264 (NAL units com start code)"""
        if len(data) < 4:
            return False
        # H.264 Annex B start codes: 0x00000001 ou 0x000001
        return (data[:4] == b'\x00\x00\x00\x01' or data[:3] == b'\x00\x00\x01')

    def _decode_frame(self, frame_data: bytes) -> Optional[np.ndarray]:
        """
        Decodifica frame (H.264 ou JPEG automaticamente)

        Args:
            frame_data: Bytes do frame codificado

        Returns:
            np.ndarray em formato BGR ou None
        """
        if not frame_data:
            return None

        # Detecta formato automaticamente
        if self._is_h264_data(frame_data):
            # Decodifica H.264
            if self.use_h264:
                frame = self.h264_decoder.decode(frame_data)
                if frame is not None:
                    return frame

            # Fallback: não pode decodificar H.264 sem PyAV
            return None

        else:
            # Assume JPEG (fallback)
            nparr = np.frombuffer(frame_data, dtype=np.uint8)
            frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
            return frame

    def process_video_queue(self):
        """Processa frames da fila de vídeo (H.264 ou JPEG)"""
        try:
            # Para H.264, TODOS os frames precisam ser decodificados em sequência
            # (P-frames dependem dos anteriores), mas só exibimos o último
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
        self._log("INFO", f"Iniciando display de vídeo (codec: {'H.264' if self.use_h264 else 'JPEG'})...")

        self.is_running = True
        no_signal_displayed = False
        last_frame_check = time.time()

        try:
            while self.is_running:
                current_time = time.time()

                if self.video_queue and not self.video_queue.empty():
                    self.process_video_queue()
                    no_signal_displayed = False
                    last_frame_check = current_time
                else:
                    if (
                        current_time - last_frame_check > 2.0
                        and not no_signal_displayed
                    ):
                        self.display_no_signal()
                        no_signal_displayed = True
                    elif (
                        self.last_frame is not None
                        and current_time - self.last_frame_time < 5.0
                    ):
                        self.display_frame(self.last_frame)

                time.sleep(0.016)  # ~60 FPS máximo

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
            "codec": "H.264" if self.use_h264 else "JPEG",
        }

        if self.use_h264:
            stats["h264_frames_decoded"] = self.h264_decoder.frames_decoded
            stats["h264_errors"] = self.h264_decoder.errors

        return stats

    def stop(self):
        """Para o display de vídeo"""
        if not self.is_running:
            return

        self.is_running = False

        # Cleanup decoder H.264 (thread-safe)
        try:
            if self.h264_decoder:
                self.h264_decoder.cleanup()
        except Exception:
            pass

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
