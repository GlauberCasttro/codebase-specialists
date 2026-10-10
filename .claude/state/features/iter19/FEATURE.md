# iter19 — Estado legível em JSON, chaves em inglês, amend refletido no arquivo

FEATURE-ID: iter19
Nome: Estado legível em JSON, chaves em inglês, amend refletido no arquivo, cs-state show e migração automática

## História
Como dono de um alvo com o harness gerado, quero que o arquivo de estado de cada entidade (task, story, sprint,
feature, épico, sessão) seja JSON padrão, em ordem de leitura, com chaves em inglês e sempre igual ao estado real
(inclusive depois de `cs-state amend`), legível também por `cs-state show`, e que o upgrade converta os alvos
existentes sozinho, para que eu possa abrir o arquivo e confiar no que leio.

## Problema / Contexto
Uso real na segunda cobaia .NET (BACKLOG B-14): o arquivo de task da SPR-001 era difícil de ler e mentia.
- Ordem alfabética, indentação 1 e objetos ora inline ora expandidos nascem em `j5._dump` (j5.py:124-141), usado por
  `hcore.write_json5` (hcore.py:229-230) e `tree.render` (tree.py:60-61) — E2 F1.
- Chaves misturam pt e en: `tipo`, `como/quero/para`, `criterios{gherkin,teste}`, `historico{acao,de,para}`,
  `closed{entregue,…}`, `metricas` ao lado de `agent`, `allowed_paths` (E2 F3, tree.py:226-229, 412-447, 836-851).
- BUG: `cs-state amend` em task iniciada grava só ops `set` no objeto M2 (cmds.py:903-909), sem `tput` no item da
  árvore; `materialize` não reescreve o arquivo (tree.py:336-340); no reopen `_m2_task` recria o AC removido
  (tree.py:683-686) — E2 F2.
- Não há `cs-state show` (state.py:437) — E2 F6.
- 34 de 70 eventos de um alvo real citam `.json5` dentro de ops encadeadas (hcore.py:325-337): a migração não pode
  reescrever o histórico — E2 F4.
Decisões da E1 (founder, "ok"): chaves do mandato M5 ficam em pt (só formato muda; selo é hash delas, auto.py:58);
memória do cs-mem fora; migração por evento novo encadeado. Idioma das chaves: inglês (founder, 2026-10-07).

## Valor de negócio
O arquivo de estado passa a ser a fonte da verdade legível do alvo: quem abre entende sem conhecer o motor, e o que lê
é o que o motor decide. Remove uma classe inteira de engano (decisão tomada sobre arquivo desatualizado) e chega aos
alvos existentes sem trabalho manual nem `--no-verify`.

## Personas / Stakeholders
- dono do alvo (lê e revisa tasks/stories no editor e no diff do git)
- orquestrador e subagentes do alvo (leem o estado; usam amend e show)
- founder da fábrica (mantém o motor; aprova o upgrade)

## Critérios de Aceitação
- **CA-01 — JSON padrão em ordem de leitura.** DADO um alvo em modo árvore, QUANDO o motor grava qualquer entidade
  (task, story, sprint, feature, épico, sessão, projeção), ENTÃO o arquivo é `.json` que `json.loads` aceita, indentado
  com 2 espaços, um item de lista por linha, chaves na ordem de leitura (id, kind, type, title, agent, allowed_paths,
  protected_paths, as_a, i_want, so_that, acceptance_criteria, …, timestamps, internos, history por último), com
  `_generated_by` como campo, e serializar o mesmo estado 2 vezes dá os mesmos bytes; o validate continua verde.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA01`
- **CA-02 — chaves em inglês, leitura das antigas.** DADO o estado de uma entidade, QUANDO é gravado, ENTÃO nenhuma
  chave de entidade está em português (mapa por caminho: `para` da story → `so_that`, `para` do histórico → `to`),
  exceto as do mandato M5; E QUANDO o motor lê um arquivo com as chaves antigas em pt, ENTÃO entende como as novas.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA02`
- **CA-03 — amend refletido no arquivo.** DADO uma task iniciada com AC-1 e AC-2, QUANDO `cs-state amend` remove o
  AC-2, ENTÃO o arquivo da task deixa de listar o AC-2, o `history` registra antes, depois e motivo, e um reopen não
  ressuscita o AC-2; e DADO uma task não iniciada, QUANDO o amend muda `acceptance_criteria`, ENTÃO é aceito e refletido.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA03`
- **CA-04 — cs-state show.** DADO uma entidade existente (id ou alias), QUANDO `cs-state show <id>` roda, ENTÃO imprime
  Markdown com título, agente, escopo, critérios, estado e histórico resumido, sem escrever nada; id inexistente sai
  com erro.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA04`
