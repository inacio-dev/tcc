#!/usr/bin/env python3
"""
test_camera_h264.py - Teste de captura H.264 da câmera OV5647

Testa se o encoder H.264 está funcionando e produzindo frames.
Execute no Raspberry Pi para verificar se a câmera está capturando.

Uso: python test/test_camera_h264.py
"""

import io
import time
import threading
from collections import deque

try:
    from picamera2 import Picamera2
    from picamera2.encoders import H264Encoder
    from picamera2.outputs import FileOutput
    PICAMERA2_AVAILABLE = True
except ImportError:
    PICAMERA2_AVAILABLE = False
    print("❌ picamera2 não disponível - execute no Raspberry Pi")


class TestBuffer(io.BufferedIOBase):
    """Buffer de teste para capturar frames H.264"""

    def __init__(self):
        self.frames = deque(maxlen=30)
        self.current_frame = io.BytesIO()
        self.lock = threading.Lock()
        self.write_count = 0
        self.total_bytes = 0
        self.frame_count = 0

    def write(self, data):
        """Recebe dados do encoder"""
        self.write_count += 1
        self.total_bytes += len(data)

        # Log detalhado dos primeiros writes
        if self.write_count <= 10:
            print(f"  [WRITE #{self.write_count}] {len(data)} bytes - primeiros 20 bytes: {data[:20].hex()}")

        with self.lock:
            # Detecta início de novo frame (NAL unit start code)
            is_new_frame = data[:4] == b'\x00\x00\x00\x01' or data[:3] == b'\x00\x00\x01'

            if is_new_frame:
                # Salva frame anterior se existir
                if self.current_frame.tell() > 0:
                    frame_data = self.current_frame.getvalue()
                    frame_size = len(frame_data)

                    # Detecta tipo de NAL
                    nal_type = self._get_nal_type(frame_data)
                    nal_name = self._nal_type_name(nal_type)

                    self.frames.append({
                        'data': frame_data,
                        'size': frame_size,
                        'nal_type': nal_type,
                        'nal_name': nal_name,
                        'timestamp': time.time()
                    })
                    self.frame_count += 1

                    # Log do frame completo
                    print(f"  [FRAME #{self.frame_count}] {frame_size} bytes - NAL type: {nal_type} ({nal_name})")

                # Inicia novo frame
                self.current_frame = io.BytesIO()

            self.current_frame.write(data)
            return len(data)

    def _get_nal_type(self, data):
        """Extrai tipo de NAL unit"""
        if len(data) < 5:
            return -1
        if data[:4] == b'\x00\x00\x00\x01':
            return data[4] & 0x1F
        elif data[:3] == b'\x00\x00\x01':
            return data[3] & 0x1F
        return -1

    def _nal_type_name(self, nal_type):
        """Nome do tipo de NAL"""
        names = {
            1: "Non-IDR slice",
            5: "IDR (keyframe)",
            6: "SEI",
            7: "SPS",
            8: "PPS",
            9: "AUD",
        }
        return names.get(nal_type, f"Unknown({nal_type})")

    def get_frame(self):
        """Obtém frame mais recente"""
        with self.lock:
            if self.frames:
                return self.frames[-1]
            return None

    def flush(self):
        pass

    def readable(self):
        return False

    def writable(self):
        return True

    def seekable(self):
        return False

    def get_stats(self):
        """Retorna estatísticas"""
        return {
            'write_count': self.write_count,
            'total_bytes': self.total_bytes,
            'frame_count': self.frame_count,
            'frames_in_buffer': len(self.frames)
        }


