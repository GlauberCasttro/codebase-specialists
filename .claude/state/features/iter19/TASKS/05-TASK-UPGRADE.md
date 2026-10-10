# 05-TASK-UPGRADE — migração automática no cs.py upgrade --apply

id: 05-TASK-UPGRADE
feature: iter19
tipo: CORRECAO
grupo: G2
agente: corretor (papel; executor e model reais vão para o Handoff)
CA: CA-05
depends: 04-TASK-MIGRAR-ESTADO (o upgrade chama o comando de migração do motor)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
Nova ação de migração (kind, ex.: `state-format`) no catálogo de ações do upgrade, que chama o comando do motor
(padrão de `do_state_tree`); `harness validate --strict` roda ANTES e DEPOIS; o plano lista a conversão sem escrever;
falha restaura o backup. O commit do resultado passa no pre-commit sem `--no-verify`. NÃO mudar o catálogo de
migrações aqui (task 06) nem preservar/alterar memória.

## Contexto
CA-05. Âncoras: upgrade/core.py:52-60 (VERIFY, PRESERVED, EXPLICIT_KINDS), 594-598 (plano), 820-845 (do_state_tree),
941-980; upgrade/version.py:23 (KINDS); guard.py:609-616 (estado passa se validate verde).

## Subtasks
1. Rodar TestCA05 (upgrade) e ver falhar (RED).
2. Registrar o kind, a ação e o validate antes; plano com a lista do dry-run do motor.
3. Rodar oráculo e suítes nos 2 Pythons (GREEN), incluindo o commit sem `--no-verify` do oráculo.

## Invariants
- Upgrade sem migração pendente não escreve nada; restauração em falha; nenhum `def` removido.

## Scope IN / OUT
IN: upgrade. OUT: motor (02–04), catálogo/versão/docs (06).

## Arquivos permitidos
- `scripts/upgrade/core.py`
- `scripts/upgrade/version.py`
- `scripts/upgrade/tests/test_iter19_upgrade.py`

## AC
- TestCA05 verde nos 2 Pythons.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA05
```

## Handoff
