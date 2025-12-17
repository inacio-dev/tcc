#!/usr/bin/env python3
"""
camera_manager.py - Gerenciamento da Câmera OV5647 com MJPEG Encoder

Usa encoder MJPEG para máxima fidelidade de imagem.
Cada frame é uma imagem JPEG independente (sem dependência entre frames).

PINOUT CÂMERA OV5647:
===================
Camera Module -> Raspberry Pi 4
- Conectar no slot CSI (Camera Serial Interface)
- Cabo flat de 15 pinos conectado na entrada "Camera" do RPi4
- Certifique-se que o cabo está com os contatos virados para baixo
- Execute 'sudo raspi-config' -> Interface Options -> Camera -> Enable

CONFIGURAÇÃO NECESSÁRIA:
=======================
1. sudo raspi-config
2. Interface Options -> Camera -> Enable
3. Reboot
4. Teste: libcamera-hello (comando de teste)

FORMATO DE SAÍDA:
================
- MJPEG (Motion JPEG)
- Cada frame é JPEG independente
- Qualidade: 85 (ajustável)
- Sem dependência entre frames (perda de 1 frame não afeta os outros)
"""

import io
import time
import threading
from collections import deque
from picamera2 import Picamera2
from picamera2.encoders import MJPEGEncoder
from picamera2.outputs import FileOutput


class CircularBuffer(io.BufferedIOBase):
    """Buffer circular para streaming MJPEG"""

    def __init__(self, max_frames=10):
        self.frames = deque(maxlen=max_frames)
        self.current_frame = io.BytesIO()
        self.lock = threading.Lock()
        self.frame_count = 0
        self.total_bytes = 0

    def write(self, data):
        """Recebe dados do encoder MJPEG"""
        with self.lock:
            # JPEG começa com SOI (Start of Image): 0xFFD8
            # JPEG termina com EOI (End of Image): 0xFFD9
            if len(data) >= 2 and data[:2] == b'\xff\xd8':
                # Novo frame JPEG iniciando - salva o anterior se existir
                if self.current_frame.tell() > 0:
                    frame_data = self.current_frame.getvalue()
                    if self._is_valid_jpeg(frame_data):
                        self.frames.append({
                            'data': frame_data,
                            'timestamp': time.time(),
                            'size': len(frame_data),
                            'keyframe': True  # MJPEG: todo frame é independente
                        })
                        self.frame_count += 1
                        self.total_bytes += len(frame_data)

                # Inicia novo frame
                self.current_frame = io.BytesIO()

            self.current_frame.write(data)
            return len(data)

    def _is_valid_jpeg(self, data):
        """Verifica se é um JPEG válido (tem SOI e EOI)"""
        if len(data) < 4:
            return False
        # Verifica SOI no início e EOI no final
        has_soi = data[:2] == b'\xff\xd8'
        has_eoi = data[-2:] == b'\xff\xd9'
        return has_soi and has_eoi

    def get_frame(self):
        """Obtém o frame mais recente"""
        with self.lock:
            if self.frames:
                return self.frames[-1]
            return None

    def flush(self):
        """Flush do buffer"""
        pass

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False


