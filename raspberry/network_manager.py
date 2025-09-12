#!/usr/bin/env python3
"""
network_manager.py - Gerenciamento de Comunicação UDP - VERSÃO CORRIGIDA
Responsável por transmitir vídeo + dados de sensores via UDP
CORREÇÃO: Agora suporta tipos numpy (bool_, float64, etc.)

CONFIGURAÇÃO DE REDE:
====================
1. Raspberry Pi e PC devem estar na mesma rede WiFi
2. Configurar IP estático no RPi (recomendado)
3. Abrir porta no firewall se necessário

ESTRUTURA DO PACOTE UDP:
=======================
| 4 bytes    | 4 bytes     | N bytes    | M bytes      |
| frame_size | sensor_size | frame_data | sensor_data  |

PORTAS UTILIZADAS:
=================
- 9999: Transmissão de vídeo + sensores (RPi -> PC)
- 9998: Comandos de controle (PC -> RPi) [futuro]
"""

import socket
import struct
import json
import time
import threading
import numpy as np
from typing import Optional, Dict, Any, Tuple
from logger import info, debug, warn, error


class NetworkManager:
    """Gerencia comunicação UDP bidirecional para transmissão de dados"""

    def __init__(
        self,
        data_port: int = 9999,  # Porta para enviar dados (RPi -> Cliente)
        command_port: int = 9998,  # Porta para receber comandos (Cliente -> RPi)
        buffer_size: int = 131072,
    ):
        """
        Inicializa o gerenciador de rede bidirecional

        Args:
            data_port (int): Porta para envio de dados aos clientes
            command_port (int): Porta para escutar comandos dos clientes  
            buffer_size (int): Tamanho do buffer UDP em bytes
        """
        self.data_port = data_port
        self.command_port = command_port
        self.buffer_size = buffer_size

        # Sockets UDP
        self.send_socket = None     # Para enviar dados
        self.receive_socket = None  # Para receber comandos
        self.is_initialized = False
        
        # Clientes conectados (descoberta automática)
        self.connected_clients = {}  # {ip: {'port': port, 'last_seen': timestamp}}
        self.clients_lock = threading.Lock()

        # Estatísticas de transmissão
        self.packets_sent = 0
        self.bytes_sent = 0
        self.commands_received = 0
        self.last_send_time = time.time()
        self.start_time = time.time()

        # Controle de erro
        self.send_errors = 0
        self.last_error_time = 0
        self.last_error_log = 0

        # Threading para recepção de comandos
        self.command_thread = None
        self.should_stop = False
        
        # Callback para processar comandos recebidos
        self.command_callback = None

    def initialize(self) -> bool:
        """
        Inicializa a comunicação UDP bidirecional

        Returns:
            bool: True se inicializado com sucesso
        """
        try:
            info("Inicializando comunicação UDP bidirecional...", "NET")
            debug(f"Porta dados: {self.data_port}, Comandos: {self.command_port}", "NET")

            # Cria socket para envio de dados
            self.send_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.send_socket.setsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF, self.buffer_size)

            # Cria socket para receber comandos
            self.receive_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            self.receive_socket.setsockopt(socket.SOL_SOCKET, socket.SO_RCVBUF, self.buffer_size)
            self.receive_socket.bind(('', self.command_port))  # Escuta em todas as interfaces
            
            # Configura timeout para evitar blocking infinito
            self.receive_socket.settimeout(1.0)

            debug("Sockets criados com sucesso", "NET")

            # Inicia thread para escutar comandos
            self._start_command_listener()

            self.is_initialized = True
            info("Comunicação UDP inicializada - Aguardando clientes...", "NET")
            
            return True

        except Exception as e:
            error(f"Erro ao inicializar UDP: {e}", "NET")
            error("Verifique rede WiFi e firewall", "NET")

            self.is_initialized = False
            return False
            
    def _start_command_listener(self):
        """Inicia thread para escutar comandos dos clientes"""
        if self.command_thread is None or not self.command_thread.is_alive():
            self.should_stop = False
            self.command_thread = threading.Thread(target=self._command_listener_loop, daemon=True)
            self.command_thread.start()
            debug("Thread de escuta iniciada", "NET")

    def _command_listener_loop(self):
        """Loop principal para escutar comandos dos clientes"""
        debug("Iniciando escuta de comandos", "NET")
        
        while not self.should_stop:
            try:
                # Recebe dados de qualquer cliente
                data, addr = self.receive_socket.recvfrom(self.buffer_size)
                client_ip, client_port = addr
                
                # Processa o comando recebido
                self._process_client_command(data, client_ip, client_port)
                
            except socket.timeout:
                # Timeout normal - continua o loop
                continue
            except Exception as e:
                if not self.should_stop:
                    warn(f"Erro ao receber comando: {e}", "NET", rate_limit=5.0)
                    time.sleep(0.1)
        
        debug("Thread de escuta finalizada", "NET")

    def _process_client_command(self, data: bytes, client_ip: str, client_port: int):
        """
        Processa comando recebido de um cliente
        
        Args:
            data: Dados recebidos
            client_ip: IP do cliente
            client_port: Porta do cliente  
        """
        try:
            # Decodifica comando
            command_str = data.decode('utf-8').strip()
            self.commands_received += 1
            
            current_time = time.time()
            
            # Processa diferentes tipos de comando
            if command_str.startswith("CONNECT"):
                # CONNECT ou CONNECT:porta
                if ":" in command_str:
                    _, listen_port = command_str.split(":", 1)
                    self._handle_client_connect(client_ip, int(listen_port))
                else:
                    self._handle_client_connect(client_ip, self.data_port)  # Porta padrão
                
            elif command_str == "DISCONNECT":
                self._handle_client_disconnect(client_ip)
                
            elif command_str.startswith("PING"):
                self._handle_client_ping(client_ip, client_port, command_str)
                
            elif command_str.startswith("CONTROL:"):
                # Comando de controle (motor, freio, direção)
                self._handle_control_command(client_ip, command_str[8:])
                
            else:
                # Comando personalizado - repassa para callback se existir
                if self.command_callback:
                    self.command_callback(client_ip, command_str)
                    
            # Atualiza última vez que vimos este cliente
            with self.clients_lock:
                if client_ip in self.connected_clients:
                    self.connected_clients[client_ip]['last_seen'] = current_time
                    
        except Exception as e:
            warn(f"Erro ao processar comando de {client_ip}: {e}", "NET", rate_limit=5.0)

    def _handle_client_connect(self, client_ip: str, listen_port: int):
        """
        Processa conexão de um novo cliente
        
        Args:
            client_ip: IP do cliente
            listen_port: Porta onde o cliente está escutando dados
        """
        with self.clients_lock:
            if client_ip not in self.connected_clients:
                # Novo cliente
                self.connected_clients[client_ip] = {
                    'port': listen_port,  # Porta onde cliente escuta dados
                    'last_seen': time.time()
                }
                info(f"Novo cliente conectado: {client_ip}", "NET")
                
                # Envia confirmação de conexão
                self._send_to_client(client_ip, b"CONNECTED")
                
            else:
                # Cliente reconectando
                self.connected_clients[client_ip]['last_seen'] = time.time()
                debug(f"Cliente reconectado: {client_ip}", "NET")
                self._send_to_client(client_ip, b"RECONNECTED")

    def _handle_client_disconnect(self, client_ip: str):
        """Processa desconexão de um cliente"""
        with self.clients_lock:
            if client_ip in self.connected_clients:
                del self.connected_clients[client_ip]
                info(f"Cliente desconectado: {client_ip}", "NET")

    def _handle_client_ping(self, client_ip: str, client_port: int, ping_data: str):
        """Responde ao ping do cliente"""
        # Extrai timestamp se enviado
        parts = ping_data.split(':')
        if len(parts) > 1:
            timestamp = parts[1]
            pong_response = f"PONG:{timestamp}".encode('utf-8')
        else:
            pong_response = b"PONG"
            
        self._send_to_client(client_ip, pong_response)

    def _handle_control_command(self, client_ip: str, command: str):
        """Processa comando de controle do veículo"""
        debug(f"Comando de {client_ip}: {command}", "NET")
        
        # Aqui você pode processar comandos como:
        # "THROTTLE:50" -> acelerar 50%
        # "BRAKE:30" -> frear 30%  
        # "STEERING:-20" -> virar esquerda 20°
        # etc.
        
        # Por enquanto só loga - implementação específica fica para depois
        if self.command_callback:
            self.command_callback(client_ip, f"CONTROL:{command}")

    def _send_to_client(self, client_ip: str, data: bytes):
        """Envia dados para um cliente específico"""
        with self.clients_lock:
            if client_ip in self.connected_clients:
                client_port = self.connected_clients[client_ip]['port']
                try:
                    self.send_socket.sendto(data, (client_ip, client_port))
                except Exception as e:
                    warn(f"Erro ao enviar para {client_ip}: {e}", "NET", rate_limit=5.0)

    def get_connected_clients(self) -> list:
        """Retorna lista de clientes conectados"""
        with self.clients_lock:
            return list(self.connected_clients.keys())

    def has_connected_clients(self) -> bool:
        """Verifica se há clientes conectados"""
        with self.clients_lock:
            return len(self.connected_clients) > 0

    def set_command_callback(self, callback):
        """Define callback para processar comandos personalizados"""
        self.command_callback = callback

    def _convert_numpy_types(self, obj):
        """
        Converte tipos numpy para tipos Python nativos recursivamente

        Args:
            obj: Objeto que pode conter tipos numpy

        Returns:
            Objeto com tipos Python nativos
        """
        if isinstance(obj, np.bool_):
            return bool(obj)
        elif isinstance(obj, np.integer):
            return int(obj)
        elif isinstance(obj, np.floating):
            return float(obj)
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, dict):
            return {key: self._convert_numpy_types(value) for key, value in obj.items()}
        elif isinstance(obj, list):
            return [self._convert_numpy_types(item) for item in obj]
        elif isinstance(obj, tuple):
            return tuple(self._convert_numpy_types(item) for item in obj)
        else:
            # Para outros tipos (incluindo tipos numpy que não foram capturados)
            if hasattr(obj, "dtype"):
                try:
                    return obj.item()  # Converte scalar numpy para Python nativo
                except:
                    return str(obj)  # Fallback para string
            return obj

    def create_packet(self, frame_data: bytes, sensor_data: Dict[Any, Any]) -> bytes:
        """
        Cria pacote UDP estruturado

        Args:
            frame_data (bytes): Dados do frame de vídeo
            sensor_data (dict): Dados dos sensores

        Returns:
            bytes: Pacote UDP completo
        """
        try:
            # Converte tipos numpy para tipos Python nativos
            cleaned_sensor_data = self._convert_numpy_types(sensor_data)

            # Serializa dados dos sensores para JSON
            sensor_json = json.dumps(cleaned_sensor_data, ensure_ascii=False)
            sensor_bytes = sensor_json.encode("utf-8")

            # Tamanhos
            frame_size = len(frame_data) if frame_data else 0
            sensor_size = len(sensor_bytes)

            # Monta pacote:
            # 4 bytes: tamanho do frame (little-endian unsigned int)
            # 4 bytes: tamanho dos dados do sensor
            # N bytes: dados do frame
            # M bytes: dados do sensor (JSON)
            packet = (
                struct.pack("<I", frame_size)  # Frame size
                + struct.pack("<I", sensor_size)  # Sensor size
                + (frame_data if frame_data else b"")  # Frame data
                + sensor_bytes  # Sensor data
            )

            return packet

        except Exception as e:
            # Log erro detalhado apenas a cada 5 segundos
            current_time = time.time()
            if current_time - self.last_error_log > 5.0:
                print(f"⚠ Erro ao criar pacote: {e}")

                # Debug adicional para identificar tipos problemáticos
                if sensor_data:
                    print(f"🔍 Debug - Tipos problemáticos nos dados:")
                    for key, value in sensor_data.items():
                        if hasattr(value, "dtype") or type(value).__module__ == "numpy":
                            print(f"  {key}: {type(value)} = {value}")

                self.last_error_log = current_time

            return b""

    def send_packet(self, packet_data: bytes) -> bool:
        """
        Envia pacote UDP para todos os clientes conectados

        Args:
            packet_data (bytes): Dados do pacote para envio

        Returns:
            bool: True se enviado para pelo menos um cliente
        """
        if not self.is_initialized or not self.send_socket:
            return False

        # Só envia se houver clientes conectados
        if not self.has_connected_clients():
            return False

        success_count = 0
        
        with self.clients_lock:
            for client_ip, client_info in self.connected_clients.items():
                try:
                    # Envia pacote para cada cliente
                    self.send_socket.sendto(packet_data, (client_ip, client_info['port']))
                    success_count += 1
                except Exception as e:
                    warn(f"Erro ao enviar para {client_ip}: {e}", "NET", rate_limit=5.0)

        # Atualiza estatísticas se enviou para pelo menos um cliente
        if success_count > 0:
            self.packets_sent += 1
            self.bytes_sent += len(packet_data)
            self.last_send_time = time.time()
            return True
        else:
            self.send_errors += 1
            return False

    def send_frame_with_sensors(
        self, frame_data: Optional[bytes], sensor_data: Dict[Any, Any]
    ) -> bool:
        """
        Envia frame de vídeo junto com dados de sensores

        Args:
            frame_data (bytes): Dados do frame codificado
            sensor_data (dict): Dados dos sensores

        Returns:
            bool: True se enviado com sucesso
        """
        # Cria pacote estruturado
        packet = self.create_packet(frame_data, sensor_data)

        if packet:
            return self.send_packet(packet)
        else:
            return False

    def send_termination_signal(self) -> bool:
        """
        Envia sinal de terminação (tamanhos zero)

        Returns:
            bool: True se enviado com sucesso
        """
        try:
            termination_packet = struct.pack("<I", 0) + struct.pack("<I", 0)
            return self.send_packet(termination_packet)
        except:
            return False

    def get_transmission_stats(self) -> Dict[str, Any]:
        """
        Obtém estatísticas de transmissão

        Returns:
            dict: Estatísticas de rede
        """
        elapsed = time.time() - self.start_time

        # Calcula taxas
        packets_per_second = self.packets_sent / elapsed if elapsed > 0 else 0
        bytes_per_second = self.bytes_sent / elapsed if elapsed > 0 else 0
        mbps = (bytes_per_second * 8) / (1024 * 1024)  # Megabits por segundo

        return {
            "packets_sent": self.packets_sent,
            "bytes_sent": self.bytes_sent,
            "send_errors": self.send_errors,
            "elapsed_time": round(elapsed, 2),
            "packets_per_second": round(packets_per_second, 2),
            "bytes_per_second": round(bytes_per_second, 2),
            "mbps": round(mbps, 3),
            "is_connected": self.has_connected_clients(),
            "target": f"auto-discovery:{self.data_port}" if not hasattr(self, 'target_ip') else f"{self.target_ip}:{self.target_port}",
            "last_send_time": self.last_send_time,
        }

    def get_network_info(self) -> Dict[str, Any]:
        """
        Obtém informações da rede local

        Returns:
            dict: Informações de rede
        """
        import subprocess

        try:
            # Obtém IP local
            result = subprocess.run(["hostname", "-I"], capture_output=True, text=True)
            local_ip = (
                result.stdout.strip().split()[0] if result.stdout else "Desconhecido"
            )

            # Testa conectividade com ping
            ping_result = subprocess.run(
                ["ping", "-c", "1", "-W", "1", self.target_ip],
                capture_output=True,
                text=True,
            )
            ping_ok = ping_result.returncode == 0

            return {
                "local_ip": local_ip,
                "target_ip": self.target_ip,
                "target_port": self.target_port,
                "ping_ok": ping_ok,
                "buffer_size_kb": self.buffer_size // 1024,
            }

        except Exception as e:
            return {
                "error": str(e),
                "local_ip": "Erro ao obter",
                "target_ip": self.target_ip,
                "ping_ok": False,
            }

    def monitor_bandwidth(self, duration: float = 5.0) -> Dict[str, float]:
        """
        Monitora uso de banda por um período

        Args:
            duration (float): Duração do monitoramento em segundos

        Returns:
            dict: Estatísticas de banda
        """
        start_packets = self.packets_sent
        start_bytes = self.bytes_sent
        start_time = time.time()

        time.sleep(duration)

        end_packets = self.packets_sent
        end_bytes = self.bytes_sent
        end_time = time.time()

        elapsed = end_time - start_time
        packets_diff = end_packets - start_packets
        bytes_diff = end_bytes - start_bytes

        return {
            "duration": round(elapsed, 2),
            "packets": packets_diff,
            "bytes": bytes_diff,
            "packets_per_second": round(packets_diff / elapsed, 2),
            "bytes_per_second": round(bytes_diff / elapsed, 2),
            "kbps": round((bytes_diff * 8) / (elapsed * 1024), 2),
            "mbps": round((bytes_diff * 8) / (elapsed * 1024 * 1024), 3),
        }

    def test_connection(self) -> bool:
        """
        Testa conectividade com o destino

        Returns:
            bool: True se conectividade OK
        """
        try:
            # Envia pacote de teste
            test_data = (
                struct.pack("<I", 4) + struct.pack("<I", 10) + b"test" + b'{"test":1}'
            )
            self.socket.sendto(test_data, (self.target_ip, self.target_port))

            print(
                f"✓ Teste de conectividade OK para {self.target_ip}:{self.target_port}"
            )
            return True

        except Exception as e:
            print(f"✗ Falha no teste de conectividade: {e}")
            return False

    def cleanup(self):
        """Libera recursos de rede"""
        try:
            info("Parando comunicação UDP...", "NET")
            
            # Para thread de escuta de comandos
            self.should_stop = True
            if self.command_thread and self.command_thread.is_alive():
                self.command_thread.join(timeout=2.0)

            # Notifica clientes sobre desconexão
            if self.has_connected_clients():
                debug("Notificando clientes sobre desconexão", "NET")
                with self.clients_lock:
                    for client_ip in list(self.connected_clients.keys()):
                        self._send_to_client(client_ip, b"SERVER_DISCONNECT")
                        
            # Envia sinal de terminação
            if self.is_initialized:
                self.send_termination_signal()

            # Fecha sockets
            if self.send_socket:
                self.send_socket.close()
                
            if self.receive_socket:
                self.receive_socket.close()

            self.is_initialized = False
            self.connected_clients.clear()
            info("Comunicação UDP finalizada", "NET")

        except Exception as e:
            warn(f"Erro ao finalizar conexão: {e}", "NET")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()
