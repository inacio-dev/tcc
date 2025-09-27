"""
components_manager.py - Gerenciamento de Componentes
====================================================

Responsável por inicializar e conectar todos os componentes do sistema F1.
"""

from typing import TYPE_CHECKING

from ...config import Config
from components import (
    NetworkClient,
    VideoDisplay,
    SensorDisplay,
    ConsoleInterface,
    info,
    debug,
    error,
)

if TYPE_CHECKING:
    from ..application import F1ClientApplication


class ComponentsManager:
    """Gerenciador de componentes da aplicação F1"""

    def __init__(self, app: "F1ClientApplication") -> None:
        """
        Inicializa o gerenciador de componentes

        Args:
            app: Instância da F1ClientApplication
        """
        self.app: "F1ClientApplication" = app

    def initialize_components(self) -> bool:
        """
        Inicializa todos os componentes do sistema

        Returns:
            bool: True se todos os componentes foram inicializados com sucesso
        """
        info("🚀 Inicializando F1 Client v2.0...", "MAIN")
        info(
            f"🔧 Porta: {self.app.port} | Buffer: {self.app.buffer_size // 1024}KB",
            "MAIN",
        )

        try:
            # 1. Cliente de rede (comunicação UDP)
            self._initialize_network_client()

            # 2. Sistema de vídeo
            self._initialize_video_display()

            # 3. Processamento de sensores
            self._initialize_sensor_display()

            # 4. Interface principal
            self._initialize_console_interface()

            # Conectar componentes
            self._connect_components()

            info("✅ Todos os componentes inicializados com sucesso!", "MAIN")
            return True

        except Exception as e:
            error(f"❌ Erro na inicialização: {e}", "MAIN")
            return False

    def _initialize_network_client(self) -> None:
        """Inicializa o cliente de rede UDP"""
        debug("📡 Inicializando cliente de rede...", "MAIN")
        self.app.network_client = NetworkClient(
            port=self.app.port,
            command_port=Config.COMMAND_PORT,
            buffer_size=self.app.buffer_size,
            rpi_ip=Config.RASPBERRY_PI_IP,
            client_ip=Config.CLIENT_IP,
            log_queue=self.app.log_queue,
            status_queue=self.app.status_queue,
            sensor_queue=self.app.sensor_queue,
            video_queue=self.app.video_queue,
        )

    def _initialize_video_display(self) -> None:
        """Inicializa o sistema de vídeo"""
        debug("🎥 Inicializando sistema de vídeo...", "MAIN")
        self.app.video_display = VideoDisplay(
            video_queue=self.app.video_queue, log_queue=self.app.log_queue
        )

    def _initialize_sensor_display(self) -> None:
        """Inicializa o processamento de sensores"""
        debug("📊 Inicializando processamento de sensores...", "MAIN")
        self.app.sensor_display = SensorDisplay(
            sensor_queue=self.app.sensor_queue, log_queue=self.app.log_queue
        )

    def _initialize_console_interface(self) -> None:
        """Inicializa a interface principal"""
        debug("🖥️ Inicializando interface do usuário...", "MAIN")

        # Verificar se sensor_display foi inicializado
        if self.app.sensor_display is None:
            error("❌ SensorDisplay não foi inicializado antes da ConsoleInterface", "COMPONENTS")
            raise RuntimeError("SensorDisplay deve ser inicializado antes da ConsoleInterface")

        self.app.console_interface = ConsoleInterface(
            log_queue=self.app.log_queue,
            status_queue=self.app.status_queue,
            sensor_display=self.app.sensor_display,
        )

    def _connect_components(self) -> None:
        """Conecta os componentes entre si"""
        # Network client ↔ Console (para envio de comandos)
        if self.app.console_interface is not None and self.app.network_client is not None:
            self.app.console_interface.set_network_client(self.app.network_client)

        # Video display ↔ Console (para vídeo integrado)
        if self.app.console_interface is not None and self.app.video_display is not None:
            self.app.console_interface.set_video_display(self.app.video_display)
