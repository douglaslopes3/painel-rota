# -*- coding: utf-8 -*-
"""Leitor do de-para de estrutura (`bases/Estrutura/DePara_Estrutura_Rota.xlsx`, aba `Hierarquia`).

As bases não ligam o login do Mercanet ao executivo da rota, nem dizem quem vê
o quê. Essa ligação é mantida pelo Douglas / time de Atacado neste arquivo, no
MESMO formato N1–N4 da `Hierarquia_Consolidada` do Dashboard Gerencial (D-16):

    1 linha = 1 posição de vendedor (N4) do Projeto Rota, com
    N1 head · N2 gerente · N3 sup./exec. · N4 vend./RCA (código, papel e nome)
    + LOGIN MERCANET / NOME MERCANET

Os painéis a gerar (visões) NÃO são digitados: saem da hierarquia — um por head,
por gerente e por supervisor —, como no Gerencial e no DN. O rótulo de cada
pessoa é `código - papel - nome`, o mesmo padrão das pastas de publicação.

Nada aqui é inferido: login vazio fica vazio. `conferir()` lista o que não fecha
com a rota e com os check-ins; quem decide entre aviso e aborto é o pipeline
(`fontes.estrutura.obrigatorio`).
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..utils.config import CFG, caminho
from ..utils.log import abortar
from ..utils.texto import chave_texto, digitos, texto

NIVEIS = ("N1", "N2", "N3", "N4")
_CODIGOS = [f"{n}_COD" for n in NIVEIS]


def arquivo() -> Path:
    return caminho(CFG["fontes"]["estrutura"]["arquivo"])


def _mapear(df: pd.DataFrame, colunas: dict[str, list[str]], arq: Path) -> pd.DataFrame:
    """`colunas`: nome no staging -> cabeçalhos aceitos. Os cabeçalhos da
    planilha têm quebra de linha e prefixos ("CRIAR NO BI\\n(N1)\\nHEAD"): vale
    quem TERMINA com um dos cabeçalhos aceitos, sem acento/caixa/quebra."""
    norm = {c: chave_texto(c) for c in df.columns}
    ren, faltam = {}, []
    for destino, aceitos in colunas.items():
        alvos = [chave_texto(a) for a in aceitos]
        achou = [c for c, n in norm.items() if any(n == a or n.endswith(" " + a) for a in alvos)]
        if len(achou) != 1:
            faltam.append(f"{destino} (aceitos {aceitos}; achei {achou})")
        else:
            ren[achou[0]] = destino
    if faltam:
        abortar(f"{arq.name}: coluna(s) da hierarquia ausente(s) ou ambigua(s): {faltam}\n  colunas da planilha: {list(norm.values())}")
    return df[list(ren)].rename(columns=ren)


def ler_arquivo(arq: Path) -> tuple[pd.DataFrame, dict]:
    cfg = CFG["fontes"]["estrutura"]
    try:
        bruto = pd.read_excel(arq, sheet_name=cfg["aba"], engine="calamine", dtype=object)
    except ValueError:
        abortar(f"{arq.name}: aba '{cfg['aba']}' nao encontrada.")
    df = _mapear(bruto.dropna(how="all"), cfg["colunas"], arq).reset_index(drop=True)

    for c in _CODIGOS:
        df[c] = digitos(df[c])
    for n in NIVEIS:
        df[f"{n}_PAPEL"] = texto(df[f"{n}_PAPEL"], maiuscula=False)
        df[f"{n}_NOME"] = texto(df[f"{n}_NOME"])
    df["PROJETO"] = texto(df["PROJETO"], maiuscula=False)
    df["LOGIN_MERCANET"] = texto(df["LOGIN_MERCANET"])
    df["NOME_MERCANET"] = texto(df["NOME_MERCANET"], maiuscula=False)

    ruins = df[df[_CODIGOS + ["N3_NOME", "N4_NOME"]].isna().any(axis=1)]
    if len(ruins):
        abortar(f"{arq.name}: {len(ruins)} linha(s) da hierarquia sem codigo de N1..N4 ou sem nome de N3/N4 "
                f"(linhas da planilha: {[int(i) + 2 for i in ruins.index[:5]]}).")
    rep = df[df.duplicated("N4_COD", keep=False)]["N4_COD"].unique()
    if len(rep):
        abortar(f"{arq.name}: codigo de vendedor (N4) repetido: {sorted(rep)}. O grao e 1 linha por posicao.")
    for n in ("N1", "N2", "N3"):                  # o mesmo código não pode ter dois rótulos nem dois pais
        cols = [f"{n}_PAPEL", f"{n}_NOME"] + ([f"N{int(n[1]) - 1}_COD"] if n != "N1" else [])
        conf = df.groupby(f"{n}_COD")[cols].nunique().max(axis=1)
        if (conf > 1).any():
            abortar(f"{arq.name}: codigo(s) de {n} com mais de um papel/nome/superior: {sorted(conf[conf > 1].index)}.")

    for n in NIVEIS:
        df[f"{n}_ROTULO"] = df[f"{n}_COD"] + " - " + df[f"{n}_PAPEL"].fillna("") + " - " + df[f"{n}_NOME"]
    df = df.astype({c: "string" for c in df.columns})
    extra = {"posicoes": len(df), "n1": int(df["N1_COD"].nunique()), "n2": int(df["N2_COD"].nunique()),
             "n3": int(df["N3_COD"].nunique()), "com_login": int(df["LOGIN_MERCANET"].notna().sum())}
    return df, extra


def visoes(hier: pd.DataFrame) -> pd.DataFrame:
    """Um painel por pessoa de N1, N2 e N3: nível, código, rótulo e os
    supervisores (N3) que compõem o recorte."""
    linhas = []
    for n in ("N1", "N2", "N3"):
        for cod, g in hier.groupby(f"{n}_COD", sort=True):
            linhas.append({"NIVEL": n, "COD": cod, "ROTULO": g[f"{n}_ROTULO"].iloc[0], "NOME": g[f"{n}_NOME"].iloc[0],
                           "N3_CODS": sorted(g["N3_COD"].unique()), "POSICOES": len(g)})
    return pd.DataFrame(linhas)


def conferir(hier: pd.DataFrame, rota: pd.DataFrame, checkins: pd.DataFrame) -> list[str]:
    """Problemas entre a hierarquia, a rota e os check-ins. Lista vazia = fechado.

    Chave rota ↔ hierarquia: o CÓDIGO do vendedor quando a rota traz a coluna
    (`COD_VENDEDOR`); senão o NOME do executivo — que só serve enquanto for único."""
    p: list[str] = []
    por_codigo = "COD_VENDEDOR" in rota.columns and rota["COD_VENDEDOR"].notna().all()
    if por_codigo:
        na_rota, no_depara, o_que = set(rota["COD_VENDEDOR"]), set(hier["N4_COD"]), "codigo(s) de vendedor"
        nome_rota = rota.drop_duplicates("COD_VENDEDOR").set_index("COD_VENDEDOR")["EXECUTIVO"]
        nome_hier = hier.set_index("N4_COD")["N4_NOME"]
        div = sorted(c for c in na_rota & no_depara if chave_texto(nome_rota[c]) != chave_texto(nome_hier[c]))
        if div:
            p.append(f"vendedor(es) com NOME diferente entre a rota e a hierarquia (codigo igual): "
                     f"{[(c, nome_rota[c], nome_hier[c]) for c in div]}")
    else:
        na_rota, no_depara, o_que = set(rota["EXECUTIVO"].dropna()), set(hier["N4_NOME"].dropna()), "executivo(s)"
        rep = sorted(hier[hier.duplicated("N4_NOME", keep=False)]["N4_NOME"].unique())
        if rep:
            p.append(f"a rota nao traz o codigo do vendedor e o NOME nao e unico na hierarquia: {rep} "
                     f"({int(hier['N4_NOME'].isin(rep).sum())} posicoes) — os clientes desses nomes ficam sem posicao definida")
    if na_rota - no_depara:
        p.append(f"{o_que} da rota sem posicao na hierarquia: {sorted(na_rota - no_depara)}")
    if no_depara - na_rota:
        p.append(f"{o_que} da hierarquia sem nenhum cliente na rota: {sorted(no_depara - na_rota)}")

    # coerência do supervisor: a rota traz só o primeiro nome; confere contra o N3 da posição do executivo
    chave_r, chave_h = ("COD_VENDEDOR", "N4_COD") if por_codigo else ("EXECUTIVO", "N4_NOME")
    unicos = hier.drop_duplicates(chave_h, keep=False)
    j = rota.drop_duplicates([chave_r, "SUPERVISOR"]).merge(unicos[[chave_h, "N3_NOME"]], left_on=chave_r, right_on=chave_h)
    ruim = j[[not chave_texto(n3).startswith(chave_texto(s)) for s, n3 in zip(j["SUPERVISOR"], j["N3_NOME"])]]
    if len(ruim):
        p.append("supervisor da rota nao bate com o N3 da hierarquia: "
                 f"{[(e, s, n3) for e, s, n3 in zip(ruim['EXECUTIVO'], ruim['SUPERVISOR'], ruim['N3_NOME'])]}")

    com_login = hier.dropna(subset=["LOGIN_MERCANET"])
    dup = sorted(com_login[com_login.duplicated("LOGIN_MERCANET", keep=False)]["LOGIN_MERCANET"].unique())
    if dup:
        p.append(f"login usado em mais de uma posicao: {dup}")
    aceitas = {str(c) for c in (CFG["fontes"]["estrutura"].get("posicoes_sem_login_aceitas") or [])}      # posto vago conhecido (D-39)
    sem = hier[hier["LOGIN_MERCANET"].isna() & ~hier["N4_COD"].isin(aceitas)]
    if len(sem):
        p.append(f"{len(sem)} posicao(oes) sem LOGIN MERCANET (check-ins nao serao atribuidos): "
                 f"{[f'{c} {n}' for c, n in zip(sem['N4_COD'], sem['N4_NOME'])]}")
    orfaos = sorted(set(checkins["LOGIN"].dropna()) - set(com_login["LOGIN_MERCANET"]))
    if orfaos:
        p.append(f"{len(orfaos)} login(s) com check-in que nao estao na hierarquia: {orfaos}")
    return p
