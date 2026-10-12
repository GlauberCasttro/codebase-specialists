# 03-TASK-VERSAO — 0.12.2 com migração no catálogo e nota de upgrade

id: 03-TASK-VERSAO
feature: iter24
tipo: CORRECAO
grupo: G2
agente: corretor (papel; executor e model reais vão para o Handoff)
CA: CA-07
depends: 01-TASK-ORACULO (o oráculo congelado é a régua; o texto descreve o comportamento que o oráculo exige)
status: DONE
gate: PASS
complexidade: normal

## Goal
VERSION 0.12.2; catálogo com `version: "0.12.2"` e UMA entrada `to: "0.12.2"` com a ação `harness` (reinstala o guard),
`why` no estilo das anteriores; README; nota "Migração 0.12.2" em docs/09-upgrade.md. NÃO mudar código.

## Contexto
CA-07. Âncoras: references/migrations.json5 (0.12.1 é a última depois da iter22); docs/09-upgrade.md.

## Subtasks
1. Rodar a parte de versão do TestCA07 e ver falhar (RED).
2. VERSION, README, catálogo, docs/09.
3. Oráculo + suítes upgrade/doctests nos 2 Pythons (GREEN); oráculos de versão relativos verdes.

## Invariants
- Nenhum nome privado; versão relativa nos oráculos (B-32).

## Scope IN / OUT
IN: versão, catálogo, docs/09. OUT: código.

## Arquivos permitidos
- `VERSION`
- `README.md`
- `references/migrations.json5`
- `docs/09-upgrade.md`

## AC
- TestCA07 verde nos 2 Pythons (junto com a task 02).

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA07
```

## Handoff
- Executor: Claude Code · general-purpose · model sonnet.
- Arquivos (cópia): VERSION 0.12.2; README "Versão: **0.12.2**"; references/migrations.json5 (version 0.12.2 + uma entrada to 0.12.2 ação harness); docs/09-upgrade.md (seção "Migração 0.12.2").
- TestCA07: 3 OK nos 2 Pythons depois do guard (task 02); oráculo inteiro 22 OK. Régua completa VERDE (upgrade 23 OK/7 skip, doctests 19 OK) nos 2.
- Escopo por snapshot: só os 4 arquivos. Privacidade: 0.
- Revisor: instância isolada general-purpose · sonnet · APPROVED. Ressalva MENOR: o texto diz "branch -D" sem "de branch protegida" (para o principal só a protegida é recusada).
- Limites: RED não foi rodado antes da edição (executor declarou); a falha anterior era trivialmente VERSION 0.12.1.
