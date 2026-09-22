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

from rota.extract import checkins, clientes, comum, estrutura, pedidos, rota_mensal, sellin  # noqa: E402
from rota.utils import texto as T  # noqa: E402
from rota.utils.config import CFG, RAIZ  # noqa: E402

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


def test_checkins_aceita_data_sem_segundos_e_mistura():
    """D-42: a extração de 22/09/2026 veio sem segundos; os dois formatos convivem no mesmo arquivo."""
    l1 = "ABC;Fulano;15/09/2026 13:00;1000001;LOJA A;RUA X;SAO PAULO;SP;CHECKIN;Checkin;-24;-47"
    l2 = "ABC;Fulano;15/09/2026 13:20:30;1000001;LOJA A;RUA X;SAO PAULO;SP;CHECKOUT;Checkout;-24;-47"
    df, _ = checkins.ler_arquivo(_csv("ci_min.csv", [CAB_CI, l1, l2]))
    assert df["DATA_HORA"].tolist() == [pd.Timestamp("2026-09-15 13:00"), pd.Timestamp("2026-09-15 13:20:30")]


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


CAB_H = ["(N1)\nCÓDIGO HEAD", "CRIAR NO BI\n(N1)\nHEAD", "(N1)\nNOME HEAD", "(N2)\nCÓDIGO GERENTE", "(N2)\nGERENTE", "(N2)\nNOME GERENTE",
         "(N3)\nCÓDIGO SUP./EXEC.", "(N3)\nSUP./EXEC.", "(N3)\nNOME SUP./EXEC.", "(N4)\nCÓDIGO VEND./RCA", "(N4)\nVEND./RCA",
         "(N4)\nNOME VEND./RCA", "PROJETO", "LOGIN MERCATNET", "NOME MERCANET"]


def _hier(nome: str, n4: list[tuple]) -> Path:
    """n4 = (cod N2, gerente, cod N3, supervisor, cod N4, nome N4, login)."""
    linhas = [[20, "ATACADO", "HEAD UM", g, "Ger", gn, s, "Superv", sn, c, "Vend", n, "Projeto Rota", lg, None] for g, gn, s, sn, c, n, lg in n4]
    a = TMP / nome
    pd.DataFrame(linhas, columns=CAB_H).to_excel(a, sheet_name="Hierarquia", index=False)
    return a


H_OK = [(21000, "GER A", 2110, "MARCO MASSON", 101, "FULANO SILVA", "FSILVA"), (21000, "GER A", 2110, "MARCO MASSON", 103, "BELTRANO SOUZA", None),
        (21000, "GER A", 2120, "ROBSON DIAS", 118, "[VAGO]", None), (22000, "GER B", 2220, "ADRIANA MIRANDA", 127, "CICRANO LIMA", "CLIMA")]


def test_hierarquia_cabecalho_com_quebra_e_visoes_derivadas():
    df, x = estrutura.ler_arquivo(_hier("h_ok.xlsx", H_OK))
    assert (x["posicoes"], x["n1"], x["n2"], x["n3"], x["com_login"]) == (4, 1, 2, 3, 2)
    assert df["N3_ROTULO"].iloc[0] == "2110 - Superv - MARCO MASSON" and df["LOGIN_MERCANET"].iloc[0] == "FSILVA"
    v = estrutura.visoes(df)
    assert v["NIVEL"].value_counts().to_dict() == {"N3": 3, "N2": 2, "N1": 1}
    assert v[(v.NIVEL == "N2") & (v.COD == "21000")]["N3_CODS"].iloc[0] == ["2110", "2120"]      # o gerente vê as duas supervisões


def test_hierarquia_codigo_n4_repetido_aborta():
    assert aborta(estrutura.ler_arquivo, _hier("h_dup.xlsx", H_OK + [(22000, "GER B", 2220, "ADRIANA MIRANDA", 127, "OUTRO", None)]))


def test_hierarquia_supervisor_com_dois_gerentes_aborta():
    assert aborta(estrutura.ler_arquivo, _hier("h_pai.xlsx", H_OK + [(22000, "GER B", 2110, "MARCO MASSON", 140, "OUTRO", None)]))


