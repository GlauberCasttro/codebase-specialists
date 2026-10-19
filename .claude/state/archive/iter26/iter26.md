# iter26 — Canonização do modelo de itens (inglês por dentro e na CLI, com aliases), remoção dos campos gravados e nunca lidos, histórico de rejeição e de gate por tentativa, custo real (tokens) por despacho, verify sem culpar a task pela escrita do próprio harness (B-49) e aviso do git add depois do close (B-67)

## Resumo
0.14.0: modelo de itens canônico. Tasks novas sem os 5 campos mortos (tolerados na leitura, sem migração); épico grava
`kind: "epic"` ("epico" segue lido); `repro_steps` separado de `failing_test`; CLI, templates, docs e textos emitidos em
inglês com aliases pt depreciados (aviso no stderr); `rejections` e `gate_history` por tentativa (o "último" segue);
tokens por despacho medidos no guard (`delegation.usage`, NOT_RUN/ERROR com motivo, nunca zero); verify não culpa a
task pelo caderno regravado pelo harness (B-49); `close` e orquestrador orientam o `git add` (B-67). Oráculo 51/51
nos 2 Pythons; portão VERDE; D-35 sem regressão.

## Critérios de aceite
### CA-01 — sem campos mortos
DADO um alvo 0.14.0, QUANDO se cria uma task (avulsa, de story e a partir da árvore
  no start), ENTÃO a task NÃO tem `dod`, `handoff`, `knowledge_context`, `briefing.context` nem `briefing.scope.in`, e
  o `add` não faz busca na memória; um alvo com tasks antigas que têm esses campos continua carregando, despachando e
  validando (`validate --strict` OK).
  Prova: `cd campanhas/iter26/oraculo && python3 -m unittest test_iter26.TestCA01`

### CA-02 — épico e chaves internas em inglês
DADO um alvo 0.14.0, QUANDO se cria um épico, ENTÃO o arquivo grava
  `kind: "epic"`; um arquivo antigo com `kind: "epico"` é lido como épico (board/show/validate iguais); os demais campos
  do disco continuam iguais aos da 0.13.1 (B-14) e a exibição não muda.
  Prova: `cd campanhas/iter26/oraculo && python3 -m unittest test_iter26.TestCA02`

### CA-03 — passos de reprodução separados do teste que falha
DADO um BUG criado na árvore com passos de
  reprodução e com teste que falha, QUANDO se grava, ENTÃO os passos ficam em `repro_steps` e o teste em
  `failing_test`, cada um no seu campo; um arquivo antigo (passos em `failing_test`) continua carregando sem perder o
  texto.
  Prova: `cd campanhas/iter26/oraculo && python3 -m unittest test_iter26.TestCA03`

### CA-04 — CLI e textos em inglês, português como alias
DADO um alvo 0.14.0, QUANDO se usa `cs-state new` com as
  flags em inglês (`--type`, `--as-a`, `--i-want`, `--so-that`, `--reason`, `new epic`), ENTÃO funciona; com as flags e
  o subcomando antigos em português, funciona igual e imprime um aviso de depreciação; o help, os templates e os textos
  emitidos citam só o inglês.
  Prova: `cd campanhas/iter26/oraculo && python3 -m unittest test_iter26.TestCA04`

### CA-05 — histórico de rejeição e de gate por tentativa
DADO uma task que passa por reject → retry → verify →
  reject → retry → verify → accept, QUANDO se consulta a task (`cs-state show`/JSON), ENTÃO há a lista de rejeições
  (tentativa, motivo, quem, quando) e a lista de resultados do gate por tentativa (exit, shas, quando), e o "último" que
  o motor já usa continua igual.
  Prova: `cd campanhas/iter26/oraculo && python3 -m unittest test_iter26.TestCA05`

