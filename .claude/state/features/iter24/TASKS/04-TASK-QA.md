# 04-TASK-QA — Portão e oráculos, CA a CA

id: 04-TASK-QA
feature: iter24
tipo: QA
grupo: —
agente: QA
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07
depends: 02-TASK-GUARD-PORTAS (guard corrigido), 03-TASK-VERSAO (versão e catálogo entram no portão)
status: DONE
gate: PASS

## Goal
Rodar o portão sobre a lista exata dos Arquivos permitidos das CORRECAO, com os oráculos iter24, iter16, iter18,
iter19, iter20, iter21 e iter22 inteiros, e conferir CA a CA. NÃO corrigir nada.

## Contexto
CA-01..CA-07. Fase de fechamento do `/e2e-loop`; portão em background.

## Subtasks
1. Lista dos arquivos das CORRECAO (02, 03).
2. `portao.sh` com os oráculos até `FIM`.
3. CA → evidência e veredito no FEATURE.md.

## Invariants
- Só lê; o resultado é o `portao.out`.

## Scope IN / OUT
IN: portão e oráculos. OUT: edição de produto.

## Arquivos permitidos
- `.claude/state/features/iter24/TASKS/04-TASK-QA.md`

## AC
- `portao.out` termina em `RESULTADO: VERDE` e `FIM`.

## DoD
- Aceite QA registrado no FEATURE.md; Handoff preenchido.

## Verificação
```bash
bash .claude/tools/portao.sh iter24 --lista local/iter24-arquivos.txt --oraculo campanhas/iter24/oraculo:test_iter24
```

## Handoff
- QA: Claude Code · general-purpose · model sonnet · ACCEPT. Não escreveu (snapshot da cópia e do vivo).
- Portão: local/portao-iter24/portao.out → RESULTADO: VERDE, FIM; 17 suítes × 2 Pythons; oráculos iter24 (22), iter16 (48), iter18 (38), iter19 (39), iter20 (24), iter21 (64), iter22 (9) OK nos 2.
- oracle verify: intacto. Matriz CA-01..CA-07 PASS no FEATURE.md (Aceite QA).
- Limites: o portão mede suítes/oráculos/def, não uso real; matriz por teste vem de execução -v em python3.
