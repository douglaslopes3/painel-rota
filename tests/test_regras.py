# -*- coding: utf-8 -*-
"""Testes das regras de negócio (Fase 2): visita, pedido, status da loja e indicadores.

    python tests/test_regras.py

Cenário sintético pequeno, montado em memória no formato do staging. Cada teste
fixa uma regra de docs/07_CATALOGO_METRICAS.md; se a regra mudar no config, o
teste correspondente tem de mudar junto (é o registro do que foi combinado).
"""
from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from rota import metricas, painel  # noqa: E402
from rota.transform import calendario, modelo, visitas  # noqa: E402
from rota.utils.config import CFG  # noqa: E402

T = pd.Timestamp


def _ci(linhas):
    df = pd.DataFrame(linhas, columns=["LOGIN", "COD_CLIENTE", "DATA_HORA", "EVENTO"])
    df["DATA_HORA"] = pd.to_datetime(df["DATA_HORA"]); df["DATA"] = df["DATA_HORA"].dt.normalize()
    df["ANO_MES"] = df["DATA_HORA"].dt.strftime("%Y-%m"); df["NOME_USUARIO"] = "x"; df["NOME_CLIENTE"] = "LOJA " + df["COD_CLIENTE"]
    return df


def _cenario():
    """Outubro/2026. Vendedor 101 (login AAA): lojas 1..4 presenciais; vendedor 136 (sem login): loja 5 por TELEFONE.
    Rota: loja 1 e 2 em 05/10 (seg), loja 3 em 06/10, loja 4 em 09/10 (sex), loja 5 em 05/10."""
    rota = pd.DataFrame({"ANO_MES": "2026-10", "SUPERVISOR": ["Marco"] * 4 + ["Anderson"], "COD_VENDEDOR": pd.array(["101"] * 4 + ["136"], dtype="string"),
                         "EXECUTIVO": ["FULANO"] * 4 + ["HIBRIDO"], "COD_CLIENTE": ["1", "2", "3", "4", "5"], "CANAL": ["PRESENCIAL"] * 4 + ["TELEFONE"],
                         "DATA_ROTA": pd.to_datetime(["2026-10-05", "2026-10-05", "2026-10-06", "2026-10-09", "2026-10-05"]), "CIDADE": "ITU",
                         "NET_SALES_25": 1.0, "NET_SALES_26": 2.0, "FREQ_25": 4, "FREQ_26": 5, "VOLUME_25": 1.0, "VOLUME_26": 1.0, "ARQUIVO_ORIGEM": "r.xlsx"})
    ci = _ci([("AAA", "1", "2026-10-05 09:00", "CHECKIN"), ("AAA", "1", "2026-10-05 09:01", "CHECKIN"),      # 2 check-ins, 1 visita
              ("AAA", "1", "2026-10-05 09:31", "CHECKOUT"),                                                 # par com o ÚLTIMO check-in: 30 min
              ("AAA", "1", "2026-10-05 15:00", "CHECKIN"), ("AAA", "1", "2026-10-05 15:05", "CHECKOUT"),     # 2º par: 5 min (vale o maior)
              ("AAA", "2", "2026-10-07 10:00", "CHECKIN"),                                                  # loja 2 visitada FORA do dia (rota 05/10), sem check-out
              ("AAA", "3", "2026-10-06 11:00", "CHECKOUT"),                                                 # só check-out no dia da rota
              ("AAA", "9", "2026-10-06 12:00", "CHECKIN"), ("AAA", "9", "2026-10-06 12:10", "CHECKOUT")])    # cliente fora da rota
    ped = pd.DataFrame({"ANO_MES": "2026-10", "PEDIDO": ["p1", "p2", "p3", "p4", "p5", "p6"], "COD_CLIENTE": ["1", "1", "2", "4", "5", "8"],
                        "NOME_CLIENTE": "n", "DATA_EMISSAO": pd.to_datetime(["2026-10-05", "2026-10-06", "2026-10-05", "2026-10-12", "2026-10-06", "2026-10-05"]),
                        "SITUACAO": ["Aberto", "Bloqueado", "Cancelado", "Aberto", "Faturado", "Aberto"],
                        "VALOR_PEDIDO": [100.0, 50.0, 999.0, 70.0, 30.0, 10.0], "QTD_SOLICITADA": [10.0, 5.0, 99.0, 7.0, 3.0, 1.0]})
    hier = pd.DataFrame({"N1_COD": "20", "N1_ROTULO": "20 - ATACADO - HEAD", "N2_COD": ["21000", "23000"], "N2_ROTULO": ["21000 - G - A", "23000 - G - B"],
                         "N3_COD": ["2110", "2310"], "N3_ROTULO": ["2110 - S - MARCO", "2310 - S - ANDERSON"], "N4_COD": ["101", "136"],
                         "N4_ROTULO": ["101 - V - FULANO", "136 - V - HIBRIDO"], "N4_NOME": ["FULANO", "HIBRIDO"],
                         "LOGIN_MERCANET": pd.array(["AAA", pd.NA], dtype="string")})
    m = modelo.construir(rota, ci, ped, hier)
    modelo.integridade(m, ci, ped, rota)
    return m, metricas.loja_mes(m)


