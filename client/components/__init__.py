"""
F1 Client Components Package
============================

Este pacote contém todos os componentes do cliente F1:
- network_client: Gerenciamento de conexão UDP
- video_display: Exibição de vídeo integrada
- sensor_display: Processamento de dados dos sensores
- console_interface: Interface principal com controles
- keyboard_controller: Controles de teclado assíncronos
- slider_controller: Controles deslizantes
- simple_logger: Sistema de logging

Autor: Sistema F1 Remote Control
Versão: 2.0
"""

__version__ = "2.0.0"
__author__ = "Sistema F1 Remote Control"

# Importações principais dos componentes
from .network_client import NetworkClient
from .video_display import VideoDisplay
from .sensor_display import SensorDisplay
from .console_interface import ConsoleInterface  # Nova estrutura modular
from .simple_logger import init_logger, info, debug, error, LogLevel

__all__ = [
    'NetworkClient',
    'VideoDisplay',
    'SensorDisplay',
    'ConsoleInterface',
    'init_logger',
    'info',
    'debug',
    'error',
    'LogLevel'
]