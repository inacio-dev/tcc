"""
config.py - Configurações Centralizadas do Sistema F1
======================================================

Contém todas as configurações e constantes do sistema.
"""


class Config:
    """Configurações centralizadas do sistema"""

    # Network
    DEFAULT_PORT = 9999
    COMMAND_PORT = 9998
    DEFAULT_BUFFER_SIZE = 131072  # 128KB

    # IPs fixos do projeto
    RASPBERRY_PI_IP = "192.168.5.33"
    CLIENT_IP = "192.168.5.11"

    # Limites
    MIN_PORT = 1024
    MAX_PORT = 65535
    MIN_BUFFER_KB = 32
    MAX_BUFFER_KB = 1024