### CA-06 — custo real por despacho
DADO um despacho cujo transcript tem `usage`, QUANDO o guard mede o modelo,
  ENTÃO a delegação grava os tokens (entrada, saída, cache) junto do modelo medido; sem transcript, grava NOT_RUN com o
  motivo (nunca zero); uma falha da medição fica registrada, não some.
  Prova: `cd campanhas/iter26/oraculo && python3 -m unittest test_iter26.TestCA06`

### CA-07 — 0.14.0 chega aos alvos sem regressão
DADO um alvo 0.13.1, QUANDO roda `cs.py upgrade` e
  `upgrade --apply --allow-outside`, ENTÃO o plano lista 0.14.0 (harness + emit), o apply reemite os textos em inglês,
  `validate --strict` segue OK e os itens antigos continuam legíveis; VERSION 0.14.0 com a migração no catálogo.
  Prova: `cd campanhas/iter26/oraculo && python3 -m unittest test_iter26.TestCA07`

### CA-08 — o verify não culpa a task pela escrita do harness
DADO uma task submetida, QUANDO, entre o dispatch e
  o verify, o próprio harness regrava o caderno de um agente (o da task ou de outro) por `cs-mem notebook`/`correct`
  ou pelo upgrade, ENTÃO o verify NÃO acusa "alterado FORA de allowed_paths" por esse caderno; se o caderno mudou de um
  jeito que o harness não produziria (bloco gerado diferente do render do cs-mem), ou outro arquivo em área reservada
  mudou, o verify continua acusando.
  Prova: `cd campanhas/iter26/oraculo && python3 -m unittest test_iter26.TestCA08`

### CA-09 — o orquestrador avisa o git add depois do close
DADO um alvo emitido pela 0.14.0, QUANDO se lê o texto
  do orquestrador (e a saída do `close` de task/story/sprint), ENTÃO ele orienta a incluir os arquivos movidos para
  archive/ (`git add .swarm` antes do commit).
  Prova: `cd campanhas/iter26/oraculo && python3 -m unittest test_iter26.TestCA09`

## Linha do tempo
- 2026-10-17T00:05:43-0300 · inicio E0
- 2026-10-17T00:06:06-0300 · proposta E1
- 2026-10-17T00:07:33-0300 · aprovacao E1
- 2026-10-17T00:08:04-0300 · proposta E2
- 2026-10-17T00:08:29-0300 · aprovacao E2
- 2026-10-17T00:09:03-0300 · proposta E3
- 2026-10-17T00:11:53-0300 · aprovacao E3
- 2026-10-17T00:12:49-0300 · proposta E4
- 2026-10-17T00:15:58-0300 · rejeicao E4
- 2026-10-17T00:17:12-0300 · proposta E4
- 2026-10-17T00:17:48-0300 · aprovacao E4
- 2026-10-17T00:17:48-0300 · proposta E5
- 2026-10-17T00:18:05-0300 · aprovacao E5
- 2026-10-17T00:18:05-0300 · abertura abertura
- [NOTA] 2026-10-17T00:18:05-0300 — Abertura da feature iter26
- [PASS] 01-TASK-ORACULO — 2026-10-17T00:32:25-0300
- [NOTA] 02-TASK-MODELO-CANONICO — 2026-10-17T11:09:26-0300
- [NOTA] 03-TASK-CUSTO-NO-GUARD — 2026-10-17T11:09:27-0300
- [PASS] 03-TASK-CUSTO-NO-GUARD — 2026-10-17T11:15:47-0300
- [PASS] 02-TASK-MODELO-CANONICO — 2026-10-17T12:16:33-0300
- [NOTA] 04-TASK-TEXTOS-EN — 2026-10-17T12:16:39-0300
- [NOTA] 08-TASK-VERIFY-HARNESS — 2026-10-17T12:16:39-0300
- [PASS] 08-TASK-VERIFY-HARNESS — 2026-10-17T12:47:05-0300
- [PASS] 04-TASK-TEXTOS-EN — 2026-10-17T12:57:43-0300
- [NOTA] 05-TASK-VERSAO — 2026-10-17T12:57:52-0300
- [PASS] 05-TASK-VERSAO — 2026-10-17T13:10:16-0300
- [NOTA] 06-TASK-QA — 2026-10-17T13:12:11-0300
- [REJECT] 06-TASK-QA — 2026-10-17T13:51:51-0300
- [REJECT] 02-TASK-MODELO-CANONICO — 2026-10-17T13:51:52-0300
- [REJECT] 03-TASK-CUSTO-NO-GUARD — 2026-10-17T13:51:52-0300
- [REJECT] 04-TASK-TEXTOS-EN — 2026-10-17T13:51:52-0300
- [REJECT] 05-TASK-VERSAO — 2026-10-17T14:24:09-0300
- [PASS] 02-TASK-MODELO-CANONICO — 2026-10-17T14:33:42-0300
- [PASS] 03-TASK-CUSTO-NO-GUARD — 2026-10-17T14:33:42-0300
- [PASS] 04-TASK-TEXTOS-EN — 2026-10-17T14:33:42-0300
- [PASS] 05-TASK-VERSAO — 2026-10-17T14:33:42-0300
- [NOTA] 06-TASK-QA — 2026-10-17T20:03:23-0300
- [PASS] 06-TASK-QA — 2026-10-18T13:29:41-0300
- [NOTA] 07-TASK-REVIEW — 2026-10-18T13:29:44-0300
- [PASS] 07-TASK-REVIEW — 2026-10-18T14:45:24-0300

