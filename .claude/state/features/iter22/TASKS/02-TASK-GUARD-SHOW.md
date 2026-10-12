# 02-TASK-GUARD-SHOW — show em STATE_SUB, varredura subcomandos × guard e docstring do caderno

id: 02-TASK-GUARD-SHOW
feature: iter22
tipo: CORRECAO
grupo: G1
agente: corretor (papel; executor e model reais vão para o Handoff)
CA: CA-01, CA-02, CA-03, CA-04
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
`show` entra em STATE_SUB["main"] e STATE_SUB["any"]; teste de regressão que roda o show PELO hook pre-bash
(principal e subagente); teste-varredura que compara o argparse do state.py com STATE_SUB + regras explícitas e
falha com subcomando sem regra; docstring de notebook_text_problems com o comportamento atual (bloco aceito só se
igual ao render do cs-mem). NÃO mudar regras de outros subcomandos nem o fail-closed do desconhecido.

## Contexto
CA-01..CA-03 e a docstring do CA-04. Âncoras: guard.py:104-105 (F4), :262-267 (F1/F3), :330, :345.

## Subtasks
1. Rodar o oráculo e ver CA-01..CA-03 falharem (RED).
2. Acrescentar `show` às duas listas; escrever os testes (hook + varredura); corrigir a docstring.
3. Oráculo e suíte harness nos 2 Pythons (GREEN).

## Invariants
- Subcomando desconhecido continua recusado; nenhum `def` removido.

## Scope IN / OUT
IN: guard e testes. OUT: catálogo/versão/docs (task 03); o que o show exibe (B-33).

## Arquivos permitidos
- `scripts/harness/engine/guard.py`
- `scripts/harness/tests/test_iter22_guard.py`

## AC
- TestCA01..TestCA03 verdes nos 2 Pythons; suíte harness sem regressão.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter22/oraculo && python3 -m unittest test_iter22.TestCA01 test_iter22.TestCA02 test_iter22.TestCA03
```

## Handoff
