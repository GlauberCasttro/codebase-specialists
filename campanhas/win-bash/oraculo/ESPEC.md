# ESPEC — oráculo da feature win-bash

Oráculo de aceite da feature `win-bash`: no Windows, o fechamento de feature roda o `conferir-commit.sh` pelo bash
do Git, nunca pelo do WSL (`C:\Windows\System32\bash.exe`). Escrito por um agente SEPARADO do corretor (quem testa não
constrói): não implementou nada, não escreveu protótipo de correção e não congela o oráculo (o tech-lead congela, com
TODOS os arquivos: `ESPEC.md` e `test_win_bash.py`).

Arquivo de testes: `test_win_bash.py` (unittest puro, stdlib, Python 3.9+, LF). Uma classe por CA, com o prefixo que
o filtro `-k` do FEATURE.md usa:

| CA | Classe | Testes | Prova |
|---|---|---|---|
| CA-01 | `CA01BashForaDoSystem32` | 5 (2 só no Windows) | `python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -k CA01` |
| CA-02 | `CA02BashDoGitQuandoPathSoTemWsl` | 7 | idem `-k CA02` |
| CA-03 | `CA03RecusaSemBashDoGit` | 3 | idem `-k CA03` |
| CA-04 | `CA04ForaDoWindowsInalterado` | 2 | idem `-k CA04` |
| CA-05 | `CA05ConferirCommitRodaDeVerdade` | 1 | idem `-k CA05` |

## Contrato testado (fixado pelo tech-lead)

- `feature.bash_exe()` → `str`: o caminho do bash ou `"bash"`. Falha = levanta `feature.Recusa` com mensagem que
  cita "Git Bash" (comparação sem diferenciar caixa).
- No Windows (`os.name == "nt"`): (1) `shutil.which("bash")` se NÃO estiver dentro de `%SystemRoot%\System32`
  (comparação sem diferenciar caixa; `SystemRoot` ausente ⇒ `C:\Windows`); (2) senão, a partir de
  `shutil.which("git")` (`<raiz>\cmd\git.exe` ou `<raiz>\mingw64\bin\git.exe`), o primeiro que existir entre
  `<raiz>\bin\bash.exe` e `<raiz>\usr\bin\bash.exe`; (3) senão `Recusa`.
- Fora do Windows: devolve `"bash"`, sem consultar `which("git")` nem `SystemRoot`.
- `feature.conferir_commit(fid, arqs, r)` mantém o retorno `(ok: bool, saida: str)`.

## Variáveis e isolamento

- Raiz testada: `ORACULO_SKILL`; senão `CS_SKILL_DIR` (o portão passa a cópia limpa por ela); senão três pastas acima
  do arquivo de teste. O `feature.py` é carregado por `importlib` de `<raiz>/.claude/tools/feature.py`, com
  `<raiz>/.claude/tools` no `sys.path` (ele importa `contrato` e `estado_lib`). Se o import falhar, ou se
  `feature.bash_exe` não existir, cada teste FALHA (`self.fail`) com a mensagem e o caminho — não dá erro de import.
- CA01–CA04: `unittest.mock.patch.object` em `feature.os.name`, `feature.shutil.which` (resposta por nome: `bash`/`git`,
  com ou sem `.exe`) e `mock.patch.dict` em `os.environ` (`SystemRoot` e `SYSTEMROOT` com o mesmo valor — no Linux as
  chaves diferenciam caixa). As árvores falsas são REAIS num `tempfile.mkdtemp()` (arquivos `.exe` vazios), apagado no
  fim: a correção pode testar existência como quiser (`isfile`, `exists`, `access`).
- Árvore de cada teste: `<tmp>/Windows` (= `SystemRoot`), `<tmp>/WINDOWS/system32/bash.exe` (o "WSL", mesma pasta com
  outra caixa), `<tmp>/Git/{cmd/git.exe | mingw64/bin/git.exe | bin/bash.exe | usr/bin/bash.exe}` conforme o caso.
  Caminhos com separador NATIVO, para os mesmos testes valerem no Windows e no Linux (com `os.name` simulado).
