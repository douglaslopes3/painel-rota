# -*- coding: utf-8 -*-
"""Testes dos leitores (Fase 1). Rodam sem pytest:

    python tests/test_leitores.py

Usam arquivos SINTÉTICOS numa pasta temporária — nunca as bases reais, que mudam
todo dia. Cada teste prova uma proteção do leitor: o que entra, o que sai
contado e o que ABORTA (SystemExit) em vez de ingerir pela metade.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from rota.extract import checkins, comum, estrutura, pedidos, rota_mensal  # noqa: E402
from rota.utils import texto as T  # noqa: E402
from rota.utils.config import RAIZ  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="rota_testes_"))


def aborta(fn, *a) -> bool:
    try:
        fn(*a)
    except SystemExit:
        return True
    return False


# ------------------------------------------------------------------ texto
def test_numero_ptbr_ponto_e_sempre_milhar():
    s = pd.Series(["2952,5365", "17.734.952,08", "208.960", "14", ""])
    assert T.numero_ptbr(s).tolist()[:4] == [2952.5365, 17734952.08, 208960.0, 14.0]
    assert pd.isna(T.numero_ptbr(s).iloc[4])


def test_digitos_casa_os_tres_formatos():
    assert T.digitos(pd.Series(["0001010846", "1010846.0", 1010846])).tolist() == ["1010846"] * 3


def test_chave_texto_ignora_acento_caixa_e_espaco():
    assert T.chave_texto(" Cód.  cliente ") == "COD. CLIENTE"


# ------------------------------------------------------------------ check-ins
CAB_CI = "USUÁRIO;NOME USUÁRIO;DATA EVENTO;CÓDIGO CLIENTE;NOME CLIENTE;ENDEREÇO CLIENTE;CIDADE CLIENTE;ESTADO;EVENTO TIME LINE;DESCRIÇÃO TIMELINE;LATITUDE;LONGITUDE"


def _csv(nome: str, linhas: list[str]) -> Path:
    a = TMP / nome
    a.write_text("\n".join(linhas) + "\n", encoding="cp1252")
    return a


def test_checkins_tira_repetida_e_login_de_teste_contando():
    l1 = "ABC;Fulano;03/09/2026 10:00:00;1000001;LOJA A;RUA X;SAO PAULO;SP;CHECKIN;Checkin;-24;-47"
    l2 = "ABC;Fulano;03/09/2026 10:20:00;1000001;LOJA A;RUA X;SAO PAULO;SP;CHECKOUT;Checkout;-24;-47"
    l3 = "TESTERTM;Teste RTM;03/09/2026 11:00:00;1000002;LOJA B;RUA Y;SAO PAULO;SP;CHECKIN;Checkin;-24;-47"
    df, x = checkins.ler_arquivo(_csv("ci_ok.csv", [CAB_CI, l1, l1, l2, l3]))
    assert (x["lidas"], x["repetidas"], x["logins_ignorados"], len(df)) == (4, 1, 1, 2)
    assert x["meses"] == ["2026-09"] and df["EVENTO"].tolist() == ["CHECKIN", "CHECKOUT"]
    assert "LATITUDE" not in df.columns and "ENDERECO" not in " ".join(df.columns)   # minimização


def test_checkins_data_invalida_aborta():
    ruim = "ABC;Fulano;2026-09-03 10:00;1000001;LOJA A;RUA X;SAO PAULO;SP;CHECKIN;Checkin;-24;-47"
    assert aborta(checkins.ler_arquivo, _csv("ci_data.csv", [CAB_CI, ruim]))


def test_checkins_coluna_ausente_aborta():
    assert aborta(checkins.ler_arquivo, _csv("ci_col.csv", ["USUÁRIO;DATA EVENTO", "ABC;03/09/2026 10:00:00"]))


def test_checkins_evento_desconhecido_aborta():
    ruim = "ABC;Fulano;03/09/2026 10:00:00;1000001;LOJA A;RUA X;SAO PAULO;SP;PAUSA;x;-24;-47"
    assert aborta(checkins.ler_arquivo, _csv("ci_ev.csv", [CAB_CI, ruim]))


# ------------------------------------------------------------------ pedidos
CAB_PD = ("Pedido;Código;Cliente;Ordem de compra;Data de emissão;Data Estimada de Entrega;Sit. Embarque;Data de faturamento;Situação;"
          "Valor total do pedido;Quantidade solicitada;Representante;Cidade;UF;Nota fiscal;Cliente CNPJ;Valor total bruto;Desconto médio;Valor desconto;Preço médio liquido")
P1 = "1/1;1000001;LOJA A;;03/09/2026;10/09/2026;Não embarcado;;Aberto;1.000,50;10;116;SAO PAULO;SP;0;11111111000111;1.500,50;33,3;500,00;100,05"
P2 = "1/2;1000002;LOJA B;;04/09/2026;11/09/2026;Não embarcado;05/09/2026;Faturado;2000;20;116;SAO PAULO;SP;1-1;22222222000122;3000;33,3;1000;100"


def test_pedidos_rodape_vira_gabarito_e_sai_dos_dados():
    rod = ";;;;;;;;;3.000,50;30;;;;;;4.500,50;33,3;1.500,00;100"
    df, x = pedidos.ler_arquivo(_csv("pd_ok.csv", [CAB_PD, P1, P2, rod]))
    assert len(df) == 2 and x["rodape"] == 1 and x["gabarito"]["VALOR_PEDIDO"] == 3000.5
    assert df["VALOR_PEDIDO"].tolist() == [1000.5, 2000.0] and "CNPJ" not in " ".join(df.columns)
    assert pd.isna(df["DATA_FATURAMENTO"].iloc[0]) and df["DATA_FATURAMENTO"].iloc[1] == pd.Timestamp("2026-09-05")


def test_pedidos_truncado_nao_reconcilia_e_aborta():
    rod = ";;;;;;;;;3.000,50;30;;;;;;4.500,50;33,3;1.500,00;100"
    assert aborta(pedidos.ler_arquivo, _csv("pd_trunc.csv", [CAB_PD, P1, rod]))


def test_pedidos_numero_repetido_aborta():
    assert aborta(pedidos.ler_arquivo, _csv("pd_dup.csv", [CAB_PD, P1, P1]))


# ------------------------------------------------------------------ rota
def _rota(nome: str, datas: list[str], clientes: list[int], col_data: str = "Datas Rota Outubro") -> Path:
    n = len(clientes)
    df = pd.DataFrame({"Supervisor": ["Marco"] * n, "Executivo": ["FULANO SILVA"] * n, "Cód. cliente": clientes,
                       "canal": ["PRESENCIAL"] * n, col_data: pd.to_datetime(datas), "cidade": ["ITU"] * n,
                       "Net Sales 25": [1.0] * n, "Frequência anual 2025": [4] * n, "Net Sales 26": [2.0] * n,
                       "Frequência anual 2026": [5] * n, "Volume 25": [3.0] * n, "Volume 26": [4.0] * n})
    a = TMP / nome
    df.to_excel(a, sheet_name="Base de Clientes", index=False)
    return a


def test_rota_mes_vem_do_conteudo_e_nao_do_nome_da_coluna():
    df, x = rota_mensal.ler_arquivo(_rota("Rota_a.xlsx", ["2026-10-01", "2026-10-02"], [1000001, 1000002]))
    assert x["mes"] == "2026-10" and x["coluna_data"] == "Datas Rota Outubro"
    assert df["COD_CLIENTE"].tolist() == ["1000001", "1000002"] and df["SUPERVISOR"].iloc[0] == "Marco"


def test_rota_com_dois_meses_aborta():
    assert aborta(rota_mensal.ler_arquivo, _rota("Rota_b.xlsx", ["2026-10-01", "2026-11-02"], [1000001, 1000002]))


def test_rota_cliente_repetido_aborta():
    assert aborta(rota_mensal.ler_arquivo, _rota("Rota_c.xlsx", ["2026-10-01", "2026-10-02"], [1000001, 1000001]))


def test_rota_sem_coluna_de_data_aborta():
    assert aborta(rota_mensal.ler_arquivo, _rota("Rota_d.xlsx", ["2026-10-01"], [1000001], col_data="Quando"))


# ------------------------------------------------------------------ comum / estrutura
def test_mesmo_mes_em_dois_arquivos_aborta():
    assert aborta(comum.conferir_meses, "checkins", {"a.csv": ["2026-09"], "b.csv": ["2026-09", "2026-10"]})
    comum.conferir_meses("checkins", {"a.csv": ["2026-09"], "b.csv": ["2026-10"]})    # meses distintos: passa


def test_modelo_do_depara_e_lido_e_aponta_o_que_falta():
    modelo = RAIZ / "docs" / "DePara_Estrutura_Rota_MODELO.xlsx"
    if not modelo.exists():
        print("   (modelo do de-para ausente: teste pulado)")
        return
    df, x = estrutura.ler_arquivo(modelo)
    ex, vi = estrutura.separar(df)
    assert x["executivos"] == len(ex) > 0 and len(vi) > 0
    assert not vi["VISAO"].str.upper().str.startswith("EXEMPLO").any()          # a linha de exemplo não entra
    rota = pd.DataFrame({"EXECUTIVO": ex["EXECUTIVO"], "SUPERVISOR": ex["SUPERVISOR"]})
    ci = pd.DataFrame({"LOGIN": ["XYZ"]})
    prob = estrutura.conferir(ex, vi, rota, ci)
    assert any("sem LOGIN_MERCANET" in p for p in prob) and any("XYZ" in p for p in prob)   # modelo em branco => pendências listadas
    assert any("sem PASTA_USUARIO" in p for p in prob)


if __name__ == "__main__":
    testes = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    falhas = 0
    for nome, fn in testes:
        try:
            fn()
            print(f"  ok    {nome}")
        except Exception as e:                                   # noqa: BLE001
            falhas += 1
            print(f" FALHA  {nome}: {type(e).__name__}: {e}")
    print(f"\n{len(testes) - falhas}/{len(testes)} testes ok")
    sys.exit(1 if falhas else 0)
