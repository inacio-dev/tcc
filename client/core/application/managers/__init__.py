"""
Managers Package - Gerenciadores da Aplicação F1
=================================================

Este pacote contém os gerenciadores especializados da aplicação:
- components_manager: Gerenciamento de componentes do sistema
- threads_manager: Gerenciamento de threads
- lifecycle_manager: Gerenciamento do ciclo de vida (run/stop)

Autor: Sistema F1 Remote Control
Versão: 2.0
"""

from .components_manager import ComponentsManager
from .threads_manager import ThreadsManager
from .lifecycle_manager import LifecycleManager

__all__ = [
    'ComponentsManager',
    'ThreadsManager',
    'LifecycleManager'
]