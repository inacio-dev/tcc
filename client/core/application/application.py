"""
application.py - Classe Principal da Aplicação F1
==================================================

Contém a classe F1ClientApplication principal que orquestra todo o sistema.
"""

import sys
import threading
import time
import queue
from typing import Optional, Any

from ..config import Config
from components import (
    NetworkClient,
    VideoDisplay,
    SensorDisplay,
    ConsoleInterface,
    init_logger,
    LogLevel,
)

# Importar gerenciadores especializados
from .managers import ComponentsManager, ThreadsManager, LifecycleManager


class F1ClientApplication:
    """
    Aplicação principal do cliente F1

    Gerencia todos os componentes do sistema:
    - Conexão de rede UDP
    - Interface gráfica
    - Exibição de vídeo
    - Processamento de telemetria
    - Controles de usuário
    """

    def __init__(
        self,
        port: int = Config.DEFAULT_PORT,
        buffer_size: int = Config.DEFAULT_BUFFER_SIZE,
        debug_mode: bool = False,
    ):
        """
        Inicializa a aplicação F1

        Args:
            port: Porta UDP para receber dados
            buffer_size: Tamanho do buffer UDP em bytes
            debug_mode: Ativa logs detalhados
        """
        # Configurações
        self.port: int = port
        self.buffer_size: int = buffer_size
        self.debug_mode: bool = debug_mode

        # Componentes principais
        self.network_client: Optional[NetworkClient] = None
        self.video_display: Optional[VideoDisplay] = None
        self.sensor_display: Optional[SensorDisplay] = None
        self.console_interface: Optional[ConsoleInterface] = None

        # Threading
        self.network_thread: Optional[threading.Thread] = None
        self.video_thread: Optional[threading.Thread] = None
        self.console_thread: Optional[threading.Thread] = None

        # Estado
        self.running: bool = False
        self.start_time: float = time.time()

        # Filas de comunicação entre threads (serão inicializadas em _setup_queues)
        self.log_queue: queue.Queue[Any]
        self.status_queue: queue.Queue[Any]
        self.sensor_queue: queue.Queue[Any]
        self.video_queue: queue.Queue[Any]

        # Configurar filas de comunicação entre threads
        self._setup_queues()

        # Inicializar logger
        init_logger(LogLevel.DEBUG if debug_mode else LogLevel.INFO)

        # Gerenciadores especializados
        self.components_manager: ComponentsManager = ComponentsManager(self)
        self.threads_manager: ThreadsManager = ThreadsManager(self)
        self.lifecycle_manager: LifecycleManager = LifecycleManager(self)

    def _setup_queues(self) -> None:
        """Configura filas de comunicação entre threads"""
        self.log_queue = queue.Queue()
        self.status_queue = queue.Queue()
        self.sensor_queue = queue.Queue()
        self.video_queue = queue.Queue()

    def initialize_components(self) -> bool:
        """Delega inicialização para o ComponentsManager"""
        return self.components_manager.initialize_components()

    def start_threads(self) -> None:
        """Delega gerenciamento de threads para o ThreadsManager"""
        self.threads_manager.start_threads()

    def run(self) -> bool:
        """Delega execução para o LifecycleManager"""
        return self.lifecycle_manager.run()

    def stop(self) -> None:
        """Delega parada para o LifecycleManager"""
        self.lifecycle_manager.stop()
