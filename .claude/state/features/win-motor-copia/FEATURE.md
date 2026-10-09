# win-motor-copia — Motor de campanhas embutido corrigido para Windows

FEATURE-ID: win-motor-copia
Nome: Motor de campanhas embutido corrigido para Windows

## História
Como founder desenvolvendo a skill numa máquina Windows, quero que o motor de campanhas embutido neste harness seja
o motor corrigido do `auto-correcao` (`30e2da6`), para abrir, aprovar e fechar features pelo PowerShell sem a WSL e
com o hook de aprovação vigiando também a ferramenta PowerShell.

## Problema / Contexto
O motor embutido (`.claude/tools/ac/`, ORIGEM `da3ea45`) é o de antes das campanhas win-motor e win-hook. E2:
F1 — `frase.py:187-239` só lê a frase por `/dev/tty`+`termios` (abertura da campanha impossível no PowerShell);
F2 — `ac.py:952`/`:929` quebram com stdout cp1252; F3 — `hook_aprovacao.py:259` e `.claude/settings.json:15`
(`"matcher": "Bash"`) deixam a ferramenta PowerShell sem análise; F4 — `test_harness_dev.py:451`
(`test_origem_confere_sha256`) já falha neste clone porque o checkout com `core.autocrlf=true` pôs CRLF nos 8
arquivos do motor (`de78cc5a…` ≠ `fbd0f1cd…`); F5 — a fonte ainda precisa das 2 linhas do layout embutido.
Fonte: `auto-correcao`, branch `release/version-windows`, commit `30e2da6` (+440/−44 em 3 arquivos; `references/` igual).

## Valor de negócio
Destrava as features seguintes do Windows (B-15 harness, B-14 produto) no fluxo normal deste projeto e fecha, aqui,
a janela em que um agente aprovaria pela ferramenta PowerShell sem ser barrado pelo hook.

## Personas / Stakeholders
- founder (aprova portões no PowerShell com a frase; dono das decisões E1–E5)
- agente executor/tech-lead (usa o motor; passa a ser barrado também pela ferramenta PowerShell)
- projeto `auto-correcao` (fonte do motor; nada muda lá)

## Critérios de Aceitação
- **CA-01 — cópia fiel e rastreável.** DADO o `auto-correcao` em `30e2da6`, QUANDO se compara o motor embutido com a
  fonte, ENTÃO `frase.py`, `hook_aprovacao.py` e os 4 `references/*.json5` são idênticos byte a byte (após normalizar
  CRLF→LF), o `ac.py` difere SÓ pelas 2 linhas do layout embutido logo depois de `CICLO = ...`, e o `ORIGEM.txt` cita
  `30e2da6` com o sha256 de origem e embutido de cada um dos 7 arquivos.
  Prova: `python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA01`
- **CA-02 — frase e saída no Windows.** DADO o motor embutido, QUANDO `frase.exigir_tty`/`frase.ler` rodam no ramo
  Windows (console simulado) e `ac.py load oraculo` / `status` rodam com stdout cp1252 sem `PYTHONUTF8`, ENTÃO a frase
  é lida só do console, sem eco (stdin NUL/pipe recusada com SemTTY), e os comandos saem 0 sem traceback.
  Prova: `python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA02`
- **CA-03 — hook vê o PowerShell neste projeto.** DADO `.claude/settings.json`, QUANDO se lê o registro do
  `hook_aprovacao.py`, ENTÃO o matcher cobre `Bash` e `PowerShell`; e o hook embutido nega `gate`/`preauth`/`frase` via
  ferramenta PowerShell (incluindo `iex`, `cmd /c` e `-EncodedCommand`) com o `--selftest` em mais de 83 casos.
  Prova: `python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA03`
- **CA-04 — ORIGEM confere num checkout Windows.** DADO um clone com `core.autocrlf=true`, QUANDO o motor é extraído
  do git, ENTÃO os arquivos de `.claude/tools/ac/` ficam em LF (regra `eol=lf` no `.gitattributes`) e
  `MotorEmbutido.test_origem_confere_sha256` passa.
  Prova: `python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA04`
