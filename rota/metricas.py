# -*- coding: utf-8 -*-
"""Indicadores do Painel de Rota. Catálogo com a definição de cada um: docs/07_CATALOGO_METRICAS.md.

Tudo parte da LOJA_MES (1 linha = 1 loja na rota do mês), que já responde, para
o DIA DA ROTA de cada loja: foi visitada? teve pedido na janela? As visões de
dia, semana e mês são só escolhas de QUAIS dias de rota entram (`kpis`).

`kpis` é a única função que soma — o pipeline, os testes, a reconciliação com o
protótipo 2 e (na Fase 3) o painel chamam a mesma conta.
"""
from __future__ import annotations

import pandas as pd

from .utils.config import CFG

STATUS = {3: "visita + pedido", 2: "so visita", 1: "so pedido", 0: "sem contato"}


def loja_mes(m: dict[str, pd.DataFrame]) -> pd.DataFrame:
    fr, fv, fp = m["FATO_ROTA_PLANEJADA"], m["FATO_VISITA"], m["FATO_PEDIDO"]
    v = fv[fv["NA_ROTA"] & fv["CONTA_COMO_VISITA"]]
    ch = ["ANO_MES", "COD_CLIENTE"]

    no_dia = v[v["NO_DIA_DA_ROTA"]].groupby(ch).agg(MINUTOS_EM_LOJA=("MINUTOS_EM_LOJA", "max"), N_CHECKINS=("N_CHECKINS", "sum")).reset_index()
    no_dia["VISITA_NO_DIA"] = True
    no_mes = v.groupby(ch).agg(DIAS_VISITADOS=("DATA", "nunique"), PRIMEIRA_VISITA=("DATA", "min"), ULTIMA_VISITA=("DATA", "max")).reset_index()
    fora = v[~v["NO_DIA_DA_ROTA"]].groupby(ch).agg(DIAS_FORA_DO_ROTEIRO=("DATA", "nunique")).reset_index()

    p = fp[fp["NA_ROTA"] & fp["VALIDO"]]
    jan = p[p["NA_JANELA_DA_ROTA"]].groupby(ch).agg(PEDIDOS_JANELA=("PEDIDO", "size"), VALOR_JANELA=("VALOR", "sum"), QTD_JANELA=("QTD_SOLICITADA", "sum")).reset_index()
    mes = p.groupby(ch).agg(PEDIDOS_MES=("PEDIDO", "size"), VALOR_MES=("VALOR", "sum"), QTD_MES=("QTD_SOLICITADA", "sum")).reset_index()

    L = fr[["ANO_MES", "COD_CLIENTE", "COD_VENDEDOR", "EXECUTIVO", "SUPERVISOR", "N3_COD", "N2_COD", "N1_COD", "CANAL", "CONTROLA_VISITA",
            "DATA_ROTA", "CIDADE", "NET_SALES_26", "FREQ_26"]].copy()
    for t in (no_dia, no_mes, fora, jan, mes):
        L = L.merge(t, on=ch, how="left")
    L["VISITA_NO_DIA"] = L["VISITA_NO_DIA"].fillna(False).astype(bool) & L["CONTROLA_VISITA"]
    for c in ("N_CHECKINS", "DIAS_VISITADOS", "DIAS_FORA_DO_ROTEIRO", "PEDIDOS_JANELA", "PEDIDOS_MES"):
        L[c] = L[c].fillna(0).astype(int)
    for c in ("VALOR_JANELA", "QTD_JANELA", "VALOR_MES", "QTD_MES"):
        L[c] = L[c].fillna(0.0)
    L["PEDIDO_NA_JANELA"] = L["PEDIDOS_JANELA"] > 0
    L["STATUS"] = (L["VISITA_NO_DIA"].astype(int) * 2 + L["PEDIDO_NA_JANELA"].astype(int)).astype(int)
    return L.merge(m["DIM_CLIENTE"][["COD_CLIENTE", "NOME_CLIENTE"]], on="COD_CLIENTE", how="left")


