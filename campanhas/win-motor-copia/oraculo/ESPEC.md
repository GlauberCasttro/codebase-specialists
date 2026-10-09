# ESPEC — oráculo da feature win-motor-copia

Oráculo de aceite da feature `win-motor-copia` (motor de campanhas embutido corrigido para Windows). Escrito por um
agente SEPARADO do corretor (quem testa não constrói): não viu a cópia de trabalho, não implementou nada e não congela
o oráculo (o tech-lead congela, com TODOS os arquivos: `ESPEC.md` e `test_win_motor_copia.py`).

Arquivo de testes: `test_win_motor_copia.py` (unittest puro, stdlib, Python 3.9+, LF). Uma classe por CA, com prefixo
que o filtro `-k` do FEATURE.md usa:

| CA | Classe | Prova (`-k`) |
|---|---|---|
| CA-01 | `CA01CopiaFielRastreavelTest` | `python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA01` |
| CA-02 | `CA02FraseESaidaWindowsTest` | idem `-k CA02` |
| CA-03 | `CA03HookPowerShellTest` | idem `-k CA03` |
| CA-04 | `CA04OrigemConfereCheckoutWindowsTest` | idem `-k CA04` |
| CA-05 | `CA05SemRegressaoHarnessTest` | idem `-k CA05` |

## Variáveis e isolamento

- Raiz testada: `ORACULO_SKILL`; senão `CS_SKILL_DIR` (o `portao.sh` passa a cópia limpa por ela e roda o oráculo de
  dentro de `campanhas/<feature>/oraculo`); senão a raiz do projeto (três pastas acima do arquivo de teste).
- Motor testado: `ORACULO_SCRIPTS`, senão `<raiz>/.claude/tools/ac/`.
- Fonte: `ORACULO_FONTE_AC` (raiz do clone do `auto-correcao`); senão `<raiz>/../auto-correcao`; senão
  `<projeto do oráculo>/../auto-correcao` (para o portão, cuja raiz é a cópia limpa em `local/`). A fonte só é lida por
  `git -C <fonte> show 30e2da6:<caminho>` — nunca pela working tree. Fonte ausente ou commit inacessível = FALHA com
  mensagem `fonte do motor ausente/inacessível ... (defina ORACULO_FONTE_AC)` (não pula).
- `HOME`, `USERPROFILE`, `AC_FRASE_FILE`, `AC_AUDIT_LOG` → `tempfile.mkdtemp()` por teste, apagado no fim. O
  `~/.claude` real nunca é tocado. Git só roda em repositórios temporários. Os subprocessos da suíte harness-dev
  (CA04, CA05) recebem `TMP`/`TEMP`/`TMPDIR` dentro do mesmo temporário; a limpeza apaga também arquivos somente-leitura
  (objetos do git no Windows).
- Nenhum teste roda `gate`, `preauth` nem `frase` do `ac.py`: os comandos de aprovação são STRINGS de payload
  entregues ao `decide()` do hook (importlib).

## Como cada CA é verificado

### CA-01 — cópia fiel e rastreável
- `test_frase_hook_e_references_iguais_a_fonte_apos_lf`: `frase.py`, `hook_aprovacao.py` e os 4 `references/*.json5`
  embutidos, normalizados CRLF→LF, têm o mesmo sha256 que `git show 30e2da6:<scripts|references>/...` (subTest por
  arquivo).
- `test_ac_py_difere_so_pelas_2_linhas_do_layout_depois_de_CICLO`: `difflib.SequenceMatcher` (sem autojunk) entre as
  linhas da fonte e do embutido (LF): exatamente UM opcode não-`equal`, que é `insert` na posição logo após a única
  linha da fonte que começa com `CICLO = `, com 2 linhas; o bloco inserido cita `references`.
- `test_origem_cita_commit_e_confere_sha256_dos_7_arquivos`: `ORIGEM.txt` contém `30e2da6`; as linhas
  `<sha256>  <caminho>` antes de `sha256 EMBUTIDO` são os 7 caminhos da fonte (`scripts/ac.py`, `scripts/frase.py`,
  `scripts/hook_aprovacao.py`, `references/{ciclo,formatos,licoes,prompts}.json5`) e conferem com os bytes de
  `git show 30e2da6:<caminho>`; as linhas depois de `sha256 EMBUTIDO` são os 7 caminhos relativos ao motor (`ac.py`,
  `frase.py`, `hook_aprovacao.py`, `references/*.json5`) e conferem com os bytes do arquivo normalizados para LF.

