# -*- coding: utf-8 -*-
"""Leitor da rota planejada do mês (`Bases/Rota/Rota_*.xlsx`, aba `Base de Clientes`).

Grão: 1 linha = 1 cliente na rota do mês. A planilha é construída à mão pelo
time de Atacado, então o leitor desconfia do layout:

- a coluna de data traz o mês no NOME (`Datas Rota Setembro`): é localizada por
  padrão (`coluna_data_regex`), e o mês do arquivo vem do CONTEÚDO das datas;
- um arquivo tem de ter UM mês só e cada cliente UMA vez — senão aborta.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ..utils.config import CFG
from ..utils.log import abortar, contar, log
from ..utils.texto import chave_texto, digitos, texto
from . import cache, comum

_NUMERICAS = ["NET_SALES_25", "NET_SALES_26", "FREQ_25", "FREQ_26", "VOLUME_25", "VOLUME_26"]


def ler_arquivo(arq: Path) -> tuple[pd.DataFrame, dict]:
    cfg = CFG["fontes"]["rota"]
    try:
        bruto = pd.read_excel(arq, sheet_name=cfg["aba"], engine="calamine", dtype=object)
    except ValueError:
        abortar(f"{arq.name}: aba '{cfg['aba']}' nao encontrada.")
    bruto = bruto.dropna(how="all")

    padrao = re.compile(cfg["coluna_data_regex"])
    col_data = [c for c in bruto.columns if padrao.search(chave_texto(c))]
    if len(col_data) != 1:
        abortar(f"{arq.name}: esperava UMA coluna de data da rota (padrao '{cfg['coluna_data_regex']}'), "
                f"achei {len(col_data)}: {col_data}.\n  colunas: {list(bruto.columns)}")

    df = comum.mapear_colunas(bruto, cfg["colunas"], arq)
    df["DATA_ROTA"] = pd.to_datetime(bruto[col_data[0]], errors="coerce").dt.normalize()

    # código do vendedor (D-17): opcional na planilha; presente, tem de vir em TODAS as linhas
    df["COD_VENDEDOR"] = pd.NA
    for orig, novo in (cfg.get("colunas_opcionais") or {}).items():
        achada = [c for c in bruto.columns if chave_texto(c) == chave_texto(orig)]
        if achada:
            df[novo] = digitos(bruto[achada[0]])
            if df[novo].isna().any():
                abortar(f"{arq.name}: coluna '{achada[0]}' com {int(df[novo].isna().sum())} linha(s) vazia(s) ou nao numericas "
                        f"(linhas da planilha: {[int(i) + 2 for i in df.index[df[novo].isna()][:5]]}).")
    df["COD_VENDEDOR"] = df["COD_VENDEDOR"].astype("string")

    df["COD_CLIENTE"] = digitos(df["COD_CLIENTE"])
    for c in ("SUPERVISOR", "EXECUTIVO", "CANAL", "CIDADE"):
        df[c] = texto(df[c], maiuscula=(c != "SUPERVISOR"))
    for c in _NUMERICAS:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    ruins = df[df["COD_CLIENTE"].isna() | df["DATA_ROTA"].isna() | df["EXECUTIVO"].isna() | df["SUPERVISOR"].isna()]
    if len(ruins):
        abortar(f"{arq.name}: {len(ruins)} linha(s) sem cliente, data da rota, executivo ou supervisor "
                f"(primeiras linhas da planilha: {[int(i) + 2 for i in ruins.index[:5]]}).")

    df["ANO_MES"] = df["DATA_ROTA"].dt.strftime("%Y-%m")
    meses = sorted(df["ANO_MES"].unique())
    if len(meses) != 1:
        abortar(f"{arq.name}: as datas da rota cobrem {len(meses)} meses ({meses}); cada arquivo de rota tem de ser de UM mes.")

    rep = df[df.duplicated("COD_CLIENTE", keep=False)]
    if len(rep):
        abortar(f"{arq.name}: {rep['COD_CLIENTE'].nunique()} cliente(s) aparecem mais de uma vez na rota "
                f"(ex.: {sorted(rep['COD_CLIENTE'].unique())[:5]}). O grao e 1 linha por cliente.")

    fora = sorted(set(df["CANAL"].dropna()) - set(cfg.get("canais_esperados") or []))
    if fora:
        log(f"{arq.name}: canal fora do gabarito {fora} — entra como esta; conferir", "aviso")

    if df["COD_VENDEDOR"].notna().any():         # um vendedor = um executivo e um supervisor dentro do arquivo
        conf = df.groupby("COD_VENDEDOR")[["EXECUTIVO", "SUPERVISOR"]].nunique().max(axis=1)
        if (conf > 1).any():
            abortar(f"{arq.name}: codigo(s) de vendedor com mais de um executivo/supervisor: {sorted(conf[conf > 1].index)}.")

    df["ARQUIVO_ORIGEM"] = arq.name
    ordem = ["ANO_MES", "SUPERVISOR", "COD_VENDEDOR", "EXECUTIVO", "COD_CLIENTE", "CANAL", "DATA_ROTA", "CIDADE", *_NUMERICAS, "ARQUIVO_ORIGEM"]
    extra = {"mes": meses[0], "coluna_data": str(col_data[0]), "linhas": len(df), "com_codigo_vendedor": bool(df["COD_VENDEDOR"].notna().any()),
             "executivos": int(df["EXECUTIVO"].nunique()), "supervisores": int(df["SUPERVISOR"].nunique()),
             "datas_de_rota": int(df["DATA_ROTA"].nunique())}
    return df[ordem].reset_index(drop=True), extra


def carregar(forcar: bool = False) -> pd.DataFrame:
    arqs = comum.arquivos("rota")
    if not arqs:
        abortar(f"nenhuma rota em {CFG['fontes']['rota']['pasta']} (padroes {CFG['fontes']['rota']['padroes_aceitos']}).")
    partes, meses = [], {}
    for a in arqs:
        df, extra = cache.ler(a, ler_arquivo, forcar)
        contar(a.name, extra["linhas"], 0, mes=extra["mes"], executivos=extra["executivos"], datas_de_rota=extra["datas_de_rota"])
        meses[a.name] = [extra["mes"]]
        partes.append(df)
    comum.conferir_meses("rota", meses)
    return pd.concat(partes, ignore_index=True)
