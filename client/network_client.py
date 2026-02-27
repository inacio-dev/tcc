#!/usr/bin/env python3
"""
network_client.py - Cliente de Rede UDP
Responsável por receber pacotes UDP do Raspberry Pi

FORMATO DO PACOTE RECEBIDO (normal):
===================================
| 4 bytes    | 4 bytes     | N bytes    | M bytes      |
| frame_size | sensor_size | frame_data | sensor_data  |

FORMATO DO PACOTE RECEBIDO (fragmentado):
========================================
| 4 bytes    | 4 bytes  | 2 bytes     | 2 bytes      | N bytes    |
| FRAG_MAGIC | frame_id | chunk_index | total_chunks | chunk_data |

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

import json
import socket
import struct
import threading
import time
from collections import defaultdict


class NetworkClient:
    """Cliente de rede para comunicação UDP bidirecional"""

    # Constantes de fragmentação (devem ser iguais ao servidor)
    FRAG_MAGIC = 0x46524147  # "FRAG" em ASCII hex
    FRAG_HEADER_SIZE = 12    # 4 (magic) + 4 (frame_id) + 2 (chunk_idx) + 2 (total_chunks)
    FRAG_TIMEOUT = 1.0       # Timeout para descartar fragmentos incompletos (segundos)

    def __init__(
        self,
        video_port=9999,
        sensor_port=9997,
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
            video_port (int): Porta UDP para receber vídeo
            sensor_port (int): Porta UDP para receber sensores
            command_port (int): Porta UDP para enviar comandos
            buffer_size (int): Tamanho do buffer UDP
            host (str): IP para escutar (0.0.0.0 = todas as interfaces)
            log_queue (Queue): Fila para mensagens de log
            status_queue (Queue): Fila para estatísticas de conexão
            sensor_queue (Queue): Fila para dados de sensores
            video_queue (Queue): Fila para frames de vídeo
        """
        self.port = video_port
        self.sensor_port = sensor_port
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
        self.receive_socket = None  # Para receber vídeo (porta 9999)
        self.sensor_socket = None  # Para receber sensores (porta 9997)
        self.send_socket = None  # Para enviar comandos (porta 9998)
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

        # Buffer para reassembly de fragmentos
        # Estrutura: {frame_id: {'chunks': {chunk_idx: data}, 'total': N, 'timestamp': time}}
        self.fragment_buffer = {}
        self.fragment_lock = threading.Lock()
        self.last_fragment_cleanup = time.time()

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
            self._log("INFO", "Inicializando cliente UDP bidirecional (Multi-Thread)")
            self._log("INFO", f"Vídeo: porta {self.port}, Sensores: porta {self.sensor_port}, Comandos: porta {self.command_port}")

            # Socket para receber vídeo (porta 9999)
            self.receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.receive_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.receive_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 65536)
            self.receive_socket.settimeout(1.0)
            self.receive_socket.bind((self.host, self.port))

            # Socket para receber sensores (porta 9997)
            self.sensor_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.sensor_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.sensor_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, 32768)
            self.sensor_socket.settimeout(1.0)
            self.sensor_socket.bind((self.host, self.sensor_port))

            # Socket para enviar comandos (porta 9998)
            self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            self._log("INFO", "Sockets UDP inicializados (vídeo + sensores + comandos)")
            self._log("INFO", "Aguardando dados do Raspberry Pi...")

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
        if not self.raspberry_pi_ip or not self.is_connected_to_rpi:
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

    def send_control_command(self, control_type: str, value) -> bool:
        """
        Envia comando de controle para o Raspberry Pi

        Args:
            control_type: Tipo do controle (STATE, GEAR_UP, GEAR_DOWN, etc.)
            value: Valor do controle (float ou string)

        Returns:
            bool: True se enviado com sucesso
        """
        command = f"CONTROL:{control_type}:{value}"
        return self.send_command_to_rpi(command)

    def parse_packet(self, packet):
        """
        Analisa pacote UDP recebido.
        Detecta automaticamente se é pacote normal ou fragmentado.

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

            # Verifica se é pacote fragmentado (magic number no início)
            magic = struct.unpack("<I", packet[:4])[0]
            if magic == self.FRAG_MAGIC:
                return self._handle_fragment(packet)

            # Pacote normal - extrai tamanhos dos dados
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

    def _handle_fragment(self, packet):
        """
        Processa pacote fragmentado e reassembla quando completo.

        Estrutura do fragmento:
        | 4 bytes    | 4 bytes  | 2 bytes     | 2 bytes      | N bytes    |
        | FRAG_MAGIC | frame_id | chunk_index | total_chunks | chunk_data |

        Args:
            packet (bytes): Pacote fragmentado

        Returns:
            tuple: (frame_data, sensor_data) quando completo, ou (None, None) se ainda aguardando
        """
        try:
            if len(packet) < self.FRAG_HEADER_SIZE:
                return None, None

            # Extrai cabeçalho do fragmento
            magic, frame_id, chunk_idx, total_chunks = struct.unpack("<IIHH", packet[:12])
            chunk_data = packet[12:]

            current_time = time.time()

            with self.fragment_lock:
                # Limpa fragmentos antigos periodicamente
                if current_time - self.last_fragment_cleanup > 1.0:
                    self._cleanup_old_fragments(current_time)
                    self.last_fragment_cleanup = current_time

                # Cria entrada para este frame se não existe
                if frame_id not in self.fragment_buffer:
                    self.fragment_buffer[frame_id] = {
                        'chunks': {},
                        'total': total_chunks,
                        'timestamp': current_time
                    }

                # Armazena chunk
                self.fragment_buffer[frame_id]['chunks'][chunk_idx] = chunk_data

                # Verifica se temos todos os chunks
                if len(self.fragment_buffer[frame_id]['chunks']) == total_chunks:
                    # Reassembla o pacote completo
                    complete_data = b''
                    for i in range(total_chunks):
                        if i in self.fragment_buffer[frame_id]['chunks']:
                            complete_data += self.fragment_buffer[frame_id]['chunks'][i]
                        else:
                            # Falta um chunk - não deveria acontecer
                            del self.fragment_buffer[frame_id]
                            return None, None

                    # Remove do buffer
                    del self.fragment_buffer[frame_id]

                    # Processa o pacote completo como pacote normal
                    return self._parse_complete_packet(complete_data)

            # Ainda aguardando mais chunks
            return None, None

        except Exception as e:
            self._log("ERROR", f"Erro ao processar fragmento: {e}")
            return None, None

    def _parse_complete_packet(self, packet):
        """
        Analisa pacote completo (após reassembly de fragmentos).

        Args:
            packet (bytes): Pacote completo

        Returns:
            tuple: (frame_data, sensor_data)
        """
        try:
            if len(packet) < 8:
                return None, None

            frame_size, sensor_size = struct.unpack("<II", packet[:8])

            if frame_size == 0 and sensor_size == 0:
                return "TERMINATE", None

            frame_start = 8
            frame_end = frame_start + frame_size
            sensor_start = frame_end
            sensor_end = sensor_start + sensor_size

            expected_size = 8 + frame_size + sensor_size
            if len(packet) < expected_size:
                return None, None

            frame_data = packet[frame_start:frame_end] if frame_size > 0 else None

            sensor_data = None
            if sensor_size > 0:
                try:
                    sensor_bytes = packet[sensor_start:sensor_end]
                    sensor_json = sensor_bytes.decode("utf-8")
                    sensor_data = json.loads(sensor_json)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    pass

            return frame_data, sensor_data

        except Exception:
            return None, None

    def _cleanup_old_fragments(self, current_time):
        """Remove fragmentos incompletos que expiraram"""
        expired_frames = []
        for frame_id, data in self.fragment_buffer.items():
            if current_time - data['timestamp'] > self.FRAG_TIMEOUT:
                expired_frames.append(frame_id)

        for frame_id in expired_frames:
            del self.fragment_buffer[frame_id]

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
        """Inicia recepção em 2 threads: vídeo (9999) + sensores (9997)"""
        if not self.initialize():
            self._log("ERROR", "Falha ao inicializar cliente de rede")
            return

        self.is_running = True
        self._log("INFO", "Cliente de rede iniciado")
        self._log("INFO", f"Vídeo: {self.rpi_ip}:{self.port}, Sensores: {self.rpi_ip}:{self.sensor_port}")

        if self.rpi_ip:
            self.raspberry_pi_ip = self.rpi_ip
            self._log("INFO", f"Raspberry Pi configurado: {self.raspberry_pi_ip} (aguardando conexão)")

        # Thread de sensores roda em background
        self._sensor_rx_thread = threading.Thread(
            target=self._sensor_receiver_loop, name="SensorRX", daemon=True
        )
        self._sensor_rx_thread.start()

        # Thread principal: recepção de vídeo
        try:
            self._video_receiver_loop()
        except KeyboardInterrupt:
            self._log("INFO", "Recepção interrompida pelo usuário")
        finally:
            self.stop()

    def _confirm_connection(self, addr):
        """Confirma conexão no primeiro pacote recebido"""
        if not self.is_connected_to_rpi:
            self.raspberry_pi_ip = addr[0]
            self.is_connected_to_rpi = True
            self._log("INFO", f"🔗 Raspberry Pi conectado: {self.raspberry_pi_ip}")
            self._log("INFO", "✅ Conexão estabelecida!")

    def _video_receiver_loop(self):
        """Recebe frames de vídeo (porta 9999)"""
        while self.is_running:
            try:
                packet, addr = self.receive_socket.recvfrom(self.buffer_size)

                if self.rpi_ip and addr[0] != self.rpi_ip:
                    continue

                self._confirm_connection(addr)
                self.packets_received += 1
                self.bytes_received += len(packet)
                self.update_connection_status(addr)

                # Verifica comando de texto (SERVER_CONNECT)
                try:
                    packet_str = packet.decode("utf-8")
                    if packet_str.startswith("SERVER_CONNECT"):
                        self._log("INFO", "🔄 Recebido comando de reconexão do Raspberry Pi")
                        self.raspberry_pi_ip = addr[0]
                        self.is_connected_to_rpi = True
                        self._update_status({
                            "connection": f"Reconectado com {addr[0]}",
                            "status": "Ativo via SERVER_CONNECT",
                        })
                        continue
                except UnicodeDecodeError:
                    pass

                # Pacote de vídeo: 4 bytes tamanho + dados do frame
                frame_data = self._parse_video_packet(packet)
                if frame_data == "TERMINATE":
                    break
                if frame_data is not None:
                    self.frames_received += 1
                    self._send_video_frame(frame_data)

                self.update_statistics()

            except socket.timeout:
                self.check_connection_timeout()
            except Exception as e:
                current_time = time.time()
                if current_time - self.last_error_log > 5.0:
                    self._log("ERROR", f"Erro na recepção de vídeo: {e}")
                    self.last_error_log = current_time
                time.sleep(0.001)

    def _sensor_receiver_loop(self):
        """Recebe dados de sensores (porta 9997)"""
        while self.is_running:
            try:
                packet, addr = self.sensor_socket.recvfrom(32768)

                if self.rpi_ip and addr[0] != self.rpi_ip:
                    continue

                self._confirm_connection(addr)

                # Pacote de sensores: JSON direto
                try:
                    sensor_data = json.loads(packet.decode("utf-8"))
                    self.sensor_packets_received += 1
                    self._send_sensor_data(sensor_data)
                except (json.JSONDecodeError, UnicodeDecodeError):
                    self.decode_errors += 1

            except socket.timeout:
                continue
            except Exception as e:
                current_time = time.time()
                if current_time - self.last_error_log > 5.0:
                    self._log("ERROR", f"Erro na recepção de sensores: {e}")
                    self.last_error_log = current_time
                time.sleep(0.001)

    def _parse_video_packet(self, packet):
        """Parse de pacote de vídeo (4 bytes tamanho + frame data).
        Compatível com pacotes antigos (frame_size + sensor_size + data)."""
        try:
            if len(packet) < 4:
                return None

            # Verifica se é fragmento
            if len(packet) >= 4:
                magic = struct.unpack("<I", packet[:4])[0]
                if magic == self.FRAG_MAGIC:
                    return self._handle_fragment(packet)

            frame_size = struct.unpack("<I", packet[:4])[0]

            if frame_size == 0:
                # Pode ser pacote antigo com sensor_size no offset 4
                if len(packet) >= 8:
                    sensor_size = struct.unpack("<I", packet[4:8])[0]
                    if sensor_size == 0:
                        return "TERMINATE"
                return None

            # Novo formato: 4 bytes tamanho + frame
            if len(packet) >= 4 + frame_size:
                return packet[4:4 + frame_size]

            return None
        except Exception:
            self.packet_errors += 1
            return None

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
            "sensor_hz": (
                round(self.sensor_packets_received / elapsed, 2) if elapsed > 0 else 0
            ),
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
            except Exception:
                pass

        # Fecha sockets
        if self.receive_socket:
            try:
                self.receive_socket.close()
            except Exception:
                pass

        if self.sensor_socket:
            try:
                self.sensor_socket.close()
            except Exception:
                pass

        if self.send_socket:
            try:
                self.send_socket.close()
            except Exception:
                pass

        # Envia estatísticas finais
        stats = self.get_statistics()
        self._log("INFO", "Estatísticas finais:")
        self._log("INFO", f"  - Pacotes recebidos: {stats['packets_received']}")
        self._log("INFO", f"  - Frames de vídeo: {stats['frames_received']}")
        self._log("INFO", f"  - Sensores: {stats['sensor_packets_received']}")
        self._log("INFO", f"  - Taxa média: {stats['fps']:.1f} FPS")
        self._log("INFO", f"  - Erros de decodificação: {stats['decode_errors']}")

        self._log("INFO", "Cliente de rede parado")
