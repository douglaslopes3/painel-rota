# -*- coding: utf-8 -*-
"""Modelo estrela do Painel de Rota (camada curated).

    DIM_CALENDARIO ─┐                        ┌─ DIM_VENDEDOR (posição N4 da hierarquia: N1..N3, login)
                    ├── FATO_ROTA_PLANEJADA ─┤
                    ├── FATO_VISITA ─────────┼─ DIM_CLIENTE
                    └── FATO_PEDIDO ─────────┘

Nada é descartado: check-in em cliente fora da rota, pedido de cliente fora da
rota e pedido cancelado ficam nas fatos, MARCADOS. O dono de uma loja é o
vendedor da ROTA daquele mês (é por ele que visita e pedido são atribuídos,
como no protótipo 2); o login de quem fez o check-in fica ao lado, para os
horários do dia e para a conferência "quem visitou × de quem é a loja".
"""
from __future__ import annotations

import pandas as pd

from ..utils.config import CFG
from ..utils.log import abortar, log
from . import calendario, visitas

_HIER = ["N1_COD", "N1_ROTULO", "N2_COD", "N2_ROTULO", "N3_COD", "N3_ROTULO", "N4_COD", "N4_ROTULO"]


def _ligar_hierarquia(rota: pd.DataFrame, hier: pd.DataFrame | None) -> pd.DataFrame:
    """Cada linha da rota ganha a posição (N4) e os superiores. Chave: código do
    vendedor (D-17); sem ele, o nome do executivo — desde que seja único."""
    if hier is None:
        for c in _HIER:
            rota[c] = pd.NA
        return rota
    if rota["COD_VENDEDOR"].notna().all():
        r = rota.merge(hier[_HIER], left_on="COD_VENDEDOR", right_on="N4_COD", how="left")
    else:
        unicos = hier.drop_duplicates("N4_NOME", keep=False)
        r = rota.merge(unicos[_HIER + ["N4_NOME"]], left_on="EXECUTIVO", right_on="N4_NOME", how="left").drop(columns="N4_NOME")
        r["COD_VENDEDOR"] = r["COD_VENDEDOR"].fillna(r["N4_COD"])
    sem = r[r["N4_COD"].isna()]
    if len(sem):
        msg = (f"{len(sem)} cliente(s) da rota sem posicao na hierarquia (vendedores: "
               f"{sorted(sem['EXECUTIVO'].unique())}) — ficam fora de todas as visoes.")
        if CFG["fontes"]["estrutura"].get("obrigatorio"):
            abortar(msg)
        log(msg, "aviso")
    return r


def _nomes(rota: pd.DataFrame, checkins: pd.DataFrame, pedidos: pd.DataFrame, clientes: pd.DataFrame | None) -> pd.DataFrame:
    """1 nome por cliente, pela ordem de `regras.nome_cliente.precedencia` (D-38): vale a primeira fonte que tiver o nome.
    Dentro do Mercanet (pedido e check-in) vale o registro mais recente; dentro da rota, o mês mais recente."""
    merc = pd.concat([pedidos[["COD_CLIENTE", "NOME_CLIENTE", "DATA_EMISSAO"]].rename(columns={"DATA_EMISSAO": "QUANDO"}),
                      checkins[["COD_CLIENTE", "NOME_CLIENTE", "DATA_HORA"]].rename(columns={"DATA_HORA": "QUANDO"})]).sort_values("QUANDO")
    fontes = {"clientes": clientes, "mercanet": merc,
              "rota": rota.sort_values("DATA_ROTA") if "NOME_CLIENTE" in rota.columns else None}
    ordem = list(CFG["regras"]["nome_cliente"]["precedencia"])
    invalidas = sorted(set(ordem) - set(fontes))
    if invalidas:
        raise ValueError(f"regras.nome_cliente.precedencia: fonte(s) invalida(s) {invalidas} (use {sorted(fontes)})")
    partes = [fontes[f][["COD_CLIENTE", "NOME_CLIENTE"]].dropna(subset=["NOME_CLIENTE"]).drop_duplicates("COD_CLIENTE", keep="last").assign(NOME_ORIGEM=f)
              for f in ordem if fontes[f] is not None]
    if not partes:
        return pd.DataFrame(columns=["COD_CLIENTE", "NOME_CLIENTE", "NOME_ORIGEM"])
    return pd.concat(partes, ignore_index=True).drop_duplicates("COD_CLIENTE", keep="first")


