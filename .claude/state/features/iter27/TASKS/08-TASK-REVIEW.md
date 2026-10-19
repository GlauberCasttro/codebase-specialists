# 08-TASK-REVIEW — Revisão isolada da iter27

id: 08-TASK-REVIEW
feature: iter27
tipo: REVIEW
grupo: —
agente: revisor isolado (/revisor, sem escrita)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09
depends: 07-TASK-QA (revisa o que a QA aceitou, com as evidências do portão)
status: PENDENTE
gate: PENDENTE

## Goal
Parecer APPROVED ou CHANGES_REQUESTED contra os CA, os RNFs, o diff e as evidências. Atenção especial: compatibilidade
pt (RNF-02), replay misto pt/en (CA-08), interior do mandato intocado (D-20), nenhum `def` removido, prosa em pt.
NÃO escrever em nada além deste arquivo.

## Contexto
FEATURE.md (CA-01..CA-09, RNF-01..05), E2 (F1–F12), Handoff da 07-TASK-QA, diff da cópia de trabalho.

## Subtasks
1. Ler o diff inteiro contra os Arquivos permitidos de cada task.
2. Conferir cada CA e RNF com evidência (arquivo:linha ou saída).
3. Registrar achados (BLOQUEANTE/MENOR) e o parecer no Handoff.

## Invariants
- Revisor isolado: nenhuma escrita fora deste arquivo; nada de "corrigir de passagem".

## Scope IN / OUT
IN: revisar. OUT: corrigir, medir de novo.

## Arquivos permitidos
- `.claude/state/features/iter27/TASKS/08-TASK-REVIEW.md`

## AC
- Parecer emitido com evidência por CA e por RNF.

## DoD
- Handoff com o parecer e os achados; o tech-lead confere por `tech_lead.py snap`.

## Verificação
```bash
python3 .claude/tools/feature.py checklist iter27 && git diff --stat
```

## Handoff
