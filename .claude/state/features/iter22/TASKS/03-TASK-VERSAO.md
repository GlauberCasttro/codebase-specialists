# 03-TASK-VERSAO — 0.12.1 com migração no catálogo e nota de upgrade

id: 03-TASK-VERSAO
feature: iter22
tipo: CORRECAO
grupo: G2
agente: corretor (papel; executor e model reais vão para o Handoff)
CA: CA-04
depends: 01-TASK-ORACULO (o oráculo congelado é a régua; o texto descreve o comportamento que o oráculo exige)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
VERSION 0.12.1; `references/migrations.json5` com `version: "0.12.1"` e entrada `to: "0.12.1"` com a ação `harness`
(reinstala o guard), `why` no estilo das anteriores; README com a versão; nota em docs/09-upgrade.md. NÃO mudar código.

## Contexto
CA-04. Âncoras: references/migrations.json5:25,95 (F5); docs/09-upgrade.md (seção Migração 0.12.0).

## Subtasks
1. Rodar a parte de versão do TestCA04 e ver falhar (RED).
2. VERSION, README, catálogo, nota na docs/09.
3. Oráculo e suítes upgrade/doctests nos 2 Pythons (GREEN).

## Invariants
- Nenhum nome privado; oráculos de versão relativos (B-32) seguem verdes.

## Scope IN / OUT
IN: versão, catálogo e doc de upgrade. OUT: código.

## Arquivos permitidos
- `VERSION`
- `README.md`
- `references/migrations.json5`
- `docs/09-upgrade.md`

## AC
- TestCA04 verde nos 2 Pythons (junto com a task 02).

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter22/oraculo && python3 -m unittest test_iter22.TestCA04
```

## Handoff
