# ESPEC — oráculo da feature win-harness

Oráculo de aceite da feature `win-harness` (harness de desenvolvimento no Windows nativo, sem o atalho `python3`).
Escrito por um agente SEPARADO do corretor (quem testa não constrói): não implementou nada, não escreveu protótipo de
correção e não congela o oráculo (o tech-lead congela com TODOS os arquivos: `ESPEC.md` e `test_win_harness.py`).

Arquivo de testes: `test_win_harness.py` (unittest puro, stdlib, Python 3.9+, LF). Uma classe `TestCA<NN>` por CA do
FEATURE.md; o filtro `-k CA<NN>` seleciona a classe. Os testes `test_calibracao_*` passam hoje e continuam passando:
provam que a classe não está vermelha por acaso (saída boa conhecida passa; saída vazia ou errada reprova).

| CA | Classe | Testes | Onde roda |
|---|---|---|---|
| CA-01 | `TestCA01HooksPythonSemPython3` | 8 (6 só Windows) | Windows; calibração em todos |
| CA-02 | `TestCA02GuardGitPowerShell` | 5 (1 só Windows) | todos |
| CA-03 | `TestCA03PrivacidadeCaminhoWindows` | 3 | todos |
| CA-04 | `TestCA04SaidaUtf8` | 3 | todos (o defeito só aparece no Windows) |
| CA-05 | `TestCA05GravaEmLf` | 6 | todos (CRLF só aparece no Windows) |
| CA-06 | `TestCA06ReguaComPythonsDaMaquina` | 7 (5 só Windows, 1 só POSIX) | todos |
| CA-07 | `TestCA07BashDoGitNuncaAliasWsl` | 5 | todos (plataforma simulada por mock) |
| CA-08 | `TestCA08CarimboAnunciaInterpretador` | 2 | todos |
| CA-09 | `TestCA09ScriptAprovacaoPs1` | 3 (1 só Windows, 1 só POSIX) | todos |
| CA-10 | `TestCA10InstalarComJuncao` | 2 | só Windows |
| CA-11 | `TestCA11PerfilTemporarioCompleto` | 2 | todos (USERPROFILE conferido só no Windows) |
| CA-12 | `TestCA12FecharComQualidade` | 4 | todos |
| CA-13 | `TestCA13SuiteHarnessDevVerdeNoWindows` | 2 | só Windows (demora: a suíte inteira por Python) |
| CA-14 | `TestCA14PosixInalterado` | 3 | só WSL/macOS/Linux com `python3` e `/usr/bin/python3` |

Prova de cada CA (da raiz do projeto): `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA<NN>`
(no WSL, `python3`). Skip sempre com motivo: o que é só do Windows pula fora dele, e vice-versa.

## Raiz testada, variáveis e isolamento

- Raiz: `CS_DEV_SKILL_DIR`; senão `ORACULO_SKILL`; senão `CS_SKILL_DIR` (o portão passa a cópia limpa por ela); senão
  três pastas acima do arquivo de teste. Tools em `<raiz>/.claude/tools`, hooks em `<raiz>/.claude/settings.json`.
- `ORACULO_GIT_RAIZ`: raiz do Git for Windows; padrão = achada a partir do `git` do PATH (`cmd\git.exe` ou
  `mingw64\bin\git.exe`), senão `%ProgramFiles%\Git`. Sem `usr\bin\bash.exe` e `cmd\git.exe` ⇒ FALHA citando LACUNA de
  ambiente (nunca pula).
- Ambiente "sem atalho" (Windows) = PATH do subprocesso montado pelo teste só com a pasta de `sys.executable`,
  `<Git>\cmd`, `<Git>\usr\bin` e `%SystemRoot%\System32` (pré-condição conferida: `python3` ausente, `python`
  presente). "Sem Python" = o mesmo sem a pasta do Python (pré-condição: `python3`, `python` e `py` ausentes; o `py.exe`
  de `C:\Windows` não entra). "Com atalho" (só calibração) = o atalho de hoje (`python3` = sh que faz
  `PYTHONUTF8=1 exec python "$@"`) num diretório temporário à frente do PATH.
- Todo subprocesso: sem `PYTHONUTF8`, `PYTHONIOENCODING`, `PYTHONPATH`, `PYTHONHOME`, `BASH_ENV`, `ENV` e sem variáveis
  `CS_*`/`CLAUDE_*` herdadas; `HOME` e `USERPROFILE` = perfil temporário. O bash é sempre o do Git por caminho
  explícito (`<Git>\usr\bin\bash.exe`): `bash` pelo nome num subprocess do Python cai no WSL. Fora do Windows, `sh -c`
  (hooks) e `bash` (scripts) do sistema.
