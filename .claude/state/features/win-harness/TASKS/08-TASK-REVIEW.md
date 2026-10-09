# 08-TASK-REVIEW — Revisão isolada da feature

id: 08-TASK-REVIEW
feature: win-harness
tipo: REVIEW
grupo: —
agente: revisor isolado (/revisor, sem escrita)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14
depends: 07-TASK-QA (revisa sobre o portão verde e a matriz da QA)
status: PENDENTE
gate: PENDENTE

## Goal
Revisar o diff da cópia de trabalho contra o HEAD, os 14 CAs, o oráculo congelado e as evidências da QA; atenção a
guard que passou a deixar passar algo (falha aberta), mudança de comportamento fora do Windows, asserção
enfraquecida e termo privado. Veredito APPROVED ou CHANGES_REQUESTED. NÃO alterar nenhum arquivo.

## Contexto
FEATURE.md (14 CAs, RNF-02 falha fechada), Handoffs das tasks 02–06 e da 07, `portao.out` dos dois ambientes.

## Subtasks
1. Matriz CA → evidência (comando executado, não alegado).
2. Findings classificados (BLOQUEANTE/MENOR · REGRESSÃO/PRÉ-EXISTENTE · CONFIRMADO/SUSPEITA).
3. Veredito.

## Invariants
- Só leitura; cada finding com `arquivo:linha` e como reproduzir.

## Scope IN / OUT
IN: diff, oráculo, evidências. OUT: corrigir (volta ao corretor pelo tech-lead).

## Arquivos permitidos
- `.claude/state/features/win-harness/TASKS/08-TASK-REVIEW.md`

## AC
- Veredito registrado com a matriz e os findings; nenhum BLOQUEANTE aberto para APPROVED.

## DoD
- Handoff com o veredito; Aceite Review proposto.

## Verificação
```bash
python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -v
```

## Handoff
