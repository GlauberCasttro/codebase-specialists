# 05-TASK-REVIEW — Revisão isolada da feature (segurança)

id: 05-TASK-REVIEW
feature: iter24
tipo: REVIEW
grupo: —
agente: revisor isolado (/revisor)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07
depends: 04-TASK-QA (a revisão parte do portão verde)
status: IN_PROGRESS
gate: PENDENTE

## Goal
Revisar o diff da cópia × HEAD contra os CAs, o oráculo e as evidências, tentando REABRIR as portas por variações
(outros shells, `python -m` com caminho, hardlink por outros programas, flags equivalentes, refspecs), e checar que
não há falso bloqueio novo nas leituras do dia a dia. Veredito APPROVED ou CHANGES_REQUESTED. NÃO editar.

## Contexto
CA-01..CA-07; E2 F1–F9; portão da task 04.

## Subtasks
1. Ler FEATURE.md, E2, diff e portão.
2. Sondas de variação em cópia temporária; matriz CA → evidência.
3. Parecer no FEATURE.md.

## Invariants
- Sem escrita no produto; achado sem evidência não conta.

## Scope IN / OUT
IN: revisão. OUT: correção.

## Arquivos permitidos
- `.claude/state/features/iter24/TASKS/05-TASK-REVIEW.md`

## AC
- Parecer APPROVED registrado, ou CHANGES_REQUESTED com findings que voltam às tasks donas.

## DoD
- Aceite Review registrado no FEATURE.md; Handoff preenchido.

## Verificação
```bash
python3 .claude/tools/contrato.py completo .claude/state/features/iter24
```

## Handoff
