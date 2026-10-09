# win-motor-copia — Motor de campanhas embutido corrigido para Windows

## Resumo
O motor de campanhas embutido no harness (`.claude/tools/ac/`) era o de antes das correções do Windows. A feature o
substitui pelo motor de `auto-correcao@30e2da6` (frase pelo console do Windows, stdin de console real, saída cp1252,
hash do oráculo neutro a CRLF, hook de aprovação que analisa a ferramenta PowerShell), reaplica as 2 linhas do layout
embutido, regrava o `ORIGEM.txt`, cria `.gitattributes` com `eol=lf` só para o motor e passa o matcher do hook do
projeto a `Bash|PowerShell`. Oráculo 0/16 → 16/16 (+ 5/5 guardas) no Windows (Git Bash e PowerShell) e no WSL;
portão VERDE com todas as suítes. Prova real: a aprovação da feature win-bash foi feita pelo founder no PowerShell
com este motor embutido.

## Critérios de aceite
### CA-01 — cópia fiel e rastreável
DADO o `auto-correcao` em `30e2da6`, QUANDO se compara o motor embutido com a
  fonte, ENTÃO `frase.py`, `hook_aprovacao.py` e os 4 `references/*.json5` são idênticos byte a byte (após normalizar
  CRLF→LF), o `ac.py` difere SÓ pelas 2 linhas do layout embutido logo depois de `CICLO = ...`, e o `ORIGEM.txt` cita
  `30e2da6` com o sha256 de origem e embutido de cada um dos 7 arquivos.
  Prova: `python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA01`

### CA-02 — frase e saída no Windows
DADO o motor embutido, QUANDO `frase.exigir_tty`/`frase.ler` rodam no ramo
  Windows (console simulado) e `ac.py load oraculo` / `status` rodam com stdout cp1252 sem `PYTHONUTF8`, ENTÃO a frase
  é lida só do console, sem eco (stdin NUL/pipe recusada com SemTTY), e os comandos saem 0 sem traceback.
  Prova: `python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA02`

### CA-03 — hook vê o PowerShell neste projeto
DADO `.claude/settings.json`, QUANDO se lê o registro do
  `hook_aprovacao.py`, ENTÃO o matcher cobre `Bash` e `PowerShell`; e o hook embutido nega `gate`/`preauth`/`frase` via
  ferramenta PowerShell (incluindo `iex`, `cmd /c` e `-EncodedCommand`) com o `--selftest` em mais de 83 casos.
  Prova: `python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA03`

### CA-04 — ORIGEM confere num checkout Windows
DADO um clone com `core.autocrlf=true`, QUANDO o motor é extraído
  do git, ENTÃO os arquivos de `.claude/tools/ac/` ficam em LF (regra `eol=lf` no `.gitattributes`) e
  `MotorEmbutido.test_origem_confere_sha256` passa.
  Prova: `python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA04`

### CA-05 — sem regressão no harness
DADO o motor novo, QUANDO roda a suíte do harness, ENTÃO
  `test_harness_dev.MotorEmbutido` passa inteira e nenhum teste do harness que passava antes passa a falhar.
  Prova: `python -m unittest discover -s campanhas/win-motor-copia/oraculo -p "test_*.py" -k CA05`

## Linha do tempo
- 2026-10-08T12:28:44-0300 · inicio E0
- 2026-10-08T12:29:32-0300 · proposta E1
- 2026-10-08T12:30:07-0300 · aprovacao E1
- 2026-10-08T12:31:57-0300 · proposta E2
- 2026-10-08T12:32:26-0300 · aprovacao E2
- 2026-10-08T12:33:29-0300 · proposta E3
- 2026-10-08T12:39:26-0300 · aprovacao E3
- 2026-10-08T12:41:00-0300 · proposta E4
- 2026-10-08T12:41:27-0300 · aprovacao E4
- 2026-10-08T12:41:50-0300 · proposta E5
- 2026-10-08T12:42:35-0300 · aprovacao E5
- 2026-10-08T12:42:51-0300 · abertura abertura
- [NOTA] 2026-10-08T12:42:51-0300 — Abertura da feature win-motor-copia
- [PASS] 01-TASK-ORACULO — 2026-10-08T14:40:48-0300
- [NOTA] 02-TASK-MOTOR — 2026-10-08T14:42:56-0300
- [NOTA] 03-TASK-MATCHER — 2026-10-08T14:42:57-0300
- [PASS] 02-TASK-MOTOR — 2026-10-08T18:30:48-0300
- [PASS] 03-TASK-MATCHER — 2026-10-08T18:30:50-0300
- [NOTA] 04-TASK-QA — 2026-10-08T18:31:13-0300
- [PASS] 04-TASK-QA — 2026-10-08T20:36:26-0300
- [NOTA] 05-TASK-REVIEW — 2026-10-08T20:36:27-0300
- [PASS] 05-TASK-REVIEW — 2026-10-08T20:46:18-0300

