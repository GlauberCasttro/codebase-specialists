# HISTORICO — feature win-harness

<!-- APPEND-ONLY: [NOTA] | [PASS] | [REJECT]; escrito pelo feature.py e pelo tech-lead, em série -->

## [NOTA] 2026-10-09T11:34:49-0300 — Abertura da feature win-harness
- campanha: campanhas/win-harness (ac.py init; escopo: .claude/settings.json, .claude/CLAUDE.md, .claude/skills/e2e-loop/SKILL.md, .claude/tools/_py.sh, .claude/tools/_comum.sh, .claude/tools/guard-git.sh, .claude/tools/guard_git.py, .claude/tools/guard-privacidade.sh, .claude/tools/guard_privacidade.py, .claude/tools/pre-commit.sh, .claude/tools/guard-entrega.py, .claude/tools/exige-modelo.py, .claude/tools/carimbo.sh, .claude/tools/script-aprovacao.sh, .claude/tools/instalar.sh, .claude/tools/package.sh, .claude/tools/package_validar.py, .claude/tools/publicar_regras.py, .claude/tools/estado_lib.py, .claude/tools/feature.py, .claude/tools/e2e.py, .claude/tools/regua.json, .claude/tools/portao.sh, .claude/tools/campanha.py, .claude/tools/tests/test_harness_dev.py, .claude/tools/tests/test_feature.py, .claude/tools/tests/test_orquestracao.py, .gitattributes)
- tasks: 8 · primeira: 01-TASK-ORACULO
- investigação aprovada (E2):

    # E2 — Investigação medida
    
    Máquina: Windows 11, Git Bash 5.3, Python 3.12.7 só como `python` (`C:\Program Files\Python312`), sem
    `/usr/bin/python3`, `core.autocrlf=input` (do `.git/config`), WSL presente. "Sem o atalho" = PATH sem `~/bin` e sem
    `PYTHONUTF8`, o mesmo ambiente de um hook ou de um `subprocess` do Python.
    
    ## Inventário
    - **Suíte harness-dev no Python nativo, sem o atalho** (`cd .claude/tools && python.exe -m unittest discover -s
      tests`, saída em `local/criar-win-harness/harness-dev-nativo.out`): `Ran 83 tests` · `FAILED (failures=33,
      errors=30)` — 63 de 83 quebram (20 passam). No WSL a mesma suíte passa (portão da win-motor-copia:
      `harness-dev: Ran 76 tests … OK`, antes dos 7 testes da win-bash).
    - **Causas das 63** (contagem das linhas de erro na saída): ~30 `UnicodeDecodeError` (saída cp1252 lida como utf-8:
      bytes 0x97, 0xe1, 0xb7…); 16 `/bin/bash: C:Users…: No such file or directory` (subprocess `["bash",…]` cai no WSL:
      copia.sh 12, carimbo.sh 4); 1 `wsl: Failed to start the systemd user session`; 1
      `guard-privacidade.sh: line 7: exec: python3: not found`; 2 `'ask' != 'deny'` (guard-git sem python3 pede em vez
      de negar); 1 `OSError: [WinError 1314] O cliente não tem o privilégio necessário` (os.symlink); o resto assertivas
      em cadeia das anteriores.
    - **`python3` no `.claude/`** (sem `ac/`, `state/`, `package/`): 193 ocorrências — 126 em 23 `.md` (skills e
      referências), 30 em `.sh`, 24 em `.py` de tools, 6 nos testes, 7 em `.json`. Em código (`.sh`/`.py`/`.json`, sem
      testes): 57 linhas.
    - **Encoding (cp1252)**: `python.exe <tool> --help` com saída em pipe, sem `PYTHONUTF8`: 11 de 17 tools caem com
      `UnicodeEncodeError` (campanha, custo, e2e, feature, guard-entrega, package_validar, publicar_regras, rh, sessao,
      tech_lead — `→ ⇒ ← ≥`); 6 passam (contrato, estado_lib, exige-modelo, guard-estado, guard_git,
      guard_privacidade). Nenhum tool chama `sys.stdout.reconfigure` (`grep -l reconfigure` = 0). `sessao.py briefing`
      sem `PYTHONUTF8` imprime acentos trocados por `�`.
    - **Shell pelo nome**: 0 nos tools (a `feature.py` já usa `bash_exe()`); 13 nos testes — `test_harness_dev.py`
      :138,:177,:242,:244 (`sh`), :349,:471,:504,:542,:551,:567 (`bash`), :499 (`sh -n`); `test_orquestracao.py`
      :163,:167 (`bash`).
    - **Escrita em modo texto sem `newline=`**: 4 — `estado_lib.py:115` (`gravar`), `:122` (`apensar`),
      `publicar_regras.py:161,179`; `grep -c 'newline='` = 0 em todos os tools.
    - **Fim de linha no disco** (`git ls-files --eol`): 627 `w/lf`, 7 `w/crlf`, 1 `w/mixed`, 22 `w/none`; os 8 CRLF/misto
      são todos gravados pelo harness (`features.json`, `RESUME.md`, `LAST_DELIVERY.md`, `logs/custo.jsonl`,
      `logs/sessoes.jsonl`, 2 archives, `campanhas/README.md`). `.claude/tools/**`: 45 `w/lf`, 0 CRLF.
    - **Hooks** (`.claude/settings.json`): 6 entradas; 4 com `python3 …` (:19 hook_aprovacao, :29 guard-entrega,
      :39 guard-estado, :49 exige-modelo); 1 `sh guard-git.sh` só com matcher `Bash` (:5); 1 `bash carimbo.sh`.
    - **Caminhos/HOME**: `package_validar.py:82` e `test_feature.py:62` trocam só `HOME`; `custo.py:39`,
      `guard-entrega.py:68`, `guard-estado.py:74` usam `expanduser` (no Windows lê `USERPROFILE`).
    - **Symlink**: `instalar.sh:88` (`ln -s`), `_comum.sh:65` (`readlink`), `test_harness_dev.py:111` (`os.symlink`).
    
    ## Classificação
    - **57 linhas de código com `python3`**: muda 22 · não muda 35 (soma 57).
      - muda (executam `python3`): `settings.json` :19,:29,:39,:49 (4); `regua.json:3` (1); `carimbo.sh` :15,:37,:51,:78
        (4); `guard-git.sh` :6,:7,:10 (3); `guard-privacidade.sh` :6,:7 (2); `pre-commit.sh` :9,:11 (2);
        `script-aprovacao.sh` :30,:38,:39,:40 (4); `portao.sh:24` (1); `_comum.sh:81` (1).
      - não muda: 15 shebangs `#!/usr/bin/env python3` (inertes no Windows: os tools são chamados como
        `<py> arquivo.py`); 20 linhas de texto/ajuda/mensagem (`--help`, docstrings, `campanha.py:32`, `contrato.py:250,282`,
        `personas.json`, `evals.json`, `_comum.sh:16-17` — o `PY` já com fallback, sujo).
    - **126 menções em `.md`**: não muda (instrução ao agente; sem `python3` falha ALTO com "command not found", não em
      silêncio; `test_harness_dev.py:591,594` exige o texto). O que muda é o harness dizer qual Python usar (F9).
    - **Encoding**: muda 11 tools (+ os que imprimem pelos módulos comuns) · não muda 6 (já passam).
    - **Shell pelo nome nos testes**: muda 13 (soma 13).
    - **Escrita em texto**: muda 4 (soma 4). Os 8 arquivos CRLF já no disco: renormalizar 8.
    - **Hooks**: muda 5 (4 `python3` + matcher do guard-git) · não muda 1 (`bash carimbo.sh`: o Claude Code no Windows
      roda o hook pelo Git Bash) — soma 6.
    - **Congelado**: `.claude/tools/ac/**` (cópia do motor, `ac/ORIGEM.txt`); oráculos `campanhas/*/oraculo/`.
    
    ## Exclusões
    - `.claude/tools/ac/` — motor embutido (cópia; B-18 (1)(2) vão ao `auto-correcao`).
    - `.claude/package/`, `scripts/`, `SKILL.md`, `references/`, `docs/`, `evals/` — produto (B-14). As suítes do produto
      no Windows nativo não foram medidas aqui (B-14 e B-17/`make`).
    - `.claude/state/` — dados; só entram os 8 arquivos com CRLF (renormalização) e a regra de gravação.
    - Hooks rodados pela ferramenta PowerShell do Claude Code: medido só o matcher no `settings.json`; o PATH real que o
      Claude Code passa aos hooks no Windows **não foi medido** (vai como CA com prova: hook rodado sem `python3` no PATH).
    - B-18 (5) (guard de privacidade no `feature.py criar propor` e no `oracle freeze`): não é Windows; fica no BACKLOG.
    - macOS/Linux: não medidos nesta máquina; a garantia é a régua no WSL (`python3` + `/usr/bin/python3`).
    
    ## Achados
    - F1 — `.claude/settings.json:19,29,39,49` — os 4 hooks Python chamam `python3`; sem ele saem 127 e o Claude Code
      segue (falha ABERTA): guard-entrega, guard-estado, hook de aprovação e exige-modelo deixam de guardar.
    - F2 — `.claude/settings.json:5` — `guard-git.sh` só no matcher `Bash`: `git push`/`reset --hard` pela ferramenta
      PowerShell não passam por ele (B-18 (3)). E `guard-git.sh:7-8` sem `python3` devolve `ask`, não `deny` (medido:
      2 testes `'ask' != 'deny'`).
    - F3 — `.claude/tools/regua.json:3` e `portao.sh:24` — `["python3", "/usr/bin/python3"]` fixos: no Windows nativo
      `/usr/bin/python3` não existe ⇒ `NOT_RUN` ⇒ régua/portão nunca VERDE; o portão das features do Windows rodou no
      WSL (`portao.out`: `Python 3.10.12` nas duas passadas).
    - F4 — 11 de 17 tools (`feature.py`, `sessao.py`, `e2e.py`, `tech_lead.py` …) — `UnicodeEncodeError` no `--help`
      com stdout em pipe (cp1252); nenhum faz `reconfigure`. Nos testes, ~30 `UnicodeDecodeError` ao ler a saída.
    - F5 — `.claude/tools/estado_lib.py:115,122` — `gravar`/`apensar` em modo texto sem `newline="\n"`: no Windows
      gravam CRLF ⇒ os 8 arquivos `w/crlf`/`w/mixed` medidos; `sessao.py` calcula o ESTADO por bytes (carimbo muda só
      pelo fim de linha). Mesmo em `publicar_regras.py:161,179`.
    - F6 — `.gitattributes:1` — só `.claude/tools/ac/** text eol=lf`; `.claude/**` e `campanhas/**` sem regra.
    - F7 — `.claude/tools/guard_privacidade.py:32-33` — padrões de caminho pessoal só com `/` (`/Users/…`, `/home/…`):
      medido num arquivo com `C:\Users\x\proj` ⇒ `0 achado(s)`; as formas com barra normal (drive + `/Users/x/` e `/c/Users/x`) são pegas.
      O repositório é público.
    - F8 — `.claude/tools/tests/test_harness_dev.py` (13 chamadas `["bash"|"sh",…]`, listadas no Inventário) — no
      Windows o `bash` do PATH do Python é o do WSL: 16 falhas `/bin/bash: C:Users…`. A régua do harness não roda no
      Windows nativo.
    - F9 — 126 menções de `python3` em 23 `.md` — instrução ao agente; nesta máquina só funcionam pelo atalho
      `~/bin/python3`. Sem ele, falham alto. Falta o harness anunciar o interpretador (o SessionStart `carimbo.sh` é o
      ponto natural).
    - F10 — `.claude/tools/package_validar.py:82` e `test_feature.py:62` — trocam só `HOME`; no Windows o
      `expanduser("~")` lê `USERPROFILE` ⇒ a validação do pacote e os testes leem o perfil real.
    - F11 — `.claude/tools/instalar.sh:88` (`ln -s`) e `test_harness_dev.py:111` (`os.symlink`) — sem Modo Desenvolvedor:
      `WinError 1314` (medido no teste); no MSYS o `ln -s` copia em vez de linkar (inferido, não medido).
    - F12 — `.claude/tools/carimbo.sh:40-41` — conta etapas por `grep '^ ✓'` sobre a saída do `ac.py status`; com saída
      cp1252 a contagem cai (B-18 (4)).
    - F13 — `.claude/tools/feature.py:556-558` — `bash_exe()` descarta só `System32`; o alias do WSL em
      `%LOCALAPPDATA%\Microsoft\WindowsApps\bash.exe` passaria se viesse antes no PATH (B-18 (6)). E
      `test_feature.py:275-277` só testa a Recusa com mock: nenhum teste prova que `conferir_commit` usa o `argv[0]` de
      `bash_exe()` (B-18 (7)).
    - F14 — `.claude/tools/campanha.py:123-125` — `run record` sem nota de qualidade antes de `done remedicao` (o motor
      recusa) (B-18 (8)).
    - F15 — `.claude/tools/_comum.sh:16-17` e `package.sh:24` (alterações sujas, fora de feature) — `PY` com fallback
      para `python` + `PYTHONUTF8=1`: direção certa para os `.sh`, sem teste. Entram como ponto de partida.
    - F16 (DESCARTADO por medição) — suspeita da auditoria de que `core.autocrlf=true` converte o checkout: o repo tem
      `core.autocrlf=input` (`.git/config`) e 627 arquivos `w/lf`; o CRLF vem da gravação do Python (F5), não do git.
    - F17 (DESCARTADO por medição) — suspeita de `e2e.py:128-133` cair com `FileNotFoundError`: hoje confere
      `shutil.which(py)` antes e marca `NOT_RUN`.
    
    ## Enforcement existente
    - Suíte `harness-dev` (`.claude/tools/tests/`, 83 testes): cobre guards, carimbo, portão, portar, package — mas só
      roda verde no WSL/macOS; no Windows nativo 63/83 quebram (o próprio enforcement não roda aqui).
    - Oráculos `campanhas/win-bash/oraculo/test_win_bash.py` (bash_exe/conferir_commit) e
      `campanhas/win-motor-copia/oraculo/test_win_motor_copia.py` (motor embutido) — congelados; o portão os roda.
    - Nenhum teste roda um hook do `settings.json` sem `python3` no PATH; nenhum confere o matcher do guard-git; nenhum
      confere fim de linha do que o harness grava; nenhum confere `C:\Users\` no guard de privacidade.
    - `test_harness_dev.py:591,594` exige o texto `python3 .claude/tools/…` nas skills (mantém F9 como "não muda").

## [PASS] 01-TASK-ORACULO — 2026-10-09T12:31:05-0300
- status: DONE · gate: PASS
- oráculo 540e1eccf037 congelado; RED 13/13 CAs no Windows, CA-14 verde no WSL

## [PASS] 2026-10-09 — 01-TASK-ORACULO
- Contratado: oraculista (general-purpose, opus) · feature win-harness aberta sem oráculo: 14 CAs a provar (quem testa não constrói) · resultado: oráculo 14 classes/55 testes; RED reproduzido (13/13 CAs vermelhos no Windows sem atalho, CA-14 verde no WSL); escrita só no oráculo (snapshot).
- Oráculo congelado `540e1eccf037` (ESPEC.md + test_win_harness.py).

## [NOTA] 02-TASK-LANCADOR-HOOKS — 2026-10-09T13:00:10-0300
- status: IN_PROGRESS · gate: PENDENTE

## [NOTA] 04-TASK-ESTADO-ENCODING — 2026-10-09T13:00:12-0300
- status: IN_PROGRESS · gate: PENDENTE

## [REJECT] 04-TASK-ESTADO-ENCODING — 2026-10-09T13:21:45-0300
- status: IN_PROGRESS · gate: FAIL
- revisor CHANGES_REQUESTED: def dentro_sys32 removido de feature.py (portão reprova); ciclo 2

## [REJECT] 02-TASK-LANCADOR-HOOKS — 2026-10-09T13:28:20-0300
- status: IN_PROGRESS · gate: FAIL
- revisor CHANGES_REQUESTED: CS_DEV_PY inválido ⇒ hooks saem 127 (falha aberta); ciclo 2

## [PASS] 04-TASK-ESTADO-ENCODING — 2026-10-09T13:32:32-0300
- status: DONE · gate: PASS
- régua PASS (oráculo Windows sem atalho, win-bash, harness-dev WSL 2 Pythons); revisor ciclo 2 APPROVED

## [PASS] 02-TASK-LANCADOR-HOOKS — 2026-10-09T13:50:02-0300
- status: DONE · gate: PASS
- régua PASS (oráculo Windows sem atalho, harness-dev WSL 2 Pythons, CA-14); revisor ciclo 2 APPROVED

## [NOTA] 03-TASK-SCRIPTS-SHELL — 2026-10-09T13:51:06-0300
- status: IN_PROGRESS · gate: PENDENTE

## [NOTA] 05-TASK-REGUA-PORTAO — 2026-10-09T13:51:10-0300
- status: IN_PROGRESS · gate: PENDENTE

## [PASS] 05-TASK-REGUA-PORTAO — 2026-10-09T14:09:14-0300
- status: DONE · gate: PASS
- régua PASS (oráculo Windows sem atalho, WSL harness-dev 2 Pythons, CA-14); revisor APPROVED

## [PASS] 03-TASK-SCRIPTS-SHELL — 2026-10-09T14:11:47-0300
- status: DONE · gate: PASS
- régua PASS (oráculo Windows sem atalho, WSL harness-dev 2 Pythons, CA-14; .ps1 parse PS 5.1 ok); revisor APPROVED

## [NOTA] 06-TASK-SUITE-HARNESS-DEV — 2026-10-09T14:12:24-0300
- status: IN_PROGRESS · gate: PENDENTE

## [NOTA] 2026-10-09T15:34:39-0300 — Redação na E2 por decisão do founder
- O guard de privacidade recusou o commit do estado: a E2 aprovada (`propostas/E2.md:83`) e a cópia dela neste HISTORICO
  citavam, como exemplo da medição F7, um nome de exemplo em caminhos com barra normal (drive + `/Users/<nome>` e `/c/Users/<nome>`) (falso
  positivo: não é pessoa real). Founder escolheu "Redigir fulano → x" (2026-10-09): o nome de exemplo virou `x` nos 2
  arquivos e no rascunho `local/criar-win-harness/E2.md`. Conteúdo da investigação inalterado; o sha registrado da E2
  aprovada é o de antes da redação.
- Pendente para o fechamento: `FEATURE.md` (CA-03 e Problema) usa o mesmo nome de exemplo na forma com barra invertida,
  que só o guard novo (task 02) detecta — tratar antes do commit da feature.
- Complemento: a forma "drive + barra normal + Users" é termo da lista local de privacidade mesmo com nome de
  exemplo; o trecho foi reescrito por extenso (sem a forma literal) na E2, aqui e no rascunho. Guard: 0 achados.