M, L = _cenario()
FV, FP = M["FATO_VISITA"], M["FATO_PEDIDO"]
loja = lambda c: L[L.COD_CLIENTE == c].iloc[0]          # noqa: E731


def test_varios_checkins_no_dia_sao_uma_visita():
    v = FV[(FV.COD_CLIENTE == "1")]
    assert len(v) == 1 and v.N_CHECKINS.iloc[0] == 3 and v.N_CHECKOUTS.iloc[0] == 2 and len(FV) == 4


def test_minutos_e_o_maior_par_com_o_ultimo_checkin_antes_do_checkout():
    assert FV[FV.COD_CLIENTE == "1"].MINUTOS_EM_LOJA.iloc[0] == 30.0          # 09:01->09:31, não 09:00->09:31 nem a soma (35)


def test_visita_sem_par_conta_mas_nao_tem_minutos():
    v2, v3 = FV[FV.COD_CLIENTE == "2"].iloc[0], FV[FV.COD_CLIENTE == "3"].iloc[0]
    assert v2.CONTA_COMO_VISITA and pd.isna(v2.MINUTOS_EM_LOJA)
    assert v3.N_CHECKINS == 0 and v3.CONTA_COMO_VISITA and loja("3").VISITA_NO_DIA      # só check-out conta (regra do protótipo, P-12)


def test_nome_da_loja_segue_a_precedencia_do_config():
    """D-38. O cadastro de nomes vence o Mercanet; a loja que não está nele fica com o nome do Mercanet; trocar a lista troca o nome."""
    from rota.utils.config import CFG
    rota, ci, ped = (M["FATO_ROTA_PLANEJADA"][["COD_CLIENTE", "DATA_ROTA"]], _ci([("AAA", "1", "2026-10-05 09:00", "CHECKIN")]),
                     pd.DataFrame({"COD_CLIENTE": ["2"], "NOME_CLIENTE": ["PEDIDO DOIS LTDA"], "DATA_EMISSAO": pd.to_datetime(["2026-10-05"])}))
    cad = pd.DataFrame({"COD_CLIENTE": ["1", "3"], "NOME_CLIENTE": ["CADASTRO UM", "CADASTRO TRES"]})
    antes = CFG["regras"]["nome_cliente"]["precedencia"]
    try:
        CFG["regras"]["nome_cliente"]["precedencia"] = ["clientes", "rota", "mercanet"]
        n = modelo._nomes(rota, ci, ped, cad).set_index("COD_CLIENTE")
        assert (n.NOME_CLIENTE["1"], n.NOME_ORIGEM["1"]) == ("CADASTRO UM", "clientes") and (n.NOME_CLIENTE["2"], n.NOME_ORIGEM["2"]) == ("PEDIDO DOIS LTDA", "mercanet")
        CFG["regras"]["nome_cliente"]["precedencia"] = ["mercanet", "clientes"]
        n = modelo._nomes(rota, ci, ped, cad).set_index("COD_CLIENTE")
        assert n.NOME_CLIENTE["1"] == "LOJA 1" and n.NOME_CLIENTE["3"] == "CADASTRO TRES"
        assert len(modelo._nomes(rota, ci, ped, None)) == 2                     # sem o cadastro, segue só com o Mercanet
    finally:
        CFG["regras"]["nome_cliente"]["precedencia"] = antes