def test_conferir_por_nome_aponta_vago_repetido_faltantes_e_logins():
    df, _ = estrutura.ler_arquivo(_hier("h_vago.xlsx", H_OK + [(21000, "GER A", 2120, "ROBSON DIAS", 121, "[VAGO]", None)]))
    rota = pd.DataFrame({"EXECUTIVO": ["FULANO SILVA", "[VAGO]", "NOVATO"], "SUPERVISOR": ["Marco", "Robson", "Adriana"],
                         "COD_VENDEDOR": pd.array([pd.NA] * 3, dtype="string")})
    prob = " | ".join(estrutura.conferir(df, rota, pd.DataFrame({"LOGIN": ["FSILVA", "XYZ"]})))
    assert "NOME nao e unico" in prob and "[VAGO]" in prob                   # 2 posições [VAGO]: ambíguo por nome
    assert "NOVATO" in prob and "XYZ" in prob and "sem LOGIN MERCANET" in prob


def test_conferir_por_codigo_resolve_o_vago_e_acusa_supervisor_trocado():
    df, _ = estrutura.ler_arquivo(_hier("h_cod.xlsx", H_OK + [(21000, "GER A", 2120, "ROBSON DIAS", 121, "[VAGO]", None)]))
    rota = pd.DataFrame({"EXECUTIVO": ["FULANO SILVA", "BELTRANO SOUZA", "[VAGO]", "[VAGO]", "CICRANO LIMA"],
                         "SUPERVISOR": ["Marco", "Marco", "Robson", "Robson", "Marco"],
                         "COD_VENDEDOR": pd.array(["101", "103", "118", "121", "127"], dtype="string")})
    prob = estrutura.conferir(df, rota, pd.DataFrame({"LOGIN": ["FSILVA", "CLIMA"]}))
    assert not any("nao e unico" in p or "sem posicao" in p for p in prob)   # por código, dois [VAGO] não são problema
    assert any("supervisor da rota nao bate" in p and "CICRANO LIMA" in p for p in prob)


def test_hierarquia_coluna_encerrada_em_e_opcional_e_marca_a_posicao():
    """D-45: sem a coluna, toda posicao e ativa; com data, a posicao e encerrada (sem exigir login nem loja no mes corrente)."""
    df, x = estrutura.ler_arquivo(_hier("h_semcol.xlsx", H_OK))
    assert x["encerradas"] == 0 and df["ATIVA"].all()
    a = TMP / "h_enc.xlsx"
    linhas = [[20, "ATACADO", "HEAD UM", g, "Ger", gn, s, "Superv", sn, c, "Vend", n, "Projeto Rota", lg, None, enc]
              for (g, gn, s, sn, c, n, lg), enc in zip(H_OK, [None, "2026-09-30", None, None])]
    pd.DataFrame(linhas, columns=CAB_H + ["ENCERRADA EM"]).to_excel(a, sheet_name="Hierarquia", index=False)
    df, x = estrutura.ler_arquivo(a)
    assert x["encerradas"] == 1 and df.set_index("N4_COD")["ATIVA"].to_dict() == {"101": True, "103": False, "118": True, "127": True}
    rota = pd.DataFrame({"ANO_MES": ["2026-09", "2026-10", "2026-10", "2026-10"], "EXECUTIVO": ["BELTRANO SOUZA", "FULANO SILVA", "[VAGO]", "CICRANO LIMA"],
                         "SUPERVISOR": ["Marco", "Marco", "Robson", "Adriana"], "COD_VENDEDOR": pd.array(["103", "101", "118", "127"], dtype="string")})
    prob = " | ".join(estrutura.conferir(df, rota, pd.DataFrame({"LOGIN": ["FSILVA"]}), mes_corrente="2026-10"))
    assert "103" not in prob                                                   # encerrada: sem login e sem loja em outubro, tudo bem
    assert "118" in prob and "sem LOGIN" in prob                               # ativa sem login continua sendo problema


