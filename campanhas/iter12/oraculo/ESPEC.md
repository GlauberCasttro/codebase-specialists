# ESPEC — campanha-iter12: `cs.py upgrade` em uso real (repositório-piloto (projeto-legado) legado)

Skill sob teste: 0.7.0 (commit 3127bf9), cópia limpa em `scratchpad/cs-070/codebase-specialists`.
Alvo: cópia do repositório-piloto (projeto-legado) (legado `.specialists/`, `current_stage: finished`, board plano com 2 épicos,
2 features, 6 stories — US-3 IN_PROGRESS, US-2 IN_REVIEW — e 5 tasks: TASK-01-001-DOC ACCEPTED,
TASK-02-001-AGT BLOCKED, TASK-02-002-KEY BLOCKED, TASK-02-003-OPS REJECTED, TASK-02-004-QA READY; 80 eventos).
Oráculo: `test_upgrade_real.py` (16 testes; copia o repositório-piloto para tmp a cada classe; nunca escreve na fonte).
Linhas citadas: `scripts/...` da skill 0.7.0.

## Diagnóstico

### D1 — causa raiz da falha do `emit validate` (U-5)
Reproduzido à mão na cópia, etapa por etapa (`core._run_action` de cada ação e depois `emit validate`):

| passo | resultado |
|---|---|
| rename-dir, harness install, state-tree (10 itens), emit | ok |
| `cs.py emit validate` logo depois do emit | **exit 0** — `G7 ok: 67 artefatos válidos` |
| passada de resíduo `rewrite_legacy_refs(target)` (`upgrade/core.py:844-848`) | reescreve `.claude/rules/cs-dev-consensus.md` e `.claude/rules/cs-dev-self-improve.md` |
| `cs.py emit validate` de novo | **exit 1** — `G7 FALHOU (2 erro(s))`: os dois arquivos "desatualizado ou editado à mão" |

Cadeia:
1. O **dado preservado** `team.json5` do repositório-piloto cita o caminho legado no texto das regras dos cartões:
   `.specialists/team.json5:86` (regra de dev-consensus: "`.specialists/bin/cs-mem search ...`") e `:174`
   (`check: ".specialists/bin/cs-mem search '<nome perguntado>' ..."`, dev-self-improve). O rename-dir move a
   pasta mas não reescreve dados (`upgrade/core.py:46-48`, `RENAME_INSIDE = ("bin","harness")`).
2. `cs.py emit` renderiza esse texto verbatim nos emitidos e grava o conteúdo/hash no manifesto.
3. Depois de TODAS as ações, a passada de resíduo do rename-dir (`upgrade/core.py:844-850`) roda
   `rewrite_legacy_refs`, cujo conjunto de alvos inclui os arquivos do manifesto do emit
   (`upgrade/core.py:150`, `_emit_manifest_paths`) → troca `.specialists` por `.swarm` em arquivos que o emit acabou
   de gerar.
4. `emit validate` compara o texto em disco com o que renderiza de `team.json5` (`emit/validate.py:359-360`,
   `text != art.content`) → G7 reprova → verify falha (`upgrade/core.py:808-809`) → restaura → exit 1.

Efeito colateral mesmo se o G7 fosse ignorado: os emitidos mandariam o agente rodar `.specialists/bin/cs-mem`,
que deixa de existir depois do rename (o binário vai para `.swarm/bin/cs-mem`).
A mensagem antiga "team.json5 ausente: .swarm/team.json5" não é a causa: é `emit validate` rodado à mão no alvo
AINDA legado (o emit só conhece `.swarm/`).

### D2 — motivo invisível (U-3)
- `verify` monta o motivo e o devolve (`upgrade/core.py:808-809`), mas `apply` só o escreve em **stderr**
  (`upgrade/core.py:863-866`). O stdout — onde está o progresso — termina em
  `cs.py harness validate --strict --allow-empty: ok` e cala: quem lê só o progresso vê exit 1 sem motivo.
- O motivo é cortado por `_tail(n=8)` (`upgrade/core.py:254-256`): só as 8 últimas linhas não vazias de
  `out + err`. Um validador que lista a linha do erro e depois gates ok perde exatamente a linha do motivo
  (o teste U-3 induz isso: linha do motivo no topo + 20 linhas de ruído → motivo some).

### D3 — resíduo `.swarm/state/selftest.json5` que bloqueia o próximo upgrade (U-4)
- O rollback do próprio upgrade NÃO deixa resíduo (reproduzido: depois de `upgrade FALHOU`, `.swarm/` não
  existe na cópia; `restore_backup` renomeia `.swarm` de volta, `upgrade/core.py:646-652`). O teste
  `test_falha_restaurada_nao_deixa_swarm` passa hoje e fica como guarda de regressão.
- A origem do resíduo é rodar a verificação à mão no alvo legado: `cs.py harness selftest` (e
  `cs.py harness validate`) num alvo ainda em `.specialists/` gravam o resultado em
  `hcore.state_paths(root)["selftest"]` = `<alvo>/.swarm/state/selftest.json5` (`harness/engine/selftest.py:290`,
  `harness/engine/hcore.py:149-159`) sem conferir se o harness `.swarm/` existe — criam `.swarm/state/` do nada e
  saem 1 com stderr vazio. Reproduzido na cópia limpa: após `harness selftest`, `find .swarm` →
  `.swarm/state/selftest.json5`. (O arquivo no repositório-piloto real tem mtime 17:21:38, a hora da rodada real.)
