# -*- coding: utf-8 -*-
"""Orquestrador do Painel de Rota.

0 verificar -> 1 ingerir (bases -> staging, com as validações de leitura e a
reconciliação com a fonte) -> 2 modelar (staging -> fatos e dimensões) ->
3 calcular (indicadores + conferências de soma) -> gravar a camada curada, o
relatório de qualidade, o resumo e o manifesto. NADA é gravado na camada curada
antes de todas as validações passarem.
4 renderizar + 5 validar os painéis — um por visão da hierarquia, em pasta LOCAL.
6 publicar (`rota/publicar.py`): por padrão só LISTA o plano; `--ensaio` copia para pasta local; `--publicar` só copia para o
destino real com `publicacao.liberada: true` no config (D-28).

Qualquer falha termina em `PIPELINE ABORTADO`, exit code 1.
"""
from __future__ import annotations

import json
import time
from datetime import datetime

from . import manifesto, metricas, painel, publicar, qualidade, render
from .extract import checkins, clientes, comum, estrutura, pedidos, rota_mensal, sellin
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
    cli = None                                     # D-38: cadastro de nomes das lojas da rota
    obrig = bool(CFG["fontes"]["clientes"].get("obrigatorio"))
    if clientes.arquivo().exists():
        from .extract import cache
        cli, x = cache.ler(clientes.arquivo(), clientes.ler_arquivo, forcar)
        L.contar(clientes.arquivo().name, x["clientes"], 0, **x)
        com_nome = set(cli.dropna(subset=["NOME_CLIENTE"])["COD_CLIENTE"])
        sem = sorted(R - com_nome)
        L.log(f"nomes de clientes: {x['clientes']:,} no cadastro | {len(R & com_nome):,} de {len(R):,} lojas da rota com nome | "
              f"{len(com_nome - R):,} do cadastro fora da rota | maior nome {x['maior_nome']} caracteres ({x['nomes_no_tamanho_maximo']:,} nesse tamanho)", "ok")
        if sem:
            msg = f"{len(sem)} loja(s) da rota sem nome em {clientes.arquivo().name} (ex.: {sem[:5]}) — aparecem com o nome das outras fontes ou so pelo codigo."
            if obrig:
                L.abortar(msg)
            L.log(msg, "aviso")
    else:
        msg = f"cadastro de nomes ausente ({CFG['fontes']['clientes']['arquivo']}): o nome da loja vem so de pedido/check-in."
        if obrig:
            L.abortar(msg)
        L.log(msg, "aviso")
    si = sellin.carregar(forcar)                   # D-42: sell-in do BI — só lido e conferido; nenhum indicador usa ainda (P-16)
    cruz = None
    if si is not None:
        avisos, difs = sellin.conferir(si)
        for a in avisos:
            L.log("sell-in: " + a, "aviso")
        cruz = sellin.cruzar(si, rota, hier)
        cruz["_diferencas"] = difs
        L.log(f"sell-in: {cruz['clientes_bi']:,} clientes no BI | {cruz['lojas_rota_no_bi']:,} de {cruz['lojas_rota']:,} lojas da rota no BI | "
              f"{cruz['clientes_bi_fora_da_rota']:,} clientes do BI fora da rota (receita {cruz['receita_fora_da_rota']:,.2f}) | "
              f"vendedor do BI diferente do da rota em {cruz['vendedor_diferente']:,} loja(s)", "ok")
        if cruz["vendedores_bi_fora_do_depara"]:
            L.log(f"sell-in: vendedor(es) do BI fora do de-para {cruz['vendedores_bi_fora_do_depara']} — ficam so no relatorio de qualidade", "aviso")
    L.etapa_fim("ok", chaves=chaves, problemas_depara=len(problemas))
    return {"chaves": chaves, "problemas_depara": problemas, "sellin": {k: v for k, v in (cruz or {}).items() if not k.startswith("_")},
            "_sellin": cruz, "_dados": (rota, ci, pd_, hier, cli)}