## Tasks
| id | entrega | tipo | grupo | status | gate |
|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da iter26 (CA-01..CA-09), escrito por agente separado | ORACULO | — | DONE | PASS |
| 02-TASK-MODELO-CANONICO | campos mortos fora, chaves/kind em inglês, repro_steps, CLI com aliases, histórico por tentativa; saída do close orienta o git add | CORRECAO | G1 | DONE | PASS |
| 03-TASK-CUSTO-NO-GUARD | tokens reais por despacho medidos no guard, sem falha silenciosa | CORRECAO | G2 | DONE | PASS |
| 04-TASK-TEXTOS-EN | templates, textos emitidos e docs da CLI em inglês | CORRECAO | G3 | DONE | PASS |
| 05-TASK-VERSAO | 0.14.0 com migração no catálogo e nota de upgrade | CORRECAO | G3 | DONE | PASS |
| 06-TASK-QA | Portão e oráculos, CA a CA | QA | — | DONE | PASS |
| 07-TASK-REVIEW | Revisão isolada da feature | REVIEW | — | DONE | PASS |
| 08-TASK-VERIFY-HARNESS | verify não culpa a task pela escrita do próprio harness nos cadernos (B-49) | CORRECAO | G1 | DONE | PASS |

### Handoff 01-TASK-ORACULO
- Oraculista: Claude Code · general-purpose · opus, agente separado; não abriu a cópia do corretor.
- Arquivos: campanhas/iter26/oraculo/{ESPEC.md, test_iter26.py (51 testes: 36 D, 15 R), medir.py, base.txt}.
- Base reproduzida pelo tech-lead: 15/51 (D 0/36, R 15/15) em python3 3.13.3 e /usr/bin/python3 3.9.6; D por asserção.
- Calibração: mutação A (isenção cega do caderno) reprovada pelo controle do caderno adulterado; mutação C (tokens) 4/4; mutação B (NOT_RUN com 0) reprovada.
- Escolhas do oráculo que o corretor segue (ESPEC.md): flags `--repro`/`--failing-test` (CA-03); listas do CA-05 achadas pela forma; tokens somados do usage (CA-06); linhas do cs-auto fora da varredura do CA-04; help só com flags en.
- Limites: CA-05 sem mutação boa conhecida; CA-07 e controles legados só medidos como no-op no HEAD; CA-09 confere só o orchestrator.md.

