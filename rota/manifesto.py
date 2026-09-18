# -*- coding: utf-8 -*-
"""Manifesto das bases: de quais arquivos a última ingestão foi construída.

`data/rota/curated/manifesto.json` guarda a impressão digital (caminho, tamanho,
mtime, hash rápido) de CADA arquivo de base lido, mais a versão do código dos
leitores. É contra ele que o orquestrador diz o que mudou desde a última
execução e que o painel carimba o "dados atualizados em". Adaptado de
`dn/manifesto.py`.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from .extract import cache, clientes, comum, estrutura
from .utils.config import PASTA_CURATED
from .utils.log import log

ARQUIVO = PASTA_CURATED / "manifesto.json"
FONTES = ("rota", "checkins", "pedidos")


def bases_declaradas() -> list[Path]:
    """Todos os arquivos de base que o config declara (existentes)."""
    out: list[Path] = []
    for f in FONTES:
        out += comum.arquivos(f)
    for opcional in (estrutura.arquivo(), clientes.arquivo()):
        if opcional.exists():
            out.append(opcional)
    return sorted(set(out))


def atual() -> dict:
    return {"versao_leitores": cache.VERSAO_LEITORES,
            "bases": {cache.relativo(a): cache.impressao(a) for a in bases_declaradas()}}


def gravado() -> dict | None:
    if not ARQUIVO.exists():
        return None
    try:
        return json.loads(ARQUIVO.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def comparar(novo: dict | None = None, velho: dict | None = None) -> dict:
    """Diferenças entre o estado atual das bases e o manifesto gravado."""
    novo = novo or atual()
    velho = gravado() if velho is None else velho
    if velho is None:
        return {"motivo": "sem manifesto (primeira ingestao)", "mudou": True,
                "novos": sorted(novo["bases"]), "alterados": [], "removidos": [], "leitores_mudaram": False}
    nb, vb = novo["bases"], velho.get("bases", {})
    novos = sorted(set(nb) - set(vb))
    removidos = sorted(set(vb) - set(nb))
    alterados = sorted(k for k in set(nb) & set(vb)
                       if (nb[k]["tamanho"], nb[k]["mtime"], nb[k]["hash"]) !=
                          (vb[k]["tamanho"], vb[k]["mtime"], vb[k]["hash"]))
    leitores = novo["versao_leitores"] != velho.get("versao_leitores")
    mudou = bool(novos or removidos or alterados or leitores)
    motivo = ("bases inalteradas" if not mudou else
              "; ".join(m for m in (f"{len(novos)} base(s) nova(s)" if novos else "",
                                    f"{len(alterados)} base(s) alterada(s)" if alterados else "",
                                    f"{len(removidos)} base(s) removida(s)" if removidos else "",
                                    "codigo dos leitores ou config mudou" if leitores else "") if m))
    return {"motivo": motivo, "mudou": mudou, "novos": novos, "alterados": alterados,
            "removidos": removidos, "leitores_mudaram": leitores}


def gravar(execucao_id: str, extras: dict | None = None) -> None:
    m = atual()
    m["execucao"] = execucao_id
    m["gravado_em"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    m.update(extras or {})
    PASTA_CURATED.mkdir(parents=True, exist_ok=True)
    tmp = ARQUIVO.with_suffix(".tmp")
    tmp.write_text(json.dumps(m, ensure_ascii=False, indent=1), encoding="utf-8")
    tmp.replace(ARQUIVO)
    log(f"manifesto: {len(m['bases'])} base(s) registradas -> {ARQUIVO.name}", "ok")
