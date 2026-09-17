# -*- coding: utf-8 -*-
"""Normalização de tipos vindos do Excel e dos CSVs do Mercanet.

Adaptado de `dn/utils/texto.py` (Scorecard DN). O que estas funções fazem:
tirar sujeira de FORMATO (espaço duplo, `.0` de float, célula vazia que vira a
string "nan"). O que elas NÃO fazem: corrigir grafia, mapear valor ou decidir
precedência — isso é decisão de negócio e vive no config ou no de-para.
"""
from __future__ import annotations

import re
import unicodedata

import pandas as pd

_RE_ESPACO = re.compile(r"\s+")


def texto(s: pd.Series, maiuscula: bool = True) -> pd.Series:
    """Trim + colapsa espaços + (opcional) MAIÚSCULA. Vazio vira <NA>."""
    out = (s.astype("string").str.strip()
            .str.replace(_RE_ESPACO, " ", regex=True))
    if maiuscula:
        out = out.str.upper()
    return out.replace({"": pd.NA, "NAN": pd.NA, "NONE": pd.NA, "nan": pd.NA})


def digitos(s: pd.Series) -> pd.Series:
    """Só os dígitos, sem zeros à esquerda. Tolera float (`1010846.0`), int e
    texto zero-preenchido (`0001010846`): as três bases precisam casar pelo
    mesmo código de cliente."""
    out = (s.astype("string")
            .str.replace(r"\.0+$", "", regex=True)
            .str.replace(r"\D", "", regex=True)
            .str.lstrip("0"))
    return out.replace({"": pd.NA})


def numero_ptbr(s: pd.Series) -> pd.Series:
    """Float a partir do formato brasileiro dos CSVs do Mercanet: vírgula
    decimal, ponto de milhar (`2952,5365`, `17.734.952,08`, `208.960`).

    Estrito de propósito: o ponto é SEMPRE milhar. O rodapé de `Pedidos.csv`
    traz `208.960` (208 mil), que um leitor tolerante leria como 208,96. Se a
    origem um dia mudar de locale, a reconciliação contra o rodapé acusa."""
    if pd.api.types.is_numeric_dtype(s):
        return pd.to_numeric(s, errors="coerce")
    txt = (s.astype("string").str.strip()
            .str.replace(".", "", regex=False)
            .str.replace(",", ".", regex=False))
    return pd.to_numeric(txt, errors="coerce")


def chave_texto(v) -> str:
    """Texto sem acento, em maiúscula, com espaços colapsados — para COMPARAR
    nomes de coluna e rótulos. Nunca é gravado como dado."""
    t = unicodedata.normalize("NFD", str(v))
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return _RE_ESPACO.sub(" ", t).strip().upper()