def test_evento_em_fim_de_semana_nao_conta_como_visita():
    """D-32 (config: sabado, domingo, feriado). 10/10/2026 é sábado, 11/10 é domingo, 12/10 é segunda."""
    v = visitas.gerar(_ci([("AAA", "1", "2026-10-10 09:00", "CHECKIN"), ("AAA", "1", "2026-10-10 09:30", "CHECKOUT"),
                           ("AAA", "2", "2026-10-11 09:00", "CHECKIN"), ("AAA", "3", "2026-10-12 09:00", "CHECKIN")]))
    assert len(v) == 3 and list(v.sort_values("DATA").CONTA_COMO_VISITA) == [False, False, True]      # a linha fica, só não conta
    assert list(v.sort_values("DATA").DIA_NAO_CONTA) == [True, True, False]


def test_feriado_nao_conta_e_a_lista_do_config_muda_a_regra():
    """D-32. A regra é a lista `regras.visita.dias_que_nao_contam`: esvaziar a lista devolve a contagem, sem mexer em código."""
    from rota.utils.config import CFG
    ev = _ci([("AAA", "1", "2026-10-12 09:00", "CHECKIN"), ("AAA", "2", "2026-10-13 09:00", "CHECKIN"), ("AAA", "3", "2026-10-10 09:00", "CHECKIN")])
    regra, feriados = CFG["regras"]["visita"]["dias_que_nao_contam"], CFG["calendario"]["feriados"]
    try:
        CFG["calendario"]["feriados"] = ["2026-10-12"]                       # segunda-feira, feriado
        CFG["regras"]["visita"]["dias_que_nao_contam"] = ["sabado", "domingo", "feriado"]
        assert list(visitas.gerar(ev).sort_values("DATA").CONTA_COMO_VISITA) == [False, False, True]      # sáb 10, feriado 12, ter 13
        CFG["regras"]["visita"]["dias_que_nao_contam"] = ["sabado", "domingo"]
        assert list(visitas.gerar(ev).sort_values("DATA").CONTA_COMO_VISITA) == [False, True, True]
        CFG["regras"]["visita"]["dias_que_nao_contam"] = []
        assert visitas.gerar(ev).CONTA_COMO_VISITA.all()
        CFG["regras"]["visita"]["dias_que_nao_contam"] = ["sabadu"]
        try:
            visitas.gerar(ev)
        except ValueError:
            pass
        else:
            raise AssertionError("valor invalido na lista passou sem erro")
    finally:
        CFG["regras"]["visita"]["dias_que_nao_contam"], CFG["calendario"]["feriados"] = regra, feriados


def test_visita_fora_do_dia_nao_e_visita_no_dia_mas_e_fora_do_roteiro():
    l2 = loja("2")
    assert not l2.VISITA_NO_DIA and l2.DIAS_FORA_DO_ROTEIRO == 1 and l2.DIAS_VISITADOS == 1


def test_pedido_vale_no_dia_da_rota_ou_no_dia_corrido_seguinte_e_soma_todos():
    l1 = loja("1")
    assert l1.PEDIDOS_JANELA == 1 and l1.VALOR_JANELA == 100.0 and l1.QTD_JANELA == 10.0 and l1.STATUS == 3    # o Bloqueado de 06/10 NÃO conta (D-33)


