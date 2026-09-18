# -*- coding: utf-8 -*-
"""Dados de cada painel (uma visão da hierarquia), prontos para o template.

Regra de ouro: o navegador NÃO calcula indicador. Para cada dia de rota e cada
escopo (dia · semana até o dia · mês até o dia) os números saem de
`metricas.kpis`, por vendedor; o JavaScript só soma vendedores (por supervisor
e no total) e divide. A lista de lojas leva o mínimo para o status do dia:
quando foi visitada e quando pediu.

`preparar` faz a conta UMA vez, para todos os vendedores; `montar` só RECORTA
para a visão. Recorte físico (D-05): no arquivo de uma visão só existem lojas,
vendedores e supervisores dela — `validar` confere, e `conferir_niveis` prova que
os painéis dos supervisores somam o do gerente e os dos gerentes somam o do head.
"""
from __future__ import annotations

import pandas as pd

from . import metricas
from .utils.config import CFG

COLS = ["ROTEIRO", "VISITADAS_NO_DIA", "FORA_DO_ROTEIRO", "VISITADAS_ATE_A_DATA", "COM_PEDIDO", "VISITA_E_PEDIDO", "SEM_CONTATO",
        "VALOR_PEDIDOS", "TEL_ROTEIRO", "TEL_COM_PEDIDO", "TEL_VALOR_PEDIDOS", "VISITAS_COM_PAR", "MINUTOS_SOMA"]      # D-35: valor no painel; quantidade fora
_DECIMAIS = {"VALOR_PEDIDOS", "TEL_VALOR_PEDIDOS", "MINUTOS_SOMA"}
_SOMAVEIS = [c for c in COLS if c not in _DECIMAIS]
_MESES = ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro", "outubro", "novembro", "dezembro"]


class PainelInvalido(Exception):
    """A visão não passou na validação: o arquivo dela não é gerado (as outras seguem)."""


def _hhmm(ts) -> str | None:
    return None if pd.isna(ts) else f"{ts:%H:%M}"


def preparar(m: dict[str, pd.DataFrame], lojas: pd.DataFrame, ate: pd.Timestamp) -> dict:
    """Tudo o que não depende da visão: dias de rota do mês, indicadores por vendedor × dia × escopo, jornada e, por loja,
    as visitas e os pedidos do mês."""
    fv, fp, cal = m["FATO_VISITA"], m["FATO_PEDIDO"], m["DIM_CALENDARIO"]
    mes = ate.strftime("%Y-%m")
    L = lojas[lojas["ANO_MES"] == mes]
    fv, fp = fv[fv["ANO_MES"] == mes], fp[fp["ANO_MES"] == mes]
    c_mes = cal[cal["ANO_MES"] == mes]
    dias_rota = c_mes[c_mes["DIA_DE_ROTA"]].reset_index(drop=True)
    ini_mes = c_mes["DATA"].min()

    agg = {"dia": [], "sem": [], "mes": []}
    for d, ini_sem in zip(dias_rota["DATA"], dias_rota["SEMANA_INICIO"]):
        for e, dias in {"dia": [d], "sem": pd.date_range(max(ini_sem, ini_mes), d), "mes": pd.date_range(ini_mes, d)}.items():
            k = metricas.kpis(L, fv, fp, dias, por="COD_VENDEDOR").merge(metricas.jornada(fv, dias), on="COD_VENDEDOR", how="outer")
            agg[e].append(k.set_index("COD_VENDEDOR")[COLS].fillna(0))

    vis = {c: [[int(r.DATA.day), None if pd.isna(r.MINUTOS_EM_LOJA) else round(float(r.MINUTOS_EM_LOJA), 1), int(r.N_CHECKINS)] for r in g.sort_values("DATA").itertuples()]
           for c, g in fv[fv["NA_ROTA"] & fv["CONTA_COMO_VISITA"]].groupby("COD_CLIENTE")}
    ped = fp[fp["NA_ROTA"] & fp["VALIDO"]].groupby(["COD_CLIENTE", "DATA_EMISSAO"]).agg(V=("VALOR", "sum"), N=("PEDIDO", "size")).reset_index()
    ped = {c: [[int(r.DATA_EMISSAO.day), round(float(r.V), 2), int(r.N)] for r in g.itertuples()] for c, g in ped.groupby("COD_CLIENTE")}
    return {"ate": ate, "mes": mes, "L": L, "dias_rota": dias_rota, "agg": agg, "jornada_dia": metricas.jornada_dia(fv), "vis": vis, "ped": ped,
            "checkins_ate": fv["DATA"].max() if len(fv) else pd.NaT, "pedidos_ate": fp["DATA_EMISSAO"].max() if len(fp) else pd.NaT}


