# -*- coding: utf-8 -*-
"""Do JSON do painel ao HTML autocontido.

`template/template.html` é editado à mão: toda a interface vive lá, nenhuma
linha de HTML/CSS/JS nasce em Python. Aqui acontece UMA substituição de texto:
o marcador de dados recebe o JSON compactado (gzip + base64), que o navegador
descompacta na abertura com `DecompressionStream` — sem rede, sem servidor,
abre por duplo clique (mesmo desenho do DN e do Gerencial).
"""
from __future__ import annotations

import base64
import gzip
import json
import re
from pathlib import Path

from .utils.config import CFG, PASTA_PAINEL, PASTA_TEMPLATE
from .utils.log import abortar

MARCADOR = "/*__PAINEL_DADOS__*/"
_EXTERNO = re.compile(r"""(?:src|href)\s*=\s*["']https?://|@import|url\(\s*["']?https?://""", re.I)


def slug(rotulo: str) -> str:
    import unicodedata
    s = unicodedata.normalize("NFD", rotulo.lower())
    s = "".join(c for c in s if unicodedata.category(c) != "Mn")
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def gerar(J: dict, nome_arquivo: str) -> Path:
    tpl = (PASTA_TEMPLATE / "template.html").read_text(encoding="utf-8")
    if tpl.count(MARCADOR) != 1:
        abortar(f"template.html: o marcador {MARCADOR} tem de existir exatamente 1 vez (achei {tpl.count(MARCADOR)}).")
    if _EXTERNO.search(tpl):
        abortar("template.html referencia recurso externo (http/https). O painel tem de abrir offline: embuta o recurso.")
    bruto = json.dumps(J, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    carga = json.dumps({"z": "gzip+base64", "bytes": len(bruto), "b64": base64.b64encode(gzip.compress(bruto, 9, mtime=0)).decode("ascii")})
    html = tpl.replace(MARCADOR, "const PAYLOAD=" + carga + ";")
    teto = float(CFG["validacao"]["html_max_mb"]) * 1024 * 1024
    if len(html.encode("utf-8")) > teto:
        abortar(f"{nome_arquivo}: {len(html.encode('utf-8')) / 1048576:.1f} MB, acima do teto de {CFG['validacao']['html_max_mb']} MB (validacao.html_max_mb).")
    PASTA_PAINEL.mkdir(parents=True, exist_ok=True)
    alvo = PASTA_PAINEL / nome_arquivo
    tmp = alvo.with_suffix(".tmp")
    tmp.write_text(html, encoding="utf-8", newline="\n")
    tmp.replace(alvo)
    return alvo
