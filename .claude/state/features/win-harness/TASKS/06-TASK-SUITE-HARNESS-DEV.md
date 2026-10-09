# 06-TASK-SUITE-HARNESS-DEV — Suíte do harness verde no Windows nativo

id: 06-TASK-SUITE-HARNESS-DEV
feature: win-harness
tipo: CORRECAO
grupo: G3
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-13, CA-14
depends: 02-TASK-LANCADOR-HOOKS (os testes chamam os hooks e guards novos), 03-TASK-SCRIPTS-SHELL (testam carimbo, aprovação e install), 04-TASK-ESTADO-ENCODING (usam o bash_exe e o stdio UTF-8), 05-TASK-REGUA-PORTAO (testam portão e régua)
status: IN_PROGRESS
gate: PENDENTE
complexidade: normal

## Goal
As 13 chamadas `["bash"|"sh", …]` dos testes passam a usar o bash resolvido por `estado_lib.bash_exe()`; os helpers
`run()` passam `PYTHONUTF8=1` e decodificam UTF-8; o perfil temporário troca `HOME` e `USERPROFILE`; o teste de
symlink pula com motivo quando o Windows nega o privilégio (`WinError 1314`); testes novos para o que a feature
acrescentou (lançador, guard-git PowerShell, privacidade `C:\Users`, `e2e.py pythons`, `--qualidade`) entram na
régua permanente. NÃO enfraquecer asserção existente, NÃO remover teste, NÃO pular teste sem motivo declarado.

## Contexto
CA-13, CA-14. Âncoras: `test_harness_dev.py:111,138,177,242,244,349,471,499,504,542,551,567,591-594`;
`test_orquestracao.py:163,167`; `test_feature.py:62,275-277`. Medição de partida:
`local/criar-win-harness/harness-dev-nativo.out` (63/83 quebram). E2: F8, F10, F11; B-18 (7).

## Subtasks
1. Rodar a suíte no Windows sem atalho e confirmar o RED de partida (comparar com a medição da E2).
2. Helpers: bash resolvido, `PYTHONUTF8`, `USERPROFILE`; skip com motivo para symlink sem privilégio.
3. Testes permanentes para as mudanças das tasks 02–05 (incluindo `argv[0]` do `conferir_commit`).
4. Rodar a suíte no Windows sem atalho e no WSL, e o oráculo `-k CA13 -k CA14` (GREEN).

## Invariants
- Nenhuma asserção enfraquecida; nenhum teste removido; skip só com motivo (contado no Handoff).
- `test_harness_dev.py:591,594` continua exigindo o texto `python3 .claude/tools/…` nas skills.

## Scope IN / OUT
IN: as 3 suítes do harness. OUT: código dos tools (tasks 02–05), oráculos congelados.

## Arquivos permitidos
- `.claude/tools/tests/test_harness_dev.py`
- `.claude/tools/tests/test_feature.py`
- `.claude/tools/tests/test_orquestracao.py`

## AC
- Suíte harness-dev 0 falhas e 0 erros no Windows nativo sem atalho e no WSL; `-k CA13` e `-k CA14` verdes.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff com a contagem de testes e de skips.

## Verificação
```bash
python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA13 -k CA14
```

## Handoff
