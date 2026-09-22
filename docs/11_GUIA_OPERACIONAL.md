# 11 · Guia operacional

Para quem roda o painel no dia a dia: Douglas; na ausência, Gui (D-10). Tudo é feito na pasta do projeto (`ROTA/`).
O que está marcado **A PREENCHER** depende de informação que só o Douglas tem e não foi inferido.

## Todo dia útil (≈ 10 minutos)

1. **Extrair do Mercanet**, sempre o mês corrente ACUMULADO (do dia 1 até hoje), nunca só o dia:
   - timeline de check-in/check-out → salvar como `bases/Mercanet/Mercanet.csv`
   - consulta de pedidos do canal Atacado → salvar como `bases/Pedidos/Pedidos.csv`
   - sell-in no BI (D-42), os 3 exports em sequência, com o mesmo filtro, salvos em `bases/SellIn/` com os nomes de sempre:
     `Projeto Rota.xlsx`, `Projeto Rota Carteira.xlsx` e `Proejto Rota Faturado.xlsx` (sem eles o painel sai, com aviso)
   - **A PREENCHER:** caminho de menu de cada consulta e os filtros exatos (período, canal, usuários). Atenção à P-03: conferir
     se a consulta de check-ins tem filtro de usuário/equipe que deixa vendedores de fora.
2. **Substituir, nunca somar.** O arquivo novo entra no lugar do antigo, com o mesmo nome. Se quiser guardar o antigo, mova para
   `_versoes/` (subpasta não é lida). Dois arquivos com o mesmo mês na mesma pasta ABORTAM a execução (D-13).
3. **Fechar os arquivos no Excel** e rodar:

   ```
   python run_rota.py
   ```

4. **Ler o fim do log.** O esperado é `SUCESSO — 0 aviso(s)`. Conferir a linha `MES ATE dd/mm/aaaa` (a data tem de ser a da
   extração) e a linha `9 paineis: zero vazamento…`.
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

## Virada do mês (≈ 1 hora)

1. Rota do mês novo (vem do Gui, 13 colunas, com `Cód. vendedor`) → `bases/Rota/`. A do mês anterior vai para `bases/Rota/_versoes/`.
2. Lojas novas da rota → incluir código e nome em `bases/Estrutura/Clientes_Rota.xlsx`. Se faltar alguma, o log avisa quantas.
3. Feriados do mês → `calendario.feriados` no config (feriado não conta como visita, D-32).
4. Mês fechado → reextrair check-ins e pedidos do mês inteiro no Mercanet e guardar ao lado do arquivo do mês corrente (D-07).
   **A PREENCHER:** nome de arquivo combinado para o mês fechado (ex.: `Mercanet_2026-09.csv`).

## Quando algo muda

| Mudou | O que fazer |
|---|---|
| Vendedor, supervisor ou login | editar `bases/Estrutura/DePara_Estrutura_Rota.xlsx` (1 linha por posição N4). Problema no de-para ABORTA (D-39) |
| Uma posição ficou vaga | nome `[VAGO]` no de-para e na rota, e o código N4 em `fontes.estrutura.posicoes_sem_login_aceitas` (a 121 foi preenchida em 22/09, D-43) |
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