def kpis(L: pd.DataFrame, fv: pd.DataFrame, fp: pd.DataFrame, dias, por: str | None = None, criterio: str | None = None) -> pd.DataFrame:
    """Indicadores das lojas cuja DATA DE ROTA cai em `dias` (um dia, a semana até o dia, o mês até o dia).
    `por` = coluna de agrupamento (COD_VENDEDOR, N3_COD…); None devolve uma linha só, com o total.

    `criterio` (padrão: `regras.pedido.criterio`, D-25) decide o que é "com pedido" e "contato":
      mes    -> a loja tem pedido válido NO MÊS até o último dia do período; "visitada" = visita em qualquer dia do mês
                até essa data (a mesma lógica da aderência, D-03);
      janela -> regra do protótipo 2: pedido no dia da rota ou até N dias corridos depois; "visitada" = no dia da rota."""
    criterio = criterio or CFG["regras"]["pedido"]["criterio"]
    dias = pd.DatetimeIndex(pd.to_datetime(list(dias)))
    ate = dias.max()
    L = L.assign(_G="TOTAL") if por is None else L.rename(columns={por: "_G"})
    P = L[L["DATA_ROTA"].isin(dias)].copy()

    if criterio == "mes":
        ped = fp[fp["NA_ROTA"] & fp["VALIDO"] & (fp["DATA_EMISSAO"] <= ate) & (fp["ANO_MES"] == ate.strftime("%Y-%m"))]
        ped = ped.groupby(["ANO_MES", "COD_CLIENTE"]).agg(_VAL=("VALOR", "sum"), _QTD=("QTD_SOLICITADA", "sum")).reset_index()
        P = P.merge(ped, on=["ANO_MES", "COD_CLIENTE"], how="left")
        P["_PED"] = P["_VAL"].notna()
        P["_VIS"] = (P["PRIMEIRA_VISITA"] <= ate) & P["CONTROLA_VISITA"]
    elif criterio == "janela":
        P["_PED"], P["_VAL"], P["_QTD"], P["_VIS"] = P["PEDIDO_NA_JANELA"], P["VALOR_JANELA"], P["QTD_JANELA"], P["VISITA_NO_DIA"]
    else:
        raise ValueError(f"regras.pedido.criterio invalido: {criterio!r} (use 'mes' ou 'janela')")
    P[["_VAL", "_QTD"]] = P[["_VAL", "_QTD"]].fillna(0.0)
    P["_VP"], P["_NADA"] = P["_VIS"] & P["_PED"], ~P["_VIS"] & ~P["_PED"]
    pres, tel = P[P["CONTROLA_VISITA"]], P[~P["CONTROLA_VISITA"]]

    k = pres.groupby("_G").agg(ROTEIRO=("COD_CLIENTE", "size"), VISITADAS_NO_DIA=("VISITA_NO_DIA", "sum"), VISITADAS_ATE_A_DATA=("_VIS", "sum"),
                               COM_PEDIDO=("_PED", "sum"), VISITA_E_PEDIDO=("_VP", "sum"), SEM_CONTATO=("_NADA", "sum"),
                               VALOR_PEDIDOS=("_VAL", "sum"), QTD_SOLICITADA=("_QTD", "sum"))
    kt = tel.groupby("_G").agg(TEL_ROTEIRO=("COD_CLIENTE", "size"), TEL_COM_PEDIDO=("_PED", "sum"),
                               TEL_VALOR_PEDIDOS=("_VAL", "sum"), TEL_QTD_SOLICITADA=("_QTD", "sum"))
    # fora do roteiro: loja (com controle de visita) visitada, dentro do período, num dia que NÃO é o da rota dela — conta 1 vez
    v = fv[fv["NA_ROTA"] & fv["CONTA_COMO_VISITA"] & ~fv["NO_DIA_DA_ROTA"] & fv["DATA"].isin(dias)]
    donos = L[L["CONTROLA_VISITA"]][["ANO_MES", "COD_CLIENTE", "_G"]]
    kf = v[["ANO_MES", "COD_CLIENTE"]].drop_duplicates().merge(donos, on=["ANO_MES", "COD_CLIENTE"]).groupby("_G").size().rename("FORA_DO_ROTEIRO")

    out = pd.concat([k, kt, kf], axis=1).fillna(0)
    for c in out.columns:
        if "VALOR" not in c and "QTD" not in c:
            out[c] = out[c].astype(int)
    out["NAO_ATENDIDAS"] = out["ROTEIRO"] - out["VISITADAS_NO_DIA"]
    out["TOTAL_VISITADAS"] = out["VISITADAS_NO_DIA"] + out["FORA_DO_ROTEIRO"]
    out["PCT_VISITA_NO_DIA"] = (100 * out["VISITADAS_NO_DIA"] / out["ROTEIRO"]).where(out["ROTEIRO"] > 0)
    out["PCT_ADERENCIA"] = (100 * out["VISITADAS_ATE_A_DATA"] / out["ROTEIRO"]).where(out["ROTEIRO"] > 0)
    out["PCT_POSITIVACAO"] = (100 * out["COM_PEDIDO"] / out["ROTEIRO"]).where(out["ROTEIRO"] > 0)
    return out.rename_axis(por or "GRUPO").reset_index()


