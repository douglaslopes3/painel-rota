# Painel de Rota · Projeto Rota (Atacado)

Painel diário de execução de rota — visitas planejadas × check-ins × pedidos — para supervisores, gerente e head do
Atacado. Mesmo padrão do Scorecard DN e do Dashboard Gerencial: **bases → ETL Python → Parquet → HTML offline**, um
arquivo por usuário, publicado nas pastas de `Painéis Comerciais`.

Estado em **17/09/2026**: **Fases 1, 2, 3 e 4a concluídas** — o pipeline gera os **9 painéis** (1 head, 3 gerentes, 5 supervisores) em pasta
local, validados; **nada é publicado** até tudo estar sem pendências e validado com o time (D-28) — as bases são lidas e reconciliadas com a fonte, viram o modelo
(fatos, dimensões, LOJA_MES, DIARIO_VENDEDOR) e os indicadores fecham com o protótipo 2. A publicação (Fase 4b) é a última etapa (`docs/Fase0_Diagnostico_Roadmap.html`, Etapa 8).

## Como rodar

```powershell
cd "C:\Users\dldsouza\OneDrive - Dori Alimentos S.A\Documentos\Painéis - Alavancas\ROTA"
python run_rota.py            # verificar -> ingerir -> modelar -> calcular -> painel (pasta local) -> gravar curated + qualidade   (~5 s)
python run_rota.py --forcar   # relê todas as bases ignorando o cache
python tests/test_leitores.py # 29 testes dos leitores (não precisa de pytest)
python tests/test_regras.py   # 23 testes das regras de visita, pedido, indicadores, sell-in e meses
python run_rota.py --ensaio       # ensaia a publicacao em pasta local (nao toca em Paineis Comerciais)
python run_rota.py --publicar     # publica — so com publicacao.liberada: true no config (D-28)
python tests/test_publicar.py     # trava, tudo ou nada e copia conferida (D-39)
python ferramentas/reconciliar_prototipo2.py   # aceite da Fase 2 (só vale com as bases de 16/09)
```

Qualquer falha termina com `PIPELINE ABORTADO`, exit code 1, dizendo o arquivo, a linha e o motivo.

## Bases (`bases/`, somente leitura)

| Pasta | Arquivo | O que é | Rotina |
|---|---|---|---|
| `Rota/` | `Rota_*.xlsx`, aba `Base de Clientes` | rota planejada do mês, 1 linha por cliente, com `Cód. vendedor` (chave com a hierarquia, D-17) | 1 arquivo por mês, entregue pelo time de Atacado no fechamento |
| `Mercanet/` | `*.csv` | timeline de check-in/check-out | extração acumulada do mês: **substituir** o arquivo do mês corrente todo dia |
| `Pedidos/` | `*.csv` | consulta de pedidos (canal Atacado inteiro), com rodapé de totais | idem |
| `Estrutura/` | `DePara_Estrutura_Rota.xlsx`, aba `Hierarquia` | hierarquia N1–N4 do Projeto Rota (formato da `Hierarquia_Consolidada` do Gerencial) + login do Mercanet; as visões saem de N1, N2 e N3 | mantido pelo Douglas / Atacado; as 22 posições com login desde 22/09 (121 = Marcelo Silva, D-43) |
| `SellIn/` | `Projeto Rota.xlsx`, `Projeto Rota Carteira.xlsx`, `Proejto Rota Faturado.xlsx` | sell-in do BI: cliente × mês (orçado, carteira, receita, LY), pedidos em carteira e faturado — complemento aos pedidos (D-42); alimenta o bloco de sell-in e a meta por semana (D-44, pesos em `metas_sellin`) | extrair os 3 juntos todo dia e substituir |
| `Estrutura/` | `Clientes_Rota.xlsx` | nome de TODAS as lojas da rota (código + nome); vence o nome do Mercanet (D-38) | mantido pelo Douglas; atualizar quando entrar loja nova na rota |

Regras de operação:

