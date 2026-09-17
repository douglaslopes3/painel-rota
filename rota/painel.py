# -*- coding: utf-8 -*-
"""Dados de UM painel (uma visão da hierarquia), prontos para o template.

Regra de ouro: o navegador NÃO calcula indicador. Para cada dia de rota e cada
escopo (dia · semana até o dia · mês até o dia) os números saem de
`metricas.kpis`, por vendedor; o JavaScript só soma vendedores (por supervisor
e no total) e divide. A lista de lojas leva o mínimo para o status do dia:
quando foi visitada e quando pediu.

Recorte físico (D-05): só entram lojas, vendedores e supervisores da visão. O que
é de outro escopo não existe no arquivo — `validar` confere.
"""
from __future__ import annotations

import pandas as pd

from . import metricas
from .utils.config import CFG
from .utils.log import abortar

COLS = ["ROTEIRO", "VISITADAS_NO_DIA", "FORA_DO_ROTEIRO", "VISITADAS_ATE_A_DATA", "COM_PEDIDO", "VISITA_E_PEDIDO", "SEM_CONTATO",
        "QTD_SOLICITADA", "TEL_ROTEIRO", "TEL_COM_PEDIDO", "TEL_QTD_SOLICITADA", "VISITAS_COM_PAR", "MINUTOS_SOMA"]
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


def _hhmm(ts) -> str | None:
    return None if pd.isna(ts) else f"{ts:%H:%M}"


def montar(m: dict[str, pd.DataFrame], lojas: pd.DataFrame, visao: dict, ate: pd.Timestamp, atualizado_em: str) -> dict:
    """`atualizado_em` = data/hora do arquivo de base mais recente (não o relógio): mesma base -> mesmo HTML, byte a byte."""
    fv, fp, cal, dv = m["FATO_VISITA"], m["FATO_PEDIDO"], m["DIM_CALENDARIO"], m["DIM_VENDEDOR"]
    mes = ate.strftime("%Y-%m")
    n3 = set(visao["N3_CODS"])
    L = lojas[(lojas["ANO_MES"] == mes) & lojas["N3_COD"].isin(n3)].copy()
    vend = dv[dv["N3_COD"].isin(n3)].sort_values(["N3_NOME", "N4_NOME", "N4_COD"]).reset_index(drop=True)
    sups = vend.drop_duplicates("N3_COD")[["N3_COD", "N3_NOME", "N3_ROTULO"]].reset_index(drop=True)
    i_sup = {c: i for i, c in enumerate(sups["N3_COD"])}
    i_vend = {c: i for i, c in enumerate(vend["N4_COD"])}
    clientes = set(L["COD_CLIENTE"])
    fv = fv[(fv["ANO_MES"] == mes) & (fv["COD_CLIENTE"].isin(clientes) | fv["COD_VENDEDOR_LOGIN"].isin(i_vend))]
    fp = fp[(fp["ANO_MES"] == mes) & fp["COD_CLIENTE"].isin(clientes)]

    c_mes = cal[cal["ANO_MES"] == mes]
    dias_rota = c_mes[c_mes["DIA_DE_ROTA"]].reset_index(drop=True)
    i_dia = {d: i for i, d in enumerate(dias_rota["DATA"])}
    agg = {"dia": [], "sem": [], "mes": []}
    horarios = []
    jd = metricas.jornada_dia(fv)
    for d, ini_sem in zip(dias_rota["DATA"], dias_rota["SEMANA_INICIO"]):
        escopos = {"dia": [d], "sem": pd.date_range(max(ini_sem, c_mes["DATA"].min()), d), "mes": pd.date_range(c_mes["DATA"].min(), d)}
        for e, dias in escopos.items():
            k = metricas.kpis(L, fv, fp, dias, por="COD_VENDEDOR").merge(metricas.jornada(fv, dias), on="COD_VENDEDOR", how="outer").fillna(0)
            tab = [[0] * len(COLS) for _ in vend.index]
            for r in k.itertuples(index=False):
                if r.COD_VENDEDOR in i_vend:
                    tab[i_vend[r.COD_VENDEDOR]] = [round(float(getattr(r, c)), 1) if c in ("QTD_SOLICITADA", "TEL_QTD_SOLICITADA", "MINUTOS_SOMA") else int(getattr(r, c)) for c in COLS]
            agg[e].append(tab)
        h = [[None, None] for _ in vend.index]
        for r in jd[jd["DATA"] == d].itertuples(index=False):
            if r.COD_VENDEDOR in i_vend:
                h[i_vend[r.COD_VENDEDOR]] = [_hhmm(r.PRIMEIRA_ENTRADA), _hhmm(r.ULTIMA_SAIDA)]
        horarios.append(h)

    vis = fv[fv["NA_ROTA"] & fv["CONTA_COMO_VISITA"]].groupby("COD_CLIENTE")
    vis = {c: [[int(r.DATA.day), None if pd.isna(r.MINUTOS_EM_LOJA) else round(float(r.MINUTOS_EM_LOJA), 1), int(r.N_CHECKINS)] for r in g.sort_values("DATA").itertuples()]
           for c, g in vis}
    ped = fp[fp["VALIDO"]].groupby(["COD_CLIENTE", "DATA_EMISSAO"]).agg(Q=("QTD_SOLICITADA", "sum"), N=("PEDIDO", "size")).reset_index()
    ped = {c: [[int(r.DATA_EMISSAO.day), round(float(r.Q), 1), int(r.N)] for r in g.itertuples()] for c, g in ped.groupby("COD_CLIENTE")}
    lj = [[r.COD_CLIENTE, None if pd.isna(r.NOME_CLIENTE) else r.NOME_CLIENTE.title(), (r.CIDADE or "").title(), i_vend[r.COD_VENDEDOR], i_dia[r.DATA_ROTA],
           int(bool(r.CONTROLA_VISITA)), vis.get(r.COD_CLIENTE, []), ped.get(r.COD_CLIENTE, [])]
          for r in L.sort_values(["DATA_ROTA", "COD_VENDEDOR", "NOME_CLIENTE"]).itertuples(index=False)]

    ci_fim = fv["DATA"].max() if len(fv) else pd.NaT
    pd_fim = m["FATO_PEDIDO"]["DATA_EMISSAO"].max()
    return {
        "meta": {"visao": visao["ROTULO"], "nome": visao["NOME"].title(), "nivel": visao["NIVEL"], "mes": f"{_MESES[ate.month - 1]}/{ate.year}",
                 "dados_ate": f"{ate:%Y-%m-%d}", "checkins_ate": None if pd.isna(ci_fim) else f"{ci_fim:%d/%m/%Y}", "pedidos_ate": f"{pd_fim:%d/%m/%Y}",
                 "atualizado_em": atualizado_em, "criterio_pedido": CFG["regras"]["pedido"]["criterio"],
                 "faixas": CFG["painel"]["faixas"], "rotulo_quantidade": CFG["painel"]["rotulo_quantidade"]},
        "dias": [{"d": f"{r.DATA:%Y-%m-%d}", "dm": int(r.DATA.day), "lab": f"{r.DATA:%d/%m}", "dow": r.DIA_SEMANA, "n": int(r.N_DIA_CICLO),
                  "futuro": bool(r.DATA > ate)} for r in dias_rota.itertuples(index=False)],
        "sups": [{"cod": r.N3_COD, "nome": r.N3_NOME.title()} for r in sups.itertuples(index=False)],
        "vend": [{"cod": r.N4_COD, "nome": r.N4_NOME.title(), "sup": i_sup[r.N3_COD], "app": bool(r.USA_APP), "cart": int(r.CLIENTES)} for r in vend.itertuples(index=False)],
        "cols": COLS, "agg": agg, "horarios": horarios,
        "lojas_cols": ["cod", "nome", "cidade", "vend", "dia", "pres", "vis[dia_do_mes, min, n_checkins]", "ped[dia_do_mes, qtd, n_pedidos]"], "lojas": lj,
    }


