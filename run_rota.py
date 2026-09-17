# -*- coding: utf-8 -*-
"""Painel de Rota · ponto único de execução.

    python run_rota.py            verificar -> ingerir (bases -> staging) -> resumo e manifesto
    python run_rota.py --forcar   ignora o cache: relê todas as bases

Saídas: data/rota/staging/ (Parquet por arquivo de origem), data/rota/curated/manifesto.json,
data/rota/logs/ (log + resumo da execução). Exit code 1 e "PIPELINE ABORTADO" em qualquer falha.
As etapas de modelo, painel e publicação entram nas próximas fases (docs/10_DECISOES.md).
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
    a = ap.parse_args()
    from rota import pipeline
    return pipeline.executar(forcar=a.forcar)


if __name__ == "__main__":
    sys.exit(main())
