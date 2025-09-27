"""
startup.py - Funções de Inicialização
=====================================

Contém funções relacionadas à inicialização e banner do sistema.
"""

import argparse
from .config import Config


def print_startup_banner(args: argparse.Namespace) -> None:
    """Exibe banner de inicialização"""
    print("🏎️" + "=" * 70)
    print("    F1 CAR CLIENT v2.0 - REMOTE CONTROL SYSTEM")
    print("    Sistema de Telemetria e Controle em Tempo Real")
    print("=" * 72)
    print()

    print("📋 CONFIGURAÇÃO:")
    print(f"   🔌 Porta UDP:    {args.port}")
    print(f"   📦 Buffer:       {args.buffer} KB")
    print(f"   🐛 Debug:        {'Ativado' if args.debug else 'Desativado'}")
    print()

    print("🔗 REDE:")
    print(f"   📡 Raspberry Pi: {Config.RASPBERRY_PI_IP}:{Config.DEFAULT_PORT}")
    print(f"   💻 Cliente:      {Config.CLIENT_IP}:{Config.DEFAULT_PORT}")
    print()