- Comparação de caminho: `os.path.normcase(os.path.normpath(...))`.
- CA05: sem mock da plataforma; só tira `CS_DEV_WS` do ambiente (desviaria a área de trabalho do script). Não escreve
  nada: o `conferir-commit.sh` só lê.
- Nenhum teste roda `gate`, `preauth` nem `frase`, nem escreve no projeto. O `discover` gera `__pycache__/` ao importar o
  módulo de teste (ignorado pelo `.gitignore`); rode com `python -B` para não gerar.

## Como cada CA é verificado

### CA-01 — escolhe um bash fora do System32 no Windows
- `test_bash_do_path_fora_do_system32_e_devolvido`: `which("bash")` = `<tmp>/Git/usr/bin/bash.exe`, sem git ⇒ devolve
  esse caminho, sem `Recusa`.
- `test_bash_do_system32_com_outra_caixa_e_descartado`: `SystemRoot=<tmp>/Windows`, `which("bash")` =
  `<tmp>/WINDOWS/system32/bash.exe`, git em `<tmp>/Git/cmd/git.exe` com `bin/bash.exe` ⇒ devolve o bash do Git (o do
  System32 é descartado sem diferenciar caixa).
- `test_bash_do_system32_sem_git_nao_e_devolvido`: idem sem git ⇒ não devolve o do System32 (recusa).
- `test_literal_windows_system32_maiusculo_descartado` (só Windows): `which("bash")` = `C:\WINDOWS\system32\bash.exe`,
  `SystemRoot=C:\Windows`, git na árvore falsa ⇒ bash do Git.
- `test_sem_systemroot_usa_c_windows` (só Windows): sem `SystemRoot`, `which("bash")` = `C:\Windows\System32\bash.exe`,
  sem git ⇒ recusa (o padrão `C:\Windows` reconhece o WSL).
- Os dois "só Windows" pulam onde `os.sep != "\\"` (no Linux não há como expressar `C:\...` com o `os.path` nativo).

### CA-02 — cai no bash do Git quando o PATH só tem o do WSL
`which("bash")` = o "WSL" da árvore (ou `None`), `which("git")` dentro de `<tmp>/Git`:
- `cmd/git.exe` + `bin/bash.exe` ⇒ `bin/bash.exe`; `mingw64/bin/git.exe` + `bin/bash.exe` ⇒ `bin/bash.exe`;
- `cmd/git.exe` + só `usr/bin/bash.exe` ⇒ `usr/bin/bash.exe`; `mingw64/bin/git.exe` + só `usr/bin` ⇒ `usr/bin`;
- os dois existem ⇒ `bin/bash.exe` (ordem do contrato);
- `which("bash")` = `None` ⇒ `bin/bash.exe`;
- raiz com espaço (`<tmp>/Program Files/Git`) ⇒ `usr/bin/bash.exe`.
Em todos: sem `Recusa`, e o resultado não é o do System32.

### CA-03 — sem bash do Git, recusa clara
Ambiente `nt`; `res` é `None`, levanta `feature.Recusa` e a mensagem contém "git bash" (sem caixa); nada do System32:
- só o "WSL" no PATH, sem git; nada no PATH; git em `cmd/git.exe` mas sem `bin/bash.exe` nem `usr/bin/bash.exe`.
- Consequência do contrato: um fallback fixo (ex.: `C:\Program Files\Git\bin\bash.exe`) fora dos 3 passos reprova aqui.

### CA-04 — macOS/Linux inalterado
- `test_posix_devolve_bash_sem_consultar_git`: `os.name="posix"`, git e bash existentes na árvore ⇒ devolve `"bash"`
  e a lista de chamadas do `which` mockado não contém `git`.
- `test_posix_nao_le_systemroot`: `os.environ` trocado por um espião (dict) que anota leitura de `SystemRoot` (qualquer
  caixa) por `[]`, `get` e `in` ⇒ devolve `"bash"` e nenhuma leitura anotada.

