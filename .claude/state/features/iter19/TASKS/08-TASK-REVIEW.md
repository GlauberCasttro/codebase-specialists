# 08-TASK-REVIEW — Revisão isolada da feature

id: 08-TASK-REVIEW
feature: iter19
tipo: REVIEW
grupo: —
agente: revisor isolado (/revisor)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06
depends: 07-TASK-QA (a revisão parte do portão verde)
status: PENDENTE
gate: PENDENTE

## Goal
Revisar o diff da cópia de trabalho × HEAD contra os CAs, o oráculo congelado e as evidências, com foco em: cadeia de
eventos, idempotência da migração, mapa de chaves por caminho, amend atômico. Veredito APPROVED ou CHANGES_REQUESTED.
NÃO editar nada.

## Contexto
CA-01..CA-06; E2 F1–F6; portão da task 07.

## Subtasks
1. Ler FEATURE.md, E2, diff e portão.
2. Matriz CA → evidência; findings classificados.
3. Registrar o parecer no FEATURE.md.

## Invariants
- Sem escrita no produto; achado sem evidência não conta.

## Scope IN / OUT
IN: revisão. OUT: correção.

## Arquivos permitidos
- `.claude/state/features/iter19/TASKS/08-TASK-REVIEW.md`

## AC
- Parecer APPROVED registrado, ou CHANGES_REQUESTED com findings que voltam às tasks donas.

## DoD
- Aceite Review registrado no FEATURE.md; Handoff preenchido.

## Verificação
```bash
python3 .claude/tools/contrato.py completo .claude/state/features/iter19
```

## Handoff
