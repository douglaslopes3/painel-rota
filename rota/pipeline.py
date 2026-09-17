# -*- coding: utf-8 -*-
"""Orquestrador do Painel de Rota.

0 verificar -> 1 ingerir (bases -> staging, com as validações de leitura e a
reconciliação com a fonte) -> 2 modelar (staging -> fatos e dimensões) ->
3 calcular (indicadores + conferências de soma) -> gravar a camada curada, o
relatório de qualidade, o resumo e o manifesto. NADA é gravado na camada curada
antes de todas as validações passarem.
As etapas 4 renderizar, 5 validar o painel e 6 publicar entram nas Fases 3 e 4.

Qualquer falha termina em `PIPELINE ABORTADO`, exit code 1.
"""
from __future__ import annotations

import json
import time
from datetime import datetime

from . import manifesto, metricas, qualidade
from .extract import checkins, comum, estrutura, pedidos, rota_mensal
from .load import parquet
from .transform import modelo
from .utils import log as L
from .utils.config import CFG, PASTA_LOGS, RAIZ, preparar_pastas


def _verificar() -> dict:
    L.etapa_inicio("0 · VERIFICAR")
    L.log(f"projeto: {CFG['projeto']['nome']}  |  raiz: {RAIZ}")
    for f in manifesto.FONTES:
        arqs = comum.arquivos(f)
        if not arqs:
            L.abortar(f"fonte '{f}': nenhum arquivo em {CFG['fontes'][f]['pasta']} (padroes {CFG['fontes'][f]['padroes_aceitos']}).")
        L.log(f"fonte {f:<9} {len(arqs)} arquivo(s): {[a.name for a in arqs]}")
    dep = estrutura.arquivo()
    if not dep.exists():
        msg = (f"de-para de estrutura ausente ({CFG['fontes']['estrutura']['arquivo']}). "
               "Formato: aba Hierarquia, N1-N4 + LOGIN MERCANET (docs/05_DICIONARIO_DADOS.md).")
        if CFG["fontes"]["estrutura"].get("obrigatorio"):
            L.abortar(msg)
        L.log(msg + " Seguindo SEM estrutura: check-ins nao serao atribuidos a executivos.", "aviso")
    dif = manifesto.comparar()
    L.log(f"manifesto: {dif['motivo']}" + (f" -> {dif['novos'] + dif['alterados']}" if dif["mudou"] and (dif["novos"] or dif["alterados"]) else ""))
    horas = float(CFG["validacao"].get("base_velha_horas", 0) or 0)
    for f in ("checkins", "pedidos"):
        novo = max(a.stat().st_mtime for a in comum.arquivos(f))
        idade = (time.time() - novo) / 3600
        if horas and idade > horas:
            L.log(f"fonte {f}: o arquivo mais recente tem {idade:,.0f} h (limite {horas:,.0f} h) — a extracao do dia foi feita?", "aviso")
    L.etapa_fim("ok")
    return dif


