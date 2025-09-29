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
from typing import Optional
import tkinter as tk
from PIL import Image, ImageTk


class VideoDisplay:
    """Gerencia a exibição de vídeo do carrinho F1 (Tkinter apenas)"""

    def __init__(
        self,
        video_queue=None,
        log_queue=None,
        enable_video_enhancements=True,
    ):
        """
        Inicializa o display de vídeo

        Args:
            video_queue (Queue): Fila de frames de vídeo
            log_queue (Queue): Fila para mensagens de log
            enable_video_enhancements (bool): Ativa processamentos avançados no cliente
        """
        self.video_queue = video_queue
        self.log_queue = log_queue
        self.enable_video_enhancements = enable_video_enhancements

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

        # Configurações de processamento de vídeo
        self.color_correction_enabled = enable_video_enhancements
        self.sharpening_enabled = enable_video_enhancements
        self.brightness_auto_adjust = enable_video_enhancements

        self._log("INFO", f"VideoDisplay inicializado - Melhorias: {'Ativadas' if enable_video_enhancements else 'Desativadas'}")

        if enable_video_enhancements:
            self._log("INFO", "🎨 Correção automática de cor: ATIVA (resolve tom azulado)")
            self._log("INFO", "🔍 Sharpening inteligente: ATIVO (melhora nitidez)")
            self._log("INFO", "💡 Ajuste automático de brilho: ATIVO (otimiza exposição)")

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

            # Usar resolução original da câmera (sem redimensionamento forçado)
            height, width = frame.shape[:2]
            # Mantém resolução original recebida da câmera para máxima qualidade

            # Conversão BGR→RGB mais rápida
            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

            # Usar modo direto do PIL (mais rápido)
            pil_image = Image.fromarray(rgb_frame, mode='RGB')

            # PhotoImage direto sem cópia extra
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
                    'connected': True,
                    'resolution': f"{frame.shape[1]}x{frame.shape[0]}",
                    'fps': self.current_fps
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
                    image='',
                    text="📡 Sem Sinal\n\nAguardando vídeo do Raspberry Pi...",
                    fg="red",
                    bg="#1a1a1a",
                    font=("Arial", 12)
                )
                self.tkinter_label.image = None

            # Atualizar status
            if self.status_callback:
                status = {
                    'connected': False,
                    'resolution': 'N/A',
                    'fps': 0
                }
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
            cv2.putText(frame, resolution_text, (10, 50), font, font_scale, color, thickness)

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
        """Processa frames da fila de vídeo (super otimizado para baixo delay)"""
        try:
            # OTIMIZAÇÃO AVANÇADA: Processa inteligentemente para mínimo delay
            frames_processed = 0
            latest_frame = None
            total_queue_size = self.video_queue.qsize() if hasattr(self.video_queue, 'qsize') else 0

            # Se fila muito cheia (>5), descarta frames antigos agressivamente
            max_frames_to_process = 15 if total_queue_size > 5 else 3

            # Drena a fila mantendo apenas o frame mais recente
            while not self.video_queue.empty() and self.is_running and frames_processed < max_frames_to_process:
                frame_data = self.video_queue.get_nowait()
                frames_processed += 1

                if frame_data is None:
                    continue

                # OTIMIZAÇÃO: Decodificação JPEG mais eficiente
                if isinstance(frame_data, bytes):
                    # Usa numpy direto para velocidade máxima
                    nparr = np.frombuffer(frame_data, dtype=np.uint8)

                    # Decodifica JPEG - cv2.imdecode SEMPRE retorna BGR (padrão OpenCV)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)

                    # PROCESSAMENTO ADICIONAL NO CLIENTE (configurável):
                    if frame is not None and self.enable_video_enhancements:
                        # Aqui o cliente processa o que o Raspberry Pi não fez:

                        # 1. Correção automática de cor (resolve tom azulado)
                        if self.color_correction_enabled:
                            frame = self._enhance_colors_if_needed(frame)

                        # 2. Sharpening inteligente para melhor qualidade
                        if self.sharpening_enabled:
                            frame = self._apply_smart_sharpening(frame)

                        # 3. Ajuste automático de brilho/contraste
                        if self.brightness_auto_adjust:
                            frame = self._auto_brightness_contrast(frame)

                else:
                    frame = frame_data

                if frame is not None:
                    latest_frame = frame

            # Exibe apenas o frame mais recente
            if latest_frame is not None:
                self.display_frame(latest_frame)

                # Log inteligente sobre desempenho
                if frames_processed > 5:
                    self._log("DEBUG", f"Processados {frames_processed} frames (fila: {total_queue_size}) - descartando {frames_processed-1} antigos")
                elif total_queue_size > 10:
                    self._log("WARN", f"Fila de vídeo crescendo: {total_queue_size} frames pendentes")

        except Exception as e:
            self._log("ERROR", f"Erro ao processar fila de vídeo: {e}")

    def _enhance_colors_if_needed(self, frame):
        """Correção automática de cores (cliente pode processar)"""
        try:
            # Verifica se frame tem tom azulado excessivo (problema típico de câmeras)
            b, g, r = cv2.split(frame)
            blue_mean = np.mean(b)
            green_mean = np.mean(g)
            red_mean = np.mean(r)

            # Se azul está dominando muito (>15% mais que vermelho), corrige
            if blue_mean > red_mean * 1.15:
                # Reduz canal azul levemente e aumenta vermelho
                correction_factor = 0.9
                enhanced_frame = frame.copy()
                enhanced_frame[:,:,0] = np.clip(b * correction_factor, 0, 255)  # Reduz azul
                enhanced_frame[:,:,2] = np.clip(r * 1.1, 0, 255)  # Aumenta vermelho
                return enhanced_frame

            return frame
        except:
            # Em caso de erro, retorna frame original
            return frame

    def _apply_smart_sharpening(self, frame):
        """Aplica sharpening inteligente (cliente pode processar)"""
        try:
            # Aplica sharpening leve apenas se necessário
            # Só a cada 3 frames para economizar CPU
            if self.frame_count % 3 != 0:
                return frame

            # Kernel de sharpening suave
            kernel = np.array([[-0.1, -0.1, -0.1],
                              [-0.1,  1.8, -0.1],
                              [-0.1, -0.1, -0.1]])

            sharpened = cv2.filter2D(frame, -1, kernel)
            return sharpened
        except:
            return frame

    def _auto_brightness_contrast(self, frame):
        """Ajuste automático de brilho/contraste (cliente pode processar)"""
        try:
            # Só aplica a cada 5 frames para economizar CPU
            if self.frame_count % 5 != 0:
                return frame

            # Calcula estatísticas da imagem
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            mean_brightness = np.mean(gray)

            # Se muito escuro ou muito claro, ajusta automaticamente
            if mean_brightness < 80:  # Muito escuro
                # Aumenta brilho
                brightness = int((80 - mean_brightness) * 0.5)
                brightened = cv2.convertScaleAbs(frame, alpha=1.0, beta=brightness)
                return brightened
            elif mean_brightness > 200:  # Muito claro
                # Reduz brilho
                brightness = -int((mean_brightness - 200) * 0.3)
                darkened = cv2.convertScaleAbs(frame, alpha=1.0, beta=brightness)
                return darkened

            return frame
        except:
            return frame

    def toggle_color_correction(self, enabled=None):
        """Ativa/desativa correção de cor"""
        if enabled is None:
            self.color_correction_enabled = not self.color_correction_enabled
        else:
            self.color_correction_enabled = enabled
        self._log("INFO", f"Correção de cor: {'Ativada' if self.color_correction_enabled else 'Desativada'}")

    def toggle_sharpening(self, enabled=None):
        """Ativa/desativa sharpening"""
        if enabled is None:
            self.sharpening_enabled = not self.sharpening_enabled
        else:
            self.sharpening_enabled = enabled
        self._log("INFO", f"Sharpening: {'Ativado' if self.sharpening_enabled else 'Desativado'}")

    def toggle_brightness_adjustment(self, enabled=None):
        """Ativa/desativa ajuste automático de brilho"""
        if enabled is None:
            self.brightness_auto_adjust = not self.brightness_auto_adjust
        else:
            self.brightness_auto_adjust = enabled
        self._log("INFO", f"Ajuste de brilho: {'Ativado' if self.brightness_auto_adjust else 'Desativado'}")

    def get_enhancement_status(self):
        """Retorna status das melhorias de vídeo"""
        return {
            "enhancements_enabled": self.enable_video_enhancements,
            "color_correction": self.color_correction_enabled,
            "sharpening": self.sharpening_enabled,
            "brightness_adjustment": self.brightness_auto_adjust
        }

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