- Hook "pelo comando exato do settings.json": o teste lê o `command` da entrada cujo texto cita o script
  (`hook_aprovacao.py`, `guard-entrega.py`, `guard-estado.py`, `exige-modelo.py`, `guard-git`) e o roda com
  `bash -c <command>` (Windows) ou `sh -c <command>`, `CLAUDE_PROJECT_DIR=<raiz>` e o payload JSON pela stdin.
  NEGOU = exit 2 OU exit 0 com `hookSpecificOutput.permissionDecision == "deny"` numa linha JSON do stdout.
- Caminhos entregues a scripts bash no Windows vão com barras normais (`C:/…`): o MSYS e o Python aceitam os dois.
- Tudo em `tempfile.mkdtemp()` (apagado no fim; junções removidas antes, sem descer no alvo). Nada é escrito no
  projeto nem no perfil real. Git só em repositórios temporários, com `-c user.name=Ana`. Nenhum teste roda `gate`,
  `preauth` nem `frase` do motor: o comando de aprovação do CA-01 é STRING de payload; as campanhas do CA-08/09/12 são
  temporárias (`ac.py init` + `oracle freeze` de um arquivo de fixture; no CA-12 o `state.json` temporário é editado
  para pôr a campanha no ponto da remedição — fixture, nunca aprovação real).
- O próprio arquivo de teste é varrido pelo guard de privacidade: o caminho de usuário do Windows do CA-03 é montado
  em partes (`"C:" + "\\" + "Users" …`) — nenhum literal casa com o padrão novo.

## Contrato fixado (interfaces previstas no FEATURE.md)

- `e2e.py pythons [--json]`: `--json` imprime `{"pythons": [str, …]}` (uma lista pura `[str, …]` também é aceita).
  Windows: os interpretadores achados no PATH entre `python3`, `python` e `py`, sem repetir o mesmo executável (dedup
  pelo `sys.executable` resolvido de cada um), ≥ 1; nenhum ⇒ exit 2 (não o exit 2 do argparse). macOS/Linux/WSL:
  exatamente `["python3", "/usr/bin/python3"]`. `e2e.py rodar --dry-run` e `portao.sh <f> --dry-run` usam essa lista.
- `carimbo.sh --brief` imprime uma linha que começa com `python: ` seguida do interpretador; a linha da campanha mantém
  o formato de hoje `<camp>: etapa <etapa> (<feitas>/<total> etapas)`, com feitas = etapas marcadas `✓` no
  `ac.py status` e total = TODAS as linhas de etapa (inclusive as `…` parciais).
