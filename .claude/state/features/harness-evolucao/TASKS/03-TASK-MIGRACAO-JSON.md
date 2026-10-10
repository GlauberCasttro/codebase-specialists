# 03-TASK-MIGRACAO-JSON — Migração JSON5 → JSON pelo upgrade, com detecção no init e contrato revisto

id: 03-TASK-MIGRACAO-JSON
feature: harness-evolucao
tipo: CORRECAO
grupo: G3
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-19, CA-18
depends: 02-TASK-GRAVADOR-JSON (usa o gravador e o resolvedor; mesmo grupo), 11-TASK-JSON-ARVORE (a migração do estado em árvore é delegada ao `cs-state migrate json-format` do motor), 06-TASK-CORRECT-ESCOPO (o ARCHITECTURE descreve o escopo do correct entregue), 12-TASK-RELATORIO-AUTOCORRECAO (o ARCHITECTURE descreve o relatório e a autocorreção entregues)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
Nova ação de upgrade `json-format` (kind explícito em `EXPLICIT_KINDS`) na entrada `0.11.0` de
`references/migrations.json5`: para cada documento `.json5` do harness no alvo, ler → gravar `.json` validado → só
então mover o original para o backup; estado em árvore delegado ao `cs-state migrate json-format` (evento do motor,
cadeia de hash íntegra); registro arquivo a arquivo no `upgrade_history`; restauração em falha; idempotente. O
`cs.py` detecta `.json5` de dados do harness no init/install e aponta o upgrade (sem aplicar sozinho). Revisar
`references/ARCHITECTURE.md` (§8-decies JSON, §8-duodecies escopo do correct, §8-septies árvore) e `docs/09-upgrade.md`.
NÃO converter artefatos do pipeline (facts, team, knowledge, panel, probes, run), NÃO converter JSONL.

## Contexto
CA-19 (e a parte de contrato do CA-18). Âncoras: `scripts/upgrade/core.py:675,864,959`, `scripts/cs.py:111-118`,
`references/migrations.json5:67`, `references/ARCHITECTURE.md:403`; achados F25, F27, F29.

## Subtasks
1. Rodar o oráculo (`-k CA19`) e ver falhar (RED).
2. `do_json_format` em `upgrade/core.py` + entrada 0.11.0 + kind explícito; testes em
   `scripts/upgrade/tests/test_json_format.py` (backup, roundtrip, original preservado até o fim, falha restaura,
   segunda execução sem mudança).
3. Detecção no `cs.py` (aviso + comando de upgrade); ARCHITECTURE e docs/09 atualizados com as decisões da E1.
4. Rodar o oráculo e as suítes de `upgrade` e `doctests` nos 2 Pythons.

## Invariants
- Original só sai depois do sucesso; falha no meio restaura o backup inteiro.
- O upgrade continua mostrando o plano e pedindo OK antes do `--apply` (SKILL.md:33).

## Scope IN / OUT
IN: upgrade, migração, detecção, contrato em prosa. OUT: o comando do motor (11), gravador (02).

## Arquivos permitidos
- `scripts/upgrade/core.py`
- `scripts/upgrade/tests/test_json_format.py`
- `scripts/cs.py`
- `references/migrations.json5`
- `references/ARCHITECTURE.md`
- `docs/09-upgrade.md`

## AC
- Alvo 0.10.0 em JSON5 migra para JSON com `validate` OK, registro por arquivo e idempotência; falha injetada restaura.

## DoD
- Régua seletiva verde (upgrade, doctests) nos 2 Pythons; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA19
```

## Handoff