def aderencia_mes(L: pd.DataFrame, fv: pd.DataFrame, ate, por: str | None = None) -> pd.DataFrame:
    """D-03 · Aderência no mês: das lojas com roteiro JÁ VENCIDO até `ate`, quantas
    receberam ao menos uma visita no mês (em qualquer dia, até `ate`)."""
    ate = pd.Timestamp(ate)
    mes = ate.strftime("%Y-%m")
    L = L.assign(_G="TOTAL") if por is None else L.rename(columns={por: "_G"})
    venc = L[(L["ANO_MES"] == mes) & L["CONTROLA_VISITA"] & (L["DATA_ROTA"] <= ate)]
    vis = fv[(fv["ANO_MES"] == mes) & fv["NA_ROTA"] & fv["CONTA_COMO_VISITA"] & (fv["DATA"] <= ate)]["COD_CLIENTE"].unique()
    venc = venc.assign(_V=venc["COD_CLIENTE"].isin(vis))
    out = venc.groupby("_G").agg(ROTEIRO_VENCIDO=("COD_CLIENTE", "size"), VISITADAS_NO_MES=("_V", "sum")).astype(int)
    out["PCT_ADERENCIA_MES"] = (100 * out["VISITADAS_NO_MES"] / out["ROTEIRO_VENCIDO"]).where(out["ROTEIRO_VENCIDO"] > 0)
    return out.rename_axis(por or "GRUPO").reset_index()


def jornada(fv: pd.DataFrame, dias) -> pd.DataFrame:
    """Jornada somável de um período, por vendedor (pelo LOGIN): nº de visitas com par e soma dos minutos."""
    v = fv[fv["CONTA_COMO_VISITA"] & fv["COD_VENDEDOR_LOGIN"].notna() & fv["DATA"].isin(pd.to_datetime(list(dias)))]
    return v.groupby("COD_VENDEDOR_LOGIN").agg(VISITAS_COM_PAR=("MINUTOS_EM_LOJA", "count"), MINUTOS_SOMA=("MINUTOS_EM_LOJA", "sum")).reset_index().rename(
        columns={"COD_VENDEDOR_LOGIN": "COD_VENDEDOR"})


