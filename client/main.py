#!/usr/bin/env python3
"""
F1 Client Application - Sistema de Controle Remoto
=================================================

Cliente principal do sistema F1 que recebe telemetria em tempo real
e controla o veículo remotamente via interface gráfica moderna.

Funcionalidades:
- Recepção de vídeo HD com baixa latência
- Telemetria completa (IMU, motor, sensores)
- Controles em tempo real (WASD, marcha manual)
- Interface F1 com dashboard profissional
- Comunicação UDP otimizada para performance

Autor: Sistema F1 Remote Control
Versão: 2.0
"""

import sys
import time
import os

# Core imports - funções principais do sistema
try:
    from core import (
        F1ClientApplication,
        create_argument_parser,
        validate_arguments,
        setup_signal_handlers,
        print_startup_banner,
    )
except ImportError as e:
    print(f"❌ ERRO: Não foi possível importar módulos do core: {e}")
    print("\nVerifique se os arquivos estão na pasta core/:")
    print("  - config.py, application.py, argument_parser.py")
    print("  - signal_handler.py, startup.py")
    sys.exit(1)


def main() -> None:
    """Função principal do programa"""
    # Parse argumentos
    parser = create_argument_parser()
    args = parser.parse_args()

    # Validar argumentos
    if not validate_arguments(args):
        sys.exit(1)

    # Banner
    print_startup_banner(args)

    # Converter buffer para bytes
    buffer_size = args.buffer * 1024

    # Criar aplicação
    app = F1ClientApplication(
        port=args.port, buffer_size=buffer_size, debug_mode=args.debug
    )

    # Configurar handlers de sinal
    setup_signal_handlers(app)

    try:
        # Executar
        success = app.run()

        if not success:
            print("\n❌ Falha na execução da aplicação")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️ Interrompido pelo usuário")

    except Exception as e:
        print(f"\n❌ Erro crítico: {e}")
        import traceback

        traceback.print_exc()
        sys.exit(1)

    finally:
        # Cleanup com timeout forçado
        try:
            app.stop()
        except:
            pass

        # Força saída limpa antes que o garbage collector cause problemas
        # Aguarda muito pouco para cleanup básico
        time.sleep(0.1)

        print("\n👋 Obrigado por usar o F1 Client!")

        # Força saída imediata para evitar problemas com Tkinter cleanup
        # Isso evita que o garbage collector tente limpar variáveis Tkinter
        # depois que o mainloop já foi destruído
        os._exit(0)


if __name__ == "__main__":
    main()
