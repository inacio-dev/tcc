"""
lifecycle_manager.py - Gerenciamento do Ciclo de Vida
======================================================

Responsável por gerenciar o ciclo de vida da aplicação (run/stop).
"""

from typing import TYPE_CHECKING

from components import info, debug, error

if TYPE_CHECKING:
    from ..application import F1ClientApplication


class LifecycleManager:
    """Gerenciador do ciclo de vida da aplicação F1"""

    def __init__(self, app: "F1ClientApplication") -> None:
        """
        Inicializa o gerenciador de ciclo de vida

        Args:
            app: Instância da F1ClientApplication
        """
        self.app: "F1ClientApplication" = app

    def run(self) -> bool:
        """
        Executa a aplicação principal

        Returns:
            bool: True se executou com sucesso
        """
        # Inicializar componentes
        if not self.app.initialize_components():
            error("❌ Falha na inicialização", "MAIN")
            return False

        info("🏎️ SISTEMA F1 CLIENT ATIVO", "MAIN")
        info("📡 Aguardando Raspberry Pi... (Ctrl+C para parar)", "MAIN")

        self.app.running = True

        try:
            # Iniciar threads
            self.app.start_threads()

            # Aguardar thread principal (interface)
            if self.app.console_thread:
                self.app.console_thread.join()

            info("✅ Sistema encerrado com sucesso!", "MAIN")
            return True

        except KeyboardInterrupt:
            info("⚠️ Interrompido pelo usuário (Ctrl+C)", "MAIN")
            return True

        except Exception as e:
            error(f"❌ Erro durante execução: {e}", "MAIN")
            import traceback

            traceback.print_exc()
            return False

        finally:
            self.stop()

    def stop(self) -> None:
        """Para a aplicação de forma limpa"""
        if not self.app.running:
            return

        try:
            info("🛑 Parando F1 Client...", "MAIN")
        except:
            pass

        self.app.running = False

        # Parar componentes em ordem REVERSA da inicialização
        self._stop_components()

        # Aguardar threads daemon com timeout
        self.app.threads_manager.join_threads_with_timeout()

    def _stop_components(self) -> None:
        """Para todos os componentes em ordem reversa"""
        components = [
            (self.app.console_interface, "Interface"),
            (self.app.video_display, "Vídeo"),
            (self.app.network_client, "Rede"),
        ]

        for component, name in components:
            try:
                if component and hasattr(component, "stop"):
                    component.stop()
                    debug(f"✅ {name} parado", "MAIN")
            except Exception as e:
                try:
                    debug(f"⚠️ Erro ao parar {name}: {e}", "MAIN")
                except:
                    pass