def test_cancelado_fica_fora_e_pedido_fora_da_janela_so_entra_no_mes():
    assert loja("2").PEDIDOS_MES == 0 and loja("2").STATUS == 0                                     # o único pedido da loja 2 é Cancelado
    l4 = loja("4")                                                                                    # rota sexta 09/10, pedido segunda 12/10: fora da janela de 1 dia CORRIDO (P-13)
    assert not l4.PEDIDO_NA_JANELA and l4.PEDIDOS_MES == 1 and l4.VALOR_MES == 70.0


def test_telefone_nao_entra_no_roteiro_de_visita_so_no_de_pedido():
    k = metricas.kpis(L, FV, FP, pd.to_datetime(["2026-10-05"]), criterio="janela").iloc[0]
    assert (k.ROTEIRO, k.VISITADAS_NO_DIA, k.COM_PEDIDO, k.SEM_CONTATO) == (2, 1, 1, 1)             # lojas 1 e 2
    assert (k.TEL_ROTEIRO, k.TEL_COM_PEDIDO, k.TEL_VALOR_PEDIDOS) == (1, 1, 30.0)                     # loja 5: pedido em 06/10, na janela


def test_kpis_da_semana_e_a_soma_das_partes():
    dias = pd.to_datetime(["2026-10-05", "2026-10-06", "2026-10-07"])
    tot = metricas.kpis(L, FV, FP, dias, criterio="janela").iloc[0]
    assert (tot.ROTEIRO, tot.VISITADAS_NO_DIA, tot.FORA_DO_ROTEIRO, tot.TOTAL_VISITADAS, tot.NAO_ATENDIDAS) == (3, 2, 1, 3, 1)
    por = metricas.kpis(L, FV, FP, dias, por="COD_VENDEDOR", criterio="janela")
    assert por.ROTEIRO.sum() == tot.ROTEIRO and por.TEL_ROTEIRO.sum() == tot.TEL_ROTEIRO and set(por.COD_VENDEDOR) == {"101", "136"}


def test_criterio_mes_pedido_e_visita_valem_em_qualquer_dia_ate_a_data():
    """D-25. Semana 05..09/10: lojas 1, 2, 3 e 4 no roteiro. Até 09/10 só a loja 1 tem pedido válido (05 e 06/10); a 4 pede em 12/10."""
    k9 = metricas.kpis(L, FV, FP, pd.date_range("2026-10-05", "2026-10-09"), criterio="mes").iloc[0]
    assert (k9.ROTEIRO, k9.COM_PEDIDO, k9.VALOR_PEDIDOS, k9.VISITADAS_ATE_A_DATA, k9.VISITA_E_PEDIDO, k9.SEM_CONTATO) == (4, 1, 100.0, 3, 1, 1)
    k12 = metricas.kpis(L, FV, FP, pd.date_range("2026-10-01", "2026-10-12"), criterio="mes").iloc[0]      # o pedido de 12/10 (fora da janela) agora conta
    assert (k12.COM_PEDIDO, k12.VALOR_PEDIDOS, k12.SEM_CONTATO, k12.TEL_COM_PEDIDO) == (2, 170.0, 0, 1)
    a = metricas.aderencia_mes(L, FV, "2026-10-12").iloc[0]
    assert a.VISITADAS_NO_MES == k12.VISITADAS_ATE_A_DATA == 3 and k12.PCT_ADERENCIA == 75.0


def test_aderencia_no_mes_conta_visita_em_qualquer_dia_sobre_o_roteiro_vencido():
    a5 = metricas.aderencia_mes(L, FV, "2026-10-05").iloc[0]                  # vencidas: lojas 1 e 2; só a 1 foi visitada até 05/10
    a7 = metricas.aderencia_mes(L, FV, "2026-10-07").iloc[0]                  # vencidas: 1, 2, 3; a 2 foi visitada em 07/10 (fora do dia) e CONTA (D-03)
    assert (a5.ROTEIRO_VENCIDO, a5.VISITADAS_NO_MES) == (2, 1) and (a7.ROTEIRO_VENCIDO, a7.VISITADAS_NO_MES, a7.PCT_ADERENCIA_MES) == (3, 3, 100.0)


