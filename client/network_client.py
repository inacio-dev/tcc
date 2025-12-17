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
    """Cliente de rede para comunicação UDP bidirecional"""

    def __init__(
        self,
        port=9999,
        command_port=9998,
        buffer_size=131072,
        host="0.0.0.0",
        rpi_ip=None,
        client_ip=None,
        log_queue=None,
        status_queue=None,
        sensor_queue=None,
        video_queue=None,
    ):
        """
        Inicializa o cliente de rede bidirecional

        Args:
            port (int): Porta UDP para receber dados
            command_port (int): Porta UDP para enviar comandos
            buffer_size (int): Tamanho do buffer UDP
            host (str): IP para escutar (0.0.0.0 = todas as interfaces)
            log_queue (Queue): Fila para mensagens de log
            status_queue (Queue): Fila para estatísticas de conexão
            sensor_queue (Queue): Fila para dados de sensores
            video_queue (Queue): Fila para frames de vídeo
        """
        self.port = port
        self.command_port = command_port
        self.buffer_size = buffer_size
        self.host = host
        self.client_ip = client_ip  # IP deste cliente

        # Resolve hostname para IP se necessário
        self.rpi_ip = None
        if rpi_ip:
            try:
                # Se for hostname (como f1car.local), resolve para IP
                resolved_ip = socket.gethostbyname(rpi_ip)
                self.rpi_ip = resolved_ip
                if resolved_ip != rpi_ip:
                    print(f"[NET] Hostname {rpi_ip} resolvido para {resolved_ip}")
            except socket.gaierror as e:
                print(f"[NET] ERRO: Não foi possível resolver {rpi_ip}: {e}")
                self.rpi_ip = rpi_ip  # Usa o valor original como fallback

        # Filas de comunicação
        self.log_queue = log_queue
        self.status_queue = status_queue
        self.sensor_queue = sensor_queue
        self.video_queue = video_queue

        # Sockets UDP
        self.receive_socket = None  # Para receber dados
        self.send_socket = None  # Para enviar comandos
        self.is_running = False

        # Status da conexão
        self.connected_addr = None
        self.raspberry_pi_ip = None
        self.is_connected_to_rpi = False
        self.last_packet_time = time.time()
        self.connection_timeout = 10.0  # segundos (aumentado para tolerar perdas UDP)

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
        Inicializa os sockets UDP para comunicação bidirecional

        Returns:
            bool: True se inicializado com sucesso
        """
        try:
            self._log("INFO", f"Inicializando cliente UDP bidirecional")
            self._log("INFO", f"Recebendo dados na porta {self.port}")
            self._log("INFO", f"Enviando comandos para porta {self.command_port}")

            # Cria socket para receber dados
            self.receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.receive_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

            # Buffer menor para tempo real (menos latência, mais responsivo)
            self.receive_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            # Timeout baixo para processamento em tempo real
            self.receive_socket.settimeout(0.001)  # 1ms timeout

            # Vincula socket à porta de recepção
            self.receive_socket.bind((self.host, self.port))

            # Cria socket para enviar comandos
            self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Timeout para não bloquear indefinidamente
            self.receive_socket.settimeout(1.0)

            self._log("INFO", f"Sockets UDP inicializados com sucesso")
            self._log("INFO", f"Aguardando dados do Raspberry Pi...")
            self._log("INFO", f"Cliente pronto para enviar comandos")

            return True

        except Exception as e:
            self._log("ERROR", f"Erro ao inicializar sockets UDP: {e}")
            return False

    def connect_to_raspberry_pi(self, rpi_ip):
        """
        Conecta diretamente ao Raspberry Pi no IP especificado

        Args:
            rpi_ip (str): IP do Raspberry Pi
        """
        try:
            # Envia comando CONNECT com porta de escuta
            connect_msg = f"CONNECT:{self.port}".encode("utf-8")
            self.send_socket.sendto(connect_msg, (rpi_ip, self.command_port))
            self._log("INFO", f"📡 Enviando CONNECT para {rpi_ip}:{self.command_port}")

            # Marca como conectado diretamente
            self.raspberry_pi_ip = rpi_ip
            self.is_connected_to_rpi = True
            self._update_status(
                {
                    "connection": f"Conectando a {rpi_ip}:{self.command_port}",
                    "discovery": "IP direto fornecido",
                }
            )

        except Exception as e:
            self._log("ERROR", f"Erro ao conectar ao Raspberry Pi {rpi_ip}: {e}")


    def send_command_to_rpi(self, command: str) -> bool:
        """
        Envia comando para o Raspberry Pi descoberto

        Args:
            command: Comando a ser enviado

        Returns:
            bool: True se enviado com sucesso
        """
        if not self.raspberry_pi_ip:
            self._log("WARN", "Raspberry Pi não descoberto ainda")
            return False

        try:
            command_bytes = command.encode("utf-8")
            self.send_socket.sendto(
                command_bytes, (self.raspberry_pi_ip, self.command_port)
            )
            return True
        except Exception as e:
            self._log("ERROR", f"Erro ao enviar comando '{command}': {e}")
            return False

    def send_control_command(self, control_type: str, value: float) -> bool:
        """
        Envia comando de controle para o Raspberry Pi

        Args:
            control_type: Tipo do controle (THROTTLE, BRAKE, STEERING, GEAR_UP, GEAR_DOWN)
            value: Valor do controle

        Returns:
            bool: True se enviado com sucesso
        """
        command = f"CONTROL:{control_type}:{value}"
        success = self.send_command_to_rpi(command)
        if success:
            self._log("INFO", f"✅ Comando enviado: {control_type}:{value}")
        return success


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
        self._log("INFO", "Cliente de rede iniciado em modo fixo")
        self._log("INFO", f"🔗 Raspberry Pi: {self.rpi_ip}:9999")
        self._log("INFO", f"🎮 Cliente: {self.client_ip}:9999")

        # Modo fixo - configura Raspberry Pi IP diretamente
        if self.rpi_ip:
            self.raspberry_pi_ip = self.rpi_ip
            self.is_connected_to_rpi = True
            self._log("INFO", f"🔗 Raspberry Pi configurado: {self.raspberry_pi_ip}")

        try:
            while self.is_running:
                try:
                    # Recebe pacote de dados
                    packet, addr = self.receive_socket.recvfrom(self.buffer_size)

                    # Filtra: só aceita pacotes do IP configurado
                    if self.rpi_ip and addr[0] != self.rpi_ip:
                        continue  # Ignora pacotes de outros IPs

                    # Se é a primeira vez que recebemos dados deste endereço
                    if not self.raspberry_pi_ip:
                        self.raspberry_pi_ip = addr[0]
                        self.is_connected_to_rpi = True
                        self._log(
                            "INFO",
                            f"🔗 Raspberry Pi descoberto: {self.raspberry_pi_ip}",
                        )
                        self._log("INFO", "✅ Conexão estabelecida!")

                    # Atualiza estatísticas
                    self.packets_received += 1
                    self.bytes_received += len(packet)

                    # Atualiza status da conexão
                    self.update_connection_status(addr)

                    # Verifica se é um comando de texto (como SERVER_CONNECT)
                    try:
                        packet_str = packet.decode("utf-8")
                        if packet_str.startswith("SERVER_CONNECT"):
                            self._log(
                                "INFO",
                                f"🔄 Recebido comando de reconexão do Raspberry Pi",
                            )
                            # Marca como conectado/reconectado
                            self.raspberry_pi_ip = addr[0]
                            self.is_connected_to_rpi = True
                            self._update_status(
                                {
                                    "connection": f"Reconectado com {addr[0]}",
                                    "status": "Ativo via SERVER_CONNECT",
                                }
                            )
                            continue  # Pula processamento como dados binários
                    except UnicodeDecodeError:
                        # Não é comando de texto, processa como dados binários
                        pass

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
                    time.sleep(0.001)  # Sleep mínimo para tempo real

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

        # Envia comando DISCONNECT se conectado
        if self.is_connected_to_rpi:
            try:
                self.send_command_to_rpi("DISCONNECT")
            except:
                pass

        # Fecha sockets
        if self.receive_socket:
            try:
                self.receive_socket.close()
            except:
                pass

        if self.send_socket:
            try:
                self.send_socket.close()
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
