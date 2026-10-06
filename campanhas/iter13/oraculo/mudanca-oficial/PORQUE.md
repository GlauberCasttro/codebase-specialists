# Por que mexer no teste congelado `test_swarm_dir.py` (só 1 asserção)

**Arquivo:** `codebase-specialists/scripts/harness/tests/test_swarm_dir.py`
(sha256 antes do patch: `d56b7014e7b82d0d4d1334445f67bec739932e6f5eb5304d7bd636065f6cf687`)
**Patch:** `test_swarm_dir.patch`. Aplicar a partir de `~/.claude/skills/`:
`patch -p0 < campanhas/iter13/oraculo/mudanca-oficial/test_swarm_dir.patch`
(conferido com `patch -p0 --dry-run`).

## O conflito
`TestSwarmDir1InitNovo.test_cria_swarm_com_wrappers_estado_e_run` (oráculo da iter9, antes da árvore) exige
`.swarm/state/board.json5` depois do caminho de alvo novo (`cs.py init` + `cs.py harness install`). O requisito R3
da iter13 diz o contrário: alvo novo nasce em ÁRVORE, **sem** board plano legado (o layout da iter10, ESPEC §2.1:
"`board.json5` não existe mais"). Sem o patch, implementar R3 deixa esse teste vermelho; mantê-lo verde impede R3.

## O que muda (só esse ponto)
A asserção `isfile(.swarm/state/board.json5)` vira:
- `.swarm/backlog/`, `.swarm/state/`, `.swarm/archive/` existem (as três zonas);
- `.swarm/events.jsonl` existe (a cadeia do estado; no modo árvore ela mora na raiz de `.swarm/`);
- `.swarm/state/board.json5` **não** existe.

## Por que não enfraquece nada
- A intenção da asserção original era "o init criou o estado". Continua provada, agora pelo layout vigente, e com
  **mais** checagens (3 zonas + cadeia + ausência do legado) no lugar de 1.
- Nenhuma outra asserção do arquivo é tocada. Conferido à mão num alvo migrado para árvore: o guard continua
  bloqueando `Write` em `.swarm/state/board.json5` (exit 2: "é a árvore de estado... só o motor escreve") e
  `cs-state next` sai 0, ou seja, `test_wrapper_funciona_e_guard_protege_swarm_state` segue válido sem alteração.
- `TestSwarmDir3UpgradeLegado` (`PRESERVE_EQUAL = ("state/board.json5", ...)`) trata de alvo **legado**, que
  tem board plano por definição. Isso não muda.
- O que o oráculo da iter13 exige além disso (1º evento `init` com `layout: tree`, nenhuma migração, `cs-state tree`
  sem `migrate`, reinstalação mantendo a árvore) está em `../test_menores.py::TestR3InitNasceEmArvore`.
