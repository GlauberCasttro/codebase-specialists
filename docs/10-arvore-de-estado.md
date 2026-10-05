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
