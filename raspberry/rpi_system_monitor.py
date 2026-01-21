#!/usr/bin/env python3
"""
rpi_system_monitor.py - Monitor de Métricas do Sistema Raspberry Pi

Coleta métricas do sistema operacional do Raspberry Pi:
- CPU: uso percentual, frequência, temperatura
- Memória: total, usada, livre, porcentagem
- Disco: espaço total, usado, livre
- Rede: bytes/pacotes enviados e recebidos, taxa de transferência
- Sistema: uptime, load average

CARACTERÍSTICAS:
================
- Leitura direta de /proc/ e /sys/ (sem dependências externas)
- Thread-safe com locks
- Cálculo de taxas de transferência de rede
- Detecção automática de interfaces de rede ativas
- Sampling rate configurável (padrão: 1Hz)
"""

import os
import threading
import time
from typing import Any, Dict, Optional

from logger import debug, error, info, warn


class RpiSystemMonitor:
    """
    Monitor de métricas do sistema Raspberry Pi

    Coleta dados de CPU, memória, disco, rede e sistema.
    """

    # Thresholds de alerta
    CPU_WARNING_THRESHOLD = 80.0
    CPU_CRITICAL_THRESHOLD = 95.0
    MEMORY_WARNING_THRESHOLD = 80.0
    MEMORY_CRITICAL_THRESHOLD = 95.0
    DISK_WARNING_THRESHOLD = 80.0
    DISK_CRITICAL_THRESHOLD = 95.0
    TEMP_WARNING_THRESHOLD = 70.0
    TEMP_CRITICAL_THRESHOLD = 80.0

    def __init__(self, sample_rate: float = 1.0):
        """
        Inicializa o monitor de sistema

        Args:
            sample_rate: Taxa de amostragem em Hz (padrão: 1.0 = 1 vez por segundo)
        """
        self.sample_rate = sample_rate
        self.sample_interval = 1.0 / sample_rate

        # Estado
        self.is_initialized = False
        self.is_running = False

        # Lock para thread-safety
        self.data_lock = threading.Lock()

        # Dados atuais
        self.current_data: Dict[str, Any] = {}

        # Dados anteriores para cálculo de taxas
        self._prev_cpu_times: Optional[Dict[str, float]] = None
        self._prev_net_stats: Optional[Dict[str, int]] = None
        self._prev_net_time: float = 0.0

        # Contadores
        self.readings_count = 0
        self.start_time = time.time()

        # Interface de rede primária
        self._primary_interface: Optional[str] = None

        info(f"RpiSystemMonitor inicializado @ {sample_rate}Hz", "RPI_SYS")

    def initialize(self) -> bool:
        """
        Inicializa o monitor de sistema

        Returns:
            bool: True se inicialização bem sucedida
        """
        try:
            info("Inicializando RpiSystemMonitor...", "RPI_SYS")

            # Verifica acesso aos arquivos do sistema
            required_files = [
                "/proc/stat",
                "/proc/meminfo",
                "/proc/uptime",
                "/proc/loadavg",
            ]

            for filepath in required_files:
                if not os.path.exists(filepath):
                    error(f"Arquivo não encontrado: {filepath}", "RPI_SYS")
                    return False

            # Detecta interface de rede primária
            self._detect_primary_interface()

            # Faz primeira leitura para inicializar dados anteriores
            self._read_cpu_times()
            self._read_network_stats()

            self.is_initialized = True
            info("RpiSystemMonitor inicializado com sucesso", "RPI_SYS")
            return True

        except Exception as e:
            error(f"Erro ao inicializar RpiSystemMonitor: {e}", "RPI_SYS")
            return False

    def _detect_primary_interface(self):
        """Detecta a interface de rede primária (wlan0 ou eth0)"""
        try:
            interfaces = ["wlan0", "eth0", "wlan1", "eth1"]
            for iface in interfaces:
                if os.path.exists(f"/sys/class/net/{iface}/statistics"):
                    self._primary_interface = iface
                    info(f"Interface de rede primária: {iface}", "RPI_SYS")
                    return

            # Fallback: primeira interface encontrada
            net_dir = "/sys/class/net"
            if os.path.exists(net_dir):
                for iface in os.listdir(net_dir):
                    if iface != "lo" and os.path.exists(f"{net_dir}/{iface}/statistics"):
                        self._primary_interface = iface
                        info(f"Interface de rede (fallback): {iface}", "RPI_SYS")
                        return

            warn("Nenhuma interface de rede encontrada", "RPI_SYS")

        except Exception as e:
            warn(f"Erro ao detectar interface de rede: {e}", "RPI_SYS")

    def update(self) -> bool:
        """
        Atualiza todas as métricas do sistema

        Returns:
            bool: True se atualização bem sucedida
        """
        if not self.is_initialized:
            return False

        try:
            with self.data_lock:
                # CPU
                cpu_data = self._read_cpu_metrics()
                self.current_data.update(cpu_data)

                # Memória
                mem_data = self._read_memory_metrics()
                self.current_data.update(mem_data)

                # Disco
                disk_data = self._read_disk_metrics()
                self.current_data.update(disk_data)

                # Rede
                net_data = self._read_network_metrics()
                self.current_data.update(net_data)

                # Sistema
                sys_data = self._read_system_metrics()
                self.current_data.update(sys_data)

                # Metadados
                self.readings_count += 1
                self.current_data["rpi_sys_timestamp"] = round(time.time(), 3)
                self.current_data["rpi_sys_readings_count"] = self.readings_count

            return True

        except Exception as e:
            error(f"Erro ao atualizar métricas: {e}", "RPI_SYS")
            return False

    def _read_cpu_metrics(self) -> Dict[str, Any]:
        """Lê métricas de CPU"""
        data = {}

        try:
            # Uso de CPU (calculado a partir de /proc/stat)
            cpu_usage = self._calculate_cpu_usage()
            data["rpi_cpu_usage_percent"] = round(cpu_usage, 1)
            data["rpi_cpu_status"] = self._get_cpu_status(cpu_usage)

            # Frequência da CPU
            freq = self._read_cpu_frequency()
            data["rpi_cpu_freq_mhz"] = freq

            # Temperatura da CPU
            temp = self._read_cpu_temperature()
            data["rpi_cpu_temp_c"] = round(temp, 1)
            data["rpi_cpu_temp_status"] = self._get_temp_status(temp)

            # Número de cores
            data["rpi_cpu_cores"] = os.cpu_count() or 4

        except Exception as e:
            warn(f"Erro ao ler métricas de CPU: {e}", "RPI_SYS", rate_limit=5.0)

        return data

    def _read_cpu_times(self) -> Dict[str, float]:
        """Lê tempos de CPU de /proc/stat"""
        try:
            with open("/proc/stat", "r") as f:
                line = f.readline()

            parts = line.split()
            # cpu user nice system idle iowait irq softirq steal guest guest_nice
            times = {
                "user": float(parts[1]),
                "nice": float(parts[2]),
                "system": float(parts[3]),
                "idle": float(parts[4]),
                "iowait": float(parts[5]) if len(parts) > 5 else 0,
                "irq": float(parts[6]) if len(parts) > 6 else 0,
                "softirq": float(parts[7]) if len(parts) > 7 else 0,
                "steal": float(parts[8]) if len(parts) > 8 else 0,
            }

            return times

        except Exception as e:
            warn(f"Erro ao ler /proc/stat: {e}", "RPI_SYS", rate_limit=5.0)
            return {}

    def _calculate_cpu_usage(self) -> float:
        """Calcula uso de CPU baseado na diferença de tempos"""
        try:
            current_times = self._read_cpu_times()

            if not current_times or not self._prev_cpu_times:
                self._prev_cpu_times = current_times
                return 0.0

            # Calcula diferenças
            prev = self._prev_cpu_times
            curr = current_times

            idle_diff = (curr.get("idle", 0) - prev.get("idle", 0)) + \
                        (curr.get("iowait", 0) - prev.get("iowait", 0))

            total_diff = sum(curr.values()) - sum(prev.values())

            self._prev_cpu_times = current_times

            if total_diff <= 0:
                return 0.0

            cpu_usage = ((total_diff - idle_diff) / total_diff) * 100.0
            return max(0.0, min(100.0, cpu_usage))

        except Exception as e:
            warn(f"Erro ao calcular uso de CPU: {e}", "RPI_SYS", rate_limit=5.0)
            return 0.0

    def _read_cpu_frequency(self) -> int:
        """Lê frequência atual da CPU em MHz"""
        try:
            # Tenta ler de /sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq
            freq_file = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"
            if os.path.exists(freq_file):
                with open(freq_file, "r") as f:
                    freq_khz = int(f.read().strip())
                    return freq_khz // 1000  # Converte kHz para MHz

            # Fallback: /proc/cpuinfo
            with open("/proc/cpuinfo", "r") as f:
                for line in f:
                    if "cpu MHz" in line:
                        return int(float(line.split(":")[1].strip()))

            return 0

        except Exception as e:
            warn(f"Erro ao ler frequência da CPU: {e}", "RPI_SYS", rate_limit=5.0)
            return 0

    def _read_cpu_temperature(self) -> float:
        """Lê temperatura da CPU"""
        try:
            with open("/sys/class/thermal/thermal_zone0/temp", "r") as f:
                millidegrees = int(f.read().strip())
                return millidegrees / 1000.0
        except Exception:
            return 0.0

    def _get_cpu_status(self, usage: float) -> str:
        """Retorna status do uso de CPU"""
        if usage >= self.CPU_CRITICAL_THRESHOLD:
            return "CRITICAL"
        elif usage >= self.CPU_WARNING_THRESHOLD:
            return "WARNING"
        else:
            return "NORMAL"

    def _get_temp_status(self, temp: float) -> str:
        """Retorna status da temperatura"""
        if temp >= self.TEMP_CRITICAL_THRESHOLD:
            return "CRITICAL"
        elif temp >= self.TEMP_WARNING_THRESHOLD:
            return "WARNING"
        elif temp >= 60.0:
            return "WARM"
        else:
            return "NORMAL"

    def _read_memory_metrics(self) -> Dict[str, Any]:
        """Lê métricas de memória de /proc/meminfo"""
        data = {}

        try:
            meminfo = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().split()[0]  # Remove 'kB'
                        meminfo[key] = int(value)

            # RAM
            total = meminfo.get("MemTotal", 0) // 1024  # MB
            free = meminfo.get("MemFree", 0) // 1024
            available = meminfo.get("MemAvailable", 0) // 1024
            buffers = meminfo.get("Buffers", 0) // 1024
            cached = meminfo.get("Cached", 0) // 1024

            used = total - available
            usage_percent = (used / total * 100) if total > 0 else 0

            data["rpi_mem_total_mb"] = total
            data["rpi_mem_used_mb"] = used
            data["rpi_mem_free_mb"] = available
            data["rpi_mem_buffers_mb"] = buffers
            data["rpi_mem_cached_mb"] = cached
            data["rpi_mem_usage_percent"] = round(usage_percent, 1)
            data["rpi_mem_status"] = self._get_memory_status(usage_percent)

            # Swap
            swap_total = meminfo.get("SwapTotal", 0) // 1024
            swap_free = meminfo.get("SwapFree", 0) // 1024
            swap_used = swap_total - swap_free
            swap_percent = (swap_used / swap_total * 100) if swap_total > 0 else 0

            data["rpi_swap_total_mb"] = swap_total
            data["rpi_swap_used_mb"] = swap_used
            data["rpi_swap_usage_percent"] = round(swap_percent, 1)

        except Exception as e:
            warn(f"Erro ao ler métricas de memória: {e}", "RPI_SYS", rate_limit=5.0)

        return data

    def _get_memory_status(self, usage: float) -> str:
        """Retorna status do uso de memória"""
        if usage >= self.MEMORY_CRITICAL_THRESHOLD:
            return "CRITICAL"
        elif usage >= self.MEMORY_WARNING_THRESHOLD:
            return "WARNING"
        else:
            return "NORMAL"

    def _read_disk_metrics(self) -> Dict[str, Any]:
        """Lê métricas de disco"""
        data = {}

        try:
            # Usa statvfs para obter informações do disco raiz
            stat = os.statvfs("/")

            total = (stat.f_blocks * stat.f_frsize) // (1024 * 1024 * 1024)  # GB
            free = (stat.f_bavail * stat.f_frsize) // (1024 * 1024 * 1024)
            used = total - free
            usage_percent = (used / total * 100) if total > 0 else 0

            data["rpi_disk_total_gb"] = total
            data["rpi_disk_used_gb"] = used
            data["rpi_disk_free_gb"] = free
            data["rpi_disk_usage_percent"] = round(usage_percent, 1)
            data["rpi_disk_status"] = self._get_disk_status(usage_percent)

        except Exception as e:
            warn(f"Erro ao ler métricas de disco: {e}", "RPI_SYS", rate_limit=5.0)

        return data

    def _get_disk_status(self, usage: float) -> str:
        """Retorna status do uso de disco"""
        if usage >= self.DISK_CRITICAL_THRESHOLD:
            return "CRITICAL"
        elif usage >= self.DISK_WARNING_THRESHOLD:
            return "WARNING"
        else:
            return "NORMAL"

    def _read_network_stats(self) -> Dict[str, int]:
        """Lê estatísticas de rede da interface primária"""
        try:
            if not self._primary_interface:
                return {}

            base_path = f"/sys/class/net/{self._primary_interface}/statistics"

            stats = {}
            for stat_name in ["rx_bytes", "tx_bytes", "rx_packets", "tx_packets"]:
                stat_file = f"{base_path}/{stat_name}"
                if os.path.exists(stat_file):
                    with open(stat_file, "r") as f:
                        stats[stat_name] = int(f.read().strip())

            return stats

        except Exception as e:
            warn(f"Erro ao ler estatísticas de rede: {e}", "RPI_SYS", rate_limit=5.0)
            return {}

    def _read_network_metrics(self) -> Dict[str, Any]:
        """Lê métricas de rede com cálculo de taxa de transferência"""
        data = {}

        try:
            current_stats = self._read_network_stats()
            current_time = time.time()

            if not current_stats:
                return data

            # Dados absolutos
            data["rpi_net_rx_bytes"] = current_stats.get("rx_bytes", 0)
            data["rpi_net_tx_bytes"] = current_stats.get("tx_bytes", 0)
            data["rpi_net_rx_packets"] = current_stats.get("rx_packets", 0)
            data["rpi_net_tx_packets"] = current_stats.get("tx_packets", 0)
            data["rpi_net_interface"] = self._primary_interface

            # Dados formatados (MB)
            data["rpi_net_rx_mb"] = round(current_stats.get("rx_bytes", 0) / (1024 * 1024), 2)
            data["rpi_net_tx_mb"] = round(current_stats.get("tx_bytes", 0) / (1024 * 1024), 2)

            # Calcula taxa de transferência
            if self._prev_net_stats and self._prev_net_time > 0:
                time_diff = current_time - self._prev_net_time

                if time_diff > 0:
                    rx_diff = current_stats.get("rx_bytes", 0) - self._prev_net_stats.get("rx_bytes", 0)
                    tx_diff = current_stats.get("tx_bytes", 0) - self._prev_net_stats.get("tx_bytes", 0)

                    # KB/s
                    data["rpi_net_rx_rate_kbps"] = round((rx_diff / 1024) / time_diff, 2)
                    data["rpi_net_tx_rate_kbps"] = round((tx_diff / 1024) / time_diff, 2)

            # Atualiza dados anteriores
            self._prev_net_stats = current_stats
            self._prev_net_time = current_time

        except Exception as e:
            warn(f"Erro ao ler métricas de rede: {e}", "RPI_SYS", rate_limit=5.0)

        return data

    def _read_system_metrics(self) -> Dict[str, Any]:
        """Lê métricas gerais do sistema"""
        data = {}

        try:
            # Uptime
            with open("/proc/uptime", "r") as f:
                uptime_seconds = float(f.read().split()[0])
                data["rpi_uptime_seconds"] = int(uptime_seconds)
                data["rpi_uptime_formatted"] = self._format_uptime(uptime_seconds)

            # Load average
            with open("/proc/loadavg", "r") as f:
                parts = f.read().split()
                data["rpi_load_1min"] = float(parts[0])
                data["rpi_load_5min"] = float(parts[1])
                data["rpi_load_15min"] = float(parts[2])

                # Processos (running/total)
                processes = parts[3].split("/")
                data["rpi_processes_running"] = int(processes[0])
                data["rpi_processes_total"] = int(processes[1])

            # Hostname
            try:
                with open("/etc/hostname", "r") as f:
                    data["rpi_hostname"] = f.read().strip()
            except Exception:
                data["rpi_hostname"] = "unknown"

        except Exception as e:
            warn(f"Erro ao ler métricas do sistema: {e}", "RPI_SYS", rate_limit=5.0)

        return data

    def _format_uptime(self, seconds: float) -> str:
        """Formata uptime em string legível"""
        days = int(seconds // 86400)
        hours = int((seconds % 86400) // 3600)
        minutes = int((seconds % 3600) // 60)

        if days > 0:
            return f"{days}d {hours}h {minutes}m"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"

    def get_sensor_data(self) -> Dict[str, Any]:
        """
        Retorna dados atuais das métricas do sistema

        Returns:
            Dict com todas as métricas
        """
        with self.data_lock:
            return self.current_data.copy()

    def get_summary(self) -> Dict[str, Any]:
        """
        Retorna resumo das métricas principais

        Returns:
            Dict com métricas principais resumidas
        """
        with self.data_lock:
            return {
                "cpu_usage": self.current_data.get("rpi_cpu_usage_percent", 0),
                "cpu_temp": self.current_data.get("rpi_cpu_temp_c", 0),
                "mem_usage": self.current_data.get("rpi_mem_usage_percent", 0),
                "disk_usage": self.current_data.get("rpi_disk_usage_percent", 0),
                "net_rx_rate": self.current_data.get("rpi_net_rx_rate_kbps", 0),
                "net_tx_rate": self.current_data.get("rpi_net_tx_rate_kbps", 0),
                "uptime": self.current_data.get("rpi_uptime_formatted", "0m"),
                "load_1min": self.current_data.get("rpi_load_1min", 0),
            }

    def cleanup(self):
        """Limpa recursos do monitor"""
        info("RpiSystemMonitor finalizado", "RPI_SYS")
        self.is_initialized = False
        self.is_running = False
