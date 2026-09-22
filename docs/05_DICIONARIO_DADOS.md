# 05 · Dicionário de dados — camada staging

Um Parquet (zstd) por arquivo de origem em `data/rota/staging/<arquivo>.<hash>.parquet`, com um JSON ao lado (contagens e
gabarito). O mapa "coluna na origem → coluna no staging" vive em `config/config.yaml → fontes.*.colunas`. A camada
curada (fatos e dimensões) entra na Fase 2 e será documentada em `06_MODELO.md`.

Tratamentos comuns: texto com trim e espaços colapsados; `COD_CLIENTE` só dígitos, sem zeros à esquerda (as três bases
casam por ele); números no formato brasileiro (ponto é sempre milhar); `ANO_MES` = `AAAA-MM` tirado do CONTEÚDO.

## Rota planejada (`rota_mensal.py`)

| Coluna | Tipo | Origem | Observação |
|---|---|---|---|
| ANO_MES | texto | derivada de DATA_ROTA | um arquivo = um mês (senão aborta) |
| SUPERVISOR | texto | `Supervisor` | como na planilha (primeiro nome) |
| EXECUTIVO | texto, maiúscula | `Executivo` | inclui `[VAGO]` |
| COD_CLIENTE | texto | `Cód. cliente` | único no arquivo (senão aborta) |
| CANAL | texto, maiúscula | `canal` | PRESENCIAL · TELEFONE (valor novo = aviso) |
| DATA_ROTA | data | coluna `Datas Rota <mês>` | localizada por padrão `^DATAS? ROTA`; nula aborta |
| CIDADE | texto, maiúscula | `cidade` | |
| NET_SALES_25 · NET_SALES_26 | decimal | `Net Sales 25/26` | histórico anual por cliente; há zeros e negativos na origem, mantidos |
| FREQ_25 · FREQ_26 | inteiro | `Frequência anual 2025/2026` | de visita ou de compra? (P-07) |
| VOLUME_25 · VOLUME_26 | decimal | `Volume 25/26` | unidade não declarada |
| ARQUIVO_ORIGEM | texto | — | linhagem |

## Check-ins (`checkins.py`) — evento bruto

| Coluna | Tipo | Origem | Observação |
|---|---|---|---|
| ANO_MES · DATA | texto · data | derivadas de DATA_HORA | |
| DATA_HORA | data-hora | `DATA EVENTO` | `dd/mm/aaaa hh:mm:ss`; inválida aborta |
| LOGIN | texto, maiúscula | `USUÁRIO` | logins de `logins_ignorados` saem, contados |
| NOME_USUARIO | texto | `NOME USUÁRIO` | dado pessoal |
| COD_CLIENTE | texto | `CÓDIGO CLIENTE` | |
| NOME_CLIENTE · CIDADE · UF | texto, maiúscula | `NOME CLIENTE` · `CIDADE CLIENTE` · `ESTADO` | |
| EVENTO | texto | `EVENTO TIME LINE` | CHECKIN · CHECKOUT (outro valor aborta) |
| ARQUIVO_ORIGEM | texto | — | |

**Fora do staging** (minimização): `ENDEREÇO CLIENTE`, `DESCRIÇÃO TIMELINE`, `LATITUDE`, `LONGITUDE`. A deduplicação em
visita (1 por cliente × dia) e o pareamento check-in/check-out são regra de negócio da Fase 2 — o staging guarda o evento.

## Pedidos (`pedidos.py`)

| Coluna | Tipo | Origem | Observação |
|---|---|---|---|
| ANO_MES | texto | derivada de DATA_EMISSAO | |
| PEDIDO | texto | `Pedido` | único (repetido aborta, inclusive entre arquivos) |
| COD_CLIENTE · NOME_CLIENTE | texto | `Código` · `Cliente` | |
| DATA_EMISSAO · DATA_ENTREGA_ESTIMADA · DATA_FATURAMENTO | data | idem | faturamento só preenchido em Faturado / Parcial / Fatur.+Canc. |
| SITUACAO | texto | `Situação` | Aberto · Fatur. Parcial · Faturado · Fatur. + Canc. · Bloqueado · Cancelado (valor novo = aviso) |
| VALOR_PEDIDO | decimal | `Valor total do pedido` | reconciliado com o rodapé |
| QTD_SOLICITADA | decimal | `Quantidade solicitada` | reconciliado; unidade não declarada; fica na camada curada, fora do painel (D-35) |
| VALOR_BRUTO · VALOR_DESCONTO | decimal | `Valor total bruto` · `Valor desconto` | bruto reconciliado; bruto − desconto ≠ valor do pedido em 155 linhas (Bloqueado/Cancelado na maioria) |
| REPRESENTANTE · CIDADE · UF | texto | idem | `REPRESENTANTE` não identifica o executivo |
| ARQUIVO_ORIGEM | texto | — | |

