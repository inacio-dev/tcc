#!/usr/bin/env python3
"""
network_manager.py - Gerenciamento de Comunicação UDP
Responsável por transmitir vídeo + dados de sensores via UDP

CONFIGURAÇÃO DE REDE:
====================
1. Raspberry Pi e PC devem estar na mesma rede WiFi
2. Configurar IP estático no RPi (recomendado)
3. Abrir porta no firewall se necessário

EXEMPLO DE CONFIGURAÇÃO IP ESTÁTICO:
===================================
sudo nano /etc/dhcpcd.conf
Adicionar no final:

interface wlan0
static ip_address=192.168.1.100/24
static routers=192.168.1.1
static domain_name_servers=192.168.1.1

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
from typing import Optional, Dict, Any, Tuple


class NetworkManager:
    """Gerencia comunicação UDP para transmissão de dados"""

    def __init__(
        self,
        target_ip: str = "192.168.5.120",
        target_port: int = 9999,
        buffer_size: int = 131072,
    ):
        """
        Inicializa o gerenciador de rede

        Args:
            target_ip (str): IP do computador de destino
            target_port (int): Porta de destino
            buffer_size (int): Tamanho do buffer UDP em bytes
        """
        self.target_ip = target_ip
        self.target_port = target_port
        self.buffer_size = buffer_size

        # Socket UDP
        self.socket = None
        self.is_connected = False

        # Estatísticas de transmissão
        self.packets_sent = 0
        self.bytes_sent = 0
        self.last_send_time = time.time()
        self.start_time = time.time()

        # Controle de erro
        self.send_errors = 0
        self.last_error_time = 0

        # Threading para envio assíncrono (opcional)
        self.send_queue = []
        self.send_thread = None
        self.should_stop = False

    def initialize(self) -> bool:
        """
        Inicializa a conexão UDP

        Returns:
            bool: True se inicializado com sucesso
        """
        try:
            print(f"Inicializando conexão UDP...")
            print(f"Destino: {self.target_ip}:{self.target_port}")

            # Cria socket UDP
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

            # Configura buffer de envio
            self.socket.setsockopt(
                socket.SOL_SOCKET, socket.SO_SNDBUF, self.buffer_size
            )

            # Verifica buffer configurado
            actual_buffer = self.socket.getsockopt(socket.SOL_SOCKET, socket.SO_SNDBUF)

            # Teste de conectividade (envia pacote pequeno)
            test_data = b"UDP_TEST"
            self.socket.sendto(test_data, (self.target_ip, self.target_port))

            self.is_connected = True

            print("✓ Conexão UDP inicializada com sucesso")
            print(f"  - Buffer de envio: {actual_buffer // 1024} KB")
            print(f"  - Destino: {self.target_ip}:{self.target_port}")

            return True

        except Exception as e:
            print(f"✗ Erro ao inicializar UDP: {e}")
            print("\nVerifique:")
            print("1. IP do destino está correto")
            print("2. Rede WiFi conectada")
            print("3. PC de destino acessível (ping)")
            print("4. Firewall não está bloqueando a porta")

            self.is_connected = False
            return False

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
            # Serializa dados dos sensores para JSON
            sensor_json = json.dumps(sensor_data)
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
            print(f"⚠ Erro ao criar pacote: {e}")
            return b""

    def send_packet(self, packet_data: bytes) -> bool:
        """
        Envia pacote UDP

        Args:
            packet_data (bytes): Dados do pacote para envio

        Returns:
            bool: True se enviado com sucesso
        """
        if not self.is_connected or not self.socket:
            return False

        try:
            # Envia pacote
            self.socket.sendto(packet_data, (self.target_ip, self.target_port))

            # Atualiza estatísticas
            self.packets_sent += 1
            self.bytes_sent += len(packet_data)
            self.last_send_time = time.time()

            return True

        except Exception as e:
            self.send_errors += 1
            self.last_error_time = time.time()

            # Log erro a cada 5 segundos para evitar spam
            if time.time() - self.last_error_time > 5.0:
                print(f"⚠ Erro ao enviar pacote: {e}")

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
            "is_connected": self.is_connected,
            "target": f"{self.target_ip}:{self.target_port}",
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
            # Para thread de envio se existir
            self.should_stop = True
            if self.send_thread and self.send_thread.is_alive():
                self.send_thread.join(timeout=1.0)

            # Envia sinal de terminação
            if self.is_connected:
                self.send_termination_signal()

            # Fecha socket
            if self.socket:
                self.socket.close()

            self.is_connected = False
            print("✓ Conexão UDP finalizada")

        except Exception as e:
            print(f"⚠ Erro ao finalizar conexão: {e}")

    def __del__(self):
        """Destrutor - garante limpeza dos recursos"""
        self.cleanup()


# Exemplo de uso
if __name__ == "__main__":
    # Teste da classe NetworkManager
    print("=== TESTE DO NETWORK MANAGER ===")

    # Cria instância
    net_mgr = NetworkManager(
        target_ip="192.168.5.120",  # ALTERE PARA SEU IP
        target_port=9999,
        buffer_size=131072,
    )

    # Mostra informações de rede
    net_info = net_mgr.get_network_info()
    print(f"IP Local: {net_info['local_ip']}")
    print(f"IP Destino: {net_info['target_ip']}")
    print(f"Ping OK: {net_info['ping_ok']}")

    # Inicializa
    if net_mgr.initialize():
        print("Enviando pacotes de teste...")

        # Envia 10 pacotes de teste
        for i in range(10):
            # Dados de teste
            frame_test = f"frame_data_{i}".encode("utf-8")
            sensor_test = {
                "test_count": i,
                "timestamp": time.time(),
                "accel_x": i * 0.1,
                "gyro_z": i * 2.0,
            }

            # Envia pacote
            success = net_mgr.send_frame_with_sensors(frame_test, sensor_test)
            print(f"Pacote {i+1}: {'✓' if success else '✗'}")

            time.sleep(0.1)

        # Mostra estatísticas
        stats = net_mgr.get_transmission_stats()
        print(f"\n=== ESTATÍSTICAS ===")
        print(f"Pacotes enviados: {stats['packets_sent']}")
        print(f"Bytes enviados: {stats['bytes_sent']}")
        print(f"Taxa: {stats['packets_per_second']:.1f} pkt/s")
        print(f"Banda: {stats['kbps']:.1f} kbps")
        print(f"Erros: {stats['send_errors']}")

        # Teste de monitoramento
        print("\nMonitorando banda por 2 segundos...")
        band_stats = net_mgr.monitor_bandwidth(2.0)
        print(
            f"Durante monitoramento: {band_stats['packets']} pacotes, {band_stats['kbps']:.1f} kbps"
        )

        # Finaliza
        net_mgr.cleanup()

    else:
        print("✗ Falha ao inicializar rede")
        print("Verifique IP e conectividade")
