"""
signal_handler.py - Gerenciamento de Sinais do Sistema
=======================================================

Configura handlers para sinais do sistema (SIGINT, SIGTERM).
"""

import signal
import os


def setup_signal_handlers(app):
    """Configura handlers para sinais do sistema"""

    def signal_handler(signum, frame):
        """Handler para sinais de interrupção"""
        try:
            print("\n⚠️ Sinal de interrupção recebido - parando aplicação...")
            app.stop()
        except:
            pass
        finally:
            # Força saída imediata
            os._exit(0)

    # Configura handlers para SIGINT (Ctrl+C) e SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