### CA-02 — frase e saída no Windows
Ramo Windows de `frase.py` exercitado por mocks no mesmo arquivo para Windows e WSL (`_windows` → True, `msvcrt`
falso em `sys.modules` com `getwch`/`putwch`, `sys.stdin` falso que reprova qualquer leitura, `os.open` espionado).
- `test_ramo_windows_existe_e_consulta_os_name`: `frase._windows` e `frase._abrir_console` existem; `_windows()` segue
  `os.name` na chamada (`nt` → True, `posix` → False).
- `test_ler_windows_so_pelo_console_sem_eco`: `ler(prompt, contexto)` devolve a frase digitada lendo só por
  `msvcrt.getwch`; não lê `sys.stdin`, não abre `/dev/tty`, não escreve em stdout/stderr; contexto antes do prompt no
  console; depois do prompt só `\r\n` (sem eco); a frase nunca aparece na saída.
- `test_windows_stdin_pipe_semtty_sem_ler_tecla`: stdin não-tty (pipe) → `exigir_tty()` e `ler()` levantam `SemTTY`
  sem consumir tecla.
- `test_windows_stdin_nul_nao_console_semtty`: stdin tty mas não-console (é o caso do `NUL` no Windows): `CONIN$`
  abre (open falso no módulo), `_stdin_e_console` levanta `OSError` (mock) → `SemTTY` em `exigir_tty()` e `ler()`,
  nenhuma tecla lida, e a prova de console foi chamada.
- `test_load_oraculo_stdout_cp1252_sem_pythonutf8` / `test_status_stdout_cp1252_sem_pythonutf8`: campanha temporária
  (`ac.py init` num mkdtemp; intake.1–3 marcadas direto no `state.json`, sem gate); `ac.py load oraculo` e `ac.py status`
  em subprocesso com `PYTHONIOENCODING=cp1252` e SEM `PYTHONUTF8` saem 0, sem `Traceback`/`UnicodeEncodeError`.
- Guarda `test_guarda_stdin_nul_e_pipe_reais_nunca_leem_a_frase`: processo real com stdin NUL e pipe → `exigir_tty()`
  levanta `SemTTY` (passa hoje e depois; RNF-02).

### CA-03 — hook vê o PowerShell neste projeto
- `test_settings_matcher_do_hook_aprovacao_cobre_bash_e_powershell`: em `<raiz>/.claude/settings.json`, todo registro
  `PreToolUse` cujo comando cita `hook_aprovacao.py` tem matcher que, separado por `|`, contém `Bash` e `PowerShell`.
- `test_decide_nega_aprovacao_pela_ferramenta_powershell`: `decide({"tool_name": "PowerShell", ...})` do hook embutido
  NEGA: `python scripts\ac.py --work c gate stop --by f --decision approve`;
  `iex "python scripts\ac.py --work c preauth commit --by f --requires a"`;
  `cmd /c "python scripts\ac.py --work c frase conferir"`;
  `powershell -EncodedCommand <base64 UTF-16LE de python scripts\ac.py --work c gate stop>`.
- `test_selftest_mais_de_83_casos_todos_ok`: `hook_aprovacao.py --selftest` sai 0 e imprime `selftest: N/M ok` com
  N = M e M > 83.
- Guardas: `test_guarda_powershell_git_status_permitido` (PowerShell `git status` permitido) e
  `test_guarda_bash_gate_continua_negado` (Bash `python3 .claude/tools/ac/ac.py ... gate stop ...` negado).

### CA-04 — ORIGEM confere num checkout Windows
Repositório git temporário (`git init`, `core.autocrlf=true`) com o `<raiz>/.gitattributes` (se existir), o conteúdo
de `<motor>` (sem `__pycache__`) em `.claude/tools/ac/` e o `test_harness_dev.py` do projeto em `.claude/tools/tests/`;
commit; `git clone -c core.autocrlf=true` para outro temporário (extração do git, como um clone Windows).
- `test_motor_extraido_com_autocrlf_fica_em_lf`: nenhum arquivo extraído de `.claude/tools/ac/` contém `\r\n`.
- `test_sha256_dos_bytes_extraidos_bate_com_origem_embutido`: o sha256 dos BYTES de cada arquivo extraído bate com a
  lista `sha256 EMBUTIDO` do `ORIGEM.txt` extraído (7 linhas).
