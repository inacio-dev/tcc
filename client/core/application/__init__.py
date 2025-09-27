"""
F1 Client Application Package
=============================

Este pacote contém a classe F1ClientApplication dividida em módulos temáticos:
- application_core: Classe principal e inicialização
- components_manager: Gerenciamento de componentes
- threads_manager: Gerenciamento de threads
- lifecycle_manager: Ciclo de vida da aplicação (run/stop)

Autor: Sistema F1 Remote Control
Versão: 2.0
"""

__version__ = "2.0.0"
__author__ = "Sistema F1 Remote Control"

from .application import F1ClientApplication

__all__ = ['F1ClientApplication']