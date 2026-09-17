# -*- coding: utf-8 -*-
"""DIM_CALENDARIO: um dia por linha, para cada mês que tem rota planejada.

Dia útil = segunda a sexta fora de `calendario.feriados` (parâmetro declarado no
config). Dia de rota e número do dia no ciclo vêm das DATAS DA ROTA do mês — o
planejado nunca é deduzido do calendário.
"""
from __future__ import annotations

import pandas as pd

from ..utils.config import CFG

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
        d["SEMANA_INICIO"] = d["DATA"] - pd.to_timedelta(d["DATA"].dt.dayofweek, unit="D")     # a segunda-feira da semana
        datas_rota = sorted(rota.loc[rota["ANO_MES"] == mes, "DATA_ROTA"].unique())
        d["DIA_DE_ROTA"] = d["DATA"].isin(datas_rota)
        ordem = {dt: i + 1 for i, dt in enumerate(datas_rota)}
        d["N_DIA_CICLO"] = d["DATA"].map(ordem).astype("Int64")             # 1..N nos dias de rota; vazio nos demais
        d["DIAS_NO_CICLO"] = len(datas_rota)
        partes.append(d)
    return pd.concat(partes, ignore_index=True)
