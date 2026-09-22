# -*- coding: utf-8 -*-
"""Leitor dos exports de sell-in do BI (`bases/SellIn/`, D-42 · P-16).

Três arquivos de nome fixo, extraídos juntos, com o mesmo filtro do BI (mês, Tipo
mercado e a lista de vendedores N4):

- `cliente`  1 linha = 1 cliente no mês: orçado, carteira, receita, LY e a hierarquia N1–N4 do BI;
- `carteira` 1 linha = 1 pedido em aberto;
- `faturado` 1 linha = 1 pedido × data de faturamento (faturamento parcial = várias linhas).

O sell-in COMPLEMENTA os pedidos do Mercanet, não os substitui: o número do
pedido do BI (`0111…`) não é o do Mercanet (`1160/5846`) — a ligação é só por
cliente. Nesta etapa só se lê e se confere; indicador de sell-in é decisão à parte.

O rodapé do export ("Total", linha em branco, "Filtros aplicados…") sai dos
dados: o Total vira o GABARITO e a soma das linhas tem de bater com ele, senão o
arquivo está truncado — e o pipeline aborta. Linha que não é dado nem rodapé
também aborta: nunca se ingere pela metade.
"""
from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from ..utils.config import CFG, caminho
from ..utils.log import abortar, contar, log
from ..utils.texto import digitos, texto
from . import cache
from .comum import mapear_colunas

_RE_ANO_MES = re.compile(r"^\d{4}/\d{2}$")
_RE_COD_N4 = re.compile(r"\((\d+)\)\s*$")


def arquivos() -> dict[str, Path]:
    """Os 3 arquivos do mês CORRENTE (raiz da pasta)."""
    cfg = CFG["fontes"]["sellin"]
    pasta = caminho(cfg["pasta"])
    return {k: pasta / a["arquivo"] for k, a in cfg["arquivos"].items()}


def pastas_meses_fechados() -> dict[str, Path]:
    """D-45: subpastas `AAAA-MM` da pasta do sell-in = meses fechados."""
    cfg = CFG["fontes"]["sellin"]
    pasta = caminho(cfg["pasta"])
    rx = re.compile(cfg.get("subpasta_mes_regex") or r"^\d{4}-\d{2}$")
    if not pasta.exists():
        return {}
    return {d.name: d for d in sorted(pasta.iterdir()) if d.is_dir() and rx.match(d.name)}


def todos_arquivos() -> list[Path]:
    """Raiz + subpastas de mês fechado (os que existem) — para o manifesto."""
    cfg = CFG["fontes"]["sellin"]
    out = [a for a in arquivos().values() if a.exists()]
    for d in pastas_meses_fechados().values():
        out += [d / a["arquivo"] for a in cfg["arquivos"].values() if (d / a["arquivo"]).exists()]
    return out


