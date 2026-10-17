# iter25 — Hotfix 0.13.1 — o arquivo JSON de cada item da árvore carrega o próprio `status`, sempre em dia, conferido pelo validate e preenchido pelo upgrade nos itens existentes

## Resumo
0.13.1 — hotfix B-64 pedido pelo dono da cobaia .NET: o arquivo JSON de cada item da árvore (task, story, sprint,
feature, épico) grava o próprio `status`, sempre em dia. Valor canônico em inglês (D-37: TODO, BACKLOG, ACTIVE, DONE,
DROPPED; task com M2 = par `<STATUS>/<DELEG>`), exibição segue em português. O arquivo é regravado quando só o status
muda (transições M2); o validate acusa status divergente, fora do vocabulário ou ausente num alvo migrado, e reporta
falha de cálculo; o motor completa a migração no 1º commit de alvo não migrado; o upgrade 0.13.0→0.13.1 roda
`cs-state migrate item-status` (sem evento, idempotente). Oráculo 8/21 → 21/21.

## Critérios de aceite
### CA-01 — status no arquivo, igual ao derivado
DADO um alvo em modo árvore, QUANDO se cria um épico, uma sprint,
  uma feature, uma story e uma task (na sprint e no backlog), ENTÃO o arquivo JSON de cada um tem `status` igual a
  o valor CANÔNICO em inglês correspondente a `tree.status_of` (D-37: task na sprint `TODO`; backlog `BACKLOG`; sprint/feature/épico ativos `ACTIVE`; task com M2 o par `<STATUS>/<DELEG>`), e a exibição segue em português.
  Prova: `cd campanhas/iter25/oraculo && python3 -m unittest test_iter25.TestCA01`

### CA-02 — o status acompanha as transições M2
DADO uma task da árvore, QUANDO passa por start, dispatch, submit,
  verify, review e accept, ENTÃO depois de CADA comando o `status` do arquivo é igual ao derivado (o arquivo é regravado
  mesmo quando só o status mudou).
  Prova: `cd campanhas/iter25/oraculo && python3 -m unittest test_iter25.TestCA02`

### CA-03 — fechamento e descarte
DADO tasks e sprints, QUANDO se faz drop, close e o item vai para archive/, ENTÃO o
  arquivo em archive/ tem `status` `DROPPED` (descartado) ou `DONE` (fechado), correspondente ao derivado (D-37).
  Prova: `cd campanhas/iter25/oraculo && python3 -m unittest test_iter25.TestCA03`

### CA-04 — status editado à mão é acusado
DADO um item com `status` correto, QUANDO alguém troca o valor no arquivo,
  ENTÃO `cs-state validate --strict` sai ≠ 0 citando o item e o valor certo; sem edição, sai 0 (o campo novo não vira
  falso "edição à mão").
  Prova: `cd campanhas/iter25/oraculo && python3 -m unittest test_iter25.TestCA04`

### CA-05 — upgrade 0.13.1 preenche os itens existentes
DADO um alvo 0.13.0 com itens em state/, backlog/ e
  archive/ sem `status`, QUANDO roda `cs.py upgrade` e `upgrade --apply --allow-outside`, ENTÃO o plano lista 0.13.1, o
  apply grava `status` em TODOS os itens sem mudar nenhum outro campo, a cadeia de eventos não muda, `validate --strict`
  segue verde, e um segundo apply não altera nada; VERSION 0.13.1 com a migração no catálogo.
  Prova: `cd campanhas/iter25/oraculo && python3 -m unittest test_iter25.TestCA05`