def jornada_dia(fv: pd.DataFrame) -> pd.DataFrame:
    """Horários do dia por vendedor (pelo LOGIN de quem fez o check-in): 1ª entrada,
    última saída e tempo médio em loja das visitas com par."""
    v = fv[fv["CONTA_COMO_VISITA"] & fv["COD_VENDEDOR_LOGIN"].notna()]
    return v.groupby(["DATA", "COD_VENDEDOR_LOGIN"]).agg(
        VISITAS=("COD_CLIENTE", "nunique"), PRIMEIRA_ENTRADA=("PRIMEIRO_CHECKIN", "min"), ULTIMA_SAIDA=("ULTIMO_CHECKOUT", "max"),
        VISITAS_COM_PAR=("MINUTOS_EM_LOJA", "count"), TEMPO_MEDIO_LOJA_MIN=("MINUTOS_EM_LOJA", "mean")).reset_index().rename(columns={"COD_VENDEDOR_LOGIN": "COD_VENDEDOR"})


def diario_vendedor(L: pd.DataFrame, fv: pd.DataFrame, fp: pd.DataFrame) -> pd.DataFrame:
    """1 linha = dia de rota × vendedor: os KPIs do dia + a jornada. É a tabela que
    alimenta tabela e gráfico do painel na visão 'dia'."""
    partes = []
    for d in sorted(L["DATA_ROTA"].unique()):
        k = kpis(L, fv, fp, [d], por="COD_VENDEDOR")
        k.insert(0, "DATA", d)
        partes.append(k)
    out = pd.concat(partes, ignore_index=True)
    return out.merge(jornada_dia(fv), on=["DATA", "COD_VENDEDOR"], how="left")


SELLIN_COLS = ["LOJAS_SI", "ORCADO_SI", "META_SI", "FATURADO_SI", "CARTEIRA_SI", "LOJAS_FATURADAS_SI"]


def sellin(L: pd.DataFrame, si: dict | None, dias, meta_pct: float, com_carteira: bool, por: str = "COD_VENDEDOR") -> pd.DataFrame:
    """D-44 · Sell-in do BI, SÓ das lojas da rota (a loja é do vendedor da rota), num período (`dias`):
    orçado do mês, meta do período (= orçado × `meta_pct`/100), faturado no período (data de faturamento, com as devoluções
    como o BI traz), carteira em aberto HOJE (só quando `com_carteira`) e lojas com faturado líquido > 0 no período."""
    donos = L[["COD_CLIENTE", por]].drop_duplicates("COD_CLIENTE")
    base = donos.groupby(por).size().rename("LOJAS_SI").to_frame()
    if si is None:
        return base.assign(**{c: 0.0 for c in SELLIN_COLS[1:]}).rename_axis(por).reset_index()
    dias = pd.to_datetime(list(dias))
    # D-52: o orçado vem do arquivo de metas compartilhado ("meta", posto pelo pipeline) quando o mês está nele; senão, do BI
    orc = si["meta"] if "meta" in si else si["cliente"]
    cli = orc[["COD_CLIENTE", "ORCADO"]].merge(donos, on="COD_CLIENTE")                       # a loja é do vendedor da ROTA
    fat = si["faturado"].loc[si["faturado"]["DATA_FATURAMENTO"].isin(dias), ["COD_CLIENTE", "RECEITA"]].merge(donos, on="COD_CLIENTE")
    por_loja = fat.groupby([por, "COD_CLIENTE"])["RECEITA"].sum()
    out = base.join(cli.groupby(por)["ORCADO"].sum().rename("ORCADO_SI"))
    out["META_SI"] = out["ORCADO_SI"] * float(meta_pct) / 100
    out = out.join(fat.groupby(por)["RECEITA"].sum().rename("FATURADO_SI"))
    out = out.join(si["carteira"][["COD_CLIENTE", "CARTEIRA"]].merge(donos, on="COD_CLIENTE").groupby(por)["CARTEIRA"].sum().rename("CARTEIRA_SI") if com_carteira
                   else pd.Series(dtype=float, name="CARTEIRA_SI"))
    out = out.join((por_loja > 0).groupby(level=0).sum().rename("LOJAS_FATURADAS_SI"))
    return out.fillna(0.0)[SELLIN_COLS].rename_axis(por).reset_index()