- `test_harness_origem_confere_sha256_passa_no_clone`: `python -m unittest
  test_harness_dev.MotorEmbutido.test_origem_confere_sha256` dentro do clone sai 0.
- Guarda `test_guarda_checkout_sem_autocrlf_preserva_lf_do_indice`: o blob no índice é LF (o defeito é só a conversão
  na extração).

### CA-05 — sem regressão no harness
- `test_motor_embutido_da_suite_harness_passa_inteira`: `python -m unittest test_harness_dev.MotorEmbutido` em
  `<raiz>/.claude/tools/tests`, subprocesso sem `PYTHONUTF8`, sai 0.
- Guarda `test_guarda_selftest_do_hook_embutido_sai_0`: o `--selftest` do hook embutido sai 0 (passa hoje e depois).
  Mostra que a classe CA05 não está vermelha por acaso: o hook roda e o subprocesso funciona; o vermelho de hoje é só
  o `test_origem_confere_sha256` (F4).

#### Calibração do CA05 (`PYTHONIOENCODING=utf-8`)
O subprocesso do CA05 (e o do CA04 que roda o teste do harness no clone) remove `PYTHONUTF8` mas fixa
`PYTHONIOENCODING=utf-8`. Motivo medido: o `run()` de `test_harness_dev.py` decodifica a saída dos filhos como UTF-8
estrito; no Windows nativo, sem nenhuma das duas variáveis, `ac.py --help` sai em cp1252 (`mecânico` → `\xe2`) e
`MotorEmbutido.test_help_e_init_com_ciclo_embutido` dá `UnicodeDecodeError` — hoje e também com o motor da fonte, que
escapa só o que não codifica em cp1252 (`errors="backslashreplace"`). Isso é do harness no Windows nativo (B-15,
fora do escopo de escrita desta feature). A saída cp1252 do MOTOR é provada à parte no CA02.

## Resultado hoje (antes da correção)

Medido em 2026-10-08 12:53 -0300, HEAD `e8a9b93`, motor embutido ORIGEM `da3ea45`, sem `.gitattributes`, clone com
`core.autocrlf=true` (motor em CRLF na working tree).
- Windows nativo: Python 3.12.7, Git Bash, `env -u PYTHONUTF8 python -m unittest discover -s
  campanhas/win-motor-copia/oraculo -p "test_*.py" -v` → exit 1, `Ran 21 tests`, `FAILED (failures=26)` (falhas
  contadas por subTest).
- WSL: Python 3.10.12, `env -u PYTHONUTF8 python3 -m unittest discover ...` → exit 1, `Ran 21 tests`,
  `FAILED (failures=26)`.
- Por CA (`-k`), nos dois ambientes: CA01 4 falhas · CA02 6 · CA03 6 · CA04 9 · CA05 1.

