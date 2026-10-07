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

`scripts/upgrade/tests/test_upgrade.py` cobre UPGRADE-1..6 contra uma **cópia** (mktemp) do alvo real legado da
iteração 4 (`campanhas/iteration-4/ts-shop-setup-vague/with_skill/target`; outro caminho via
`$CS_UPGRADE_LEGACY_TARGET`). Versões futuras são simuladas com `$CS_SKILL_VERSION_FILE` e `$CS_MIGRATIONS_FILE`.

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

## Migração 0.8.0: modo autônomo

A entrada `to: "0.8.0"` do catálogo declara só `harness` e `emit`. O `harness` reinstala motor, guards e wrappers
(passa a incluir o `cs-auto` e o hook PreCompact, que pausa um mandato em andamento) e o `emit` reemite os artefatos,
incluindo as 9 skills `/auto-*`. Nada de entrevista, roster, cartões, memória ou board é refeito; sem mandato
aberto o PreCompact não faz nada. Veja [11-modo-autonomo.md](11-modo-autonomo.md).

## Migração 0.9.0: skills com nome em inglês

A entrada `to: "0.9.0"` do catálogo declara `harness` e `emit`. As skills geradas passam a ter nome em inglês
(verbo-objeto), em todas as plataformas onde já saíam:

| 0.8.x | 0.9.0 |
|---|---|
| `/salvar-sessao` | `/save-session` |
| `/carregar-sessao` | `/load-session` |
| `/corrigir` | `/correct` |
| `/planejar-sprint` | `/plan-sprint` |
| `/new-epico` | `/new-epic` |
| `/close-epico` | `/close-epic` |

Só o nome muda: política (`disable-model-invocation`, "só o humano executa" no Codex), `argument-hint`,
`allowed-tools` e os comandos `.swarm/bin/cs-*` citados ficam iguais. Os subcomandos do motor também ficam
(`cs-state new epico`, `cs-mem correct`).

O `emit` da migração gera as pastas novas e poda as antigas pelo manifesto (`.swarm/emit/manifest.json5`): sai só a
`SKILL.md` que o emit gerou e que ainda tem o marcador `codebase-specialists:generated`; a pasta sai quando fica vazia.
Arquivo humano dentro da pasta antiga fica (com a pasta). Pasta de mesmo nome fora do manifesto (do usuário) nunca é
tocada. O plano (`cs.py upgrade`, sem `--apply`) lista cada `delete` e cada `create` e não escreve nada. Depois do
`--apply`, `emit validate` sai verde, sem órfão.

## Migração 0.10.0: correções de uso real (segunda cobaia .NET)

A entrada `to: "0.10.0"` do catálogo declara `harness` e `emit`: reinstala o motor e reemite os artefatos, sem
refazer entrevista, roster, cartões, memória nem board. O que muda no repositório gerado:

| Onde | 0.9.x | 0.10.0 |
|---|---|---|
| `verify` / `accept` | o hash da árvore (`tree_sha256`) incluía artefato ignorado pelo git (`bin/`, `obj/`): a build de outra task travava o accept | arquivo ignorado pelo git fica fora do hash; rastreado ou não-rastreado-não-ignorado continua contando |
| VERIFIED/REVIEWED com a árvore mudada | impasse: `reverify` só saía de REJECTED/ESCALATED | `cs-state reverify --task <id>` (recusado com a árvore intacta); reviews valem se `files_changed` não mudou; se mudou, nova review |
| DoR / despacho | `allowed_paths` igual ao território inteiro do agente passava | recusado no check/start (também glob que contém o território), com a dica `cs-state amend <id> --field allowed_paths --after '["arquivo"]' --reason …`, que funciona também em item da árvore ainda não iniciado |
| pre-commit (`guard.py check-diff --staged`) | commit dos `allowed_paths` com a delegação em DISPATCHED/RETURNED/VERIFIED/REVIEWED passava | barrado até o `accept`; ACCEPTED com a task aberta continua liberado; task fechada continua barrando |
| guard de Bash | `git check-ignore`, `git ls-remote`, `git count-objects` contavam como escrita | contam como leitura |
| cartão do gate | dizia o enum do veredito, sem o comando | manda registrar com `cs-state review --task <id> --by <gate> --verdict … --findings …`; só leitura = não editar arquivos (os comandos de estado do gate são dele) |
| orquestrador (passo 5) | — | nunca dita o veredito ao gate; sem registro, redespacha revisão independente com o mesmo id `.dN`; não pede ao usuário para carimbar |

