# 02-TASK-GUARD-PORTAS — fechar as portas do guard (harness indireto, hardlink, registros humanos, saída, inline, git)

id: 02-TASK-GUARD-PORTAS
feature: iter24
tipo: CORRECAO
grupo: G1
agente: corretor (papel; executor e model reais vão para o Handoff)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: IN_PROGRESS
gate: FAIL
complexidade: normal

## Goal
No bashscan/guard/hcore/auto: identificar chamada ao harness por `sh|bash <script>`, `python3 -m state|auto`, opções
com valor (`-W/-X`) e `cd .swarm/harness &&` e aplicar as regras do caminho direto; recusar `ln`/`cp -l` de protegido
e escrita em arquivo que é hardlink (nlink>1) de protegido; proteger os registros humanos (approvals.jsonl,
team-approvals.jsonl, acceptance.json5, run.json5, team.json5) contra Write/Edit/redirect do agente; modelar destinos
`--output=`, `-o`, `-O`, `-C`, `-d`; fail-closed para inline com flags combinadas e stdin; barrar git que desliga
proteção (core.hooksPath, --no-verify/-n), push protegido por refspec/-f/--delete/--mirror, branch -D/-f em protegida,
remote set-url|add, reflog expire. NÃO liberar troca de branch; NÃO bloquear leituras do dia a dia.

## Contexto
CA-01..CA-06. Âncoras: bashscan.py:16-32, :132, :202, :208-215, :299, :325; guard.py:177-183, :383-388;
hcore.py:830-836; auto.py:3045-3051.

## Subtasks
1. Rodar TestCA01..TestCA06 e ver falhar (RED).
2. Corrigir porta a porta, um teste de regressão em test_iter24_guard.py por porta, com controle do caminho legítimo.
3. Oráculo + suíte harness nos 2 Pythons (GREEN); oráculos iter16..iter22 intactos.

## Invariants
- Fail-closed preservado; nenhum `def` removido; varredura subcomandos × guard (iter22) segue verde.

## Scope IN / OUT
IN: guard e testes. OUT: versão/catálogo (03); troca de branch; falsos bloqueios do B-51.

## Arquivos permitidos
- `scripts/harness/engine/bashscan.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/engine/hcore.py`
- `scripts/harness/engine/auto.py`
- `scripts/harness/tests/test_iter24_guard.py`
- `scripts/harness/tests/test_guards.py` (founder, 2026-10-12, opção 1: a linha 57 contradizia o CA-03 — team.json5 passa a esperar 2 e `.swarm/knowledge/` prova a escrita do principal)

## AC
- TestCA01..TestCA06 verdes nos 2 Pythons; suíte harness sem regressão.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA01 test_iter24.TestCA02 test_iter24.TestCA03 test_iter24.TestCA04 test_iter24.TestCA05 test_iter24.TestCA06
```

## Handoff
- Executor: Claude Code · general-purpose · model sonnet (ciclo 1) + executor novo sonnet para o ajuste de test_guards.py:57 (decisão do founder, opção 1).
- Arquivos (cópia local/work/iter24): scripts/harness/engine/{bashscan,guard,hcore,auto}.py; scripts/harness/tests/test_iter24_guard.py (novo, 12 testes); scripts/harness/tests/test_guards.py (team.json5 espera 2; .swarm/knowledge/notas-da-ana.md espera 0).
- RED: oráculo CA01..06 19 testes, 11 falhas (exit 0 em vez de 2). GREEN: oráculo test_iter24 inteiro 22 OK em python3 e /usr/bin/python3.
- Régua completa (tech-lead, 17 suítes × 2 Pythons): VERDE; harness 384 OK (16 skips pré-existentes) nos 2.
- Escopo por snapshot: só arquivos permitidos; projeto vivo intocado pelo executor. Privacidade: 0 achados.
- Revisor: instância isolada general-purpose · opus · APPROVED, sem findings; ~40 variantes de bypass sondadas e recusadas. Independência: instâncias distintas.
- Limites: hardlink detectado só sob prefixos literais de `protected`/HUMAN_RECORDS; refspec cobre main/master e refs/heads/…; efeito colateral: subagente não cria branch nem `git config <k> <v>`. Script auxiliar do executor em local/work/iter24/run_or.sh (fora do produto).
