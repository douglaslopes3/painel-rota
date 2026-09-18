# 06 · Modelo de dados — camada curada

`data/rota/curated/*.parquet` (zstd), regravada inteira a cada execução, só depois de todas as validações. Toda tabela
leva `EXECUCAO_ID`. Números da execução de 17/09/2026 (dados até 16/09).

```
DIM_CALENDARIO ─┐                        ┌─ DIM_VENDEDOR (posição N4: N1..N3, login)  ──  DIM_VISAO (painéis)
                ├── FATO_ROTA_PLANEJADA ─┤
                ├── FATO_VISITA ─────────┼─ DIM_CLIENTE
                └── FATO_PEDIDO ─────────┘
        derivadas:  LOJA_MES (1 linha por loja na rota do mês)  ·  DIARIO_VENDEDOR (dia de rota × vendedor)
```

| Tabela | Grão (1 linha =) | Linhas | Chave | Origem |
|---|---|---:|---|---|
| FATO_ROTA_PLANEJADA | loja na rota do mês | 2.973 | ANO_MES + COD_CLIENTE | rota mensal + hierarquia (por `COD_VENDEDOR`) |
| FATO_VISITA | login × cliente × dia | 952 (de 3.068 eventos) | LOGIN + COD_CLIENTE + DATA | check-ins |
| FATO_PEDIDO | pedido (canal inteiro) | 2.468 | PEDIDO | pedidos |
| DIM_CLIENTE | cliente das três bases | 4.591 | COD_CLIENTE | nome mais recente de pedidos/check-ins; cidade da rota |
| DIM_VENDEDOR | posição N4 da hierarquia | 22 | N4_COD | de-para + `USA_APP`, `CLIENTES` |
| DIM_VISAO | painel a gerar | 9 | NIVEL + COD | derivada de N1, N2, N3 (D-21) |
| DIM_CALENDARIO | dia dos meses com rota | 30 | DATA | gerada; `feriados` do config |
| LOJA_MES | loja na rota do mês, já com visita e pedido do DIA DA ROTA e do mês | 2.973 | ANO_MES + COD_CLIENTE | fatos |
| DIARIO_VENDEDOR | dia de rota × vendedor | 440 | DATA + COD_VENDEDOR | LOJA_MES + jornada |

Cardinalidades: toda fato é N:1 para calendário (DATA), cliente (COD_CLIENTE) e vendedor (COD_VENDEDOR). Visão → N3 é N:N
(`DIM_VISAO.N3_CODS`), usada só no recorte dos painéis.

## Quem é o "dono" de uma visita ou de um pedido

O **vendedor da rota daquele mês** para aquele cliente (`COD_VENDEDOR_ROTA`), como no protótipo 2 — não o login de quem
fez o check-in nem o `Representante` do pedido. O login fica ao lado (`COD_VENDEDOR_LOGIN`) e serve à jornada do dia
(1ª entrada, última saída, tempo em loja) e à lista de exceção "visita feita por vendedor diferente do dono" (hoje: 0).

## Colunas que carregam regra

| Tabela | Coluna | Regra |
|---|---|---|
| FATO_ROTA_PLANEJADA | CONTROLA_VISITA | `CANAL` fora de `regras.canais_sem_controle_de_visita` (TELEFONE) |
| FATO_VISITA | N_CHECKINS, N_CHECKOUTS | eventos do cliente no dia: vários check-ins = UMA visita |
| FATO_VISITA | MINUTOS_EM_LOJA, N_PARES | maior par check-in → check-out do dia; cada check-out pareia com o último check-in antes dele; nulo sem par |
| FATO_VISITA | CONTA_COMO_VISITA | tem evento de `regras.visita.eventos_que_contam` (e duração ≥ `minutos_minimos`, se definido) |
| FATO_VISITA | NA_ROTA · NO_DIA_DA_ROTA | cliente está na rota do mês · DATA = DATA_ROTA |
| FATO_PEDIDO | VALIDO | `SITUACAO` fora de `regras.pedido.situacoes_excluidas` (Cancelado e Bloqueado, D-33) |
| FATO_PEDIDO | VALOR | `regras.pedido.coluna_valor` (VALOR_PEDIDO) |
| FATO_PEDIDO | NA_JANELA_DA_ROTA | emissão entre DATA_ROTA e DATA_ROTA + `janela_dias_corridos` (1) |
| LOJA_MES | STATUS | 3 visita + pedido · 2 só visita · 1 só pedido · 0 sem contato — sempre referente ao DIA DA ROTA |

## Validações que abortam (nada é gravado)

Linhas da rota ≠ staging ou cliente repetido no mês · pedidos ≠ staging (linhas ou valor) · soma de eventos das visitas ≠
eventos do staging · cliente de fato sem linha na dimensão · soma dos indicadores por vendedor, supervisor, gerente e
head ≠ total · DIARIO_VENDEDOR ≠ total do mês · (com `estrutura.obrigatorio: true`) loja sem posição na hierarquia.
