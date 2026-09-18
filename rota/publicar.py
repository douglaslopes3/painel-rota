# -*- coding: utf-8 -*-
"""Etapa 6 · publicar: leva o HTML de cada visão para a pasta do usuário (D-05).

    <publicacao.destino>/<rótulo da hierarquia>/<painel.arquivo>
    ex.: Painéis Comerciais/Gerencial/2110 - Superv_SPC 1 - MARCO MASSON/Painel_Rota.html

Três modos, do mais inofensivo ao real:

    plano    (padrão)      só LISTA o que seria copiado e para onde. Não grava nada.
    ensaio   (--ensaio)    copia de verdade, mas para `publicacao.pasta_ensaio` (pasta local): exercita
                           a cópia, a conferência de md5 e o "sem mudança" sem tocar no destino real.
    publicar (--publicar)  copia para o destino real. Exige DUAS chaves: a flag na linha de comando E
                           `publicacao.liberada: true` no config — que só o Douglas vira, depois da
                           validação com o time (D-28). Uma sem a outra não publica.

Regras da cópia (as do DN): tudo ou nada — se alguma visão falhou na geração, NENHUMA é publicada
(os painéis de um nível somam o de cima; publicar metade deixaria os níveis inconsistentes); conteúdo
idêntico ao já publicado não é recopiado (o OneDrive não ressincroniza); a cópia vai para um `.tmp` e
troca de nome no fim; o md5 do destino é conferido depois. Nada é apagado na pasta do usuário: os
painéis do Gerencial e do DN moram lá.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
from pathlib import Path

from .utils import log as L
from .utils.config import CFG, caminho

MODOS = ("plano", "ensaio", "publicar")


def pasta_usuario(rotulo: str) -> str:
    """Pasta = rótulo completo, com os caracteres inválidos de pasta trocados por '-' ('Superv_PR/CO' -> 'Superv_PR-CO').
    É a mesma regra do DN, que criou as pastas de `Painéis Comerciais/Gerencial`."""
    return re.sub(r'[<>:"/\\|?*]', "-", str(rotulo)).strip(" .")[:100]


def _md5(arq: Path) -> str:
    h = hashlib.md5()
    with open(arq, "rb") as f:
        for bloco in iter(lambda: f.read(1 << 20), b""):
            h.update(bloco)
    return h.hexdigest()


def base(modo: str) -> Path:
    pub = CFG["publicacao"]
    return caminho(os.path.expandvars(str(pub["pasta_ensaio" if modo == "ensaio" else "destino"]))).resolve()


def plano(gerados: dict, modo: str) -> list[dict]:
    """`gerados`: rótulo da visão -> {"arquivo": caminho do HTML local, …}. Uma linha por visão, sem gravar nada."""
    raiz, nome = base(modo), CFG["painel"]["arquivo"]
    out = []
    for rotulo, g in sorted(gerados.items()):
        origem = Path(g["arquivo"])
        destino = raiz / pasta_usuario(rotulo) / nome
        md5 = _md5(origem)
        igual = destino.exists() and destino.stat().st_size == origem.stat().st_size and _md5(destino) == md5
        out.append({"rotulo": rotulo, "origem": str(origem), "destino": str(destino), "md5": md5, "pasta_existe": destino.parent.exists(),
                    "situacao": "sem mudanca" if igual else ("substitui" if destino.exists() else "novo")})
    return out


def _copiar(item: dict) -> str:
    origem, destino = Path(item["origem"]), Path(item["destino"])
    if not destino.parent.exists():
        if not CFG["publicacao"].get("criar_pasta", True):
            return f"erro: pasta inexistente ({destino.parent})"
        destino.parent.mkdir(parents=True, exist_ok=True)
        L.log(f"{item['rotulo']}: pasta criada em {destino.parent}", "aviso")
    if item["situacao"] == "sem mudanca" and CFG["publicacao"].get("pular_se_identico", True):
        return "sem mudanca"
    tmp = destino.with_name(destino.name + ".tmp")
    try:
        shutil.copyfile(origem, tmp)
        os.replace(tmp, destino)
    except OSError as e:
        return f"erro: {e}"
    return "publicado" if _md5(destino) == item["md5"] else "erro: md5 divergente apos a copia"


def executar(gerados: dict, falhas: list[str], modo: str = "plano") -> dict:
    """Devolve {"modo", "destino", "itens", "erros"}. Em `plano` nada é gravado."""
    if modo not in MODOS:
        raise ValueError(f"modo de publicacao invalido: {modo!r} (use {MODOS})")
    L.etapa_inicio(f"6 · PUBLICAR ({modo})")
    res = {"modo": modo, "destino": str(base(modo)), "itens": [], "erros": []}

    def fim(situacao: str) -> dict:
        L.etapa_fim(situacao, modo=modo, itens=len(res["itens"]), erros=len(res["erros"]))
        return res

    if not gerados:
        L.log("nenhum painel gerado nesta execucao: nada a publicar", "aviso")
        return fim("pulada")
    if modo == "publicar" and not CFG["publicacao"].get("liberada", False):
        res["erros"].append("publicacao NAO liberada no config (publicacao.liberada: false — D-28)")
        L.log("--publicar pedido, mas `publicacao.liberada` esta false no config (D-28: so depois da validacao com o time). "
              "NADA foi publicado. Para ensaiar a copia sem tocar no destino real, use --ensaio.", "erro")
        return fim("bloqueada")
    if falhas and modo != "plano":
        res["erros"].append(f"{len(falhas)} falha(s) na geracao dos paineis: nenhuma visao publicada (tudo ou nada)")
        L.log(f"{len(falhas)} falha(s) na geracao dos paineis — NENHUMA visao foi publicada (tudo ou nada).", "erro")
        return fim("bloqueada")

    res["itens"] = plano(gerados, modo)
    for it in res["itens"]:
        if modo != "plano":
            it["situacao"] = _copiar(it)
            if it["situacao"].startswith("erro"):
                res["erros"].append(f"{it['rotulo']}: {it['situacao']}")
        nivel = "erro" if it["situacao"].startswith("erro") else ("aviso" if not it["pasta_existe"] else "ok")
        L.log(f"{it['situacao']:<12} {it['rotulo']:<46} -> {it['destino']}" + ("" if it["pasta_existe"] else "   (a pasta NAO existia)"), nivel)
    if modo == "plano":
        L.log(f"PLANO de publicacao: {len(res['itens'])} arquivo(s) listados, NADA copiado. Use --ensaio para testar a copia em pasta local; "
              "--publicar so funciona com `publicacao.liberada: true` (D-28).")
    else:
        n = sum(i["situacao"] == "publicado" for i in res["itens"])
        L.log(f"{modo.upper()}: {n} copiado(s), {sum(i['situacao'] == 'sem mudanca' for i in res['itens'])} sem mudanca, {len(res['erros'])} erro(s) "
              f"em {res['destino']}", "ok" if not res["erros"] else "erro")
    return fim("ok" if not res["erros"] else "com erros")
