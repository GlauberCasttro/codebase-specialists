# 12-TASK-RELATORIO-AUTOCORRECAO — Relatório final sem mandato, retry estruturado, escalada automática e lessons_checked

id: 12-TASK-RELATORIO-AUTOCORRECAO
feature: harness-evolucao
tipo: CORRECAO
grupo: G2
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-16, CA-17, CA-06
depends: 11-TASK-JSON-ARVORE (edita o mesmo state.py e teste; o relatório lê o estado já em JSON), 08-TASK-CLASSIFY-TEXTOS (edita o mesmo engine.py, cmds.py, machines.json5, platforms.py e harness.md), 06-TASK-CORRECT-ESCOPO (usa `mem.mark_applied` e a lição de falha com causa)
status: PENDENTE
gate: PENDENTE
complexidade: normal

## Goal
(1) `engine/report.py` + `cs-state report [--epico ID | --desde SEQ]`, só leitura, montado da projeção e do
`events.jsonl`: cenários, itens criados, estrutura, testes, falhas, correções, retestes, aprendizado (lições
registradas e aplicadas), memória atualizada, não resolvidos e evidências (comandos, sha das saídas, ids de evento);
skill `report` emitida (template `assets/templates/state/report.md`). (2) `retry` exige `--esperado --obtido --causa
--correcao`; esgotar `max_retries` leva a task a ESCALATED automaticamente com relatório; `max_attempts =
max_retries + 1` conferido ao carregar as máquinas. (3) `lessons_checked` entra em `SUBMISSION_KEYS`: submissão sem
ele, quando o brief injetou lição, é recusada; as lições checadas chamam `mem.mark_applied`. docs/02 e §6–7 de
`references/harness.md` atualizados. NÃO usar o mandato M5 (sem senha no TTY), NÃO mudar o relatório do M5.

## Contexto
CA-16, CA-17, CA-06 (submissão). Âncoras: `scripts/harness/engine/auto.py:2904-2908` (report só com mandato),
`scripts/harness/engine/cmds.py:94-101` (BLOCKED silencioso), `scripts/harness/machines.json5:8` (max_attempts
decorativo), `scripts/harness/engine/engine.py:929-945` (SUBMISSION_KEYS), `references/brief-schema.json5:52`;
achados F7, F31, F32.

## Subtasks
1. Rodar o oráculo (`-k CA16`, `-k CA17`, `-k CA06`) e ver falhar (RED).
2. `report.py` + subcomando + skill emitida e template.
3. Retry estruturado, escalada automática, conferência de `max_attempts`; `lessons_checked` na submissão.
4. Testes em `scripts/harness/tests/test_evolucao_arvore.py`; docs; oráculo e suítes `harness` e `emit` nos 2 Pythons.

## Invariants
- O relatório não escreve estado; o M5 e a senha (D-04) seguem intocados.
- Nada é marcado como resolvido sem evidência no relatório.

## Scope IN / OUT
IN: relatório, retry, escalada, submissão. OUT: memória em si (04–06), ciclo de vida (10).

## Arquivos permitidos
- `scripts/harness/engine/report.py`
- `scripts/harness/engine/state.py`
- `scripts/harness/engine/engine.py`
- `scripts/harness/engine/cmds.py`
- `scripts/harness/machines.json5`
- `scripts/harness/tests/test_evolucao_arvore.py`
- `scripts/emit/platforms.py`
- `assets/templates/state/report.md`
- `references/harness.md`
- `docs/02-harness.md`

## AC
- `cs-state report` sem mandato traz os 11 campos; 3 falhas levam a ESCALATED com o item no relatório; submissão sem
  `lessons_checked` com lição injetada é recusada.

## DoD
- Régua seletiva verde (harness, emit) nos 2 Pythons; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA16
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA17
```

## Handoff
