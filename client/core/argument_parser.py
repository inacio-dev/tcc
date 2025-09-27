"""
argument_parser.py - Parser e Validação de Argumentos
======================================================

Gerencia argumentos da linha de comando e sua validação.
"""

import argparse
from .config import Config


def create_argument_parser() -> argparse.ArgumentParser:
    """Cria parser para argumentos da linha de comando"""
    parser = argparse.ArgumentParser(
        description="🏎️ F1 Client v2.0 - Sistema de Controle Remoto",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=f"""
🔧 Exemplos de uso:
  python3 main.py                    # Configuração padrão
  python3 main.py --port 8888        # Porta personalizada
  python3 main.py --buffer 256       # Buffer maior
  python3 main.py --debug             # Modo debug

📡 Configuração de rede:
  Raspberry Pi: {Config.RASPBERRY_PI_IP}:{Config.DEFAULT_PORT}
  Cliente:      {Config.CLIENT_IP}:{Config.DEFAULT_PORT}
        """,
    )

    parser.add_argument(
        "--port",
        "-p",
        type=int,
        default=Config.DEFAULT_PORT,
        help=f"Porta UDP (padrão: {Config.DEFAULT_PORT})",
    )

    parser.add_argument(
        "--buffer",
        "-b",
        type=int,
        default=Config.DEFAULT_BUFFER_SIZE // 1024,
        help=f"Buffer em KB (padrão: {Config.DEFAULT_BUFFER_SIZE // 1024})",
    )

    parser.add_argument(
        "--debug",
        "-d",
        action="store_true",
        help="Ativa modo debug com logs detalhados",
    )

    return parser


def validate_arguments(args: argparse.Namespace) -> bool:
    """
    Valida argumentos da linha de comando

    Args:
        args: Argumentos parseados

    Returns:
        bool: True se argumentos são válidos
    """
    # Validar porta
    if not (Config.MIN_PORT <= args.port <= Config.MAX_PORT):
        print(f"❌ ERRO: Porta deve estar entre {Config.MIN_PORT} e {Config.MAX_PORT}")
        return False

    # Validar buffer
    if not (Config.MIN_BUFFER_KB <= args.buffer <= Config.MAX_BUFFER_KB):
        print(
            f"❌ ERRO: Buffer deve estar entre {Config.MIN_BUFFER_KB} e {Config.MAX_BUFFER_KB} KB"
        )
        return False

    return True
