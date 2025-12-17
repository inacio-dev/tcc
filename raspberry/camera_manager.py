#!/usr/bin/env python3
"""
camera_manager.py - Gerenciamento da Câmera OV5647 com H.264 Hardware Encoder

Usa o encoder H.264 de hardware do Raspberry Pi 4 (VideoCore VI) para
compressão eficiente de vídeo com baixa latência e mínimo uso de CPU.

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
- H.264 Annex B (NAL units com start codes 0x00000001)
- Profile: Baseline (decodificação rápida)
- Keyframes a cada 30 frames (1 segundo @ 30 FPS)
- Bitrate: 1.5 Mbps (ajustável)
"""

import time
import threading
from collections import deque
from picamera2 import Picamera2
from picamera2.encoders import H264Encoder
from picamera2.outputs import Output


class StreamingOutput(Output):
    """Output customizado para capturar frames H.264 em buffer circular"""

    def __init__(self, buffer_size=5):
        super().__init__()
        self.frame_buffer = deque(maxlen=buffer_size)
        self.lock = threading.Lock()
        self.frame_count = 0
        self.total_bytes = 0

    def outputframe(self, frame, keyframe=True, timestamp=None):
        """Recebe frame codificado do encoder H.264"""
        with self.lock:
            self.frame_buffer.append({
                'data': bytes(frame),
                'keyframe': keyframe,
                'timestamp': timestamp or time.time(),
                'size': len(frame)
            })
            self.frame_count += 1
            self.total_bytes += len(frame)

    def get_frame(self):
        """Obtém o frame mais recente do buffer"""
        with self.lock:
            if self.frame_buffer:
                return self.frame_buffer[-1]
            return None

    def get_all_frames(self):
        """Obtém todos os frames do buffer e limpa"""
        with self.lock:
            frames = list(self.frame_buffer)
            self.frame_buffer.clear()
            return frames


class CameraManager:
    """Gerencia a captura de vídeo da câmera OV5647 com H.264 hardware encoding"""

    def __init__(self, resolution=(640, 480), frame_rate=30, bitrate=1500000):
        """
        Inicializa o gerenciador da câmera

        Args:
            resolution (tuple): Resolução do vídeo (largura, altura)
            frame_rate (int): Taxa de frames por segundo
            bitrate (int): Bitrate do H.264 em bps (padrão: 1.5 Mbps)
        """
        self.resolution = resolution
        self.frame_rate = frame_rate
        self.bitrate = bitrate
        self.camera = None
        self.encoder = None
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
        Inicializa a câmera OV5647 com encoder H.264 de hardware

        Returns:
            bool: True se inicializada com sucesso, False caso contrário
        """
        try:
            print("Inicializando câmera OV5647 com H.264 hardware encoder...")

            # Cria instância da PiCamera2
            self.camera = Picamera2()

            # Configuração para encoding de vídeo H.264
            config = self.camera.create_video_configuration(
                main={"size": self.resolution, "format": "YUV420"},
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

            # Cria encoder H.264 com configurações de baixa latência
            self.encoder = H264Encoder(
                bitrate=self.bitrate,
                repeat=True,          # Repete SPS/PPS para resiliência
                iperiod=30,           # Keyframe a cada 30 frames
            )

            # Cria output para capturar frames
            self.output = StreamingOutput(buffer_size=5)

            # Inicia câmera
            self.camera.start()
            time.sleep(0.3)

            # Inicia gravação com encoder H.264
            self.camera.start_encoder(self.encoder, self.output)
            self.is_recording = True
            self.start_time = time.time()

            self.is_initialized = True

            print("✓ Câmera OV5647 inicializada com H.264 hardware encoder")
            print(f"  Resolução: {self.resolution[0]}x{self.resolution[1]}")
            print(f"  Bitrate: {self.bitrate / 1000000:.1f} Mbps")
            print(f"  Encoder: H.264 (VideoCore VI hardware)")

            return True

        except Exception as e:
            print(f"✗ Erro ao inicializar câmera: {e}")
            print("\nVerifique:")
            print("1. Cabo da câmera conectado corretamente")
            print("2. Câmera habilitada: sudo raspi-config -> Interface Options -> Camera")
            print("3. Sistema reiniciado após habilitar")

            self.is_initialized = False
            return False

    def capture_frame(self):
        """
        Obtém o frame H.264 mais recente do buffer

        Returns:
            bytes: Frame H.264 codificado (NAL units), ou None se não disponível
        """
        if not self.is_initialized or self.output is None:
            return None

        try:
            frame_info = self.output.get_frame()

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
        Obtém frame H.264 com metadados

        Returns:
            dict: {'data': bytes, 'keyframe': bool, 'timestamp': float, 'size': int}
        """
        if not self.is_initialized or self.output is None:
            return None

        try:
            frame_info = self.output.get_frame()

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
            "bitrate": self.bitrate,
            "bitrate_mbps": self.bitrate / 1000000,
            "last_capture_time": self.last_capture_time,
            "last_frame_size": self.last_frame_size,
            "encoder": "H.264 Hardware",
        }

        # Estatísticas do output
        if self.output:
            stats["encoder_frames"] = self.output.frame_count
            stats["encoder_bytes"] = self.output.total_bytes

            if self.start_time:
                elapsed = time.time() - self.start_time
                if elapsed > 0:
                    stats["actual_bitrate"] = (self.output.total_bytes * 8) / elapsed
                    stats["actual_fps"] = self.output.frame_count / elapsed

        return stats

    def set_bitrate(self, bitrate):
        """
        Altera o bitrate do encoder (requer reinicialização)

        Args:
            bitrate (int): Novo bitrate em bps
        """
        if bitrate > 0:
            self.bitrate = bitrate
            print(f"Bitrate alterado para: {bitrate / 1000000:.1f} Mbps")
            print("⚠ Reinicialize a câmera para aplicar a mudança")
        else:
            print("⚠ Bitrate deve ser maior que 0")

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
            self.output = None

        except Exception as e:
            print(f"⚠ Erro ao finalizar câmera: {e}")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()