def test_rota_com_codigo_do_vendedor():
    a = _rota("Rota_e.xlsx", ["2026-10-01", "2026-10-02"], [1000001, 1000002])
    d = pd.read_excel(a, sheet_name="Base de Clientes"); d.insert(2, "Cód. vendedor", [101, 101])
    d.to_excel(a, sheet_name="Base de Clientes", index=False)
    df, x = rota_mensal.ler_arquivo(a)
    assert x["com_codigo_vendedor"] and df["COD_VENDEDOR"].tolist() == ["101", "101"]
    d.loc[1, "Cód. vendedor"] = None; d.to_excel(a, sheet_name="Base de Clientes", index=False)
    assert aborta(rota_mensal.ler_arquivo, a)                                # coluna presente tem de vir completa


# ------------------------------------------------------------------ sell-in do BI (D-42)
_FILTRO = "Filtros aplicados:\nAno mês é 2026/09"
_CAB_SI_CART = ["Ano mês", "Número pedido", "Data Pedido", "Cód. cliente", "Receita Líquida Carteira Total"]
_CAB_SI_CLI = ["Ano mês", "Cód. cliente", "Cliente", "Bandeira cliente", "Cidade", "Nome Head Vendas (N1)", "Nome Gerente Vendas (N2)",
               "Nome Executivo Vendas (N3)", "Nome Vendedor Novo (N4)", "Receita Líquida Orçamento", "Receita Líquida Carteira Total",
               "Receita Líquida", "Receita Líquida LY"]


def _xlsx(nome: str, cab: list[str], linhas: list[list]) -> Path:
    a = TMP / nome
    pd.DataFrame(linhas, columns=cab).to_excel(a, index=False)
    return a


def _cart(nome: str, linhas: list[list], total: float | None) -> Path:
    rod = ([["Total", None, None, None, total]] if total is not None else []) + [[None] * 5, [_FILTRO, None, None, None, None]]
    return _xlsx(nome, _CAB_SI_CART, linhas + rod)


def test_sellin_rodape_vira_gabarito_e_sai_dos_dados():
    L = [["2026/09", "0111000001", pd.Timestamp("2026-09-10"), "0001004628", 100.5], ["2026/09", "0111000002", pd.Timestamp("2026-08-20"), "0001004629", -20.0]]
    df, x = sellin.ler_arquivo(_cart("si_ok.xlsx", L, 80.5), "carteira")
    assert (len(df), x["rodape"], x["gabarito"]["CARTEIRA"]) == (2, 3, 80.5)
    assert df["COD_CLIENTE"].tolist() == ["1004628", "1004629"] and df["ANO_MES"].tolist() == ["2026-09"] * 2
    assert x["filtros"].startswith("Filtros aplicados")


def test_sellin_truncado_linha_estranha_e_pedido_repetido_abortam():
    L = [["2026/09", "0111000001", pd.Timestamp("2026-09-10"), "0001004628", 100.5]]
    assert aborta(sellin.ler_arquivo, _cart("si_trunc.xlsx", L, 999.0), "carteira")
    assert aborta(sellin.ler_arquivo, _cart("si_estr.xlsx", L + [["Subtotal", None, None, None, 1.0]], 100.5), "carteira")
    assert aborta(sellin.ler_arquivo, _cart("si_dup.xlsx", L + L, 201.0), "carteira")


def test_sellin_codigo_do_vendedor_sai_do_n4_e_conferencia_aponta_diferenca():
    cli = [["2026/09", "0001004628", "LOJA A", "A", "BH", "ADEMIR", "G (22000)", "S (2220)", "RODRIGO MATOS (128)", 10.0, 100.5, 50.0, None],
           ["2026/09", "0001004629", "LOJA B", "B", "BH", "ADEMIR", "G (22000)", "S (2220)", "PATRICIA ALVES (135)", 10.0, None, None, None]]
    rod = [["Total", None, None, None, None, None, None, None, None, 20.0, 100.5, 50.0, None]]
    c, _ = sellin.ler_arquivo(_xlsx("si_cli.xlsx", _CAB_SI_CLI, cli + rod), "cliente")
    assert c["COD_VENDEDOR"].tolist() == ["128", "135"]
    cart, _ = sellin.ler_arquivo(_cart("si_c2.xlsx", [["2026/09", "0111000001", pd.Timestamp("2026-09-10"), "0001004628", 100.5]], 100.5), "carteira")
    fat = pd.DataFrame({"COD_CLIENTE": ["1004628", "1004629"], "RECEITA": [50.0, 7.0]})
    avisos, lista = sellin.conferir({"cliente": c, "carteira": cart, "faturado": fat})
    assert len(avisos) == 1 and lista["COD_CLIENTE"].tolist() == ["1004629"]      # carteira fecha; faturado do 1004629 nao esta no cliente


