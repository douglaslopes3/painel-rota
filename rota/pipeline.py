# -*- coding: utf-8 -*-
"""Orquestrador do Painel de Rota.

Fase 1 (fundação): 0 verificar -> 1 ingerir (bases -> staging, com todas as
validações de leitura e a reconciliação com a fonte) -> resumo + manifesto.
As etapas seguintes (2 modelar, 3 calcular, 4 renderizar, 5 validar,
6 publicar) entram nas próximas fases, nesta mesma função.

Qualquer falha termina em `PIPELINE ABORTADO`, exit code 1.
"""
from __future__ import annotations

import json
import time
from datetime import datetime

from . import manifesto
from .extract import checkins, comum, estrutura, pedidos, rota_mensal
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
               "Preencha docs/DePara_Estrutura_Rota_MODELO.xlsx e salve com esse nome (pendencia P-01).")
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
            L.log(f"{nome}: mes(es) {sem_rota} sem rota planejada em Bases/Rota — esses meses nao terao planejado x realizado", "aviso")

    problemas: list[str] = []
    if estrutura.arquivo().exists():
        from .extract import cache
        df, x = cache.ler(estrutura.arquivo(), estrutura.ler_arquivo, forcar)
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
    return {"chaves": chaves, "problemas_depara": problemas}


def executar(forcar: bool = False) -> int:
    preparar_pastas()
    arq_log = L.abrir()
    L.titulo(f"PAINEL DE ROTA · execucao {L.EXECUCAO_ID}")
    dif = _verificar()
    info = _ingerir(forcar)
    manifesto.gravar(L.EXECUCAO_ID)

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
