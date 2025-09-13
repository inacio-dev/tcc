#!/usr/bin/env python3
"""
video_display.py - Gerenciamento da Exibição de Vídeo
Responsável por exibir frames de vídeo recebidos do Raspberry Pi

CARACTERÍSTICAS:
===============
- Decodificação JPEG automática
- Redimensionamento automático
- Controles de janela (ESC para fechar)
- Estatísticas de FPS em tempo real
- Tratamento de erros robusto
- Último frame válido em caso de falha
"""

import cv2
import numpy as np
import time
import threading
from typing import Optional
import tkinter as tk
from PIL import Image, ImageTk


class VideoDisplay:
    """Gerencia a exibição de vídeo do carrinho F1"""

    def __init__(
        self,
        video_queue=None,
        log_queue=None,
        window_name="🏎️ F1 Car - Video Feed",
        window_width=854,
        window_height=480,
    ):
        """
        Inicializa o display de vídeo

        Args:
            video_queue (Queue): Fila de frames de vídeo
            log_queue (Queue): Fila para mensagens de log
            window_name (str): Nome da janela
            window_width (int): Largura da janela
            window_height (int): Altura da janela
        """
        self.video_queue = video_queue
        self.log_queue = log_queue
        self.window_name = window_name
        self.window_width = window_width
        self.window_height = window_height

        # Controle de execução
        self.is_running = False
        self.window_created = False

        # Último frame válido
        self.last_frame = None
        self.last_frame_time = time.time()

        # Estatísticas
        self.frames_displayed = 0
        self.decode_errors = 0
        self.start_time = time.time()
        self.last_fps_time = time.time()
        self.last_fps_count = 0

        # Lock para thread safety
        self.frame_lock = threading.Lock()

        # Integração com Tkinter (sempre ativo)
        self.tkinter_label = None
        self.status_callback = None
        self.use_tkinter = True  # Sempre usar Tkinter
        self.current_fps = 0

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
        """Atualiza frame no label Tkinter"""
        try:
            if not self.tkinter_label:
                return

            # Redimensionar frame para caber no container (largura fixa)
            target_width = 320  # Largura fixa para o container
            height, width = frame.shape[:2]
            aspect_ratio = width / height
            target_height = int(target_width / aspect_ratio)

            # Redimensionar
            resized = cv2.resize(frame, (target_width, target_height))

            # Converter BGR (OpenCV) para RGB (PIL)
            rgb_frame = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)

            # Converter para PIL Image
            pil_image = Image.fromarray(rgb_frame)

            # Converter para PhotoImage do Tkinter
            photo = ImageTk.PhotoImage(pil_image)

            # Atualizar label
            self.tkinter_label.configure(image=photo)
            self.tkinter_label.image = photo  # Manter referência

            # Atualizar status se callback definido
            if self.status_callback:
                status = {
                    'connected': True,
                    'fps': self.current_fps,
                    'width': width,
                    'height': height
                }
                self.status_callback(status)

        except Exception as e:
            self._log("ERROR", f"Erro ao atualizar frame Tkinter: {e}")

    def create_window(self):
        """Cria e configura a janela de vídeo (só se não estiver usando Tkinter)"""
        # Se está usando Tkinter, não cria janela OpenCV
        if self.use_tkinter:
            self.window_created = True
            self._log("INFO", "Modo Tkinter - janela OpenCV não será criada")
            return True

        try:
            cv2.namedWindow(self.window_name, cv2.WINDOW_NORMAL)
            cv2.resizeWindow(self.window_name, self.window_width, self.window_height)

            # Permite redimensionamento, mas mantém aspect ratio
            cv2.setWindowProperty(
                self.window_name, cv2.WND_PROP_ASPECT_RATIO, cv2.WINDOW_KEEPRATIO
            )

            self.window_created = True
            self._log(
                "INFO",
                f"Janela OpenCV criada: {self.window_width}x{self.window_height}",
            )

            return True

        except Exception as e:
            self._log("ERROR", f"Erro ao criar janela de vídeo: {e}")
            return False

    def decode_frame(self, frame_data):
        """
        Decodifica frame JPEG

        Args:
            frame_data (bytes): Dados do frame codificado

        Returns:
            np.ndarray: Frame decodificado ou None em caso de erro
        """
        try:
            # Converte bytes para array numpy
            frame_array = np.frombuffer(frame_data, dtype=np.uint8)

            # Decodifica JPEG
            frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)

            if frame is None:
                # Tenta encontrar início de JPEG se decodificação falhar
                for i in range(min(50, len(frame_data))):
                    if frame_data[i : i + 2] == b"\xff\xd8":  # Marcador de início JPEG
                        frame_array = np.frombuffer(frame_data[i:], dtype=np.uint8)
                        frame = cv2.imdecode(frame_array, cv2.IMREAD_COLOR)
                        if frame is not None:
                            self._log("WARNING", f"JPEG encontrado no offset {i}")
                            break

            return frame

        except Exception as e:
            self._log("ERROR", f"Erro ao decodificar frame: {e}")
            return None

    def add_overlay_info(self, frame):
        """
        Adiciona informações sobrepostas no frame

        Args:
            frame (np.ndarray): Frame original

        Returns:
            np.ndarray: Frame com overlay
        """
        try:
            # Calcula FPS atual
            current_time = time.time()
            elapsed = current_time - self.last_fps_time

            if elapsed >= 1.0:
                fps = (self.frames_displayed - self.last_fps_count) / elapsed
                self.current_fps = fps
                self.last_fps_time = current_time
                self.last_fps_count = self.frames_displayed
            else:
                fps = getattr(self, "current_fps", 0.0)

            # Informações para overlay
            height, width = frame.shape[:2]
            info_text = [
                f"FPS: {fps:.1f}",
                f"Resolução: {width}x{height}",
                f"Frames: {self.frames_displayed}",
                f"Erros: {self.decode_errors}",
            ]

            # Adiciona texto no canto superior esquerdo
            y_offset = 25
            for i, text in enumerate(info_text):
                y = y_offset + (i * 25)

                # Fundo semi-transparente para melhor legibilidade
                text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)[0]
                cv2.rectangle(
                    frame, (5, y - 20), (15 + text_size[0], y + 5), (0, 0, 0), -1
                )
                cv2.rectangle(
                    frame, (5, y - 20), (15 + text_size[0], y + 5), (255, 255, 255), 1
                )

                # Texto
                cv2.putText(
                    frame, text, (10, y), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2
                )

            # Status da conexão no canto superior direito
            status_text = "🔴 AO VIVO"
            text_size = cv2.getTextSize(status_text, cv2.FONT_HERSHEY_SIMPLEX, 0.7, 2)[
                0
            ]
            x = width - text_size[0] - 15
            y = 30

            cv2.rectangle(
                frame, (x - 5, y - 20), (x + text_size[0] + 5, y + 5), (0, 0, 0), -1
            )
            cv2.putText(
                frame,
                status_text,
                (x, y),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                (0, 0, 255),
                2,
            )

            return frame

        except Exception as e:
            self._log("ERROR", f"Erro ao adicionar overlay: {e}")
            return frame

    def display_frame(self, frame):
        """
        Exibe frame na janela ou no Tkinter

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
                self.frames_displayed += 1

        except Exception as e:
            self._log("ERROR", f"Erro ao exibir frame: {e}")

    def display_no_signal(self):
        """Exibe tela de 'sem sinal' quando não há dados"""
        try:
            # Cria frame preto com mensagem
            frame = np.zeros((self.window_height, self.window_width, 3), dtype=np.uint8)

            # Mensagem principal
            text = "🏎️ Aguardando sinal do carrinho..."
            text_size = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, 1.0, 2)[0]
            x = (self.window_width - text_size[0]) // 2
            y = (self.window_height - text_size[1]) // 2

            cv2.putText(
                frame, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (100, 100, 100), 2
            )

            # Informações adicionais
            info_lines = [
                "Verifique:",
                "1. Raspberry Pi ligado",
                "2. Rede WiFi conectada",
                "3. IP configurado corretamente",
                f"4. Porta {9999} desbloqueada",
            ]

            y_start = y + 60
            for i, line in enumerate(info_lines):
                text_size = cv2.getTextSize(line, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 1)[0]
                x_line = (self.window_width - text_size[0]) // 2
                y_line = y_start + (i * 30)

                color = (0, 255, 255) if i == 0 else (150, 150, 150)
                cv2.putText(
                    frame,
                    line,
                    (x_line, y_line),
                    cv2.FONT_HERSHEY_SIMPLEX,
                    0.6,
                    color,
                    1,
                )

            # Exibe frame
            cv2.imshow(self.window_name, frame)

        except Exception as e:
            self._log("ERROR", f"Erro ao exibir tela sem sinal: {e}")

    def process_video_queue(self):
        """Processa fila de frames de vídeo"""
        frames_processed = 0

        while (
            not self.video_queue.empty() and frames_processed < 5
        ):  # Limita processos por ciclo
            try:
                frame_data = self.video_queue.get_nowait()

                # Decodifica frame
                frame = self.decode_frame(frame_data)

                if frame is not None:
                    # Exibe frame
                    self.display_frame(frame)
                else:
                    self.decode_errors += 1
                    # Exibe último frame válido se disponível
                    if self.last_frame is not None:
                        self.display_frame(self.last_frame)

                frames_processed += 1

            except Exception as e:
                self._log("ERROR", f"Erro ao processar fila de vídeo: {e}")
                break

    def check_window_events(self):
        """Verifica eventos da janela (teclas, fechamento)"""
        # Se está usando Tkinter, não precisa verificar eventos OpenCV
        if self.use_tkinter:
            return True

        try:
            key = cv2.waitKey(1) & 0xFF

            if key == 27:  # ESC
                self._log("INFO", "ESC pressionado - fechando janela de vídeo")
                return False
            elif key == ord("f") or key == ord("F"):  # F para fullscreen
                cv2.setWindowProperty(
                    self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN
                )
            elif key == ord("w") or key == ord("W"):  # W para windowed
                cv2.setWindowProperty(
                    self.window_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL
                )
            elif key == ord("r") or key == ord("R"):  # R para reset stats
                self.frames_displayed = 0
                self.decode_errors = 0
                self.start_time = time.time()
                self._log("INFO", "Estatísticas de vídeo resetadas")

            return True

        except Exception as e:
            self._log("ERROR", f"Erro ao verificar eventos da janela: {e}")
            return True

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

                # Sleep curto para não sobrecarregar
                time.sleep(0.033)  # ~30 FPS

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
            dict: Estatísticas de exibição
        """
        elapsed = time.time() - self.start_time
        avg_fps = self.frames_displayed / elapsed if elapsed > 0 else 0

        return {
            "frames_displayed": self.frames_displayed,
            "decode_errors": self.decode_errors,
            "elapsed_time": round(elapsed, 2),
            "average_fps": round(avg_fps, 2),
            "window_created": self.window_created,
            "is_running": self.is_running,
            "last_frame_time": self.last_frame_time,
        }

    def stop(self):
        """Para o display de vídeo"""
        self._log("INFO", "Parando display de vídeo...")

        self.is_running = False

        # Fecha janela OpenCV (só se não estiver usando Tkinter)
        try:
            if self.window_created and not self.use_tkinter:
                cv2.destroyWindow(self.window_name)
                cv2.destroyAllWindows()
        except:
            pass

        # Estatísticas finais
        stats = self.get_statistics()
        self._log("INFO", f"Estatísticas de vídeo:")
        self._log("INFO", f"  - Frames exibidos: {stats['frames_displayed']}")
        self._log("INFO", f"  - FPS médio: {stats['average_fps']:.1f}")
        self._log("INFO", f"  - Erros de decodificação: {stats['decode_errors']}")

        self._log("INFO", "Display de vídeo parado")


