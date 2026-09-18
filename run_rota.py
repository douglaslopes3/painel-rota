# -*- coding: utf-8 -*-
"""Painel de Rota · ponto único de execução.

    python run_rota.py            verificar -> ingerir (bases -> staging) -> resumo e manifesto
    python run_rota.py --forcar   ignora o cache: relê todas as bases
    python run_rota.py --ensaio   além de gerar, ENSAIA a publicação numa pasta local (não toca em Painéis Comerciais)
    python run_rota.py --publicar publica nas pastas dos usuários — só funciona com `publicacao.liberada: true` no config (D-28)

Sem --ensaio nem --publicar, a etapa de publicação só LISTA o que seria copiado e para onde.

Saídas: data/rota/staging/ (Parquet por arquivo de origem), data/rota/curated/manifesto.json,
data/rota/logs/ (log + resumo da execução). Exit code 1 e "PIPELINE ABORTADO" em qualquer falha.
Guia do dia a dia: docs/11_GUIA_OPERACIONAL.md.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass


def main() -> int:
    ap = argparse.ArgumentParser(description="Painel de Rota · pipeline único")
    ap.add_argument("--forcar", action="store_true", help="relê todas as bases mesmo sem mudança")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--ensaio", action="store_true", help="ensaia a publicação numa pasta local (não toca no destino real)")
    g.add_argument("--publicar", action="store_true", help="publica nas pastas dos usuários (exige publicacao.liberada: true no config)")
    a = ap.parse_args()
    from rota import pipeline
    return pipeline.executar(forcar=a.forcar, modo_publicacao="publicar" if a.publicar else ("ensaio" if a.ensaio else "plano"))


if __name__ == "__main__":
    sys.exit(main())
