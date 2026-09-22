# -*- coding: utf-8 -*-
"""Leitor da timeline de check-in/check-out do Mercanet (`bases/Mercanet/*.csv`).

Grão: 1 linha = 1 evento (CHECKIN ou CHECKOUT) de um usuário num cliente. O
staging guarda o EVENTO BRUTO: a deduplicação em visita (1 por cliente × dia) e
o pareamento check-in/check-out são regra de negócio e ficam na transformação
(Fase 2), para poderem mudar sem reler a base.

O que o leitor tira, contando: linha 100% repetida e logins declarados em
`logins_ignorados` (usuário de teste). Endereço, descrição e latitude/longitude
não vão para o staging (ver config).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..utils.config import CFG
from ..utils.log import abortar, contar, log
from ..utils.texto import digitos, texto
from . import cache, comum


def ler_arquivo(arq: Path) -> tuple[pd.DataFrame, dict]:
    cfg = CFG["fontes"]["checkins"]
    try:
        bruto = pd.read_csv(arq, sep=cfg["separador"], encoding=cfg["encoding"], dtype=str, keep_default_na=False)
    except (UnicodeDecodeError, pd.errors.ParserError) as e:
        abortar(f"{arq.name}: arquivo ilegivel como CSV '{cfg['separador']}' / {cfg['encoding']} ({e}).")
    lidas = len(bruto)
    repetidas = int(bruto.duplicated().sum())
    bruto = bruto.drop_duplicates()

    df = comum.mapear_colunas(bruto, cfg["colunas"], arq)
    df["LOGIN"] = texto(df["LOGIN"])
    df["NOME_USUARIO"] = texto(df["NOME_USUARIO"], maiuscula=False)
    df["COD_CLIENTE"] = digitos(df["COD_CLIENTE"])
    df["NOME_CLIENTE"] = texto(df["NOME_CLIENTE"])
    df["CIDADE"] = texto(df["CIDADE"])
    df["UF"] = texto(df["UF"])
    df["EVENTO"] = texto(df["EVENTO"])
    df["DATA_HORA"] = comum.datas(df["DATA_HORA"], cfg["formato_data"])

    ruins = df[df["DATA_HORA"].isna() | df["LOGIN"].isna() | df["COD_CLIENTE"].isna()]
    if len(ruins):
        abortar(f"{arq.name}: {len(ruins)} linha(s) com data do evento invalida ou sem usuario/cliente "
                f"(linhas do arquivo: {[int(i) + 2 for i in ruins.index[:5]]}). Formato(s) aceito(s): {cfg['formato_data']}.")
    estranhos = sorted(set(df["EVENTO"].dropna()) - set(cfg["eventos_esperados"]))
    if estranhos:
        abortar(f"{arq.name}: evento(s) nao reconhecido(s) {estranhos}; esperados {cfg['eventos_esperados']}.")

    ignorar = {str(k).upper() for k in (cfg.get("logins_ignorados") or {})}
    n_ign = int(df["LOGIN"].isin(ignorar).sum())
    df = df[~df["LOGIN"].isin(ignorar)].copy()

    df["DATA"] = df["DATA_HORA"].dt.normalize()
    df["ANO_MES"] = df["DATA_HORA"].dt.strftime("%Y-%m")
    df["ARQUIVO_ORIGEM"] = arq.name
    ordem = ["ANO_MES", "DATA", "DATA_HORA", "LOGIN", "NOME_USUARIO", "COD_CLIENTE", "NOME_CLIENTE", "CIDADE", "UF", "EVENTO", "ARQUIVO_ORIGEM"]
    extra = {"lidas": lidas, "repetidas": repetidas, "logins_ignorados": n_ign, "linhas": len(df),
             "meses": sorted(df["ANO_MES"].unique()), "logins": int(df["LOGIN"].nunique()),
             "inicio": str(df["DATA_HORA"].min()), "fim": str(df["DATA_HORA"].max()),
             "checkins": int((df["EVENTO"] == "CHECKIN").sum()), "checkouts": int((df["EVENTO"] == "CHECKOUT").sum())}
    return df[ordem].sort_values(["LOGIN", "DATA_HORA"]).reset_index(drop=True), extra


def carregar(forcar: bool = False) -> pd.DataFrame:
    arqs = comum.arquivos("checkins")
    if not arqs:
        abortar(f"nenhum arquivo de check-in em {CFG['fontes']['checkins']['pasta']}.")
    partes, meses = [], {}
    for a in arqs:
        df, x = cache.ler(a, ler_arquivo, forcar)
        contar(a.name, x["lidas"], x["repetidas"] + x["logins_ignorados"], repetidas=x["repetidas"],
               logins_ignorados=x["logins_ignorados"], meses=x["meses"], inicio=x["inicio"], fim=x["fim"],
               checkins=x["checkins"], checkouts=x["checkouts"])
        if x["repetidas"] or x["logins_ignorados"]:
            log(f"{a.name}: {x['repetidas']} linha(s) 100% repetida(s) e {x['logins_ignorados']} evento(s) de login ignorado fora")
        meses[a.name] = x["meses"]
        partes.append(df)
    comum.conferir_meses("checkins", meses)
    return pd.concat(partes, ignore_index=True)
