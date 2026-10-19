# 06-TASK-VERSAO — 0.15.0: VERSION, migração (harness + item-status + emit) e docs do upgrade

id: 06-TASK-VERSAO
feature: iter27
tipo: CORRECAO
grupo: G3
agente: corretor (papel; executor e model no Handoff)
CA: CA-09
depends: 03-TASK-MEMORIA-EN (a item-status normaliza o kind), 05-TASK-TEXTOS-EN (o upgrade reemite os textos já em inglês)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
VERSION 0.15.0 com UMA entrada nova em `references/migrations.json5` (actions: harness, item-status, emit) que leva
aos alvos o motor novo, o kind normalizado e os textos en; `docs/09-upgrade.md` com a migração 0.15.0 citando
`--include-emitted`; README com a versão. NÃO editar entradas antigas de migrations.json5 (histórico), NÃO reescrever
events.jsonl, NÃO mudar código.

## Contexto
CA-09. Âncoras: padrão da entrada 0.14.0 (`references/migrations.json5:132-139`); a `item-status` já regrava só o
arquivo cujo texto difere, sem evento (entrada 0.13.1); F5 (kind preservado hoje); `docs/09-upgrade.md` (5 citações
de flag pt).

## Subtasks
1. Rodar TestCA09 e ver vermelho.
2. VERSION, README e a entrada 0.15.0 em migrations.json5.
3. docs/09-upgrade.md: seção da 0.15.0 e citações en; teste novo `test_iter27_upgrade.py` (versão relativa).

## Invariants
- Entradas antigas de migrations.json5 intactas; events.jsonl do alvo byte a byte igual depois do upgrade.

## Scope IN / OUT
IN: versão, migração, doc do upgrade. OUT: código (02–04), outros textos (05).

## Arquivos permitidos
- `VERSION`
- `README.md`
- `references/migrations.json5`
- `docs/09-upgrade.md`
- `scripts/upgrade/tests/test_iter27_upgrade.py`

## AC
- TestCA09 verde nos 2 Pythons; suítes upgrade e doctests verdes.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA09 && cd ../../.. && python3 .claude/tools/e2e.py rodar --suites upgrade,doctests
```

## Handoff
