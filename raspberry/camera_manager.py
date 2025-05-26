#!/usr/bin/env python3
"""
camera_manager.py - Gerenciamento da Câmera OV5647
Responsável por capturar e codificar frames de vídeo

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
"""

import cv2
import time
from picamera2 import Picamera2


class CameraManager:
    """Gerencia a captura de vídeo da câmera OV5647"""

    def __init__(self, resolution=(640, 480), frame_rate=30, jpeg_quality=20):
        """
        Inicializa o gerenciador da câmera

        Args:
            resolution (tuple): Resolução do vídeo (largura, altura)
            frame_rate (int): Taxa de frames por segundo
            jpeg_quality (int): Qualidade JPEG (1-100, menor = mais compressão)
        """
        self.resolution = resolution
        self.frame_rate = frame_rate
        self.jpeg_quality = jpeg_quality
        self.camera = None
        self.is_initialized = False

        # Estatísticas
        self.frames_captured = 0
        self.last_frame = None
        self.last_capture_time = time.time()

    def initialize(self):
        """
        Inicializa a câmera OV5647

        Returns:
            bool: True se inicializada com sucesso, False caso contrário
        """
        try:
            print("Inicializando câmera OV5647...")

            # Cria instância da PiCamera2
            self.camera = Picamera2()

            # Configuração otimizada para OV5647
            config = self.camera.create_preview_configuration(
                main={"size": self.resolution, "format": "RGB888"},
                buffer_count=4,  # Múltiplos buffers para melhor performance
            )

            # Aplica configuração
            self.camera.configure(config)

            # Tenta configurar limitação de duração de frame para controlar FPS
            try:
                frame_duration = 1000000 // self.frame_rate  # microssegundos
                self.camera.set_controls(
                    {"FrameDurationLimits": (frame_duration, frame_duration)}
                )
                print(f"✓ Frame rate configurado para {self.frame_rate} FPS")
            except Exception as e:
                print(f"⚠ Aviso: Não foi possível configurar FrameDurationLimits: {e}")
                print("Continuando com configuração padrão...")

            # Inicia a câmera
            self.camera.start()

            # Aguarda estabilização
            time.sleep(0.5)

            self.is_initialized = True

            print("✓ Câmera OV5647 inicializada com sucesso")
            print(f"  - Resolução: {self.resolution[0]}x{self.resolution[1]}")
            print(f"  - Taxa de frames: {self.frame_rate} FPS")
            print(f"  - Qualidade JPEG: {self.jpeg_quality}%")

            return True

        except Exception as e:
            print(f"✗ Erro ao inicializar câmera OV5647: {e}")
            print("\nVerifique:")
            print("1. Cabo da câmera conectado corretamente")
            print(
                "2. Câmera habilitada: sudo raspi-config -> Interface Options -> Camera"
            )
            print("3. Sistema reiniciado após habilitar")

            self.is_initialized = False
            return False

    def capture_frame(self):
        """
        Captura um frame da câmera

        Returns:
            bytes: Frame codificado em JPEG, ou None em caso de erro
        """
        if not self.is_initialized or self.camera is None:
            print("⚠ Câmera não inicializada")
            return None

        try:
            # Captura frame RGB
            frame = self.camera.capture_array()

            # Converte de RGB para BGR (formato OpenCV)
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Codifica como JPEG
            success, encoded_frame = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.jpeg_quality]
            )

            if success:
                # Atualiza estatísticas
                self.frames_captured += 1
                self.last_frame = frame.copy()
                self.last_capture_time = time.time()

                return encoded_frame.tobytes()
            else:
                print("⚠ Erro ao codificar frame JPEG")
                return None

        except Exception as e:
            print(f"⚠ Erro ao capturar frame: {e}")
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
        Obtém estatísticas da câmera

        Returns:
            dict: Estatísticas de captura
        """
        return {
            "frames_captured": self.frames_captured,
            "is_initialized": self.is_initialized,
            "resolution": self.resolution,
            "frame_rate": self.frame_rate,
            "jpeg_quality": self.jpeg_quality,
            "last_capture_time": self.last_capture_time,
        }

    def set_jpeg_quality(self, quality):
        """
        Altera a qualidade JPEG dinamicamente

        Args:
            quality (int): Nova qualidade (1-100)
        """
        if 1 <= quality <= 100:
            self.jpeg_quality = quality
            print(f"Qualidade JPEG alterada para: {quality}%")
        else:
            print("⚠ Qualidade deve estar entre 1 e 100")

    def set_frame_rate(self, frame_rate):
        """
        Altera a taxa de frames dinamicamente (requer reinicialização)

        Args:
            frame_rate (int): Nova taxa de frames
        """
        if frame_rate > 0:
            self.frame_rate = frame_rate
            print(f"Taxa de frames alterada para: {frame_rate} FPS")
            print("⚠ Reinicialize a câmera para aplicar a mudança")
        else:
            print("⚠ Taxa de frames deve ser maior que 0")

    def cleanup(self):
        """Libera recursos da câmera"""
        try:
            if self.camera is not None:
                self.camera.close()
                print("✓ Câmera OV5647 finalizada")

            self.is_initialized = False
            self.camera = None

        except Exception as e:
            print(f"⚠ Erro ao finalizar câmera: {e}")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()


# Exemplo de uso
if __name__ == "__main__":
    # Teste da classe CameraManager
    print("=== TESTE DO CAMERA MANAGER ===")

    # Cria instância
    camera_mgr = CameraManager(resolution=(640, 480), frame_rate=30, jpeg_quality=20)

    # Inicializa
    if camera_mgr.initialize():
        print("Capturando 10 frames de teste...")

        start_time = time.time()

        for i in range(10):
            # Captura frame
            frame_data = camera_mgr.capture_frame()

            if frame_data:
                # Mostra informações
                info = camera_mgr.get_frame_size_info(frame_data)
                print(f"Frame {i+1}: {info['size_kb']} KB")
            else:
                print(f"Frame {i+1}: Erro na captura")

            # Aguarda um pouco
            time.sleep(0.1)

        end_time = time.time()

        # Mostra estatísticas
        stats = camera_mgr.get_statistics()
        elapsed = end_time - start_time
        actual_fps = stats["frames_captured"] / elapsed

        print(f"\n=== ESTATÍSTICAS ===")
        print(f"Frames capturados: {stats['frames_captured']}")
        print(f"Tempo decorrido: {elapsed:.2f}s")
        print(f"FPS real: {actual_fps:.2f}")

        # Finaliza
        camera_mgr.cleanup()

    else:
        print("✗ Falha ao inicializar câmera")
        print("Verifique a conexão e configuração da câmera")
