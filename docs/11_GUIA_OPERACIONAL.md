# 11 · Guia operacional

Para quem roda o painel no dia a dia: Douglas; na ausência, Gui (D-10). Tudo é feito na pasta do projeto (`ROTA/`).
O que está marcado **A PREENCHER** depende de informação que só o Douglas tem e não foi inferido.

## Todo dia útil (≈ 10 minutos)

1. **Extrair do Mercanet**, sempre o mês corrente ACUMULADO (do dia 1 até hoje), nunca só o dia:
   - timeline de check-in/check-out → salvar como `bases/Mercanet/Mercanet_AAAA-MM.csv` (ex.: `Mercanet_2026-10.csv`), no lugar do arquivo do mesmo mês
   - consulta de pedidos do canal Atacado → salvar como `bases/Pedidos/Pedidos_AAAA-MM.csv`, idem
   - sell-in no BI (D-42), os 3 exports em sequência, com o mesmo filtro, salvos em `bases/SellIn/` com os nomes de sempre:
     `Projeto Rota.xlsx`, `Projeto Rota Carteira.xlsx` e `Proejto Rota Faturado.xlsx` (sem eles o painel sai, com aviso)
     (D-44: alimentam o bloco "Sell-in do mês", o card da semana e as colunas Faturado / % meta / % c/ carteira)
   - **A PREENCHER:** caminho de menu de cada consulta e os filtros exatos (período, canal, usuários). Atenção à P-03: conferir
     se a consulta de check-ins tem filtro de usuário/equipe que deixa vendedores de fora.
2. **Substituir, nunca somar.** O arquivo novo entra no lugar do antigo, com o mesmo nome. Se quiser guardar o antigo, mova para
   `_versoes/` (subpasta não é lida). Dois arquivos com o mesmo mês na mesma pasta ABORTAM a execução (D-13).
3. **Fechar os arquivos no Excel** e rodar:

   ```
   python run_rota.py
   ```

4. **Ler o fim do log.** O esperado é `SUCESSO — N aviso(s)`. Conferir a linha `MES CORRENTE AAAA-MM ATE dd/mm/aaaa` (a data tem de ser
   a da extração) e a linha `9 paineis: zero vazamento…`. Avisos **normais**, que não impedem publicar (D-48): `sell-in … RECEITA diferente
   … exports em momentos diferentes` (os 3 exports não saem no mesmo segundo) e `vendedor(es) do BI fora do de-para ['145']` (P-17).
   Qualquer outro aviso: ler antes de publicar.
5. **Publicar** (só depois que a publicação for liberada — ver abaixo):

   ```
   python run_rota.py --publicar
   ```

   Painel que não mudou aparece como `sem mudanca` e não é recopiado.

## Os três modos da publicação

| Comando | O que faz | Toca em `Painéis Comerciais`? |
|---|---|---|
| `python run_rota.py` | gera os 9 painéis em pasta local e LISTA o plano de publicação | não |
| `python run_rota.py --ensaio` | além disso, copia para `%LOCALAPPDATA%\Dori\ROTA\ensaio_publicacao\Gerencial` | não |
| `python run_rota.py --publicar` | copia para `Painéis Comerciais\Gerencial\<usuário>\Painel_Rota.html` | **sim**, e só se `publicacao.liberada: true` |

**A trava (D-28):** `publicacao.liberada` está `false` em `config/config.yaml`. Enquanto estiver assim, `--publicar` recusa e não
copia nada. Quem vira para `true` é o Douglas, uma vez, depois da validação com o time (Gui, supervisores, gerentes e head).

Regras da cópia: tudo ou nada (se um painel falhar na geração, nenhum é publicado); o arquivo vai para um `.tmp` e troca de nome
no fim; o md5 é conferido depois; nada é apagado na pasta do usuário (os painéis do Gerencial e do DN moram lá).

## Virada do mês (≈ 1 hora) — D-45: o mês fechado continua no painel

0. **Último dia útil do mês:** fazer a extração do dia normalmente. É ela que o mês fechado mostra até a reextração do dia 5; sem ela, o
   mês fechado sai parcial nos primeiros dias do mês seguinte.
1. Rota do mês novo (vem do Gui, 13 colunas, com `Cód. vendedor`) → `bases/Rota/Rota_AAAA-MM.xlsx` (ex.: `Rota_2026-10.xlsx`). **Sem a rota
   do mês novo o pipeline aborta inteiro assim que houver check-in ou pedido do mês novo, e nem o mês fechado sai** (P-18): pedir a rota ao Gui
   antes do dia 1. A do mês anterior FICA na pasta (é ela que dá o mês fechado); `_versoes/` é só para versão substituída de um mesmo mês.
