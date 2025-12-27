#!/usr/bin/env python
"""
split_pdf.py - Divide PDFs em partes menores para leitura

Limites recomendados para Claude Code:
- Tamanho máximo por parte: ~5MB (seguro para leitura)
- Páginas máximas por parte: ~30 páginas (dependendo do conteúdo)

Uso:
    python split_pdf.py arquivo.pdf
    python split_pdf.py arquivo.pdf --max-pages 20
    python split_pdf.py arquivo.pdf --max-size 3
    python split_pdf.py arquivo.pdf --max-pages 15 --max-size 2
    python split_pdf.py arquivo.pdf --analyse

Requisitos:
    pip install pypdf
    pip install cryptography
"""

import argparse
import os
import sys
from pathlib import Path

try:
    from pypdf import PdfReader, PdfWriter
except ImportError:
    print("Erro: pypdf não instalado.")
    print("Instale com: pip install pypdf")
    sys.exit(1)


# Limites padrão para Claude Code
DEFAULT_MAX_SIZE_MB = 5  # 5MB por parte (seguro)
DEFAULT_MAX_PAGES = 30   # 30 páginas por parte


def get_file_size_mb(file_path: str) -> float:
    """Retorna o tamanho do arquivo em MB"""
    return os.path.getsize(file_path) / (1024 * 1024)


def estimate_page_size(reader: PdfReader, page_num: int) -> float:
    """Estima o tamanho de uma página em bytes"""
    writer = PdfWriter()
    writer.add_page(reader.pages[page_num])

    # Escreve em memória para calcular tamanho
    from io import BytesIO
    buffer = BytesIO()
    writer.write(buffer)
    return buffer.tell()


def split_pdf(
    input_path: str,
    output_dir: str = None,
    max_pages: int = DEFAULT_MAX_PAGES,
    max_size_mb: float = DEFAULT_MAX_SIZE_MB
) -> list:
    """
    Divide um PDF em partes menores

    Args:
        input_path: Caminho do PDF de entrada
        output_dir: Diretório de saída (padrão: mesmo do arquivo)
        max_pages: Número máximo de páginas por parte
        max_size_mb: Tamanho máximo em MB por parte

    Returns:
        Lista de caminhos dos arquivos gerados
    """
    input_path = Path(input_path)

    if not input_path.exists():
        print(f"Erro: Arquivo não encontrado: {input_path}")
        return []

    if output_dir is None:
        output_dir = input_path.parent
    else:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

    # Informações do arquivo original
    original_size = get_file_size_mb(input_path)
    print(f"\n{'='*60}")
    print(f"Arquivo: {input_path.name}")
    print(f"Tamanho: {original_size:.2f} MB")

    # Lê o PDF
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)
    print(f"Páginas: {total_pages}")
    print(f"{'='*60}")

    # Se já está dentro dos limites, não precisa dividir
    if total_pages <= max_pages and original_size <= max_size_mb:
        print(f"\n✓ PDF já está dentro dos limites!")
        print(f"  - Páginas: {total_pages} <= {max_pages}")
        print(f"  - Tamanho: {original_size:.2f} MB <= {max_size_mb} MB")
        return [str(input_path)]

    print(f"\nLimites configurados:")
    print(f"  - Máximo de páginas: {max_pages}")
    print(f"  - Tamanho máximo: {max_size_mb} MB")
    print(f"\nDividindo PDF...")

    output_files = []
    part_num = 1
    current_page = 0
    max_size_bytes = max_size_mb * 1024 * 1024

    while current_page < total_pages:
        writer = PdfWriter()
        part_start = current_page
        current_size = 0
        pages_in_part = 0

        # Adiciona páginas até atingir um limite
        while current_page < total_pages:
            # Verifica limite de páginas
            if pages_in_part >= max_pages:
                break

            # Estima tamanho da página
            page_size = estimate_page_size(reader, current_page)

            # Verifica limite de tamanho (exceto primeira página da parte)
            if pages_in_part > 0 and current_size + page_size > max_size_bytes:
                break

            # Adiciona página
            writer.add_page(reader.pages[current_page])
            current_size += page_size
            pages_in_part += 1
            current_page += 1

        # Salva a parte
        base_name = input_path.stem
        output_name = f"{base_name}_parte{part_num:02d}.pdf"
        output_path = output_dir / output_name

        with open(output_path, 'wb') as f:
            writer.write(f)

        actual_size = get_file_size_mb(output_path)
        print(f"  Parte {part_num}: páginas {part_start+1}-{current_page} "
              f"({pages_in_part} pág, {actual_size:.2f} MB) -> {output_name}")

        output_files.append(str(output_path))
        part_num += 1

    print(f"\n{'='*60}")
    print(f"✓ PDF dividido em {len(output_files)} partes")
    print(f"  Diretório: {output_dir}")
    print(f"{'='*60}\n")

    # Lista os arquivos gerados
    print("Arquivos gerados:")
    for i, f in enumerate(output_files, 1):
        size = get_file_size_mb(f)
        print(f"  {i}. {Path(f).name} ({size:.2f} MB)")

    return output_files


