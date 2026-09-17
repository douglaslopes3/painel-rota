# 10 · Registro de decisões e pendências

Decisões do Douglas (17/09/2026, Fase 0), salvo indicação. O porquê e as alternativas estão em
`Fase0_Diagnostico_Roadmap.html`. Decisão nova entra no fim, com data; decisão revista é riscada, não apagada.

## Decisões

| # | Data | Decisão |
|---|---|---|
| D-01 | 17/09 | Layout do `Diario_Rota_Campo.html`, com os blocos dia · semana · mês; identidade visual do DN. |
| D-02 | 17/09 | Regras do protótipo `painel_execucao_rota_22.html` como ponto de partida: 1 visita por cliente × dia; pedido Cancelado fora; valor = bruto − desconto; pedido conta para a loja quando digitado no dia da rota ou no dia seguinte; TELEFONE só por pedido; semana = segunda até o dia; faixas 90/60. |
| D-03 | 17/09 | Aderência medida no MÊS: check-in em qualquer dia conta. Denominador = roteiro vencido até a data. |
| D-04 | 17/09 | Receita fora do painel. "Volume" = `Quantidade solicitada` — em aberto (P-02). |
| D-05 | 17/09 | 1 HTML por visão, recorte físico, sem senha; publicado em `Painéis Comerciais\Gerencial\<usuário>\Painel_Rota.html` (pastas faltantes serão criadas). |
| D-06 | 17/09 | Extrações do Mercanet acumuladas do mês; 1 atualização por dia, desenho pronto para 4. |
| D-07 | 17/09 | Histórico guardado. **Revista em 17/09:** os meses fechados são REEXTRAÍDOS do Mercanet (é possível pedir período passado) e ficam na pasta ao lado do arquivo do mês corrente; ~~cópia das extrações em `_historico/` no último dia útil~~. Setembro entra quando fechar. |
| D-08 | 17/09 | Padrão técnico: base no DN + git, `requirements.txt`, `tests/` e docs numerados do Gerencial. |
| D-09 | 17/09 | Produto fase 1: KPIs, tabela/gráfico por executivo, lista de lojas, tempo em loja. Fase 2: "Minha equipe no mês" (radar), "Lojas em aberto", deslocamento, evolução histórica, metas. |
| D-10 | 17/09 | Uso no computador. Operação: Douglas, suplente Gui. Rastreamento por check-in é prática aceita. |
| D-11 | 17/09 | `bases/` organizada em subpastas por fonte (Rota, Mercanet, Pedidos, Estrutura); os 3 arquivos foram movidos sem alteração (MD5 conferido). `Painel Referência/` e `Transcrições/` ficam onde estão. |
| D-12 | 17/09 | Git local na pasta do projeto, sem remoto; `bases/`, `data/`, protótipos e transcrições fora do versionamento. |
| D-13 | 17/09 | Mesmo mês em dois arquivos da mesma fonte ABORTA (padrão DN/Gerencial); versão antiga vai para subpasta não lida. Substitui a proposta da Etapa 6 de "vale a mais recente". |
| D-14 | 17/09 | Minimização no staging: endereço, descrição, latitude/longitude (check-ins) e CNPJ/CPF, ordem de compra, nota fiscal, desconto e preço médios (pedidos) não são ingeridos. |
| D-15 | 17/09 | Enquanto o de-para oficial não chega, `fontes.estrutura.obrigatorio: false` (ausência e pendências = aviso). Ao chegar, passa a `true` (aborta). |
| D-16 | 17/09 | De-para de estrutura no formato da `Hierarquia_Consolidada` do Gerencial (aba `Hierarquia`, 1 linha por posição N4, com N1–N3 e LOGIN/NOME MERCANET), montado pelo Douglas. Substitui o modelo de 2 abas (`Executivos`/`Visoes`): as visões saem de N1, N2 e N3 e o rótulo `código - papel - nome` é o das pastas de publicação. |
| D-17 | 17/09 | A chave rota ↔ hierarquia passa a ser o CÓDIGO do vendedor (N4). A planilha de rota ganha a coluna `Cód. vendedor`, que vira parte do modelo que o Gui entrega todo mês. Enquanto a coluna não existir, o pipeline liga pelo nome do executivo (que tem de ser único). |
| D-18 | 17/09 | Posições confirmadas pelo Douglas: **118 = HYGOR DOREA** (evidência: os 8 pedidos de set/26 com representante 118 são de clientes dele) e **119 = LUIS SOUSA** (por eliminação: única posição vaga do supervisor Hudson; sem pedido com o código 119 no mês). 121 · Litoral segue `[VAGO]` (os 33 clientes `[VAGO]` da rota são do litoral e os 3 pedidos com representante 121 são deles). Gravado no de-para; cabeçalho corrigido para `LOGIN MERCANET`. Versão anterior em `bases/Estrutura/_versoes/`. |
| D-19 | 17/09 | Coluna **`Cód. vendedor`** inserida na rota de setembro (`bases/Rota/Rota_14092026.xlsx`, depois de `Executivo`), preenchida pela hierarquia. Original intacto em `bases/Rota/_versoes/Rota_14092026_original.xlsx`. Conferido: 2.973 linhas, 22 códigos, 1 código = 1 executivo e 1 supervisor, demais colunas iguais (diferença máxima de 6e-11 em decimais, por regravação do xlsx). Este passa a ser o MODELO da rota mensal (13 colunas). |
| D-20 | 17/09 | Pasta de origem renomeada pelo Douglas para `bases/` (minúscula, como no DN e no Gerencial); config e docs atualizados. |
| D-21 | 17/09 | **9 painéis**: 1 head, 3 gerentes e 5 supervisores — todo nível da hierarquia recebe o seu, como no Gerencial (fecha a P-11). |
| D-22 | 17/09 | Fase 2: regras do protótipo 2 conferidas contra os dados embutidos nele e adotadas no config (`regras`): visita = cliente × dia com qualquer evento (inclui o dia que só tem check-out); minutos = maior par, check-out pareado com o último check-in anterior; pedido válido = situação ≠ Cancelado, valor = `Valor total do pedido`, janela = dia da rota + 1 dia corrido. Diferença deliberada: o modelo soma TODOS os pedidos da janela (o protótipo soma só o primeiro). |
| D-23 | 17/09 | Visita e pedido são atribuídos ao vendedor DONO da loja na rota do mês; o login serve à jornada do dia e à conferência. Reconciliação com o protótipo 2 (mês até 16/09): contagens idênticas nos 22 vendedores, salvo 1 visita do usuário de teste (`docs/07`). |
| D-24 | 17/09 | `calendario.feriados` no config (hoje: 07/09/2026) — só rotula dia útil; o planejado vem sempre das datas da rota. |
| D-25 | 17/09 | **"Com pedido" = pedido no mês** (fecha a P-13): a loja conta se tem pedido válido no mês até a data; "contato" e "visita + pedido" usam visita em qualquer dia do mês até a data — a mesma lógica da aderência (D-03). `regras.pedido.criterio: mes`. A regra da janela (dia da rota + 1) segue calculada na LOJA_MES e é a usada na reconciliação com o protótipo 2. |
| D-26 | 17/09 | Tela da Fase 3 aprovada: layout do Diário Rota + seletor de dia + blocos dia · semana · mês + tabela/gráfico por vendedor (por supervisor nas visões de gerente e head) + lista de lojas do dia. **Valor de pedido não vai para o painel** (D-04): só a quantidade solicitada, com o rótulo do config. |
| D-27 | 17/09 | O navegador não calcula indicador: `rota/painel.py` entrega os números de `metricas.kpis` por vendedor × dia de rota × escopo e o JavaScript só soma vendedores. O carimbo do painel é a data do arquivo de base mais recente (não o relógio): mesma base → mesmo HTML byte a byte (MD5 conferido em duas execuções). |