## Linha do tempo
- 2026-10-14T20:25:21-0300 · inicio E0
- 2026-10-14T20:25:36-0300 · proposta E1
- 2026-10-14T20:25:57-0300 · aprovacao E1
- 2026-10-14T20:26:43-0300 · proposta E2
- 2026-10-14T20:28:46-0300 · aprovacao E2
- 2026-10-14T20:29:20-0300 · proposta E3
- 2026-10-14T20:29:44-0300 · aprovacao E3
- 2026-10-14T20:30:19-0300 · proposta E4
- 2026-10-14T20:30:44-0300 · aprovacao E4
- 2026-10-14T20:30:44-0300 · proposta E5
- 2026-10-14T20:31:24-0300 · aprovacao E5
- 2026-10-14T20:31:24-0300 · abertura abertura
- [NOTA] 2026-10-14T20:31:24-0300 — Abertura da feature iter25
- [PASS] 01-TASK-ORACULO — 2026-10-14T20:37:42-0300
- [NOTA] 02-TASK-STATUS-NO-ITEM — 2026-10-16T20:21:20-0300
- [REJECT] 02-TASK-STATUS-NO-ITEM — 2026-10-16T20:31:40-0300
- [REJECT] 02-TASK-STATUS-NO-ITEM — 2026-10-16T20:54:26-0300
- [PASS] 02-TASK-STATUS-NO-ITEM — 2026-10-16T21:27:01-0300
- [NOTA] 03-TASK-UPGRADE-VERSAO — 2026-10-16T21:27:02-0300
- [REJECT] 03-TASK-UPGRADE-VERSAO — 2026-10-16T21:38:17-0300
- [PASS] 03-TASK-UPGRADE-VERSAO — 2026-10-16T21:48:42-0300
- [NOTA] 04-TASK-QA — 2026-10-16T21:48:42-0300
- [PASS] 04-TASK-QA — 2026-10-16T23:50:07-0300
- [NOTA] 05-TASK-REVIEW — 2026-10-16T23:50:08-0300
- [PASS] 05-TASK-REVIEW — 2026-10-16T23:52:33-0300

## Tasks
| id | entrega | tipo | grupo | status | gate |
|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da iter25 (CA-01..CA-05), escrito por agente separado | ORACULO | — | DONE | PASS |
| 02-TASK-STATUS-NO-ITEM | gravar o status derivado no arquivo do item e conferi-lo no validate | CORRECAO | G1 | DONE | PASS |
| 03-TASK-UPGRADE-VERSAO | 0.13.1 com migração que preenche o status dos itens existentes | CORRECAO | G2 | DONE | PASS |
| 04-TASK-QA | Portão e oráculos, CA a CA | QA | — | DONE | PASS |
| 05-TASK-REVIEW | Revisão isolada da feature | REVIEW | — | DONE | PASS |

### Handoff 01-TASK-ORACULO
- Oraculista: Claude Code · general-purpose · opus, agente separado; não abriu a cópia do corretor.
- Arquivos: campanhas/iter25/oraculo/{ESPEC.md, test_iter25.py (19 testes: 12 D, 7 R), medir.py, base.txt}.
- Base reproduzida pelo tech-lead: 7/19 (D 0/12, R 7/7) em python3 3.13.3 e /usr/bin/python3 3.9.6; D falham por asserção.
- Calibração: mutação "status só por zona/tipo" passa CA-01/CA-03 e mantém CA-02 FAIL; o controle do CA-04 pega falso "edição à mão".
- Critério de eventos: events.jsonl idêntico em bytes (status derivado não entra na projeção).
- Congelado (ver oracle verify); escopo por snapshot: só os 4 arquivos; privacidade 0.
- Limites: R do CA-05 vacuamente verdes no HEAD (0.13.0→0.13.0); CA-04 aceita o valor certo em qualquer linha da saída.
- Mudança oficial 01 (D-37, oraculista opus separado): status canônico em inglês no arquivo, exibição em pt; +2 testes (exibição pt; valor fora do vocabulário). Base 8/21 (D 0/13, R 8/8) nos 2 Pythons; recongelado eb921af3a8f9.

