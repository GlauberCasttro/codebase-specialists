# ESPEC — oráculo SWARM-DIR (campanha-iter9)

Fonte: `codebase-specialists/docs/ROADMAP-proxima-rodada.md` §"P1 da rodada 1 — renomear a pasta gerada de
`.specialists/` para `.swarm/`" (SWARM-DIR-1..4) e `docs/PONTOS-DO-FOUNDER.md` C4 ("um harness não pode existir
junto com o outro"; substituir só com `--replace-harness`, com backup).
Arquivo de teste: `test_swarm_dir.py` (unittest puro, Python 3.9+; 31 testes, ~30 s). **Contrato: o corretor não o
edita.** Insumos (só leitura): a skill (`$CS_SKILL_DIR`, padrão `~/.claude/skills/codebase-specialists`), o
repo v8 (`$CS_V8_REPO_SRC`, copiado com `git archive HEAD` para um mktemp) e o alvo legado da iteração 4
(`$CS_UPGRADE_LEGACY_TARGET`, o mesmo que `scripts/upgrade/tests/test_upgrade.py` usa). Os subprocessos rodam com
`PYTHONDONTWRITEBYTECODE=1`.

## Interfaces FIXADAS por este oráculo

| Item | Valor fixado |
|---|---|
| Constante | `cslib.paths.STATE_DIR = ".swarm"`; `cslib.paths.LEGACY_STATE_DIR = ".specialists"` |
| Espelho no motor (copiado ao alvo, não importa cslib) | `hcore.STATE_DIR = ".swarm"`; `hcore.state_paths(r)["state_dir"] == r/.swarm/state` |
| Funções de caminho | `paths.state_dir(t) == t/.swarm/state`, `paths.facts_dir(t) == t/.swarm/facts`; `is_self(".swarm/…")` verdadeiro; o legado continua em `is_reserved` (o scan não o analisa) e NÃO é `is_self` |
| Layout no alvo | `.swarm/run.json5`, `.swarm/state/board.json5`, `.swarm/harness/guard.py`, `.swarm/bin/cs-{state,mem,session,route,precommit}`, `.swarm/facts/`; `specialists.mk` com `CS_BIN = .swarm/bin`; `.git/hooks/pre-commit` → `…/.swarm/bin/cs-precommit` |
| Detecção de outro harness | **`cs.py init` e `cs.py harness install`** detectam, cada sinal sozinho: `.swarm/instance.json` (v8), `scripts/harness/`, `.claude/kernel/`, hook em `.claude/settings.json` cujo comando não é `cs-guard.sh`, e o diretório legado `.specialists/` |
| Recusa | exit **3** ("recusado sem escrever", a mesma convenção de `harness install`/`upgrade`), árvore idêntica byte a byte (fora de `.git`, mais `.git/hooks` e `.git/config`) |
| Mensagem da recusa (harness estranho) | contém `plano de substituição` e `--replace-harness`; no repo v8, cita ainda `.swarm/instance.json`, `scripts/harness`, `.claude/kernel`, `.claude/settings.json` e o destino do backup `.swarm/backups/harness-anterior` (o `harness install` só precisa citar `--replace-harness`) |
| Mensagem da recusa (legado desta skill) | contém `upgrade` (é o mesmo harness: migra, não substitui) |
| Não é harness (falso positivo proibido) | `settings.json` só com `permissions`/`env`; o próprio harness da skill em `.swarm/` (reinit/reinstall = exit 0, idempotente); o backup em `.swarm/backups/harness-anterior/` |
| Substituição | `cs.py init --platforms claude-code --replace-harness --allow-outside` → exit 0. Depois, o oráculo roda `cs.py harness install --allow-outside` (exit 0; pode não mudar nada se o init já instalou) |
| Backup | `<alvo>/.swarm/backups/harness-anterior/<caminho relativo original>`; cópia fiel (sha256) de TODO arquivo do v8 em `.swarm/**`, `scripts/harness/**`, `.claude/hooks/**`, `.claude/kernel/**`, `.claude/settings.json` e `lefthook.yml`. Arquivos extras (manifesto etc.) são livres |
| Fatos importados | em `.swarm/facts/*.json5` (forma de lista ou `{facts: [...]}`) e listados no `.swarm/facts/index.json5`; para cada BIZ-n do `DOMAIN_INVARIANTS.yaml`: id contendo `biz-n` (sem diferenciar maiúsculas) **ou** claim com o texto do invariante; o claim traz o texto (60 primeiros caracteres); `origin` não vazio; `evidence[].file` terminando em `DOMAIN_INVARIANTS.yaml` e EXISTENTE no alvo (é a cópia no backup) |
| Sonda de harness único | `cs.py harness selftest` imprime uma linha `OK …`/`FALHA …` cujo nome casa `harness[ _-]?[uú]nico` (sem diferenciar maiúsculas). Com resíduo → `FALHA` e exit 1; limpo → `OK` |
| Upgrade rename | `references/migrations.json5` ganha uma migração com `{kind: "rename-dir"}`; o plano (`cs.py upgrade`) cita `rename-dir` e `.swarm/`; `--apply` grava em `.swarm/run.json5` `skill_version` = VERSION e `upgrade_history[-1].actions` contendo `"rename-dir"`; um segundo `upgrade` diz `nada a fazer` |
| Conflito no upgrade | legado + `.swarm/instance.json` estranho → `upgrade --apply --allow-outside` sai com **3** sem escrever nada |