def ler_arquivo(arq: Path, tipo: str | None = None) -> tuple[pd.DataFrame, dict]:
    cfg = CFG["fontes"]["sellin"]
    tipo = tipo or next((k for k, a in cfg["arquivos"].items() if a["arquivo"].lower() == arq.name.lower()), None)
    if tipo is None:
        abortar(f"{arq.name}: arquivo de sell-in nao declarado em fontes.sellin.arquivos.")
    dcl = cfg["arquivos"][tipo]
    tol = float(CFG["validacao"]["tolerancia_reconciliacao"])
    try:
        bruto = pd.read_excel(arq, sheet_name=0, engine="calamine", dtype=object)
    except Exception as e:                                   # noqa: BLE001 — arquivo corrompido/aberto: mensagem clara e aborta
        abortar(f"{arq.name}: nao foi possivel ler a planilha ({e}).")
    df = mapear_colunas(bruto, dcl["colunas"], arq)
    lidas = len(df)

    # separa dado x rodape pela 1a coluna (Ano mes): "2026/09" = dado; "Total" = gabarito; vazio = linha em branco; "Filtros..." = filtro
    am = df["ANO_MES"].astype("string").str.strip()
    e_dado = am.str.match(_RE_ANO_MES).fillna(False)
    e_total = am.eq(cfg["rotulo_total"]).fillna(False)
    e_filtro = am.str.startswith(cfg["prefixo_filtros"]).fillna(False)
    e_branco = df.drop(columns="ANO_MES").isna().all(axis=1) & am.isna()
    estranhas = df[~(e_dado | e_total | e_filtro | e_branco)]
    if len(estranhas):
        abortar(f"{arq.name}: {len(estranhas)} linha(s) que nao sao dado nem rodape (linhas da planilha: "
                f"{[int(i) + 2 for i in estranhas.index[:5]]}; 'Ano mes' = {am[estranhas.index[:3]].tolist()}).")
    if int(e_total.sum()) > 1:
        abortar(f"{arq.name}: {int(e_total.sum())} linhas '{cfg['rotulo_total']}'; esperava no maximo 1.")
    filtros = " | ".join(am[e_filtro].str.replace(r"\s*\n\s*", " / ", regex=True).tolist())
    total = df[e_total]
    df = df[e_dado].copy()

    valores = dcl["valores"]
    for c in valores:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    gabarito = {c: float(pd.to_numeric(total[c], errors="coerce").fillna(0).iloc[0]) for c in valores} if len(total) else {}
    for c, esperado in gabarito.items():
        soma = float(df[c].sum())
        if abs(soma - esperado) > tol:
            abortar(f"{arq.name}: {c} nao reconcilia com a linha '{cfg['rotulo_total']}': soma das linhas {soma:,.2f} x total {esperado:,.2f} "
                    f"(diferenca {soma - esperado:,.2f}). Arquivo truncado?")
    if not gabarito:
        log(f"{arq.name}: sem linha '{cfg['rotulo_total']}' — arquivo aceito SEM reconciliacao com a fonte", "aviso")

    df["ANO_MES"] = df["ANO_MES"].astype("string").str.replace("/", "-", regex=False)
    df["COD_CLIENTE"] = digitos(df["COD_CLIENTE"])
    if "PEDIDO" in df:
        df["PEDIDO"] = texto(df["PEDIDO"])
    for c in ("DATA_PEDIDO", "DATA_FATURAMENTO"):
        if c in df:
            df[c] = pd.to_datetime(df[c], errors="coerce")
    for c in ("NOME_CLIENTE", "BANDEIRA", "CIDADE", "N1_BI", "N2_BI", "N3_BI", "N4_BI"):
        if c in df:
            df[c] = texto(df[c])
    if "N4_BI" in df:
        df["COD_VENDEDOR"] = df["N4_BI"].str.extract(_RE_COD_N4, expand=False).astype("string")

    obrig = [c for c in ("COD_CLIENTE", "PEDIDO", "DATA_PEDIDO", "DATA_FATURAMENTO", "COD_VENDEDOR") if c in df]
    ruins = df[df[obrig].isna().any(axis=1)]
    if len(ruins):
        abortar(f"{arq.name}: {len(ruins)} linha(s) sem {obrig} preenchido(s) (linhas da planilha: {[int(i) + 2 for i in ruins.index[:5]]}).")
    rep = df[df.duplicated(dcl["chave"], keep=False)]
    if len(rep):
        abortar(f"{arq.name}: {len(rep)} linha(s) com a chave {dcl['chave']} repetida — o grao declarado e 1 linha por {dcl['chave']} "
                f"(ex.: {rep[dcl['chave']].head(3).astype(str).values.tolist()}).")

    df["ARQUIVO_ORIGEM"] = arq.name
    extra = {"tipo": tipo, "lidas": lidas, "rodape": int(lidas - len(df)), "linhas": len(df), "meses": sorted(df["ANO_MES"].unique()),
             "gabarito": gabarito, "somas": {c: round(float(df[c].sum()), 2) for c in valores}, "filtros": filtros}
    return df.reset_index(drop=True), extra


def _carregar_pasta(rotulo: str, arqs: dict[str, Path], forcar: bool) -> tuple[dict[str, pd.DataFrame], list[str]]:
    out, meses, filtros = {}, {}, {}
    for tipo, a in arqs.items():
        df, x = cache.ler(a, ler_arquivo, forcar)
        contar(f"{rotulo}/{a.name}" if rotulo else a.name, x["lidas"], x["rodape"], rodape=x["rodape"], meses=x["meses"],
               reconciliado=bool(x["gabarito"]), somas=x["somas"])
        if x["gabarito"]:
            log(f"{rotulo + '/' if rotulo else ''}{a.name}: reconciliado com a linha Total em {list(x['gabarito'])}", "ok")
        out[tipo], meses[tipo], filtros[tipo] = df, x["meses"], x["filtros"]
    if len({tuple(m) for m in meses.values()}) > 1:
        log(f"sell-in {rotulo or 'corrente'}: os 3 arquivos nao cobrem os mesmos meses {meses} — foram extraidos com filtros diferentes?", "aviso")
    if len(set(filtros.values())) > 1:
        log(f"sell-in {rotulo or 'corrente'}: os 3 arquivos tem 'Filtros aplicados' DIFERENTES — conferir a extracao no BI", "aviso")
    return out, sorted(set(m for ms in meses.values() for m in ms))


