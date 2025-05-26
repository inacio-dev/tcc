#!/usr/bin/env python3
# Servidor UDP para Raspberry Pi com PiCamera2 e dados de sensores
# Envia frames de vídeo + dados de sensores via UDP

import json
import socket
import struct
import time
import math

import cv2
from picamera2 import Picamera2

# Configurações de rede - ALTERE O IP PARA O DO SEU PC
PC_IP = "192.168.5.120"  # IP do computador que receberá o vídeo
PC_PORT = 9999  # Porta para comunicação

# Configurações da câmera OV5647
RESOLUTION = (640, 480)  # Resolução otimizada para OV5647
JPEG_QUALITY = 20  # Qualidade da compressão JPEG (1-100) - menor = mais compressão
FRAME_RATE = 30  # Taxa de frames desejada

# Estrutura do pacote:
# 4 bytes: tamanho do frame JPEG
# 4 bytes: tamanho dos dados JSON dos sensores
# N bytes: dados do frame JPEG
# M bytes: dados JSON dos sensores


class SensorData:
    """Classe para simular e gerenciar dados de sensores"""

    def __init__(self):
        self.start_time = time.time()
        self.last_update = time.time()

        # Variáveis dos sensores (simuladas - substitua pela leitura real)
        self.accel_x = 0.0
        self.accel_y = 0.0
        self.accel_z = 9.81  # Gravidade padrão

        self.gyro_x = 0.0
        self.gyro_y = 0.0
        self.gyro_z = 0.0

        self.velocidade = 0.0
        self.steering_angle = 0.0
        self.bateria_nivel = 100.0
        self.temperatura = 25.0

        # Contadores e status
        self.frame_count = 0
        self.packet_count = 0

    def update_sensors(self):
        """
        Atualiza os dados dos sensores.
        SUBSTITUA esta função pela leitura real dos seus sensores!
        """
        current_time = time.time()
        elapsed = current_time - self.start_time
        dt = current_time - self.last_update

        # SIMULAÇÃO - Substitua por leitura real dos sensores

        # Simula movimento senoidal para demonstração
        self.accel_x = math.sin(elapsed * 0.5) * 2.0  # ±2g
        self.accel_y = math.cos(elapsed * 0.3) * 1.0  # ±1g

        # Simula rotação lenta
        self.gyro_z = math.sin(elapsed * 0.2) * 45.0  # ±45°/s

        # Simula variação de velocidade
        self.velocidade = abs(math.sin(elapsed * 0.1)) * 50.0  # 0-50 km/h

        # Simula ângulo do volante
        self.steering_angle = math.sin(elapsed * 0.4) * 30.0  # ±30°

        # Simula descarga lenta da bateria
        self.bateria_nivel = max(0, 100 - elapsed * 0.1)  # 0.1% por segundo

        # Simula variação de temperatura
        self.temperatura = 25 + math.sin(elapsed * 0.05) * 5  # 20-30°C

        self.last_update = current_time

    def get_sensor_dict(self):
        """Retorna dicionário com todos os dados dos sensores"""
        return {
            # Acelerômetro (m/s²)
            "accel_x": round(self.accel_x, 3),
            "accel_y": round(self.accel_y, 3),
            "accel_z": round(self.accel_z, 3),
            # Giroscópio (°/s)
            "gyro_x": round(self.gyro_x, 3),
            "gyro_y": round(self.gyro_y, 3),
            "gyro_z": round(self.gyro_z, 3),
            # Dados do veículo
            "velocidade": round(self.velocidade, 1),  # km/h
            "steering_angle": round(self.steering_angle, 1),  # graus
            # Status do sistema
            "bateria_nivel": round(self.bateria_nivel, 1),  # %
            "temperatura": round(self.temperatura, 1),  # °C
            # Metadados
            "timestamp": round(time.time(), 3),
            "frame_count": self.frame_count,
            "packet_count": self.packet_count,
        }


def main():
    print(f"Iniciando transmissão para {PC_IP}:{PC_PORT}")
    print("Utilizando PiCamera2 + dados de sensores")
    print(
        f"Resolução: {RESOLUTION[0]}x{RESOLUTION[1]}, FPS: {FRAME_RATE}, Qualidade JPEG: {JPEG_QUALITY}"
    )

    # Inicializa os sensores
    sensors = SensorData()

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
        server.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, 131072)  # 128KB
    except Exception as e:
        print(f"Erro ao criar socket: {e}")
        if "camera" in locals():
            camera.close()
        return

    print("Iniciando envio de frames com dados de sensores...")

    try:
        last_time = time.time()
        frames_sent = 0
        last_sensor_display = time.time()

        while True:
            # Atualiza dados dos sensores
            sensors.update_sensors()

            # Captura um frame da PiCamera2
            frame = camera.capture_array()

            # Converte de RGB para BGR para uso com OpenCV
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

            # Codifica o frame como JPEG
            _, encoded_frame = cv2.imencode(
                ".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
            )
            frame_data = encoded_frame.tobytes()

            # Obtém dados dos sensores como JSON
            sensor_dict = sensors.get_sensor_dict()
            sensor_json = json.dumps(sensor_dict)
            sensor_data = sensor_json.encode("utf-8")

            # Atualiza contadores
            sensors.frame_count += 1
            sensors.packet_count += 1

            # Cria o pacote completo:
            # 4 bytes: tamanho do frame
            # 4 bytes: tamanho dos dados de sensor
            # N bytes: dados do frame
            # M bytes: dados do sensor
            frame_size = len(frame_data)
            sensor_size = len(sensor_data)

            message = (
                struct.pack(
                    "<I", frame_size
                )  # Tamanho do frame (little-endian unsigned int)
                + struct.pack("<I", sensor_size)  # Tamanho dos dados do sensor
                + frame_data  # Dados do frame JPEG
                + sensor_data  # Dados do sensor (JSON)
            )

            # Envia o pacote
            try:
                server.sendto(message, (PC_IP, PC_PORT))
            except Exception as e:
                print(f"Erro ao enviar pacote: {e}")
                continue

            frames_sent += 1

            # Exibe estatísticas a cada segundo
            current_time = time.time()
            elapsed = current_time - last_time
            if elapsed >= 1.0:
                fps = frames_sent / elapsed
                total_size = len(message)
                print(
                    f"FPS: {fps:.1f} - Frame: {frame_size} bytes - Sensores: {sensor_size} bytes - Total: {total_size} bytes"
                )
                frames_sent = 0
                last_time = current_time

            # Exibe dados dos sensores a cada 2 segundos
            if current_time - last_sensor_display >= 2.0:
                print(
                    f"Sensores - Accel: ({sensor_dict['accel_x']:.2f}, {sensor_dict['accel_y']:.2f}, {sensor_dict['accel_z']:.2f}) | "
                    + f"Gyro Z: {sensor_dict['gyro_z']:.1f}°/s | Vel: {sensor_dict['velocidade']:.1f} km/h | "
                    + f"Bateria: {sensor_dict['bateria_nivel']:.1f}%"
                )
                last_sensor_display = current_time

            # Controle de taxa de frames simples
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
            # Pacote especial de encerramento (sem dados de sensor)
            termination_packet = struct.pack("<I", 0) + struct.pack("<I", 0)
            server.sendto(termination_packet, (PC_IP, PC_PORT))
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
