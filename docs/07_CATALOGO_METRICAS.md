# 07 · Catálogo de métricas

Uma conta só: `rota.metricas.kpis(LOJA_MES, FATO_VISITA, dias, por)`. **Dia, semana e mês são apenas o conjunto de DIAS DE
ROTA que entra**: dia = [d]; semana = do 1º dia da semana do mês (S1 = 1 a 7, S2 = 8 a 14, S3 = 15 a 21, S4 = 22 a 31, D-44) até d;
faixa = da S<a> até d (D-47); mês = do dia 1 até d. Toda métrica de roteiro olha a loja no **dia da rota dela**. Parâmetros em
`config.yaml → regras` e `calendario`. Testes: `tests/test_regras.py`.

| Métrica | Definição | Origem |
|---|---|---|
| **Roteiro** (lojas na rota) | lojas com controle de visita (canal ≠ TELEFONE) cuja DATA_ROTA está no período | rota |
| **Visitadas no dia da rota** | lojas do roteiro com visita na própria DATA_ROTA | check-ins |
| **Não atendidas** | Roteiro − Visitadas no dia da rota | — |
| **Fora do roteiro** | lojas (com controle de visita) visitadas, dentro do período, num dia que não é o da rota delas — cada loja conta 1 vez | check-ins |
| **Total de lojas visitadas** | Visitadas no dia da rota + Fora do roteiro | — |
| **% visita no dia** | Visitadas no dia da rota ÷ Roteiro | — |
| **Aderência no mês (D-03)** | das lojas com roteiro **já vencido** até a data, as que tiveram ≥ 1 visita no mês, em qualquer dia ÷ roteiro vencido | rota + check-ins |
| **Com pedido (D-25)** | lojas do roteiro com pedido válido **no mês, até o último dia do período** (critério `mes`). Critério `janela` (protótipo 2): pedido na DATA_ROTA ou até 1 dia corrido depois | pedidos |
| **Visita + pedido** · **Sem contato** | critério `mes`: visita em qualquer dia do mês até a data E pedido no mês · nem uma nem outro. Critério `janela`: no dia da rota | — |
| **% positivação** · **% aderência** | Com pedido ÷ Roteiro · Visitadas até a data (qualquer dia do mês) ÷ Roteiro — no escopo mês é a Aderência no mês (D-03) | — |
| **Valor dos pedidos** (D-35) | Σ `Valor total do pedido` (valor bruto) dos pedidos válidos contados — **é o valor mostrado no painel**, em todas as visões | pedidos |
| **Quantidade solicitada** | Σ `Quantidade solicitada` dos mesmos pedidos — unidade não declarada; fica na camada curada, **fora do painel** (D-35) | pedidos |
| **Telefone: roteiro / com pedido / valor** | as mesmas contas para as lojas TELEFONE, que não têm controle de visita | rota + pedidos |
| **1ª entrada · Última saída** | menor check-in e maior check-out do dia, pelo LOGIN do vendedor | check-ins |
| **Tempo médio em loja** | média dos MINUTOS_EM_LOJA das visitas do dia que têm par | check-ins |
| **Status da loja** | 3 visita + pedido · 2 só visita · 1 só pedido · 0 sem contato (no dia da rota) | — |

Também ficam na LOJA_MES, por loja: `DIAS_VISITADOS`, `PRIMEIRA/ULTIMA_VISITA`, `DIAS_FORA_DO_ROTEIRO`, `PEDIDOS_MES`,
`VALOR_MES`, `QTD_MES` (pedidos válidos do mês, dentro ou fora da janela).

Fora do escopo desta fase (D-09 / GAPs): volume em kg, tempo de deslocamento, registro do contato telefônico, radar "Minha equipe",
"prioridades de ação". Receita líquida e meta entraram pelo sell-in do BI (D-44, abaixo).

## Regras revistas em 18/09/2026 (D-31 a D-36)

Visita: qualquer check-in ou check-out do dia conta, sem duração mínima (D-31, D-34), **exceto em sábado, domingo e feriado** (D-32 — lista
`regras.visita.dias_que_nao_contam`). Check-in em cliente que não está na rota do mês não entra em indicador (D-36).
Pedido válido: situação diferente de **Cancelado e Bloqueado** (D-33). Efeito na visão do head, mês até 16/09/2026:

| Indicador | Antes | Depois |
|---|---:|---:|
| Fora do roteiro | 482 | 479 |
| Visitadas até a data · Aderência no mês | 501 · 36,6% | 500 · 36,5% |
| Com pedido · % positivação | 238 · 17,4% | 228 · 16,7% |
| Visita + pedido · Sem contato | 94 · 723 | 88 · 728 |
| Valor dos pedidos (presencial · telefone) | fora do painel | R$ 1.578.081 · R$ 62.062 |