def _modelar(rota, ci, pd_, hier, cli=None) -> dict:
    L.etapa_inicio("2 · MODELAR (staging -> fatos e dimensoes)")
    m = modelo.construir(rota, ci, pd_, hier, cli)
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
    fv, fp = m["FATO_VISITA"], m["FATO_PEDIDO"]
    lojas = metricas.loja_mes(m)
    diario = metricas.diario_vendedor(lojas, fv, fp)
    ate = min(fv["DATA"].max(), m["FATO_PEDIDO"]["DATA_EMISSAO"].max())
    mes = ate.strftime("%Y-%m")
    dias_mes = [d for d in m["DIM_CALENDARIO"].query("ANO_MES == @mes")["DATA"] if d <= ate]
    total = metricas.kpis(lojas[lojas["ANO_MES"] == mes], fv, fp, dias_mes).iloc[0]
    # conferências de soma: o total tem de ser a soma das partes, em qualquer corte da hierarquia
    soma_cols = ["ROTEIRO", "VISITADAS_NO_DIA", "COM_PEDIDO", "VISITA_E_PEDIDO", "SEM_CONTATO", "FORA_DO_ROTEIRO", "TEL_ROTEIRO", "TEL_COM_PEDIDO"]
    for por in ("COD_VENDEDOR", "N3_COD", "N2_COD", "N1_COD"):
        if lojas[por].isna().any():
            L.log(f"conferencia de soma por {por} pulada: ha lojas sem {por} (hierarquia incompleta)", "aviso")
            continue
        k = metricas.kpis(lojas[lojas["ANO_MES"] == mes], fv, fp, dias_mes, por=por)
        for c in soma_cols:
            if int(k[c].sum()) != int(total[c]):
                L.abortar(f"soma por {por} nao fecha com o total em {c}: {int(k[c].sum())} x {int(total[c])}.")
        if abs(k["VALOR_PEDIDOS"].sum() - total["VALOR_PEDIDOS"]) > 0.01:
            L.abortar(f"soma por {por} nao fecha com o total em VALOR_PEDIDOS.")
    dia_mes = diario[(diario["DATA"].dt.strftime("%Y-%m") == mes) & (diario["DATA"] <= ate)]
    for c in ("ROTEIRO", "VISITADAS_NO_DIA"):                  # COM_PEDIDO no criterio "mes" depende da data final: nao se soma dia a dia
        if int(dia_mes[c].sum()) != int(total[c]):
            L.abortar(f"DIARIO_VENDEDOR nao fecha com o total do mes em {c}: {int(dia_mes[c].sum())} x {int(total[c])}.")
    L.log("somas por vendedor, supervisor, gerente e head = total; diario = mes", "ok")
    ad = metricas.aderencia_mes(lojas, fv, ate).iloc[0]
    if CFG["regras"]["pedido"]["criterio"] == "mes" and int(ad["VISITADAS_NO_MES"]) != int(total["VISITADAS_ATE_A_DATA"]):
        L.abortar(f"aderencia do mes ({int(ad['VISITADAS_NO_MES'])}) nao fecha com kpis.VISITADAS_ATE_A_DATA ({int(total['VISITADAS_ATE_A_DATA'])}).")
    L.log(f"MES ATE {ate:%d/%m/%Y} | roteiro vencido {int(total['ROTEIRO']):,} | visitadas no dia da rota {int(total['VISITADAS_NO_DIA']):,} "
          f"({total['PCT_VISITA_NO_DIA']:.1f}%) | fora do roteiro {int(total['FORA_DO_ROTEIRO']):,} | ADERENCIA NO MES (D-03) "
          f"{int(ad['VISITADAS_NO_MES']):,}/{int(ad['ROTEIRO_VENCIDO']):,} = {ad['PCT_ADERENCIA_MES']:.1f}% | com pedido ({CFG['regras']['pedido']['criterio']}) {int(total['COM_PEDIDO']):,} | "
          f"telefone com pedido {int(total['TEL_COM_PEDIDO']):,}/{int(total['TEL_ROTEIRO']):,}", "ok")
    L.etapa_fim("ok")
    return {"LOJA_MES": lojas, "DIARIO_VENDEDOR": diario, "_ate": ate, "_total": total.to_dict(), "_aderencia": ad.to_dict()}


def _painel(m: dict, calc: dict, hier) -> dict:
    """Um HTML por visão da hierarquia, em pasta LOCAL (D-28: nada é publicado até a validação final). A falha de uma visão
    não derruba as outras: o arquivo dela não sai, o erro fica no log e a execução termina com exit code 1."""
    L.etapa_inicio("4-5 · RENDERIZAR E VALIDAR OS PAINEIS")
    if hier is None:
        L.log("sem hierarquia nao ha visoes: paineis nao gerados", "aviso")
        L.etapa_fim("pulada")
        return {"paineis": {}, "falhas": []}
    # carimbo do painel = arquivo de base mais recente (nao o relogio): mesma base -> mesmo HTML, byte a byte
    mais_novo = max(a.stat().st_mtime for f in ("checkins", "pedidos") for a in comum.arquivos(f))
    atualizado_em = datetime.fromtimestamp(mais_novo).strftime("%d/%m/%Y %H:%M")
    niveis = CFG["painel"].get("niveis_gerados") or ["N1", "N2", "N3"]
    todas = estrutura.visoes(hier).to_dict("records")
    visoes = [v for v in todas if v["NIVEL"] in niveis]
    P = painel.preparar(m, calc["LOJA_MES"], calc["_ate"])
    dv = m["DIM_VENDEDOR"]
    gerados, totais, falhas, nomes = {}, {}, [], set()
    for v in visoes:
        nome = f"Painel_Rota_{v['NIVEL']}_{render.slug(v['ROTULO'])}.html"
        try:
            J = painel.montar(P, dv, v, atualizado_em)
            painel.validar(J, P, dv, v)
            arq = render.gerar(J, nome)
        except painel.PainelInvalido as e:
            falhas.append(str(e))
            L.log(f"painel NAO gerado — {e}", "erro")
            continue
        nomes.add(nome)
        totais[v["ROTULO"]] = painel.totais(J)
        gerados[v["ROTULO"]] = {"arquivo": str(arq), "kb": round(arq.stat().st_size / 1024, 1), **totais[v["ROTULO"]]}
        L.log(f"{v['NIVEL']} {v['ROTULO']:<46} {len(J['vend']):>2} vendedores {len(J['lojas']):>5,} lojas -> {arq.name} ({arq.stat().st_size / 1024:,.0f} KB)", "ok")
    for e in painel.conferir_niveis(totais, visoes):
        falhas.append(e)
        L.log("soma entre niveis — " + e, "erro")
    if not falhas and len(niveis) > 1:
        L.log(f"{len(gerados)} paineis: zero vazamento, cards = lista de lojas em todos os dias, supervisores somam o gerente e gerentes somam o head", "ok")
    for velho in render.PASTA_PAINEL.glob("Painel_Rota_*.html"):          # painel de visao que deixou de existir (ou falhou) nao fica para tras
        if velho.name not in nomes:
            velho.unlink()
            L.log(f"removido painel sem visao correspondente nesta execucao: {velho.name}", "aviso")
    L.log(f"paineis em {render.PASTA_PAINEL} (pasta local, fora do OneDrive).")
    L.etapa_fim("ok" if not falhas else "com falhas", paineis=len(gerados), falhas=len(falhas))
    return {"paineis": gerados, "falhas": falhas}


