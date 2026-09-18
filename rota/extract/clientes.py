# -*- coding: utf-8 -*-
"""Leitor do cadastro de nomes dos clientes do Projeto Rota (`bases/Estrutura/Clientes_Rota.xlsx`).

A rota mensal traz só o código do cliente, e o Mercanet só dá nome a quem teve
pedido ou check-in. Este arquivo, mantido pelo Douglas, dá nome a TODA loja da
rota (D-38): 1 linha = 1 cliente, código + nome.

Só lê e confere o formato. Qual nome vale quando há mais de um é regra de
negócio e vive no config (`regras.nome_cliente.precedencia`).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..utils.config import CFG, caminho
from ..utils.log import abortar
from ..utils.texto import digitos, texto
from .comum import mapear_colunas


def arquivo() -> Path:
    return caminho(CFG["fontes"]["clientes"]["arquivo"])


def ler_arquivo(arq: Path) -> tuple[pd.DataFrame, dict]:
    cfg = CFG["fontes"]["clientes"]
    aba = cfg.get("aba")
    try:
        bruto = pd.read_excel(arq, sheet_name=0 if aba is None else aba, engine="calamine", dtype=object)
    except ValueError:
        abortar(f"{arq.name}: aba '{aba}' nao encontrada.")
    df = mapear_colunas(bruto.dropna(how="all"), cfg["colunas"], arq).reset_index(drop=True)
    df["COD_CLIENTE"] = digitos(df["COD_CLIENTE"])
    df["NOME_CLIENTE"] = texto(df["NOME_CLIENTE"])

    ruins = df[df["COD_CLIENTE"].isna()]
    if len(ruins):
        abortar(f"{arq.name}: {len(ruins)} linha(s) sem codigo de cliente (linhas da planilha: {[int(i) + 2 for i in ruins.index[:5]]}).")
    rep = df[df.duplicated("COD_CLIENTE", keep=False)]
    if rep.groupby("COD_CLIENTE")["NOME_CLIENTE"].nunique(dropna=False).gt(1).any():
        cods = sorted(rep["COD_CLIENTE"].unique())[:5]
        abortar(f"{arq.name}: cliente repetido com nomes DIFERENTES (ex.: {cods}). O grao e 1 linha por cliente.")
    repetidas = int(df.duplicated("COD_CLIENTE").sum())
    df = df.drop_duplicates("COD_CLIENTE").reset_index(drop=True)
    df["ARQUIVO_ORIGEM"] = arq.name
    tam = df["NOME_CLIENTE"].str.len()
    maior = int(tam.max()) if tam.notna().any() else 0
    return df, {"clientes": len(df), "sem_nome": int(df["NOME_CLIENTE"].isna().sum()), "repetidas_iguais": repetidas,
                "maior_nome": maior, "nomes_no_tamanho_maximo": int((tam == maior).sum()) if maior else 0}
