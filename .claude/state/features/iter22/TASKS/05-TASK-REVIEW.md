# 05-TASK-REVIEW — Revisão isolada da feature

id: 05-TASK-REVIEW
feature: iter22
tipo: REVIEW
grupo: —
agente: revisor isolado (/revisor)
CA: CA-01, CA-02, CA-03, CA-04
depends: 04-TASK-QA (a revisão parte do portão verde)
status: PENDENTE
gate: PENDENTE

## Goal
Revisar o diff da cópia × HEAD contra os CAs, o oráculo e as evidências, com foco em: o guard continua fail-closed;
o subagente não ganhou escrita; a varredura falha de verdade. Veredito APPROVED ou CHANGES_REQUESTED. NÃO editar.

## Contexto
CA-01..CA-04; E2 F1–F5; portão da task 04.

## Subtasks
1. Ler FEATURE.md, E2, diff e portão.
2. Matriz CA → evidência; findings classificados.
3. Parecer no FEATURE.md.

## Invariants
- Sem escrita no produto; achado sem evidência não conta.

## Scope IN / OUT
IN: revisão. OUT: correção.

## Arquivos permitidos
- `.claude/state/features/iter22/TASKS/05-TASK-REVIEW.md`

## AC
- Parecer APPROVED registrado, ou CHANGES_REQUESTED com findings que voltam às tasks donas.

## DoD
- Aceite Review registrado no FEATURE.md; Handoff preenchido.

## Verificação
```bash
python3 .claude/tools/contrato.py completo .claude/state/features/iter22
```

## Handoff
