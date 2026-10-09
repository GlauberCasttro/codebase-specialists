# win-bash — Fechar feature no Windows: bash do Git, nunca o do WSL

FEATURE-ID: win-bash
Nome: Fechar feature no Windows: bash do Git, nunca o do WSL

## História
Como founder desenvolvendo a skill numa máquina Windows, quero que o fechamento de feature rode o
`conferir-commit.sh` pelo bash do Git, para que `fechar check`, `fechar archive` e `fechar commit` funcionem aqui
como no macOS, sem cair no bash do WSL.

## Problema / Contexto
`.claude/tools/feature.py:548` (`conferir_commit`) roda `subprocess.run(["bash", <conferir-commit.sh>, …])`; no
Windows o Python 3.12 acha `C:\Windows\System32\bash.exe` (WSL), que não entende `C:\…` (E2 F1: `fechar check
win-motor-copia` reprova só por isso, com o `conferir-commit.sh` passando pelo Git Bash). `shutil.which("bash")` acha o
Git Bash no Git Bash e no PowerShell (F2); não há contorno de ambiente no Python 3.12 (F3). Única chamada desse tipo
nos tools (F4 descartado); usada pelo gate (`:580`, também no archive) e pelo commit (`:840`).

## Valor de negócio
Destrava o fechamento de toda feature nesta máquina — a começar pela win-motor-copia, aceita e parada no gate.

## Personas / Stakeholders
- founder (fecha features no Windows)
- tech-lead (roda `/fechar-feature`)

## Critérios de Aceitação
- **CA-01 — escolhe um bash fora do System32 no Windows.** DADO `os.name == "nt"` e `shutil.which("bash")` apontando
  para um bash fora de `%SystemRoot%\System32`, QUANDO `feature.bash_exe()` roda, ENTÃO devolve esse caminho; e
  DADO `shutil.which("bash")` dentro do `System32`, ENTÃO esse resultado é descartado.
  Prova: `python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -k CA01`
- **CA-02 — cai no bash do Git quando o PATH só tem o do WSL.** DADO Windows sem bash utilizável no PATH e
  `shutil.which("git")` apontando para `<raiz>\cmd\git.exe` ou `<raiz>\mingw64\bin\git.exe`, QUANDO
  `feature.bash_exe()` roda, ENTÃO devolve `<raiz>\bin\bash.exe` (ou `<raiz>\usr\bin\bash.exe`) se existir.
  Prova: `python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -k CA02`
- **CA-03 — sem bash do Git, recusa clara.** DADO Windows sem bash fora do System32 e sem Git, QUANDO
  `feature.bash_exe()` roda, ENTÃO levanta `feature.Recusa` com mensagem que cita o Git Bash — nunca devolve o WSL.
  Prova: `python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -k CA03`
- **CA-04 — macOS/Linux inalterado.** DADO `os.name != "nt"`, QUANDO `feature.bash_exe()` roda, ENTÃO devolve
  `"bash"` (a mesma busca de hoje), sem consultar `git` nem `SystemRoot`.
  Prova: `python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -k CA04`
- **CA-05 — o conferir-commit roda de verdade.** DADO a máquina real (Windows nesta máquina, Linux no WSL), QUANDO
  `feature.conferir_commit("feature-inexistente", ["x"], <raiz>)` roda, ENTÃO a saída é a do próprio
  `conferir-commit.sh` (ex.: "portão da feature … não existe") e não um erro de bash que não acha o script.
  Prova: `python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -k CA05`

## RNFs
- RNF-01: Python 3.9+ stdlib; oráculo verde no Windows nativo (Git Bash e PowerShell, sem `PYTHONUTF8`) e no WSL.
- RNF-02: nenhum `def` removido; `conferir_commit` mantém assinatura e retorno `(ok, saida)`.

## Edge cases
- `SystemRoot` ausente no ambiente: usa `C:\Windows` como padrão para reconhecer o WSL.
- caminho com maiúsculas/minúsculas diferentes (`C:\WINDOWS\system32\bash.exe`): comparação sem diferenciar caixa.
- Git instalado em pasta com espaço (`C:\Program Files\Git`): o caminho é passado como item da lista, sem shell.

## Dependências
- Nenhuma feature bloqueante. Destrava o fechamento da win-motor-copia.

## Escopo IN
- função `bash_exe()` em `feature.py` e o uso dela em `conferir_commit`; testes unitários dela em `test_feature.py`.

## Escopo OUT
- as 13 chamadas `["bash"…]`/`["sh"…]` nas suítes do harness, `python3` fixo, régua com 2 Pythons, mover a função
  para `estado_lib.py` (B-15); `conferir-commit.sh` e demais tools.

## Escopo de escrita
- `.claude/tools/feature.py`
- `.claude/tools/tests/test_feature.py`

## Critério de parada
oráculo da feature 5/5 CAs verde no Windows nativo (Git Bash e PowerShell, sem PYTHONUTF8) e no WSL; `fechar check
win-motor-copia` sai ok no Windows; suíte harness-dev sem falha nova; 0 `def` removido.

## Métrica de sucesso
Features fechadas pelo `/fechar-feature` nesta máquina: hoje 0 (gate reprova por F1); depois, a win-motor-copia e a
própria win-bash.

## Aceite da Feature
### Aceite QA — PENDENTE
### Aceite Review — PENDENTE
