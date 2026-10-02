# -*- coding: utf-8 -*-
"""Hierarquia do Projeto Rota (D-49, 02/10/2026).

Duas fontes, ligadas pelo CÓDIGO do vendedor (N4):

- `bases/Estrutura/DePara_Estrutura_Rota.xlsx` (aba `Hierarquia`): 1 linha = 1 posição N4 do Projeto Rota com o
  LOGIN MERCANET (as bases não ligam o login do Mercanet ao vendedor). Desde a D-49 só o código N4, o login, o nome no
  Mercanet e o ENCERRADA EM (opcional, D-45) são lidos; as outras colunas continuam na planilha, sem uso.
- `../../bases compartilhadas/Hierarquia_AAAAMMDD.xlsx` (a de data mais recente no nome): hierarquia oficial comum ao DN
  e ao Gerencial, 1 linha por cliente, N1 a N4 com código e nome.

A cadeia N1–N3 de cada vendedor sai SÓ das linhas da base em que os clientes da rota estão com esse mesmo N4 (opção B
das decisões 15/15a): o vendedor que visita é o dono do cliente no painel. Cadeia ambígua aborta; cliente da rota com
outro N4 na base fica com quem visita e vai para a lista de exceção. Rótulo de cada pessoa = `código - nome`, o mesmo
das pastas de publicação do DN e do Gerencial.

Os painéis a gerar (visões) NÃO são digitados: saem da hierarquia — um por head, por gerente e por supervisor.
Nada aqui é inferido: login vazio fica vazio. `conferir()` lista o que não fecha com a rota e com os check-ins; quem
decide entre aviso e aborto é o pipeline (`fontes.estrutura.obrigatorio`).
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

import pandas as pd

from ..utils.config import CFG, caminho
from ..utils.log import abortar
from ..utils.texto import chave_texto, digitos, texto

NIVEIS = ("N1", "N2", "N3", "N4")
_CODIGOS = [f"{n}_COD" for n in NIVEIS]


def arquivo() -> Path:
    return caminho(CFG["fontes"]["estrutura"]["arquivo"])


# ------------------------------------------------------------------ hierarquia comum
def arquivo_hierarquia() -> Path | None:
    """A Hierarquia_AAAAMMDD.xlsx de data mais recente; arquivo do padrão sem data válida aborta (uma cópia de conflito do
    OneDrive não vira desempate silencioso). Sem pasta ou sem arquivo: None."""
    cfg = CFG["fontes"]["hierarquia"]
    pasta = caminho(cfg["pasta"])
    if not pasta.is_dir():
        return None
    rx = re.compile(cfg["data_regex"])
    datas: dict[datetime, Path] = {}
    fora: list[str] = []
    for a in sorted(pasta.glob(cfg["padrao"])):
        if a.name.startswith("~$"):
            continue
        m = rx.match(a.name)
        try:
            d = datetime.strptime(m.group(1), "%Y%m%d") if m else None
        except ValueError:
            d = None
        if d is None:
            fora.append(a.name)
        else:
            datas[d] = a
    if fora:
        abortar(f"arquivo(s) fora do padrao {cfg['data_regex']} em {pasta}: {fora}. "
                "Renomeie para Hierarquia_AAAAMMDD.xlsx ou tire da pasta.")
    return datas[max(datas)] if datas else None


def _nome_limpo(cod: pd.Series, nome: pd.Series) -> pd.Series:
    """Nome sem o "(código)" do fim e sem o "_" inicial, só quando o número entre parênteses é o código da linha."""
    partes = nome.str.extract(r"^_?(.+?)\s*\(\s*(\d+)\s*\)$")
    casa = (partes[0].notna() & (partes[1] == cod)).fillna(False)
    return nome.where(~casa, partes[0].str.strip())


def ler_hierarquia(arq: Path) -> tuple[pd.DataFrame, dict]:
    """1 linha por cliente: COD_CLIENTE e N1..N4 (código e nome limpo)."""
    cfg = CFG["fontes"]["hierarquia"]
    try:
        df = pd.read_excel(arq, sheet_name=cfg["aba"], engine="calamine", dtype=str)
    except ValueError:
        abortar(f"{arq.name}: aba '{cfg['aba']}' nao encontrada.")
    df.columns = [re.sub(r"\s+", " ", str(c)).strip() for c in df.columns]
    obrig = [cfg["coluna_cliente"]] + [c for cols in cfg["niveis"].values() for c in cols]
    faltam = [c for c in obrig if c not in df.columns]
    if faltam:
        abortar(f"{arq.name}: coluna(s) ausente(s): {faltam}\n  colunas da planilha: {list(df.columns)}")
    out = pd.DataFrame({"COD_CLIENTE": digitos(df[cfg["coluna_cliente"]])})
    for n, (c_cod, c_nome) in cfg["niveis"].items():
        out[f"{n}_COD"] = digitos(df[c_cod])
        out[f"{n}_NOME"] = _nome_limpo(out[f"{n}_COD"], texto(df[c_nome]))
    out = out.dropna(subset=["COD_CLIENTE"])
    rep = int(out["COD_CLIENTE"].duplicated().sum())
    if rep:
        abortar(f"{arq.name}: {rep} cliente(s) repetido(s); o grao esperado e 1 linha por cliente.")
    for n in NIVEIS:                                           # um nome por código, senão o rótulo seria escolhido
        conf = out.groupby(f"{n}_COD")[f"{n}_NOME"].nunique()
        if (conf > 1).any():
            abortar(f"{arq.name}: codigo(s) de {n} com mais de um nome: {sorted(conf[conf > 1].index)[:10]}.")
    return out.astype("string").reset_index(drop=True), {"clientes": len(out)}


# ------------------------------------------------------------------ de-para de login
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
        abortar(f"{arq.name}: coluna(s) do de-para ausente(s) ou ambigua(s): {faltam}\n  colunas da planilha: {list(norm.values())}")
    return df[list(ren)].rename(columns=ren)


def ler_arquivo(arq: Path) -> tuple[pd.DataFrame, dict]:
    """De-para N4 -> login do Mercanet: 1 linha por posição."""
    cfg = CFG["fontes"]["estrutura"]
    try:
        bruto = pd.read_excel(arq, sheet_name=cfg["aba"], engine="calamine", dtype=object)
    except ValueError:
        abortar(f"{arq.name}: aba '{cfg['aba']}' nao encontrada.")
    bruto = bruto.dropna(how="all")
    df = _mapear(bruto, cfg["colunas"], arq).reset_index(drop=True)
    # D-45: colunas opcionais (ENCERRADA_EM): entram se existirem; ausentes ficam vazias
    norm = {chave_texto(c): c for c in bruto.columns}
    for destino, aceitos in (cfg.get("colunas_opcionais") or {}).items():
        achou = [c for n, c in norm.items() if any(n == chave_texto(a) or n.endswith(" " + chave_texto(a)) for a in aceitos)]
        df[destino] = bruto[achou[0]].reset_index(drop=True) if len(achou) == 1 else pd.NA
    df["ENCERRADA_EM"] = pd.to_datetime(df["ENCERRADA_EM"], errors="coerce") if "ENCERRADA_EM" in df else pd.NaT
    df["N4_COD"] = digitos(df["N4_COD"])
    df["LOGIN_MERCANET"] = texto(df["LOGIN_MERCANET"])
    df["NOME_MERCANET"] = texto(df["NOME_MERCANET"], maiuscula=False)
    ruins = df[df["N4_COD"].isna()]
    if len(ruins):
        abortar(f"{arq.name}: {len(ruins)} linha(s) sem codigo de vendedor (N4) "
                f"(linhas da planilha: {[int(i) + 2 for i in ruins.index[:5]]}).")
    rep = df[df.duplicated("N4_COD", keep=False)]["N4_COD"].unique()
    if len(rep):
        abortar(f"{arq.name}: codigo de vendedor (N4) repetido: {sorted(rep)}. O grao e 1 linha por posicao.")
    df = df.astype({c: "string" for c in df.columns if c != "ENCERRADA_EM"})
    return df, {"posicoes": len(df), "com_login": int(df["LOGIN_MERCANET"].notna().sum()),
                "encerradas": int(df["ENCERRADA_EM"].notna().sum())}


# ------------------------------------------------------------------ montagem
def montar(depara: pd.DataFrame, base: pd.DataFrame, rota: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    """Hierarquia por posição (as do de-para) com a cadeia da base comum.

    Cadeia de um N4 = (N1, N2, N3) das linhas da base em que os clientes da rota (qualquer mês) com esse vendedor estão com o
    MESMO N4. Posição sem cliente da rota casado (nova ou encerrada): a cadeia de todas as linhas da base com esse N4. Mais
    de uma cadeia, ou nenhuma, aborta. Devolve (hierarquia, excecoes, contagens); exceção = cliente da rota cujo N4 na
    base difere do vendedor da rota (ou que não está na base): fica com quem visita."""
    r = rota.dropna(subset=["COD_VENDEDOR"])[["COD_CLIENTE", "COD_VENDEDOR"]].drop_duplicates()
    j = r.merge(base, on="COD_CLIENTE", how="left")
    casa = (j["N4_COD"] == j["COD_VENDEDOR"]).fillna(False).astype(bool)
    exc = j[~casa][["COD_CLIENTE", "COD_VENDEDOR", "N4_COD", "N4_NOME", "N3_COD", "N3_NOME", "N1_COD"]].rename(
        columns={"COD_VENDEDOR": "N4_ROTA", "N4_COD": "N4_BASE", "N4_NOME": "N4_NOME_BASE", "N3_COD": "N3_BASE",
                 "N3_NOME": "N3_NOME_BASE", "N1_COD": "N1_BASE"}).reset_index(drop=True)
    cad = ["N1_COD", "N2_COD", "N3_COD"]
    pela_rota = j[casa].drop_duplicates(["COD_VENDEDOR"] + cad)
    linhas, ruins = [], []
    for n4 in depara["N4_COD"]:
        ch = pela_rota[pela_rota["COD_VENDEDOR"] == n4][cad]
        if not len(ch):
            ch = base[base["N4_COD"] == n4][cad].drop_duplicates()
        if len(ch) != 1:
            ruins.append((n4, [tuple(x) for x in ch.itertuples(index=False)]))
            continue
        linhas.append({"N4_COD": n4, **ch.iloc[0].to_dict()})
    if ruins:
        abortar(f"hierarquia: vendedor(es) sem cadeia unica N1-N3 na base comum (sem linha ou mais de uma): {ruins[:10]}")
    h = pd.DataFrame(linhas, columns=["N4_COD"] + cad)
    for n in NIVEIS:
        nomes = base.drop_duplicates(f"{n}_COD").set_index(f"{n}_COD")[f"{n}_NOME"]
        h[f"{n}_NOME"] = h[f"{n}_COD"].map(nomes)
        h[f"{n}_ROTULO"] = h[f"{n}_COD"] + " - " + h[f"{n}_NOME"].fillna("")
    h = h.merge(depara, on="N4_COD", how="left", validate="1:1")
    h = h.astype({c: "string" for c in h.columns if c != "ENCERRADA_EM"})
    h["ATIVA"] = h["ENCERRADA_EM"].isna()
    extra = {"posicoes": len(h), "n1": int(h["N1_COD"].nunique()), "n2": int(h["N2_COD"].nunique()),
             "n3": int(h["N3_COD"].nunique()), "com_login": int(h["LOGIN_MERCANET"].notna().sum()),
             "encerradas": int((~h["ATIVA"]).sum()), "excecoes": len(exc)}
    return h, exc, extra


def visoes(hier: pd.DataFrame) -> pd.DataFrame:
    """Um painel por pessoa de N1, N2 e N3: nível, código, rótulo e os
    supervisores (N3) que compõem o recorte."""
    linhas = []
    for n in ("N1", "N2", "N3"):
        for cod, g in hier.groupby(f"{n}_COD", sort=True):
            linhas.append({"NIVEL": n, "COD": cod, "ROTULO": g[f"{n}_ROTULO"].iloc[0], "NOME": g[f"{n}_NOME"].iloc[0],
                           "N3_CODS": sorted(g["N3_COD"].unique()), "POSICOES": len(g)})
    return pd.DataFrame(linhas)


def avisos_nome(hier: pd.DataFrame, rota: pd.DataFrame) -> list[str]:
    """D-49 (R1): nome do vendedor diferente entre a rota e a base comum, com o mesmo código, é só aviso — a ligação é pelo
    código. No mês corrente o painel mostra o nome da base; no mês fechado, o `Executivo` da rota daquele mês (D-45)."""
    if not ("COD_VENDEDOR" in rota.columns and rota["COD_VENDEDOR"].notna().all()):
        return []
    nome_rota = rota.drop_duplicates("COD_VENDEDOR").set_index("COD_VENDEDOR")["EXECUTIVO"]
    nome_hier = hier.set_index("N4_COD")["N4_NOME"]
    div = sorted(c for c in set(nome_rota.index) & set(nome_hier.index)
                 if chave_texto(nome_rota[c]) != chave_texto(nome_hier[c]))
    if not div:
        return []
    return [f"vendedor(es) com NOME diferente entre a rota e a base comum (codigo igual, so aviso): "
            f"{[(c, nome_rota[c], nome_hier[c]) for c in div]}"]


def conferir(hier: pd.DataFrame, rota: pd.DataFrame, checkins: pd.DataFrame, mes_corrente: str | None = None) -> list[str]:
    """Problemas entre a hierarquia, a rota e os check-ins. Lista vazia = fechado.

    Chave rota ↔ hierarquia: o CÓDIGO do vendedor quando a rota traz a coluna
    (`COD_VENDEDOR`); senão o NOME do executivo — que só serve enquanto for único.
    D-49: nome diferente com o mesmo código deixou de ser problema (ver `avisos_nome`).

    D-45: com `mes_corrente`, a rota pode ter vários meses. Todo código da rota (qualquer mês) precisa de posição; nome, supervisor
    e "posição sem cliente na rota" são conferidos só na rota do mês corrente e só para posições ATIVAS (sem ENCERRADA_EM)."""
    p: list[str] = []
    todos = rota
    if mes_corrente is not None and "ANO_MES" in rota.columns:
        rota = rota[rota["ANO_MES"] == mes_corrente]
    ativa = hier["ATIVA"] if "ATIVA" in hier.columns else pd.Series(True, index=hier.index)
    hier_ativa = hier[ativa]
    por_codigo = "COD_VENDEDOR" in todos.columns and todos["COD_VENDEDOR"].notna().all()
    if por_codigo:
        na_rota, no_depara, o_que = set(rota["COD_VENDEDOR"]), set(hier["N4_COD"]), "codigo(s) de vendedor"
    else:
        na_rota, no_depara, o_que = set(rota["EXECUTIVO"].dropna()), set(hier["N4_NOME"].dropna()), "executivo(s)"
        rep = sorted(hier[hier.duplicated("N4_NOME", keep=False)]["N4_NOME"].unique())
        if rep:
            p.append(f"a rota nao traz o codigo do vendedor e o NOME nao e unico na hierarquia: {rep} "
                     f"({int(hier['N4_NOME'].isin(rep).sum())} posicoes) — os clientes desses nomes ficam sem posicao definida")
    todos_na_rota = set(todos["COD_VENDEDOR"]) if por_codigo else set(todos["EXECUTIVO"].dropna())
    if todos_na_rota - no_depara:
        p.append(f"{o_que} da rota sem posicao na hierarquia: {sorted(todos_na_rota - no_depara)}"
                 + (" (vendedor que saiu continua no de-para, com ENCERRADA EM)" if mes_corrente else ""))
    no_depara_ativa = set(hier_ativa["N4_COD"]) if por_codigo else set(hier_ativa["N4_NOME"].dropna())
    if no_depara_ativa - na_rota:
        p.append(f"{o_que} da hierarquia sem nenhum cliente na rota: {sorted(no_depara_ativa - na_rota)}")

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
    sem = hier_ativa[hier_ativa["LOGIN_MERCANET"].isna() & ~hier_ativa["N4_COD"].isin(aceitas)]
    if len(sem):
        p.append(f"{len(sem)} posicao(oes) sem LOGIN MERCANET (check-ins nao serao atribuidos): "
                 f"{[f'{c} {n}' for c, n in zip(sem['N4_COD'], sem['N4_NOME'])]}")
    orfaos = sorted(set(checkins["LOGIN"].dropna()) - set(com_login["LOGIN_MERCANET"]))
    if orfaos:
        p.append(f"{len(orfaos)} login(s) com check-in que nao estao na hierarquia: {orfaos}")
    return p