def _ingerir(forcar: bool) -> dict:
    L.etapa_inicio("1 · INGERIR (bases -> staging)")
    rota = rota_mensal.carregar(forcar)
    ci = checkins.carregar(forcar)
    pd_ = pedidos.carregar(forcar)
    L.log(f"rota      {len(rota):>8,} clientes | meses {sorted(rota['ANO_MES'].unique())} | {rota['EXECUTIVO'].nunique()} executivos | {rota['SUPERVISOR'].nunique()} supervisores", "ok")
    L.log(f"check-ins {len(ci):>8,} eventos  | {ci['DATA_HORA'].min():%d/%m/%Y %H:%M} a {ci['DATA_HORA'].max():%d/%m/%Y %H:%M} | {ci['LOGIN'].nunique()} logins", "ok")
    L.log(f"pedidos   {len(pd_):>8,} pedidos  | emissao {pd_['DATA_EMISSAO'].min():%d/%m/%Y} a {pd_['DATA_EMISSAO'].max():%d/%m/%Y}", "ok")

    # chaves entre as bases: só MEDE nesta fase (a marcação por linha é da Fase 2)
    R, C, P = set(rota["COD_CLIENTE"]), set(ci["COD_CLIENTE"]), set(pd_["COD_CLIENTE"])
    chaves = {"clientes_rota": len(R), "clientes_checkin": len(C), "clientes_checkin_na_rota": len(C & R),
              "clientes_checkin_fora_da_rota": len(C - R), "eventos_fora_da_rota": int((~ci["COD_CLIENTE"].isin(R)).sum()),
              "clientes_pedido": len(P), "clientes_pedido_na_rota": len(P & R), "pedidos_de_clientes_da_rota": int(pd_["COD_CLIENTE"].isin(R).sum())}
    L.log(f"chave COD_CLIENTE: check-ins {chaves['clientes_checkin_na_rota']}/{chaves['clientes_checkin']} clientes na rota "
          f"({chaves['clientes_checkin_fora_da_rota']} fora, {chaves['eventos_fora_da_rota']} eventos) | "
          f"pedidos {chaves['pedidos_de_clientes_da_rota']} de {len(pd_)} sao de clientes da rota ({chaves['clientes_pedido_na_rota']} clientes)")
    meses_rota = set(rota["ANO_MES"])
    for nome, df in (("check-ins", ci), ("pedidos", pd_)):
        sem_rota = sorted(set(df["ANO_MES"]) - meses_rota)
        if sem_rota:
            L.log(f"{nome}: mes(es) {sem_rota} sem rota planejada em bases/Rota — esses meses nao terao planejado x realizado", "aviso")

    problemas: list[str] = []
    hier = None
    if estrutura.arquivo().exists():
        from .extract import cache
        df, x = cache.ler(estrutura.arquivo(), estrutura.ler_arquivo, forcar)
        hier = df
        L.contar(estrutura.arquivo().name, x["posicoes"], 0, **x)
        vis = estrutura.visoes(df)
        L.log(f"hierarquia: {x['posicoes']} posicoes (N4) | {x['n3']} supervisores | {x['n2']} gerentes | {x['n1']} head | "
              f"{x['com_login']} com login | {len(vis)} visoes possiveis", "ok")
        L.log("chave rota x hierarquia: " + ("CODIGO do vendedor" if rota["COD_VENDEDOR"].notna().all() else "NOME do executivo (a rota nao traz o codigo do vendedor)"))
        problemas = estrutura.conferir(df, rota, ci)
        for p in problemas:
            L.log("de-para: " + p, "aviso")
        if problemas and CFG["fontes"]["estrutura"].get("obrigatorio"):
            L.abortar(f"de-para de estrutura com {len(problemas)} problema(s) (listados acima). Corrija o arquivo e rode de novo.")
        if not problemas:
            L.log("de-para fechado com a rota e os check-ins", "ok")
    L.etapa_fim("ok", chaves=chaves, problemas_depara=len(problemas))
    return {"chaves": chaves, "problemas_depara": problemas, "_dados": (rota, ci, pd_, hier)}


def _modelar(rota, ci, pd_, hier) -> dict:
    L.etapa_inicio("2 · MODELAR (staging -> fatos e dimensoes)")
    m = modelo.construir(rota, ci, pd_, hier)
    modelo.integridade(m, ci, pd_, rota)
    fv, fp = m["FATO_VISITA"], m["FATO_PEDIDO"]
    L.log(f"visitas: {len(fv):,} (login x cliente x dia) | contam como visita {int(fv['CONTA_COMO_VISITA'].sum()):,} | a clientes da rota "
          f"{int(fv['NA_ROTA'].sum()):,} | no dia da rota {int((fv['NA_ROTA'] & fv['NO_DIA_DA_ROTA']).sum()):,} | com minutos {int(fv['MINUTOS_EM_LOJA'].notna().sum()):,}")
    L.log(f"pedidos: {len(fp):,} | de clientes da rota {int(fp['NA_ROTA'].sum()):,} | validos {int((fp['NA_ROTA'] & fp['VALIDO']).sum()):,} | "
          f"na janela do dia da rota {int((fp['NA_ROTA'] & fp['VALIDO'] & fp['NA_JANELA_DA_ROTA']).sum()):,}")
    L.etapa_fim("ok")
    return m