def executar(forcar: bool = False, modo_publicacao: str = "plano") -> int:
    preparar_pastas()
    arq_log = L.abrir()
    L.titulo(f"PAINEL DE ROTA · execucao {L.EXECUCAO_ID}")
    dif = _verificar()
    info = _ingerir(forcar)
    rota, ci, pd_, hier, cli = info.pop("_dados")
    cruz_sellin = info.pop("_sellin")
    m = _modelar(rota, ci, pd_, hier, cli)
    calc = _calcular(m)
    gerados = _painel(m, calc, hier)

    L.etapa_inicio("GRAVAR (camada curada + qualidade)")
    for nome, df in {**m, "LOJA_MES": calc["LOJA_MES"], "DIARIO_VENDEDOR": calc["DIARIO_VENDEDOR"]}.items():
        if len(df.columns):
            parquet.salvar(df.assign(EXECUCAO_ID=L.EXECUCAO_ID), nome)
    if hier is not None:
        vis = estrutura.visoes(hier)
        parquet.salvar(vis.assign(N3_CODS=vis["N3_CODS"].map(";".join), EXECUCAO_ID=L.EXECUCAO_ID), "DIM_VISAO")
    info["qualidade"] = qualidade.gerar(m, calc["LOJA_MES"], L.contagens(), info["problemas_depara"], cruz_sellin)
    info["dados_ate"] = str(calc["_ate"].date())
    info["paineis"], info["falhas_paineis"] = gerados["paineis"], gerados["falhas"]
    info["total_mes"] = {k: (round(float(v), 2) if v == v else None) for k, v in calc["_total"].items() if k != "GRUPO"}
    info["aderencia_mes"] = {k: (round(float(v), 2) if v == v else None) for k, v in calc["_aderencia"].items() if k != "GRUPO"}
    L.etapa_fim("ok")
    manifesto.gravar(L.EXECUCAO_ID, {"dados_ate": info["dados_ate"]})
    info["publicacao"] = publicar.executar(gerados["paineis"], gerados["falhas"], modo_publicacao)

    resumo = {"execucao": L.EXECUCAO_ID, "inicio": L.INICIO.isoformat(timespec="seconds"),
              "fim": datetime.now().isoformat(timespec="seconds"), "situacao": "paineis com falha" if info["falhas_paineis"] else ("publicacao com erro" if info["publicacao"]["erros"] else "ok"),
              "manifesto": dif, "etapas": L.etapas(), "arquivos": L.contagens(), **info,
              "avisos": L.avisos(), "erros": L.erros()}
    alvo = PASTA_LOGS / f"resumo_{L.EXECUCAO_ID}.json"
    alvo.write_text(json.dumps(resumo, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    L.log("")
    if info["falhas_paineis"]:
        L.log(f"CONCLUIDO COM {len(info['falhas_paineis'])} FALHA(S) NOS PAINEIS (acima). Log: {arq_log.name} | resumo: {alvo.name}", "erro")
        L.fechar()
        return 1
    if info["publicacao"]["erros"]:
        L.log(f"PAINEIS GERADOS, MAS A PUBLICACAO TEVE {len(info['publicacao']['erros'])} ERRO(S) (acima). Log: {arq_log.name} | resumo: {alvo.name}", "erro")
        L.fechar()
        return 1
    L.log(f"SUCESSO — {len(L.avisos())} aviso(s). Log: {arq_log.name} | resumo: {alvo.name}", "ok")
    L.fechar()
    return 0
