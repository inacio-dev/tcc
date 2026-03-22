#!/usr/bin/env python3
"""
logger.py - Sistema de Logging Otimizado para F1 Car
Substitui prints excessivos por logging com níveis configuráveis

NÍVEIS DE LOGGING:
=================
- ERROR: Apenas erros críticos
- WARN: Avisos importantes
- INFO: Informações essenciais (padrão)
- DEBUG: Informações detalhadas
- VERBOSE: Tudo (debug completo)

VANTAGENS:
==========
- Performance: Evita prints desnecessários em tempo real
- Configurável: Pode ser silenciado completamente
- Thread-safe: Seguro para uso em múltiplas threads
- Timestamps: Facilita debug quando necessário
"""

import sys
import threading
import time
from enum import Enum


class LogLevel(Enum):
    """Níveis de logging disponíveis"""

    ERROR = 0  # Apenas erros críticos
    WARN = 1  # Avisos importantes
    INFO = 2  # Informações essenciais (padrão)
    DEBUG = 3  # Informações detalhadas
    VERBOSE = 4  # Debug completo


class F1Logger:
    """Logger otimizado para o sistema F1"""

    def __init__(self, level: LogLevel = LogLevel.INFO, enable_timestamp: bool = False):
        """
        Inicializa o logger

        Args:
            level: Nível mínimo de log a exibir
            enable_timestamp: Se deve incluir timestamp nos logs
        """
        self.level = level
        self.enable_timestamp = enable_timestamp
        self.lock = threading.Lock()

        # Contadores para rate limiting
        self.last_log_times = {}
        self.log_counts = {}

    def _should_log(
        self, level: LogLevel, message: str = "", rate_limit: float = 0
    ) -> bool:
        """
        Verifica se deve fazer o log baseado no nível e rate limiting

        Args:
            level: Nível da mensagem
            message: Mensagem (para rate limiting)
            rate_limit: Intervalo mínimo entre logs iguais (segundos)

        Returns:
            bool: True se deve fazer o log
        """
        # Verifica nível
        if level.value > self.level.value:
            return False

        # Rate limiting se especificado
        if rate_limit > 0:
            current_time = time.time()
            key = f"{level.name}:{message[:50]}"  # Usa primeiros 50 chars como chave

            with self.lock:
                if key in self.last_log_times:
                    if current_time - self.last_log_times[key] < rate_limit:
                        return False

                self.last_log_times[key] = current_time

                # Evita crescimento indefinido do dict de rate limiting
                if len(self.last_log_times) > 500:
                    self.last_log_times.clear()

        return True

    def _format_message(
        self, level: LogLevel, message: str, component: str = ""
    ) -> str:
        """Formata a mensagem de log"""
        parts = []

        # Timestamp se habilitado
        if self.enable_timestamp:
            timestamp = time.strftime("%H:%M:%S", time.localtime())
            parts.append(f"[{timestamp}]")

        # Nível
        level_symbols = {
            LogLevel.ERROR: "❌",
            LogLevel.WARN: "⚠️",
            LogLevel.INFO: "ℹ️",
            LogLevel.DEBUG: "🔧",
            LogLevel.VERBOSE: "📝",
        }
        symbol = level_symbols.get(level, "📝")
        parts.append(f"{symbol}")

        # Componente se especificado
        if component:
            parts.append(f"[{component}]")

        # Mensagem
        parts.append(message)

        return " ".join(parts)

    def _log(
        self, level: LogLevel, message: str, component: str = "", rate_limit: float = 0
    ):
        """Método interno para fazer log"""
        if not self._should_log(level, message, rate_limit):
            return

        with self.lock:
            formatted = self._format_message(level, message, component)

            # Usa stderr para ERROR, stdout para o resto
            output = sys.stderr if level == LogLevel.ERROR else sys.stdout
            print(formatted, file=output, flush=True)

    def error(self, message: str, component: str = ""):
        """Log de erro crítico"""
        self._log(LogLevel.ERROR, message, component)

    def warn(self, message: str, component: str = "", rate_limit: float = 0):
        """Log de aviso"""
        self._log(LogLevel.WARN, message, component, rate_limit)

    def info(self, message: str, component: str = "", rate_limit: float = 0):
        """Log de informação"""
        self._log(LogLevel.INFO, message, component, rate_limit)

    def debug(self, message: str, component: str = "", rate_limit: float = 0):
        """Log de debug"""
        self._log(LogLevel.DEBUG, message, component, rate_limit)


# Instância global do logger
_global_logger = None


def get_logger() -> F1Logger:
    """Obtém a instância global do logger"""
    global _global_logger
    if _global_logger is None:
        _global_logger = F1Logger(LogLevel.INFO, enable_timestamp=True)
    return _global_logger


def init_logger(level: LogLevel = LogLevel.INFO, enable_timestamp: bool = True):
    """Inicializa o logger global"""
    global _global_logger
    _global_logger = F1Logger(level, enable_timestamp)


# Funções de conveniência
def error(message: str, component: str = ""):
    """Log de erro"""
    get_logger().error(message, component)


def warn(message: str, component: str = "", rate_limit: float = 0):
    """Log de aviso"""
    get_logger().warn(message, component, rate_limit)


def info(message: str, component: str = "", rate_limit: float = 0):
    """Log de informação"""
    get_logger().info(message, component, rate_limit)


def debug(message: str, component: str = "", rate_limit: float = 0):
    """Log de debug"""
    get_logger().debug(message, component, rate_limit)