2. Extrações de check-ins e pedidos do mês novo com o mês no nome (`Mercanet_2026-10.csv`, `Pedidos_2026-10.csv`); as do mês anterior
   ficam ao lado, com o nome delas. Dois arquivos do MESMO mês na mesma pasta abortam (D-13).
3. Sell-in do mês novo nos 3 arquivos da raiz de `bases/SellIn/` (mesmos nomes de sempre).
4. **Dia 5 do mês seguinte:** reextrair o mês fechado UMA vez — check-ins e pedidos do mês inteiro (substituindo os arquivos do mês
   fechado) e os 3 exports do BI com o filtro "Ano mês" do mês fechado, salvos em `bases/SellIn/AAAA-MM/` (ex.: `bases/SellIn/2026-09/`).
   Depois disso o mês fechado não é mais tocado.
5. Lojas novas da rota → incluir código e nome em `bases/Estrutura/Clientes_Rota.xlsx`. Se faltar alguma, o log avisa quantas.
6. Feriados do mês → `calendario.feriados` no config (feriado não conta como visita, D-32).
7. Vendedor que saiu → data na coluna `ENCERRADA EM` do de-para (a posição fica lá, para os meses fechados). Vendedor novo → linha nova
   no de-para e no filtro N4 dos exports do BI.

No painel, o seletor "Mês" mostra o mês em andamento e os últimos 12 meses fechados (`painel.meses_fechados`).

## Quando algo muda

| Mudou | O que fazer |
|---|---|
| Vendedor, supervisor ou login | editar `bases/Estrutura/DePara_Estrutura_Rota.xlsx` (1 linha por posição N4). Problema no de-para ABORTA (D-39) |
| Uma posição ficou vaga | nome `[VAGO]` no de-para e na rota, e o código N4 em `fontes.estrutura.posicoes_sem_login_aceitas` (a 121 foi preenchida em 22/09, D-43) |
| **Os pesos das semanas do sell-in** (S1 30 · S2 30 · S3 20 · S4 20, a confirmar com o time) | editar `metas_sellin.pesos` no config (somam 100), rodar `python run_rota.py`; o rodapé do painel mostra os pesos em uso. Mês com pesos próprios: `metas_sellin.pesos_por_mes`. Faixas das semanas: `calendario.semanas_do_mes` |
| Voltar a semana para "segunda até o dia" (D-02) | `calendario.semana: segunda` — o sell-in fica sem meta semanal |
| Quantos meses fechados ficam no painel | `painel.meses_fechados` (12). O período em que a tabela abre: `painel.periodo_inicial` (mes) |
| Uma regra de negócio | editar a lista no config (`regras.*`), rodar os testes, registrar a decisão em `docs/10_DECISOES.md` |
| Vendedor novo no Projeto Rota | incluir o nome dele no filtro `Nome Vendedor Novo (N4)` dos 3 exports do BI, além do de-para |
| Nome de loja errado | corrigir em `Clientes_Rota.xlsx` |

Testes (rodar depois de qualquer mudança de regra ou de código):

```
python tests/test_leitores.py
python tests/test_regras.py
python tests/test_publicar.py
```

## Quando dá erro

| Mensagem | Causa provável | Saída |
|---|---|---|
| `PermissionError … .xlsx` ou `.csv` | arquivo aberto no Excel ou OneDrive sincronizando | fechar o arquivo, esperar a sincronização, rodar de novo |
| `o mes AAAA-MM aparece em DOIS arquivos` | extração antiga esquecida na pasta ou cópia de conflito do OneDrive | mover a versão antiga para `_versoes/` |
| `coluna(s) obrigatoria(s) ausente(s)` | o layout da extração mudou | conferir a consulta no Mercanet; os nomes aceitos estão em `fontes.*.colunas` |
| `nao reconcilia` (pedidos) | arquivo truncado ou locale diferente | extrair de novo |
| `de-para de estrutura com N problema(s)` | hierarquia não fecha com a rota ou com os check-ins | corrigir o de-para; os problemas vêm listados acima da mensagem |
| `VAZAMENTO` ou `soma entre niveis` | erro de recorte — não publicar | guardar o log e avisar |
| `publicacao.liberada esta false` | a trava da D-28 está fechada | é o esperado até a validação com o time |

Logs e resumo de cada execução: `data/rota/logs/`. Relatório de qualidade e listas de exceção: `data/rota/quality/`.

## Máquina do suplente (Gui) — A PREENCHER após o teste (T11)

- Python instalado e `pip install -r requirements.txt` feito na pasta do projeto.
- A pasta `Painéis - Alavancas\ROTA` sincronizada pelo OneDrive, com `bases/` e `config/`.
- Acesso de escrita a `Painéis Comerciais\Gerencial`.
- Uma execução completa de `python run_rota.py --ensaio` feita por ele, com `SUCESSO` no fim.