- **CA-05 — sem regressão no harness.** DADO o motor novo, QUANDO roda a suíte do harness, ENTÃO
  `test_harness_dev.MotorEmbutido` passa inteira e nenhum teste do harness que passava antes passa a falhar.
  Prova: `python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA05`

## RNFs
- RNF-01: Python 3.9+ stdlib; oráculo verde no Windows nativo (Python 3.12, Git Bash e PowerShell, sem `PYTHONUTF8`)
  e no WSL (python3 3.10). O portão deste harness exige 2 Pythons POSIX: roda no WSL (B-15 trata o nativo).
- RNF-02: a frase nunca é impressa, gravada ou pedida no chat; nenhum teste roda `gate`/`preauth`/`frase` de verdade.
- RNF-03: nada fora do Escopo de escrita muda; nenhum `def` removido; comportamento no macOS/Linux = o da fonte.

## Edge cases
- clone já existente com CRLF: depois da feature, um `git add --renormalize` (ou checkout) deixa o motor em LF.
- `references/` não muda: o ORIGEM continua listando os 4 com o mesmo sha.
- campanha antiga aberta com o motor velho: o formato do estado não mudou (só hash neutro a CRLF, igual para LF).

## Dependências
- `auto-correcao@30e2da6` disponível localmente (clone irmão em `../auto-correcao`, branch publicada).
- Nenhuma feature ativa bloqueante.

## Escopo IN
- copiar `ac.py`, `frase.py`, `hook_aprovacao.py` da fonte e reaplicar o layout; regravar `ORIGEM.txt`;
- matcher do hook em `.claude/settings.json`; regra `eol=lf` só para `.claude/tools/ac/**` no `.gitattributes`.

## Escopo OUT
- `python3` no comando do hook e nos demais tools, régua/portão com 2 Pythons, `.gitattributes` do repositório
  inteiro (B-15); produto `scripts/` (B-14); mudar o motor (é do `auto-correcao`); publicar pacote.

## Escopo de escrita
- `.claude/tools/ac/ac.py`
- `.claude/tools/ac/frase.py`
- `.claude/tools/ac/hook_aprovacao.py`
- `.claude/tools/ac/ORIGEM.txt`
- `.claude/settings.json`
- `.gitattributes`

## Critério de parada
oráculo da feature 5/5 CAs verde no Windows nativo (Git Bash e PowerShell, sem PYTHONUTF8) e no WSL; suíte
harness-dev sem nenhuma falha nova; hook --selftest com mais de 83 casos todos ok; 0 `def` removido.

## Métrica de sucesso
`test_origem_confere_sha256` verde neste clone Windows (hoje vermelho) e 3 de 3 bloqueios do Windows (frase no
console, saída cp1252, hook PowerShell) resolvidos no motor embutido (hoje 0 de 3).

## Aceite da Feature
### Aceite QA — ACCEPT
QA: subagente general-purpose · sonnet (2026-10-08). Matriz: CA-01..CA-05 PASS no portão WSL (2 Pythons), no Windows
Git Bash e no Windows PowerShell (sem PYTHONUTF8). Portão: `local/portao-win-motor-copia/portao.out` →
`RESULTADO: VERDE` / `FIM` (17 suítes + harness-dev + oráculo 21/21 nos 2 Pythons).
### Aceite Review — APPROVED
Revisor: subagente general-purpose · opus, instância nova, modo feature (2026-10-08). Matriz CA-01..CA-05 PASS (verde
na cópia, vermelho no HEAD pelo motivo). 3 findings MENOR · PRÉ-EXISTENTE (hook `${AC}` pelo PowerShell; guard-git só
`Bash`; carimbo no Windows) — candidatos ao BACKLOG, nenhum bloqueante. Revisão por instância isolada, não humana.
