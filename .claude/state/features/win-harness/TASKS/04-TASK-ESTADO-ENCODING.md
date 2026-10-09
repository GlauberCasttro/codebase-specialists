# 04-TASK-ESTADO-ENCODING — stdio UTF-8, gravação em LF, bash_exe e perfil temporário

id: 04-TASK-ESTADO-ENCODING
feature: win-harness
tipo: CORRECAO
grupo: G2
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-04, CA-05, CA-07, CA-11
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: DONE
gate: PASS
complexidade: normal

## Goal
`estado_lib.py` reconfigura stdin/stdout/stderr para UTF-8 ao ser importado (cobre os 9 tools que o importam),
grava com `newline="\n"` em `gravar`/`apensar` e passa a ter `bash_exe()` (descartando `System32` e o alias
`WindowsApps\bash.exe`); `feature.py` usa o `bash_exe` do `estado_lib` e mantém o nome `feature.bash_exe`;
`publicar_regras.py` grava em LF e com stdio UTF-8; `package_validar.py` troca `HOME` e `USERPROFILE` e usa stdio
UTF-8; `.gitattributes` ganha `.claude/** text=auto eol=lf` e `campanhas/** text=auto eol=lf`. NÃO mudar o formato
de nenhum arquivo de estado além do fim de linha, NÃO remover `feature.bash_exe` (o oráculo da win-bash o usa).

## Contexto
CA-04, CA-05, CA-07, CA-11. Âncoras: `estado_lib.py:115,122`; `feature.py:544-575,583`; `publicar_regras.py:161,179`;
`package_validar.py:82`; `.gitattributes:1`. E2: F4, F5, F6, F10, F13; B-18 (6) e (7).

## Subtasks
1. Rodar o oráculo `-k CA04 -k CA05 -k CA07 -k CA11` e ver falharem (RED).
2. `estado_lib.py`: stdio UTF-8, `newline="\n"`, `bash_exe()` com o descarte do `WindowsApps`; `feature.py` delega.
3. `publicar_regras.py`, `package_validar.py` e `.gitattributes`.
4. Rodar o oráculo desta task, os oráculos `win-bash` e `win-motor-copia` e a suíte harness-dev (GREEN).

## Invariants
- O oráculo congelado da win-bash continua verde (`feature.bash_exe`, `feature.conferir_commit`, `feature.Recusa`).
- Fora do Windows, `bash_exe()` devolve `"bash"`. Nenhum `def` existente some.

## Scope IN / OUT
IN: módulo comum, `feature.py` (só o bash), publicar/validar pacote, `.gitattributes`. OUT: hooks e guards (task
02), régua e `campanha.py` (task 05), testes da suíte (task 06).

## Arquivos permitidos
- `.claude/tools/estado_lib.py`
- `.claude/tools/feature.py`
- `.claude/tools/publicar_regras.py`
- `.claude/tools/package_validar.py`
- `.gitattributes`

## AC
- `-k CA04` (parte dos tools desta task), `-k CA05`, `-k CA07` e `-k CA11` verdes; oráculos anteriores verdes.

## DoD
- Régua seletiva verde; diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA04 -k CA05 -k CA07 -k CA11
```

## Handoff
- Executores: ciclo 1 general-purpose · sonnet (20 turnos); ciclo 2 general-purpose · opus, instância nova (12
  turnos). Revisores isolados: ciclo 1 sonnet → CHANGES_REQUESTED (1 BLOQUEANTE·REGRESSÃO·CONFIRMADO: `def dentro_sys32`
  removido de `feature.py`, o portão reprovaria); ciclo 2 sonnet, instância nova → APPROVED, sem findings.
  Independência: executor e revisor sempre instâncias distintas.
- Arquivos: `estado_lib.py` (`_stdio_utf8()` no import; `gravar`/`apensar` com `newline="\n"`; `BashAusente`,
  `bash_descartado(p)` = System32 + `WindowsApps`, `bash_exe()`); `feature.py` (`bash_exe` delega e converte em
  `Recusa`; `dentro_sys32(p)` no módulo, delegando a `bash_descartado`); `publicar_regras.py` (stdio UTF-8, LF);
  `package_validar.py` (stdio UTF-8, `HOME` + `USERPROFILE`); `.gitattributes` (`.claude/**` e `campanhas/**`
  `text=auto eol=lf`).
- Régua do tech-lead (cópia): oráculo win-harness no Windows sem atalho `-k CA01..05,07,11` 32 OK (ciclo 1) e
  `-k CA05 -k CA07 -k CA11` OK (ciclo 2); win-bash (cópia) 18 OK; harness-dev WSL 83/83 em python3 e /usr/bin/python3;
  CA-14 no WSL 3 OK (com ORACULO_FONTE_AC); conferência de `def` do portão vazia nos 4 .py; privacidade 0; escopo por
  snapshot só nos 5 permitidos (+ ruído `evals/**/obj/` do IDE, fora da feature).
- Limites: CA-04 completo depende também dos tools da task 02 (verde no ciclo 1 com as duas); harness-dev no Windows
  nativo fica com a task 06; `dentro_sys32` agora descarta também o alias WindowsApps (mesma regra do `estado_lib`).
