# win-harness — Harness de desenvolvimento no Windows nativo, sem atalho

FEATURE-ID: win-harness
Nome: Harness de desenvolvimento no Windows nativo, sem atalho

## História
Como founder desenvolvendo a codebase-specialists numa máquina Windows, quero que os hooks, os tools, a régua e o
portão do harness funcionem com o Python que a máquina tem (sem o atalho `~/bin/python3` e sem o WSL), e que falhem
FECHADOS quando faltar algo, para que os guards protejam de verdade e a entrega seja medida aqui mesmo.

## Problema / Contexto
Medido na E2 (Python 3.12.7 só como `python`, PATH sem `~/bin`, sem `PYTHONUTF8`):
- a suíte harness-dev quebra em 63 de 83 testes no Windows nativo (33 falhas, 30 erros; ~30 `UnicodeDecodeError`,
  16 `bash` caindo no WSL, 1 `WinError 1314` de symlink); no WSL passa;
- os 4 hooks Python de `.claude/settings.json:19,29,39,49` chamam `python3`: sem ele saem 127 e os guards ficam
  ABERTOS; o `guard-git` só tem matcher `Bash` (`settings.json:5`) e sem `python3` responde `ask`
  (`guard-git.sh:7-8`);
- `regua.json:3` e `portao.sh:24` exigem `/usr/bin/python3` — o portão das features do Windows só rodou no WSL;
- 10 de 16 tools `.py` caem com `UnicodeEncodeError` no `--help` em pipe (cp1252); nenhum reconfigura o stdio (a
  E2 diz "11 de 17" por erro de contagem; a lista de nomes da E2 tem os 10);
- `estado_lib.py:115,122` grava em modo texto ⇒ CRLF: 8 arquivos de estado `w/crlf`/`w/mixed`; `.gitattributes`
  só cobre `.claude/tools/ac/**`;
- `guard_privacidade.py:32-33` não reconhece `C:\Users\fulano\…` (0 achados medidos; repositório público);
- B-18 (4) contagem do `carimbo.sh:40-41`, (6) alias do WSL em `WindowsApps` no `bash_exe()`, (7) `conferir_commit`
  sem teste de `argv[0]`, (8) `campanha.py:123-125` sem nota de qualidade no `run record`;
- `package_validar.py:82` e `test_feature.py:62` trocam só `HOME` (o Windows lê `USERPROFILE`); `instalar.sh:88`
  usa `ln -s` (sem Modo Desenvolvedor não há symlink);
- `script-aprovacao.sh:38-40` gera um `.sh` com `python3`: as duas aprovações do Windows foram um `.ps1` escrito à mão
  (`local/aprovar-win-bash.ps1`).

## Valor de negócio
O harness é quem entrega a B-14 (produto no Windows): sem régua e portão nativos, cada feature do Windows depende do
WSL (~1h30 por régua sobre `/mnt/c`) e de um atalho local. Com guards abertos, o portão humano e a privacidade de um
repositório público dependem da sorte.

## Personas / Stakeholders
- founder (desenvolve no Windows; roda as aprovações no PowerShell com a senha)
- agente principal / tech-lead (roda tools e régua; depende dos hooks para não escapar do escopo)
- subagentes executores e revisores (rodam testes e comandos pelo Bash e pela PowerShell)