def analyze_pdf(input_path: str):
    """Analisa um PDF e mostra informações úteis"""
    input_path = Path(input_path)

    if not input_path.exists():
        print(f"Erro: Arquivo não encontrado: {input_path}")
        return

    size_mb = get_file_size_mb(input_path)
    reader = PdfReader(input_path)
    total_pages = len(reader.pages)

    print(f"\n{'='*60}")
    print(f"ANÁLISE DO PDF")
    print(f"{'='*60}")
    print(f"Arquivo: {input_path.name}")
    print(f"Tamanho: {size_mb:.2f} MB")
    print(f"Páginas: {total_pages}")
    print(f"Média por página: {size_mb/total_pages:.2f} MB")
    print(f"{'='*60}")

    # Recomendações
    print(f"\nRECOMENDAÇÕES PARA CLAUDE CODE:")
    print(f"{'='*60}")

    if size_mb <= 5 and total_pages <= 30:
        print("✓ PDF pode ser lido diretamente (tamanho e páginas OK)")
    else:
        # Calcula número de partes necessárias
        parts_by_size = max(1, int(size_mb / DEFAULT_MAX_SIZE_MB) + 1)
        parts_by_pages = max(1, int(total_pages / DEFAULT_MAX_PAGES) + 1)
        recommended_parts = max(parts_by_size, parts_by_pages)

        print(f"⚠ PDF grande demais para leitura direta")
        print(f"  Recomendado dividir em ~{recommended_parts} partes")
        print(f"\nComando sugerido:")
        print(f"  python3 split_pdf.py \"{input_path}\"")

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Divide PDFs em partes menores para leitura pelo Claude Code",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Exemplos:
  %(prog)s documento.pdf                    # Usa limites padrão
  %(prog)s documento.pdf --max-pages 20     # Máximo 20 páginas por parte
  %(prog)s documento.pdf --max-size 3       # Máximo 3MB por parte
  %(prog)s documento.pdf --analyze          # Apenas analisa o PDF
  %(prog)s documento.pdf -o ./partes/       # Salva em diretório específico

Limites padrão (seguros para Claude Code):
  - Tamanho máximo: 5 MB por parte
  - Páginas máximas: 30 por parte
        """
    )

    parser.add_argument("pdf_file", help="Arquivo PDF para dividir")
    parser.add_argument("-o", "--output-dir", help="Diretório de saída")
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help=f"Máximo de páginas por parte (padrão: {DEFAULT_MAX_PAGES})"
    )
    parser.add_argument(
        "--max-size",
        type=float,
        default=DEFAULT_MAX_SIZE_MB,
        help=f"Tamanho máximo em MB por parte (padrão: {DEFAULT_MAX_SIZE_MB})"
    )
    parser.add_argument(
        "--analyze",
        action="store_true",
        help="Apenas analisa o PDF sem dividir"
    )

    args = parser.parse_args()

    if args.analyze:
        analyze_pdf(args.pdf_file)
    else:
        split_pdf(
            args.pdf_file,
            output_dir=args.output_dir,
            max_pages=args.max_pages,
            max_size_mb=args.max_size
        )


if __name__ == "__main__":
    main()
