# -*- coding: utf-8 -*-
"""O que os leitores têm em comum: achar os arquivos de uma fonte, conferir as
colunas obrigatórias e garantir que cada mês vem de UM arquivo só."""
from __future__ import annotations

from pathlib import Path

import pandas as pd

from ..utils.config import CFG, caminho
from ..utils.log import abortar
from ..utils.texto import chave_texto


def arquivos(fonte: str) -> list[Path]:
    """Arquivos da fonte declarados no config (só a pasta, sem subpastas:
    `_versoes/` e afins não são lidas). Temporários do Excel (`~$`) ficam fora."""
    cfg = CFG["fontes"][fonte]
    pasta = caminho(cfg["pasta"])
    if not pasta.exists():
        return []
    out: set[Path] = set()
    for padrao in cfg["padroes_aceitos"]:
        out |= {a for a in pasta.glob(padrao) if a.is_file() and not a.name.startswith("~$")}
    return sorted(out)


def mapear_colunas(df: pd.DataFrame, mapa: dict[str, str], arq: Path) -> pd.DataFrame:
    """Renomeia pelas colunas do config, comparando sem acento/caixa/espaço duplo.
    Coluna obrigatória ausente aborta — nunca se ingere pela metade."""
    achadas = {chave_texto(c): c for c in df.columns}
    faltam = [orig for orig in mapa if chave_texto(orig) not in achadas]
    if faltam:
        abortar(f"{arq.name}: coluna(s) obrigatoria(s) ausente(s): {faltam}\n"
                f"  colunas encontradas: {list(df.columns)}")
    ren = {achadas[chave_texto(orig)]: novo for orig, novo in mapa.items()}
    return df[list(ren)].rename(columns=ren)


def conferir_meses(fonte: str, por_arquivo: dict[str, list[str]]) -> None:
    """Um mês só pode vir de um arquivo por fonte. Dois arquivos com o mesmo mês
    = extração antiga esquecida na pasta ou cópia de conflito do OneDrive: somar
    os dois dobraria o mês, então aborta listando os arquivos."""
    dono: dict[str, str] = {}
    for arq, meses in por_arquivo.items():
        for m in meses:
            if m in dono:
                abortar(f"{fonte}: o mes {m} aparece em DOIS arquivos: '{dono[m]}' e '{arq}'.\n"
                        "  Substitua o arquivo do mes, nunca adicione: mova a versao antiga para uma subpasta "
                        "(ex.: _versoes/) e rode de novo.")
            dono[m] = arq


def datas(s: pd.Series, formatos) -> pd.Series:
    """Converte texto em data tentando cada formato declarado, em ordem (D-42: o Mercanet já mandou com e sem segundos).
    Aceita um formato (texto) ou uma lista. O que não casa com nenhum fica NaT — quem chama decide se aborta."""
    formatos = [formatos] if isinstance(formatos, str) else list(formatos)
    s = s.astype("string").str.strip().replace("", pd.NA)
    out = pd.Series(pd.NaT, index=s.index, dtype="datetime64[ns]")
    for f in formatos:
        falta = out.isna() & s.notna()
        if not falta.any():
            break
        out[falta] = pd.to_datetime(s[falta], format=f, errors="coerce")
    return out