def test_cliente_fora_da_rota_fica_na_fato_marcado_e_nao_entra_em_indicador():
    v9 = FV[FV.COD_CLIENTE == "9"].iloc[0]
    assert not v9.NA_ROTA and "9" not in set(L.COD_CLIENTE) and M["FATO_PEDIDO"].query("COD_CLIENTE == '8'").NA_ROTA.iloc[0] == False   # noqa: E712
    assert set(M["DIM_CLIENTE"].COD_CLIENTE) >= {"8", "9"}


def test_jornada_usa_o_login_e_o_diario_fecha_com_os_kpis():
    j = metricas.jornada_dia(FV); d5 = j[j.DATA == T("2026-10-05")].iloc[0]
    assert d5.COD_VENDEDOR == "101" and d5.PRIMEIRA_ENTRADA == T("2026-10-05 09:00") and d5.ULTIMA_SAIDA == T("2026-10-05 15:05") and d5.TEMPO_MEDIO_LOJA_MIN == 30.0
    di = metricas.diario_vendedor(L, FV, FP)
    assert di.ROTEIRO.sum() == 4 and di.TEL_ROTEIRO.sum() == 1 and di.VISITADAS_NO_DIA.sum() == 2


M["DIM_VENDEDOR"]["N3_NOME"] = ["MARCO", "ANDERSON"]
V_SUP = {"NIVEL": "N3", "COD": "2110", "ROTULO": "2110 - S - MARCO", "NOME": "MARCO", "N3_CODS": ["2110"]}
V_TEL = {"NIVEL": "N3", "COD": "2310", "ROTULO": "2310 - S - ANDERSON", "NOME": "ANDERSON", "N3_CODS": ["2310"]}
V_HEAD = {"NIVEL": "N1", "COD": "20", "ROTULO": "20 - ATACADO - HEAD", "NOME": "HEAD", "N3_CODS": ["2110", "2310"]}
PP = painel.preparar(M, L, T("2026-10-07"))
DV = M["DIM_VENDEDOR"]


def test_painel_so_leva_a_visao_e_os_cards_fecham_com_a_lista():
    """Recorte físico (D-05): o painel do supervisor 2110 não contém a loja 5 (supervisor 2310) nem o vendedor 136."""
    J = painel.montar(PP, DV, V_SUP, "07/10/2026 08:00")
    painel.validar(J, PP, DV, V_SUP)                                          # levanta PainelInvalido se cards != lista ou se houver vazamento
    assert {l[0] for l in J["lojas"]} == {"1", "2", "3", "4"} and [x["cod"] for x in J["vend"]] == ["101"] and len(J["sups"]) == 1
    assert [d["lab"] for d in J["dias"]] == ["05/10", "06/10", "09/10"] and [d["futuro"] for d in J["dias"]] == [False, False, True]
    C = {c: i for i, c in enumerate(J["cols"])}
    mes_0610 = J["agg"]["mes"][1][0]                                          # mês até 06/10, vendedor 101
    assert (mes_0610[C["ROTEIRO"]], mes_0610[C["VISITADAS_NO_DIA"]], mes_0610[C["COM_PEDIDO"]], mes_0610[C["VALOR_PEDIDOS"]]) == (3, 2, 1, 100.0)      # sem o Bloqueado (D-33)
    assert "QTD_SOLICITADA" not in J["cols"] and J["horarios"][0][0] == ["09:00", "15:05"]     # D-35: o painel leva o valor; a quantidade saiu


def test_vazamento_e_detectado():
    J = painel.montar(PP, DV, V_HEAD, "x")                                    # dados do head apresentados como se fossem do supervisor
    try:
        painel.validar(J, PP, DV, V_SUP)
    except painel.PainelInvalido as e:
        assert "VAZAMENTO" in str(e)
    else:
        raise AssertionError("o painel com lojas de outra supervisao passou na validacao")


