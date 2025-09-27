"""
threads_manager.py - Gerenciamento de Threads
==============================================

Responsável por iniciar e gerenciar todas as threads do sistema F1.
"""

import threading
from typing import TYPE_CHECKING

from components import info, debug

if TYPE_CHECKING:
    from ..application import F1ClientApplication


class ThreadsManager:
    """Gerenciador de threads da aplicação F1"""

    def __init__(self, app: "F1ClientApplication") -> None:
        """
        Inicializa o gerenciador de threads

        Args:
            app: Instância da F1ClientApplication
        """
        self.app: "F1ClientApplication" = app

    def start_threads(self) -> None:
        """Inicia todas as threads do sistema"""
        info("🔄 Iniciando threads do sistema...", "MAIN")

        # Thread de rede (recepção UDP)
        self._start_network_thread()

        # Thread de vídeo
        self._start_video_thread()

        # Thread da interface (principal - não daemon)
        self._start_console_thread()

    def _start_network_thread(self) -> None:
        """Inicia thread de rede para recepção UDP"""
        if self.app.network_client:
            self.app.network_thread = threading.Thread(
                target=self.app.network_client.run_receiver,
                name="NetworkThread",
                daemon=True,
            )
            self.app.network_thread.start()
            debug("📡 Thread de rede iniciada", "MAIN")

    def _start_video_thread(self) -> None:
        """Inicia thread de processamento de vídeo"""
        if self.app.video_display:
            self.app.video_thread = threading.Thread(
                target=self.app.video_display.run_display,
                name="VideoThread",
                daemon=True,
            )
            self.app.video_thread.start()
            debug("🎥 Thread de vídeo iniciada", "MAIN")

    def _start_console_thread(self) -> None:
        """Inicia thread da interface principal (não-daemon)"""
        if self.app.console_interface:
            self.app.console_thread = threading.Thread(
                target=self.app.console_interface.run_interface,
                name="ConsoleThread",
                daemon=False,  # Thread principal
            )
            self.app.console_thread.start()
            debug("🖥️ Thread da interface iniciada", "MAIN")

    def join_threads_with_timeout(self) -> None:
        """Aguarda threads daemon com timeout controlado"""
        threads = [(self.app.network_thread, "Rede"), (self.app.video_thread, "Vídeo")]

        for thread, name in threads:
            try:
                if thread and thread.is_alive():
                    thread.join(timeout=0.5)  # Timeout reduzido
                    if thread.is_alive():
                        debug(f"⚠️ Thread {name} ainda ativa (ignorando)", "MAIN")
                    else:
                        debug(f"✅ Thread {name} finalizada", "MAIN")
            except Exception as e:
                try:
                    debug(f"⚠️ Erro ao aguardar thread {name}: {e}", "MAIN")
                except:
                    pass
