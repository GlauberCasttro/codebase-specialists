# 04-TASK-QA — Portão e oráculos, CA a CA

id: 04-TASK-QA
feature: iter22
tipo: QA
grupo: —
agente: QA
CA: CA-01, CA-02, CA-03, CA-04
depends: 02-TASK-GUARD-SHOW (guard corrigido), 03-TASK-VERSAO (versão e catálogo entram no portão)
status: PENDENTE
gate: PENDENTE

## Goal
Rodar o portão sobre a lista exata dos Arquivos permitidos das CORRECAO, com os oráculos iter22, iter16, iter18,
iter19, iter20 e iter21 inteiros, e conferir CA a CA. NÃO corrigir nada.

## Contexto
CA-01..CA-04. Fase de fechamento do `/e2e-loop`; portão em background.

## Subtasks
1. Lista dos arquivos das CORRECAO (02, 03).
2. `portao.sh` com os oráculos até `FIM`.
3. CA → evidência e veredito no FEATURE.md.

## Invariants
- Só lê; o resultado é o `portao.out`.

## Scope IN / OUT
IN: portão e oráculos. OUT: edição de produto.

## Arquivos permitidos
- `.claude/state/features/iter22/TASKS/04-TASK-QA.md`

## AC
- `portao.out` termina em `RESULTADO: VERDE` e `FIM`.

## DoD
- Aceite QA registrado no FEATURE.md; Handoff preenchido.

## Verificação
```bash
bash .claude/tools/portao.sh iter22 --lista local/iter22-arquivos.txt --oraculo campanhas/iter22/oraculo:test_iter22
```

## Handoff
