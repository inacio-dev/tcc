#!/usr/bin/env python3
"""
client_system_monitor.py - Monitor de Métricas do Sistema Cliente (Notebook/PC)

Coleta métricas do sistema operacional do cliente:
- CPU: uso percentual, frequência, temperatura (se disponível)
- Memória: total, usada, livre, porcentagem
- Rede: taxa de transferência

Usa leitura direta de /proc/ para Linux (sem dependências externas).
"""

import os
import threading
import time
from typing import Any, Dict, Optional


class ClientSystemMonitor:
    """
    Monitor de métricas do sistema cliente (notebook/PC)
    """

    def __init__(self, sample_rate: float = 1.0):
        """
        Inicializa o monitor de sistema

        Args:
            sample_rate: Taxa de amostragem em Hz (padrão: 1.0)
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

        # Thread de monitoramento
        self._monitor_thread: Optional[threading.Thread] = None

    def initialize(self) -> bool:
        """Inicializa o monitor de sistema"""
        try:
            # Verifica acesso aos arquivos do sistema
            if not os.path.exists("/proc/stat"):
                return False

            # Detecta interface de rede primária
            self._detect_primary_interface()

            # Faz primeira leitura para inicializar dados anteriores
            self._read_cpu_times()
            self._read_network_stats()

            self.is_initialized = True
            return True

        except Exception:
            return False

    def start(self):
        """Inicia thread de monitoramento em background"""
        if not self.is_initialized:
            self.initialize()

        if self.is_running:
            return

        self.is_running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop, daemon=True, name="ClientSysMonitor"
        )
        self._monitor_thread.start()

    def stop(self):
        """Para a thread de monitoramento"""
        self.is_running = False
        if self._monitor_thread and self._monitor_thread.is_alive():
            self._monitor_thread.join(timeout=2.0)

    def _monitor_loop(self):
        """Loop de monitoramento em background"""
        while self.is_running:
            try:
                self.update()
                time.sleep(self.sample_interval)
            except Exception:
                time.sleep(1.0)

    def _detect_primary_interface(self):
        """Detecta a interface de rede primária"""
        try:
            interfaces = ["wlan0", "eth0", "wlp0s20f3", "enp0s31f6", "wlan1", "eth1"]
            for iface in interfaces:
                if os.path.exists(f"/sys/class/net/{iface}/statistics"):
                    self._primary_interface = iface
                    return

            # Fallback: primeira interface encontrada
            net_dir = "/sys/class/net"
            if os.path.exists(net_dir):
                for iface in os.listdir(net_dir):
                    if iface != "lo" and os.path.exists(f"{net_dir}/{iface}/statistics"):
                        self._primary_interface = iface
                        return

        except Exception:
            pass

    def update(self) -> bool:
        """Atualiza todas as métricas do sistema"""
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

                # Rede
                net_data = self._read_network_metrics()
                self.current_data.update(net_data)

                # Metadados
                self.readings_count += 1
                self.current_data["client_sys_timestamp"] = round(time.time(), 3)

            return True

        except Exception:
            return False

    def _read_cpu_times(self) -> Dict[str, float]:
        """Lê tempos de CPU de /proc/stat"""
        try:
            with open("/proc/stat", "r") as f:
                line = f.readline()

            parts = line.split()
            times = {
                "user": float(parts[1]),
                "nice": float(parts[2]),
                "system": float(parts[3]),
                "idle": float(parts[4]),
                "iowait": float(parts[5]) if len(parts) > 5 else 0,
            }
            return times
        except Exception:
            return {}

    def _read_cpu_metrics(self) -> Dict[str, Any]:
        """Lê métricas de CPU"""
        data = {}

        try:
            # Uso de CPU
            cpu_usage = self._calculate_cpu_usage()
            data["client_cpu_usage_percent"] = round(cpu_usage, 1)

            # Número de cores
            data["client_cpu_cores"] = os.cpu_count() or 1

            # Frequência (se disponível)
            freq = self._read_cpu_frequency()
            if freq > 0:
                data["client_cpu_freq_mhz"] = freq

            # Temperatura (se disponível)
            temp = self._read_cpu_temperature()
            if temp > 0:
                data["client_cpu_temp_c"] = round(temp, 1)

        except Exception:
            pass

        return data

    def _calculate_cpu_usage(self) -> float:
        """Calcula uso de CPU"""
        try:
            current_times = self._read_cpu_times()

            if not current_times or not self._prev_cpu_times:
                self._prev_cpu_times = current_times
                return 0.0

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

        except Exception:
            return 0.0

    def _read_cpu_frequency(self) -> int:
        """Lê frequência da CPU"""
        try:
            freq_file = "/sys/devices/system/cpu/cpu0/cpufreq/scaling_cur_freq"
            if os.path.exists(freq_file):
                with open(freq_file, "r") as f:
                    return int(f.read().strip()) // 1000
            return 0
        except Exception:
            return 0

    def _read_cpu_temperature(self) -> float:
        """Lê temperatura da CPU (se disponível)"""
        try:
            # Tenta várias fontes de temperatura
            temp_sources = [
                "/sys/class/thermal/thermal_zone0/temp",
                "/sys/class/hwmon/hwmon0/temp1_input",
                "/sys/class/hwmon/hwmon1/temp1_input",
            ]

            for source in temp_sources:
                if os.path.exists(source):
                    with open(source, "r") as f:
                        millidegrees = int(f.read().strip())
                        return millidegrees / 1000.0
            return 0.0
        except Exception:
            return 0.0

    def _read_memory_metrics(self) -> Dict[str, Any]:
        """Lê métricas de memória"""
        data = {}

        try:
            meminfo = {}
            with open("/proc/meminfo", "r") as f:
                for line in f:
                    parts = line.split(":")
                    if len(parts) == 2:
                        key = parts[0].strip()
                        value = parts[1].strip().split()[0]
                        meminfo[key] = int(value)

            total = meminfo.get("MemTotal", 0) // 1024  # MB
            available = meminfo.get("MemAvailable", 0) // 1024
            used = total - available
            usage_percent = (used / total * 100) if total > 0 else 0

            data["client_mem_total_mb"] = total
            data["client_mem_used_mb"] = used
            data["client_mem_free_mb"] = available
            data["client_mem_usage_percent"] = round(usage_percent, 1)

        except Exception:
            pass

        return data

    def _read_network_stats(self) -> Dict[str, int]:
        """Lê estatísticas de rede"""
        try:
            if not self._primary_interface:
                return {}

            base_path = f"/sys/class/net/{self._primary_interface}/statistics"

            stats = {}
            for stat_name in ["rx_bytes", "tx_bytes"]:
                stat_file = f"{base_path}/{stat_name}"
                if os.path.exists(stat_file):
                    with open(stat_file, "r") as f:
                        stats[stat_name] = int(f.read().strip())

            return stats

        except Exception:
            return {}

    def _read_network_metrics(self) -> Dict[str, Any]:
        """Lê métricas de rede com taxa de transferência"""
        data = {}

        try:
            current_stats = self._read_network_stats()
            current_time = time.time()

            if not current_stats:
                return data

            # Calcula taxa de transferência
            if self._prev_net_stats and self._prev_net_time > 0:
                time_diff = current_time - self._prev_net_time

                if time_diff > 0:
                    rx_diff = current_stats.get("rx_bytes", 0) - self._prev_net_stats.get("rx_bytes", 0)
                    tx_diff = current_stats.get("tx_bytes", 0) - self._prev_net_stats.get("tx_bytes", 0)

                    data["client_net_rx_rate_kbps"] = round((rx_diff / 1024) / time_diff, 1)
                    data["client_net_tx_rate_kbps"] = round((tx_diff / 1024) / time_diff, 1)

            self._prev_net_stats = current_stats
            self._prev_net_time = current_time

        except Exception:
            pass

        return data

    def get_data(self) -> Dict[str, Any]:
        """Retorna dados atuais"""
        with self.data_lock:
            return self.current_data.copy()