## Pendências

| # | Pendência | Com quem | Bloqueia |
|---|---|---|---|
| P-01 | ~~Hierarquia fechada com a rota~~ **feito em 17/09 (D-16 a D-19)**: chave por código, 22 posições = 22 vendedores da rota. Falta só: LOGIN MERCANET de 7 posições (Richard Silva, Hygor Dorea, Mauricio Rodrigues, Luis Sousa, Icaro Sanches, Marcus Flavio e o `[VAGO]` 121) — ligado à P-03 — e confirmar com o Gui a posição 119 = Luis Sousa e o `TESTERTM` ignorado | Douglas / Gui | atribuição de check-ins dessas 7 posições |
| P-02 | Unidade e nome do indicador de volume (`Quantidade solicitada`) | Gui | card de volume |
| P-03 | Por que 6 executivos não têm check-in (Hygor Dorea, Icaro Sanches, Luis Sousa, Marcus Flavio, Mauricio Rodrigues, Richard Silva) | Gui | leitura da aderência |
| P-04 | Corte de duração para visita válida e tempo em loja | Gui | Fase 2 |
| P-05 | Passar ao Gui o modelo da rota mensal: as 13 colunas de `bases/Rota/Rota_14092026.xlsx` (com `Cód. vendedor`), de preferência com nome fixo na coluna de data (ex.: `Data Rota`) | Douglas → Gui | rota de outubro |
| P-06 | Meta: arquivo próprio ou Net Sales 26 ÷ frequência? | Gui | fase 2 do produto |
| P-07 | `Frequência anual` é de visita ou de compra? | Gui | evolução da frequência |
| P-08 | Visitas em fim de semana e check-in em cliente fora da rota contam? | Gui | Fase 2 |
| P-09 | Pedido Bloqueado conta como pedido tirado? (o protótipo 2 conta) | Gui | Fase 2 |
| P-10 | Registro do contato telefônico (284 clientes) | Gui / Mercanet | fase 2 do produto |
| P-12 | Dia que só tem CHECK-OUT (sem check-in) conta como visita? O protótipo 2 conta (14 casos em set/26); o config segue o protótipo | Gui | — (parâmetro `regras.visita.eventos_que_contam`) |
| P-13 | ~~Regra do "com pedido"~~ **decidida em 17/09: pedido no mês (D-25).** Texto original: **Regra do "com pedido"**: hoje o pedido só conta para a loja se emitido no dia da rota ou 1 dia corrido depois (rota na sexta → pedido na segunda NÃO conta). Em set/26 isso deixa 502 de 548 pedidos fora: 42 lojas com pedido na janela × 238 com pedido no mês. Manter a janela, usar dia ÚTIL seguinte, ou medir pedido no mês (como a aderência)? | Gui / Douglas | leitura da positivação; Fase 3 (qual número vai no card) |
| P-14 | **Nome do cliente na rota**: a planilha de rota não traz razão social; o nome vem de pedido ou check-in, então **1.947 das 2.973 lojas** aparecem na lista só pelo código. Pedir ao Gui a coluna `Nome cliente` no modelo da rota (o leitor já aceita, opcional) | Douglas → Gui | qualidade da lista de lojas |
| P-15 | Pedido junto da VISITA real (mesmo dia ou dia útil seguinte ao check-in) como indicador de conversão | Douglas / Gui | fase 2 do produto |