## Requisito → testes

| Requisito | Testes (classe.método) | Negativos incluídos |
|---|---|---|
| **Constante única** | `TestConstanteUnica.test_constante_em_cslib_paths`, `.test_motor_espelha_a_constante`, `.test_nome_legado_so_na_allowlist_codigo_e_templates`, `.test_nome_legado_fora_de_docs_de_entrada_e_corretor`, `.test_templates_e_install_apontam_para_swarm` | o legado deixa de ser `is_self`; teto de ocorrências nos arquivos da allowlist; "apagar em vez de renomear" (os templates precisam citar `.swarm/harness/guard.py`) |
| **SWARM-DIR-1** init novo só `.swarm/` | `TestSwarmDir1InitNovo.*` (6): wrappers/estado/run; nenhum nome legado em arquivo, symlink ou diretório do alvo (`.git/hooks` incluído); hooks só `cs-guard.sh`, que aponta para `.swarm/harness/guard.py`; `cs-state next` roda; o guard bloqueia (exit 2) escrita direta em `.swarm/state/board.json5`; selftest verde com a sonda de harness único em OK | reinit/reinstall no próprio `.swarm/` não é tratado como outro harness |
| **SWARM-DIR-2** outro harness → não escreve | `TestSwarmDir2OutroHarnessNaoEscreve.test_cada_sinal_sozinho_bloqueia_init_e_install` (4 subTests: instance-v8, scripts-harness, kernel, hooks-terceiros, cada um com init e install), `.test_legado_desta_skill_aponta_upgrade`, `.test_repo-v8_v8_init_sem_flag_mostra_plano_e_nao_escreve` | `.test_settings_sem_hooks_nao_e_harness` (falso positivo proibido) |
| **SWARM-DIR-3** upgrade do legado | `TestSwarmDir3UpgradeLegado.*` (6): plano cita rename e não escreve; move para `.swarm/` sem sobrar o legado; caminhos reescritos (veja o escopo abaixo); board/team iguais byte a byte; ledgers append-only (o conteúdo novo começa com o antigo): `state/events.jsonl`, `state/harness-ledger.jsonl`, `memory/episodes.jsonl`, `interview.jsonl`, `team-approvals.jsonl`, `approvals.jsonl`; `team approved` continua exit 0; selftest G6 VERDE com a sonda de harness único em OK; validate --strict OK; o 2º upgrade é no-op | conflito com o `.swarm/` de outro harness → exit 3 sem escrever |
| **SWARM-DIR-4** `--replace-harness` no repo v8 | `TestSwarmDir4ReplaceHarness.*` (9): backup completo e fiel; removidos `scripts/harness`, `.claude/kernel`, `.swarm/instance.json`, `.swarm/init`, `.swarm/knowledge/{DOMAIN_INVARIANTS,ORCHESTRATION_MAP}.yaml`, `.swarm/state/init-validation.jsonl` e cada hook v8 citado no settings (`.claude/hooks/` == `[cs-guard.sh]`); settings só com hooks `cs-guard.sh` (com PreToolUse, PostToolUse e SessionStart); bloco v8 do `lefthook.yml` e chamadas `scripts/harness/` do Makefile removidos, PRESERVANDO `conventional:` (regra do usuário) e com `include specialists.mk`; BIZ-1..3 viram fatos citáveis; produto intacto; nenhum nome legado; selftest verde com harness único em OK | produto intacto (todo arquivo fora das zonas tem o mesmo sha, inclusive `harness/` da raiz, que é PRODUTO do repo v8); reinit após a substituição é exit 0 e não toca o backup; `test_pre_condicoes_da_copia` (sanidade do insumo) |
| **Harness único pós-instalação** | `TestHarnessUnicoPosInstalacao.test_residuo_reprova_e_limpo_aprova` (5 subTests de resíduo: kernel, scripts-harness, instance-v8, legado, hook-terceiro) | instalação limpa → `OK` e exit 0 |