def test_camera():
    """Testa a câmera OV5647 com encoder H.264"""

    if not PICAMERA2_AVAILABLE:
        print("❌ Teste não pode ser executado - picamera2 não disponível")
        return False

    print("=" * 60)
    print("TESTE DE CÂMERA OV5647 COM H.264 ENCODER")
    print("=" * 60)
    print()

    camera = None
    buffer = None

    try:
        # 1. Verificar câmeras disponíveis
        print("[1/5] Verificando câmeras disponíveis...")
        camera_info = Picamera2.global_camera_info()
        print(f"  Câmeras encontradas: {len(camera_info)}")
        for i, info in enumerate(camera_info):
            print(f"    [{i}] {info}")

        if len(camera_info) == 0:
            print("❌ Nenhuma câmera encontrada!")
            return False
        print("  ✓ Câmera detectada")
        print()

        # 2. Inicializar câmera
        print("[2/5] Inicializando Picamera2...")
        camera = Picamera2()

        # Configuração de vídeo
        video_config = camera.create_video_configuration(
            main={"size": (640, 480), "format": "XBGR8888"},
            encode="main"
        )
        camera.configure(video_config)
        print("  ✓ Configuração aplicada: 640x480")
        print()

        # 3. Criar encoder e buffer
        print("[3/5] Criando encoder H.264 e buffer...")
        encoder = H264Encoder(
            bitrate=1500000,  # 1.5 Mbps
            repeat=True,
            iperiod=30
        )
        buffer = TestBuffer()
        output = FileOutput(buffer)
        print("  ✓ Encoder H.264 criado (1.5 Mbps, keyframe a cada 30 frames)")
        print()

        # 4. Iniciar câmera e encoder
        print("[4/5] Iniciando câmera e encoder...")
        camera.start()
        time.sleep(0.5)  # Aguarda estabilização

        camera.start_encoder(encoder, output)
        print("  ✓ Câmera e encoder iniciados")
        print()

        # 5. Capturar frames por 5 segundos
        print("[5/5] Capturando frames por 5 segundos...")
        print("-" * 60)

        start_time = time.time()

        while time.time() - start_time < 5.0:
            time.sleep(0.1)

            # Mostra progresso a cada segundo
            elapsed = time.time() - start_time
            if int(elapsed) > int(elapsed - 0.1):
                stats = buffer.get_stats()
                print(f"  [{elapsed:.0f}s] Frames: {stats['frame_count']}, Writes: {stats['write_count']}, Bytes: {stats['total_bytes']}")

        print("-" * 60)
        print()

        # Resultados finais
        stats = buffer.get_stats()
        elapsed = time.time() - start_time

        print("=" * 60)
        print("RESULTADOS DO TESTE")
        print("=" * 60)
        print(f"  Tempo de teste:     {elapsed:.1f} segundos")
        print(f"  Total de writes:    {stats['write_count']}")
        print(f"  Total de bytes:     {stats['total_bytes']} ({stats['total_bytes']/1024:.1f} KB)")
        print(f"  Frames completos:   {stats['frame_count']}")
        print(f"  FPS médio:          {stats['frame_count']/elapsed:.1f}")
        print(f"  Bitrate médio:      {(stats['total_bytes']*8/elapsed)/1000000:.2f} Mbps")
        print()

        # Verificar último frame
        last_frame = buffer.get_frame()
        if last_frame:
            print(f"  Último frame: {last_frame['size']} bytes, NAL: {last_frame['nal_name']}")

        print()

        if stats['frame_count'] > 0:
            print("✅ TESTE PASSOU - Encoder H.264 está funcionando!")
            return True
        else:
            print("❌ TESTE FALHOU - Nenhum frame foi capturado")
            print()
            print("Possíveis causas:")
            print("  1. Encoder não está produzindo dados")
            print("  2. FileOutput não está chamando write()")
            print("  3. Problema no buffer circular")
            return False

    except Exception as e:
        print(f"❌ ERRO: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Cleanup
        print()
        print("Limpando recursos...")
        try:
            if camera:
                camera.stop_encoder()
                camera.close()
                print("  ✓ Câmera finalizada")
        except Exception as e:
            print(f"  ⚠ Erro ao finalizar: {e}")


def test_simple_capture():
    """Teste mais simples - apenas verifica se a câmera captura algo"""

    if not PICAMERA2_AVAILABLE:
        return False

    print()
    print("=" * 60)
    print("TESTE SIMPLES - CAPTURA JPEG")
    print("=" * 60)
    print()

    try:
        print("Capturando um frame JPEG...")
        camera = Picamera2()
        camera.start()
        time.sleep(1)

        # Captura array numpy
        frame = camera.capture_array()
        print(f"  ✓ Frame capturado: {frame.shape}")

        camera.close()
        print("  ✓ Câmera funciona corretamente")
        return True

    except Exception as e:
        print(f"  ❌ Erro: {e}")
        return False


if __name__ == "__main__":
    print()

    # Primeiro teste simples
    simple_ok = test_simple_capture()

    if simple_ok:
        print()
        # Depois teste H.264
        h264_ok = test_camera()

        print()
        print("=" * 60)
        print("RESUMO FINAL")
        print("=" * 60)
        print(f"  Captura simples: {'✅ OK' if simple_ok else '❌ FALHOU'}")
        print(f"  Encoder H.264:   {'✅ OK' if h264_ok else '❌ FALHOU'}")
        print()
    else:
        print()
        print("❌ Câmera não funciona - verifique conexões e configuração")
