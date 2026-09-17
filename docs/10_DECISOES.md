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
| D-11 | 17/09 | `Bases/` organizada em subpastas por fonte (Rota, Mercanet, Pedidos, Estrutura); os 3 arquivos foram movidos sem alteração (MD5 conferido). `Painel Referência/` e `Transcrições/` ficam onde estão. |
| D-12 | 17/09 | Git local na pasta do projeto, sem remoto; `Bases/`, `data/`, protótipos e transcrições fora do versionamento. |
| D-13 | 17/09 | Mesmo mês em dois arquivos da mesma fonte ABORTA (padrão DN/Gerencial); versão antiga vai para subpasta não lida. Substitui a proposta da Etapa 6 de "vale a mais recente". |
| D-14 | 17/09 | Minimização no staging: endereço, descrição, latitude/longitude (check-ins) e CNPJ/CPF, ordem de compra, nota fiscal, desconto e preço médios (pedidos) não são ingeridos. |
| D-15 | 17/09 | Enquanto o de-para oficial não chega, `fontes.estrutura.obrigatorio: false` (ausência e pendências = aviso). Ao chegar, passa a `true` (aborta). |

## Pendências

| # | Pendência | Com quem | Bloqueia |
|---|---|---|---|
| P-01 | Preencher `DePara_Estrutura_Rota_MODELO.xlsx` e salvar em `Bases/Estrutura/DePara_Estrutura_Rota.xlsx`: confirmar 15 logins sugeridos, informar os 6 sem check-in, usuários e pastas das 7 visões, gerente de Hudson · Robson · Marco, confirmar `TESTERTM` ignorado | Gui / Atacado | Fase 2 |
| P-02 | Unidade e nome do indicador de volume (`Quantidade solicitada`) | Gui | card de volume |
| P-03 | Por que 6 executivos não têm check-in (Hygor Dorea, Icaro Sanches, Luis Sousa, Marcus Flavio, Mauricio Rodrigues, Richard Silva) | Gui | leitura da aderência |
| P-04 | Corte de duração para visita válida e tempo em loja | Gui | Fase 2 |
| P-05 | Layout fixo da rota mensal (nome estável da coluna de data) e nome do arquivo | Gui | robustez (o leitor já tolera o mês no nome da coluna) |
| P-06 | Meta: arquivo próprio ou Net Sales 26 ÷ frequência? | Gui | fase 2 do produto |
| P-07 | `Frequência anual` é de visita ou de compra? | Gui | evolução da frequência |
| P-08 | Visitas em fim de semana e check-in em cliente fora da rota contam? | Gui | Fase 2 |
| P-09 | Pedido Bloqueado conta como pedido tirado? (o protótipo 2 conta) | Gui | Fase 2 |
| P-10 | Registro do contato telefônico (284 clientes) | Gui / Mercanet | fase 2 do produto |
