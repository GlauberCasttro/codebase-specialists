# 03-TASK-AMEND-SHOW — amend refletido no arquivo e cs-state show

id: 03-TASK-AMEND-SHOW
feature: iter19
tipo: CORRECAO
grupo: G1
agente: corretor (papel; executor e model reais vão para o Handoff)
CA: CA-03, CA-04
depends: 02-TASK-FORMATO-CHAVES (mesmos arquivos tree.py/state.py; o show e o history usam o formato novo)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
`cs-state amend` numa task iniciada anexa ao MESMO evento uma op `tput` do item da árvore (mapeamento inverso de
tree.py:683-686) e um registro em `history` com before/after/reason; o reopen não ressuscita o AC removido; task não
iniciada aceita amend de `acceptance_criteria`. Novo `cs-state show <id>` (TREE_CMDS) imprime Markdown sem escrever.
NÃO mudar o formato dos eventos antigos nem o comportamento de campos não espelháveis (seguem só na M2).

## Contexto
CA-03, CA-04. Âncoras: state.py:312-327, 437, 448, 664-666; cmds.py:883-937; tree.py:593-615, 633, 648-686,
1207; views.py (resumo do histórico).

## Subtasks
1. Rodar TestCA03/TestCA04 e ver falhar (RED).
2. Espelhar amend da M2 no item (tput + history) para acceptance_criteria/allowed_paths/verification_command/title;
   liberar acceptance_criteria em TREE_AMENDABLE para task não iniciada.
3. Implementar `cs-state show <id>` (aceita alias; id inexistente ⇒ erro, exit ≠ 0).
4. Rodar oráculo e suítes nos 2 Pythons (GREEN).

## Invariants
- Um único evento por amend (atomicidade); cadeia íntegra; validate verde; nenhum `def` removido.

## Scope IN / OUT
IN: amend (M2 e árvore) e show. OUT: formato (02), migração (04/05), docs (06).

## Arquivos permitidos
- `scripts/harness/engine/cmds.py`
- `scripts/harness/engine/state.py`
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/views.py`
- `scripts/harness/tests/test_iter19_estado.py`

## AC
- TestCA03 e TestCA04 verdes nos 2 Pythons; TestCA01/02 continuam verdes.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA03 test_iter19.TestCA04
```

## Handoff
