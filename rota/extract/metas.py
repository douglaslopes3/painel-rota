# -*- coding: utf-8 -*-
"""Meta do sell-in por loja (D-52, 02/10/2026): o arquivo de METAS da pasta compartilhada, o MESMO que o Gerencial lê
(`../../bases compartilhadas/Metas_*.xlsx`; D-74 e D-87 do Gerencial).

Antes vinha do `Receita Líquida Orçamento` do export do BI (D-44). Medido em 02/10/2026: nos 3.731 clientes do export as
duas fontes são iguais (diferença máxima R$ 0,0003), mas o export filtra pelo vendedor da Hierarquia e deixa de fora as
12 lojas da rota cujo N4 na base é outro (D-49) — R$ 145.410,53 de meta em set/26 que o painel mostrava como zero.

Formato: 1 linha por CLIENTE × CATEGORIA × PERÍODO × TIPO DE META, valor em `Valor`. Daqui só sai a meta em R$ por
cliente × mês (soma das categorias). Regras iguais às do leitor do Gerencial, para os dois painéis não divergirem:
a competência vem do CONTEÚDO (`Período`: data, serial do Excel ou texto AAAA-MM), nunca do nome; o mesmo mês em dois
arquivos ABORTA; tipo de meta fora de `fontes.metas.tipos_meta` ABORTA; chave repetida, valor ou período vazio ABORTA;
a soma por mês depois de agrupar tem de bater com a soma bruta das linhas. Meta negativa entra como vem.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..utils.config import CFG, caminho
from ..utils.log import abortar
from ..utils.texto import digitos, texto
from .comum import mapear_colunas

_ORIGEM_EXCEL = pd.Timestamp("1899-12-30")      # serial do Excel (sistema 1900): 46266 = 01/09/2026


def arquivos() -> list[Path]:
    """Os `Metas_*.xlsx` da pasta (sem subpastas; temporários do Excel fora)."""
    cfg = CFG["fontes"].get("metas") or {}
    if not cfg:
        return []
    pasta = caminho(cfg["pasta"])
    if not pasta.is_dir():
        return []
    out: set[Path] = set()
    for padrao in cfg["padroes_aceitos"]:
        out |= {a for a in pasta.glob(padrao) if a.is_file() and not a.name.startswith("~$")}
    return sorted(out)


def ano_mes_periodo(s: pd.Series) -> pd.Series:
    """`Período` -> `AAAA-MM`: data, serial do Excel ou texto AAAA-MM / AAAA/MM. O que não casar vira <NA> (e aborta)."""
    if pd.api.types.is_datetime64_any_dtype(s):
        return s.dt.strftime("%Y-%m").astype("string")
    out = pd.Series(pd.NA, index=s.index, dtype="string")
    for i, v in s.items():
        if hasattr(v, "year") and hasattr(v, "month") and not isinstance(v, (int, float, str)):
            out[i] = f"{v.year:04d}-{v.month:02d}"
            continue
        t = str(v).strip() if v is not None and not (isinstance(v, float) and pd.isna(v)) else ""
        if t.replace(".0", "").isdigit() and 1 <= float(t) <= 80000:
            d = _ORIGEM_EXCEL + pd.Timedelta(days=float(t))
            out[i] = f"{d.year:04d}-{d.month:02d}"
        elif len(t) >= 7 and t[:4].isdigit() and t[4] in "-/" and t[5:7].isdigit() and 1 <= int(t[5:7]) <= 12:
            out[i] = f"{t[:4]}-{t[5:7]}"
    return out


def ler_arquivo(arq: Path) -> tuple[pd.DataFrame, dict]:
    """(ANO_MES, COD_CLIENTE, ORCADO) com a meta em R$ do cliente no mês; `extra` traz o gabarito bruto por mês."""
    cfg = CFG["fontes"]["metas"]
    aba = cfg.get("aba")
    try:
        bruto = pd.read_excel(arq, sheet_name=0 if aba is None else aba, engine="calamine")
    except ValueError:
        abortar(f"{arq.name}: aba '{aba}' nao encontrada.")
    df = mapear_colunas(bruto.dropna(how="all"), cfg["colunas"], arq).reset_index(drop=True)
    out = pd.DataFrame({"COD_CLIENTE": digitos(df["COD_CLIENTE"]), "CATEGORIA": texto(df["CATEGORIA"]),
                        "ANO_MES": ano_mes_periodo(df["PERIODO"]), "TIPO": texto(df["TIPO"]),
                        "VALOR": pd.to_numeric(df["VALOR"], errors="coerce")})
    for col in out.columns:
        ruins = out[col].isna()
        if ruins.any():
            abortar(f"{arq.name}: {int(ruins.sum()):,} linha(s) com {col} vazio ou irreconhecivel "
                    f"(linhas da planilha: {[int(i) + 2 for i in out.index[ruins][:5]]}). A meta nao entra pela metade.")
    tipos = {str(k).upper(): v for k, v in cfg["tipos_meta"].items()}
    fora = sorted(set(out["TIPO"]) - set(tipos))
    if fora:
        abortar(f"{arq.name}: 'Tipo Meta' fora de fontes.metas.tipos_meta: {fora} (aceitos: {sorted(tipos)}).")
    out["METRICA"] = out["TIPO"].map(tipos)
    chave = ["ANO_MES", "COD_CLIENTE", "CATEGORIA", "METRICA"]
    dup = out.duplicated(chave, keep=False)
    if dup.any():
        abortar(f"{arq.name}: {int(dup.sum()):,} linha(s) com a chave (mes, cliente, categoria, tipo) REPETIDA "
                f"(ex.: {out.loc[dup, chave].head(3).values.tolist()}). Meta repetida somaria em dobro.")
    r = out[out["METRICA"] == "META_RECEITA"]
    if r.empty:
        abortar(f"{arq.name}: nenhuma linha de meta em R$ (META_RECEITA).")
    gabarito = {am: float(v) for am, v in r.groupby("ANO_MES")["VALOR"].sum().items()}
    meta = r.groupby(["ANO_MES", "COD_CLIENTE"], as_index=False)["VALOR"].sum().rename(columns={"VALOR": "ORCADO"})
    for am, v in meta.groupby("ANO_MES")["ORCADO"].sum().items():
        if abs(v - gabarito[am]) > 0.01:
            abortar(f"{arq.name}: meta {am} agrupada ({v:,.2f}) difere da soma bruta do arquivo ({gabarito[am]:,.2f}).")
    meta["ARQUIVO_ORIGEM"] = arq.name
    return meta.astype({"ANO_MES": "string", "COD_CLIENTE": "string"}), {"meses": sorted(gabarito), "gabarito": gabarito,
                                                                         "linhas": int(len(out)), "clientes": int(meta["COD_CLIENTE"].nunique())}


def carregar(forcar: bool = False) -> tuple[pd.DataFrame | None, dict]:
    """Junta os arquivos da pasta; o mesmo mês em dois arquivos ABORTA (meta é substituída, nunca somada).
    Sem arquivo: (None, {}) — quem chama decide entre aviso e aborto."""
    from . import cache
    arqs = arquivos()
    if not arqs:
        return None, {}
    partes, dono = [], {}
    for arq in arqs:
        try:
            d, x = cache.ler(arq, ler_arquivo, forcar)
        except PermissionError:
            abortar(f"nao consegui abrir {arq.name}: o arquivo esta ABERTO em outro programa (Excel?). Feche e rode de novo.")
        for am in x["meses"]:
            if am in dono:
                abortar(f"o mes {am} aparece em DOIS arquivos de metas: {dono[am]} e {arq.name}. Deixe o mes em um arquivo so.")
            dono[am] = arq.name
        partes.append(d)
    return pd.concat(partes, ignore_index=True), {"arquivos": [a.name for a in arqs], "meses": sorted(dono)}


def conferir_bi(meta_mes: pd.DataFrame, cli_bi: pd.DataFrame, tolerancia: float = 0.01) -> tuple[list[str], pd.DataFrame]:
    """Só MEDE: orçado do export do BI × meta do arquivo, nos clientes do export. Diferença vira aviso + lista (não aborta)."""
    j = (cli_bi[["COD_CLIENTE", "ORCADO"]].groupby("COD_CLIENTE")["ORCADO"].sum().rename("ORCADO_BI").to_frame()
         .join(meta_mes.set_index("COD_CLIENTE")["ORCADO"].rename("META_ARQUIVO"), how="left").fillna(0.0))
    dif = j[(j["ORCADO_BI"] - j["META_ARQUIVO"]).abs() > tolerancia]
    avisos = []
    if len(dif):
        avisos.append(f"orcado do BI x arquivo de metas: {len(dif)} cliente(s) com diferenca (soma "
                      f"{(dif['ORCADO_BI'] - dif['META_ARQUIVO']).sum():,.2f}) — vale o arquivo de metas; algum dos dois foi revisado?")
    return avisos, dif.reset_index()
