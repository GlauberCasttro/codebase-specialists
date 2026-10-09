# HISTORICO — feature win-motor-copia

<!-- APPEND-ONLY: [NOTA] | [PASS] | [REJECT]; escrito pelo feature.py e pelo tech-lead, em série -->

## [NOTA] 2026-10-08T12:42:51-0300 — Abertura da feature win-motor-copia
- campanha: campanhas/win-motor-copia (ac.py init; escopo: .claude/tools/ac/ac.py, .claude/tools/ac/frase.py, .claude/tools/ac/hook_aprovacao.py, .claude/tools/ac/ORIGEM.txt, .claude/settings.json, .gitattributes)
- tasks: 5 · primeira: 01-TASK-ORACULO
- investigação aprovada (E2):

    # E2 — Investigação medida
    
    ## Inventário
    - Motor embutido: 8 arquivos em `.claude/tools/ac/` (`ac.py`, `frase.py`, `hook_aprovacao.py`, 4 `references/*.json5`,
      `ORIGEM.txt`) — `git ls-files .claude/tools/ac/`.
    - Mudança na fonte entre a cópia atual e `30e2da6` (`git -C ../auto-correcao diff --stat 868a18b 30e2da6 -- scripts/
      references/`): 3 arquivos, +440/−44 — `scripts/ac.py` (12 linhas), `scripts/frase.py` (89), `scripts/hook_aprovacao.py`
      (383). `references/`: 0 linhas de diferença (os 4 `.json5` ficam iguais).
    - Consumidores do motor embutido no harness (`grep -rln -E 'tools/ac/|ac/ac\.py|hook_aprovacao' .claude`): 10 arquivos
      além do próprio motor — `settings.json`, `_comum.sh`, `campanha.py`, `carimbo.sh`, `estado_lib.py`, `guard-entrega.py`,
      `regua.json`, `script-aprovacao.sh`, `tests/test_harness_dev.py`, `skills/rh/evals/evals.json`.
    - Finais de linha neste clone (`git ls-files --eol .claude/tools/ac/`): 8 de 8 com `w/crlf` (`core.autocrlf=true`, sem
      `.gitattributes` no repositório).
    
    ## Classificação
    - muda: 5 — `ac.py`, `frase.py`, `hook_aprovacao.py` (cópia da fonte; no `ac.py` reaplicar as 2 linhas do layout),
      `ORIGEM.txt` (commit e sha256 novos), `.claude/settings.json` (só o matcher do hook, decisão 3 da E1).
    - não muda: 4 `references/*.json5` (iguais na fonte) e os 10 consumidores (usam o motor pelo caminho; a interface de
      linha de comando não mudou — `ac.py --help` igual em subcomandos).
    - congelado: nenhum oráculo de campanha anterior aponta para `.claude/tools/ac/`.
    - Soma: os 8 arquivos do motor + `settings.json` = 9 = 5 (muda) + 4 (não muda, `references/`). Os 10 consumidores
      ficam fora da soma: não mudam.
    
    ## Exclusões
    - Fora: o `python3` fixo no comando do hook e nos outros tools (B-15), `.gitattributes` do repositório inteiro (B-15),
      produto `scripts/` (B-14). Não auditei os 10 consumidores linha a linha: a interface do motor não mudou (mesmos
      subcomandos), e a régua da feature roda a suíte harness-dev inteira, que os exercita.
    
    ## Achados
    - F1 — `.claude/tools/ac/frase.py:187-239` (cópia atual) — a frase só entra por `/dev/tty` + `termios`: no PowerShell
      `frase definir`/`gate`/`preauth` saem com SemTTY; a abertura da campanha (`gate stop`, intake.3) é impossível no
      Windows nativo. Corrigido na fonte em `3e81f49` (+ D-0-10).
    - F2 — `.claude/tools/ac/ac.py:952` (`cmd_load`) — `UnicodeEncodeError` com stdout cp1252 (≈, ≥); `:929` status (✓).
      Corrigido na fonte em `3e81f49`.
    - F3 — `.claude/tools/ac/hook_aprovacao.py:259` — só analisa `tool_name == "Bash"`; e `.claude/settings.json:15`
      registra o hook com `"matcher": "Bash"`: a ferramenta PowerShell passa sem análise. Corrigido na fonte em `30e2da6`
      (selftest 83 → 135 casos); o matcher é deste projeto.
    - F4 — `.claude/tools/tests/test_harness_dev.py:451-458` (`MotorEmbutido.test_origem_confere_sha256`) — JÁ FALHA HOJE
      neste clone: sha256 dos BYTES do `ac.py` no disco = `de78cc5a…` (CRLF) ≠ `fbd0f1cd…` registrado no ORIGEM (LF).
      Medido: `python3 -m unittest test_harness_dev.MotorEmbutido.test_origem_confere_sha256` → FAILED. Copiar sem tratar
      os finais de linha deixa o teste vermelho no Windows de novo no próximo checkout.
    - F5 — fonte `30e2da6:scripts/ac.py:35` — `CICLO` ainda resolve `references/` só pela pasta-pai: as 2 linhas do layout
      embutido continuam necessárias (decisão 2 da E1).
    - F6 (DESCARTADO por medição) — suspeita de que a fonte mudou `references/`: `git diff 868a18b 30e2da6 -- references/`
      = 0 linhas.
    
    ## Enforcement existente
    - `test_harness_dev.py:447` (`test_hook_aprovacao_selftest`) — roda o selftest do hook embutido: hoje 83/83, verde.
    - `test_harness_dev.py:451` (`test_origem_confere_sha256`) — confere sha256 de 7 arquivos contra o ORIGEM: vermelho
      neste clone (F4); verde no macOS.
    - `test_harness_dev.py:594` exige o texto `python3 .claude/tools/ac/ac.py` nas skills (não muda nesta feature).
    - Nenhum teste deste projeto cobre frase no console do Windows, cp1252 ou o matcher PowerShell — as provas disso estão
      nos oráculos do `auto-correcao` (`campanhas/win-motor`, `campanhas/win-hook`), que podem rodar contra a cópia
      embutida via `ORACULO_SCRIPTS`.

