#!/usr/bin/env python3
"""
simple_logger.py - Logger Simples para Cliente F1
Logging otimizado para performance em tempo real
"""

import sys
import threading
from enum import Enum


class LogLevel(Enum):
    ERROR = 0
    WARN = 1
    INFO = 2
    DEBUG = 3


class SimpleLogger:
    def __init__(self, level: LogLevel = LogLevel.INFO):
        self.level = level
        self.lock = threading.Lock()

    def _should_log(self, level: LogLevel) -> bool:
        return level.value <= self.level.value

    def _log(self, level: LogLevel, message: str, component: str = ""):
        if not self._should_log(level):
            return

        with self.lock:
            symbols = {
                LogLevel.ERROR: "❌",
                LogLevel.WARN: "⚠️",
                LogLevel.INFO: "ℹ️",
                LogLevel.DEBUG: "🔧",
            }

            symbol = symbols.get(level, "📝")
            comp_str = f"[{component}]" if component else ""

            output = sys.stderr if level == LogLevel.ERROR else sys.stdout
            print(f"{symbol} {comp_str} {message}", file=output, flush=True)

    def error(self, message: str, component: str = ""):
        self._log(LogLevel.ERROR, message, component)

    def warn(self, message: str, component: str = ""):
        self._log(LogLevel.WARN, message, component)

    def info(self, message: str, component: str = ""):
        self._log(LogLevel.INFO, message, component)

    def debug(self, message: str, component: str = ""):
        self._log(LogLevel.DEBUG, message, component)


# Global logger instance
_logger = SimpleLogger()


def init_logger(level: LogLevel = LogLevel.INFO):
    global _logger
    _logger = SimpleLogger(level)


def error(message: str, component: str = ""):
    _logger.error(message, component)


def warn(message: str, component: str = ""):
    _logger.warn(message, component)


def info(message: str, component: str = ""):
    _logger.info(message, component)


def debug(message: str, component: str = ""):
    _logger.debug(message, component)
