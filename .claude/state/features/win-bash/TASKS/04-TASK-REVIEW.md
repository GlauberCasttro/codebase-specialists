# 04-TASK-REVIEW — Revisão isolada da escolha do bash

id: 04-TASK-REVIEW
feature: win-bash
tipo: REVIEW
grupo: —
agente: revisor isolado (/revisor, sem escrita)
CA: CA-01, CA-02, CA-03, CA-04, CA-05
depends: 03-TASK-QA (revisa o que o portão aprovou)
status: PENDENTE
gate: PENDENTE

## Goal
Revisar o diff da task 02 contra os CAs e as evidências do QA; parecer APPROVED ou CHANGES_REQUESTED com
`arquivo:linha`. NÃO editar nada.

## Contexto
CA-01..CA-05. Pontos de atenção: nenhum caminho cai no WSL em silêncio; macOS/Linux igual a hoje; a Recusa é clara.

## Subtasks
1. Diff do `feature.py` e do `test_feature.py` contra o HEAD.
2. Conferir as evidências do QA (portão, oráculo nos 2 shells, `fechar check win-motor-copia`).
3. Parecer com achados evidenciados.

## Invariants
- Revisão é leitura: nenhum arquivo do projeto muda.

## Scope IN / OUT
IN: diff e evidências. OUT: correção.

## Arquivos permitidos
- `.claude/state/features/win-bash/TASKS/04-TASK-REVIEW.md`

## AC
- Parecer no Handoff, cada achado em `arquivo:linha`.

## DoD
- APPROVED, ou CHANGES_REQUESTED devolvido à task 02.

## Verificação
```bash
git diff --stat HEAD -- .claude/tools/feature.py .claude/tools/tests/test_feature.py
```

## Handoff