O pre-commit novo muda o ritmo: commite os `allowed_paths` depois do `cs-state accept` e antes do `close` (o
passo 6 do orquestrador já pedia isso).

## Migração 0.10.1: o pre-commit aceita o resultado da própria ferramenta

A entrada `to: "0.10.1"` do catálogo declara `harness` e `emit`. Um alvo em 0.9.0 vai direto: o plano lista as
migrações 0.10.0 e 0.10.1, e o `--apply` aplica as duas em sequência (cada ação roda uma vez) e registra
`migrations: ["0.10.0", "0.10.1"]` no `upgrade_history`.

Antes, o pre-commit do alvo (`.swarm/bin/cs-precommit` → `guard.py check-diff --staged`) barrava o resultado do
próprio `upgrade --apply`, do `emit` avulso e do `harness install` avulso: o motor fica em `.swarm/harness/` (área
protegida) e os emitidos (`.claude/agents/`, `.claude/orchestrator.md`, `CLAUDE.md`…) ficam fora de qualquer
`allowed_paths`. O commit do upgrade só passava com `--no-verify`. **Agora o commit do upgrade não precisa mais de
`--no-verify`**: `git add` do que mudou e `git commit`.

| Onde | 0.10.0 | 0.10.1 |
|---|---|---|
| `harness install` / `emit` | escreviam sem registro | gravam um **atestado**: sha256 de cada arquivo que deixaram no alvo (remoção = `null`) |
| pre-commit (`check-diff`) | barrava motor e emitidos | libera o arquivo atestado enquanto o conteúdo staged tiver o sha atestado; edição à mão depois disso barra |
| remoção à mão de arquivo do motor | o git via "renomeação" para dentro de `.swarm/backups/upgrade-*` e só o nome novo era conferido: passava | `--no-renames`: a remoção aparece com o próprio nome e barra |
| `emit` num alvo com motor anterior ao atestado | — | reinstala o harness antes de emitir (o pre-commit antigo não lê o atestado) |
| `__pycache__` do motor | entrava no `git add -A` e o pre-commit barrava | `.swarm/harness/.gitignore` (gerado pelo install) |

O atestado:

- mora em `<git-dir>/codebase-specialists/atestado.json`, fora da árvore versionada: nunca entra num commit nem vai
  para outro clone. `.git/` é área protegida do guard (Write/Edit/Bash do modelo bloqueados, como o motor);
- é ancorado no harness-ledger (cadeia de hashes): cada gravação anexa `{kind: "attest", sha256}`. O check-diff só
  confia no atestado cujo sha256 é o do último `attest` de um ledger íntegro. Atestado editado à mão fica ignorado e
  o commit barra, citando o motivo;
- guarda só a última escrita da ferramenta por caminho, e cada gravação descarta o que o HEAD já tem (consumido no
  commit). Um 2º commit com o arquivo mudado à mão barra; `upgrade --apply` sem migração pendente não escreve nada e
  não abençoa a edição;
- só libera caminhos que a ferramenta gera (`.swarm/`, `.claude/`, `.cursor/`, `.codex/`, `.agents/`,
  `.github/agents|instructions|skills/`, `CLAUDE.md`, `AGENTS.md`, `Makefile`, `specialists.mk`), nunca estado do
  motor. Estado (`.swarm/state/`, zonas, eventos, ledgers, memória) continua passando pelo `validate`;
- arquivo mesclado (bloco gerenciado, `settings.json`, `Makefile`) só é atestado se, antes da escrita, era igual ao
  HEAD: edição humana ainda não commitada nesse arquivo não é abençoada pela ferramenta.

Arquivo que a ferramenta não escreveu (fonte, skill do usuário em `.claude/skills/`, arquivo novo em
`.swarm/harness/`) continua barrado, junto ou não do resultado do upgrade.
