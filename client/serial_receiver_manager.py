#!/usr/bin/env python3
"""
serial_receiver_manager.py - Gerenciador de Recepção Serial
Responsável por receber comandos seriais do cockpit Arduino Mega

Este módulo recebe comandos de controle do cockpit do Arduino Mega via USB serial
e encaminha para o Raspberry Pi via cliente de rede.

Formato do Protocolo (recebido do Arduino Mega):
- THROTTLE:<valor>   (0-100%)
- BRAKE:<valor>      (0-100%)
- STEERING:<valor>   (-100 a +100%)
- GEAR_UP
- GEAR_DOWN

Conexão:
- Arduino Mega USB → /dev/ttyACM0 ou /dev/ttyUSB0 (Linux)
- Porta COM (Windows)
- Taxa de transmissão: 115200

@author F1 RC Car Project
@date 2025-10-09
"""

import serial
import serial.tools.list_ports
import threading
import time
from typing import Optional, Callable


class SerialReceiverManager:
    """Receptor serial para comandos do cockpit Arduino Mega"""

    def __init__(
        self,
        port: Optional[str] = None,
        baud_rate: int = 115200,
        timeout: float = 1.0,
        command_callback: Optional[Callable[[str, str], None]] = None,
        log_callback: Optional[Callable[[str, str], None]] = None,
    ):
        """
        Inicializa receptor serial

        Args:
            port: Porta serial (detecção automática se None)
            baud_rate: Taxa de transmissão (padrão: 115200)
            timeout: Timeout de leitura em segundos
            command_callback: Função de callback(tipo_comando, valor)
            log_callback: Função de callback(nível, mensagem)
        """
        self.port = port
        self.baud_rate = baud_rate
        self.timeout = timeout
        self.command_callback = command_callback
        self.log_callback = log_callback

        # Conexão serial
        self.serial_conn: Optional[serial.Serial] = None
        self.is_running = False
        self.receiver_thread: Optional[threading.Thread] = None

        # Estatísticas
        self.commands_received = 0
        self.last_command_time = 0.0
        self.errors = 0

        # Últimos valores para detecção de mudanças
        self.last_throttle = -1
        self.last_brake = -1
        self.last_steering = 0

    def _log(self, level: str, message: str):
        """Envia mensagem de log"""
        if self.log_callback:
            self.log_callback(level, message)
        else:
            print(f"[{level}] {message}")

    def list_available_ports(self) -> list:
        """
        Lista todas as portas seriais disponíveis com descrições

        Returns:
            list: Lista de tuplas (dispositivo_porta, descrição_porta)
        """
        ports = serial.tools.list_ports.comports()
        available_ports = []

        for port in ports:
            description = f"{port.device}"
            if port.description:
                description += f" - {port.description}"
            if port.manufacturer:
                description += f" ({port.manufacturer})"
            available_ports.append((port.device, description))

        return available_ports

    def auto_detect_port(self) -> Optional[str]:
        """
        Detecta automaticamente a porta serial do ESP32

        Returns:
            str: Porta detectada ou None
        """
        self._log("INFO", "Detectando porta ESP32 automaticamente...")

        # Lista todas as portas seriais disponíveis
        ports = serial.tools.list_ports.comports()

        # Procura por ESP32 (VID:PID varia por fabricante)
        for port in ports:
            # Verifica IDs de vendor/produto comuns do ESP32
            # Silicon Labs CP2102: 0x10C4:0xEA60
            # FTDI FT232: 0x0403:0x6001
            # CH340: 0x1A86:0x7523
            if port.vid in [0x10C4, 0x0403, 0x1A86]:
                self._log("INFO", f"Dispositivo tipo ESP32 encontrado em {port.device}")
                return port.device

            # Fallback: verifica descrição
            if "CP210" in port.description or "CH340" in port.description or "FTDI" in port.description:
                self._log("INFO", f"Dispositivo tipo ESP32 encontrado em {port.device}")
                return port.device

        # Se nenhum ESP32 encontrado, tenta portas comuns
        common_ports = ["/dev/ttyUSB0", "/dev/ttyUSB1", "/dev/ttyACM0", "/dev/ttyACM1"]
        for common_port in common_ports:
            try:
                test_serial = serial.Serial(common_port, self.baud_rate, timeout=0.5)
                test_serial.close()
                self._log("INFO", f"Porta serial encontrada em {common_port}")
                return common_port
            except:
                continue

        self._log("WARN", "Não foi possível detectar porta ESP32 automaticamente")
        return None

    def connect_to_port(self, port: str) -> bool:
        """
        Conecta a uma porta serial específica

        Args:
            port: Caminho do dispositivo da porta serial

        Returns:
            bool: True se conectado com sucesso
        """
        try:
            # Fecha conexão existente se houver
            if self.serial_conn:
                try:
                    self.serial_conn.close()
                except:
                    pass
                self.serial_conn = None

            # Define nova porta
            self.port = port

            # Abre conexão serial
            self._log("INFO", f"Conectando ao ESP32 em {self.port}")
            self.serial_conn = serial.Serial(
                port=self.port,
                baudrate=self.baud_rate,
                timeout=self.timeout,
                write_timeout=1.0,
            )

            # Aguarda ESP32 resetar (DTR causa reset)
            time.sleep(2.0)

            # Limpa qualquer lixo de inicialização
            self.serial_conn.reset_input_buffer()
            self.serial_conn.reset_output_buffer()

            self._log("INFO", f"Conectado ao ESP32 em {self.port}")
            return True

        except serial.SerialException as e:
            self._log("ERROR", f"Falha ao conectar a {self.port}: {e}")
            return False
        except Exception as e:
            self._log("ERROR", f"Erro inesperado durante conexão: {e}")
            return False

    def connect(self) -> bool:
        """
        Conecta à porta serial do ESP32 (detecção automática se não especificada)

        Returns:
            bool: True se conectado com sucesso
        """
        try:
            # Detecta porta automaticamente se não especificada
            if not self.port:
                self.port = self.auto_detect_port()

            if not self.port:
                self._log("ERROR", "Nenhuma porta serial especificada ou detectada")
                return False

            # Usa connect_to_port para conexão real
            return self.connect_to_port(self.port)

        except Exception as e:
            self._log("ERROR", f"Erro inesperado durante conexão: {e}")
            return False

    def parse_command(self, line: str):
        """
        Analisa comando recebido do ESP32

        Args:
            line: String de linha de comando
        """
        try:
            line = line.strip()
            if not line:
                return

            # Log de comando bruto para debugging
            # self._log("DEBUG", f"Recebido: {line}")

            # Analisa diferentes tipos de comando
            if line.startswith("THROTTLE:"):
                value = int(line.split(":")[1])
                if value != self.last_throttle:
                    self.last_throttle = value
                    if self.command_callback:
                        self.command_callback("THROTTLE", str(value))
                    self._log("INFO", f"🎮 Throttle: {value}%")

            elif line.startswith("BRAKE:"):
                value = int(line.split(":")[1])
                if value != self.last_brake:
                    self.last_brake = value
                    if self.command_callback:
                        self.command_callback("BRAKE", str(value))
                    self._log("INFO", f"🎮 Brake: {value}%")

            elif line.startswith("STEERING:"):
                value = int(line.split(":")[1])
                if value != self.last_steering:
                    self.last_steering = value
                    if self.command_callback:
                        self.command_callback("STEERING", str(value))
                    self._log("INFO", f"🎮 Steering: {value:+d}%")

            elif line == "GEAR_UP":
                if self.command_callback:
                    self.command_callback("GEAR_UP", "")
                self._log("INFO", "🎮 Gear Up")

            elif line == "GEAR_DOWN":
                if self.command_callback:
                    self.command_callback("GEAR_DOWN", "")
                self._log("INFO", "🎮 Gear Down")

            # === COMANDOS DE CALIBRAÇÃO ===
            elif line.startswith("CAL_THROTTLE:"):
                # Valor bruto do encoder para calibração do acelerador
                raw_value = int(line.split(":")[1])
                if self.command_callback:
                    self.command_callback("CAL_THROTTLE", str(raw_value))
                # Não loga cada valor para evitar spam

            elif line.startswith("CAL_BRAKE:"):
                # Valor bruto do encoder para calibração do freio
                raw_value = int(line.split(":")[1])
                if self.command_callback:
                    self.command_callback("CAL_BRAKE", str(raw_value))
                # Não loga cada valor para evitar spam

            elif line.startswith("CAL_STEERING:"):
                # Valor bruto do encoder para calibração da direção
                raw_value = int(line.split(":")[1])
                if self.command_callback:
                    self.command_callback("CAL_STEERING", str(raw_value))
                # Não loga cada valor para evitar spam

            elif line.startswith("CAL_COMPLETE:"):
                # Mensagem de calibração concluída
                component = line.split(":")[1]
                self._log("INFO", f"✅ Calibração concluída: {component}")
                if self.command_callback:
                    self.command_callback("CAL_COMPLETE", component)

            else:
                # Comando desconhecido ou mensagem do sistema
                if not line.startswith("F1 Cockpit") and not line.startswith("ESP32") and not line.startswith("="):
                    self._log("WARN", f"Comando desconhecido: {line}")

            self.commands_received += 1
            self.last_command_time = time.time()

        except Exception as e:
            self._log("ERROR", f"Erro ao analisar comando '{line}': {e}")
            self.errors += 1

    def receiver_loop(self):
        """Loop principal de recepção (executa em thread separada)"""
        self._log("INFO", "Loop de recepção serial iniciado")

        while self.is_running:
            try:
                # Lê linha da serial
                if self.serial_conn and self.serial_conn.in_waiting > 0:
                    line = self.serial_conn.readline().decode("utf-8", errors="ignore")
                    self.parse_command(line)
                else:
                    # Sleep pequeno para evitar uso excessivo de CPU
                    time.sleep(0.01)

            except serial.SerialException as e:
                self._log("ERROR", f"Erro de conexão serial: {e}")
                break
            except Exception as e:
                self._log("ERROR", f"Erro no loop de recepção: {e}")
                self.errors += 1
                time.sleep(0.1)

        self._log("INFO", "Loop de recepção serial parado")

    def start(self) -> bool:
        """
        Inicia recepção de comandos seriais

        Returns:
            bool: True se iniciado com sucesso
        """
        if self.is_running:
            self._log("WARN", "Receptor serial já está em execução")
            return False

        # Conecta à porta serial
        if not self.serial_conn:
            if not self.connect():
                return False

        # Inicia thread de recepção
        self.is_running = True
        self.receiver_thread = threading.Thread(target=self.receiver_loop, daemon=True)
        self.receiver_thread.start()

        self._log("INFO", "Receptor serial iniciado")
        return True

    def stop(self):
        """Para recepção de comandos seriais"""
        self._log("INFO", "Parando receptor serial...")

        self.is_running = False

        # Aguarda thread finalizar
        if self.receiver_thread and self.receiver_thread.is_alive():
            self.receiver_thread.join(timeout=2.0)

        # Fecha conexão serial
        if self.serial_conn:
            try:
                self.serial_conn.close()
            except:
                pass
            self.serial_conn = None

        self._log("INFO", f"Receptor serial parado - {self.commands_received} comandos recebidos")

    def get_statistics(self) -> dict:
        """
        Obtém estatísticas do receptor

        Returns:
            dict: Dicionário de estatísticas
        """
        return {
            "port": self.port,
            "baud_rate": self.baud_rate,
            "connected": self.serial_conn is not None and self.serial_conn.is_open,
            "running": self.is_running,
            "commands_received": self.commands_received,
            "errors": self.errors,
            "last_command_time": self.last_command_time,
        }

    def is_connected(self) -> bool:
        """Verifica se a conexão serial está ativa"""
        return self.serial_conn is not None and self.serial_conn.is_open

    def send_command(self, command: str) -> bool:
        """
        Envia comando para o ESP32 via serial

        Args:
            command: String de comando a enviar

        Returns:
            bool: True se enviado com sucesso
        """
        try:
            if not self.is_connected():
                self._log("WARN", "Não conectado ao ESP32")
                return False

            # Envia comando com newline
            command_bytes = (command + "\n").encode("utf-8")
            self.serial_conn.write(command_bytes)
            self.serial_conn.flush()

            self._log("DEBUG", f"Comando enviado: {command}")
            return True

        except Exception as e:
            self._log("ERROR", f"Erro ao enviar comando: {e}")
            return False