## [PASS] 01-TASK-ORACULO — 2026-10-08T14:40:48-0300
- status: DONE · gate: PASS
- oráculo afeac8b409ff congelado; 21 testes, 16 CA vermelhos hoje pelo motivo, 5 guardas verdes; oraculista separado (opus)

## [NOTA] 02-TASK-MOTOR — 2026-10-08T14:42:56-0300
- status: IN_PROGRESS · gate: PENDENTE

## [NOTA] 03-TASK-MATCHER — 2026-10-08T14:42:57-0300
- status: IN_PROGRESS · gate: PENDENTE

## [PASS] 02-TASK-MOTOR — 2026-10-08T18:30:48-0300
- status: DONE · gate: PASS
- régua completa WSL 2 Pythons verde (harness/scan após make, iguais ao HEAD); oráculo 21/21 Win+WSL; revisor opus APPROVED

## [PASS] 03-TASK-MATCHER — 2026-10-08T18:30:50-0300
- status: DONE · gate: PASS
- diff 1 linha; oráculo 21/21 Win+WSL; revisor sonnet APPROVED

## [NOTA] 04-TASK-QA — 2026-10-08T18:31:13-0300
- status: IN_PROGRESS · gate: PENDENTE

## [PASS] 04-TASK-QA — 2026-10-08T20:36:26-0300
- status: DONE · gate: PASS
- QA sonnet ACCEPT; portão VERDE (WSL 2 Pythons); oráculo 21/21 Win Git Bash e PowerShell

## [NOTA] 05-TASK-REVIEW — 2026-10-08T20:36:27-0300
- status: IN_PROGRESS · gate: PENDENTE

## [PASS] 05-TASK-REVIEW — 2026-10-08T20:46:18-0300
- status: DONE · gate: PASS
- review opus APPROVED; 3 MENOR pré-existentes