class CameraManager:
    """Gerencia a captura de vídeo da câmera OV5647 com MJPEG encoding"""

    def __init__(self, resolution=(640, 480), frame_rate=30, quality=85):
        """
        Inicializa o gerenciador da câmera

        Args:
            resolution (tuple): Resolução do vídeo (largura, altura)
            frame_rate (int): Taxa de frames por segundo
            quality (int): Qualidade JPEG (1-100, padrão: 85)
        """
        self.resolution = resolution
        self.frame_rate = frame_rate
        self.quality = max(1, min(100, quality))  # Clamp entre 1-100
        self.camera = None
        self.encoder = None
        self.buffer = None
        self.output = None
        self.is_initialized = False
        self.is_recording = False

        # Estatísticas
        self.frames_captured = 0
        self.last_capture_time = time.time()
        self.last_frame_size = 0
        self.start_time = None

    def initialize(self):
        """
        Inicializa a câmera OV5647 com encoder MJPEG

        Returns:
            bool: True se inicializada com sucesso, False caso contrário
        """
        try:
            print("Inicializando câmera OV5647 com MJPEG encoder...")

            # Verifica câmeras disponíveis ANTES de criar instância
            try:
                camera_info = Picamera2.global_camera_info()
                print(f"  Câmeras encontradas: {len(camera_info)}")
                if camera_info:
                    for i, cam in enumerate(camera_info):
                        print(f"    [{i}] {cam.get('Model', 'Desconhecida')}")
                else:
                    print("❌ Nenhuma câmera detectada pelo sistema!")
                    print("   Execute: libcamera-hello --list-cameras")
                    return False
            except Exception as e:
                print(f"⚠ Erro ao listar câmeras: {e}")

            # Cria instância da PiCamera2 com índice explícito
            self.camera = Picamera2(camera_num=0)

            # Configuração para encoding de vídeo MJPEG
            config = self.camera.create_video_configuration(
                main={"size": self.resolution, "format": "XBGR8888"},
                encode="main",  # IMPORTANTE: indica qual stream usar para o encoder
                buffer_count=4,
            )

            # Aplica configuração
            self.camera.configure(config)

            # Configura frame rate
            try:
                frame_duration = 1000000 // self.frame_rate  # microssegundos
                self.camera.set_controls({
                    "FrameDurationLimits": (frame_duration, frame_duration)
                })
                print(f"  Frame rate: {self.frame_rate} FPS")
            except Exception as e:
                print(f"⚠ Aviso: FrameDurationLimits não configurado: {e}")

            # Cria encoder MJPEG com qualidade configurável
            self.encoder = MJPEGEncoder(q=self.quality)

            # Cria buffer circular
            self.buffer = CircularBuffer(max_frames=10)

            # Cria output que escreve no buffer
            self.output = FileOutput(self.buffer)

            # Inicia câmera
            self.camera.start()
            time.sleep(0.5)

            # Inicia gravação com encoder MJPEG
            self.camera.start_encoder(self.encoder, self.output)
            self.is_recording = True
            self.start_time = time.time()

            self.is_initialized = True

            print("✓ Câmera OV5647 inicializada com MJPEG encoder")
            print(f"  Resolução: {self.resolution[0]}x{self.resolution[1]}")
            print(f"  Qualidade JPEG: {self.quality}%")
            print(f"  Encoder: MJPEG (cada frame é JPEG independente)")

            return True

        except IndexError as e:
            print(f"✗ Erro ao detectar câmera: {e}")
            print("\nVerifique:")
            print("1. Cabo da câmera conectado corretamente")
            print("2. Câmera habilitada: sudo raspi-config -> Interface Options -> Camera")
            print("3. Sistema reiniciado após habilitar")
            print("4. Execute: libcamera-hello para testar")

            self.is_initialized = False
            return False

        except Exception as e:
            print(f"✗ Erro ao inicializar câmera: {e}")
            import traceback
            traceback.print_exc()

            self.is_initialized = False
            return False

    def capture_frame(self):
        """
        Obtém o frame JPEG mais recente do buffer

        Returns:
            bytes: Frame JPEG codificado, ou None se não disponível
        """
        if not self.is_initialized or self.buffer is None:
            return None

        try:
            frame_info = self.buffer.get_frame()

            if frame_info:
                self.frames_captured += 1
                self.last_capture_time = time.time()
                self.last_frame_size = frame_info['size']
                return frame_info['data']

            return None

        except Exception as e:
            print(f"⚠ Erro ao obter frame: {e}")
            return None

    def get_frame_with_metadata(self):
        """
        Obtém frame JPEG com metadados

        Returns:
            dict: {'data': bytes, 'keyframe': bool, 'timestamp': float, 'size': int}
        """
        if not self.is_initialized or self.buffer is None:
            return None

        try:
            frame_info = self.buffer.get_frame()

            if frame_info:
                self.frames_captured += 1
                self.last_capture_time = time.time()
                self.last_frame_size = frame_info['size']
                return frame_info

            return None

        except Exception as e:
            print(f"⚠ Erro ao obter frame: {e}")
            return None

    def get_frame_size_info(self, frame_data):
        """
        Obtém informações sobre o tamanho do frame

        Args:
            frame_data (bytes): Dados do frame codificado

        Returns:
            dict: Informações do frame
        """
        if frame_data is None:
            return {"size_bytes": 0, "size_kb": 0.0}

        size_bytes = len(frame_data)
        size_kb = size_bytes / 1024.0

        return {"size_bytes": size_bytes, "size_kb": round(size_kb, 2)}

    def get_statistics(self):
        """
        Obtém estatísticas da câmera e encoder

        Returns:
            dict: Estatísticas de captura
        """
        stats = {
            "frames_captured": self.frames_captured,
            "is_initialized": self.is_initialized,
            "is_recording": self.is_recording,
            "resolution": self.resolution,
            "frame_rate": self.frame_rate,
            "quality": self.quality,
            "last_capture_time": self.last_capture_time,
            "last_frame_size": self.last_frame_size,
            "encoder": "MJPEG",
        }

        # Estatísticas do buffer
        if self.buffer:
            stats["encoder_frames"] = self.buffer.frame_count
            stats["encoder_bytes"] = self.buffer.total_bytes

            if self.start_time:
                elapsed = time.time() - self.start_time
                if elapsed > 0:
                    stats["bytes_per_second"] = self.buffer.total_bytes / elapsed
                    stats["actual_fps"] = self.buffer.frame_count / elapsed

        return stats

    def set_quality(self, quality):
        """
        Altera a qualidade JPEG do encoder (requer reinicialização)

        Args:
            quality (int): Nova qualidade (1-100)
        """
        if 1 <= quality <= 100:
            self.quality = quality
            print(f"Qualidade JPEG alterada para: {quality}%")
            print("⚠ Reinicialize a câmera para aplicar a mudança")
        else:
            print("⚠ Qualidade deve estar entre 1 e 100")

    def cleanup(self):
        """Libera recursos da câmera e encoder"""
        try:
            if self.is_recording and self.camera:
                self.camera.stop_encoder()
                self.is_recording = False

            if self.camera is not None:
                self.camera.close()
                print("✓ Câmera OV5647 finalizada")

            self.is_initialized = False
            self.camera = None
            self.encoder = None
            self.buffer = None
            self.output = None

        except Exception as e:
            print(f"⚠ Erro ao finalizar câmera: {e}")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()