## Tasks
| id | entrega | tipo | grupo | status | gate |
|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da cópia do motor corrigido | ORACULO | — | DONE | PASS |
| 02-TASK-MOTOR | Copiar o motor de 30e2da6, reaplicar o layout, ORIGEM e eol=lf | CORRECAO | G1 | DONE | PASS |
| 03-TASK-MATCHER | Hook de aprovação do projeto vigia também a ferramenta PowerShell | CORRECAO | G2 | DONE | PASS |
| 04-TASK-QA | Portão e oráculo, CA a CA, nos dois ambientes | QA | — | DONE | PASS |
| 05-TASK-REVIEW | Revisão isolada da cópia do motor e do matcher | REVIEW | — | DONE | PASS |

### Handoff 01-TASK-ORACULO
- Executor real: subagente general-purpose, model opus (persona oraculista; agente separado, nunca viu cópia de
  trabalho — não existia). Arquivos: `campanhas/win-motor-copia/oraculo/ESPEC.md`, `test_win_motor_copia.py` (LF).
- Resultado: 21 testes (16 de CA em 5 classes CA01..CA05 + 5 guardas). Hoje, HEAD `e8a9b93`: Windows (3.12, sem
  PYTHONUTF8) `Ran 21 · FAILED (failures=26)` — conferido pelo tech-lead; WSL (3.10) idem (relatório do oraculista).
  Motivos = achados da E2 (F1 `_windows` ausente, F2 UnicodeEncodeError, F3 matcher Bash/decide sem PowerShell/
  selftest 83, F4 sha CRLF, ORIGEM `da3ea45`). Guardas 5/5 verdes. Entrega simulada fora do repo: 21/21 nos 2.
- Congelado pelo tech-lead: `oracle freeze` → `afeac8b409ff` (2 arquivos); `oracle verify` intacto.
- Limites: CA05 na raiz viva depende dos `references/*.json5` em LF (normalizado no ambiente em 2026-10-08);
  `test_help_e_init_com_ciclo_embutido` dá UnicodeDecodeError no Windows sem PYTHONUTF8 (B-15).

### Handoff 02-TASK-MOTOR
- Executor real: subagente general-purpose, model sonnet (roteador: executor ciclo 1). Arquivos (na cópia):
  `.claude/tools/ac/ac.py` (fonte `30e2da6` + 2 linhas do layout, linhas 36–37), `frase.py` e `hook_aprovacao.py`
  (idênticos à fonte), `ORIGEM.txt` (30e2da6; 7+7 sha256; só o ac.py difere), `.gitattributes` (1 regra). Os 4
  `references/*.json5` já estavam em LF e iguais à fonte (não mudaram).
- Conferência do tech-lead: escopo por snapshot = só os arquivos permitidos (+ settings.json da 03; `obj/` da fixture
  .NET é ruído de build da IDE, fora do commit); projeto vivo intacto fora do estado; oráculo inteiro contra a cópia
  Windows 3.12 sem PYTHONUTF8 `Ran 21 · OK`, WSL `Ran 21 · OK`; selftest 135/135; 0 `def` removido; privacidade 0.
- Régua completa (e2e.py, WSL, python3 e /usr/bin/python3): 15 de 17 suítes PASS de primeira; `harness` (2 erros) e
  `scan` (5 falhas) eram IDÊNTICAS no HEAD — causa: `make` ausente no WSL (FileNotFoundError 'make'; `make test`
  unavailable). Founder instalou o `make`; rerodadas HEAD × cópia: `harness` 306 OK (16 skips) e `scan` 90 OK nas duas.
- Executor declarou BLOCKED por `test_help_e_init_com_ciclo_embutido` (UnicodeDecodeError no Windows sem PYTHONUTF8):
  PRÉ-EXISTENTE (mesmo erro no HEAD; helper `run()` de test_harness_dev.py:32 decodifica UTF-8 estrito) → B-15.
- Revisor pontual isolado: general-purpose · opus · APPROVED (CA-01/02/04/05 PASS). Ressalvas MENOR: (1)
  `carimbo.sh:40-41` subconta etapas no Windows (✓ vira `✓`) — PRÉ-EXISTENTE, B-15; (2) `ac.py:174-175` hash
  neutro a CRLF faria reprovar oráculo antigo congelado com bytes CRLF no Windows — SUSPEITA, sem caso nesta máquina.

