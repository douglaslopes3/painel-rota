# Painel de Rota · Projeto Rota (Atacado)

Painel diário de execução de rota — visitas planejadas × check-ins × pedidos — para supervisores, gerente e head do
Atacado. Mesmo padrão do Scorecard DN e do Dashboard Gerencial: **bases → ETL Python → Parquet → HTML offline**, um
arquivo por usuário, publicado nas pastas de `Painéis Comerciais`.

Estado em **17/09/2026**: **Fase 1 (fundação) concluída** — as bases são lidas, validadas e reconciliadas com a fonte.
Modelo, indicadores, painel e publicação entram nas fases 2 a 4 (`docs/Fase0_Diagnostico_Roadmap.html`, Etapa 8).

## Como rodar

```powershell
cd "C:\Users\dldsouza\OneDrive - Dori Alimentos S.A\Documentos\Painéis - Alavancas\ROTA"
python run_rota.py            # verificar -> ingerir (bases -> staging) -> resumo e manifesto   (~1 s)
python run_rota.py --forcar   # relê todas as bases ignorando o cache
python tests/test_leitores.py # 21 testes dos leitores (não precisa de pytest)
```

Qualquer falha termina com `PIPELINE ABORTADO`, exit code 1, dizendo o arquivo, a linha e o motivo.

## Bases (`bases/`, somente leitura)

| Pasta | Arquivo | O que é | Rotina |
|---|---|---|---|
| `Rota/` | `Rota_*.xlsx`, aba `Base de Clientes` | rota planejada do mês, 1 linha por cliente, com `Cód. vendedor` (chave com a hierarquia, D-17) | 1 arquivo por mês, entregue pelo time de Atacado no fechamento |
| `Mercanet/` | `*.csv` | timeline de check-in/check-out | extração acumulada do mês: **substituir** o arquivo do mês corrente todo dia |
| `Pedidos/` | `*.csv` | consulta de pedidos (canal Atacado inteiro), com rodapé de totais | idem |
| `Estrutura/` | `DePara_Estrutura_Rota.xlsx`, aba `Hierarquia` | hierarquia N1–N4 do Projeto Rota (formato da `Hierarquia_Consolidada` do Gerencial) + login do Mercanet; as visões saem de N1, N2 e N3 | mantido pelo Douglas / Atacado; faltam 7 logins (P-01) |

Regras de operação:

- **O mês vem do conteúdo**, nunca do nome do arquivo. Dois arquivos da mesma fonte com o mesmo mês **abortam de
  propósito** (uma cópia de conflito do OneDrive dobraria o mês): substitua, nunca adicione. Versão antiga vai para uma
  subpasta (`_versoes/`), que não é lida.
- **Mês fechado:** quando o mês vira, extrair do Mercanet o mês fechado inteiro (check-ins e pedidos) e deixar na pasta
  ao lado do arquivo do mês corrente (ex.: `Mercanet_2026-09.csv` + `Mercanet.csv`). É assim que o histórico se forma (D-07).
- A soma de `Pedidos` tem de bater com o rodapé do próprio arquivo (valor do pedido, quantidade e valor bruto).

## Estrutura

```
bases/                 origem (somente leitura)
config/config.yaml     caminhos, colunas de cada base, logins ignorados, tolerâncias — nenhuma regra mora no código
rota/                  extract/ (cache, comum, rota_mensal, checkins, pedidos, estrutura) · utils/ · manifesto · pipeline
data/rota/             staging/ (Parquet por arquivo) · curated/manifesto.json · quality/ · logs/   (não versionado)
docs/                  Fase 0, inventário, dicionário, decisões, modelo do de-para
tests/                 testes dos leitores com arquivos sintéticos
template/              (Fase 3)
Painel Referência/ · Transcrições/   material de referência, não alterado
run_rota.py · requirements.txt
```

## Documentação

| Documento | Conteúdo |
|---|---|
| `docs/Fase0_Diagnostico_Roadmap.html` | diagnóstico completo, arquitetura, riscos e roadmap (abrir por duplo clique) |
| `docs/01_INVENTARIO_FONTES.md` | o que cada base tem, medido |
| `docs/05_DICIONARIO_DADOS.md` | colunas do staging, tipos e o que fica de fora |
| `docs/10_DECISOES.md` | decisões D-nn e pendências P-nn, com data |

## Regras que o projeto segue

Nada é inventado: todo número vem das bases; o que não tem origem é GAP declarado. Nada é descartado para o número
fechar: o que sai na leitura (linha repetida, login de teste, rodapé) é contado no log e no resumo da execução. Regras e
parâmetros vivem no `config.yaml` e no de-para, nunca no código. Arquivos originais não são alterados.
