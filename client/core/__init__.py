"""
F1 Client Core Package
======================

Este pacote contém as funções principais do sistema F1:
- config: Configurações centralizadas do sistema
- application: Classe principal da aplicação F1
- argument_parser: Parser e validação de argumentos
- signal_handler: Gerenciamento de sinais do sistema
- startup: Funções de inicialização e banner

Autor: Sistema F1 Remote Control
Versão: 2.0
"""

__version__ = "2.0.0"
__author__ = "Sistema F1 Remote Control"

# Importações principais do core
from .config import Config
from .application import F1ClientApplication
from .argument_parser import create_argument_parser, validate_arguments
from .signal_handler import setup_signal_handlers
from .startup import print_startup_banner

__all__ = [
    'Config',
    'F1ClientApplication',
    'create_argument_parser',
    'validate_arguments',
    'setup_signal_handlers',
    'print_startup_banner'
]