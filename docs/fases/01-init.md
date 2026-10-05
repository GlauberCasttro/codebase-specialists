# Etapa 1 — init

**Objetivo:** alvo confirmado, plataformas escolhidas, estado de execução criado.

**Por que existe:** tudo o que vem depois lê `.swarm/run.json5` (plataformas, modo, commit, estado das
sub-etapas). Errar o alvo (subdiretório em vez da raiz, ou pasta que não é git) contamina o scan inteiro: o
histórico vira o de outro repositório e o inventário fica parcial.

```text
 init.1 (main)                 init.2 (user)                       init.3 (main)
 ┌───────────────────────┐     ┌─────────────────────────────┐     ┌────────────────────────────────┐
 │ alvo é RAIZ de repo   │ ──▶ │ plataformas + modo; mostra  │ ──▶ │ cs.py init --platforms <…>     │
 │ git? (recomenda limpo)│     │ o que será criado (4–6 l.)  │     │ merge idempotente em run.json5 │
 └───────────────────────┘     └─────────────────────────────┘     └────────────────────────────────┘
   check: init --check-repo      check: resposta literal             check: init --check
                                                                         │
                                               cs.py stage done init ◀───┘ → stages/init.handoff.json5
```

## Sub-etapas

### init.1 — confirmar a raiz do repositório

| | |
|---|---|
| Quem | main |
| Comando / check | `cs.py stage check init.1` (roda `cs.py init --check-repo`) |
| Lê | o git do alvo |
| Grava | o estado do item em `.swarm/run.json5` |

`init --check-repo` falha se o alvo não é a raiz de um repositório git. Recomenda-se `git status` limpo: a
skill escreve em `.swarm/`, `.claude/`, `.cursor/`, `.github/`, `.codex/`, `AGENTS.md`, `CLAUDE.md` (bloco
gerenciado, com backup) e `Makefile` (uma linha `include`), e um working tree limpo deixa claro o que veio dela.

### init.2 — plataformas e modo (toque humano)

| | |
|---|---|
| Quem | user |
| Comando | `cs.py stage check init.2 --answer "<resposta literal>"` |
| Grava | resposta em `run.json5` e uma linha em `.swarm/interview.jsonl` |

O orquestrador mostra em 4–6 linhas o que será criado e confirma: plataformas (default: as 4 —
`claude-code,cursor,copilot,codex`) e **modo** (`--fast` padrão; `--full` só se o usuário pediu). A resposta
registra o modo (SKILL.md: `--answer "… modo --fast"` ou `"… --full pedido pelo usuário"`).

Exemplo real sem usuário (py-billing, iteração 4, `outputs/stage-log.txt`):

```text
$ cs stage check init.2 --answer [sem usuário] plataformas default: claude-code,cursor,copilot,codex; modo --fast (padrão). Será criado: .swarm/ (run.json5, facts, team, memória, bin), cartões por plataforma (.claude/agents, .cursor, .github, AGENTS.md), harness com hooks/gates e pre-commit.
ok init.2: confirmar plataformas e mostrar o que será criado (4–6 linhas)
```

(`cs` ali é a função de shell `cs() { python3 …/cs.py "$@"; }` que o executor usou.)

### init.3 — criar/mesclar o estado

| | |
|---|---|
| Quem | main |
| Comando | `cs.py init --platforms claude-code,cursor,copilot,codex` (ou só as pedidas) |
| Check | `cs.py init --check` — `run.json5` válido e criado/mesclado por um `cs.py init` **explícito** |
| Grava | `.swarm/run.json5`; se `team.json5` já existe, sincroniza as plataformas dele |

`cs.py init` faz **merge idempotente** (`scripts/stage/engine.py → init_run`): rodar de novo não perde progresso;
`--platforms` substitui as plataformas. `--force` recria `run.json5` e **perde** o progresso. Plataforma
desconhecida é recusada ("válidas: … (default: as 4)").

Saída real (py-billing, iteração 4) — o `stage check init.1` já tinha criado o arquivo, e o `init` explícito
mesclou:

```text
$ cs init --platforms claude-code,cursor,copilot,codex
mesclado em .swarm/run.json5 (run_id f124f41b05083906; progresso mantido): init explícito registrado
```

### Fechamento

```text
cs.py stage done init
```

Saída real: `etapa init fechada → .swarm/stages/init.handoff.json5; próxima: scan`.

## Erros comuns e como resolver

| Sintoma | Causa | Resolução |
|---|---|---|
| `C="python3 …/cs.py --target X"; $C stage status` não funciona em zsh | zsh não divide palavras de variável | use a função `cs() { python3 …/cs.py "$@"; }` ou escreva o comando inteiro (notas da iteração 3, go-polyglot e py-billing) |
| `init --platforms` "sem efeito" depois de `stage check init.1` | defeito da iteração 2 (o check criava `run.json5` e o init não mesclava) | corrigido: hoje o `init` explícito mescla (saída "mesclado em … progresso mantido") |
| `plataforma desconhecida` | nome fora de `claude-code,cursor,copilot,codex` | use exatamente esses nomes, separados por vírgula |
| alvo errado | sessão aberta num subdiretório | `--target <raiz>`; o `init --check-repo` reprova |

## O que muda no `--fast`

Nada na execução do init. O modo é **registrado** em init.2 e decide, depois, quais sub-etapas serão puladas
(`rt.1`–`rt.4`, `validate.4`).