### Handoff 02-TASK-MODELO-CANONICO
- Executor: Claude Code · general-purpose · model sonnet (ciclo 1). Arquivos: scripts/harness/engine/cmds.py (sem campos mortos nem busca BM25 no add; `rejections` e `gate_history` por tentativa via op append; reject_reason/gate_report seguem o último), tree.py (repro_steps; show de BUG antigo; validate aceita "epico"; migrações preservam o kind), hcore.py (kind epic↔epico na borda do disco), state.py (`new epic`, flags en, aliases pt com aviso de depreciação, help só en; saída do close cita `git add .swarm`), tests/test_iter26_modelo.py (8, novo). Testes existentes não precisaram de mudança.
- Régua (tech-lead, cópia): suíte harness OK (16 skips, igual à base) em python3 e /usr/bin/python3; oráculo iter26 42/51 nos 2 Pythons — os 9 restantes são de outras tasks (04: CA-04 textos, CA-09 orquestrador; 05: CA-07 ×3, CA-03 BUG antigo pós-upgrade; 08: CA-08 ×3). iter23 41 OK, iter25 21 OK (executor). Escopo por snapshot OK; privacidade 0; nenhum def removido (revisor contou).
- iter19: test_ca01_entidades_e_sessao_sao_json exige kind "epico" — conflito com CA-02; mudança oficial proposta ao founder (local/iter26-mo19/patch.diff; com ela iter19 OK nos 2 Pythons contra a cópia e o HEAD).
- Revisor: Claude Code · general-purpose · opus, instância isolada → APPROVED. MENOR: (1) heurística do show trata failing_test com espaço como passos (falso positivo possível em id parametrizado); (2) rejections de return_ grava by "gate". Decisão do tech-lead: normalizar kind "epico"→"epic" no upgrade fica para a task 05.
- Limite: motor segue com chaves pt em memória (traduzidas na borda); CAs medem o disco; renomear por dentro tocaria auto.py/painel (fora do escopo) — vai para a iter27, declarado no aceite.
- Ciclo 2 (QA reprovou: textos residuais com flags pt, D-44): executor Claude Code · general-purpose · opus; revisor opus isolado → APPROVED sem findings. Executor: doctests, emit, upgrade, harness completo (442 OK/16 skips), oráculos iter26 e iter13 OK nos 2 Pythons; escopo por snapshot só nos 6 arquivos do ciclo; privacidade 0. Arquivo desta task: tree.py (mensagens de recusa/DoR; :619 mantém "(antes --reproducao)" exigido por test_iter23_arvore)

### Handoff 03-TASK-CUSTO-NO-GUARD
- Executor: Claude Code · general-purpose · model sonnet (ciclo 1). Arquivos: scripts/harness/engine/guard.py (`_measure_usage` novo; usage gravado na delegação no evento delegation.measure_model; NOT_RUN/ERROR com motivo; falha da medição vira linha `usage_measure_failed` no ledger), scripts/harness/tests/test_iter26_custo.py (5 testes, novo).
- CA-06: TestCA06 4/4 OK em python3 e /usr/bin/python3 (rodado pelo tech-lead, CS_SKILL_DIR = cópia). Régua: test_iter26_custo, test_guards, test_iter24_guard, test_iter22_guard, test_faixas_aceite OK nos 2 Pythons. Escopo por snapshot: só guard.py e o teste (demais mudanças da cópia são da 02, em paralelo). Privacidade 0. RED não observado pelo executor; coberto pela base do oráculo (D de CA-06 falham no HEAD, 15/51).
- Revisor: Claude Code · general-purpose · opus, instância isolada → APPROVED. Ressalvas MENOR: (1) todo SubagentStop com delegação aberta agora faz um commit (usage sempre presente), sem efeito em bloqueio/roteamento; (2) dedup por message.id fica com o primeiro bloco — mesmo critério do custo.py do harness de dev (precedente), sem prova de streaming real; (3) transcript lido inteiro no hook (pré-filtro por "usage"), tempo não medido em arquivo grande.
- Limites: testes do harness rodam de dentro de scripts/harness/tests (import fixture). Portão completo fica para a QA.
- Ciclo 2 (QA reprovou: textos residuais com flags pt, D-44): executor Claude Code · general-purpose · opus; revisor opus isolado → APPROVED sem findings. Executor: doctests, emit, upgrade, harness completo (442 OK/16 skips), oráculos iter26 e iter13 OK nos 2 Pythons; escopo por snapshot só nos 6 arquivos do ciclo; privacidade 0. Arquivo desta task: guard.py (MIN_TASK_HINT --type FIX --avulsa)

