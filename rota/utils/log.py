# -*- coding: utf-8 -*-
"""Log em console e em arquivo, com identificador de execução.

O `EXECUCAO_ID` carimba o staging, o relatório de qualidade e o nome do arquivo
de log — é ele que amarra "este número veio desta execução".

Dado sensível não vai para o log: nome de cliente e de funcionário aparecem só
em contagem e em CSV de exceção dentro de `data/rota/quality/`, nunca no console.

Cada leitor registra, por arquivo, quantas linhas leu e quantas descartou
(`contar`). O orquestrador grava tudo no `resumo_<execução>.json`.
"""
from __future__ import annotations

import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

from .config import CFG, PASTA_LOGS

EXECUCAO_ID = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:6]
INICIO = datetime.now()

_T0 = time.time()
_ARQ = None
_AVISOS: list[str] = []
_ERROS: list[str] = []
_CONTAGENS: dict[str, dict] = {}
_ETAPAS: list[dict] = []

_MARCA = {"ok": "  ok  ", "aviso": " aviso", "erro": " ERRO ", "": "      "}


def abrir() -> Path:
    """Abre o arquivo de log da execução e limpa os antigos."""
    global _ARQ
    PASTA_LOGS.mkdir(parents=True, exist_ok=True)
    alvo = PASTA_LOGS / f"pipeline_{EXECUCAO_ID}.log"
    _ARQ = open(alvo, "w", encoding="utf-8")
    _limpar_antigos()
    return alvo


def _limpar_antigos() -> None:
    manter = int(CFG.get("logs", {}).get("manter_ultimos", 30))
    for padrao in ("pipeline_*.log", "resumo_*.json"):
        velhos = sorted(PASTA_LOGS.glob(padrao))
        for v in velhos[:-manter] if len(velhos) > manter else []:
            try:
                v.unlink()
            except OSError:
                pass


def log(msg: str = "", nivel: str = "") -> None:
    linha = f"[{time.time() - _T0:6.1f}s]{_MARCA.get(nivel, _MARCA[''])} {msg}"
    print(linha, flush=True)
    if _ARQ:
        _ARQ.write(linha + "\n")
        _ARQ.flush()
    if nivel == "aviso":
        _AVISOS.append(msg)
    elif nivel == "erro":
        _ERROS.append(msg)


def titulo(msg: str) -> None:
    barra = "=" * 78
    for l in (barra, msg, barra):
        log(l)


def etapa_inicio(nome: str) -> None:
    titulo(nome)
    _ETAPAS.append({"etapa": nome, "inicio": datetime.now().isoformat(timespec="seconds"), "t0": time.time()})


def etapa_fim(situacao: str = "ok", **info) -> None:
    e = _ETAPAS[-1]
    e["fim"] = datetime.now().isoformat(timespec="seconds")
    e["segundos"] = round(time.time() - e.pop("t0"), 1)
    e["situacao"] = situacao
    e.update(info)
    log(f"etapa '{e['etapa']}' {situacao} em {e['segundos']} s", "ok" if situacao in ("ok", "pulada") else "aviso")


def contar(arquivo: str, lidas: int, rejeitadas: int = 0, **detalhe) -> None:
    """Linhas lidas e descartadas por arquivo de origem."""
    _CONTAGENS[arquivo] = {"lidas": int(lidas), "rejeitadas": int(rejeitadas), **detalhe}


def contagens() -> dict[str, dict]:
    return dict(_CONTAGENS)


def etapas() -> list[dict]:
    return [{k: v for k, v in e.items() if k != "t0"} for e in _ETAPAS]


def abortar(msg: str, situacao: str | None = None) -> None:
    """Erro fatal: registra, fecha o log e sai com exit code 1.

    `situacao` substitui a frase final quando o padrão ("nada foi gravado")
    não for verdade — aborto no MEIO de uma gravação."""
    log(msg, "erro")
    if _ETAPAS and "fim" not in _ETAPAS[-1]:
        etapa_fim("abortada")
    log("")
    log("PIPELINE ABORTADO — "
        + (situacao or "nada foi gravado na camada curada nesta execucao; nada foi publicado."), "erro")
    fechar()
    sys.exit(1)


def avisos() -> list[str]:
    return list(_AVISOS)


def erros() -> list[str]:
    return list(_ERROS)


def fechar() -> None:
    global _ARQ
    if _ARQ:
        _ARQ.close()
        _ARQ = None
