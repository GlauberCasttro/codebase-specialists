# 06-TASK-VERSAO-DOCS — 0.11.0, migração no catálogo e documentação do formato

id: 06-TASK-VERSAO-DOCS
feature: iter19
tipo: CORRECAO
grupo: G3
agente: corretor (papel; executor e model reais vão para o Handoff)
CA: CA-06
depends: 01-TASK-ORACULO (o oráculo congelado é a régua; o texto descreve o comportamento que o oráculo exige)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
VERSION 0.11.0; `references/migrations.json5` com `version: "0.11.0"` e entrada `to: "0.11.0"` (harness, emit e a
ação de formato de estado), `why` no estilo das anteriores; README com a versão; docs do formato JSON, do mapa de
chaves, do amend refletido, do `cs-state show` e da migração. NÃO mudar código.

## Contexto
CA-06. Âncoras: references/migrations.json5 (0.10.1 é a última); docs/09-upgrade.md; docs/10-arvore-de-estado.md;
docs/06-referencia-cli.md; E2 F3 (mapa pt→en).

## Subtasks
1. Rodar a parte de versão de TestCA06 e ver falhar (RED).
2. VERSION, README, catálogo de migrações.
3. Docs: formato, chaves, amend, show, migração (inclui nota B-20: 1º reverify de verify pré-0.10.0 pede revisão nova).
4. Rodar oráculo e suítes nos 2 Pythons (GREEN).

## Invariants
- Nenhum nome privado; o kind citado no catálogo é o que a task 05 registra.

## Scope IN / OUT
IN: versão, catálogo e docs. OUT: código.

## Arquivos permitidos
- `VERSION`
- `README.md`
- `references/migrations.json5`
- `references/ARCHITECTURE.md`
- `docs/01-conceitos.md`
- `docs/05-sessao-e-retomada.md`
- `docs/06-referencia-cli.md`
- `docs/09-upgrade.md`
- `docs/10-arvore-de-estado.md`

## AC
- TestCA06 verde nos 2 Pythons; docs coerentes com o comportamento.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA06
```

## Handoff