def _pasta_sellin(pasta: Path, mes: str) -> None:
    """Os 3 exports de um mes numa pasta, com os nomes do config."""
    pasta.mkdir(parents=True, exist_ok=True)
    nomes = {k: a["arquivo"] for k, a in CFG["fontes"]["sellin"]["arquivos"].items()}
    am = mes.replace("-", "/")
    cli = [[am, "0001004628", "LOJA A", "A", "BH", "H", "G (22000)", "S (2220)", "RODRIGO MATOS (128)", 10.0, 5.0, 50.0, None]]
    pd.DataFrame(cli + [["Total"] + [None] * 8 + [10.0, 5.0, 50.0, None]], columns=_CAB_SI_CLI).to_excel(pasta / nomes["cliente"], index=False)
    pd.DataFrame([[am, "0111000001", pd.Timestamp(mes + "-10"), "0001004628", 5.0], ["Total", None, None, None, 5.0]], columns=_CAB_SI_CART).to_excel(pasta / nomes["carteira"], index=False)
    fat = pd.DataFrame([[am, "0111000002", pd.Timestamp(mes + "-03"), pd.Timestamp(mes + "-05"), "0001004628", 50.0], ["Total", None, None, None, None, 50.0]],
                       columns=["Ano mês", "Numero Pedido", "Data Pedido", "Data Faturamento", "Cód. cliente", "Receita Líquida"])
    fat.to_excel(pasta / nomes["faturado"], index=False)


def test_sellin_raiz_e_mes_corrente_e_subpasta_e_mes_fechado():
    """D-45: raiz = corrente; subpasta AAAA-MM = mes fechado, cujo conteudo tem de ser desse mes."""
    base = TMP / "sellin_ok"
    _pasta_sellin(base, "2026-10"); _pasta_sellin(base / "2026-09", "2026-09")
    antes = CFG["fontes"]["sellin"]["pasta"]
    CFG["fontes"]["sellin"]["pasta"] = str(base)
    try:
        si = sellin.carregar(forcar=True)
        assert sorted(si) == ["2026-09", "2026-10"] and si["2026-09"]["faturado"]["RECEITA"].sum() == 50.0
        assert len(sellin.todos_arquivos()) == 6
        _pasta_sellin(base / "2026-08", "2026-07")                             # subpasta com mes errado aborta
        assert aborta(sellin.carregar, True)
    finally:
        CFG["fontes"]["sellin"]["pasta"] = antes


# ------------------------------------------------------------------ cadastro de nomes (D-38)
def _cli(nome: str, linhas: list[tuple]) -> Path:
    a = TMP / nome
    pd.DataFrame(linhas, columns=["Cód. cliente", "Nome Cliente"]).to_excel(a, index=False)
    return a


def test_clientes_le_codigo_e_nome_e_tolera_linha_repetida_igual():
    df, x = clientes.ler_arquivo(_cli("c_ok.xlsx", [(1010846.0, " loja  um "), ("0001010847", "LOJA DOIS"), (1010847, "LOJA DOIS")]))
    assert df[["COD_CLIENTE", "NOME_CLIENTE"]].values.tolist() == [["1010846", "LOJA UM"], ["1010847", "LOJA DOIS"]]
    assert (x["clientes"], x["repetidas_iguais"], x["maior_nome"]) == (2, 1, 9)


def test_clientes_mesmo_codigo_com_dois_nomes_ou_sem_codigo_aborta():
    assert aborta(clientes.ler_arquivo, _cli("c_dup.xlsx", [(1, "LOJA A"), (1, "LOJA B")]))
    assert aborta(clientes.ler_arquivo, _cli("c_sem.xlsx", [(None, "LOJA A"), (2, "LOJA B")]))


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
