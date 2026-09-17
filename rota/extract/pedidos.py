# -*- coding: utf-8 -*-
"""Leitor da consulta de pedidos do Mercanet (`bases/Pedidos/*.csv`).

Grão: 1 linha = 1 pedido, do canal Atacado INTEIRO (o recorte "cliente de rota"
é uma marca feita na transformação; nada é descartado aqui).

A última linha do arquivo é um rodapé com os totais da extração. Ela sai dos
dados e vira o GABARITO: a soma das linhas tem de bater com ela nas colunas de
`reconciliar`, senão o arquivo está truncado ou o formato numérico mudou — e o
pipeline aborta. Arquivo sem rodapé entra com aviso (não há como reconciliar).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..utils.config import CFG
from ..utils.log import abortar, contar, log
from ..utils.texto import digitos, numero_ptbr, texto
from . import cache, comum

_VALORES = ["VALOR_PEDIDO", "QTD_SOLICITADA", "VALOR_BRUTO", "VALOR_DESCONTO"]
_DATAS = ["DATA_EMISSAO", "DATA_ENTREGA_ESTIMADA", "DATA_FATURAMENTO"]


def ler_arquivo(arq: Path) -> tuple[pd.DataFrame, dict]:
    cfg = CFG["fontes"]["pedidos"]
    tol = float(CFG["validacao"]["tolerancia_reconciliacao"])
    try:
        bruto = pd.read_csv(arq, sep=cfg["separador"], encoding=cfg["encoding"], dtype=str, keep_default_na=False)
    except (UnicodeDecodeError, pd.errors.ParserError) as e:
        abortar(f"{arq.name}: arquivo ilegivel como CSV '{cfg['separador']}' / {cfg['encoding']} ({e}).")
    df = comum.mapear_colunas(bruto, cfg["colunas"], arq)
    lidas = len(df)

    # rodapé = linha(s) sem número de pedido
    sem_pedido = df["PEDIDO"].str.strip() == ""
    rodape = df[sem_pedido]
    df = df[~sem_pedido].copy()
    if len(rodape) > 1:
        abortar(f"{arq.name}: {len(rodape)} linhas sem numero de pedido; esperava no maximo 1 (o rodape de totais).")

    for c in _VALORES:
        df[c] = numero_ptbr(df[c])
    gabarito = {c: float(numero_ptbr(rodape[c]).iloc[0]) for c in cfg["reconciliar"]} if len(rodape) else {}
    for c, esperado in gabarito.items():
        soma = float(df[c].sum())
        if abs(soma - esperado) > tol:
            abortar(f"{arq.name}: {c} nao reconcilia com o rodape da extracao: soma das linhas {soma:,.2f} x rodape {esperado:,.2f} "
                    f"(diferenca {soma - esperado:,.2f}). Arquivo truncado ou formato numerico diferente do esperado.")
    if not gabarito:
        log(f"{arq.name}: sem rodape de totais — arquivo aceito SEM reconciliacao com a fonte", "aviso")

    df["PEDIDO"] = texto(df["PEDIDO"])
    df["COD_CLIENTE"] = digitos(df["COD_CLIENTE"])
    df["NOME_CLIENTE"] = texto(df["NOME_CLIENTE"])
    df["SITUACAO"] = texto(df["SITUACAO"], maiuscula=False)
    df["REPRESENTANTE"] = texto(df["REPRESENTANTE"])
    df["CIDADE"] = texto(df["CIDADE"])
    df["UF"] = texto(df["UF"])
    for c in _DATAS:
        df[c] = pd.to_datetime(df[c].str.strip().replace("", pd.NA), format=cfg["formato_data"], errors="coerce")

    ruins = df[df["DATA_EMISSAO"].isna() | df["COD_CLIENTE"].isna() | df["VALOR_PEDIDO"].isna()]
    if len(ruins):
        abortar(f"{arq.name}: {len(ruins)} pedido(s) sem data de emissao, cliente ou valor "
                f"(linhas do arquivo: {[int(i) + 2 for i in ruins.index[:5]]}).")
    rep = df[df.duplicated("PEDIDO", keep=False)]
    if len(rep):
        abortar(f"{arq.name}: {rep['PEDIDO'].nunique()} numero(s) de pedido repetido(s) (ex.: {sorted(rep['PEDIDO'].unique())[:5]}).")
    estranhas = sorted(set(df["SITUACAO"].dropna()) - set(cfg["situacoes_esperadas"]))
    if estranhas:
        log(f"{arq.name}: situacao de pedido fora do gabarito {estranhas} — entra como esta; decidir se conta como pedido valido", "aviso")

    df["ANO_MES"] = df["DATA_EMISSAO"].dt.strftime("%Y-%m")
    df["ARQUIVO_ORIGEM"] = arq.name
    ordem = ["ANO_MES", "PEDIDO", "COD_CLIENTE", "NOME_CLIENTE", *_DATAS, "SITUACAO", *_VALORES, "REPRESENTANTE", "CIDADE", "UF", "ARQUIVO_ORIGEM"]
    extra = {"lidas": lidas, "rodape": int(len(rodape)), "linhas": len(df), "meses": sorted(df["ANO_MES"].unique()),
             "inicio": str(df["DATA_EMISSAO"].min().date()), "fim": str(df["DATA_EMISSAO"].max().date()),
             "gabarito": gabarito, "somas": {c: round(float(df[c].sum()), 2) for c in cfg["reconciliar"]}}
    return df[ordem].reset_index(drop=True), extra


def carregar(forcar: bool = False) -> pd.DataFrame:
    arqs = comum.arquivos("pedidos")
    if not arqs:
        abortar(f"nenhum arquivo de pedidos em {CFG['fontes']['pedidos']['pasta']}.")
    partes, meses = [], {}
    for a in arqs:
        df, x = cache.ler(a, ler_arquivo, forcar)
        contar(a.name, x["lidas"], x["rodape"], rodape=x["rodape"], meses=x["meses"], inicio=x["inicio"], fim=x["fim"],
               reconciliado=bool(x["gabarito"]), somas=x["somas"])
        if x["gabarito"]:
            log(f"{a.name}: reconciliado com o rodape em {list(x['gabarito'])}", "ok")
        meses[a.name] = x["meses"]
        partes.append(df)
    comum.conferir_meses("pedidos", meses)
    todos = pd.concat(partes, ignore_index=True)
    rep = todos[todos.duplicated("PEDIDO", keep=False)]
    if len(rep):
        abortar(f"pedidos: {rep['PEDIDO'].nunique()} pedido(s) aparecem em mais de um arquivo (ex.: {sorted(rep['PEDIDO'].unique())[:5]}).")
    return todos
