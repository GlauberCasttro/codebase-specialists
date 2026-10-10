# 14-TASK-REVIEW — Revisão isolada da feature

id: 14-TASK-REVIEW
feature: harness-evolucao
tipo: REVIEW
grupo: —
agente: revisor isolado (/revisor, sem escrita)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09, CA-10, CA-11, CA-12, CA-13, CA-14, CA-15, CA-16, CA-17, CA-18, CA-19
depends: 13-TASK-QA (revisa sobre o portão verde e a matriz da QA)
status: PENDENTE
gate: PENDENTE

## Goal
Revisar o diff da cópia de trabalho contra o HEAD, os 19 CAs, o oráculo congelado e as evidências da QA; atenção a:
guard que passou a deixar passar algo (falha aberta), segredo que escapa da redação, fechamento automático sem
evento ou sem aceite, migração que perde dado ou quebra a cadeia de hash, regressão no board legado, asserção
enfraquecida, `def` removido e termo privado. Veredito APPROVED ou CHANGES_REQUESTED. NÃO alterar nenhum arquivo.

## Contexto
FEATURE.md (19 CAs, RNF-01..05, decisões da E1), Handoffs das tasks 02–12 e da 13, `portao.out` dos dois ambientes,
`local/levantamento-evolucao-harness/` (achados de origem).

## Subtasks
1. Ler o diff por grupo (G1 memória, G2 árvore, G3 JSON) contra os CAs.
2. Reexecutar o oráculo e checar os pontos de atenção acima com comando.
3. Emitir matriz CA → evidência, findings classificados e veredito.

## Invariants
- Sem escrita; todo finding com arquivo:linha ou comando.

## Scope IN / OUT
IN: revisão. OUT: correção (volta ao corretor).

## Arquivos permitidos
- `.claude/state/features/harness-evolucao/TASKS/14-TASK-REVIEW.md`

## AC
- Veredito com matriz dos 19 CAs e findings classificados (BLOQUEANTE/MENOR · REGRESSÃO/PRÉ-EXISTENTE).

## DoD
- Handoff com o parecer; Aceite Review proposto.

## Verificação
```bash
python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -v
```

## Handoff
