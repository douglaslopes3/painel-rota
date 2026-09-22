# -*- coding: utf-8 -*-
"""Relatório de qualidade e listas de exceção (`data/rota/quality/`), refeitos a cada execução.

Nada aqui muda número: é o lugar onde os problemas de origem ficam VISÍVEIS todo
dia (check-in sem par, visita relâmpago, vendedor sem app, loja visitada por
outro vendedor…). Nome de cliente e de funcionário só aparecem nestes arquivos,
nunca no log.
"""
from __future__ import annotations

import pandas as pd

from .utils.config import CFG, PASTA_QUALITY
from .utils.log import EXECUCAO_ID, log


def _csv(df: pd.DataFrame, nome: str) -> int:
    PASTA_QUALITY.mkdir(parents=True, exist_ok=True)
    df.to_csv(PASTA_QUALITY / nome, sep=";", index=False, encoding="utf-8-sig", decimal=",")
    return len(df)


def gerar(m: dict[str, pd.DataFrame], L: pd.DataFrame, contagens: dict, problemas_depara: list[str], sellin: dict | None = None) -> dict:
    q = CFG["qualidade"]
    fv, fp, dv, dc = m["FATO_VISITA"], m["FATO_PEDIDO"], m["DIM_VENDEDOR"], m["DIM_CLIENTE"]
    nome = dc.set_index("COD_CLIENTE")["NOME_CLIENTE"]
    vis = fv.assign(NOME_CLIENTE=fv["COD_CLIENTE"].map(nome))
    cols = ["DATA", "LOGIN", "NOME_USUARIO", "COD_CLIENTE", "NOME_CLIENTE", "N_CHECKINS", "N_CHECKOUTS", "N_PARES", "MINUTOS_EM_LOJA", "PRIMEIRO_EVENTO", "ULTIMO_EVENTO"]

    n = {
        "visitas_sem_par": _csv(vis[vis["N_PARES"] == 0][cols], "visitas_sem_par_checkin_checkout.csv"),
        "visitas_so_checkout": int((fv["N_CHECKINS"] == 0).sum()),
        "visitas_curtas": _csv(vis[vis["MINUTOS_EM_LOJA"] < q["visita_curta_min"]][cols], "visitas_curtas.csv"),
        "visitas_longas": _csv(vis[vis["MINUTOS_EM_LOJA"] > q["visita_longa_min"]][cols], "visitas_longas.csv"),
        "visitas_multiplos_checkins": int((fv["N_CHECKINS"] > 1).sum()),
        "visitas_fora_da_rota": _csv(vis[~vis["NA_ROTA"]][cols], "visitas_a_clientes_fora_da_rota.csv"),
        "visitas_dia_nao_util": _csv(vis[~vis["DIA_UTIL"]][cols], "visitas_em_dia_nao_util.csv"),
        "visitas_sem_controle": int((fv["NA_ROTA"] & ~fv["CONTROLA_VISITA"].fillna(True)).sum()),
    }
    outro = vis[vis["NA_ROTA"] & vis["COD_VENDEDOR_LOGIN"].notna() & (vis["COD_VENDEDOR_LOGIN"] != vis["COD_VENDEDOR_ROTA"])]
    n["visitas_por_outro_vendedor"] = _csv(outro[cols + ["COD_VENDEDOR_LOGIN", "COD_VENDEDOR_ROTA"]], "visitas_por_vendedor_diferente_do_dono.csv")
    sem_h = vis[vis["COD_VENDEDOR_LOGIN"].isna()].groupby(["LOGIN", "NOME_USUARIO"]).size().reset_index(name="VISITAS")
    n["logins_sem_hierarquia"] = _csv(sem_h, "logins_sem_posicao_na_hierarquia.csv")
    if len(dv):
        sem_app = dv[~dv["USA_APP"]][["N3_ROTULO", "N4_COD", "N4_NOME", "LOGIN_MERCANET", "CLIENTES", "CLIENTES_COM_VISITA"]]
        n["vendedores_sem_app"] = _csv(sem_app, "vendedores_sem_checkin.csv")
    pr = fp[fp["NA_ROTA"]]
    n["pedidos_rota"] = len(pr)
    n["pedidos_rota_excluidos"] = int((~pr["VALIDO"]).sum())
    n["pedidos_rota_fora_da_janela"] = int((pr["VALIDO"] & ~pr["NA_JANELA_DA_ROTA"]).sum())
    fora_j = pr[pr["VALIDO"] & ~pr["NA_JANELA_DA_ROTA"]][["PEDIDO", "COD_CLIENTE", "NOME_CLIENTE", "DATA_EMISSAO", "DATA_ROTA", "SITUACAO", "VALOR", "COD_VENDEDOR_ROTA"]]
    _csv(fora_j, "pedidos_de_clientes_da_rota_fora_da_janela.csv")

    if sellin:                                     # D-42: sell-in do BI, só conferido (nenhum indicador usa ainda)
        n["sellin_fora_da_rota"] = _csv(sellin["_fora_da_rota"], "sellin_clientes_fora_da_rota.csv")
        n["sellin_rota_sem_bi"] = _csv(sellin["_rota_sem_bi"], "sellin_lojas_da_rota_sem_sellin.csv")
        n["sellin_vendedor_diferente"] = _csv(sellin["_vendedor_diferente"], "sellin_vendedor_diferente_da_rota.csv")
        n["sellin_diferencas"] = _csv(sellin["_diferencas"], "sellin_diferencas_entre_arquivos.csv")
    mins = fv["MINUTOS_EM_LOJA"].dropna()
    linhas = [
        f"# Relatório de qualidade · execução {EXECUCAO_ID}", "",
        "## 1. Arquivos lidos", "", "| Arquivo | Lidas | Descartadas | Detalhe |", "|---|---:|---:|---|",
        *[f"| {a} | {c['lidas']:,} | {c['rejeitadas']:,} | {', '.join(f'{k}={v}' for k, v in c.items() if k not in ('lidas', 'rejeitadas', 'somas'))} |" for a, c in contagens.items()],
        "", "## 2. Visitas (check-in / check-out)", "",
        f"- Visitas (login × cliente × dia): **{len(fv):,}**, de {int(fv['N_CHECKINS'].sum() + fv['N_CHECKOUTS'].sum()):,} eventos; {int(fv['CONTA_COMO_VISITA'].sum()):,} contam como visita pelas regras do config.",
        f"- Com mais de um check-in no mesmo cliente e dia: **{n['visitas_multiplos_checkins']:,}** ({100 * n['visitas_multiplos_checkins'] / max(len(fv), 1):.1f}%) — contam como uma visita.",
        f"- Sem par check-in → check-out (sem minutos em loja): **{n['visitas_sem_par']:,}**, das quais {n['visitas_so_checkout']:,} só têm check-out → `visitas_sem_par_checkin_checkout.csv`.",
        f"- Minutos em loja (visitas com par): mediana **{mins.median():.1f}**, média {mins.mean():.1f}; menos de {q['visita_curta_min']} min: **{n['visitas_curtas']:,}**; mais de {q['visita_longa_min']} min: **{n['visitas_longas']:,}** → `visitas_curtas.csv`, `visitas_longas.csv`.",
        f"- A clientes fora da rota do mês: **{n['visitas_fora_da_rota']:,}** → `visitas_a_clientes_fora_da_rota.csv`. Em dia não útil: **{n['visitas_dia_nao_util']:,}** → `visitas_em_dia_nao_util.csv`.",
        f"- A lojas sem controle de visita (telefone): {n['visitas_sem_controle']:,}. Feitas por vendedor diferente do dono da loja na rota: **{n['visitas_por_outro_vendedor']:,}** → `visitas_por_vendedor_diferente_do_dono.csv`.",
        f"- Logins com check-in e sem posição na hierarquia: **{n['logins_sem_hierarquia']:,}** → `logins_sem_posicao_na_hierarquia.csv`.",
        "", "## 3. Vendedores", "",
        (f"- Posições sem nenhum check-in no período: **{n.get('vendedores_sem_app', 0)}** de {len(dv)} → `vendedores_sem_checkin.csv`. "
         "As visitas deles aparecem zeradas por falta de registro, não necessariamente por falta de atendimento." if len(dv) else "- Hierarquia ausente."),
        *[f"- De-para: {p}" for p in problemas_depara],
        "", "## 4. Pedidos", "",
        f"- Pedidos de clientes da rota: **{n['pedidos_rota']:,}** de {len(fp):,}; excluídos pela situação ({', '.join(CFG['regras']['pedido']['situacoes_excluidas'])}): {n['pedidos_rota_excluidos']:,}.",
        f"- Válidos mas FORA da janela do dia da rota (+{CFG['regras']['pedido']['janela_dias_corridos']} dia corrido): **{n['pedidos_rota_fora_da_janela']:,}** — entram no total do mês da loja, não no 'com pedido' do roteiro → `pedidos_de_clientes_da_rota_fora_da_janela.csv`.",
        "", "## 5. Lojas do roteiro", "",
        f"- Lojas na rota: {len(L):,} ({int(L['CONTROLA_VISITA'].sum()):,} com controle de visita, {int((~L['CONTROLA_VISITA']).sum()):,} só por pedido).",
        f"- Status no dia da rota: " + " · ".join(f"{v} **{int((L['STATUS'] == k).sum()):,}**" for k, v in {3: 'visita + pedido', 2: 'só visita', 1: 'só pedido', 0: 'sem contato'}.items()) + " (inclui lojas com rota ainda por vencer).",
    ]
    if sellin:
        linhas += [
            "", "## 6. Sell-in (BI) — só conferido, fora dos indicadores (D-42)", "",
            f"- Clientes no BI: {sellin['clientes_bi']:,}; lojas da rota no BI: **{sellin['lojas_rota_no_bi']:,} de {sellin['lojas_rota']:,}** → sem sell-in: `sellin_lojas_da_rota_sem_sellin.csv`.",
            f"- Clientes do BI FORA da rota: **{sellin['clientes_bi_fora_da_rota']:,}** (receita R$ {sellin['receita_fora_da_rota']:,.2f}) → `sellin_clientes_fora_da_rota.csv`.",
            f"- Vendedor do BI diferente do vendedor da rota: **{sellin['vendedor_diferente']:,}** loja(s) → `sellin_vendedor_diferente_da_rota.csv`.",
            f"- Vendedores do BI fora do de-para: {sellin['vendedores_bi_fora_do_depara'] or 'nenhum'}.",
            f"- Diferenças por cliente entre os 3 arquivos: **{n['sellin_diferencas']:,}** → `sellin_diferencas_entre_arquivos.csv`.",
        ]
    (PASTA_QUALITY / "relatorio_qualidade.md").write_text("\n".join(linhas) + "\n", encoding="utf-8")
    log(f"relatorio de qualidade e {len(list(PASTA_QUALITY.glob('*.csv')))} listas de excecao -> {PASTA_QUALITY.name}/", "ok")
    return n
