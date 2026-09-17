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


def test_visita_fora_do_dia_nao_e_visita_no_dia_mas_e_fora_do_roteiro():
    l2 = loja("2")
    assert not l2.VISITA_NO_DIA and l2.DIAS_FORA_DO_ROTEIRO == 1 and l2.DIAS_VISITADOS == 1


def test_pedido_vale_no_dia_da_rota_ou_no_dia_corrido_seguinte_e_soma_todos():
    l1 = loja("1")
    assert l1.PEDIDOS_JANELA == 2 and l1.VALOR_JANELA == 150.0 and l1.QTD_JANELA == 15.0 and l1.STATUS == 3    # Bloqueado conta (P-09)


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
    assert (k9.ROTEIRO, k9.COM_PEDIDO, k9.VALOR_PEDIDOS, k9.VISITADAS_ATE_A_DATA, k9.VISITA_E_PEDIDO, k9.SEM_CONTATO) == (4, 1, 150.0, 3, 1, 1)
    k12 = metricas.kpis(L, FV, FP, pd.date_range("2026-10-01", "2026-10-12"), criterio="mes").iloc[0]      # o pedido de 12/10 (fora da janela) agora conta
    assert (k12.COM_PEDIDO, k12.VALOR_PEDIDOS, k12.SEM_CONTATO, k12.TEL_COM_PEDIDO) == (2, 220.0, 0, 1)
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


def test_painel_so_leva_a_visao_e_os_cards_fecham_com_a_lista():
    """Recorte físico (D-05): o painel do supervisor 2110 não contém a loja 5 (supervisor 2310) nem o vendedor 136."""
    v = {"NIVEL": "N3", "COD": "2110", "ROTULO": "2110 - S - MARCO", "NOME": "MARCO", "N3_CODS": ["2110"]}
    M["DIM_VENDEDOR"]["N3_NOME"] = ["MARCO", "ANDERSON"]; M["DIM_VENDEDOR"]["N4_NOME"] = ["FULANO", "HIBRIDO"]
    J = painel.montar(M, L, v, T("2026-10-07"), "07/10/2026 08:00")
    painel.validar(J, L, v)                                                   # aborta (SystemExit) se cards != lista ou se houver vazamento
    assert {l[0] for l in J["lojas"]} == {"1", "2", "3", "4"} and [x["cod"] for x in J["vend"]] == ["101"] and len(J["sups"]) == 1
    assert [d["lab"] for d in J["dias"]] == ["05/10", "06/10", "09/10"] and [d["futuro"] for d in J["dias"]] == [False, False, True]
    C = {c: i for i, c in enumerate(J["cols"])}
    mes_0610 = J["agg"]["mes"][1][0]                                          # mês até 06/10, vendedor 101
    assert (mes_0610[C["ROTEIRO"]], mes_0610[C["VISITADAS_NO_DIA"]], mes_0610[C["COM_PEDIDO"]], mes_0610[C["QTD_SOLICITADA"]]) == (3, 2, 1, 15.0)
    assert "VALOR_PEDIDOS" not in J["cols"] and J["horarios"][0][0] == ["09:00", "15:05"]      # D-04: valor não vai para o painel
    todos = {"NIVEL": "N1", "COD": "20", "ROTULO": "20 - ATACADO - HEAD", "NOME": "HEAD", "N3_CODS": ["2110", "2310"]}
    J1 = painel.montar(M, L, todos, T("2026-10-07"), "x"); painel.validar(J1, L, todos)
    i136 = [x["cod"] for x in J1["vend"]].index("136")                        # a ordem é por supervisor e nome: achar o híbrido pelo código
    assert len(J1["lojas"]) == 5 and len(J1["sups"]) == 2 and J1["agg"]["dia"][0][i136][C["TEL_ROTEIRO"]] == 1


def test_calendario_ciclo_vem_das_datas_da_rota():
    cal = calendario.gerar(M["FATO_ROTA_PLANEJADA"])
    assert len(cal) == 31 and cal.DIA_DE_ROTA.sum() == 3 and cal[cal.DATA == T("2026-10-09")].N_DIA_CICLO.iloc[0] == 3
    assert cal[cal.DATA == T("2026-10-07")].SEMANA_INICIO.iloc[0] == T("2026-10-05") and not cal[cal.DATA == T("2026-10-10")].DIA_UTIL.iloc[0]


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