# Teste independente
if __name__ == "__main__":
    import queue
    import threading
    import numpy as np
    import cv2

    print("=== TESTE DO VIDEO DISPLAY ===")

    # Cria filas de teste
    video_q = queue.Queue()
    log_q = queue.Queue()

    # Cria display
    display = VideoDisplay(video_queue=video_q, log_queue=log_q)

    def generate_test_frames():
        """Gera frames de teste"""
        print("Gerando frames de teste...")

        for i in range(100):
            # Cria frame de teste colorido
            frame = np.zeros((480, 640, 3), dtype=np.uint8)

            # Adiciona cor de fundo que muda
            color = (i * 2) % 255
            frame[:] = (color // 3, color // 2, color)

            # Adiciona texto
            text = f"Frame de Teste #{i+1}"
            cv2.putText(
                frame, text, (50, 240), cv2.FONT_HERSHEY_SIMPLEX, 2, (255, 255, 255), 3
            )

            # Codifica como JPEG
            _, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
            frame_data = encoded.tobytes()

            # Adiciona à fila
            video_q.put(frame_data)

            time.sleep(0.1)  # 10 FPS

        print("Frames de teste gerados")

    # Inicia gerador de frames em thread separada
    generator_thread = threading.Thread(target=generate_test_frames, daemon=True)
    generator_thread.start()

    # Inicia display em thread separada para poder mostrar logs
    display_thread = threading.Thread(target=display.run_display, daemon=True)
    display_thread.start()

    print("Display iniciado - pressione ESC na janela de vídeo para parar")

    try:
        # Mostra logs em tempo real
        while display.is_running:
            try:
                while not log_q.empty():
                    level, message = log_q.get_nowait()
                    print(f"[{level}] {message}")

                time.sleep(0.1)

            except KeyboardInterrupt:
                break

    except KeyboardInterrupt:
        print("\nParando teste...")

    display.stop()
    print("Teste concluído")