- `script-aprovacao.sh <f>` no Windows grava `<CS_DEV_WS>/aprovar-<f>.ps1` com: o interpretador resolvido (o caminho
  Windows do Python achado, ex.: `C:\…\python.exe` — comparado sem caixa e com `\`≡`/`; forma `/c/…` do MSYS não
  serve ao PowerShell), os 3 passos de hoje nesta ordem (`gate stop`, `gate oracle:requisito`, `preauth commit`) e,
  depois de CADA passo e antes do próximo, uma conferência de `$LASTEXITCODE` com `throw`. Gerar não roda: o
  `state.json` da campanha fica sem `gates`/`preauth`. Fora do Windows: o `aprovar-<f>.sh` de hoje e nenhum `.ps1`.
- `estado_lib.bash_exe()` existe e aplica a MESMA regra que `feature.bash_exe()` (que continua existindo):
  descarta o bash dentro de `%LOCALAPPDATA%\Microsoft\WindowsApps\` (sem diferenciar caixa), como já descarta o do
  `System32`. `feature.conferir_commit` chama o `conferir-commit.sh` por `subprocess.run` com `argv[0]` = o devolvido
  por `bash_exe()`.
- `campanha.py fechar <f> --relatorio R --config C --decisao D --qualidade P/T`: o `run record` grava
  `quality = {"passed": P, "total": T}` (inteiros) e o motor aceita `done remedicao`; sem `--qualidade`, exit ≠ 0
  ANTES de qualquer chamada ao motor (`state.json` e `ledger.jsonl` intactos; nenhum `front report`).
- `instalar.sh` no Windows: `$HOME/.claude/skills/codebase-specialists` é uma JUNÇÃO (reparse tag
  `IO_REPARSE_TAG_MOUNT_POINT`) para `<projeto>/dist/codebase-specialists`; `instalar.sh --check` sai 0 e não diz
  "não é o link".
- `package_validar.py`: o subprocesso da skill instalada vê `HOME` e `USERPROFILE` = o HOME temporário.
- `.gitattributes`: `eol=lf` para `.claude/**` e `campanhas/**`; em `campanhas/**`, `text=auto` (binário não converte).

## Como cada CA é verificado (ambiente → entrada → esperado)

- **CA-01** — Windows sem atalho → cada um dos 4 hooks Python, pelo comando do settings.json, com um payload negável
  (aprovação `ac.py … gate stop` no Bash; Write em `<raiz>/SKILL.md`; Write em `<raiz>/.claude/state/features.json`;
  despacho `Agent` de `01-TASK-ORACULO` sem `model`) → NEGOU e exit ≠ 127. Mesmo ambiente, payload inofensivo
  (`Read`) → exit 0 sem deny (o hook roda de verdade; um lançador que sempre sai 2 reprova). Sem Python nenhum → exit 2
  com motivo no stderr. Calibração: com o atalho, os 4 negam e o inofensivo passa; `negou("",0)` é falso.
- **CA-02** — matcher do guard-git casa (`re.fullmatch`) `Bash` e `PowerShell`. Payload `tool_name: PowerShell` com
  `git push`, `git reset --hard`, `git clean -fd`, `git stash`, `git add -A`, `git commit -a -m wip`,
  `git checkout -- x`, `& git.exe push origin master`, `& git.exe reset --hard HEAD~1`, `Set-Location x; git push`,
  `cd x; git stash` → NEGOU. `git status`, `git log --oneline -5` e `Write-Host "git push"` → exit 0, nem deny nem
  ask. Windows sem atalho, `Bash` + `git push` → NEGOU (hoje: `ask`). Calibração: com o atalho, Bash `git push` nega e
  `git status` passa.
- **CA-03** — `guard_privacidade.py <arquivo>` com `CS_TERMOS_PRIVADOS` = arquivo vazio (só padrões genéricos): um
  arquivo por forma `C:\Users\<nome>\proj` com nome real, `C:\\Users\\<nome>\\proj`, `c:\users\<nome>\proj` → exit 1
  citando o arquivo; um arquivo com `C:\Users\x\proj`, `C:\Users\<nome>\proj` (placeholder literal) e
  `%USERPROFILE%\proj` → exit 0. Calibração: `/Users/<nome>/proj` é acusado hoje; arquivo vazio passa.
- **CA-04** — para cada `<raiz>/.claude/tools/*.py` (16 hoje) `--help`, e `sessao.py briefing` num repositório
  temporário: rodado sem `PYTHONUTF8`, stdout em pipe, `COLUMNS=120` → exit 0 e os bytes decodificam como UTF-8 e são
  IDÊNTICOS aos da mesma execução com `PYTHONUTF8=1` (a referência; ela própria tem de sair 0 e, no briefing, ter
  acento). Calibração: bytes cp1252, saída vazia e `?` no lugar do acento reprovam; idênticos passam.
- **CA-05** — `estado_lib.gravar` e `estado_lib.apensar` (importados de `<raiz>/.claude/tools`) e `publicar_regras.py
  aplicar <dir> --regras <json>` (um bloco e uma regra geral que de fato mudam 2 arquivos) → bytes sem `\r\n` e com o
  conteúdo transformado. `git check-attr eol` num repositório temporário com o `.gitattributes` da raiz →
  `.claude/state/RESUME.md` e `campanhas/qualquer/oraculo/ESPEC.md` dão `lf`; `git check-attr text` de
  `campanhas/qualquer/figura.png` dá `auto`. Calibração: `.claude/tools/ac/ac.py` já dá `lf`.
- **CA-06** — Windows sem atalho: `e2e.py pythons --json` exit 0, ≥ 1, cada item achado no PATH montado e roda, sem
  executável repetido. Com um `python3.cmd` (shim que chama o mesmo `python.exe`) à frente → exatamente 1. Sem Python →
  exit 2 (depois de provar que o subcomando existe). `e2e.py rodar --suites harness-dev --dry-run` e `portao.sh
  wh-portao --src <tmp> --dry-run -- a.txt` (projeto git temporário) citam cada item da lista e não citam
  `/usr/bin/python3`. POSIX: a lista é `["python3", "/usr/bin/python3"]`. Calibração: o leitor da lista aceita os dois
  formatos e recusa vazio/ilegível.
- **CA-07** — mock: `os.name = "nt"`, `shutil.which("bash")` = `<tmp>\AppData\Local\Microsoft\WindowsApps\bash.exe`
  (`LOCALAPPDATA = <tmp>\AppData\Local`; também com outra caixa), `which("git")` = `<tmp>\Git\cmd\git.exe`, árvore real
  com `<tmp>\Git\bin\bash.exe` → `feature.bash_exe()` e `estado_lib.bash_exe()` devolvem o bash do Git; com
  `subprocess.run` simulado, `feature.conferir_commit("wh-x", ["a.txt"], <raiz>)` chama o `conferir-commit.sh` com
  `argv[0]` = `bash_exe()` = bash do Git. Calibração: bash do PATH fora de WindowsApps é devolvido (hoje já).
- **CA-08** — projeto git temporário com uma campanha (`ac.py init`; `state.json` com `intake` completa e `oraculo.1`
  feita ⇒ `ac.py status` = 1 etapa ✓, 1 parcial, 9 linhas) → `carimbo.sh --brief` (Windows sem atalho;
  `CS_DEV_SKILL_DIR` = o projeto temporário) sai 0, tem `python: <interpretador>` (cita "py"; no Windows não é
  `python3`) e `wh-carimbo: etapa … (1/9 etapas)`, igual ao contado no `ac.py status`. Calibração: o leitor acha a
  linha e a contagem num texto bom e devolve nada no vazio.
- **CA-09** — campanha temporária com oráculo congelado (`CS_DEV_CAMP`, `CS_DEV_WS`, `CS_DEV_SKILL_DIR` temporários),
  Windows sem atalho → `script-aprovacao.sh wh-aprov --por Ana` exit 0 e o `.ps1` do contrato. POSIX → o `.sh` de hoje
  (`#!/bin/sh`, `python3 "$M"`, os 3 passos), sem `.ps1`. Calibração: um `.ps1` bom passa; vazio ou sem a conferência
  depois de um passo reprova.
- **CA-10** — Windows sem atalho, perfil temporário, projeto git temporário (`SKILL.md`, `VERSION`, `scripts/cs.py`) e
  uma CÓPIA de `<raiz>/.claude/tools` (sem `tests/`) com `package.sh` trocado por um stub que monta
  `dist/codebase-specialists` a partir do `git archive HEAD` do projeto temporário e grava `.origem` (a validação do
  PRODUTO no Windows é a B-14, fora desta feature) → `instalar.sh` exit 0; o instalado é junção para o `dist/`; um
  arquivo criado no `dist/` aparece pelo instalado (não é cópia); `instalar.sh --check` exit 0 sem "não é o link".
- **CA-11** — pacote falso (`SKILL.md` + `scripts/cs.py` que registra `HOME`, `USERPROFILE` e `expanduser("~")`) e
  fixture falsa (`--fixture`); quem chama tem `HOME`=`USERPROFILE`=<perfil-pai temporário> → em cada passo,
  `expanduser("~")` do subprocesso ≠ perfil-pai e = `HOME` temporário; no Windows `USERPROFILE` = `HOME`; exit 0.
  Calibração: no Windows `expanduser` segue `USERPROFILE`, não `HOME`.
- **CA-12** — campanha temporária `wh-fechar` no ponto da remedição (fixture: `intake`..`plano` feitas, `preauth
  commit` condicionado a `integracao.1/2`, oráculo congelado, `PLANO.json5` com a frente `fechamento`, etapa
  `correcao`) → `campanha.py fechar wh-fechar --relatorio R --config sistema --decisao parar --qualidade 14/14` exit 0,
  `remedicao.1/2` feitas, etapa `decisao`, último run com `quality {"passed": 14, "total": 14}`. Sem `--qualidade` →
  exit ≠ 0, `state.json`/`ledger.jsonl` byte a byte iguais, sem `fronts/fechamento.md`. Calibração: a mesma fixture,
  pelos passos do motor, chega a `done remedicao` com `--grading` 14/14 e é recusada sem nota.
- **CA-13** — Windows sem atalho: para cada item de `e2e.py pythons`, `<py> -m unittest discover -s tests -v` em
  `<raiz>/.claude/tools` → exit 0, `Ran N` (N>0), linha final `OK…`, nenhum `skipped ''`. Calibração do leitor de
  resumo (OK, OK com skip, vazio, Ran 0, FAILED).
- **CA-14** — WSL/macOS/Linux (`python3` e `/usr/bin/python3`): harness-dev verde nos 2 Pythons; oráculos
  `campanhas/win-bash/oraculo` e `campanhas/win-motor-copia/oraculo` verdes nos 2 (`ORACULO_SKILL`=`CS_SKILL_DIR`=raiz);
  com espiões `python3` e `python` à frente do PATH, os 4 hooks Python e o guard-git, pelo comando do settings.json e
  com payload inofensivo, saem 0 e chamam SÓ `python3`. "O oráculo da feature verde no WSL" é medido rodando o
  `discover` inteiro no WSL (o critério de parada), não dentro do CA-14 (recursão).

## RED medido no HEAD de hoje (worktree com `_comum.sh`/`package.sh` sujos, antes da entrega)

Windows 11, Python 3.12.7 (`python`), Git Bash 5.x; `env -u PYTHONUTF8 python -B -m unittest discover -s
campanhas/win-harness/oraculo -p "test_*.py" -k CA<NN>`:

| CA | Resultado | Motivo medido |
|---|---|---|
| CA-01 | Ran 8 · failures=12 | os 4 hooks saem 127 (`python3: command not found`); sem Python, 127 em vez de 2 |
| CA-02 | Ran 5 · failures=16 | matcher só `Bash`; PowerShell passa; sem python3 o guard pede `ask` |
| CA-03 | Ran 3 · failures=3 | `C:\Users\<nome>\` não é acusado nas 3 formas |
| CA-04 | Ran 3 · failures=17 | 15 de 16 tools com `--help` fora de UTF-8 (cp1252 ou `UnicodeEncodeError`); briefing cp1252 |
| CA-05 | Ran 6 · failures=5 | `gravar`/`apensar`/`publicar_regras` gravam CRLF; `eol` e `text` = `unspecified` |
| CA-06 | Ran 7 · failures=5 · skipped=1 | `e2e.py pythons` não existe (argparse `invalid choice`) |
| CA-07 | Ran 5 · failures=4 | alias de WindowsApps devolvido; `estado_lib.bash_exe` não existe |
| CA-08 | Ran 2 · failures=1 | sem a linha `python:`; campanha some (python3 ausente) |
| CA-09 | Ran 3 · failures=1 · skipped=1 | `script-aprovacao.sh` sai 1 (`python3: command not found` no `oracle verify`) |
| CA-10 | Ran 2 · failures=1 | `ln -s` do MSYS fez CÓPIA; conferência "não é o link … (hoje: pasta/arquivo)" |
| CA-11 | Ran 2 · failures=5 | `expanduser("~")` do subprocesso = perfil de quem chamou (só `HOME` trocado) |
| CA-12 | Ran 4 · failures=2 | `--qualidade` desconhecido (exit 2); sem ele o motor é chamado e recusa `done remedicao` |
| CA-13 | Ran 2 · failures=1 | `e2e.py pythons` não existe (a suíte em si: 63/83 quebram, E2) |
| CA-14 | Ran 3 · skipped=3 | só POSIX |

Discover inteiro: Git Bash e PowerShell (`Remove-Item Env:PYTHONUTF8`) → `Ran 55 tests` · `FAILED (failures=73,
skipped=5)`, exit 1. WSL (Python 3.10.12, `python3`) → `Ran 55` · `FAILED (failures=25, skipped=17)`: CA-02 (12),
CA-03 (3), CA-05 (2: `.gitattributes`), CA-06 (1: lista POSIX), CA-07 (4), CA-08 (1), CA-12 (2) vermelhos também no
WSL (a mudança vale para todos os sistemas); CA-04, CA-09 (POSIX), CA-11 e **CA-14 verdes** (3 ok: harness-dev nos 2
Pythons, oráculos win-bash e win-motor-copia, hooks chamando só `python3`).

## Limites honestos

- O PATH que o Claude Code passa aos hooks no Windows não foi medido (E2); o oráculo SIMULA o pior caso (sem
  `python3`) rodando o `command` pelo bash do Git. Se o Claude Code usar outro shell, o CA-01/02 mede o comando, não
  o transporte.
- CA-10 usa um stub de `package.sh`: prova a junção e o reconhecimento pelo `_comum.sh`, não o pacote do produto.
- CA-07 depende de `conferir_commit` chamar `subprocess.run` (como hoje); outra API de processo não é capturada.
- CA-13 e CA-14 rodam suítes inteiras (minutos); o resto do oráculo roda em ~2–3 min no Windows.
