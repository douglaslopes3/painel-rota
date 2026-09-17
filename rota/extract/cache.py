# -*- coding: utf-8 -*-
"""Cache de leitura das bases em Parquet (camada staging).

Adaptado de `dn/extract/cache.py` (Scorecard DN). Aqui as bases são pequenas e o
cache não existe por velocidade: existe para (1) dar ao staging um Parquet
TIPADO por arquivo de origem e (2) alimentar o manifesto — a impressão digital
que diz de quais arquivos cada painel nasceu.

A chave do cache é (caminho relativo, tamanho, data de modificação, hash rápido
do conteúdo, VERSÃO DOS LEITORES). A versão é o hash do CÓDIGO dos leitores
(`rota/extract/*.py` e `rota/utils/texto.py`): mudou uma linha em qualquer
leitor, o cache inteiro é invalidado sozinho — não existe o "esqueci de subir a
versão". O `config.yaml` também entra no hash, porque o mapa de colunas e os
logins ignorados vivem nele.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from ..utils.config import PASTA_CONFIG, PASTA_STAGING, RAIZ
from ..utils.log import log

_KB64 = 65536
_PASTA_EXTRACT = Path(__file__).resolve().parent
_ARQUIVOS_LEITORES = (sorted(_PASTA_EXTRACT.glob("*.py"))
                      + [RAIZ / "rota" / "utils" / "texto.py", PASTA_CONFIG / "config.yaml"])


def versao_leitores() -> str:
    """Hash curto do código-fonte dos leitores e do config. É a 'versão do cache'."""
    h = hashlib.md5()
    for arq in _ARQUIVOS_LEITORES:
        h.update(arq.name.encode())
        h.update(arq.read_bytes().replace(b"\r\n", b"\n"))   # fim de linha não invalida o cache
    return h.hexdigest()[:10]


VERSAO_LEITORES = versao_leitores()


def hash_rapido(arq: Path, tamanho: int | None = None) -> str:
    """Hash dos primeiros e últimos 64 KB — barato e suficiente para pegar
    conteúdo trocado com tamanho+mtime preservados."""
    tamanho = arq.stat().st_size if tamanho is None else tamanho
    h = hashlib.md5()
    with open(arq, "rb") as f:
        h.update(f.read(_KB64))
        if tamanho > _KB64:
            f.seek(max(tamanho - _KB64, 0))
            h.update(f.read(_KB64))
    return h.hexdigest()[:8]


def relativo(arq: Path) -> str:
    try:
        return arq.resolve().relative_to(RAIZ).as_posix()
    except ValueError:                       # fora da raiz do projeto
        return arq.resolve().as_posix()


def impressao(arq: Path) -> dict:
    """Impressão digital de um arquivo de base: o que o manifesto guarda."""
    st = arq.stat()
    return {"caminho": relativo(arq), "tamanho": st.st_size, "mtime": int(st.st_mtime),
            "hash": hash_rapido(arq, st.st_size)}


def _chave(arq: Path) -> str:
    i = impressao(arq)
    crua = f"v{VERSAO_LEITORES}|{i['caminho']}|{i['tamanho']}|{i['mtime']}|{i['hash']}"
    return hashlib.md5(crua.encode()).hexdigest()[:10]


def ler(arq: Path, leitor, forcar: bool = False) -> tuple[pd.DataFrame, dict]:
    """`leitor(caminho) -> (df, extra)`. `extra` é um dict pequeno (gabaritos,
    contagens) guardado num JSON ao lado do Parquet."""
    arq = Path(arq)
    PASTA_STAGING.mkdir(parents=True, exist_ok=True)
    ch = _chave(arq)
    alvo = PASTA_STAGING / f"{arq.stem}.{ch}.parquet"
    lado = PASTA_STAGING / f"{arq.stem}.{ch}.json"

    if not forcar and alvo.exists() and lado.exists():
        df = pd.read_parquet(alvo)
        with open(lado, encoding="utf-8") as f:
            extra = json.load(f)
        log(f"{arq.name:<40} {len(df):>10,} linhas  (cache)")
        return df, extra

    df, extra = leitor(arq)
    df.to_parquet(alvo, index=False, compression="zstd")
    with open(lado, "w", encoding="utf-8") as f:
        json.dump(extra, f, ensure_ascii=False)
    # Versões antigas do MESMO arquivo saem sozinhas.
    for velho in PASTA_STAGING.glob(f"{arq.stem}.*"):
        if velho not in (alvo, lado):
            try:
                velho.unlink()
            except OSError:
                pass
    log(f"{arq.name:<40} {len(df):>10,} linhas  (lido)")
    return df, extra