- **CA-05 — migração automática no upgrade.** DADO um alvo 0.10.1 realista (≥ 30 eventos, itens em backlog, state e
  archive, arquivos `.json5`), QUANDO roda `cs.py upgrade` (plano) e depois `upgrade --apply`, ENTÃO o plano lista o
  que muda sem escrever; o apply converte todo `.json5` de estado de entidade para `.json` com a ordem e as chaves
  novas por UM evento encadeado novo com o mapa de caminhos, sem reescrever eventos antigos; validate e cadeia íntegros
  antes e depois; rodar de novo não muda nada; e o commit do resultado passa no pre-commit sem `--no-verify`.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA05`
- **CA-06 — o que não muda continua igual.** DADO a mudança aplicada, QUANDO se compara com antes, ENTÃO logs JSONL
  (events, ledger, approvals, model-router), arquivos de config JSON5 (team, config, machines, routing, run,
  migrations), memória do cs-mem e chaves do mandato M5 ficam iguais; e VERSION é 0.11.0 com a migração no catálogo.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA06`

## RNFs
- RNF-01: Python 3.9+ stdlib; verde em `python3` e `/usr/bin/python3` (o portão roda os dois).
- RNF-02: `hcore.canonical` (sort_keys) não muda: é a base do hash da cadeia.
- RNF-03: a migração é idempotente e tem dry-run; falha ⇒ o upgrade restaura o backup (comportamento atual).
- RNF-04: nenhum `def` removido; oráculos iter16, iter18 (R1–R7) e iter20 continuam verdes.

## Edge cases
- alvo com mistura de `.json5` e `.json` (migração interrompida): a leitura aceita os dois e o apply completa.
- `.json5` de estado órfão que sobrar depois da migração: o validate acusa.
- chave desconhecida numa entidade: vai para o fim, em ordem alfabética, antes de `history`.
- evento antigo citando caminho `.json5`: resolvido pelo mapa do evento de formato (views/find/show).
- alvo no board plano (pré-0.7.0): migra primeiro por `state-tree` e depois pelo formato.
- amend de campo não espelhável: segue só na M2, como hoje, com mensagem clara.

## Dependências
- iter20 (0.10.1) entregue: o atestado do pre-commit e a regra de estado-validado (guard.py:609-616) já existem.
- B-19 (descarte de task não iniciada) é independente; não bloqueia.

## Escopo IN
- serialização de estado de entidade e da projeção (JSON, ordem, indent 2, `_generated_by`); chaves em inglês com
  leitura dos aliases pt; amend refletido no arquivo (task iniciada e não iniciada); `cs-state show`; migração
  `arvore.format` no upgrade com validate antes e depois; versão 0.11.0; docs do formato e da migração.

## Escopo OUT
- logs JSONL; config/produto em JSON5; o parser `j5` (fica); `hcore.canonical`; chaves do mandato M5 (item novo no
  BACKLOG); memória do cs-mem; nomes de pasta em pt (`epicos/`, `sessoes/`) e valores em pt (`kind: "epico"`); flags
  da CLI; backups; B-19; harness de desenvolvimento (`.claude/`).

## Escopo de escrita
- `scripts/harness/engine/*.py`
- `scripts/harness/tests/*.py`
- `scripts/upgrade/*.py`
- `scripts/upgrade/tests/*.py`
- `references/migrations.json5`
- `references/*.md`
- `docs/*.md`
- `assets/templates/*.md`
- `assets/templates/state/*.md`
- `VERSION`
- `README.md`

## Critério de parada
oráculo iter19 100% verde (CA-01..CA-06) em python3 e /usr/bin/python3; oráculos iter16, iter18 R1–R7 e iter20 verdes;
suítes do produto e harness-dev verdes; 0 `def` removido; VERSION 0.11.0.

## Métrica de sucesso
Num alvo real migrado: 0 arquivos de estado de entidade em `.json5` (hoje 33 no alvo medido), 0 chaves pt fora do
mandato, e 1 de 1 amend refletido no arquivo (hoje 0 de 1).

## Aceite da Feature
### Aceite QA — PENDENTE
### Aceite Review — PENDENTE