def carregar(forcar: bool = False) -> dict[str, dict[str, pd.DataFrame]] | None:
    """Sell-in por mês: {`AAAA-MM`: {cliente, carteira, faturado}}. A raiz da pasta é o mês corrente; cada subpasta `AAAA-MM`
    é um mês fechado (D-45) e o mês do conteúdo tem de ser o da subpasta. None = raiz ausente e fonte não obrigatória."""
    cfg = CFG["fontes"]["sellin"]
    arqs = arquivos()
    faltam = [a.name for a in arqs.values() if not a.exists()]
    if faltam:
        msg = f"sell-in: arquivo(s) ausente(s) em {cfg['pasta']}: {faltam} — sell-in fora desta execucao."
        if cfg.get("obrigatorio"):
            abortar(msg)
        log(msg, "aviso")
        return None
    por_mes: dict[str, dict[str, pd.DataFrame]] = {}
    corrente, meses = _carregar_pasta("", arqs, forcar)
    if len(meses) != 1:
        abortar(f"sell-in: a raiz de {cfg['pasta']} deveria ter UM mes (o corrente), achei {meses}.")
    por_mes[meses[0]] = corrente
    for nome, d in pastas_meses_fechados().items():
        sub = {k: d / a["arquivo"] for k, a in cfg["arquivos"].items()}
        faltam = [a.name for a in sub.values() if not a.exists()]
        if faltam:
            abortar(f"sell-in: subpasta {nome} incompleta — falta(m) {faltam} (mes fechado precisa dos 3 arquivos).")
        dados, ms = _carregar_pasta(nome, sub, forcar)
        if ms != [nome]:
            abortar(f"sell-in: a subpasta {nome} tem dados do(s) mes(es) {ms}; o mes da subpasta tem de ser o mes do conteudo.")
        if nome in por_mes:
            abortar(f"sell-in: o mes {nome} esta na raiz E na subpasta {nome} — o mes corrente fica so na raiz.")
        por_mes[nome] = dados
    return por_mes


def conferir(si: dict[str, pd.DataFrame]) -> tuple[list[str], pd.DataFrame]:
    """Soma por cliente de cada detalhe (carteira, faturado) contra a coluna do arquivo `cliente`. Devolve os avisos e a lista
    de clientes com diferença (para a qualidade). Diferença não aborta: exports tirados em momentos diferentes divergem."""
    tol = float(CFG["validacao"]["tolerancia_reconciliacao"])
    cli = si["cliente"].set_index("COD_CLIENTE")
    avisos, difs = [], []
    for c in CFG["fontes"]["sellin"]["conferir"]:
        det = si[c["detalhe"]].groupby("COD_CLIENTE")[c["coluna"]].sum()
        base = cli[c["contra"]].fillna(0)
        fora = sorted(set(det.index) - set(base.index))
        if fora:
            avisos.append(f"{len(fora)} cliente(s) no arquivo {c['detalhe']} que nao estao no arquivo cliente (ex.: {fora[:5]})")
        j = pd.concat([base, det], axis=1, keys=["CLIENTE", "DETALHE"]).fillna(0)
        d = j[(j["DETALHE"] - j["CLIENTE"]).abs() > tol]
        if len(d):
            avisos.append(f"{c['detalhe']} x cliente: {len(d)} cliente(s) com {c['contra']} diferente (soma da diferenca "
                          f"{(d['DETALHE'] - d['CLIENTE']).sum():,.2f}) — exports em momentos diferentes?")
            difs.append(d.reset_index().rename(columns={"index": "COD_CLIENTE"}).assign(CONFERENCIA=f"{c['detalhe']}.{c['coluna']} x cliente.{c['contra']}"))
    lista = pd.concat(difs, ignore_index=True) if difs else pd.DataFrame(columns=["COD_CLIENTE", "CLIENTE", "DETALHE", "CONFERENCIA"])
    return avisos, lista


def cruzar(si: dict[str, pd.DataFrame], rota: pd.DataFrame, hier: pd.DataFrame | None) -> dict:
    """Chaves do sell-in contra a rota e a hierarquia — só MEDE (nada entra em indicador nesta etapa). Devolve contagens e as
    listas que a qualidade grava: clientes do BI fora da rota, lojas da rota fora do BI, vendedor do BI diferente do da rota."""
    cli = si["cliente"]
    R = set(rota["COD_CLIENTE"])
    fora = cli[~cli["COD_CLIENTE"].isin(R)]
    sem_bi = rota[~rota["COD_CLIENTE"].isin(set(cli["COD_CLIENTE"]))]
    j = rota[["COD_CLIENTE", "COD_VENDEDOR"]].merge(cli[["COD_CLIENTE", "COD_VENDEDOR", "N4_BI"]], on="COD_CLIENTE", suffixes=("_ROTA", "_BI"))
    div = j[j["COD_VENDEDOR_ROTA"].astype("string") != j["COD_VENDEDOR_BI"]]
    vend_fora = sorted(set(cli["COD_VENDEDOR"]) - set(hier["N4_COD"].astype(str))) if hier is not None else []
    cols = ["COD_CLIENTE", "NOME_CLIENTE", "N4_BI", "ORCADO", "CARTEIRA", "RECEITA"]
    return {"clientes_bi": len(cli), "lojas_rota": len(R), "lojas_rota_no_bi": len(R & set(cli["COD_CLIENTE"])),
            "clientes_bi_fora_da_rota": len(fora), "receita_fora_da_rota": round(float(fora["RECEITA"].sum()), 2),
            "vendedor_diferente": len(div), "vendedores_bi_fora_do_depara": vend_fora,
            "_fora_da_rota": fora[cols], "_rota_sem_bi": sem_bi[["COD_CLIENTE", "COD_VENDEDOR", "EXECUTIVO", "CANAL"]],
            "_vendedor_diferente": div}
