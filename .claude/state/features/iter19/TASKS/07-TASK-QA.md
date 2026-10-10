# 07-TASK-QA — Portão e oráculo, CA a CA

id: 07-TASK-QA
feature: iter19
tipo: QA
grupo: —
agente: QA
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06
depends: 05-TASK-UPGRADE (última correção do motor/upgrade), 06-TASK-VERSAO-DOCS (versão e docs entram no portão)
status: PENDENTE
gate: PENDENTE

## Goal
Rodar o portão da feature sobre a lista exata dos Arquivos permitidos das CORRECAO, com os oráculos iter19, iter16,
iter18 (R1–R7) e iter20, e conferir CA a CA. NÃO corrigir nada; achado vira retorno à task dona.

## Contexto
CA-01..CA-06. Fase de fechamento do `/e2e-loop`; portão em background.

## Subtasks
1. Montar a lista dos arquivos das CORRECAO (02–06).
2. Rodar `portao.sh` com os oráculos até `FIM`.
3. Registrar CA → evidência e o veredito ACCEPT/REJECT no FEATURE.md.

## Invariants
- Só lê; o resultado é o `portao.out`, não opinião.

## Scope IN / OUT
IN: portão e oráculos. OUT: qualquer edição de produto.

## Arquivos permitidos
- `.claude/state/features/iter19/TASKS/07-TASK-QA.md`

## AC
- `portao.out` termina em `RESULTADO: VERDE` e `FIM`.

## DoD
- Aceite QA registrado no FEATURE.md; Handoff preenchido.

## Verificação
```bash
bash .claude/tools/portao.sh iter19 --lista local/iter19-arquivos.txt --oraculo campanhas/iter19/oraculo:test_iter19
```

## Handoff
