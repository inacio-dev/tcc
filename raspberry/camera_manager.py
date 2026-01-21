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
import threading
import time
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
            if len(data) >= 2 and data[:2] == b"\xff\xd8":
                # Novo frame JPEG iniciando - salva o anterior se existir
                if self.current_frame.tell() > 0:
                    frame_data = self.current_frame.getvalue()
                    if self._is_valid_jpeg(frame_data):
                        self.frames.append(
                            {
                                "data": frame_data,
                                "timestamp": time.time(),
                                "size": len(frame_data),
                                "keyframe": True,  # MJPEG: todo frame é independente
                            }
                        )
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
        has_soi = data[:2] == b"\xff\xd8"
        has_eoi = data[-2:] == b"\xff\xd9"
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

    # Presets de resolução
    RESOLUTION_PRESETS = {
        "480p": (640, 480),      # VGA - leve
        "720p": (1280, 720),     # HD - balanceado
        "1080p": (1920, 1080),   # Full HD - alta qualidade
    }

    def __init__(
        self,
        resolution=(640, 480),
        frame_rate=30,
        quality=85,
        sharpness=1.0,
        contrast=1.0,
        saturation=1.0,
        brightness=0.0,
        exposure_mode="auto",
    ):
        """
        Inicializa o gerenciador da câmera

        Args:
            resolution (tuple): Resolução do vídeo (largura, altura)
            frame_rate (int): Taxa de frames por segundo
            quality (int): Qualidade MJPEG 1-100 (padrão: 85)
            sharpness (float): Nitidez 0.0-2.0 (padrão: 1.0)
            contrast (float): Contraste 0.0-2.0 (padrão: 1.0)
            saturation (float): Saturação 0.0-2.0 (padrão: 1.0)
            brightness (float): Brilho -1.0 a 1.0 (padrão: 0.0)
            exposure_mode (str): Modo de exposição (auto, short, long)
        """
        self.resolution = resolution
        self.frame_rate = frame_rate
        self.quality = quality
        self.sharpness = sharpness
        self.contrast = contrast
        self.saturation = saturation
        self.brightness = brightness
        self.exposure_mode = exposure_mode

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

            # Configura frame rate e controles de imagem
            try:
                frame_duration = 1000000 // self.frame_rate  # microssegundos
                controls = {
                    "FrameDurationLimits": (frame_duration, frame_duration),
                }

                # Controles de imagem (valores em escala libcamera)
                # Sharpness: 0.0 = sem nitidez, 1.0 = normal, 2.0+ = mais nítido
                if self.sharpness != 1.0:
                    controls["Sharpness"] = self.sharpness

                # Contrast: 0.0 = sem contraste, 1.0 = normal, 2.0 = alto contraste
                if self.contrast != 1.0:
                    controls["Contrast"] = self.contrast

                # Saturation: 0.0 = preto e branco, 1.0 = normal, 2.0 = cores vivas
                if self.saturation != 1.0:
                    controls["Saturation"] = self.saturation

                # Brightness: -1.0 a 1.0 (0.0 = normal)
                if self.brightness != 0.0:
                    controls["Brightness"] = self.brightness

                self.camera.set_controls(controls)
                print(f"  Frame rate: {self.frame_rate} FPS")
                print(f"  Controles: sharpness={self.sharpness}, contrast={self.contrast}, saturation={self.saturation}")
            except Exception as e:
                print(f"⚠ Aviso: Alguns controles não configurados: {e}")

            # Cria encoder MJPEG (usa hardware do Raspberry Pi)
            # Qualidade controlada via parâmetro quality (1-100)
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
            print(f"  Qualidade MJPEG: {self.quality}")
            print("  Encoder: MJPEG (hardware, cada frame é JPEG independente)")

            return True

        except IndexError as e:
            print(f"✗ Erro ao detectar câmera: {e}")
            print("\nVerifique:")
            print("1. Cabo da câmera conectado corretamente")
            print(
                "2. Câmera habilitada: sudo raspi-config -> Interface Options -> Camera"
            )
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
                self.last_frame_size = frame_info["size"]
                return frame_info["data"]

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
                self.last_frame_size = frame_info["size"]
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

    def set_controls(self, sharpness=None, contrast=None, saturation=None, brightness=None):
        """
        Ajusta controles de imagem em tempo real

        Args:
            sharpness (float): Nitidez 0.0-2.0
            contrast (float): Contraste 0.0-2.0
            saturation (float): Saturação 0.0-2.0
            brightness (float): Brilho -1.0 a 1.0
        """
        if not self.is_initialized or self.camera is None:
            return False

        try:
            controls = {}

            if sharpness is not None:
                controls["Sharpness"] = sharpness
                self.sharpness = sharpness

            if contrast is not None:
                controls["Contrast"] = contrast
                self.contrast = contrast

            if saturation is not None:
                controls["Saturation"] = saturation
                self.saturation = saturation

            if brightness is not None:
                controls["Brightness"] = brightness
                self.brightness = brightness

            if controls:
                self.camera.set_controls(controls)
                return True

            return False

        except Exception as e:
            print(f"⚠ Erro ao ajustar controles: {e}")
            return False

    def get_current_settings(self):
        """
        Retorna configurações atuais da câmera

        Returns:
            dict: Configurações atuais
        """
        return {
            "resolution": self.resolution,
            "resolution_name": self._get_resolution_name(),
            "frame_rate": self.frame_rate,
            "quality": self.quality,
            "sharpness": self.sharpness,
            "contrast": self.contrast,
            "saturation": self.saturation,
            "brightness": self.brightness,
        }

    def _get_resolution_name(self):
        """Retorna o nome do preset de resolução atual"""
        for name, res in self.RESOLUTION_PRESETS.items():
            if res == self.resolution:
                return name
        return f"{self.resolution[0]}x{self.resolution[1]}"

    def set_resolution(self, resolution_name):
        """
        Muda a resolução da câmera (requer reinicialização)

        Args:
            resolution_name (str): Nome do preset ('480p', '720p', '1080p')

        Returns:
            bool: True se a resolução foi alterada com sucesso
        """
        if resolution_name not in self.RESOLUTION_PRESETS:
            print(f"⚠ Resolução inválida: {resolution_name}")
            print(f"   Opções válidas: {list(self.RESOLUTION_PRESETS.keys())}")
            return False

        new_resolution = self.RESOLUTION_PRESETS[resolution_name]

        # Se a resolução já é a mesma, não faz nada
        if new_resolution == self.resolution:
            print(f"ℹ Resolução já é {resolution_name}")
            return True

        print(f"🔄 Mudando resolução para {resolution_name} ({new_resolution[0]}x{new_resolution[1]})...")

        try:
            # Para o encoder atual
            if self.is_recording and self.camera:
                self.camera.stop_encoder()
                self.is_recording = False

            # Para a câmera
            if self.camera:
                self.camera.stop()

            # Atualiza resolução
            self.resolution = new_resolution

            # Reconfigura a câmera
            config = self.camera.create_video_configuration(
                main={"size": self.resolution, "format": "XBGR8888"},
                encode="main",
                buffer_count=4,
            )
            self.camera.configure(config)

            # Reaplica controles
            frame_duration = 1000000 // self.frame_rate
            controls = {
                "FrameDurationLimits": (frame_duration, frame_duration),
            }
            if self.sharpness != 1.0:
                controls["Sharpness"] = self.sharpness
            if self.contrast != 1.0:
                controls["Contrast"] = self.contrast
            if self.saturation != 1.0:
                controls["Saturation"] = self.saturation
            if self.brightness != 0.0:
                controls["Brightness"] = self.brightness

            self.camera.set_controls(controls)

            # Recria encoder e buffer
            self.encoder = MJPEGEncoder(q=self.quality)
            self.buffer = CircularBuffer(max_frames=10)
            self.output = FileOutput(self.buffer)

            # Reinicia câmera e encoder
            self.camera.start()
            time.sleep(0.3)  # Aguarda estabilização
            self.camera.start_encoder(self.encoder, self.output)
            self.is_recording = True

            print(f"✓ Resolução alterada para {resolution_name} ({new_resolution[0]}x{new_resolution[1]})")
            return True

        except Exception as e:
            print(f"✗ Erro ao mudar resolução: {e}")
            import traceback
            traceback.print_exc()
            return False

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