As tabelas abaixo são o retrato do aceite da Fase 2, com as regras do protótipo 2 (Bloqueado, fim de semana e feriado contando). Com as
regras atuais, `ferramentas/reconciliar_prototipo2.py` passa a apontar diferenças — deliberadas, por D-32 e D-33.

## Sell-in (D-44, 22/09/2026) — só lojas da rota, fonte BI (`fontes.sellin`)

| Indicador | Cálculo | Onde |
|---|---|---|
| Faturado | Σ `RECEITA` do arquivo faturado, por data de faturamento no período (devoluções negativas entram) | mês, semana, tabela, loja |
| % do orçado | faturado do mês ÷ Σ `ORCADO` das lojas da rota do vendedor | mês (sem cor) |
| Meta | orçado × peso da semana (`metas_sellin.pesos`); até a data = orçado × Σ pesos até a semana do dia, semana em andamento inteira | mês, semana |
| % da meta | faturado ÷ meta; cores por `painel.faixas_meta_sellin` (100 / 80) | mês, semana, tabela, gráfico |
| Carteira | Σ `CARTEIRA` dos pedidos em aberto na data do export (só no dia mais recente do painel) | mês |
| % do orçado com carteira | (faturado + carteira) ÷ orçado | mês, tabela |
| Lojas faturadas | lojas com faturado líquido > 0 no mês ÷ lojas da rota | mês |

A loja é do vendedor da ROTA (não do N4 do BI — iguais em 100% em set/26). Semana = semana do mês (`calendario.semanas_do_mes`); `LY` não entra.
Conferências: faturado dos cards = Σ faturado da lista de lojas; lojas do sell-in = lojas da visão; supervisores somam gerente e head.

## Reconciliação com o protótipo 2 (aceite da Fase 2)

`reconciliar_prototipo2.py` (D-48: só valia com as bases de 16/09; excluído na limpeza de 03/10/2026) refez a conta do JavaScript do
protótipo sobre os dados embutidos nele e comparou com `kpis`, vendedor a vendedor, no mês até 16/09/2026:

| Indicador | Protótipo | Modelo | |
|---|---:|---:|---|
| Roteiro | 1.368 | 1.368 | igual nos 22 vendedores |
| Visitadas no dia da rota | 292 | 292 | igual |
| Com pedido · Visita + pedido · Sem contato | 42 · 16 · 1.050 | 42 · 16 · 1.050 | igual |
| Telefone: roteiro · com pedido | 142 · 2 | 142 · 2 | igual |
| Fora do roteiro | 483 | 482 | −1 em HYGOR DOREA: o protótipo contou o check-in do usuário `TESTERTM` (01/09, cliente 1012816), que o pipeline ignora |
| Valor dos pedidos | R$ 263.643,87 | R$ 287.214,71 | o protótipo soma só o **1º** pedido da janela de cada loja; o modelo soma todos |

Minutos em loja e número de registros por visita: iguais ao protótipo em 100% dos 947 cliente-dias comparáveis.

## O que os números de setembro já mostram (até 16/09)

| | Roteiro vencido | Visitadas no dia da rota | Fora do roteiro | **Aderência no mês** | Com pedido (janela) |
|---|---:|---:|---:|---:|---:|
| Marco Masson | 444 | 111 (25,0%) | 214 | 197 (**44,4%**) | 16 |
| Robson Dias | 214 | 25 (11,7%) | 71 | 58 (**27,1%**) | 6 |
| Hudson Lage | 351 | 75 (21,4%) | 76 | 121 (**34,5%**) | 16 |
| Adriana Miranda | 316 | 81 (25,6%) | 121 | 125 (**39,6%**) | 4 |
| Anderson Okada | 43 (+142 por telefone) | 0 | 0 | 0 (0,0%) — sem check-in | 0 (telefone: 2) |
| **Total** | **1.368** | **292 (21,3%)** | **482** | **501 (36,6%)** | **42** |

Por que a D-25 trocou a janela pelo mês (era a P-13): dos 548 pedidos válidos de clientes da rota, só **46** caem na janela "dia da rota
+ 1 dia" — **502 ficam fora**. Das 1.368 lojas com roteiro vencido, 42 têm pedido na janela, mas **238 têm pedido no
mês**. Com a visita acontecendo fora do dia planejado em 2 de cada 3 casos, "com pedido no dia da rota" mede pouco; a
alternativa (pedido no mês, como a aderência) já está calculada na LOJA_MES.