| Teste | Windows | WSL | Motivo hoje |
|---|---|---|---|
| CA01 `test_frase_hook_e_references_iguais_a_fonte_apos_lf` | FAIL (frase, hook) | FAIL (frase, hook) | frase/hook são os de `da3ea45`; references já iguais |
| CA01 `test_ac_py_difere_so_pelas_2_linhas_do_layout_depois_de_CICLO` | FAIL | FAIL | 4 blocos de diferença (insert do layout + 3 da fonte nova) |
| CA01 `test_origem_cita_commit_e_confere_sha256_dos_7_arquivos` | FAIL | FAIL | ORIGEM não cita `30e2da6` |
| CA02 `test_ramo_windows_existe_e_consulta_os_name` | FAIL | FAIL | `frase._windows`/`_abrir_console` ausentes |
| CA02 `test_ler_windows_so_pelo_console_sem_eco` | FAIL | FAIL | idem (F1) |
| CA02 `test_windows_stdin_pipe_semtty_sem_ler_tecla` | FAIL | FAIL | idem (F1) |
| CA02 `test_windows_stdin_nul_nao_console_semtty` | FAIL | FAIL | `_stdin_e_console` ausente (F1) |
| CA02 `test_load_oraculo_stdout_cp1252_sem_pythonutf8` | FAIL | FAIL | Traceback `UnicodeEncodeError` (F2) |
| CA02 `test_status_stdout_cp1252_sem_pythonutf8` | FAIL | FAIL | Traceback `UnicodeEncodeError` (F2) |
| CA02 `test_guarda_stdin_nul_e_pipe_reais_nunca_leem_a_frase` | ok | ok | guarda |
| CA03 `test_settings_matcher_do_hook_aprovacao_cobre_bash_e_powershell` | FAIL | FAIL | matcher `Bash` (F3) |
| CA03 `test_decide_nega_aprovacao_pela_ferramenta_powershell` | FAIL (4/4) | FAIL (4/4) | `decide()` ignora `tool_name` PowerShell (F3) |
| CA03 `test_selftest_mais_de_83_casos_todos_ok` | FAIL | FAIL | `83 not greater than 83` |
| CA03 `test_guarda_powershell_git_status_permitido` | ok | ok | guarda |
| CA03 `test_guarda_bash_gate_continua_negado` | ok | ok | guarda |
| CA04 `test_motor_extraido_com_autocrlf_fica_em_lf` | FAIL | FAIL | 8/8 arquivos com CRLF (sem `eol=lf`) |
| CA04 `test_sha256_dos_bytes_extraidos_bate_com_origem_embutido` | FAIL (7/7) | FAIL (7/7) | bytes CRLF ≠ sha EMBUTIDO (`de78cc5a…` ≠ `fbd0f1cd…`) |
| CA04 `test_harness_origem_confere_sha256_passa_no_clone` | FAIL | FAIL | `test_origem_confere_sha256` vermelho no clone |
| CA04 `test_guarda_checkout_sem_autocrlf_preserva_lf_do_indice` | ok | ok | guarda |
| CA05 `test_motor_embutido_da_suite_harness_passa_inteira` | FAIL | FAIL | `test_origem_confere_sha256` (F4, CRLF na working tree) |
| CA05 `test_guarda_selftest_do_hook_embutido_sai_0` | ok | ok | guarda |

Nenhuma falha de hoje é erro de import: o módulo carrega nos dois ambientes; ausências viram `self.fail` com o motivo.

## Calibração (o oráculo passa com a entrega)

Verificado sem tocar o projeto: num temporário fora do repositório, uma árvore simulada com o motor de
`git show 30e2da6:` + as 2 linhas do layout reaplicadas depois de `CICLO = `, um `ORIGEM.txt` com os 14 sha256, um
`.gitattributes` com `.claude/tools/ac/** text eol=lf`, o matcher `Bash|PowerShell` e uma cópia LF do
`test_harness_dev.py`. Rodando como o portão roda (`CS_SKILL_DIR=<árvore>`, de dentro da pasta do oráculo,
`python -m unittest test_win_motor_copia`): Windows nativo `Ran 21 tests ... OK`; WSL `Ran 21 tests ... OK`. O
temporário foi apagado. Também: só o motor da fonte (`ORACULO_SCRIPTS=<fonte>/scripts`) deixa CA02 inteiro verde e CA03
vermelho só no `settings.json` (que é deste projeto).

## Pendências de contrato (para o tech-lead)

1. CA05 e a working tree deste clone: o `.gitattributes` só vale na próxima extração. Os 4 `references/*.json5` (fora
   do Escopo de escrita) e o `ORIGEM.txt` seguem em CRLF na working tree deste clone até um re-checkout do motor; até
   lá `test_origem_confere_sha256` (e portanto o CA05) fica vermelho contra a raiz viva, no Windows e no WSL (mesmos
   arquivos em `/mnt/c`). O portão no Windows também: `git archive HEAD` com `core.autocrlf=true` sai em CRLF (medido:
   90 `\r\n` em `references/ciclo.json5`) e o HEAD ainda não tem o `.gitattributes`. No WSL (`core.autocrlf=input`) o
   archive sai em LF.
2. CA05 fixa `PYTHONIOENCODING=utf-8` (ver "Calibração do CA05"); sem isso o CA05 não fica verde no Windows nativo sem
   mudar `test_harness_dev.py` (B-15).
3. Raiz por `CS_SKILL_DIR` e fonte com segundo fallback (`<projeto do oráculo>/../auto-correcao`): acrescentados para o
   oráculo testar a cópia limpa quando rodar pelo `portao.sh`, que não exporta `ORACULO_SKILL`.