def montar(P: dict, dv: pd.DataFrame, visao: dict, atualizado_em: str) -> dict:
    """`atualizado_em` = data/hora do arquivo de base mais recente (não o relógio): mesma base -> mesmo HTML, byte a byte."""
    ate, n3 = P["ate"], set(visao["N3_CODS"])
    L = P["L"][P["L"]["N3_COD"].isin(n3)]
    vend = dv[dv["N3_COD"].isin(n3)].sort_values(["N3_NOME", "N4_NOME", "N4_COD"]).reset_index(drop=True)
    sups = vend.drop_duplicates("N3_COD")[["N3_COD", "N3_NOME"]].reset_index(drop=True)
    i_sup = {c: i for i, c in enumerate(sups["N3_COD"])}
    i_vend = {c: i for i, c in enumerate(vend["N4_COD"])}
    i_dia = {d: i for i, d in enumerate(P["dias_rota"]["DATA"])}

    def tabela(k: pd.DataFrame) -> list[list]:
        k = k.reindex(list(i_vend)).fillna(0)
        return [[round(float(r[c]), 2) if c in _DECIMAIS else int(r[c]) for c in COLS] for r in k.to_dict("records")]

    agg = {e: [tabela(k) for k in P["agg"][e]] for e in ("dia", "sem", "mes")}
    horarios = []
    for d in P["dias_rota"]["DATA"]:
        h = [[None, None] for _ in vend.index]
        jd = P["jornada_dia"]
        for r in jd[jd["DATA"] == d].itertuples(index=False):
            if r.COD_VENDEDOR in i_vend:
                h[i_vend[r.COD_VENDEDOR]] = [_hhmm(r.PRIMEIRA_ENTRADA), _hhmm(r.ULTIMA_SAIDA)]
        horarios.append(h)
    lj = [[r.COD_CLIENTE, None if pd.isna(r.NOME_CLIENTE) else r.NOME_CLIENTE.title(), ("" if pd.isna(r.CIDADE) else r.CIDADE).title(), i_vend[r.COD_VENDEDOR],
           i_dia[r.DATA_ROTA], int(bool(r.CONTROLA_VISITA)), P["vis"].get(r.COD_CLIENTE, []), P["ped"].get(r.COD_CLIENTE, [])]
          for r in L.sort_values(["DATA_ROTA", "COD_VENDEDOR", "NOME_CLIENTE"]).itertuples(index=False)]

    ci, pe = P["checkins_ate"], P["pedidos_ate"]
    return {
        "meta": {"visao": visao["ROTULO"], "nome": visao["NOME"].title(), "nivel": visao["NIVEL"], "mes": f"{_MESES[ate.month - 1]}/{ate.year}",
                 "dados_ate": f"{ate:%Y-%m-%d}", "checkins_ate": None if pd.isna(ci) else f"{ci:%d/%m/%Y}", "pedidos_ate": None if pd.isna(pe) else f"{pe:%d/%m/%Y}",
                 "atualizado_em": atualizado_em, "criterio_pedido": CFG["regras"]["pedido"]["criterio"],
                 "faixas": CFG["painel"]["faixas"], "rotulo_valor": CFG["painel"]["rotulo_valor"],
                 "situacoes_excluidas": list(CFG["regras"]["pedido"]["situacoes_excluidas"]),
                 "dias_que_nao_contam": [{"sabado": "sábado", "terca": "terça"}.get(x, x) for x in (CFG["regras"]["visita"].get("dias_que_nao_contam") or [])]},
        "dias": [{"d": f"{r.DATA:%Y-%m-%d}", "dm": int(r.DATA.day), "lab": f"{r.DATA:%d/%m}", "dow": r.DIA_SEMANA, "n": int(r.N_DIA_CICLO),
                  "futuro": bool(r.DATA > ate)} for r in P["dias_rota"].itertuples(index=False)],
        "sups": [{"cod": r.N3_COD, "nome": r.N3_NOME.title()} for r in sups.itertuples(index=False)],
        "vend": [{"cod": r.N4_COD, "nome": r.N4_NOME.title(), "sup": i_sup[r.N3_COD], "app": bool(r.USA_APP), "cart": int(r.CLIENTES)} for r in vend.itertuples(index=False)],
        "cols": COLS, "agg": agg, "horarios": horarios,
        "lojas_cols": ["cod", "nome", "cidade", "vend", "dia", "pres", "vis[dia_do_mes, min, n_checkins]", "ped[dia_do_mes, valor, n_pedidos]"], "lojas": lj,
    }