def test_paineis_dos_supervisores_somam_o_do_head():
    Js = {v["ROTULO"]: painel.montar(PP, DV, v, "x") for v in (V_SUP, V_TEL, V_HEAD)}
    tot = {r: painel.totais(j) for r, j in Js.items()}
    assert painel.conferir_niveis(tot, [V_SUP, V_TEL, V_HEAD]) == []
    assert tot[V_HEAD["ROTULO"]]["LOJAS"] == 5 and tot[V_TEL["ROTULO"]]["TEL_ROTEIRO"] == 1 and tot[V_SUP["ROTULO"]]["ROTEIRO"] == 3
    tot[V_SUP["ROTULO"]]["ROTEIRO"] += 1                                      # um supervisor "inflado" tem de ser acusado
    assert any("ROTEIRO" in e for e in painel.conferir_niveis(tot, [V_SUP, V_TEL, V_HEAD]))
    assert painel.conferir_niveis({V_HEAD["ROTULO"]: tot[V_HEAD["ROTULO"]]}, [V_SUP, V_TEL, V_HEAD])       # supervisor ausente: nao confere em silencio


def test_calendario_ciclo_vem_das_datas_da_rota():
    cal = calendario.gerar(M["FATO_ROTA_PLANEJADA"])
    assert len(cal) == 31 and cal.DIA_DE_ROTA.sum() == 3 and cal[cal.DATA == T("2026-10-09")].N_DIA_CICLO.iloc[0] == 3
    assert not cal[cal.DATA == T("2026-10-10")].DIA_UTIL.iloc[0]


def _com_cfg(secao: str, chave: str, valor, fn):
    antes = CFG[secao][chave]
    CFG[secao][chave] = valor
    try:
        return fn()
    finally:
        CFG[secao][chave] = antes


def test_semana_do_mes_ou_de_segunda_conforme_o_config():
    """D-44: faixa_do_mes = S1 dias 1-7, S2 8-14 ... (a S4 vai ate o fim do mes); segunda = regra original da D-02."""
    cal = _com_cfg("calendario", "semana", "faixa_do_mes", lambda: calendario.gerar(M["FATO_ROTA_PLANEJADA"]))
    d = cal.set_index("DATA")
    assert (d.loc[T("2026-10-07"), "SEMANA_NOME"], d.loc[T("2026-10-07"), "SEMANA_INICIO"]) == ("S1", T("2026-10-01"))
    assert (d.loc[T("2026-10-08"), "SEMANA_NOME"], d.loc[T("2026-10-31"), "SEMANA_NOME"], d.loc[T("2026-10-31"), "SEMANA_INICIO"]) == ("S2", "S4", T("2026-10-22"))
    cal = _com_cfg("calendario", "semana", "segunda", lambda: calendario.gerar(M["FATO_ROTA_PLANEJADA"]))
    d = cal.set_index("DATA")
    assert d.loc[T("2026-10-07"), "SEMANA_INICIO"] == T("2026-10-05") and pd.isna(d.loc[T("2026-10-07"), "SEMANA_NOME"])


def _aborta(fn) -> bool:
    try:
        fn()
    except SystemExit:
        return True
    return False


def test_pesos_do_sellin_mal_declarados_abortam():
    """D-44: os pesos vivem no config e sao conferidos — soma diferente de 100, semana sem peso ou faixa com buraco abortam."""
    calendario.conferir_config()                                               # o config do projeto passa
    assert _aborta(lambda: _com_cfg("metas_sellin", "pesos", {"S1": 30, "S2": 30, "S3": 20, "S4": 10}, calendario.conferir_config))
    assert _aborta(lambda: _com_cfg("metas_sellin", "pesos", {"S1": 50, "S2": 50}, calendario.conferir_config))
    buraco = [{"nome": "S1", "de": 1, "ate": 7}, {"nome": "S2", "de": 9, "ate": 14}, {"nome": "S3", "de": 15, "ate": 21}, {"nome": "S4", "de": 22, "ate": 31}]
    assert _aborta(lambda: _com_cfg("calendario", "semanas_do_mes", buraco, calendario.conferir_config))
    assert _com_cfg("metas_sellin", "pesos_por_mes", {"2026-10": {"S1": 40, "S2": 30, "S3": 20, "S4": 10}},
                    lambda: calendario.pesos("2026-10")) == {"S1": 40.0, "S2": 30.0, "S3": 20.0, "S4": 10.0}


