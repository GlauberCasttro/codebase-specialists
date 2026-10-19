# 07-TASK-QA — QA da iter27: portão completo e matriz CA a CA

id: 07-TASK-QA
feature: iter27
tipo: QA
grupo: —
agente: qa (papel; o portão longo roda sob o tech-lead com caffeinate -i, nunca dentro de subagente — B-70)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09
depends: 02-TASK-FLAGS-EN (código a medir), 03-TASK-MEMORIA-EN (código a medir), 04-TASK-INCLUDE-EMITTED (código a medir), 05-TASK-TEXTOS-EN (textos a medir), 06-TASK-VERSAO (a versão que o portão confere)
status: PENDENTE
gate: PENDENTE

## Goal
Provar o critério de parada: oráculo iter27 100% nos 2 Pythons, oráculos iter13, iter16, iter18..iter26 inteiros
verdes, iter10/iter15 sem regressão contra o HEAD (D-35), suítes do produto e harness-dev verdes, 0 `def` removido,
VERSION 0.15.0. Emitir ACCEPT ou REJECT com a matriz CA a CA. NÃO corrigir código (devolve à task dona), NÃO mudar
oráculo.

## Contexto
Todos os CA. Portão: `bash .claude/tools/portao.sh iter27 --oraculo campanhas/iter27/oraculo:test_iter27 … --lista
<arquivos da feature>`; saída em `local/portao-iter27/portao.out`. Lições: B-70a (caffeinate, sob o tech-lead),
B-70b (falha instável quando a máquina dorme: reexecutar antes de concluir).

## Subtasks
1. Montar a lista de arquivos da feature (união dos Arquivos permitidos das CORRECAO que mudaram).
2. Rodar o portão completo (tech-lead, background, caffeinate) e ler `RESULTADO:`/`FIM`.
3. Comparar iter10/iter15 contra o HEAD (D-35) e preencher a matriz CA a CA no Handoff.

## Invariants
- `oracle verify` intacto; nenhum arquivo fora da lista entra.

## Scope IN / OUT
IN: medir. OUT: corrigir.

## Arquivos permitidos
- `.claude/state/features/iter27/TASKS/07-TASK-QA.md`

## AC
- Portão VERDE com FIM; matriz CA-01..CA-09 PASS; D-35 sem regressão.

## DoD
- Handoff com a matriz, o caminho do portao.out e o veredito ACCEPT/REJECT.

## Verificação
```bash
tail -5 local/portao-iter27/portao.out && python3 .claude/tools/ac/ac.py --work campanhas/iter27 oracle verify
```

## Handoff