### Handoff 03-TASK-MATCHER
- Executor real: subagente general-purpose, model haiku (roteador: complexidade baixa válida). Arquivo:
  `.claude/settings.json` da cópia — linha 15 `"matcher": "Bash"` → `"Bash|PowerShell"` (registro do
  `hook_aprovacao.py`); os outros 5 registros intactos.
- Conferência do tech-lead: diff HEAD × cópia = só a linha 15; JSON válido; privacidade 0; oráculo inteiro contra a
  cópia `Ran 21 · OK` (Windows e WSL), incluindo CA-03 completo (matcher + decide PowerShell + selftest 135).
- Régua: a mesma da 02 (completa; `harness`/`scan` verdes depois do `make` no WSL, idênticas ao HEAD).
- Revisor pontual isolado: general-purpose · sonnet · APPROVED, sem findings. Lacuna dele (matcher sem teste ao
  vivo) já tem evidência nesta máquina: na prova da win-hook (2026-10-08), uma sessão `claude -p` com matcher
  `Bash|PowerShell` disparou `PreToolUse:PowerShell` e negou o gate.

### Handoff 04-TASK-QA
- QA real: subagente general-purpose · model sonnet (roteador: qa). VEREDITO: ACCEPT.
- Portão (WSL, cópia limpa = HEAD e8a9b93 + 6 arquivos, python3 e /usr/bin/python3 = 3.10.12):
  `local/portao-win-motor-copia/portao.out` → `RESULTADO: VERDE` + `FIM` (conferido pelo tech-lead). Suítes nos 2
  Pythons: cslib 17, doctests 19, emit 55, facts 6, harness 306 (16 skips de base), interview 8, memory 14, panel 11,
  probes 78, sanitize 8, scan 90 (1 skip), stage 51, team 61, upgrade 8 (7 skips), verify 13, evals 10, harness-dev
  76; oráculo test_win_motor_copia 21 OK.
- Windows nativo (sem PYTHONUTF8), oráculo contra a cópia: Git Bash (Python 3.12) 21/21 OK; PowerShell 5.1 21/21 OK.
  `oracle verify` intacto.
- Matriz: CA-01..CA-05 PASS nos 3 ambientes (WSL portão, Win Git Bash, Win PowerShell).
- Limites: o QA não rodou a suíte completa do produto no Windows nativo (fora da task; B-14/B-15); skips iguais nos
  2 Pythons, não comparados com portão anterior. Tech-lead conferiu por snapshot que o QA não escreveu na cópia.

### Handoff 05-TASK-REVIEW
- Revisor real: subagente general-purpose · opus · instância nova (nunca executou nada na feature), modo feature.
  VEREDITO: APPROVED. Matriz CA-01..CA-05 PASS; cada classe do oráculo verde na cópia e vermelha no HEAD pelo motivo
  (25 falhas no HEAD); selftest 135 contém literalmente os 44 DENY e 30 ALLOW antigos com o mesmo veredito; escopo
  medido por índice temporário = exatamente os 6 arquivos; 0 `def` removido. Tech-lead conferiu por snapshot que o
  revisor não escreveu na cópia.
- Findings (todos MENOR · PRÉ-EXISTENTE, nenhum bloqueante): (1) `hook_aprovacao.py:130` — `ps_lex` trata `{`/`}`
  como separador: `python3 ${AC} gate stop` pela ferramenta PowerShell passa (pelo Bash é negado); limite fora da
  lista DEC-5 do docstring — é do motor (projeto auto-correcao), candidato a item lá; (2) `.claude/settings.json:5`
  — guard-git continua com matcher `Bash`: git push/reset/stash pela ferramenta PowerShell não passam pelo guard —
  candidato a explicitar na B-15; (3) `carimbo.sh:40-41` — já ressalvado na 02 (B-15).
- Limites: matcher sem teste ao vivo nesta revisão (evidência ao vivo: prova da win-hook); frase no console real só
  por mocks — o critério do B-16 "frase/gate no PowerShell deste projeto" depende do founder.

