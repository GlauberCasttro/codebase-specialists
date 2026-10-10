# 05-TASK-MEMORIA-INIT — O init cria, valida e repara a memória do projeto e de cada agente, em JSON

id: 05-TASK-MEMORIA-INIT
feature: harness-evolucao
tipo: CORRECAO
grupo: G1
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-03, CA-18
depends: 04-TASK-MEMORIA-SEGURANCA (edita o mesmo mem.py e o mesmo teste), 02-TASK-GRAVADOR-JSON (os arquivos de memória nascem pelo gravador JSON)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
`mem.ensure_layout(root, agents)` chamado pelo `install` (e reexecutável): cria `knowledge.jsonl` e `episodes.jsonl`
vazios, `promotions` e a memória de cada agente do `team.json5` (+ `lead`) no caminho atual
(`.swarm/state/memory/agents/<a>.json`), testa escrita por sonda atômica, registra `memory_init {created, repaired,
kept}` no ledger e na saída do install, recria só o que falta e não muda o sha do que existe; arquivo ilegível gera
recusa com backup em `.swarm/backups/memory/`. Memória de agente, promotions e stale passam a ser gravadas em JSON pelo
gravador da 02 (leitura de `.json5` legado preservada); `mem_paths['board']` usa o caminho do modo árvore; o guard
resolve nomes de estado pelo resolvedor (`board.json`/`board.json5`). NÃO parar de ler o legado `.swarm/memory/agents`
(migrate_old_agents fica), NÃO mexer no escopo do correct.

## Contexto
CA-03, CA-18 (memória). Âncoras: `scripts/harness/install.py:355` (só o diretório legado), `scripts/memory/mem.py:169-174`
(caminhos; board legado), `:792` e `:208` (ilegível vira vazio e é sobrescrito), `:754,797,871` (gravação JSON5),
`scripts/harness/engine/guard.py:308,378` (nomes `board.json5`/`config.json5`); achados F3, F8b, F8d.

## Subtasks
1. Rodar o oráculo (`-k CA03`) e ver falhar (RED).
2. `ensure_layout` + chamada no `install._apply` com relatório e evento; recusa com backup para arquivo ilegível.
3. Gravação da memória em JSON pelo gravador da 02; `mem_paths` no modo árvore; guard pelo resolvedor.
4. Rodar o oráculo e as suítes de `memory` e `harness` nos 2 Pythons.

## Invariants
- Nenhuma memória existente muda sem autorização; rodar duas vezes dá o mesmo disco.
- O install continua idempotente e honesto: "nada mudou" só quando nada mudou.

## Scope IN / OUT
IN: criação, reparo e formato da memória; nomes de estado no guard. OUT: escopo/registro do correct (06).

## Arquivos permitidos
- `scripts/memory/mem.py`
- `scripts/memory/tests/test_evolucao_memoria.py`
- `scripts/harness/install.py`
- `scripts/harness/engine/guard.py`

## AC
- Alvo novo com N agentes tem N+1 memórias de agente e a memória do projeto depois do install; segunda execução
  repara um arquivo apagado sem tocar os outros; ledger com `memory_init`.

## DoD
- Régua seletiva verde (memory, harness) nos 2 Pythons; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA03
```

## Handoff
