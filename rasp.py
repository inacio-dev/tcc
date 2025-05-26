#!/usr/bin/env python3
# Servidor UDP para Raspberry Pi usando exclusivamente PiCamera2
# Envia frames de vídeo via UDP

import socket
import struct
import time

import cv2
from picamera2 import Picamera2

# Configurações de rede - ALTERE O IP PARA O DO SEU PC
PC_IP = "192.168.5.120"  # IP do computador que receberá o vídeo
PC_PORT = 9999  # Porta para comunicação

# Configurações da câmera OV5647
RESOLUTION = (640, 480)  # Resolução otimizada para OV5647
JPEG_QUALITY = 20  # Qualidade da compressão JPEG (1-100) - menor = mais compressão
FRAME_RATE = 30  # Taxa de frames desejada


def main():
    print(f"Iniciando transmissão para {PC_IP}:{PC_PORT}")
    print("Utilizando exclusivamente PiCamera2")
    print(
        f"Resolução: {RESOLUTION[0]}x{RESOLUTION[1]}, FPS: {FRAME_RATE}, Qualidade JPEG: {JPEG_QUALITY}"
    )

    # Inicializa a câmera utilizando apenas PiCamera2
    try:
        # Inicializa a PiCamera2
        camera = Picamera2()

        # Configuração otimizada para OV5647
        config = camera.create_preview_configuration(
            main={"size": RESOLUTION, "format": "RGB888"},
            buffer_count=4,  # Mais buffers para melhor desempenho
        )
        camera.configure(config)

        # Configura limite de duração de frame para controlar FPS
        try:
            camera.set_controls(
                {"FrameDurationLimits": (1000000 // FRAME_RATE, 1000000 // FRAME_RATE)}
            )
        except Exception as e:
            print(f"Aviso: Não foi possível configurar FrameDurationLimits: {e}")
            print("Continuando com configuração padrão...")

        # Inicia a câmera
        camera.start()

        # Pequena pausa para a câmera inicializar completamente
        time.sleep(0.5)

    except Exception as e:
        print(f"Erro ao inicializar PiCamera2: {e}")
        return

    # Cria o socket UDP
    try:
        server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Aumenta o buffer de envio
        server.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 65536)
    except Exception as e:
        print(f"Erro ao criar socket: {e}")
        if "camera" in locals():
            camera.close()
        return

    print("Iniciando envio de frames...")

    try:
        last_time = time.time()
        frames_sent = 0

        while True:
            # Captura um frame da PiCamera2
            frame = camera.capture_array()

            # Converte de RGB para BGR para uso com OpenCV
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Codifica o frame como JPEG
            _, encoded_frame = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
            )
            data = encoded_frame.tobytes()

            # Cria o pacote com o tamanho do frame primeiro
            # Use '<i' para garantir little-endian (padrão no Raspberry Pi)
            message = struct.pack("<i", len(data)) + data

            # Envia o pacote
            server.sendto(message, (PC_IP, PC_PORT))

            frames_sent += 1

            # Exibe estatísticas a cada segundo
            current_time = time.time()
            elapsed = current_time - last_time
            if elapsed >= 1.0:
                fps = frames_sent / elapsed
                print(f"FPS: {fps:.1f} - Tamanho do frame: {len(data)} bytes")
                frames_sent = 0
                last_time = current_time

            # Controle de taxa de frames simples
            # Apenas adiciona um pequeno atraso se estamos processando muito rápido
            processing_time = time.time() - current_time
            if processing_time < 1.0 / FRAME_RATE:
                time.sleep(max(0, 1.0 / FRAME_RATE - processing_time))

    except KeyboardInterrupt:
        print("Transmissão interrompida pelo usuário")
    except Exception as e:
        print(f"Erro durante a transmissão: {e}")
        import traceback

        traceback.print_exc()
    finally:
        # Envia sinal de encerramento
        try:
            server.sendto(struct.pack("B", 1), (PC_IP, PC_PORT))
        except:
            pass

        # Libera recursos
        if "camera" in locals():
            camera.close()
        if "server" in locals():
            server.close()

        print("Transmissão encerrada")


if __name__ == "__main__":
    main()