### Handoff 02-TASK-STATUS-NO-ITEM
- Executores: ciclo 1 general-purpose · sonnet (status_code fonte única; materialize grava status e regrava quando só ele muda; validate; `cs-state migrate item-status [--dry-run]`); ciclo 2 opus (status ausente num alvo migrado acusado; falha de status_codes vira erro); ciclo 3 opus (materialize completa a migração no 1º commit de alvo não migrado — sem isso o oráculo iter23 falhava 2 testes).
- Escopo por snapshot: tree/hcore/engine/state + test_iter25_status (guard.py sem mudança); projeto vivo intocado; privacidade 0. Artefatos de build .NET não versionados em evals/fixtures/.../obj foram regenerados pelos testes (fora do git, fora do portão).
- Régua (tech-lead, ciclo 3): harness 425 OK (16 skips pré-existentes) em python3 e /usr/bin/python3; oráculos iter23 e iter24 OK nos 2; iter25 18/21 nos 2 (CA-01..CA-04 inteiros; CA-05 é da task 03).
- Revisores: opus a cada ciclo, instâncias isoladas: ciclo 1 APPROVED (2 MENOR de falha silenciosa ⇒ ciclo 2); ciclo 2 APPROVED; ciclo 3 APPROVED.
- Ressalvas MENOR: (a) o indício de alvo não migrado é sempre o mesmo item intocado — alvo que ficou pela metade com versão não publicada não é varrido e o validate acusa sem sugerir `cs-state migrate item-status` (mensagem deveria apontar o comando); (b) apagar `status` de TODOS os itens faz o alvo parecer não migrado (guard já nega Edit/Write em .swarm/state; sem perda de dado).
- Comando para a task 03: `cs-state migrate item-status` (tree.migrate_item_status; sem evento; idempotente).

### Handoff 03-TASK-UPGRADE-VERSAO
- Executores: ciclo 1 general-purpose · sonnet (VERSION 0.13.1, catálogo to 0.13.1 harness+item-status, ação item-status no upgrade, docs 09/10, test_iter25_upgrade); complemento sonnet (D-38: item-status em version.py); ciclo 2 opus (plano: itens presos antes da regravação; item-status só com contagem, sem ids).
- Mudança oficial 02 do oráculo iter23 (D-39, oraculista opus separado): item preso não muda de lugar nem de conteúdo além do campo `status` canônico.
- Escopo por snapshot: só os arquivos permitidos; projeto vivo intocado; privacidade 0.
- Régua: upgrade 37 OK (7 skip) e doctests 19 nos 2 Pythons; oráculo iter25 21/21 nos 2; iter23 41/41 contra a cópia nos 2.
- Revisor: general-purpose · sonnet, instância isolada · APPROVED. Ressalvas MENOR: o apply não confere events.jsonl intacto para item-status (só para state-format); sem teste do caminho de falha + restauração do backup; plano esconde o stderr quando o dry-run do motor falha.

### Handoff 04-TASK-QA
- QA sonnet · ACCEPT: portão VERDE + FIM (0 FAIL/ERROR), oráculos iter25 21/21 e iter13/16/18..24 nos 2 Pythons; D-35 sem regressões iter10/iter15; oracle verify intacto.

### Handoff 05-TASK-REVIEW
- Revisão da feature: opus, instância nova · APPROVED; caso da cobaia simulado ponta a ponta (13/13 itens, eventos intactos, idempotente); matriz no FEATURE.md. MENOR: docs/09 promete '(e quais)'; linha do item-status com prefixo duplicado contada como arquivo; PRÉ-EXISTENTE: SUBMITTED/RETURNED em task só submetida.

## Como a feature nasceu
### E0 — Pré-condição · CONCLUÍDA 2026-10-14T20:25:21-0300
- Demanda: "quero que a correcao seja agora: hotfix 0.13.1, status gravado no arquivo do item da árvore (B-64); a fábrica v8 já trata isso"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-14T20:25:57-0300
- Produzido: problema enunciado; FEATURE-ID iter25
- Itens aprovados: 1: valor = tree.status_of (uma fonte); 2: validate --strict reprova status divergente; 3: upgrade 0.13.1 preenche todos os itens, idempotente
- Aprovação: "ok"
- Sha: ed84fd092a55f7c03c5f7a4bf549b3723d92d3ce168fd74e3786ad5c028e76bf
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-14T20:28:46-0300
- Produzido: investigação F1-F5 (F5 descartado)
- Medido: 1 escrita de status (closed.status); 0 testes leem status do arquivo; 4 pontos mudam
- Aprovação: "ok"
- Sha: 17be38df477b13bcc8a2182d689a1d913664479205187e8dd50692387a9c6a4a
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-14T20:29:44-0300
- Produzido: FEATURE.md CA-01..CA-05; contrato PASS
- Aprovação: "ok"
- Sha: ecf2181227b32432c1ee8df1e9706081130adcb6533182c581abed8c74cec581
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-14T20:30:44-0300
- Produzido: 5 tasks; CA-01..CA-05 cobertos; contrato PASS
- Aprovação: "ok"
- Sha: 126d7012d59d0938c1386b00626a7a9a8bd193523ed59c2de38fe5ce7bff29da
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-14T20:31:24-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: a69b8653677c354c972e8aab2df3c22bc0ce5c93d3af50420a216be6a8f3f7b5
- Próxima: oráculo por agente separado

