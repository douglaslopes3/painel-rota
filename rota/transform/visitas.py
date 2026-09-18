# -*- coding: utf-8 -*-
"""Do evento bruto à visita (FATO_VISITA). Grão: 1 linha = login × cliente × dia.

Regras (D-02, conferidas contra os dados embutidos no protótipo 2 — 100% dos
948 cliente-dias e dos minutos):

- 1 visita = 1 cliente × dia com pelo menos um evento de `regras.visita.
  eventos_que_contam`. Vários check-ins no mesmo cliente e dia são UMA visita;
  a quantidade fica em N_CHECKINS.
- Dia listado em `regras.visita.dias_que_nao_contam` (D-32: sábado, domingo e
  feriado) continua na tabela, marcado em DIA_NAO_CONTA, mas não conta como visita.
- Minutos em loja = o MAIOR par check-in -> check-out do dia. Cada check-out
  pareia com o ÚLTIMO check-in registrado antes dele (desde o check-out
  anterior). Par não atravessa a meia-noite. Sem par, MINUTOS_EM_LOJA é nulo.
"""
from __future__ import annotations

import pandas as pd

from ..utils.config import CFG

_DOW = {"segunda": 0, "terca": 1, "quarta": 2, "quinta": 3, "sexta": 4, "sabado": 5, "domingo": 6}


def dia_nao_conta(datas: pd.Series) -> pd.Series:
    """D-32 · verdadeiro para as datas em que o evento não conta como visita, conforme `regras.visita.dias_que_nao_contam`."""
    lista = [str(x).strip().lower() for x in (CFG["regras"]["visita"].get("dias_que_nao_contam") or [])]
    invalidos = sorted(set(lista) - set(_DOW) - {"feriado"})
    if invalidos:
        raise ValueError(f"regras.visita.dias_que_nao_contam: valor(es) invalido(s) {invalidos} (use {sorted(_DOW)} ou 'feriado')")
    fora = datas.dt.dayofweek.isin([_DOW[x] for x in lista if x in _DOW])
    if "feriado" in lista:
        fora |= datas.isin(pd.to_datetime(CFG["calendario"].get("feriados") or []))
    return fora


def gerar(checkins: pd.DataFrame) -> pd.DataFrame:
    regras = CFG["regras"]["visita"]
    chave = ["LOGIN", "COD_CLIENTE", "DATA"]
    ev = checkins.sort_values(chave + ["DATA_HORA"], kind="stable").copy()
    ev["E_IN"] = ev["EVENTO"] == "CHECKIN"
    ev["E_OUT"] = ev["EVENTO"] == "CHECKOUT"

    # bloco = eventos entre um check-out e o seguinte (o check-out fecha o bloco)
    outs_antes = ev.groupby(chave)["E_OUT"].cumsum() - ev["E_OUT"].astype(int)
    ev["BLOCO"] = outs_antes
    ev["TS_IN"] = ev["DATA_HORA"].where(ev["E_IN"])
    ev["TS_OUT"] = ev["DATA_HORA"].where(ev["E_OUT"])
    blocos = ev.groupby(chave + ["BLOCO"]).agg(ULT_IN=("TS_IN", "max"), OUT=("TS_OUT", "max")).reset_index()
    blocos["MIN"] = (blocos["OUT"] - blocos["ULT_IN"]).dt.total_seconds() / 60
    pares = blocos.dropna(subset=["MIN"]).groupby(chave).agg(MINUTOS_EM_LOJA=("MIN", "max"), N_PARES=("MIN", "size")).reset_index()

    v = ev.groupby(chave).agg(ANO_MES=("ANO_MES", "first"), NOME_USUARIO=("NOME_USUARIO", "first"),
                              PRIMEIRO_EVENTO=("DATA_HORA", "min"), ULTIMO_EVENTO=("DATA_HORA", "max"),
                              PRIMEIRO_CHECKIN=("TS_IN", "min"), ULTIMO_CHECKOUT=("TS_OUT", "max"),
                              N_CHECKINS=("E_IN", "sum"), N_CHECKOUTS=("E_OUT", "sum")).reset_index()
    v = v.merge(pares, on=chave, how="left")
    v["N_PARES"] = v["N_PARES"].fillna(0).astype(int)
    v[["N_CHECKINS", "N_CHECKOUTS"]] = v[["N_CHECKINS", "N_CHECKOUTS"]].astype(int)

    conta = set(regras["eventos_que_contam"])
    v["CONTA_COMO_VISITA"] = ((v["N_CHECKINS"] > 0) & ("CHECKIN" in conta)) | ((v["N_CHECKOUTS"] > 0) & ("CHECKOUT" in conta))
    minimo = regras.get("minutos_minimos")
    if minimo is not None:                          # P-04: com duração mínima, visita sem par também não vale
        v["CONTA_COMO_VISITA"] &= v["MINUTOS_EM_LOJA"].fillna(-1) >= float(minimo)
    v["DIA_NAO_CONTA"] = dia_nao_conta(v["DATA"])     # D-32
    v["CONTA_COMO_VISITA"] &= ~v["DIA_NAO_CONTA"]
    return v
