# Estado como árvore de pastas (0.7.0)

Resumo para humanos do que a campanha iter10 entregou; o passo a passo de uso está no `MODO-DE-USO.md`.

- **Árvore**: épico → sprint → feature → task, em `.swarm/backlog/` (não começou), `.swarm/state/` (em execução) e
  `.swarm/archive/` (fechado, mesma árvore). `events.jsonl` na raiz de `.swarm/`; `INDEX.md` gerado. Só o `cs-state`
  escreve nas zonas; o guard bloqueia o modelo e `cs-state validate` pega edição à mão e órfãos.
- **Stories**: 1 agente = task tipada; 2 ou mais = story composta (pasta + uma task por agente); `promote` converte.
- **Tipos e DoR** (`cs-state check <id>`): US (como/quero/para + critério), BUG (teste de reprodução que falha),
  FIX (`--fixes` + `--teste`), CHORE (`--motivo` + `--verify-cmd`).
- **Regras**: uma feature ativa por vez; tasks que colidem em arquivo ficam em ondas (`wave`) diferentes.
- **Subcomandos**: new, start, plan, move, park, promote, close, reopen, feature drop, find, tree, board, validate,
  check, migrate state-tree. `--dry-run` nos que mudam estado; `--json` em `tree` e `board`.
- **Sessão**: `cs-session save` grava o carimbo de 8 blocos; `save --check` o valida.
- **Skills (14)**: `/board` e `/new-*` o modelo chama sozinho; `/close-*`, `/reopen`, `/park`, `/move` só o humano.
- **Upgrade**: migração `state-tree` automática; correções U-1 (alvo pausado) e U-2 (backup sem `.git`/`tmp`).

## Formato do estado em JSON (0.11.0)

Desde a 0.11.0 o estado de entidade é **JSON padrão** (`.json`), não mais JSON5 (`.json5`):

- **O que muda de formato**: os itens da árvore (`epico.json`, `sprint.json`, `feature.json`, `story.json` e as
  tasks), os carimbos de sessão (`.swarm/state/sessoes/*.json`) e a projeção/visões do motor em
  `.swarm/state/.engine/` (`projection.json`, `autonomy.json`, `selftest.json`, `autonomy-report.json`).
- **Bytes determinísticos**: `indent=2`, um item de lista por linha, sem comentários; o `_generated_by` é um campo
  do próprio JSON. Só o `cs-state` (e o `cs-session save`) escreve; edição à mão continua barrada pelo guard e
  pelo `cs-state validate`.
- **Chaves em inglês, na ordem de leitura**: `id, kind, type, title, agent, allowed_paths, protected_paths, as_a,
  i_want, so_that, acceptance_criteria, verify_cmd, status, wave, route, created_at, created_by, started_at, closed,
  m2, aliases, path, parent`; o resto em ordem alfabética e o `history` por último.
- **O campo `status`** (0.13.1): todo item grava o próprio estado canônico (vocabulário D-37): `TODO`, `BACKLOG`,
  `ACTIVE`, `DONE`, `DROPPED` e, para o par M2, `<STATUS>/<DELEG>`. É derivado do ciclo de vida (zona, início,
  fechamento, descarte) e regravado pelo `cs-state` a cada mudança; um item antigo ganha o campo pelo
  `cs-state migrate item-status` (o upgrade da 0.13.1 roda). A exibição (`cs-state tree`, `show`, board) segue em
  português.
- **O mapa de chaves** (antigo → novo), por caminho — a mesma palavra pode ter outro destino em outro nível:

| Onde | Antes (pt) | Agora (en) |
|---|---|---|
| item | `tipo`, `como`, `quero`, `para` | `type`, `as_a`, `i_want`, `so_that` |
| item | `criterios` (`teste` dentro) | `acceptance_criteria` (`test` dentro) |
| item | `teste`, `reproducao`, `motivo`, `aceite` | `proving_test`, `failing_test`, `reason`, `acceptance_cmd` |
| item | `epico`, `objetivo`, `metrica`, `meta` | `epic`, `objective`, `metric`, `goal` |
| item | `reaberta`, `reaberturas` | `reopened`, `reopenings` |
| item | `historico` (`acao`, `de`, `para` dentro) | `history` (`action`, `from`, `to` dentro) |
| item `closed` | `entregue`, `devolvido`, `metricas`, `origem` | `delivered`, `returned`, `metrics`, `origin` |
| `closed.metricas` | `tentativas`, `status_m2` | `attempts`, `m2_status` |
| carimbo de sessão | `blocos` (`titulo`, `linhas` dentro) | `blocks` (`title`, `lines` dentro) |

  `para` é `so_that` na story e `to` no `history`: por isso o mapa é por caminho, não por palavra. A leitura aceita
  os dois idiomas e os dois formatos; um `.json` com chave em português é edição à mão e o `validate` o aponta, e um
  `.json5` ao lado do `.json` do mesmo item é órfão do formato anterior.
- **Não mudam** (continuam como estavam): os logs JSONL canônicos (`events.jsonl`, harness-ledger, aprovações,
  `model-router.jsonl`), a config JSON5 (`team`, `run`, `harness/config`, `machines`, `routing`, `migrations`), a
  memória do `cs-mem` e as chaves do mandato M5 (em português).

### `cs-state show` e o `amend` refletido

- `cs-state show <id>` (o id ou um id anterior) imprime a task em Markdown, **só leitura**: tipo, estado e zona,
  agente, pai, arquivo, `allowed_paths`, verificação, aceite, como/quero/para, critérios e histórico.
- `cs-state amend` numa task **já iniciada** regrava, no MESMO evento, o arquivo da task (campos `acceptance_criteria`,
  `allowed_paths`, `verify_cmd`, `title`) e acrescenta ao `history` do item `action: "amend"` com `before`, `after` e
  `reason`. Campo que não é espelhável, ou emenda que não muda nada, deixa o arquivo como está. Em task ainda não
  iniciada a emenda (`allowed_paths` e `acceptance_criteria`) já valia no item da árvore.

### Migrar um alvo existente

`python3 <alvo>/.swarm/harness/state.py --root <alvo> migrate state-format [--dry-run]` (ou `cs-state migrate
state-format`; o `upgrade --apply` chama o motor da skill):

- converte todo `.json5` de estado (itens, carimbos de sessão, `.engine`) em `.json` por **UM evento encadeado**
  novo (`arvore.format`), com o mapa de caminhos antigo → novo; os eventos antigos não são reescritos;
- **recusa** (exit 1) se `cs-state validate` não passa antes: conserte o estado e rode de novo;
- **idempotente**: sem `.json5` de estado, diz "nada a migrar" e não grava evento;
- `--dry-run` lista os arquivos e não escreve nada.