### Handoff 04-TASK-TEXTOS-EN
- Executor: Claude Code · general-purpose · model sonnet (ciclo 1, retomado 2× — liberação D-42 e ajuste do cabeçalho do docs/06). Arquivos: assets/templates/{orchestrator,product-process}.md, assets/templates/state/{new-epic,new-story,new-task}.md, scripts/emit/{render,platforms}.py, scripts/harness/install.py (só MAKE_TARGETS), docs/06-referencia-cli.md (help regerado, cabeçalho "options:"), references/harness.md, scripts/emit/tests/test_iter26_textos.py (4, novo: varre textos emitidos e executa os exemplos com --dry-run). auto-plan.md intocado (só cs-auto).
- Régua (tech-lead): TestCA04+TestCA09 OK e suíte emit OK em python3 e /usr/bin/python3; escopo por snapshot OK; privacidade 0. iter15: 4 falhas iguais às do HEAD (D-35). iter23 test_ca07 exige `new epico` ⇒ mudança oficial 03 proposta ao founder (com o patch, iter23 OK nos 2 Pythons contra a cópia).
- Revisor: Claude Code · general-purpose · opus, instância isolada → APPROVED. MENOR: (1) references/ARCHITECTURE.md:355 ainda cita `new epico`/`--tipo` (fora do escopo; alias continua aceito) — candidato ao BACKLOG; (2) docs/06 com "optional arguments:" — corrigido.
- Ciclo 2 (QA reprovou: textos residuais com flags pt, D-44): executor Claude Code · general-purpose · opus; revisor opus isolado → APPROVED sem findings. Executor: doctests, emit, upgrade, harness completo (442 OK/16 skips), oráculos iter26 e iter13 OK nos 2 Pythons; escopo por snapshot só nos 6 arquivos do ciclo; privacidade 0. Arquivos desta task: MODO-DE-USO.md, references/ARCHITECTURE.md

### Handoff 05-TASK-VERSAO
- Executor: Claude Code · general-purpose · model sonnet (ciclo 1, retomado 1× para o ajuste do revisor). Arquivos: VERSION 0.14.0; README.md; references/migrations.json5 (version 0.14.0 + UMA entrada to 0.14.0 com harness + emit); docs/09-upgrade.md (Migração 0.14.0); docs/10-arvore-de-estado.md (kind epic, repro_steps); scripts/upgrade/tests/test_iter26_upgrade.py (3, versão relativa, novo).
- Régua (tech-lead): oráculo iter26 51/51 em python3 e /usr/bin/python3; scripts/upgrade/tests 40 OK/7 skips nos 2 Pythons (depois do ajuste); escopo por snapshot OK; privacidade 0. Executor: iter19..iter25 OK contra a cópia (python3), salvo iter23 test_ca07 (mudança oficial 03 pendente com o founder).
- Revisor: Claude Code · general-purpose · sonnet, instância isolada → CHANGES_REQUESTED por 1 MENOR de texto (close cita `git add .swarm`; `-A` só no orquestrador) — corrigido e conferido pelo tech-lead (grep + snapshot só nos 2 arquivos + suíte upgrade). MENOR PRÉ-EXISTENTE: MODO-DE-USO.md:148,163,199 cita `new epico`/`--tipo`/`--motivo` (fora do escopo) — candidato ao BACKLOG.
- Limite: a migração não normaliza `kind: "epico"` dos alvos antigos (leitura aceita os dois); não há ação de código para isso no catálogo.
- Ciclo 2 (QA reprovou: textos residuais com flags pt, D-44): executor Claude Code · general-purpose · opus; revisor opus isolado → APPROVED sem findings. Executor: doctests, emit, upgrade, harness completo (442 OK/16 skips), oráculos iter26 e iter13 OK nos 2 Pythons; escopo por snapshot só nos 6 arquivos do ciclo; privacidade 0. Arquivos desta task: docs/09-upgrade.md:142, docs/10-arvore-de-estado.md:10

