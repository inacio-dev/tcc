#!/usr/bin/env python3
"""
network_client.py - Cliente de Rede UDP
Responsável por receber pacotes UDP do Raspberry Pi

FORMATO DO PACOTE RECEBIDO:
==========================
| 4 bytes    | 4 bytes     | N bytes    | M bytes      |
| frame_size | sensor_size | frame_data | sensor_data  |

DADOS DOS SENSORES ESPERADOS:
============================
O cliente está preparado para receber TODOS os 37+ campos do BMI160:
- Dados raw do BMI160 (accel/gyro LSB)
- Dados físicos convertidos (m/s², °/s)
- Forças G calculadas (frontal, lateral, vertical)
- Ângulos integrados (roll, pitch, yaw)
- Eventos detectados (curvas, freios, aceleração, impactos)
- Intensidades de force feedback (volante, pedais, assento)
- Configurações do sensor (ranges, taxa)
- Metadados (timestamp, contadores)
"""

import socket
import struct
import json
import time
import numpy as np
from typing import Optional, Dict, Any


class NetworkClient:
    """Cliente de rede para recepção de dados UDP"""

    def __init__(
        self,
        port=9999,
        buffer_size=131072,
        host="0.0.0.0",
        log_queue=None,
        status_queue=None,
        sensor_queue=None,
        video_queue=None,
    ):
        """
        Inicializa o cliente de rede

        Args:
            port (int): Porta UDP para escutar
            buffer_size (int): Tamanho do buffer UDP
            host (str): IP para escutar (0.0.0.0 = todas as interfaces)
            log_queue (Queue): Fila para mensagens de log
            status_queue (Queue): Fila para estatísticas de conexão
            sensor_queue (Queue): Fila para dados de sensores
            video_queue (Queue): Fila para frames de vídeo
        """
        self.port = port
        self.buffer_size = buffer_size
        self.host = host

        # Filas de comunicação
        self.log_queue = log_queue
        self.status_queue = status_queue
        self.sensor_queue = sensor_queue
        self.video_queue = video_queue

        # Socket UDP
        self.socket = None
        self.is_running = False

        # Status da conexão
        self.connected_addr = None
        self.last_packet_time = time.time()
        self.connection_timeout = 3.0  # segundos

        # Estatísticas
        self.packets_received = 0
        self.bytes_received = 0
        self.frames_received = 0
        self.sensor_packets_received = 0
        self.last_stats_time = time.time()
        self.start_time = time.time()

        # Controle de erros
        self.decode_errors = 0
        self.packet_errors = 0
        self.last_error_log = 0

    def _log(self, level, message):
        """Envia mensagem para fila de log"""
        if self.log_queue:
            self.log_queue.put((level, message))
        else:
            print(f"[{level}] {message}")

    def _update_status(self, status_dict):
        """Envia atualizações de status"""
        if self.status_queue:
            self.status_queue.put(status_dict)

    def _send_sensor_data(self, sensor_data):
        """Envia dados de sensores para a interface"""
        if self.sensor_queue:
            self.sensor_queue.put(sensor_data)

    def _send_video_frame(self, frame_data):
        """Envia frame de vídeo para exibição"""
        if self.video_queue:
            self.video_queue.put(frame_data)

    def initialize(self):
        """
        Inicializa o socket UDP

        Returns:
            bool: True se inicializado com sucesso
        """
        try:
            self._log("INFO", f"Inicializando cliente UDP na porta {self.port}")

            # Cria socket UDP
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Configura buffer de recepção
            self.socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_RCVBUF, self.buffer_size * 2
            )
            actual_buffer = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF)

            # Timeout para não bloquear indefinidamente
            self.socket.settimeout(0.5)

            # Vincula à porta
            self.socket.bind((self.host, self.port))

            self._log("INFO", f"Socket UDP inicializado com sucesso")
            self._log("INFO", f"Buffer de recepção: {actual_buffer // 1024} KB")
            self._log("INFO", f"Aguardando conexão do Raspberry Pi...")

            return True

        except Exception as e:
            self._log("ERROR", f"Erro ao inicializar socket UDP: {e}")
            return False

    def parse_packet(self, packet):
        """
        Analisa pacote UDP recebido

        Args:
            packet (bytes): Dados do pacote recebido

        Returns:
            tuple: (frame_data, sensor_data) ou (None, None) em caso de erro
        """
        try:
            # Verifica tamanho mínimo (8 bytes para os tamanhos)
            if len(packet) < 8:
                self._log("ERROR", f"Pacote muito pequeno: {len(packet)} bytes")
                return None, None

            # Extrai tamanhos dos dados
            frame_size, sensor_size = struct.unpack("<II", packet[:8])

            # Verifica se é sinal de término
            if frame_size == 0 and sensor_size == 0:
                self._log("INFO", "Sinal de encerramento recebido do servidor")
                return "TERMINATE", None

            # Valida tamanhos
            if frame_size < 0 or frame_size > 1000000:  # Máximo 1MB para frame
                self._log("ERROR", f"Tamanho de frame inválido: {frame_size}")
                return None, None

            if sensor_size < 0 or sensor_size > 50000:  # Máximo 50KB para sensores
                self._log("ERROR", f"Tamanho de sensor inválido: {sensor_size}")
                return None, None

            # Calcula posições dos dados
            frame_start = 8
            frame_end = frame_start + frame_size
            sensor_start = frame_end
            sensor_end = sensor_start + sensor_size

            # Verifica se o pacote contém todos os dados
            expected_size = 8 + frame_size + sensor_size
            if len(packet) < expected_size:
                self._log(
                    "ERROR", f"Pacote incompleto: {len(packet)} < {expected_size}"
                )
                return None, None

            # Extrai dados do frame
            frame_data = None
            if frame_size > 0:
                frame_data = packet[frame_start:frame_end]

            # Extrai dados dos sensores
            sensor_data = None
            if sensor_size > 0:
                try:
                    sensor_bytes = packet[sensor_start:sensor_end]
                    sensor_json = sensor_bytes.decode("utf-8")
                    sensor_data = json.loads(sensor_json)
                except (json.JSONDecodeError, UnicodeDecodeError) as e:
                    self._log("ERROR", f"Erro ao decodificar dados de sensores: {e}")
                    self.decode_errors += 1

            return frame_data, sensor_data

        except Exception as e:
            current_time = time.time()
            if current_time - self.last_error_log > 2.0:  # Log a cada 2 segundos
                self._log("ERROR", f"Erro ao analisar pacote: {e}")
                self.last_error_log = current_time
            self.packet_errors += 1
            return None, None

    def update_connection_status(self, addr):
        """Atualiza status da conexão"""
        if self.connected_addr != addr:
            self.connected_addr = addr
            connection_status = f"Conectado a {addr[0]}:{addr[1]}"
            self._log("INFO", f"Conexão estabelecida com {addr[0]}:{addr[1]}")
            self._update_status({"connection": connection_status})

        self.last_packet_time = time.time()

    def check_connection_timeout(self):
        """Verifica timeout da conexão"""
        if (
            self.connected_addr
            and time.time() - self.last_packet_time > self.connection_timeout
        ):
            self._log("WARNING", f"Conexão perdida com {self.connected_addr}")
            self.connected_addr = None
            self._update_status({"connection": "Desconectado"})

    def update_statistics(self):
        """Atualiza e envia estatísticas"""
        current_time = time.time()
        elapsed = current_time - self.last_stats_time

        if elapsed >= 2.0:  # Atualiza a cada 2 segundos
            total_elapsed = current_time - self.start_time

            # Calcula taxas
            packets_per_second = (
                self.packets_received / total_elapsed if total_elapsed > 0 else 0
            )
            bytes_per_second = (
                self.bytes_received / total_elapsed if total_elapsed > 0 else 0
            )
            fps = self.frames_received / total_elapsed if total_elapsed > 0 else 0

            # Envia estatísticas
            self._update_status(
                {
                    "packets": self.packets_received,
                    "data": self.bytes_received / 1024 / 1024,  # MB
                    "fps": fps,
                    "packets_per_second": packets_per_second,
                    "bytes_per_second": bytes_per_second,
                    "decode_errors": self.decode_errors,
                    "packet_errors": self.packet_errors,
                }
            )

            self.last_stats_time = current_time

    def run_receiver(self):
        """Loop principal de recepção de dados"""
        if not self.initialize():
            self._log("ERROR", "Falha ao inicializar cliente de rede")
            return

        self.is_running = True
        self._log("INFO", "Cliente de rede iniciado - aguardando dados...")

        try:
            while self.is_running:
                try:
                    # Recebe pacote
                    packet, addr = self.socket.recvfrom(self.buffer_size)

                    # Atualiza estatísticas
                    self.packets_received += 1
                    self.bytes_received += len(packet)

                    # Atualiza status da conexão
                    self.update_connection_status(addr)

                    # Processa pacote
                    frame_data, sensor_data = self.parse_packet(packet)

                    # Verifica sinal de término
                    if frame_data == "TERMINATE":
                        break

                    # Envia frame de vídeo
                    if frame_data is not None:
                        self.frames_received += 1
                        self._send_video_frame(frame_data)

                    # Envia dados de sensores
                    if sensor_data is not None:
                        self.sensor_packets_received += 1
                        self._send_sensor_data(sensor_data)

                    # Atualiza estatísticas periodicamente
                    self.update_statistics()

                except socket.timeout:
                    # Timeout é normal, verifica conexão
                    self.check_connection_timeout()
                    continue

                except Exception as e:
                    current_time = time.time()
                    if (
                        current_time - self.last_error_log > 5.0
                    ):  # Log a cada 5 segundos
                        self._log("ERROR", f"Erro na recepção: {e}")
                        self.last_error_log = current_time
                    time.sleep(0.1)

        except KeyboardInterrupt:
            self._log("INFO", "Recepção interrompida pelo usuário")
        finally:
            self.stop()

    def get_statistics(self):
        """
        Obtém estatísticas detalhadas

        Returns:
            dict: Estatísticas do cliente
        """
        elapsed = time.time() - self.start_time

        return {
            "packets_received": self.packets_received,
            "bytes_received": self.bytes_received,
            "frames_received": self.frames_received,
            "sensor_packets_received": self.sensor_packets_received,
            "decode_errors": self.decode_errors,
            "packet_errors": self.packet_errors,
            "elapsed_time": round(elapsed, 2),
            "packets_per_second": (
                round(self.packets_received / elapsed, 2) if elapsed > 0 else 0
            ),
            "bytes_per_second": (
                round(self.bytes_received / elapsed, 2) if elapsed > 0 else 0
            ),
            "fps": round(self.frames_received / elapsed, 2) if elapsed > 0 else 0,
            "connected": self.connected_addr is not None,
            "connected_to": (
                str(self.connected_addr) if self.connected_addr else "Nenhum"
            ),
        }

    def stop(self):
        """Para o cliente de rede"""
        self._log("INFO", "Parando cliente de rede...")

        self.is_running = False

        if self.socket:
            try:
                self.socket.close()
            except:
                pass

        # Envia estatísticas finais
        stats = self.get_statistics()
        self._log("INFO", f"Estatísticas finais:")
        self._log("INFO", f"  - Pacotes recebidos: {stats['packets_received']}")
        self._log("INFO", f"  - Frames de vídeo: {stats['frames_received']}")
        self._log("INFO", f"  - Dados de sensores: {stats['sensor_packets_received']}")
        self._log("INFO", f"  - Taxa média: {stats['fps']:.1f} FPS")
        self._log("INFO", f"  - Erros de decodificação: {stats['decode_errors']}")

        self._log("INFO", "Cliente de rede parado")


