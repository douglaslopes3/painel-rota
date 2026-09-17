# -*- coding: utf-8 -*-
"""Leitor do de-para de estrutura (`Bases/Estrutura/DePara_Estrutura_Rota.xlsx`).

As bases não ligam o login do Mercanet ao executivo da rota, nem dizem quais
painéis gerar. Essa ligação é mantida à mão pelo time de Atacado neste arquivo
(modelo em `docs/DePara_Estrutura_Rota_MODELO.xlsx`):

- aba `Executivos`: EXECUTIVO (como na rota) -> LOGIN_MERCANET, ATIVO, DESDE, ATE
- aba `Visoes`: 1 linha por painel: VISAO, NIVEL, SUPERVISORES (separados por ;),
  USUARIO_NOME, PASTA_USUARIO, ATIVO

Nada aqui é inferido: login vazio fica vazio. `conferir()` lista o que não fecha
com a rota e com os check-ins; quem decide entre aviso e aborto é o pipeline
(`fontes.estrutura.obrigatorio`).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..utils.config import CFG, caminho
from ..utils.log import abortar
from ..utils.texto import chave_texto, texto

_COLS_EXEC = ["SUPERVISOR", "EXECUTIVO", "LOGIN_MERCANET", "ATIVO", "DESDE", "ATE"]
_COLS_VISAO = ["VISAO", "NIVEL", "SUPERVISORES", "USUARIO_NOME", "PASTA_USUARIO", "ATIVO"]


def arquivo() -> Path:
    return caminho(CFG["fontes"]["estrutura"]["arquivo"])


def _aba(arq: Path, aba: str, colunas: list[str]) -> pd.DataFrame:
    try:
        df = pd.read_excel(arq, sheet_name=aba, engine="calamine", dtype=object)
    except ValueError:
        abortar(f"{arq.name}: aba '{aba}' nao encontrada.")
    # o modelo traz a instrução na 2ª linha do cabeçalho ("LOGIN_MERCANET\n(PREENCHER)"): vale a 1ª linha
    df.columns = [chave_texto(str(c).split("\n")[0]) for c in df.columns]
    faltam = [c for c in colunas if c not in df.columns]
    if faltam:
        abortar(f"{arq.name}, aba '{aba}': coluna(s) ausente(s): {faltam}. Use o modelo de docs/ sem renomear cabecalhos.")
    return df[colunas].dropna(how="all").reset_index(drop=True)


def ler_arquivo(arq: Path) -> tuple[pd.DataFrame, dict]:
    """Devolve as duas abas empilhadas (coluna ABA) para caberem num Parquet só."""
    cfg = CFG["fontes"]["estrutura"]
    ex = _aba(arq, cfg["aba_executivos"], _COLS_EXEC)
    vi = _aba(arq, cfg["aba_visoes"], _COLS_VISAO)
    vi = vi[~vi["VISAO"].astype("string").str.upper().str.startswith("EXEMPLO", na=False)]

    ex["SUPERVISOR"] = texto(ex["SUPERVISOR"], maiuscula=False)
    ex["EXECUTIVO"] = texto(ex["EXECUTIVO"])
    ex["LOGIN_MERCANET"] = texto(ex["LOGIN_MERCANET"])
    ex["ATIVO"] = texto(ex["ATIVO"])
    for c in ("DESDE", "ATE"):
        ex[c] = pd.to_datetime(ex[c], errors="coerce", dayfirst=True)
    for c in ("VISAO", "USUARIO_NOME", "PASTA_USUARIO", "SUPERVISORES"):
        vi[c] = texto(vi[c], maiuscula=False)
    vi["NIVEL"] = texto(vi["NIVEL"], maiuscula=False)
    vi["ATIVO"] = texto(vi["ATIVO"])

    ex.insert(0, "ABA", "EXECUTIVOS")
    vi.insert(0, "ABA", "VISOES")
    df = pd.concat([ex, vi], ignore_index=True)
    for c in df.columns:                      # Parquet não aceita coluna object mista
        if c not in ("DESDE", "ATE"):
            df[c] = df[c].astype("string")
    return df, {"executivos": len(ex), "visoes": len(vi)}


def separar(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    ex = df[df["ABA"] == "EXECUTIVOS"][_COLS_EXEC].reset_index(drop=True)
    vi = df[df["ABA"] == "VISOES"][_COLS_VISAO].reset_index(drop=True)
    return ex, vi


def supervisores_da_visao(v: str | None) -> list[str]:
    return [p.strip() for p in str(v or "").split(";") if p.strip()]


def conferir(ex: pd.DataFrame, vi: pd.DataFrame, rota: pd.DataFrame, checkins: pd.DataFrame) -> list[str]:
    """Problemas entre o de-para, a rota e os check-ins. Lista vazia = fechado."""
    p: list[str] = []
    na_rota = set(rota["EXECUTIVO"].dropna())
    no_depara = set(ex["EXECUTIVO"].dropna())
    if na_rota - no_depara:
        p.append(f"executivo(s) da rota sem linha no de-para: {sorted(na_rota - no_depara)}")
    if no_depara - na_rota:
        p.append(f"executivo(s) do de-para que nao estao na rota: {sorted(no_depara - na_rota)}")
    sup_rota = rota.drop_duplicates("EXECUTIVO").set_index("EXECUTIVO")["SUPERVISOR"]
    div = [e for e, s in zip(ex["EXECUTIVO"], ex["SUPERVISOR"]) if e in sup_rota.index and chave_texto(sup_rota[e]) != chave_texto(s)]
    if div:
        p.append(f"supervisor do de-para diferente do da rota para: {sorted(div)}")
    com_login = ex.dropna(subset=["LOGIN_MERCANET"])
    dup = com_login[com_login.duplicated("LOGIN_MERCANET", keep=False)]["LOGIN_MERCANET"].unique()
    if len(dup):
        p.append(f"login usado por mais de um executivo: {sorted(dup)}")
    sem_login = sorted(ex[ex["LOGIN_MERCANET"].isna()]["EXECUTIVO"].dropna())
    if sem_login:
        p.append(f"{len(sem_login)} executivo(s) sem LOGIN_MERCANET (check-ins deles nao serao atribuidos): {sem_login}")
    orfaos = sorted(set(checkins["LOGIN"].dropna()) - set(com_login["LOGIN_MERCANET"]))
    if orfaos:
        p.append(f"{len(orfaos)} login(s) com check-in que nao estao no de-para: {orfaos}")
    sups = {chave_texto(s) for s in rota["SUPERVISOR"].dropna().unique()}
    for v, lista in zip(vi["VISAO"], vi["SUPERVISORES"]):
        fora = [s for s in supervisores_da_visao(lista) if chave_texto(s) not in sups]
        if fora or not supervisores_da_visao(lista):
            p.append(f"visao '{v}': supervisor(es) inexistente(s) na rota ou lista vazia: {fora}")
    sem_pasta = sorted(vi[vi["PASTA_USUARIO"].isna()]["VISAO"].dropna())
    if sem_pasta:
        p.append(f"{len(sem_pasta)} visao(oes) sem PASTA_USUARIO (nao serao publicadas): {sem_pasta}")
    return p