### Handoff 06-TASK-QA
- QA: Claude Code · general-purpose · sonnet → ACCEPT (matriz CA-01..CA-09 51/51 nos 2 Pythons). Portão rodado pelo tech-lead com `caffeinate -i` (11:02, VERDE/FIM); D-35 iter10/iter15 0 regressões nos 2 Pythons; oracle verify intacto. Rodadas anteriores: QA 1 interrompida (textos pt, D-44); portão das 00:10 VERMELHO por 2 falhas instáveis em 3.9 (sono da máquina; reexecução 442 OK). Lição: portão longo roda sob o tech-lead, com caffeinate, nunca dentro de subagente.

### Handoff 07-TASK-REVIEW
- Revisor de feature: Claude Code · general-purpose · opus, instância isolada → APPROVED (CA-01..CA-09 PASS, RNF-01..03 PASS; 2 MENOR registrados no FEATURE.md).

### Handoff 08-TASK-VERIFY-HARNESS
- Executor: Claude Code · general-purpose · model sonnet (ciclo 1). Arquivos: scripts/harness/engine/cmds.py (`notebook_harness_write_ok`, chamada em `diff_check` antes de protected/allowed), scripts/harness/tests/test_iter26_verify_harness.py (4, novo).
- Regra: caderno `.claude/agent-memory/<a>/MEMORY.md` não é acusado só se `guard.notebook_text_problems` == [] (bloco = render do cs-mem); caderno de OUTRO agente exige também área livre igual à do HEAD (ausente ⇒ vazia); sem cs-mem/leitura ⇒ acusa (fail-closed).
- Régua (tech-lead): TestCA08 6/6 e test_iter26_verify_harness 4/4 em python3 e /usr/bin/python3. Executor: suíte harness 442 OK/16 skips; iter21 64 OK, iter24 22 OK nos 2 Pythons. iter25 TestCA05 falha contra a cópia por `emit validate` (templates da 04 em curso) — reconferir na QA. Privacidade 0; projeto vivo intacto.
- Revisor: Claude Code · general-purpose · opus, instância isolada → APPROVED. MENOR: (1) PRÉ-EXISTENTE — a fonte `.swarm/state/memory/agents/<a>.json5` não é conferida pelo verify (STATE_DIR ignorado), então lição alheia gravada na fonte gera bloco "válido" — candidato ao BACKLOG; (2) área livre do caderno do agente DA TASK passa a ser aceita (paridade com o guard; previsto no CA-08).

## Como a feature nasceu
### E0 — Pré-condição · CONCLUÍDA 2026-10-17T00:05:43-0300
- Demanda: "canonização do modelo de itens, limpeza de campos mortos e telemetria barata (sequência recomendada e escolhida pelo founder em 2026-10-17)"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-17T00:07:33-0300
- Produzido: problema enunciado; FEATURE-ID iter26
- Itens aprovados: 1: parar de gravar campos mortos e tolerar, sem migração; 2: inglês canônico na CLI/templates, pt como alias com aviso; 3: tokens medidos no guard junto do modelo, NOT_RUN sem transcript
- Aprovação: "ok"
- Sha: 4456b672c28121d8ca081fa155c6e0d416b236c5d199a76a8da6e98f6ea18ec2
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-17T00:08:29-0300
- Produzido: investigação F1-F9 (F9 descartado)
- Medido: 5 campos mortos; 103 chaves pt no motor da árvore; 12 linhas de flags pt emitidas; 4 pontos que sobrescrevem reject_reason; 1 except silencioso no guard
- Aprovação: "ok"
- Sha: 6ca3af1f9f27b61665feead67e93d8bbf63f5295cfcefb7e93c7fe363fc685b4
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-17T00:11:53-0300
- Produzido: FEATURE.md CA-01..CA-07; contrato PASS
- Aprovação: "ok"
- Sha: 75f98de3b4cae6ae202872082ee01412b7d541351667e73daf6651a8771b7d47
- Próxima: E4 — tasks