def construir(rota: pd.DataFrame, checkins: pd.DataFrame, pedidos: pd.DataFrame, hier: pd.DataFrame | None,
              clientes: pd.DataFrame | None = None) -> dict[str, pd.DataFrame]:
    regras = CFG["regras"]
    cal = calendario.gerar(rota)

    # ---------------------------------------------------------------- FATO_ROTA_PLANEJADA
    fr = _ligar_hierarquia(rota.drop(columns=["NOME_CLIENTE"], errors="ignore"), hier)
    fr["CONTROLA_VISITA"] = ~fr["CANAL"].isin(regras["canais_sem_controle_de_visita"])
    dono = fr[["ANO_MES", "COD_CLIENTE", "COD_VENDEDOR", "DATA_ROTA", "CONTROLA_VISITA"]]

    # ---------------------------------------------------------------- FATO_VISITA
    fv = visitas.gerar(checkins)
    fv = fv.merge(dono.rename(columns={"COD_VENDEDOR": "COD_VENDEDOR_ROTA"}), on=["ANO_MES", "COD_CLIENTE"], how="left")
    fv["NA_ROTA"] = fv["DATA_ROTA"].notna()
    fv["NO_DIA_DA_ROTA"] = fv["DATA"] == fv["DATA_ROTA"]
    if hier is not None:
        login = hier.dropna(subset=["LOGIN_MERCANET"]).set_index("LOGIN_MERCANET")["N4_COD"]
        fv["COD_VENDEDOR_LOGIN"] = fv["LOGIN"].map(login).astype("string")
    else:
        fv["COD_VENDEDOR_LOGIN"] = pd.array([pd.NA] * len(fv), dtype="string")
    fv = fv.merge(cal[["DATA", "DIA_UTIL"]], on="DATA", how="left")
    fv["DIA_UTIL"] = fv["DIA_UTIL"].fillna(fv["DATA"].dt.dayofweek < 5).astype(bool)
    fv["CONTROLA_VISITA"] = fv["CONTROLA_VISITA"].astype("boolean")

    # ---------------------------------------------------------------- FATO_PEDIDO
    fp = pedidos.merge(dono.rename(columns={"COD_VENDEDOR": "COD_VENDEDOR_ROTA"}), on=["ANO_MES", "COD_CLIENTE"], how="left")
    fp["NA_ROTA"] = fp["DATA_ROTA"].notna()
    fp["VALIDO"] = ~fp["SITUACAO"].isin(regras["pedido"]["situacoes_excluidas"])
    fp["VALOR"] = fp[regras["pedido"]["coluna_valor"]]
    dias = (fp["DATA_EMISSAO"] - fp["DATA_ROTA"]).dt.days
    fp["NA_JANELA_DA_ROTA"] = fp["NA_ROTA"] & dias.between(0, int(regras["pedido"]["janela_dias_corridos"]))
    fp["CONTROLA_VISITA"] = fp["CONTROLA_VISITA"].astype("boolean")

    # ---------------------------------------------------------------- dimensões
    nomes = _nomes(rota, checkins, pedidos, clientes)
    dc = pd.DataFrame({"COD_CLIENTE": sorted(set(rota["COD_CLIENTE"]) | set(checkins["COD_CLIENTE"]) | set(pedidos["COD_CLIENTE"]))})
    dc = dc.merge(nomes, on="COD_CLIENTE", how="left")
    ult_rota = rota.sort_values("ANO_MES").drop_duplicates("COD_CLIENTE", keep="last")[["COD_CLIENTE", "CIDADE"]]
    dc = dc.merge(ult_rota, on="COD_CLIENTE", how="left")
    dc["NA_ROTA"] = dc["COD_CLIENTE"].isin(set(rota["COD_CLIENTE"]))

    if hier is not None:
        dv = hier.copy()
        dv["USA_APP"] = dv["LOGIN_MERCANET"].isin(set(checkins["LOGIN"]))
        cart = fr.groupby("COD_VENDEDOR").agg(CLIENTES=("COD_CLIENTE", "nunique"), CLIENTES_COM_VISITA=("CONTROLA_VISITA", "sum")).reset_index()
        dv = dv.merge(cart, left_on="N4_COD", right_on="COD_VENDEDOR", how="left").drop(columns="COD_VENDEDOR")
        dv[["CLIENTES", "CLIENTES_COM_VISITA"]] = dv[["CLIENTES", "CLIENTES_COM_VISITA"]].fillna(0).astype(int)
    else:
        dv = pd.DataFrame()

    return {"DIM_CALENDARIO": cal, "DIM_CLIENTE": dc, "DIM_VENDEDOR": dv,
            "FATO_ROTA_PLANEJADA": fr, "FATO_VISITA": fv, "FATO_PEDIDO": fp}


def integridade(m: dict[str, pd.DataFrame], checkins: pd.DataFrame, pedidos: pd.DataFrame, rota: pd.DataFrame) -> None:
    """Nada entra ou some entre o staging e o modelo. Falha aborta."""
    fr, fv, fp = m["FATO_ROTA_PLANEJADA"], m["FATO_VISITA"], m["FATO_PEDIDO"]
    if len(fr) != len(rota) or fr.duplicated(["ANO_MES", "COD_CLIENTE"]).any():
        abortar(f"FATO_ROTA_PLANEJADA: {len(fr)} linhas x {len(rota)} na rota, ou cliente repetido no mes (a ligacao com a hierarquia multiplicou linhas).")
    if len(fp) != len(pedidos) or abs(fp["VALOR_PEDIDO"].sum() - pedidos["VALOR_PEDIDO"].sum()) > 0.01:
        abortar("FATO_PEDIDO nao fecha com o staging de pedidos (linhas ou valor).")
    if fv["N_CHECKINS"].sum() + fv["N_CHECKOUTS"].sum() != len(checkins) or fv.duplicated(["LOGIN", "COD_CLIENTE", "DATA"]).any():
        abortar("FATO_VISITA nao fecha com o staging de check-ins (eventos) ou tem visita repetida.")
    for nome, df, col in (("FATO_VISITA", fv, "COD_CLIENTE"), ("FATO_PEDIDO", fp, "COD_CLIENTE"), ("FATO_ROTA_PLANEJADA", fr, "COD_CLIENTE")):
        if not df[col].isin(set(m["DIM_CLIENTE"]["COD_CLIENTE"])).all():
            abortar(f"{nome}: cliente sem linha na DIM_CLIENTE.")
    log(f"integridade: rota {len(fr):,} | visitas {len(fv):,} (de {len(checkins):,} eventos) | pedidos {len(fp):,} | clientes {len(m['DIM_CLIENTE']):,} — fecha com o staging", "ok")
