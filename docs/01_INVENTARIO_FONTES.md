# 01 · Inventário das fontes

Medido em 17/09/2026 (diagnóstico da Fase 0 e execução `20260917-155143-25e67c`). Detalhe completo, com os achados de
qualidade Q1–Q16, em `Fase0_Diagnostico_Roadmap.html`, Etapa 4.

| Fonte | Arquivo | Formato | Linhas | Período | Grão | Chave | Origem · cadência |
|---|---|---|---:|---|---|---|---|
| Rota planejada | `bases/Rota/Rota_14092026.xlsx`, aba `Base de Clientes` | xlsx, 12 colunas | 2.973 | rota de set/26: 20 datas úteis, 02/09 a 30/09 | 1 linha = 1 cliente na rota do mês | `Cód. cliente` (7 dígitos, único) | construída pelo time de Atacado (Gui) · mensal |
| Check-ins | `bases/Mercanet/Mercanet.csv` | CSV `;`, cp1252, 12 colunas | 3.070 | 01/09/2026 06:40 a 16/09/2026 16:15 | 1 linha = 1 evento (CHECKIN 1.608 · CHECKOUT 1.462) | não há id de visita; `USUÁRIO` + `DATA EVENTO` + evento | Mercanet, timeline · diária, acumulada do mês |
| Pedidos | `bases/Pedidos/Pedidos.csv` | CSV `;`, cp1252, decimal com vírgula, 20 colunas | 2.468 + 1 rodapé de totais | emissão 01/09 a 16/09/2026 | 1 linha = 1 pedido, canal Atacado inteiro | `Pedido` (único) | Mercanet, consulta de pedidos · diária, acumulada do mês |
| Estrutura | `bases/Estrutura/DePara_Estrutura_Rota.xlsx` | xlsx, abas `Executivos` e `Visoes` | — | — | executivo · painel a gerar | `EXECUTIVO` · `VISAO` | time de Atacado · sob demanda · **pendente (P-01)** |

## O que a ingestão tira, contando

| Fonte | Sai | Quantidade (17/09) | Por quê |
|---|---|---:|---|
| Check-ins | linha 100% repetida | 1 | duplicidade exata da extração |
| Check-ins | eventos do login `TESTERTM` | 1 | usuário de teste, declarado em `config → fontes.checkins.logins_ignorados` (a confirmar, P-01) |
| Pedidos | rodapé de totais | 1 | vira o gabarito de reconciliação |

Resultado: **3.068 eventos · 15 logins**, **2.468 pedidos** (R$ 17.734.952,08 · 208.960 de quantidade · R$ 29.503.050,80
bruto, iguais ao rodapé), **2.973 clientes · 22 executivos · 5 supervisores**.

## Chaves entre as bases (medido)

| Ligação | Resultado |
|---|---|
| Check-ins → Rota (`COD_CLIENTE`) | 676 de 681 clientes com check-in estão na rota; 5 clientes (11 eventos) fora da rota |
| Pedidos → Rota (`COD_CLIENTE`) | 558 de 2.468 pedidos são de clientes da rota (492 clientes) |
| Check-in → Executivo | **não existe nas bases**: depende do de-para (login ↔ executivo). Pelo cliente visitado, 99–100% dos eventos de cada login caem em clientes de um único executivo |
| Pedido → Executivo | pelo cliente (rota). `Representante` não serve: 38 códigos nos pedidos de clientes da rota, 2 a 8 por executivo |

## O que as bases NÃO têm (GAPs)

Receita líquida / sell-in · volume em kg (há `Quantidade solicitada`, unidade não declarada — P-02) · metas · código, nome
e "base" da rota · ordem de visita · gerente e hierarquia de pessoas · registro de contato telefônico (284 clientes
TELEFONE) · latitude/longitude utilizáveis (vêm truncadas em inteiro).