### E4 — REJEITADA 2026-10-17T00:15:58-0300 · motivo: founder incluiu B-49 e B-67 na iter26: CA-08 e CA-09 novos, task nova e FEATURE.md ajustado
- Sha rejeitado: 6f400bcb50570d546a40a0958c0c39cfb4be0b9d42ee71e8aa17c228af4d9b6c

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-17T00:17:48-0300
- Produzido: 8 tasks; CA-01..CA-09 cobertos (B-49 e B-67 incluídos pelo founder); FEATURE.md ajustado; contrato PASS
- Aprovação: "ok"
- Sha: cacce0f5fefc571c43d79cade515c9d1fb706a83cee9dab7182a6dbbd4bdbd52
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-17T00:18:05-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: b03b7b71c7aea6731a3770f74fba0f3f08bc49f9712a0deb76ad8304365c7578
- Próxima: oráculo por agente separado

### Abertura · 2026-10-17T00:18:05-0300
- Campanha: campanhas/iter26
- Tasks: 8 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)

## Campanha
- campanha: campanhas/iter26 · etapa do motor: concluida · rodada: 0
- critério de parada: Oráculo iter26 100% verde (CA-01..CA-09) em python3 e /usr/bin/python3; oráculos iter13, iter16, iter18..iter25 inteiros verdes; iter10/iter15 sem regressão contra o HEAD (D-35); suítes do produto e harness-dev verdes; 0 `def` removido; VERSION 0.14.0.
- escopo: scripts/harness/engine/cmds.py, scripts/harness/engine/state.py, scripts/harness/engine/tree.py, scripts/harness/engine/hcore.py, scripts/harness/engine/guard.py, scripts/harness/engine/views.py, scripts/harness/tests/*.py, scripts/emit/render.py, scripts/emit/platforms.py, scripts/emit/tests/test_iter26_*.py, assets/templates/product-process.md, assets/templates/orchestrator.md, assets/templates/state/*.md, docs/06-referencia-cli.md, docs/09-upgrade.md, docs/10-arvore-de-estado.md, references/harness.md, references/migrations.json5, scripts/upgrade/tests/test_iter26_*.py, VERSION, README.md

## Oráculo
- `campanhas/iter26/oraculo/ESPEC.md`
- `campanhas/iter26/oraculo/test_iter26.py`
- `campanhas/iter26/oraculo/medir.py`
- `campanhas/iter26/oraculo/base.txt`

## Decisões técnicas
- Tradução só na borda do disco: o motor segue com as chaves históricas pt em memória; os CAs medem o disco e renomear
  por dentro tocaria auto.py/painel (fora do escopo). A métrica "chaves pt no motor 103 → 0" NÃO foi atingida — iter27.
- Migrações item-status/state-format preservam o `kind` do arquivo; alvos antigos podem manter "epico" (leitura aceita
  os dois). A 0.14.0 não normaliza.
- Usage: soma por message.id distinto (primeiro bloco, mesmo critério do custo.py do harness de dev); falha vira linha
  `usage_measure_failed` no ledger; o commit da medição acontece também sem tier (para gravar NOT_RUN).
- Caderno no verify: aceito só se `notebook_text_problems` == []; caderno alheio exige área livre igual ao HEAD;
  sem cs-mem ⇒ acusa (fail-closed).
- Aliases pt: pt + en na mesma linha ⇒ en vence, pt descartado com aviso; help só en.
- Mudanças oficiais de oráculos antigos (todas ampliam o aceito: en passa, pt segue passando): iter19 (D-41), iter23
  (D-43), iter13 (D-44), iter10 (D-45). Escopo ampliado: install.py e new-epic.md (D-42), MODO-DE-USO.md e
  ARCHITECTURE.md (D-44).

## Aprendizados
- "Textos emitidos em inglês" atravessa muito mais arquivos do que a E2 mediu (12 linhas): faltaram install.py
  (MAKE_TARGETS), new-epic.md, mensagens de recusa do tree.py, a dica do guard, MODO-DE-USO.md, ARCHITECTURE.md e
  quatro oráculos antigos com literais pt. Custou 1 ciclo extra em 4 tasks e 4 mudanças oficiais. Na próxima troca de
  vocabulário: grep do universo inteiro (produto + oráculos + doctests) na E2, não só templates.
- O doctest que confere todo comando citado contra o help real pegou o que os oráculos não pegavam — vale rodá-lo na
  régua seletiva de toda task de texto.
- Portão longo não pode rodar dentro de subagente: o agente ficou fazendo polling, o processo morreu com ele e o Mac
  dormiu (4 h de relógio para ~50 min de teste); uma rodada saiu VERMELHA por 2 falhas instáveis do harness em 3.9.
  Regra: o tech-lead roda o portão com `caffeinate -i`; o QA só lê o resultado.
- Paralelo 02 ∥ 03 e 04 ∥ 08 na mesma cópia funcionou com arquivos disjuntos; o snapshot precisa ser filtrado pela task
  na conferência de escopo.
- Pendências para o BACKLOG: medição de usage e de tier no mesmo try (falha inesperada perde o tier); fonte da memória
  do agente não conferida pelo verify (pré-existente); ROADMAP e docs/09:300 citam pt; testes do harness sensíveis a
  sono em 3.9; heurística do show de BUG antigo; `return_` grava by "gate".

## Arquivos da feature
- `scripts/harness/engine/cmds.py`
- `scripts/harness/engine/state.py`
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/hcore.py`
- `scripts/harness/engine/views.py`
- `scripts/harness/tests/test_iter26_modelo.py`
- `scripts/harness/tests/test_workflow_e2e.py`
- `scripts/harness/tests/test_machines.py`
- `scripts/harness/tests/test_d102_d103_extra.py`
- `scripts/harness/tests/fixture.py`
- `scripts/harness/tests/test_trabalho_na_arvore.py`
- `scripts/harness/tests/test_faixas_aceite.py`
- `scripts/harness/tests/test_iter21_motor.py`
- `scripts/harness/tests/m5_cenarios.py`
- `scripts/harness/tests/test_swarm_dir.py`
- `scripts/harness/tests/test_legacy_hierarquia.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/tests/test_iter26_custo.py`
- `assets/templates/product-process.md`
- `assets/templates/orchestrator.md`
- `assets/templates/state/new-story.md`
- `assets/templates/state/new-task.md`
- `assets/templates/state/auto-plan.md`
- `assets/templates/state/new-epic.md`
- `scripts/harness/install.py`
- `MODO-DE-USO.md`
- `references/ARCHITECTURE.md`
- `scripts/emit/render.py`
- `scripts/emit/platforms.py`
- `scripts/emit/tests/test_iter26_textos.py`
- `docs/06-referencia-cli.md`
- `references/harness.md`
- `VERSION`
- `README.md`
- `references/migrations.json5`
- `docs/09-upgrade.md`
- `docs/10-arvore-de-estado.md`
- `scripts/upgrade/tests/test_iter26_upgrade.py`
- `scripts/harness/tests/test_iter26_verify_harness.py`

## Aceite da Feature
### Aceite QA — ACCEPT
### Aceite Review — APPROVED
<!-- fechar-feature:archive-completo -->