- **O mês vem do conteúdo**, nunca do nome do arquivo. Dois arquivos da mesma fonte com o mesmo mês **abortam de
  propósito** (uma cópia de conflito do OneDrive dobraria o mês): substitua, nunca adicione. Versão antiga vai para uma
  subpasta (`_versoes/`), que não é lida.
- **Mês fechado (D-45):** as bases do mês anterior FICAM em `bases/` com o mês no nome (`Rota_…`, `Mercanet_2026-09.csv`,
  `Pedidos_2026-09.csv`, `SellIn/2026-09/`), reextraídas uma vez no dia 5 do mês seguinte. O painel de cada usuário traz o mês
  corrente e os últimos 12 meses fechados, com seletor de mês; `_versoes/` é só para versão substituída.
- A soma de `Pedidos` tem de bater com o rodapé do próprio arquivo (valor do pedido, quantidade e valor bruto).

## Estrutura

```
bases/                 origem (somente leitura)
config/config.yaml     caminhos, colunas de cada base, logins ignorados, tolerâncias — nenhuma regra mora no código
rota/                  extract/ (leitores) · transform/ (calendario, visitas, modelo) · load/parquet · metricas · painel · render · qualidade · manifesto · pipeline
ferramentas/           fora do pipeline: reconciliação com o protótipo 2
data/rota/             staging/ (Parquet por arquivo) · curated/ (modelo + manifesto) · quality/ (relatório + CSVs) · logs/   (não versionado)
docs/                  Fase 0, inventário, dicionário, decisões, modelo do de-para
tests/                 testes dos leitores com arquivos sintéticos
template/template.html interface do painel, editada à mão (marcador de dados único; sem recurso externo)
Painel Referência/ · Transcrições/   material de referência, não alterado
run_rota.py · requirements.txt
```

## O painel

Um por visão da hierarquia (`painel.niveis_gerados`), com o mês corrente e os meses fechados dentro (seletor de mês, D-45), em
`%LOCALAPPDATA%\Dori\ROTA\painel\Painel_Rota_<nível>_<rótulo>.html` (fora do OneDrive), autocontido, só com os dados da própria visão
(recorte físico, conferido a cada execução), abre por duplo clique no Chrome ou Edge. Estrutura (D-47): cabeçalho (visão, dia do ciclo,
dados até) · aviso de vendedores sem check-in · seletores de mês e de dia de rota, filtro por supervisor · **3 abas**: *Roteiro do dia*
(faixa de semanas, uma linha de cards por período Dia/Semana/Mês, 2 gráficos por supervisor/vendedor, lojas do roteiro do dia), *Equipe no mês*
(tabela por vendedor com CSV) e *Lojas do roteiro* (todas as lojas do mês com situação, filtros e CSV). Depois de editar o template, basta
rodar o pipeline de novo.

## Documentação

| Documento | Conteúdo |
|---|---|
| `docs/Fase0_Diagnostico_Roadmap.html` | diagnóstico completo, arquitetura, riscos e roadmap (abrir por duplo clique) |
| `docs/01_INVENTARIO_FONTES.md` | o que cada base tem, medido |
| `docs/05_DICIONARIO_DADOS.md` | colunas do staging, tipos e o que fica de fora |
| `docs/06_MODELO.md` | fatos, dimensões, grão, quem é o dono da visita e do pedido, validações |
| `docs/07_CATALOGO_METRICAS.md` | definição de cada indicador, reconciliação com o protótipo 2, números de setembro |
| `docs/10_DECISOES.md` | decisões D-nn e pendências P-nn, com data |

## Regras que o projeto segue

Nada é inventado: todo número vem das bases; o que não tem origem é GAP declarado. Nada é descartado para o número
fechar: o que sai na leitura (linha repetida, login de teste, rodapé) é contado no log e no resumo da execução. Regras e
parâmetros vivem no `config.yaml` e no de-para, nunca no código. Arquivos originais não são alterados.
