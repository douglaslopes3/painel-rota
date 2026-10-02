# Painel de Rota · Projeto Rota (Atacado)

Painel diário de execução de rota — visitas planejadas × check-ins × pedidos — para supervisores, gerente e head do
Atacado. Mesmo padrão do Scorecard DN e do Dashboard Gerencial: **bases → ETL Python → Parquet → HTML offline**, um
arquivo por usuário, publicado nas pastas de `Painéis Comerciais`.

Estado em **22/09/2026**: pipeline completo (leitura reconciliada com a fonte, modelo estrela, indicadores, sell-in do BI com meta por semana,
mês corrente + meses fechados no mesmo arquivo, tela de 3 abas), gerando os **9 painéis** (1 head, 3 gerentes, 5 supervisores) em pasta local e
ensaiando a publicação. **Nada é publicado** até a validação com o time (D-28). Varredura de refinamento feita em 22/09 (D-48). Pendências abertas
em `docs/10_DECISOES.md` (P-17 a P-19).

## Como rodar

```powershell
cd "C:\Users\dldsouza\OneDrive - Dori Alimentos S.A\Documentos\Painéis - Alavancas\ROTA"
python run_rota.py            # verificar -> ingerir -> modelar -> calcular -> painel (pasta local) -> gravar curated + qualidade   (~5 s)
python run_rota.py --forcar   # relê todas as bases ignorando o cache
python tests/test_leitores.py # 29 testes dos leitores (não precisa de pytest)
python tests/test_regras.py   # 24 testes das regras de visita, pedido, indicadores, sell-in e meses
python run_rota.py --ensaio       # ensaia a publicacao em pasta local (nao toca em Paineis Comerciais)
python run_rota.py --publicar     # publica — so com publicacao.liberada: true no config (D-28)
python tests/test_publicar.py     # trava, tudo ou nada e copia conferida (D-39)
```

Qualquer falha termina com `PIPELINE ABORTADO`, exit code 1, dizendo o arquivo, a linha e o motivo.

## Bases (`bases/`, somente leitura)

| Pasta | Arquivo | O que é | Rotina |
|---|---|---|---|
| `Rota/` | `Rota_AAAA-MM.xlsx`, aba `Base de Clientes` | rota planejada do mês, 1 linha por cliente, com `Cód. vendedor` (chave com a hierarquia, D-17) | 1 arquivo por mês, entregue pelo time de Atacado no fechamento |
| `Mercanet/` | `Mercanet_AAAA-MM.csv` | timeline de check-in/check-out | extração acumulada do mês: **substituir** o arquivo do mês corrente todo dia |
| `Pedidos/` | `Pedidos_AAAA-MM.csv` | consulta de pedidos (canal Atacado inteiro), com rodapé de totais | idem |
| `Estrutura/` | `DePara_Estrutura_Rota.xlsx`, aba `Hierarquia` | desde a D-49 (02/10/2026) só N4 → login do Mercanet; a hierarquia N1–N4 e os nomes vêm de `../../bases compartilhadas/Hierarquia_AAAAMMDD.xlsx` (a mais recente, comum ao DN e ao Gerencial), rótulo `código - nome`; as visões saem de N1, N2 e N3 | mantido pelo Douglas / Atacado; as 22 posições com login desde 22/09 (121 = Marcelo Silva, D-43) |
| `SellIn/` | `Projeto Rota.xlsx`, `Projeto Rota Carteira.xlsx`, `Proejto Rota Faturado.xlsx` | sell-in do BI: cliente × mês (orçado, carteira, receita, LY), pedidos em carteira e faturado — complemento aos pedidos (D-42); alimenta o bloco de sell-in e a meta por semana (D-44, pesos em `metas_sellin`) | extrair os 3 juntos todo dia e substituir |
| `../../bases compartilhadas/` | `Metas_*.xlsx` (hoje `Metas_FY'27.xlsx`) | meta em R$ por cliente × categoria × mês, a mesma do Gerencial: é o ORÇADO de cada loja da rota (D-52); o orçado do BI fica só como conferência | mantido pelo Douglas; um mês em um arquivo só |
| `../../bases compartilhadas/` | `Estrutura de Clientes_AAAAMMDD.xlsx` (a mais recente), aba `Planilha1` | nome dos clientes (código + nome, o mesmo do Gerencial); vence o nome do Mercanet (D-38, D-51). O `Clientes_Rota.xlsx` foi aposentado em 02/10/2026 | base comum ao Gerencial; loja nova da rota sem nome nela: o log avisa |

Regras de operação:

- **O mês vem do conteúdo**, nunca do nome do arquivo. Dois arquivos da mesma fonte com o mesmo mês **abortam de
  propósito** (uma cópia de conflito do OneDrive dobraria o mês): substitua, nunca adicione. Versão antiga vai para uma
  subpasta (`_versoes/`), que não é lida.
- **Nome do arquivo = `<Fonte>_AAAA-MM` (D-48)**, para o mês corrente e para os fechados. O nome não muda o resultado; é para a
  operação saber, na pasta, qual arquivo é de qual mês.
- **Mês fechado (D-45):** as bases do mês anterior FICAM em `bases/` com o mês no nome (`Rota_…`, `Mercanet_2026-09.csv`,
  `Pedidos_2026-09.csv`, `SellIn/2026-09/`), reextraídas uma vez no dia 5 do mês seguinte. O painel de cada usuário traz o mês
  corrente e os últimos 12 meses fechados, com seletor de mês; `_versoes/` é só para versão substituída.
- A soma de `Pedidos` tem de bater com o rodapé do próprio arquivo (valor do pedido, quantidade e valor bruto).

## Estrutura

```
bases/                 origem (somente leitura)
config/config.yaml     caminhos, colunas de cada base, logins ignorados, tolerâncias — nenhuma regra mora no código
rota/                  extract/ (leitores) · transform/ (calendario, visitas, modelo) · load/parquet · metricas · painel · render · qualidade · manifesto · pipeline
data/rota/             staging/ (Parquet por arquivo) · curated/ (modelo + manifesto) · quality/ (relatório + CSVs) · logs/   (não versionado)
docs/                  Fase 0, inventário, dicionário, modelo, catálogo de métricas, decisões, guia operacional
tests/                 testes dos leitores, das regras e da publicação, com dados sintéticos
template/template.html interface do painel, editada à mão (marcador de dados único; sem recurso externo)
Transcrições/          material de referência, não alterado (fora do git)
_descartar/            o que saiu de uso (protótipos, reconciliação com o protótipo 2, staging órfão) até ser apagado (fora do git, D-48)
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