- Esse resíduo próprio da skill faz `rename_conflict` recusar o próximo upgrade
  (`upgrade/core.py:125-126`: "`.swarm/` já existe com conteúdo junto do legado") → plano com BLOQUEIO, apply exit 3.

### D4 — observação (não bloqueia; coberto por teste de preservação)
A migração state-tree põe a story IN_PROGRESS (US-3) e a IN_REVIEW (US-2) em `backlog/` e o INDEX.md mostra
"Em execução: nenhum"; o status das tasks legadas só sobrevive na projeção do motor
(`.swarm/.engine/projection.json5`) e como `legacy_tasks` no item da árvore (`harness/engine/tree.py:1371-1378`).
O oráculo exige que esse estado não se perca (projeção + legacy_tasks), não que a árvore o mova para `state/`.

## Requisitos

**U-3 — motivo visível.** Quando uma verificação do `--apply` falha:
- R3.1 o fluxo de progresso (stdout / `out`), depois de `verificando:`, nomeia o comando que falhou como falha
  (ex.: `cs.py emit validate: FALHOU (exit 1)`);
- R3.2 o mesmo fluxo traz a saída do comando (as linhas de erro);
- R3.3 a linha que explica a falha não é cortada por truncamento (stdout+stderr a contêm, mesmo com ≥20 linhas
  de ruído depois dela);
- R3.4 continua exit 1 e backup restaurado.

**U-4 — rollback completo / sem resíduo próprio.**
- R4.1 falha na verificação de alvo legado → depois da restauração `.swarm/` não existe, o legado volta byte a
  byte (entrevista, aprovações, cartões, memória, board, eventos) e o plano seguinte não acusa BLOQUEIO;
- R4.2 comando da skill num alvo ainda legado (`cs.py harness selftest`) não cria `.swarm/`: opera no legado ou
  recusa com motivo apontando `cs.py upgrade`;
- R4.3 resíduo próprio da skill (`.swarm/` contendo só `state/selftest.json5`) junto do legado não bloqueia o
  plano nem faz o `--apply --allow-outside` sair 3 (conteúdo humano/de outro harness em `.swarm/` continua
  recusado — não afrouxar `rename_conflict` para conteúdo arbitrário).

**U-5 — causa raiz: o upgrade do repositório-piloto conclui.** `cs.py upgrade --apply --allow-outside` na cópia:
- R5.1 exit 0, com `cs.py emit validate: ok` no progresso, e `cs.py emit validate` verde depois;
- R5.2 nenhum arquivo do manifesto do emit cita `.specialists/` (o comando citado existe em `.swarm/bin/cs-mem`) —
  isto é: o texto legado de `team.json5` vira `.swarm/` ANTES do emit (ou o emit traduz), e a passada de resíduo
  não reescreve emitido depois do emit (ou o emit roda de novo depois dela). Só pular a passada de resíduo nos
  emitidos NÃO basta (deixa comando quebrado nos emitidos);
- R5.3 `.specialists/` não existe mais; `.git/hooks/pre-commit` resolve para dentro de `.swarm/`;
- R5.4 `run.json5`: `skill_version` = VERSION e último `upgrade_history.to` = VERSION;
- R5.5 byte a byte iguais ao legado: `interview.jsonl`, `team-approvals.jsonl`, `approvals.jsonl`,
  `cards/status.json5`, `memory/**`;
- R5.6 `events.jsonl` legado é prefixo da cadeia nova (que cresce), e `harness validate --strict --allow-empty` verde;
- R5.7 todo épico/feature/story legado tem item na árvore (`legacy_id`) e cada task legada aparece em
  `legacy_tasks` da sua story (AGT/KEY/OPS/QA de US-3);
- R5.8 a projeção do motor mantém o status de cada task e o estado de cada story do board legado.

Nota: se a correção de R5.2 reescrever `team.json5`, isso é migração explícita (rename-dir já está em
`EXPLICIT_KINDS`) — `team.json5` não está em `PRESERVED_PATHS`; R5.5 não muda.

## Sanidade do oráculo
Com uma correção hipotética mínima numa cópia descartável da skill (reescrever o caminho legado em `team.json5`
logo depois do `os.rename` do rename-dir, `upgrade/core.py:207`), os 9 testes de U-5 passam (19s). U-3 e U-4
(R4.2/R4.3) dependem das correções próprias descritas acima.

## Rodar
```
cd campanha-iter12/oraculo
CS_SKILL=<skill> python3 -m unittest -v test_upgrade_real      # PILOTO_SRC=<cópia legada> opcional
```
`setUpModule` falha alto se `PILOTO_SRC` não for mais legado (`.specialists/run.json5` ausente): nesse caso
aponte `PILOTO_SRC` para uma cópia ainda legada (não foi possível congelar um snapshot do repo real no workspace).