### CA-05 — o conferir-commit roda de verdade
- `test_portao_ausente_mensagem_do_proprio_script`: pré-condição `<raiz>/local/portao-feature-inexistente-win-bash`
  ausente; `feature.conferir_commit("feature-inexistente-win-bash", ["x"], <raiz>)` ⇒ tupla de 2, `ok is False`, a
  saída NÃO contém `No such file or directory` e CONTÉM `portão da feature feature-inexistente-win-bash não existe`
  (frase do `die` em `conferir-commit.sh:21`).
- No Windows prova a correção (hoje cai no WSL). No Linux/WSL é GUARDA: passa hoje e deve continuar passando.

## Resultado hoje (antes da correção) — medido em 2026-10-08

Comandos:
- Windows/Git Bash: `cd <raiz> && env -u PYTHONUTF8 python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -v` (Python 3.12.7)
- Windows/PowerShell: o mesmo, com `PYTHONUTF8` removido do ambiente (Python 3.12.7)
- WSL: `python3 -m unittest discover ...` em `/mnt/c/.../codebase-specialists` (Python 3.10.12)

| Teste | Win Git Bash | Win PowerShell | WSL |
|---|---|---|---|
| CA01 `test_bash_do_path_fora_do_system32_e_devolvido` | FAIL¹ | FAIL¹ | FAIL¹ |
| CA01 `test_bash_do_system32_com_outra_caixa_e_descartado` | FAIL¹ | FAIL¹ | FAIL¹ |
| CA01 `test_bash_do_system32_sem_git_nao_e_devolvido` | FAIL¹ | FAIL¹ | FAIL¹ |
| CA01 `test_literal_windows_system32_maiusculo_descartado` | FAIL¹ | FAIL¹ | skip |
| CA01 `test_sem_systemroot_usa_c_windows` | FAIL¹ | FAIL¹ | skip |
| CA02 (7 testes) | 7 FAIL¹ | 7 FAIL¹ | 7 FAIL¹ |
| CA03 (3 testes) | 3 FAIL¹ | 3 FAIL¹ | 3 FAIL¹ |
| CA04 (2 testes) | 2 FAIL¹ | 2 FAIL¹ | 2 FAIL¹ |
| CA05 `test_portao_ausente_mensagem_do_proprio_script` | FAIL² | FAIL² | ok (guarda) |
| **Total** | 18 run, 18 FAIL, RC 1 | 18 run, 18 FAIL, RC 1 | 18 run, 15 FAIL, 2 skip, 1 ok, RC 1 |

Por filtro no Git Bash: `-k CA01` 5/5 FAIL · `-k CA02` 7/7 · `-k CA03` 3/3 · `-k CA04` 2/2 · `-k CA05` 1/1.

¹ `AssertionError: feature.bash_exe() não existe em <raiz>\.claude\tools\feature.py (contrato: bash_exe() -> str; falha = feature.Recusa)` — o defeito: a função não existe.
² `'No such file or directory' unexpectedly found in '/bin/bash: C:Users<usuário>…conferir-commit.sh: No such file or directory'` — o `["bash", …]` do `feature.py:548` cai no bash do WSL (E2 F1).

Calibração da frase do CA05 (medição, sem tocar o `feature.py`): no Git Bash,
`CS_DEV_SKILL_DIR='C:\…\codebase-specialists' bash .claude/tools/conferir-commit.sh feature-inexistente-win-bash -- x`
⇒ `ERRO: portão da feature feature-inexistente-win-bash não existe: C:\…/local/portao-feature-inexistente-win-bash/portao.out`, RC 1.
No WSL o CA05 passa hoje com a mesma frase.

## Esperado depois da correção

- Windows (Git Bash e PowerShell, sem `PYTHONUTF8`): 18 ok.
- WSL/Linux: 16 ok, 2 skip (os dois literais do Windows).
