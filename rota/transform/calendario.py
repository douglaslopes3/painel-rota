# -*- coding: utf-8 -*-
"""DIM_CALENDARIO: um dia por linha, para cada mês que tem rota planejada.

Dia útil = segunda a sexta fora de `calendario.feriados` (parâmetro declarado no
config). Dia de rota e número do dia no ciclo vêm das DATAS DA ROTA do mês — o
planejado nunca é deduzido do calendário.

Semana (D-44): `calendario.semana` = `faixa_do_mes` (faixas de dias de
`semanas_do_mes`: S1 = dias 1 a 7 ...) ou `segunda` (da segunda-feira até o dia,
D-02). A mesma semana serve ao card "Semana" e à meta semanal do sell-in, cujos
pesos (`metas_sellin`) também são conferidos aqui.
"""
from __future__ import annotations

import pandas as pd

from ..utils.config import CFG
from ..utils.log import abortar

_DOW = ["seg", "ter", "qua", "qui", "sex", "sab", "dom"]


def gerar(rota: pd.DataFrame) -> pd.DataFrame:
    feriados = {pd.Timestamp(d) for d in (CFG.get("calendario", {}).get("feriados") or [])}
    partes = []
    for mes in sorted(rota["ANO_MES"].unique()):
        ini = pd.Timestamp(mes + "-01")
        d = pd.DataFrame({"DATA": pd.date_range(ini, ini + pd.offsets.MonthEnd(0), freq="D")})
        d["ANO_MES"] = mes
        d["DIA_SEMANA"] = d["DATA"].dt.dayofweek.map(lambda i: _DOW[i])
        d["DIA_UTIL"] = (d["DATA"].dt.dayofweek < 5) & ~d["DATA"].isin(feriados)
        if modo_semana() == "faixa_do_mes":
            faixa = d["DATA"].dt.day.map(lambda dia: next(f for f in faixas() if f["de"] <= dia <= f["ate"]))
            d["SEMANA_NOME"] = faixa.map(lambda f: str(f["nome"])).astype("string")
            d["SEMANA_INICIO"] = [ini.replace(day=f["de"]) for f in faixa]                    # 1º dia da faixa
            d["SEMANA_FIM"] = [min(ini.replace(day=min(f["ate"], ini.days_in_month)), d["DATA"].max()) for f in faixa]
        else:
            d["SEMANA_NOME"] = pd.Series(pd.NA, index=d.index, dtype="string")
            d["SEMANA_INICIO"] = d["DATA"] - pd.to_timedelta(d["DATA"].dt.dayofweek, unit="D")     # a segunda-feira da semana
            d["SEMANA_FIM"] = d["SEMANA_INICIO"] + pd.Timedelta(days=6)
        datas_rota = sorted(rota.loc[rota["ANO_MES"] == mes, "DATA_ROTA"].unique())
        d["DIA_DE_ROTA"] = d["DATA"].isin(datas_rota)
        ordem = {dt: i + 1 for i, dt in enumerate(datas_rota)}
        d["N_DIA_CICLO"] = d["DATA"].map(ordem).astype("Int64")             # 1..N nos dias de rota; vazio nos demais
        d["DIAS_NO_CICLO"] = len(datas_rota)
        partes.append(d)
    return pd.concat(partes, ignore_index=True)


def modo_semana() -> str:
    return (CFG.get("calendario", {}).get("semana") or "segunda").strip()


def faixas() -> list[dict]:
    return list(CFG.get("calendario", {}).get("semanas_do_mes") or [])


def pesos(mes: str) -> dict[str, float] | None:
    """Pesos (%) das semanas para o mês `AAAA-MM`: exceção do mês ou a lista geral. None = sem meta semanal (modo `segunda`)."""
    if modo_semana() != "faixa_do_mes":
        return None
    m = CFG.get("metas_sellin") or {}
    p = (m.get("pesos_por_mes") or {}).get(mes) or m.get("pesos")
    return {str(k): float(v) for k, v in p.items()} if p else None


def conferir_config() -> None:
    """Semana e pesos mal declarados ABORTAM: faixa com buraco ou sobreposição, peso que não soma 100, semana sem peso."""
    modo = modo_semana()
    if modo not in ("faixa_do_mes", "segunda"):
        abortar(f"calendario.semana invalido: {modo!r} (use faixa_do_mes ou segunda).")
    if modo == "segunda":
        return
    fx = faixas()
    esperado = 1
    for f in fx:
        if int(f["de"]) != esperado or int(f["ate"]) < int(f["de"]):
            abortar(f"calendario.semanas_do_mes: a faixa {f} deveria comecar no dia {esperado} (faixas continuas, sem buraco nem sobreposicao).")
        esperado = int(f["ate"]) + 1
    if not fx or esperado <= 31:
        abortar("calendario.semanas_do_mes: a ultima faixa tem de ir ate o dia 31 (cobrir qualquer mes).")
    nomes = [str(f["nome"]) for f in fx]
    m = CFG.get("metas_sellin") or {}
    for rot, p in [("metas_sellin.pesos", m.get("pesos"))] + [(f"metas_sellin.pesos_por_mes.{k}", v) for k, v in (m.get("pesos_por_mes") or {}).items()]:
        if not p:
            abortar(f"{rot}: pesos ausentes.")
        if sorted(map(str, p)) != sorted(nomes):
            abortar(f"{rot}: semanas {sorted(map(str, p))} diferentes das de calendario.semanas_do_mes {nomes}.")
        if abs(sum(float(v) for v in p.values()) - 100) > 1e-6:
            abortar(f"{rot}: os pesos somam {sum(float(v) for v in p.values()):g}%, tem de ser 100%.")