def validar(J: dict, P: dict, dv: pd.DataFrame, visao: dict) -> None:
    """O painel fecha consigo mesmo e com a LOJA_MES, e NADA de fora da visão está no arquivo. Falha -> PainelInvalido."""
    C = {c: i for i, c in enumerate(J["cols"])}
    n3, rot = set(visao["N3_CODS"]), visao["ROTULO"]
    esperado = set(P["L"][P["L"]["N3_COD"].isin(n3)]["COD_CLIENTE"])
    no_arquivo = {l[0] for l in J["lojas"]}
    if no_arquivo != esperado:
        raise PainelInvalido(f"'{rot}': VAZAMENTO ou falta de lojas — {len(no_arquivo - esperado)} de fora da visao, {len(esperado - no_arquivo)} faltando.")
    if {v["cod"] for v in J["vend"]} != set(dv[dv["N3_COD"].isin(n3)]["N4_COD"]) or {s["cod"] for s in J["sups"]} != n3:
        raise PainelInvalido(f"'{rot}': vendedores ou supervisores do arquivo diferentes dos da visao.")
    if any(len(t) != len(J["vend"]) for e in J["agg"].values() for t in e) or any(len(h) != len(J["vend"]) for h in J["horarios"]):
        raise PainelInvalido(f"'{rot}': tabelas de indicadores com numero de linhas diferente do numero de vendedores.")
    for i, d in enumerate(J["dias"]):
        do_dia = [l for l in J["lojas"] if l[4] == i]
        pres = [l for l in do_dia if l[5]]
        conta = {"ROTEIRO": len(pres), "TEL_ROTEIRO": len(do_dia) - len(pres), "VISITADAS_NO_DIA": sum(any(v[0] == d["dm"] for v in l[6]) for l in pres)}
        if J["meta"]["criterio_pedido"] == "mes":
            conta["COM_PEDIDO"] = sum(any(p[0] <= d["dm"] for p in l[7]) for l in pres)
            conta["VISITADAS_ATE_A_DATA"] = sum(any(v[0] <= d["dm"] for v in l[6]) for l in pres)
        for c, n in conta.items():
            soma = sum(v[C[c]] for v in J["agg"]["dia"][i])
            if soma != n:
                raise PainelInvalido(f"'{rot}', {d['lab']}: {c} dos cards ({soma}) diferente da lista de lojas ({n}).")


def totais(J: dict) -> dict[str, int]:
    """Totais do mês no último dia com dados — o que `conferir_niveis` compara entre os painéis."""
    C = {c: i for i, c in enumerate(J["cols"])}
    passados = [i for i, d in enumerate(J["dias"]) if not d["futuro"]]
    ult = passados[-1] if passados else 0
    return {c: sum(v[C[c]] for v in J["agg"]["mes"][ult]) for c in _SOMAVEIS} | {"LOJAS": len(J["lojas"]), "VENDEDORES": len(J["vend"])}


def conferir_niveis(gerados: dict[str, dict], visoes: list[dict]) -> list[str]:
    """Os painéis de um nível somam o nível de cima: Σ supervisores = gerente, Σ gerentes = head. Devolve as diferenças."""
    erros = []
    por_cod = {(v["NIVEL"], v["COD"]): v for v in visoes}
    n3_tot = {v["COD"]: gerados[v["ROTULO"]] for v in visoes if v["NIVEL"] == "N3" and v["ROTULO"] in gerados}
    for (nivel, cod), v in por_cod.items():
        if nivel == "N3" or v["ROTULO"] not in gerados:
            continue
        faltam = [c for c in v["N3_CODS"] if c not in n3_tot]
        if faltam:
            erros.append(f"{v['ROTULO']}: nao da para conferir — painel(is) de supervisor ausente(s): {faltam}")
            continue
        for c, total in gerados[v["ROTULO"]].items():
            soma = sum(n3_tot[s][c] for s in v["N3_CODS"])
            if soma != total:
                erros.append(f"{v['ROTULO']}: {c} = {total}, mas a soma dos supervisores da {soma}")
    return erros