# sell-in sintetico: orcado das lojas 1..5 (a 99 esta fora da rota e nao entra), faturado com uma devolucao, carteira de hoje
SI = {"cliente": pd.DataFrame({"COD_CLIENTE": ["1", "2", "3", "4", "5", "99"], "ORCADO": [100.0, 100.0, 0.0, 200.0, 100.0, 1000.0]}),
      "faturado": pd.DataFrame({"COD_CLIENTE": ["1", "1", "4", "99"], "RECEITA": [50.0, -10.0, 30.0, 500.0],
                                "DATA_FATURAMENTO": pd.to_datetime(["2026-10-05", "2026-10-08", "2026-10-06", "2026-10-05"])}),
      "carteira": pd.DataFrame({"COD_CLIENTE": ["2", "5", "99"], "CARTEIRA": [40.0, 20.0, 700.0]})}


def test_sellin_so_lojas_da_rota_com_meta_pelos_pesos_das_semanas():
    """D-44, pesos S1 30 · S2 30 · S3 20 · S4 20: em 06/10 (S1) a meta do mes e 30% do orcado; em 09/10 (S2), 60% (semana em andamento
    conta inteira). A semana e a do mes (S2 = 08 a 14/10). Devolucao entra como o BI traz; loja fora da rota nao entra."""
    PS = _com_cfg("calendario", "semana", "faixa_do_mes", lambda: _com_cfg(
        "metas_sellin", "pesos", {"S1": 30, "S2": 30, "S3": 20, "S4": 20}, lambda: painel.preparar(M, L, T("2026-10-07"), SI)))
    C = {c: i for i, c in enumerate(painel.COLS)}
    m6, m9, s9 = (PS["agg"][e][i].loc["101"] for e, i in (("mes", 1), ("mes", 2), ("sem", 2)))
    assert (m6["LOJAS_SI"], m6["ORCADO_SI"], m6["META_SI"], m6["FATURADO_SI"], m6["CARTEIRA_SI"], m6["LOJAS_FATURADAS_SI"]) == (4, 400, 120, 80, 40, 2)
    assert (m9["META_SI"], m9["FATURADO_SI"]) == (240, 70) and (s9["META_SI"], s9["FATURADO_SI"], s9["CARTEIRA_SI"], s9["LOJAS_FATURADAS_SI"]) == (120, -10, 0, 0)
    assert PS["agg"]["mes"][1].loc["136"]["CARTEIRA_SI"] == 20 and "FATURADO_SI" in C
    Js = {v["ROTULO"]: painel.montar(PS, DV, v, "x") for v in (V_SUP, V_TEL, V_HEAD)}
    for v in (V_SUP, V_TEL, V_HEAD):
        painel.validar(Js[v["ROTULO"]], PS, DV, v)                            # faturado dos cards = faturado da lista de lojas
    tot = {r: painel.totais(j) for r, j in Js.items()}
    assert painel.conferir_niveis(tot, [V_SUP, V_TEL, V_HEAD]) == [] and tot[V_HEAD["ROTULO"]]["ORCADO_SI"] == 500
    J = Js[V_HEAD["ROTULO"]]
    assert J["meta"]["sellin"]["pesos"]["S1"] == 30 and [(d["sem"], d["peso_acum"]) for d in J["dias"]] == [("S1", 30), ("S1", 30), ("S2", 60)]


if __name__ == "__main__":
    testes = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    falhas = 0
    for nome, fn in testes:
        try:
            fn(); print(f"  ok    {nome}")
        except Exception as e:                                   # noqa: BLE001
            falhas += 1; print(f" FALHA  {nome}: {type(e).__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes ok")
    sys.exit(1 if falhas else 0)
