# -*- coding: utf-8 -*-
"""Reconciliação do modelo com o protótipo `Painel Referência/painel_execucao_rota_22.html`.

Fora do pipeline. Refaz em Python a conta do protótipo (função `calcMetrics` do
JavaScript dele) sobre os dados EMBUTIDOS nele e compara, vendedor a vendedor,
com `rota.metricas.kpis` sobre a camada curada. Só faz sentido enquanto as bases
em `bases/` forem as mesmas do protótipo (dados até 16/09/2026): o script confere
isso antes de comparar.

    python ferramentas/reconciliar_prototipo2.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ))
for _f in (sys.stdout, sys.stderr):
    _f.reconfigure(encoding="utf-8")

from rota import metricas  # noqa: E402
from rota.load import parquet  # noqa: E402

PROTO = RAIZ / "Painel Referência" / "painel_execucao_rota_22.html"
COLS = ["ROTEIRO", "VISITADAS_NO_DIA", "FORA_DO_ROTEIRO", "COM_PEDIDO", "VISITA_E_PEDIDO", "SEM_CONTATO", "TEL_ROTEIRO", "TEL_COM_PEDIDO"]


def prototipo(dono: dict[str, str]) -> tuple[pd.DataFrame, pd.Timestamp]:
    """`dono`: cliente -> EXECUTIVO do modelo. O vendedor do protótipo é identificado pelos CLIENTES dele
    (o protótipo usa rótulos próprios, ex.: "Híberido" para o executivo híbrido), nunca pelo nome."""
    linha = next(l for l in PROTO.read_text(encoding="utf-8").splitlines() if l.startswith("const D="))
    D = json.loads(linha[len("const D="):linha.index(", M=D.meta")])
    C = {c: i for i, c in enumerate(D["cols"])}
    fim = next(i for i, d in enumerate(D["dias"]) if d["d"] == D["meta"]["ci_fim"])
    dias = set(range(fim + 1))
    sup_tel = D["sups"].index("Anderson")
    out = {}
    for c in D["cli"]:
        o = out.setdefault(dono.get(str(c[C["cli"]]), "PROTOTIPO: " + D["execs"][c[C["exec"]]]["raw"]), dict.fromkeys(COLS + ["VALOR_1o_PEDIDO"], 0))
        tel = c[C["sup"]] == sup_tel and not c[C["pres"]]
        r = c[C["rota"]]
        if r in dias:
            v = next((x for x in c[C["vis"]] if x[0] == r), None)
            p = next((x for x in c[C["ped"]] if x[0] in (r, r + 1)), None)          # o protótipo usa só o 1º pedido da janela
            if tel:
                o["TEL_ROTEIRO"] += 1; o["TEL_COM_PEDIDO"] += bool(p)
            else:
                o["ROTEIRO"] += 1; o["VISITADAS_NO_DIA"] += bool(v); o["COM_PEDIDO"] += bool(p)
                o["VISITA_E_PEDIDO"] += bool(v and p); o["SEM_CONTATO"] += not (v or p); o["VALOR_1o_PEDIDO"] += p[1] if p else 0
        if not tel and any(x[0] in dias and x[0] != r for x in c[C["vis"]]):
            o["FORA_DO_ROTEIRO"] += 1
    return pd.DataFrame(out).T.rename_axis("EXECUTIVO").reset_index(), pd.Timestamp(D["meta"]["ci_fim"])


def main() -> int:
    L, fv, cal, fp = (parquet.carregar(n) for n in ("LOJA_MES", "FATO_VISITA", "DIM_CALENDARIO", "FATO_PEDIDO"))
    P, fim = prototipo(dict(zip(L["COD_CLIENTE"], L["EXECUTIVO"])))
    if fv["DATA"].max() != fim:
        print(f"As bases atuais vao ate {fv['DATA'].max():%d/%m/%Y}; o prototipo, ate {fim:%d/%m/%Y}. A comparacao so vale com as MESMAS bases.")
        return 2
    dias = cal[(cal["ANO_MES"] == fim.strftime("%Y-%m")) & (cal["DATA"] <= fim)]["DATA"]
    K = metricas.kpis(L, fv, fp, dias, por="EXECUTIVO", criterio="janela")       # o protótipo usa a regra da janela (D-25)
    j = P.merge(K, on="EXECUTIVO", how="outer", suffixes=("_PROTO", ""))
    print(f"Mes ate {fim:%d/%m/%Y} · {len(j)} vendedores · prototipo x modelo\n")
    dif_total = 0
    for c in COLS:
        a, b = j[c + "_PROTO"].fillna(0).astype(int), j[c].fillna(0).astype(int)
        d = j[a != b]
        dif_total += len(d)
        print(f"  {c:<18} prototipo {a.sum():>6,} | modelo {b.sum():>6,} | " + ("IGUAL em todos os vendedores" if d.empty else
              "DIFERENTE em: " + "; ".join(f"{e} ({x} x {y})" for e, x, y in zip(d["EXECUTIVO"], a[d.index], b[d.index]))))
    print(f"\n  VALOR dos pedidos   prototipo (so o 1o pedido da janela) R$ {j['VALOR_1o_PEDIDO'].sum():,.2f} | modelo (todos os pedidos da janela) R$ {j['VALOR_PEDIDOS'].sum():,.2f}")
    print(f"\n{'RECONCILIADO: contagens identicas.' if dif_total == 0 else f'{dif_total} diferenca(s) de contagem — explicar antes de aceitar.'}")
    return 0 if dif_total == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
