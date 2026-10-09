# 02-TASK-LANCADOR-HOOKS — Lançador de Python e hooks que falham fechados

id: 02-TASK-LANCADOR-HOOKS
feature: win-harness
tipo: CORRECAO
grupo: G1
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-01, CA-02, CA-03, CA-04
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: DONE
gate: PASS
complexidade: normal

## Goal
Criar `.claude/tools/_py.sh` (resolve `CS_DEV_PY` → `python3` → `python` → `py`, exporta `PYTHONUTF8=1`; em modo
hook sem interpretador sai 2 com motivo) e passar por ele os 4 hooks Python do `settings.json`, o guard-git, o
guard de privacidade e o pre-commit; `_comum.sh` usa a mesma resolução (absorvendo o `PY` sujo). Guard-git passa a
cobrir a ferramenta PowerShell (matcher e análise do comando); guard de privacidade passa a reconhecer
`C:\Users\<nome>\`; os 4 tools Python fora do `estado_lib` (guard-entrega, exige-modelo, guard_git,
guard_privacidade) reconfiguram stdin/stdout/stderr para UTF-8. NÃO mexer em `.claude/tools/ac/**`, NÃO mudar a
decisão de nenhum guard no macOS/Linux, NÃO chamar `git` no lançador.

## Contexto
CA-01, CA-02, CA-03, CA-04. Âncoras: `.claude/settings.json:5,19,29,39,49`; `guard-git.sh:6-10` (`ask` sem python3);
`guard_git.py:144` (só `Bash`); `guard_privacidade.py:32-33` (só `/`); `pre-commit.sh:9,11`;
`guard-privacidade.sh:6-7`; `_comum.sh:16-17` (sujo, F15). E2: F1, F2, F4, F7, F15.

## Subtasks
1. Rodar o oráculo congelado `-k CA01`, `-k CA02`, `-k CA03` e `-k CA04` e ver falharem (RED).
2. `_py.sh` + `settings.json` (4 hooks Python pelo lançador; matcher do guard-git `Bash|PowerShell`); `.sh` dos
   guards e o pre-commit pelo lançador; `_comum.sh` reaproveita a resolução.
3. `guard_git.py`: comando PowerShell (`;`, `|`, `&`, `git.exe`, string não é chamada); `guard_privacidade.py`:
   padrão `[A-Za-z]:\\+Users\\+<nome>\\` com os mesmos placeholders; stdio UTF-8 nos 4 tools.
4. Rodar o oráculo (`-k CA01`..`-k CA04` na parte destes arquivos) e a suíte harness-dev (GREEN, sem falha nova).

## Invariants
- Hook sem interpretador nega (exit 2); nunca 127 nem 0.
- No macOS/Linux o lançador escolhe `python3`, o mesmo de hoje; as decisões dos guards não mudam.
- Nenhum `def` existente some. O `settings.json` continua JSON válido com as 6 entradas.

## Scope IN / OUT
IN: lançador, hooks, guards, pre-commit, `_comum.sh` (resolução do Python). OUT: motor `ac/`, tools que importam
`estado_lib` (task 04), régua (task 05), testes da suíte (task 06).

## Arquivos permitidos
- `.claude/tools/_py.sh`
- `.claude/settings.json`
- `.claude/tools/_comum.sh`
- `.claude/tools/guard-git.sh`
- `.claude/tools/guard_git.py`
- `.claude/tools/guard-privacidade.sh`
- `.claude/tools/guard_privacidade.py`
- `.claude/tools/pre-commit.sh`
- `.claude/tools/guard-entrega.py`
- `.claude/tools/exige-modelo.py`

## AC
- `-k CA01`, `-k CA02` e `-k CA03` verdes; `-k CA04` verde para os 4 tools desta task.
- Suíte harness-dev sem falha nova no WSL.

## DoD
- Régua seletiva (e2e-loop) verde; diff só nos arquivos permitidos; Handoff preenchido (RED → GREEN por CA).

## Verificação
```bash
python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA01 -k CA02 -k CA03
```

## Handoff
- Executores: ciclo 1 general-purpose · sonnet (11 turnos); ciclo 2 general-purpose · opus, instância nova (CS_DEV_PY
  validado, modo executado por `$0`, padrão WindowsApps). Revisores isolados (opus, área sensível): ciclo 1 →
  CHANGES_REQUESTED (BLOQUEANTE·REGRESSÃO·CONFIRMADO: `CS_DEV_PY` inválido ⇒ hooks saíam 127 = falha aberta; MENOR:
  `_PY_SOURCED` herdado desligava o lançador; padrão `\WindowsApps\` morto); ciclo 2, instância nova → APPROVED.
  Independência: executor e revisor sempre instâncias distintas.
- Arquivos: `_py.sh` (novo: `CS_DEV_PY` validado → `python3` → `python` → `py`, ignora stub WindowsApps,
  `PYTHONUTF8=1`, `--hook` sem interpretador sai 2 com motivo; incluído com `.` só define `cs_resolver_py`);
  `settings.json` (4 hooks via `sh _py.sh --hook`; matcher guard-git `Bash|PowerShell`); `_comum.sh` (PY por
  `cs_resolver_py`; absorve o PY sujo F15); `guard-git.sh` (sem Python nega, não `ask`); `guard_git.py` (modo
  PowerShell: `;`/`|`/`&`, `git.exe`, `-Command` recursivo, string não é chamada; stdio UTF-8);
  `guard-privacidade.sh`, `pre-commit.sh` (via lançador); `guard_privacidade.py` (`[A-Za-z]:\+Users\+<nome>\+`,
  mesmos placeholders; stdio UTF-8); `guard-entrega.py`, `exige-modelo.py` (stdio UTF-8).
- Régua do tech-lead (cópia, ciclo 2): oráculo win-harness Windows sem atalho `-k CA01..05,07,11` 32 OK;
  harness-dev WSL 83/83 em python3 e /usr/bin/python3; CA-14 WSL 3 OK; F1/F2 reproduzidos à mão (rc 2 / deny);
  escopo por snapshot só nos 10 permitidos; privacidade 0; RNF-02 diferencial do revisor: 432 comandos Bash HEAD ×
  cópia, nenhum negado passou a passar (30 diferenças, todas mais estritas).
- Ressalvas (MENOR·PRÉ-EXISTENTE, candidatos ao BACKLOG, não adicionados): PowerShell `{ git push }`, `$x = git push`,
  `` g`it push ``, `iex`, `Start-Process git`, `cmd /c git push`, `-EncodedCommand` passam (mesma classe que `{ git push; }`
  no Bash no HEAD). Limite: `CS_DEV_PY` apontando para executável que não é Python faz o hook sair 0/1.
- Processo: o executor do ciclo 1 rodou um `git diff --stat` só leitura e usou `/tmp` (proibidos pelo prompt; nada gravado no projeto).
