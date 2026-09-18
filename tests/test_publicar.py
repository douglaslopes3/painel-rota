# -*- coding: utf-8 -*-
"""Testes da etapa 6 · publicar (D-39): a trava da D-28, o tudo ou nada e a cópia conferida.

    python tests/test_publicar.py

Tudo acontece em pasta temporária: o destino e a pasta de ensaio do config são trocados
em memória antes de cada teste. Nenhum teste toca em `Painéis Comerciais`.
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
for _f in (sys.stdout, sys.stderr):
    try:
        _f.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass

from rota import publicar  # noqa: E402
from rota.utils import log as L  # noqa: E402
from rota.utils.config import CFG  # noqa: E402

TMP = Path(tempfile.mkdtemp(prefix="rota_pub_"))
L.abrir()


def _cenario(nome: str) -> dict:
    """Dois painéis 'gerados' em pasta temporária; destino real e ensaio apontados para dentro dela."""
    raiz = TMP / nome
    (raiz / "local").mkdir(parents=True)
    CFG["publicacao"].update({"destino": str(raiz / "real"), "pasta_ensaio": str(raiz / "ensaio"), "liberada": False,
                              "criar_pasta": True, "pular_se_identico": True})
    gerados = {}
    for rot in ("20 - ATACADO - HEAD UM", "2310 - Superv_PR/CO - FULANO"):
        arq = raiz / "local" / (publicar.pasta_usuario(rot) + ".html")
        arq.write_text("<html>" + rot + "</html>", encoding="utf-8")
        gerados[rot] = {"arquivo": str(arq)}
    return gerados


def _arquivos(pasta: Path) -> list[str]:
    return sorted(str(a.relative_to(pasta)).replace("\\", "/") for a in pasta.rglob("*") if a.is_file()) if pasta.exists() else []


def test_pasta_do_usuario_troca_caractere_invalido_por_hifen():
    assert publicar.pasta_usuario("22000 - Ger Reg_RJ/MG/ES - ERBINO BOTELHO") == "22000 - Ger Reg_RJ-MG-ES - ERBINO BOTELHO"


def test_plano_lista_e_nao_grava_nada():
    g = _cenario("plano")
    r = publicar.executar(g, [], "plano")
    assert [i["situacao"] for i in r["itens"]] == ["novo", "novo"] and not r["erros"]
    assert not (TMP / "plano" / "real").exists() and not (TMP / "plano" / "ensaio").exists()


def test_publicar_sem_liberacao_no_config_recusa_e_nao_copia():
    g = _cenario("trava")
    r = publicar.executar(g, [], "publicar")
    assert r["erros"] and not r["itens"] and not (TMP / "trava" / "real").exists()          # D-28: a flag sozinha não publica


def test_ensaio_copia_so_para_a_pasta_de_ensaio_e_repete_sem_mudanca():
    g = _cenario("ensaio")
    r = publicar.executar(g, [], "ensaio")
    assert [i["situacao"] for i in r["itens"]] == ["publicado", "publicado"] and not (TMP / "ensaio" / "real").exists()
    assert _arquivos(TMP / "ensaio" / "ensaio") == ["20 - ATACADO - HEAD UM/Painel_Rota.html", "2310 - Superv_PR-CO - FULANO/Painel_Rota.html"]
    assert [i["situacao"] for i in publicar.executar(g, [], "ensaio")["itens"]] == ["sem mudanca", "sem mudanca"]


def test_publicar_liberado_copia_confere_e_nao_apaga_o_que_ja_esta_na_pasta():
    g = _cenario("real")
    vizinho = TMP / "real" / "real" / "20 - ATACADO - HEAD UM" / "Dashboard_Gerencial.html"
    vizinho.parent.mkdir(parents=True)
    vizinho.write_text("gerencial", encoding="utf-8")
    CFG["publicacao"]["liberada"] = True
    r = publicar.executar(g, [], "publicar")
    assert not r["erros"] and [i["situacao"] for i in r["itens"]] == ["publicado", "publicado"]
    assert vizinho.read_text(encoding="utf-8") == "gerencial" and not list((TMP / "real" / "real").rglob("*.tmp"))
    Path(g["20 - ATACADO - HEAD UM"]["arquivo"]).write_text("<html>novo</html>", encoding="utf-8")      # base nova -> só esse é recopiado
    assert [i["situacao"] for i in publicar.executar(g, [], "publicar")["itens"]] == ["publicado", "sem mudanca"]


def test_falha_em_uma_visao_nao_publica_nenhuma():
    g = _cenario("tudo_ou_nada")
    CFG["publicacao"]["liberada"] = True
    r = publicar.executar(g, ["'2110 - X': VAZAMENTO"], "publicar")
    assert r["erros"] and not (TMP / "tudo_ou_nada" / "real").exists()


def test_pasta_inexistente_com_criar_pasta_desligado_e_erro_so_daquela_visao():
    g = _cenario("sem_pasta")
    CFG["publicacao"].update({"liberada": True, "criar_pasta": False})
    (TMP / "sem_pasta" / "real" / "20 - ATACADO - HEAD UM").mkdir(parents=True)
    r = publicar.executar(g, [], "publicar")
    assert [i["situacao"].split(":")[0] for i in r["itens"]] == ["publicado", "erro"] and len(r["erros"]) == 1


if __name__ == "__main__":
    original = dict(CFG["publicacao"])
    testes = [(n, f) for n, f in sorted(globals().items()) if n.startswith("test_") and callable(f)]
    falhas = 0
    for nome, fn in testes:
        try:
            fn()
            print(f"  ok    {nome}")
        except Exception as e:                                   # noqa: BLE001
            falhas += 1
            print(f" FALHA  {nome}: {type(e).__name__}: {e}")
        finally:
            CFG["publicacao"].clear(); CFG["publicacao"].update(original)
    print(f"\n{len(testes) - falhas}/{len(testes)} testes ok")
    sys.exit(1 if falhas else 0)