# Teste independente
if __name__ == "__main__":
    import queue

    print("=== TESTE DO NETWORK CLIENT ===")

    # Cria filas de teste
    log_q = queue.Queue()
    status_q = queue.Queue()
    sensor_q = queue.Queue()
    video_q = queue.Queue()

    # Cria cliente
    client = NetworkClient(
        port=9999,
        log_queue=log_q,
        status_queue=status_q,
        sensor_queue=sensor_q,
        video_queue=video_q,
    )

    print("Iniciando recepção de teste...")
    print("Execute o servidor no Raspberry Pi para testar")
    print("Pressione Ctrl+C para parar")

    try:
        # Inicia recepção em thread separada para poder mostrar logs
        import threading

        receiver_thread = threading.Thread(target=client.run_receiver, daemon=True)
        receiver_thread.start()

        # Mostra logs em tempo real
        while True:
            try:
                # Processa logs
                while not log_q.empty():
                    level, message = log_q.get_nowait()
                    print(f"[{level}] {message}")

                # Processa status
                while not status_q.empty():
                    status = status_q.get_nowait()
                    if "fps" in status:
                        print(
                            f"📊 FPS: {status['fps']:.1f}, Pacotes: {status['packets']}"
                        )

                # Processa sensores (mostra apenas timestamp)
                while not sensor_q.empty():
                    sensor_data = sensor_q.get_nowait()
                    if "timestamp" in sensor_data:
                        print(
                            f"🔧 Dados de sensores recebidos: {sensor_data['timestamp']}"
                        )

                # Processa vídeo (mostra apenas tamanho)
                while not video_q.empty():
                    frame_data = video_q.get_nowait()
                    print(f"🎥 Frame recebido: {len(frame_data)} bytes")

                time.sleep(0.1)

            except KeyboardInterrupt:
                break

    except KeyboardInterrupt:
        print("\nParando teste...")

    client.stop()
    print("Teste concluído")
