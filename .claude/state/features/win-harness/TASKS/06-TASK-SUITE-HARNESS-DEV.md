# 06-TASK-SUITE-HARNESS-DEV — Suíte do harness verde no Windows nativo

id: 06-TASK-SUITE-HARNESS-DEV
feature: win-harness
tipo: CORRECAO
grupo: G3
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-13, CA-14
depends: 02-TASK-LANCADOR-HOOKS (os testes chamam os hooks e guards novos), 03-TASK-SCRIPTS-SHELL (testam carimbo, aprovação e install), 04-TASK-ESTADO-ENCODING (usam o bash_exe e o stdio UTF-8), 05-TASK-REGUA-PORTAO (testam portão e régua)
status: IN_PROGRESS
gate: FAIL
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
- Executor: general-purpose · sonnet (64 turnos), ciclo 1. Revisor isolado: general-purpose · sonnet, instância
  distinta → APPROVED. Independência: executor e revisor instâncias distintas.
- Arquivos: `test_harness_dev.py` (13 chamadas de shell pelo bash de `estado_lib.bash_exe()`; `run()` com
  `PYTHONUTF8=1`; escritas em LF; skip com motivo só no `WinError 1314` do symlink; caminhos normalizados; ScriptAprovacao
  confere o `.ps1` no Windows e o `.sh` no POSIX como hoje; novos LancadorPy 6, GuardGitPowerShell 4,
  PrivacidadeCaminhoWindows 2); `test_orquestracao.py` (bash resolvido no portão; UTF-8; novos ReguaPythons 7,
  CampanhaQualidade 3); `test_feature.py` (UTF-8, `HOME` + `USERPROFILE`; novos ConferirCommitArgv 3).
- Régua do tech-lead (cópia): Windows sem atalho harness-dev 108 OK (1 skip: symlink sem privilégio) — antes 20/83 no
  HEAD; oráculo win-harness INTEIRO no Windows 55 OK (5 skips só-POSIX) e no WSL 55 OK (17 skips só-Windows);
  win-bash e win-motor-copia (cópia) OK; WSL harness-dev 108/108 em python3 e /usr/bin/python3. Nenhum `def` removido;
  `self.assert` HEAD→cópia 134→165, 51→59, 32→48; privacidade 0; escopo só nos 3 testes.
- Ressalvas (MENOR, revisor): fallback `BASH="bash"` em `ImportError` do `estado_lib` (para o clone parcial do oráculo
  win-motor-copia) poderia usar o bash do WSL num Windows sem `estado_lib`; `CampanhaQualidade` só assere rc ≠ 0 sem
  checar a mensagem de `--qualidade`; o `.ps1` no teste não passa por parser (o tech-lead conferiu o parse no PS 5.1 na
  task 03). Candidatos ao BACKLOG (PRÉ-EXISTENTE do tool, contornados nos testes): `portao.sh --pythons` com caminho com
  espaço; `copia.sh`/`tar` com `CS_DEV_SKILL_DIR` em barra invertida.
