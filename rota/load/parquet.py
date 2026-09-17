# -*- coding: utf-8 -*-
"""Gravação e leitura da camada curada (Parquet zstd). Adaptado de `dn/load/parquet.py`.

As tabelas são pequenas (dezenas de KB): cada uma é UM arquivo, regravado inteiro
a cada execução (reprocessamento completo, idempotente). A gravação é atômica
(`.tmp` + replace) — o OneDrive nunca vê um Parquet pela metade.
"""
from __future__ import annotations

import time
from pathlib import Path

import pandas as pd

from ..utils.config import PASTA_CURATED
from ..utils.log import abortar, log


def salvar(df: pd.DataFrame, nome: str) -> Path:
    PASTA_CURATED.mkdir(parents=True, exist_ok=True)
    alvo = PASTA_CURATED / f"{nome}.parquet"
    tmp = alvo.with_suffix(".tmp")
    df.to_parquet(tmp, index=False, compression="zstd")
    for tentativa in range(4):
        try:
            tmp.replace(alvo)
            break
        except PermissionError:
            if tentativa == 3:
                abortar(f"nao foi possivel gravar {alvo.name}: o OneDrive costuma segurar o arquivo durante a sincronizacao. "
                        "Pause a sincronizacao e rode de novo.",
                        situacao="a camada curada pode ter ficado PARCIALMENTE atualizada; rode `python run_rota.py` de novo — o reprocessamento completo regrava tudo.")
            time.sleep(0.5)
    log(f"{nome:<22} {len(df):>8,} linhas x {len(df.columns):>2} col  ->  {alvo.name} ({alvo.stat().st_size / 1024:,.0f} KB)", "ok")
    return alvo


def carregar(nome: str, colunas: list[str] | None = None) -> pd.DataFrame:
    alvo = PASTA_CURATED / f"{nome}.parquet"
    if not alvo.exists():
        abortar(f"{nome} nao existe em {PASTA_CURATED}. Rode `python run_rota.py` primeiro.")
    return pd.read_parquet(alvo, columns=colunas)