## Como a feature nasceu
### E0 — Pré-condição · CONCLUÍDA 2026-10-08T12:28:44-0300
- Demanda: "recopiar o motor corrigido no Windows (auto-correcao release/version-windows) para .claude/tools/ac/ (B-16)"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-08T12:30:07-0300
- Produzido: problema enunciado; FEATURE-ID win-motor-copia
- Itens aprovados: 3: matcher do hook do projeto para Bash|PowerShell; python3 do comando fica para B-15
- Aprovação: "ok"
- Sha: 6a5e7f19c29f27a16acaf6955fa1c60a12dd02be30c3362d0ed12cf022b0421f
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-08T12:32:26-0300
- Produzido: investigação medida: 5 arquivos mudam, 4 references iguais, 10 consumidores intactos; F1-F5 (+F6 descartado)
- Medido: fonte +440/-44 em 3 arquivos; 8/8 arquivos do motor w/crlf; test_origem vermelho hoje (de78cc5a != fbd0f1cd); selftest 83/83
- Aprovação: "ok"
- Sha: 6d079be6d6657b3835b8085e06a2ae955bed11ade5a7062bbf25911e0c275c31
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-08T12:39:26-0300
- Produzido: FEATURE.md: 5 CAs com Prova, escopo 6 arquivos, parada numérica; contrato PASS
- Aprovação: "ok"
- Sha: 1a993d1e5f27768f079deee4eb1aa35659f36d3a73aa971220295e176626c012
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-08T12:41:27-0300
- Produzido: 5 tasks: ORACULO, MOTOR (G1), MATCHER (G2), QA, REVIEW; contrato completo PASS, sonda OK
- Aprovação: "ok"
- Sha: 65728f316db278b332625c7bbdb3ed0b39c52873f6e649eebc7cd442782de3d2
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-08T12:42:35-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: dc650596069298825d9436486f043833f8e71fc246639844ab6284aee48f5cea
- Próxima: oráculo por agente separado

### Abertura · 2026-10-08T12:42:51-0300
- Campanha: campanhas/win-motor-copia
- Tasks: 5 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)

## Campanha
- campanha: campanhas/win-motor-copia · etapa do motor: concluida · rodada: 0
- critério de parada: oráculo da feature 5/5 CAs verde no Windows nativo (Git Bash e PowerShell, sem PYTHONUTF8) e no WSL; suíte harness-dev sem nenhuma falha nova; hook --selftest com mais de 83 casos todos ok; 0 `def` removido.
- escopo: .claude/tools/ac/ac.py, .claude/tools/ac/frase.py, .claude/tools/ac/hook_aprovacao.py, .claude/tools/ac/ORIGEM.txt, .claude/settings.json, .gitattributes

## Oráculo
- `campanhas/win-motor-copia/oraculo/ESPEC.md`
- `campanhas/win-motor-copia/oraculo/test_win_motor_copia.py`

## Decisões técnicas
- E1/D-19: copiar de `30e2da6` (branch `release/version-windows`, antes do merge no main), reaplicar as 2 linhas do
  layout aqui (a fonte ainda só procura `references/` na pasta-pai), e trocar só o matcher do hook (o `python3` do
  comando fica para a B-15).
- E2 F4 → `.gitattributes` mínimo (`.claude/tools/ac/** text eol=lf`): o teste do ORIGEM compara bytes e o checkout
  com `core.autocrlf=true` punha CRLF; o `.gitattributes` do repositório inteiro é da B-15.
- Fechamento: o gate parou por `feature.py:548` (bash do WSL); resolvido pela mini-feature win-bash (D-20), fechada
  antes desta.

## Aprendizados
- A campanha foi aberta pelo Python do Windows: o estado guarda caminhos `C:\…`, e o WSL deixou de servir para aprovar;
  as aprovações foram pelo juiz corrigido do `auto-correcao` no PowerShell (motor de mesma versão do copiado).
- Régua completa no WSL sobre `/mnt/c` leva ~1h30; 7 falhas em `harness`/`scan` eram `make` ausente (idênticas no
  HEAD) — o founder instalou o `make`; dependência não declarada (B-17).
- Executor declarou BLOCKED por uma falha pré-existente (UnicodeDecodeError do helper de teste sem PYTHONUTF8, B-15);
  o revisor confirmou rodando o mesmo teste no HEAD. Comparar com o HEAD antes de aceitar um BLOCKED.
- O IDE (.NET) recompila `evals/…/legacy-dotnet/obj/` dentro das cópias de trabalho: ruído no snapshot, fora do commit.
- O tech-lead não lançou intake..plano no motor durante a execução; registrado no fechamento com os dados reais.
- Revisão final: hook novo deixa passar `python3 ${AC} gate …` pela ferramenta PowerShell (`{}` como separador) e
  nega `python -c "…;…"` no PowerShell (falso positivo); guard-git ainda só com matcher `Bash` (B-18).

## Arquivos da feature
- `.claude/tools/ac/ac.py`
- `.claude/tools/ac/frase.py`
- `.claude/tools/ac/hook_aprovacao.py`
- `.claude/tools/ac/ORIGEM.txt`
- `.gitattributes`
- `.claude/settings.json`

## Aceite da Feature
### Aceite QA — ACCEPT
### Aceite Review — APPROVED
<!-- fechar-feature:archive-completo -->
