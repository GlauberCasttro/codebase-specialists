# 04-TASK-MIGRAR-ESTADO — cs-state migrate (formato) por evento encadeado

id: 04-TASK-MIGRAR-ESTADO
feature: iter19
tipo: CORRECAO
grupo: G1
agente: corretor (papel; executor e model reais vão para o Handoff)
CA: CA-05
depends: 03-TASK-AMEND-SHOW (mesmos arquivos tree.py/state.py; a migração grava no formato final)
status: DONE
gate: PASS
complexidade: normal

## Goal
Comando do motor (ex.: `cs-state migrate state-format [--dry-run]`) que converte todo `.json5` de estado de entidade
e a projeção para `.json` com chaves em inglês por UM evento encadeado novo (`arvore.format`) com `tput` de cada item e
`data.paths` {antigo.json5: novo.json}; idempotente ("nada a migrar"); dry-run lista sem escrever; validate e
`read_chain` verdes antes e depois. NÃO reescrever eventos antigos; NÃO tocar memória nem config.

## Contexto
CA-05. Âncoras: tree.py:268-287 (run_build dry_run), 1481-1530 (precedente arvore.migrate); hcore.py:325-360
(append_chained, read_chain), 573-575 (tput opaco).

## Subtasks
1. Rodar a parte do motor de TestCA05 e ver falhar (RED).
2. Implementar a migração com o evento encadeado e o mapa de caminhos; views/find/show resolvem caminho antigo.
3. Idempotência e dry-run; rodar oráculo e suítes nos 2 Pythons (GREEN).

## Invariants
- Histórico byte a byte até o append; cadeia íntegra; nenhum `def` removido.

## Scope IN / OUT
IN: o comando de migração no motor. OUT: chamada pelo upgrade (05), docs (06).

## Arquivos permitidos
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/state.py`
- `scripts/harness/engine/hcore.py`
- `scripts/harness/tests/test_iter19_estado.py`

## AC
- A migração do motor converte o alvo realista do oráculo, idempotente, com validate e cadeia íntegros.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA05
```

## Handoff
- Executor: general-purpose · sonnet (ciclo 1), RED observado (10/26 falhando antes). Revisor: general-purpose · opus,
  instância isolada · APPROVED (1ª instância caiu por limite de API; 2ª concluiu). Snapshot pré-revisor: só artefatos
  de build `evals/**/obj/` mudaram (gerados pelas suítes), nenhum código.
- Comando: `python3 <alvo>/.swarm/harness/state.py --root <alvo> migrate state-format [--dry-run]` (kind `state-format`
  para a task 05). Dry-run: "state-format (dry-run): N arquivo(s) … nada foi escrito" + pares; apply: "migrado: N …";
  sem .json5: "nada a migrar: estado já em JSON (idempotente)", exit 0; RECUSADO (exit 1) se o validate não passa antes.
- Arquivos: tree.py (migrate_format, format_plan, path_ident; find/show resolvem caminho antigo; lista plano→árvore com
  .json; `after` normalizado; amend sem mudança não registra), state.py (subcomando), tests/test_iter19_estado.py (26).
- Régua do tech-lead (cópia, 2 Pythons): harness 344 OK (16 skip), upgrade 8 OK, memory 14 OK.
- Revisor: replay do zero == disco byte a byte; dry-run não escreve nada (inclui .git); eventos antigos prefixo byte a
  byte; validate --strict e read_chain OK.
- Ressalva (MENOR, BACKLOG B-29): queda entre gravar os itens e anexar o evento perde o mapa antigo→novo na auditoria
  (operação não afetada). Limites aceitos: post=False; visões/rascunho do mandato não convertidos (leitura dos 2
  formatos); amend sem mudança em task iniciada ainda gera evento M2.
