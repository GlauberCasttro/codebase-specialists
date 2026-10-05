# 09 — `upgrade`: versão da skill e migrações

Um repositório que já tem time gerado recebe uma versão nova da skill **sem refazer o conhecimento**: o
`upgrade` atualiza o *mecanismo* (motor do harness, guards, artefatos emitidos, camadas de fatos pedidas) e
nunca reabre entrevista, roster aprovado, cartões aprovados, memória/lições nem board/eventos — salvo migração
explícita.

## Peças

| Peça | Onde | O que é |
|---|---|---|
| `VERSION` | raiz da skill | semver da skill (começou em `0.5.0`; hoje `0.7.0`) |
| `references/migrations.json5` | skill | catálogo `{version, migrations: [{to, why, actions: [{kind, ...}]}]}` |
| `skill_version`, `upgrade_history[]` | `<alvo>/.swarm/run.json5` | versão em que o alvo está e o histórico de upgrades |
| `scripts/upgrade/` | skill | `cs.py upgrade` (plano/aplicação) e a leitura de VERSION/catálogo |

`cs.py init` grava `skill_version` (= VERSION) e `upgrade_history: []` ao **criar** o `run.json5` (também com
`--force`). O merge do `init` num `run.json5` já existente **não** grava a versão: um alvo sem `skill_version`
continua legado, e quem cuida dele é o `upgrade`.

## Alvo legado

Alvo gerado antes do versionamento (sem `skill_version` no `run.json5`) é tratado como `0.0.0-legado`: o upgrade
aplica todas as migrações desde a primeira e o plano diz "partindo de repositório legado". A primeira entrada do
catálogo (`to: "0.5.0"`) documenta o estado atual: reinstala o harness e reemite os artefatos.

## Migração 0.6.0: pasta legada `.specialists/` → `.swarm/`

A entrada `to: "0.6.0"` do catálogo traz `{kind: "rename-dir", from: ".specialists", to: ".swarm"}`. Num alvo
legado, o plano cita `rename-dir` e `.swarm/` (os `--dry-run` de harness/emit rodam numa simulação já renomeada);
o `--apply` faz o backup (nasce em `backups/` da pasta legada e o rename-dir o leva para `.swarm/backups/`), move a pasta e grava em `.swarm/run.json5`
`skill_version: "0.6.0"` e `upgrade_history[-1].actions` com `rename-dir`. Um segundo `upgrade` diz
`nada a fazer`. O `init` num alvo legado recusa (exit 3) e aponta este caminho: é o mesmo harness, não um
harness estranho (esse é o caso de `cs.py init --replace-harness`, ver `02-harness.md`).

## Uso

```
python3 scripts/cs.py --target <repo> upgrade                          # PLANO: não escreve nada
python3 scripts/cs.py --target <repo> upgrade --apply --allow-outside  # aplica
```

Pela skill: `/codebase-specialists upgrade` mostra o plano e pede OK antes do `--apply`.

**Plano** (sem flags): versão do alvo × da skill, migrações no intervalo `(alvo, skill]`, ações consolidadas,
o que muda dentro de `.swarm/` (dos `--dry-run` do `harness install` e do `emit`), o que fica **fora**
de `.swarm/` (exige `--allow-outside`), o que é preservado, onde fica o backup e o comando seguinte.

**`--apply`**:
1. recusa sem escrever nada (exit 3) se há escrita fora de `.swarm/` sem `--allow-outside`, ou se o
   `emit --dry-run` acusa conflito com conteúdo humano;
2. backup em `.swarm/backups/upgrade-<de>-<para>/`: cópia de `.swarm/` (menos `backups/`) e das raízes
   fora que o harness/emit gerenciam (`.claude/`, `.cursor/`, `.codex/`, `.github/`, `AGENTS.md`, `CLAUDE.md`,
   `Makefile`, `specialists.mk`, `.git/hooks/pre-commit`, e todo caminho do manifesto do emit), com
   `manifest.json5` dizendo o que existia antes;
3. roda as ações (cada uma uma vez) chamando os comandos existentes da skill;
4. verifica: `cs.py harness selftest`, `cs.py harness validate --strict --allow-empty`, `cs.py emit validate` e,
   sem migração explícita (`schema|cards|probes`), que entrevista, aprovações, `cards/status.json5`, board,
   eventos e memória ficaram byte a byte iguais;
5. falhou qualquer passo → restaura o backup (inclusive remove o que não existia antes) e sai com **exit 1**;
   sucesso → grava `skill_version` e uma entrada em `upgrade_history` (`from`, `to`, `at`, `legacy`, `migrations`,
   `actions`, `backup`, `reexam_required`) e um evento `upgrade` no ledger.