### Abertura · 2026-10-14T20:31:24-0300
- Campanha: campanhas/iter25
- Tasks: 5 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)

## Campanha
- campanha: campanhas/iter25 · etapa do motor: concluida · rodada: 0
- critério de parada: Oráculo iter25 100% verde (CA-01..CA-05) em python3 e /usr/bin/python3; oráculos iter13, iter16, iter18, iter19, iter20, iter21, iter22, iter23 e iter24 inteiros verdes; iter10/iter15 sem regressão contra o HEAD (D-35); suítes do produto e harness-dev verdes; 0 `def` removido; VERSION 0.13.1.
- escopo: scripts/harness/engine/tree.py, scripts/harness/engine/hcore.py, scripts/harness/engine/engine.py, scripts/harness/engine/state.py, scripts/harness/engine/guard.py, scripts/harness/tests/test_iter25_*.py, scripts/upgrade/core.py, scripts/upgrade/tests/test_iter25_*.py, references/migrations.json5, docs/09-upgrade.md, docs/10-arvore-de-estado.md, VERSION, README.md

## Oráculo
- `campanhas/iter25/oraculo/ESPEC.md`
- `campanhas/iter25/oraculo/test_iter25.py`
- `campanhas/iter25/oraculo/medir.py`
- `campanhas/iter25/oraculo/base.txt`

## Decisões técnicas
- Uma fonte só: `tree.status_code(tv, it)` dá o código; `status_of` deriva o texto pt dele.
- O status NÃO entra na projeção/board: é derivado na gravação ⇒ cadeia de eventos e replay inalterados (events.jsonl
  idêntico em bytes no upgrade).
- Validate: tira `status` antes de comparar com `item_to_en` e confere o campo à parte; ausência só aceita se nenhum
  item tem o campo (alvo não migrado).
- materialize lê 1 item intocado como indício; sem status ⇒ varre e regrava os intocados (1 leitura extra por commit
  no alvo já migrado).
- Upgrade: ação nova `item-status` (registrada em version.py, D-38) depois de harness/state-format; o plano mostra
  primeiro os itens presos e depois a contagem da regravação.
- Oráculo iter23 CA-08 (D-39): item preso pode ganhar só o campo `status`.

## Aprendizados
- Gravar valor de exibição no disco cimenta o idioma errado: a decisão D-37 (código en no dado, texto pt na tela)
  custou uma mudança oficial do oráculo antes da correção — barata porque veio antes.
- Toda regra de validate que depende de "o alvo já foi migrado?" precisa de um motor que nunca deixe estado parcial:
  a regra do ciclo 2 quebrou o oráculo iter23 até o ciclo 3 fazer o materialize completar a migração.
- Listas fechadas (KINDS do catálogo) são um contrato escondido: a ação nova parou a 03 até entrar em version.py.
- Saída do plano é contrato com oráculos antigos (iter23 lê a 1ª menção do id): mudar a ordem/forma da saída precisa
  rodar os oráculos do upgrade.
- Revisor opus em cada ciclo pegou as 2 falhas silenciosas e o estado parcial antes do portão.
- Custo medido: opus 10 despachos, sonnet 5 (+ oraculistas); 0 NOT_RUN.

## Arquivos da feature
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/hcore.py`
- `scripts/harness/engine/engine.py`
- `scripts/harness/engine/state.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/tests/test_iter25_status.py`
- `scripts/upgrade/core.py`
- `scripts/upgrade/tests/test_iter25_upgrade.py`
- `references/migrations.json5`
- `docs/09-upgrade.md`
- `docs/10-arvore-de-estado.md`
- `VERSION`
- `README.md`
- `scripts/upgrade/version.py`

## Aceite da Feature
### Aceite QA — ACCEPT
### Aceite Review — APPROVED
<!-- fechar-feature:archive-completo -->