def _calcular(m: dict) -> dict:
    L.etapa_inicio("3 · CALCULAR (indicadores)")
    fv = m["FATO_VISITA"]
    lojas = metricas.loja_mes(m)
    diario = metricas.diario_vendedor(lojas, fv)
    ate = min(fv["DATA"].max(), m["FATO_PEDIDO"]["DATA_EMISSAO"].max())
    mes = ate.strftime("%Y-%m")
    dias_mes = [d for d in m["DIM_CALENDARIO"].query("ANO_MES == @mes")["DATA"] if d <= ate]
    total = metricas.kpis(lojas[lojas["ANO_MES"] == mes], fv, dias_mes).iloc[0]
    # conferências de soma: o total tem de ser a soma das partes, em qualquer corte da hierarquia
    soma_cols = ["ROTEIRO", "VISITADAS_NO_DIA", "COM_PEDIDO", "VISITA_E_PEDIDO", "SEM_CONTATO", "FORA_DO_ROTEIRO", "TEL_ROTEIRO", "TEL_COM_PEDIDO"]
    for por in ("COD_VENDEDOR", "N3_COD", "N2_COD", "N1_COD"):
        if lojas[por].isna().any():
            L.log(f"conferencia de soma por {por} pulada: ha lojas sem {por} (hierarquia incompleta)", "aviso")
            continue
        k = metricas.kpis(lojas[lojas["ANO_MES"] == mes], fv, dias_mes, por=por)
        for c in soma_cols:
            if int(k[c].sum()) != int(total[c]):
                L.abortar(f"soma por {por} nao fecha com o total em {c}: {int(k[c].sum())} x {int(total[c])}.")
        if abs(k["VALOR_PEDIDOS"].sum() - total["VALOR_PEDIDOS"]) > 0.01:
            L.abortar(f"soma por {por} nao fecha com o total em VALOR_PEDIDOS.")
    dia_mes = diario[(diario["DATA"].dt.strftime("%Y-%m") == mes) & (diario["DATA"] <= ate)]
    for c in ("ROTEIRO", "VISITADAS_NO_DIA", "COM_PEDIDO"):
        if int(dia_mes[c].sum()) != int(total[c]):
            L.abortar(f"DIARIO_VENDEDOR nao fecha com o total do mes em {c}: {int(dia_mes[c].sum())} x {int(total[c])}.")
    L.log("somas por vendedor, supervisor, gerente e head = total; diario = mes", "ok")
    ad = metricas.aderencia_mes(lojas, fv, ate).iloc[0]
    L.log(f"MES ATE {ate:%d/%m/%Y} | roteiro vencido {int(total['ROTEIRO']):,} | visitadas no dia da rota {int(total['VISITADAS_NO_DIA']):,} "
          f"({total['PCT_VISITA_NO_DIA']:.1f}%) | fora do roteiro {int(total['FORA_DO_ROTEIRO']):,} | ADERENCIA NO MES (D-03) "
          f"{int(ad['VISITADAS_NO_MES']):,}/{int(ad['ROTEIRO_VENCIDO']):,} = {ad['PCT_ADERENCIA_MES']:.1f}% | com pedido {int(total['COM_PEDIDO']):,} | "
          f"telefone com pedido {int(total['TEL_COM_PEDIDO']):,}/{int(total['TEL_ROTEIRO']):,}", "ok")
    L.etapa_fim("ok")
    return {"LOJA_MES": lojas, "DIARIO_VENDEDOR": diario, "_ate": ate, "_total": total.to_dict(), "_aderencia": ad.to_dict()}


def executar(forcar: bool = False) -> int:
    preparar_pastas()
    arq_log = L.abrir()
    L.titulo(f"PAINEL DE ROTA · execucao {L.EXECUCAO_ID}")
    dif = _verificar()
    info = _ingerir(forcar)
    rota, ci, pd_, hier = info.pop("_dados")
    m = _modelar(rota, ci, pd_, hier)
    calc = _calcular(m)

    L.etapa_inicio("GRAVAR (camada curada + qualidade)")
    for nome, df in {**m, "LOJA_MES": calc["LOJA_MES"], "DIARIO_VENDEDOR": calc["DIARIO_VENDEDOR"]}.items():
        if len(df.columns):
            parquet.salvar(df.assign(EXECUCAO_ID=L.EXECUCAO_ID), nome)
    if hier is not None:
        vis = estrutura.visoes(hier)
        parquet.salvar(vis.assign(N3_CODS=vis["N3_CODS"].map(";".join), EXECUCAO_ID=L.EXECUCAO_ID), "DIM_VISAO")
    info["qualidade"] = qualidade.gerar(m, calc["LOJA_MES"], L.contagens(), info["problemas_depara"])
    info["dados_ate"] = str(calc["_ate"].date())
    info["total_mes"] = {k: (round(float(v), 2) if v == v else None) for k, v in calc["_total"].items() if k != "GRUPO"}
    info["aderencia_mes"] = {k: (round(float(v), 2) if v == v else None) for k, v in calc["_aderencia"].items() if k != "GRUPO"}
    L.etapa_fim("ok")
    manifesto.gravar(L.EXECUCAO_ID, {"dados_ate": info["dados_ate"]})

    resumo = {"execucao": L.EXECUCAO_ID, "inicio": L.INICIO.isoformat(timespec="seconds"),
              "fim": datetime.now().isoformat(timespec="seconds"), "situacao": "ok",
              "manifesto": dif, "etapas": L.etapas(), "arquivos": L.contagens(), **info,
              "avisos": L.avisos(), "erros": L.erros()}
    alvo = PASTA_LOGS / f"resumo_{L.EXECUCAO_ID}.json"
    alvo.write_text(json.dumps(resumo, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    L.log("")
    L.log(f"SUCESSO — {len(L.avisos())} aviso(s). Log: {arq_log.name} | resumo: {alvo.name}", "ok")
    L.fechar()
    return 0