## Critérios de Aceitação
- **CA-01 — hooks Python rodam sem `python3` e falham fechados.** DADO um PATH com `python` e sem `python3`,
  QUANDO cada um dos 4 hooks Python roda pelo comando exato do `.claude/settings.json` com um payload que deve ser
  negado, ENTÃO nega como no macOS/Linux; e DADO um PATH sem nenhum Python, ENTÃO sai 2 com motivo no stderr (nunca
  127, nunca 0).
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA01`
- **CA-02 — guard-git cobre a ferramenta PowerShell.** DADO um payload `tool_name: PowerShell` com `git push`,
  `git reset --hard`, `git clean -fd`, `git stash`, `git add -A`, `git commit -a` ou `git checkout -- x` (também como
  `& git.exe …` e depois de `;`), QUANDO o hook do guard-git roda pelo comando do `settings.json`, ENTÃO nega; `git
  status` e `git log` passam; e o matcher do guard-git no `settings.json` inclui `PowerShell`.
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA02`
- **CA-03 — privacidade reconhece caminho do Windows.** DADO um arquivo com `C:\Users\fulano\proj`,
  `C:\\Users\\fulano\\proj` ou `c:\users\fulano\proj`, QUANDO `guard_privacidade.py` varre, ENTÃO acusa cada um; e os
  placeholders `C:\Users\x\`, `C:\Users\<nome>\` e `%USERPROFILE%\` passam.
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA03`
- **CA-04 — saída em UTF-8.** DADO o Windows sem `PYTHONUTF8` e stdout em pipe, QUANDO cada tool `.py` de
  `.claude/tools/` roda `--help` e `sessao.py briefing` roda, ENTÃO sai 0 e a saída decodifica como UTF-8 com os
  caracteres originais (`→`, `⇒`, acentos).
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA04`
- **CA-05 — o harness grava em LF.** DADO o Windows, QUANDO `estado_lib.gravar`, `estado_lib.apensar` e
  `publicar_regras.py aplicar` gravam, ENTÃO nenhum arquivo gravado contém `\r\n`; e `git check-attr eol` dá `lf`
  para um arquivo em `.claude/` e outro em `campanhas/`.
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA05`
- **CA-06 — régua com os Pythons da máquina.** DADO o Windows, QUANDO `e2e.py pythons` roda, ENTÃO lista os
  interpretadores encontrados entre `python3`, `python` e `py`, sem repetir o mesmo executável, no mínimo 1 (sem
  nenhum ⇒ exit 2); `e2e.py rodar --dry-run` e `portao.sh <f> --dry-run` usam essa lista; e DADO macOS/Linux/WSL,
  ENTÃO a lista é `python3 /usr/bin/python3`, como hoje.
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA06`
- **CA-07 — bash do Git, nunca alias do WSL.** DADO o Windows com `%LOCALAPPDATA%\Microsoft\WindowsApps\bash.exe`
  antes do Git Bash no PATH, QUANDO `bash_exe()` roda, ENTÃO descarta o alias (como já descarta o `System32`); e
  QUANDO `feature.conferir_commit` roda, ENTÃO o `argv[0]` do subprocess é o caminho devolvido por `bash_exe()`.
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA07`
- **CA-08 — SessionStart anuncia o interpretador e conta certo.** DADO um PATH sem `python3`, QUANDO `carimbo.sh
  --brief` roda, ENTÃO sai 0, imprime uma linha `python: <interpretador>` e, com uma campanha ativa, as etapas
  `feitas/total` batem com as do `ac.py status`.
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA08`
- **CA-09 — script de aprovação nativo do Windows.** DADO o Windows e o oráculo da feature congelado, QUANDO
  `script-aprovacao.sh <f>` roda, ENTÃO gera `local/aprovar-<f>.ps1` com o interpretador resolvido, os 3 passos de hoje
  (`gate stop`, `gate oracle:requisito`, `preauth commit`) e `throw` em `$LASTEXITCODE` diferente de 0 a cada passo,
  sem rodá-lo; e DADO macOS/Linux, ENTÃO gera o `local/aprovar-<f>.sh` de hoje.
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA09`
- **CA-10 — /install sem symlink no Windows.** DADO o Windows sem Modo Desenvolvedor e um perfil temporário
  (`HOME` e `USERPROFILE`), QUANDO `instalar.sh` roda, ENTÃO o instalado é uma junção para `dist/codebase-specialists`
  (não uma cópia) e a checagem do `_comum.sh` o reconhece como "o link deste projeto".
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA10`
- **CA-11 — perfil temporário completo.** DADO o Windows, QUANDO `package_validar.py` monta o HOME temporário, ENTÃO
  troca `HOME` e `USERPROFILE` e nada é lido do perfil real (o `expanduser("~")` do subprocesso aponta para o
  temporário).
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA11`
- **CA-12 — fechamento da campanha com nota.** DADO uma campanha temporária no ponto da remedição, QUANDO
  `campanha.py fechar <f> … --qualidade 14/14` roda, ENTÃO o `run record` vai com a nota (`quality {passed,total}`) e o
  motor aceita `done remedicao`; sem `--qualidade`, recusa antes de chamar o motor.
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA12`
- **CA-13 — suíte harness-dev verde no Windows nativo.** DADO o Windows sem o atalho (PATH sem `python3`, sem
  `PYTHONUTF8`), QUANDO a suíte `.claude/tools/tests` roda em cada Python de `e2e.py pythons`, ENTÃO 0 falhas e 0
  erros; skip só com motivo declarado (ex.: symlink sem privilégio).
  Prova: `python -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA13`
- **CA-14 — macOS/Linux/WSL inalterados.** DADO o WSL (`python3` e `/usr/bin/python3`), QUANDO o oráculo da feature,
  a suíte harness-dev e os oráculos `win-bash` e `win-motor-copia` rodam, ENTÃO todos verdes; os hooks continuam
  chamando o mesmo interpretador de hoje.
  Prova: `python3 -m unittest discover -s campanhas/win-harness/oraculo -p "test_*.py" -k CA14`

## RNFs
- RNF-01: Python 3.9+ stdlib; bash/sh POSIX (Git Bash 5.x no Windows); nenhuma dependência nova.
- RNF-02: falha FECHADA: hook sem interpretador nega (exit 2), nunca deixa passar.
- RNF-03: custo do hook: o lançador não chama `git` nem processo extra além do Python (cada ferramenta passa por
  ele).
- RNF-04: nada privado nos testes e fixtures (pessoa = "Ana"; caminhos com `~` ou variável).

## Edge cases
- Máquina com `python3` E `python` apontando para o mesmo executável: a régua roda uma vez (dedup por
  `sys.executable` resolvido).
- `py` launcher presente sem `python` no PATH: vale como interpretador.
- Variável `CS_DEV_PY` definida: vence a busca (já previsto em `_comum.sh:17`).
- Os 8 arquivos de estado já em CRLF: o índice do git já está em LF; a primeira gravação pelo harness os volta a LF
  e o carimbo ESTADO muda uma vez (cache-miss único, self-heal do `/carregar-sessao`).
- `.gitattributes` com `text=auto` (não `text`): binários em `campanhas/` não são convertidos.
- Comando PowerShell com `git` dentro de string (`Write-Host "git push"`): não é chamada de git; o guard não nega.
- Junção quando `~/.claude/skills/codebase-specialists` já existe como pasta comum: recusa sem apagar (como hoje).

## Dependências
- Nenhuma feature ativa (estado IDLE).
- As alterações sujas em `_comum.sh` e `package.sh` (F15) entram como base da cópia de trabalho, não são descartadas.
- Os oráculos congelados `campanhas/win-bash/oraculo/` e `campanhas/win-motor-copia/oraculo/` continuam verdes
  (`feature.bash_exe` continua existindo, mesmo que a lógica vá para o `estado_lib.py`).

## Escopo IN
- Lançador de Python único para `.sh` e hooks (`python3` → `python` → `py`, `CS_DEV_PY` vence, `PYTHONUTF8=1`).
- Os 5 hooks do `settings.json` (4 Python + matcher do guard-git) e o guard-git para PowerShell.
- stdio UTF-8 em todos os tools; gravação em LF; `.gitattributes` para `.claude/**` e `campanhas/**`.
- Régua e portão com os Pythons da máquina; texto da regra dos "2 Pythons" no `CLAUDE.md` e na skill `e2e-loop`.
- `carimbo.sh`, `script-aprovacao.sh` (`.ps1` no Windows), `instalar.sh` (junção), `package.sh`, `package_validar.py`.
- B-18 (3), (4), (6), (7) e a parte de `campanha.py` do (8).
- Suíte harness-dev verde no Windows nativo.

## Escopo OUT
- Produto (`scripts/`, `SKILL.md`, `references/`, `docs/`, `evals/`, `.claude/package/`) — B-14.
- Motor embutido `.claude/tools/ac/**` — B-18 (1)(2) vão ao `auto-correcao`.
- As 126 menções de `python3` nas skills `.md` (instrução ao agente; falha alta; o CA-08 anuncia o interpretador).
- B-18 (5) (guard de privacidade no `criar propor`/`oracle freeze`) e a parte do (8) sobre o `/tech-lead` registrar
  intake..plano no motor durante a execução (processo da skill, não Windows) — ficam no BACKLOG.
- Dependência de `make` nas suítes do produto — B-17.

## Escopo de escrita
- `.claude/settings.json`
- `.claude/CLAUDE.md`
- `.claude/skills/e2e-loop/SKILL.md`
- `.claude/tools/_py.sh`
- `.claude/tools/_comum.sh`
- `.claude/tools/guard-git.sh`
- `.claude/tools/guard_git.py`
- `.claude/tools/guard-privacidade.sh`
- `.claude/tools/guard_privacidade.py`
- `.claude/tools/pre-commit.sh`
- `.claude/tools/guard-entrega.py`
- `.claude/tools/exige-modelo.py`
- `.claude/tools/carimbo.sh`
- `.claude/tools/script-aprovacao.sh`
- `.claude/tools/instalar.sh`
- `.claude/tools/package.sh`
- `.claude/tools/package_validar.py`
- `.claude/tools/publicar_regras.py`
- `.claude/tools/estado_lib.py`
- `.claude/tools/feature.py`
- `.claude/tools/e2e.py`
- `.claude/tools/regua.json`
- `.claude/tools/portao.sh`
- `.claude/tools/campanha.py`
- `.claude/tools/tests/test_harness_dev.py`
- `.claude/tools/tests/test_feature.py`
- `.claude/tools/tests/test_orquestracao.py`
- `.gitattributes`

## Critério de parada
oráculo da feature 14/14 CAs verde no Windows nativo (Git Bash e PowerShell, PATH sem python3 e sem PYTHONUTF8) e no
WSL; suíte harness-dev com 0 falhas e 0 erros nos dois; oráculos win-bash e win-motor-copia verdes; 0 `def` removido.

## Métrica de sucesso
Suíte harness-dev no Windows nativo sem atalho: de 20/83 para 83/83 (ou mais testes) passando, skips só com motivo.
Hooks Python que falham fechados sem `python3`: de 0/4 para 4/4. Tools com saída UTF-8 em pipe: de 6/16 para 16/16.

## Aceite da Feature
### Aceite QA — PENDENTE
### Aceite Review — PENDENTE