Exit: 0 ok (ou nada a fazer) · 1 falhou e restaurou · 2 entrada inválida (catálogo, alvo mais novo que a skill,
ação reservada) · 3 recusado sem escrever.

## Ações (`kind`)

Ordem canônica de execução: `rename-dir → schema → scan → facts-refresh → harness → emit → cards → probes`.

| kind | Parâmetros | Chama |
|---|---|---|
| `harness` | — | `cs.py harness install` com as plataformas advisory do run (`cursor,copilot,codex`), `--git-hook` se o pre-commit já está ligado |
| `emit` | — | `cs.py emit` (plataformas do run) |
| `scan` | `layers: ["L2", ...]`, `no_exec?` | `cs.py scan --layers ...` (só essas camadas; as outras ficam byte a byte) |
| `facts-refresh` | `layers?` (default todas) | `cs.py facts check --layers ...`; se velho, `cs.py scan --layers ...` |
| `schema` | `script` (relativo à skill) | `python3 <script> --target <alvo>` — conversor **idempotente** de team.json5/board |
| `cards` / `probes` | `argv?` (args do cs.py) | só quando a migração exige; **sempre** avisam que haverá reexame |
| `rename-dir` | `from: ".specialists"`, `to: ".swarm"` (únicos aceitos) | move a pasta legada desta skill para `.swarm/` (sem mesclar), reescreve os caminhos do mecanismo (hooks, settings, `Makefile`, `specialists.mk`, emitidos, `.git/hooks`, `.swarm/bin`, `.swarm/harness`); dados e ledgers vão intactos. Outra pasta → exit 2; legado junto de um `.swarm/` de outro harness → exit 3 |

Várias migrações no intervalo são consolidadas: `harness`/`emit` rodam uma vez; `scan`/`facts-refresh` unem as
camadas; `schema`/`cards`/`probes` rodam uma vez por entrada distinta.

## Regra de manutenção

Toda mudança na skill que afete repositórios já gerados sobe `VERSION` e ganha uma entrada em
`references/migrations.json5` com `to` = nova versão (e `version` do catálogo = VERSION).
`scripts/doctests/tests/test_version_migrations.py` reprova VERSION sem migração correspondente, `to` fora de
ordem e ações fora do schema.

## Testes

`scripts/upgrade/tests/test_upgrade.py` cobre UPGRADE-1..6 contra uma **cópia** (mktemp) de um alvo legado real
(gerado por uma versão anterior da skill), apontado por `$CS_UPGRADE_LEGACY_TARGET`; sem a variável, os cenários
que precisam dele são pulados. Versões futuras são simuladas com `$CS_SKILL_VERSION_FILE` e `$CS_MIGRATIONS_FILE`.

| Cenário | Prova |
|---|---|
| UPGRADE-1 | alvo na versão anterior → `--apply`: entrevista, roster (`team approved`), cartões, estágios intactos; histórico só com o intervalo |
| UPGRADE-2 | board, `events.jsonl` (cadeia de hash válida) e memória byte a byte iguais |
| UPGRADE-3 | plano sem `--apply` não muda nenhum byte da árvore (inclusive `.git`); `--apply` sem `--allow-outside` também não |
| UPGRADE-4 | migração que quebra artefato emitido → verificação falha, exit 1, árvore idêntica à de antes (fora `backups/`) |
| UPGRADE-5 | `scan layers: [L2]` regrava só `architecture.json5`; demais fatos com o mesmo hash, índice com o mesmo conteúdo |
| UPGRADE-6 | alvo legado → `--apply` sem reabrir entrevista nem roster; `upgrade_history[0].legacy = true` |

## Migração 0.7.0: estado em árvore (`state-tree`)

A entrada `to: "0.7.0"` do catálogo declara `harness`, `state-tree` e `emit`. A ordem do `upgrade` é
`rename-dir → schema → scan → facts-refresh → harness → state-tree → emit → cards → probes`. O `state-tree` chama
`cs-state migrate state-tree`: o board plano legado vira a árvore `backlog/ state/ archive/`, `events.jsonl` é
preservado e só cresce, o `board.json5` antigo fica em backup, cada item migrado guarda `legacy_id` e uma segunda
execução não muda nada.

Correções do mesmo upgrade: **U-1** (alvo pausado antes de `validate.5`): o selftest não exige o pre-commit que
ainda não foi instalado, nada é restaurado e `current_stage` e o status das etapas ficam iguais ao legado;
**U-2** (backup): `.git` aninhado e `tmp/` ficam fora do backup, listados em `excluded` no `manifest.json5`, e o
backup do `pre-commit` é guardado sob outro nome, de modo que `cs.py sanitize --check` passa depois.