**Fora do staging:** `Ordem de compra`, `Sit. Embarque`, `Nota fiscal`, `Cliente CNPJ` (17 são CPF), `Desconto médio`,
`Preço médio liquido`.

## Estrutura (`estrutura.py`)

Aba `Hierarquia`, no formato da `Hierarquia_Consolidada` do Gerencial (D-16). Grão: 1 linha = 1 posição de vendedor (N4).
Colunas no staging: `N1_COD/PAPEL/NOME` (head), `N2_…` (gerente), `N3_…` (sup./exec.), `N4_…` (vend./RCA), `PROJETO`,
`LOGIN_MERCANET`, `NOME_MERCANET` e os rótulos `N1_ROTULO … N4_ROTULO` = `código - papel - nome` (padrão das pastas de
publicação). Código de N4 repetido, ou código de N1–N3 com dois nomes/superiores, aborta. As visões (painéis) são derivadas
de N1, N2 e N3 por `estrutura.visoes()`. Nada é inferido: login vazio fica vazio e vira pendência listada no log.

Chave com a rota (D-17): `COD_VENDEDOR` (coluna opcional `Cód. vendedor` da planilha de rota) = `N4_COD`; sem a coluna,
`EXECUTIVO` = `N4_NOME`, que só serve enquanto o nome for único (duas posições `[VAGO]` tornam a ligação ambígua).

Coluna opcional `ENCERRADA EM` (D-45) → `ENCERRADA_EM` (data) e `ATIVA` (sem data = ativa): posição de vendedor que saiu; não precisa
de login nem de lojas na rota corrente e continua no de-para para os meses fechados.

## Sell-in do BI (`sellin.py`) — D-42

Três exports do BI em `bases/SellIn/` (nomes em `fontes.sellin.arquivos`). Rodapé (`Total`, linha em branco, `Filtros aplicados…`)
sai dos dados: o `Total` é o gabarito (soma das linhas tem de bater) e o texto dos filtros fica no JSON do staging. Linha que não é
dado nem rodapé, chave repetida ou arquivo truncado abortam. `COD_CLIENTE` sem zeros à esquerda; `ANO_MES` no formato `2026-09`.

| Arquivo | Grão (chave) | Colunas no staging |
|---|---|---|
| `cliente` | 1 cliente no mês (`COD_CLIENTE`) | `ANO_MES`, `COD_CLIENTE`, `NOME_CLIENTE`, `BANDEIRA`, `CIDADE`, `N1_BI`…`N4_BI` (texto do BI, ex.: `RODRIGO MATOS (128)`), `COD_VENDEDOR` (o número entre parênteses do N4), `ORCADO`, `CARTEIRA`, `RECEITA`, `RECEITA_LY` |
| `carteira` | 1 pedido em aberto (`PEDIDO`) | `ANO_MES`, `PEDIDO`, `DATA_PEDIDO`, `COD_CLIENTE`, `CARTEIRA` |
| `faturado` | 1 pedido × data de faturamento (`PEDIDO`, `DATA_FATURAMENTO`) | `ANO_MES`, `PEDIDO`, `DATA_PEDIDO`, `DATA_FATURAMENTO`, `COD_CLIENTE`, `RECEITA` (negativos entram como vêm) |

Valores em Receita Líquida (não é o `Valor total do pedido` do Mercanet). O pedido do BI não casa com o do Mercanet: ligação só por cliente.
D-45: a raiz de `bases/SellIn/` é o mês corrente; cada subpasta `AAAA-MM` é um mês fechado (os mesmos 3 arquivos, filtrados naquele mês);
`carregar()` devolve `{mês: {cliente, carteira, faturado}}`.