def validar(J: dict, lojas: pd.DataFrame, visao: dict) -> None:
    """O que o painel vai mostrar fecha consigo mesmo e com a LOJA_MES, e nada de fora da visão está no arquivo."""
    C = {c: i for i, c in enumerate(J["cols"])}
    esperado = set(lojas[lojas["N3_COD"].isin(set(visao["N3_CODS"])) & (lojas["ANO_MES"] == J["meta"]["dados_ate"][:7])]["COD_CLIENTE"])
    no_arquivo = {l[0] for l in J["lojas"]}
    if no_arquivo != esperado:
        abortar(f"painel '{visao['ROTULO']}': VAZAMENTO ou falta de lojas — {len(no_arquivo - esperado)} de fora da visao, {len(esperado - no_arquivo)} faltando.")
    for i, d in enumerate(J["dias"]):
        do_dia = [l for l in J["lojas"] if l[4] == i]
        pres = [l for l in do_dia if l[5]]
        conta = {"ROTEIRO": len(pres), "TEL_ROTEIRO": len(do_dia) - len(pres),
                 "VISITADAS_NO_DIA": sum(any(v[0] == d["dm"] for v in l[6]) for l in pres),
                 "COM_PEDIDO": sum(any(p[0] <= d["dm"] for p in l[7]) for l in pres)}
        if J["meta"]["criterio_pedido"] != "mes":
            conta.pop("COM_PEDIDO")
        for c, n in conta.items():
            soma = sum(v[C[c]] for v in J["agg"]["dia"][i])
            if soma != n:
                abortar(f"painel '{visao['ROTULO']}', {d['lab']}: {c} dos cards ({soma}) diferente da lista de lojas ({n}).")
    ult = max(i for i, d in enumerate(J["dias"]) if not d["futuro"]) if any(not d["futuro"] for d in J["dias"]) else 0
    for e in ("dia", "sem", "mes"):
        for c in ("ROTEIRO", "VISITADAS_NO_DIA", "COM_PEDIDO"):
            por_sup = [sum(v[C[c]] for v, vd in zip(J["agg"][e][ult], J["vend"]) if vd["sup"] == s) for s in range(len(J["sups"]))]
            if sum(por_sup) != sum(v[C[c]] for v in J["agg"][e][ult]):
                abortar(f"painel '{visao['ROTULO']}': soma dos supervisores diferente do total em {c} ({e}).")