### Zonas que a substituição pode tocar (SWARM-DIR-4, "produto intacto")
`.swarm/`, `.claude/`, `scripts/harness/`, `.tmp/`, `docs/state/` e os arquivos `lefthook.yml`, `Makefile`,
`specialists.mk`, `CLAUDE.md`, `AGENTS.md`, `HARNESS.md`, `ORCHESTRATION.md`, `INSTANCE.md`, `.gitignore`. Todo o
resto precisa ficar com o mesmo sha256 e nada pode ser apagado. O oráculo NÃO exige remover nem fazer backup de
`docs/state/` (o estado do v8 também é histórico do projeto); fica a critério do corretor, desde que seja dentro
da zona.

### Escopo do "nenhum `.specialists` remanescente" no SWARM-DIR-3
São cobrados TODO arquivo/symlink fora de `.swarm/` (emitidos `.claude/ .cursor/ .codex/ .github/`, `CLAUDE.md`,
`AGENTS.md`, `Makefile`, `specialists.mk`, settings, `cs-guard.sh`, inclusive `.bak` deixados em `.claude/`), o
symlink e o conteúdo de `.git/hooks/*` e, dentro de `.swarm/`, o mecanismo operante: `.swarm/bin/**` e
`.swarm/harness/**` (fora `__pycache__`). Dentro de `.swarm/`, os dados e o histórico (ledgers `*.jsonl` com cadeia
de hash, índices de memória, handoffs, `tmp/`, `backups/`) podem citar o caminho antigo: reescrevê-los quebraria o
append-only/a cadeia. No SWARM-DIR-1 e no SWARM-DIR-4 (alvos sem legado), a regra vale para o alvo inteiro, exceto
`.swarm/backups/harness-anterior/`.

## Allowlist do nome legado (teste de constante única)
Varre `scripts/**`, `assets/templates/**` e `references/**` (sem `__pycache__`/binários) e, à parte, `SKILL.md`,
`MODO-DE-USO.md` e `evals/check_run.py`. O `check_run.py` não pode ter nenhuma ocorrência. Nos dois guias, o nome só pode aparecer dentro de uma seção cujo título contenha "migra" ou "legad" (o mesmo detector de `scripts/doctests/tests/test_guia_de_uso.py`, que EXIGE essa seção nomeando a pasta legada e citando o `upgrade`). Revisão da iter9: o conflito entre os dois oráculos foi resolvido a favor da intenção do founder. Casamento:
`(?<![A-Za-z0-9_])\.specialists(?![A-Za-z0-9_])`. Identificadores como `paths.specialists_dir` e o nome
`codebase-specialists` não casam.

| Permitido | Por quê |
|---|---|
| `scripts/cslib/paths.py` | É a fonte única do nome legado (`LEGACY_STATE_DIR`) e o mantém em `RESERVED_PREFIXES`. No máximo 6 ocorrências |
| `scripts/harness/engine/hcore.py` | O motor é copiado ao alvo sem o cslib e precisa do espelho para detectar o legado (sonda de harness único). No máximo 6 ocorrências |
| `scripts/upgrade/**` | É o pacote da migração `rename-dir` e de seus testes, que montam o alvo legado de propósito |
| `references/migrations.json5` | O catálogo descreve a migração `rename-dir` (de onde → para onde) |
| `**/test_swarm_dir.py` | Este oráculo, se for copiado para dentro da skill. Ele monta o nome em tempo de execução e não tem o literal |

Todo o resto (instalador, emit, probes, memory, stage, templates, prompts, references/*.md e os testes das outras
frentes, como `scripts/harness/tests/fixture.py`) passa a usar `.swarm`. Detecção e mensagens que precisarem do
nome legado o importam de `cslib.paths` (ou de `hcore`, no motor).

## Efeitos colaterais conhecidos (para o corretor)
- `scripts/upgrade/tests/test_upgrade.py::test_rename_dir_reserved_is_refused` contradiz o SWARM-DIR-3 (hoje
  `rename-dir` é recusado). Mudá-lo é consequência direta desta especificação. Os demais testes de upgrade
  passam a ler `.swarm/run.json5`.
- Hoje `cs.py init` e `harness install` não têm `--replace-harness`. O init ganha a flag; o install só precisa recusar.
- Com uma migração nova, `VERSION` sobe, e `test_version_migrations.py` exige a entrada correspondente.
