# win-bash — Fechar feature no Windows: bash do Git, nunca o do WSL

## Resumo
No Windows, `feature.py` chamava `bash` pelo nome para rodar o `conferir-commit.sh`; o Python 3.12 resolve esse nome
para `C:\Windows\System32\bash.exe` (o WSL), que não entende o caminho `C:\…`, e todo `/fechar-feature` reprovava no
gate (a win-motor-copia parou ali, já aceita). A feature cria `bash_exe()` (Windows: bash do PATH fora do System32,
senão o `bash.exe` do Git a partir do `git`, senão recusa clara; fora do Windows: `"bash"`) e a usa em
`conferir_commit`. Oráculo 0/18 → 18/18 no Windows (Git Bash e PowerShell) e no WSL; o `fechar check` da
win-motor-copia passou a sair ok — e as duas features fecharam por ele.

## Critérios de aceite
### CA-01 — escolhe um bash fora do System32 no Windows
DADO `os.name == "nt"` e `shutil.which("bash")` apontando
  para um bash fora de `%SystemRoot%\System32`, QUANDO `feature.bash_exe()` roda, ENTÃO devolve esse caminho; e
  DADO `shutil.which("bash")` dentro do `System32`, ENTÃO esse resultado é descartado.
  Prova: `python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -k CA01`

### CA-02 — cai no bash do Git quando o PATH só tem o do WSL
DADO Windows sem bash utilizável no PATH e
  `shutil.which("git")` apontando para `<raiz>\cmd\git.exe` ou `<raiz>\mingw64\bin\git.exe`, QUANDO
  `feature.bash_exe()` roda, ENTÃO devolve `<raiz>\bin\bash.exe` (ou `<raiz>\usr\bin\bash.exe`) se existir.
  Prova: `python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -k CA02`

### CA-03 — sem bash do Git, recusa clara
DADO Windows sem bash fora do System32 e sem Git, QUANDO
  `feature.bash_exe()` roda, ENTÃO levanta `feature.Recusa` com mensagem que cita o Git Bash — nunca devolve o WSL.
  Prova: `python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -k CA03`

### CA-04 — macOS/Linux inalterado
DADO `os.name != "nt"`, QUANDO `feature.bash_exe()` roda, ENTÃO devolve
  `"bash"` (a mesma busca de hoje), sem consultar `git` nem `SystemRoot`.
  Prova: `python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -k CA04`

### CA-05 — o conferir-commit roda de verdade
DADO a máquina real (Windows nesta máquina, Linux no WSL), QUANDO
  `feature.conferir_commit("feature-inexistente", ["x"], <raiz>)` roda, ENTÃO a saída é a do próprio
  `conferir-commit.sh` (ex.: "portão da feature … não existe") e não um erro de bash que não acha o script.
  Prova: `python -m unittest discover -s campanhas/win-bash/oraculo -p "test_*.py" -k CA05`

## Linha do tempo
- 2026-10-08T21:50:55-0300 · inicio E0
- 2026-10-08T21:52:09-0300 · proposta E1
- 2026-10-08T21:52:44-0300 · aprovacao E1
- 2026-10-08T21:53:17-0300 · proposta E2
- 2026-10-08T21:53:52-0300 · aprovacao E2
- 2026-10-08T21:54:27-0300 · proposta E3
- 2026-10-08T21:54:49-0300 · aprovacao E3
- 2026-10-08T21:55:45-0300 · proposta E4
- 2026-10-08T21:56:25-0300 · aprovacao E4
- 2026-10-08T21:56:26-0300 · proposta E5
- 2026-10-08T22:22:38-0300 · aprovacao E5
- 2026-10-08T22:22:40-0300 · abertura abertura
- [NOTA] 2026-10-08T22:22:40-0300 — Abertura da feature win-bash
- [NOTA] 2026-10-09 — redação de privacidade na E2 aprovada
- [PASS] 01-TASK-ORACULO — 2026-10-09T01:05:56-0300
- [NOTA] 02-TASK-BASH — 2026-10-09T01:06:14-0300
- [PASS] 02-TASK-BASH — 2026-10-09T01:17:13-0300
- [NOTA] 03-TASK-QA — 2026-10-09T01:17:31-0300
- [PASS] 03-TASK-QA — 2026-10-09T03:32:02-0300
- [NOTA] 04-TASK-REVIEW — 2026-10-09T03:32:03-0300
- [PASS] 04-TASK-REVIEW — 2026-10-09T03:48:07-0300

## Tasks
| id | entrega | tipo | grupo | status | gate |
|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da escolha do bash no fechamento | ORACULO | — | DONE | PASS |
| 02-TASK-BASH | bash_exe() no feature.py e conferir_commit usando-a | CORRECAO | G1 | DONE | PASS |
| 03-TASK-QA | Portão, oráculo e o fechamento real da win-motor-copia | QA | — | DONE | PASS |
| 04-TASK-REVIEW | Revisão isolada da escolha do bash | REVIEW | — | DONE | PASS |

### Handoff 01-TASK-ORACULO
- Executor real: subagente general-purpose, model opus (persona oraculista; agente separado). Arquivos:
  `campanhas/win-bash/oraculo/ESPEC.md`, `test_win_bash.py` (LF).
- 18 testes em 5 classes CA01..CA05. Hoje: Windows (Git Bash e PowerShell, 3.12, sem PYTHONUTF8) 18/18 FAIL —
  conferido pelo tech-lead (`FAILED (failures=18)`); WSL 15 FAIL + 2 skip (só-Windows) + CA05 ok (guarda no Linux).
  Motivos: `feature.bash_exe` inexistente (CA01–04); CA05 no Windows cai no WSL (`No such file or directory`).
- Congelado pelo tech-lead: `oracle freeze` → `72f0ba068049` (2 arquivos). Founder aprovou (gate stop,
  oracle:requisito, preauth commit, frase conferida) pelo motor embutido novo no PowerShell (2026-10-09).
- Limites: sem calibração positiva (exigiria protótipo de correção); pendências de contrato no ESPEC (caixa no
  Linux com `.lower()`, ordem `bin` antes de `usr\bin`, detecção por `os.name`).

### Handoff 02-TASK-BASH
- Executor real: subagente general-purpose · sonnet (roteador: executor ciclo 1). Na cópia: `feature.py` — novos
  `bash_exe()` e `dentro_sys32()` antes de `conferir_commit`, que passa a usar `bash_exe()` e devolve
  `(False, str(recusa))` na `Recusa`; `test_feature.py` — classe `BashExe` com 7 testes (árvores falsas em mkdtemp).
- Conferência do tech-lead: escopo por snapshot = os 2 arquivos permitidos (+ `obj/` da fixture .NET, ruído da IDE,
  também no projeto vivo); oráculo contra a cópia Windows 3.12 sem PYTHONUTF8 → OK (18); WSL → 18 OK (2 skips
  só-Windows); `test_feature` Windows (PYTHONUTF8=1) OK (20); régua seletiva `harness-dev` no WSL: 83 OK em python3 e
  /usr/bin/python3, `RESULTADO: VERDE` (base 76); privacidade 0; 0 `def` removido.
- Revisor pontual isolado: general-purpose · sonnet · APPROVED (CA-01..CA-05 PASS por leitura + resultados do
  tech-lead). Ressalvas MENOR: `\\?\`, nomes 8.3 ou `..` não normalizados no `which("bash")` poderiam escapar da
  checagem do System32 (SUSPEITA, improvável); `test_feature.py:271` não afirma que `which` não é chamado no posix.
- Limite: `test_feature` no Windows SEM PYTHONUTF8 tem 1 FAIL + 11 ERROR pré-existentes (helper `run_py`, B-15).

### Handoff 03-TASK-QA
- QA real: subagente general-purpose · sonnet. VEREDITO: ACCEPT.
- Portão (WSL, cópia limpa = HEAD ce19148 + 2 arquivos, python3 e /usr/bin/python3 = 3.10.12):
  `local/portao-win-bash/portao.out` → `RESULTADO: VERDE` + `FIM` (conferido pelo tech-lead; 0 linhas FAIL/ERRO).
  harness-dev 83 OK e oráculo 18 OK (2 skips só-Windows) nos 2 Pythons; todas as suítes do produto OK (skips de base).
- Windows nativo sem PYTHONUTF8: oráculo 18/18 OK no Git Bash e no PowerShell (5/5 CAs). `oracle verify` intacto.
- Ponta a ponta: `fechar check win-motor-copia` com o `feature.py` DA CÓPIA (CS_DEV_SKILL_DIR = projeto vivo) →
  `"ok": true`, `"falhas": []`; com o `feature.py` vivo → reprova só por `conferir_commit` (WSL). Só confere, não escreve.
- Tech-lead conferiu por snapshot que o QA não escreveu na cópia.

### Handoff 04-TASK-REVIEW
- Revisor real: subagente general-purpose · opus · instância nova, modo feature. VEREDITO: APPROVED. CA-01..CA-05 PASS
  no Windows (Git Bash e PowerShell) e no WSL; 10 mutantes da correção — o oráculo mata os 10, os 7 testes novos do
  `test_feature.py` matam 6; ponta a ponta reproduzido (`fechar check win-motor-copia` com o feature.py da cópia → ok;
  com o vivo → reprova por conferir_commit/WSL). Escopo = os 2 arquivos; 0 `def` removido; privacidade 0.
- Findings MENOR (nenhum bloqueante): (1) alias `%LOCALAPPDATA%\Microsoft\WindowsApps\bash.exe` (WSL fora do System32)
  seria escolhido se vier antes no PATH e sem Git Bash no PATH — falha alto, não em silêncio; descartar também
  `WindowsApps` (BACKLOG); (2) `test_feature.py` não prova que `conferir_commit` usa `bash_exe()` (só o oráculo da
  campanha pega) — um teste de argv[0] na régua permanente (BACKLOG/B-15); (3) `test_feature.py:237` linha de ~250
  colunas (cosmético).
- Limite registrado pelo revisor: `fechar check` não é 100% só-leitura — o `ac check intake.3` apensa um evento
  `check` no ledger local da campanha (gitignored); comportamento do motor, anterior à feature.
- Tech-lead conferiu por snapshot que o revisor não escreveu na cópia.

## Como a feature nasceu
### E0 — Pré-condição · CONCLUÍDA 2026-10-08T21:50:55-0300
- Demanda: "fechar feature no Windows: feature.py chama bash pelo nome e cai no bash do WSL (feature.py:548)"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-08T21:52:44-0300
- Produzido: problema enunciado; FEATURE-ID win-bash
- Itens aprovados: 2: função em feature.py; B-15 move para estado_lib
- Aprovação: "ok"
- Sha: 1788df57df98d61de83e1f3e3ac15cea71ef3f6a5b65406f39065205dfc4a4f9
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-08T21:53:52-0300
- Produzido: 1 chamada muda (feature.py:548); F1-F3 (+F4 descartado)
- Medido: 1 chamada nos tools, 13 nos testes (B-15); which(bash)=Git Bash, subprocess bash=WSL rc 2
- Aprovação: "ok"
- Sha: 27c9ee47eeb7f02d707badc3b11705210792c5c50bf6b90bc418e4695a19901f
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-08T21:54:49-0300
- Produzido: FEATURE.md: 5 CAs com Prova; escopo 2 arquivos; contrato PASS
- Aprovação: "ok"
- Sha: a00c671f5932dfde3e113ddd62d828cbeb589ba2a0e94f329d58528e6889dc06
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-08T21:56:25-0300
- Produzido: 4 tasks: ORACULO, BASH (G1), QA, REVIEW; contrato completo PASS, sonda OK
- Aprovação: "ok"
- Sha: c57002f7a22d7b2c6f0e2b777a2b61a917266335d0aaf67a92099d4c915aab83
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-08T22:22:38-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: bf1aae4d2c3eb58d1b495623b9e4e6eef6d9c4077d67a1dd6e4cf5891f9cd096
- Próxima: oráculo por agente separado

### Abertura · 2026-10-08T22:22:40-0300
- Campanha: campanhas/win-bash
- Tasks: 4 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)

## Campanha
- campanha: campanhas/win-bash · etapa do motor: concluida · rodada: 0
- critério de parada: oráculo da feature 5/5 CAs verde no Windows nativo (Git Bash e PowerShell, sem PYTHONUTF8) e no WSL; `fechar check win-motor-copia` sai ok no Windows; suíte harness-dev sem falha nova; 0 `def` removido.
- escopo: .claude/tools/feature.py, .claude/tools/tests/test_feature.py

## Oráculo
- `campanhas/win-bash/oraculo/ESPEC.md`
- `campanhas/win-bash/oraculo/test_win_bash.py`

## Decisões técnicas
- E1: `shutil.which("bash")` descartando o System32 (comparação por `.lower()` com separadores normalizados, para o
  oráculo rodar também no Linux), fallback pela raiz do Git (`bin\bash.exe` antes de `usr\bin\bash.exe`), recusa que
  cita o Git Bash — nunca o WSL em silêncio. Rejeitada a variável obrigatória `CS_DEV_BASH` (exigiria configuração).
- E1: a função fica no `feature.py` (1 arquivo, sem colidir com a win-motor-copia ativa); mover para `estado_lib.py`
  fica para a B-15. Abrir esta mini-feature antes da B-15 (D-20) porque a B-15 colide com a win-motor-copia
  (`settings.json`) e herdaria o mesmo bloqueio; o porte antes do gate faz a própria win-bash fechar.

## Aprendizados
- Python 3.12 no Windows não procura executável na pasta atual: rodar com cwd na pasta do Git Bash não contorna — é
  código, não ambiente.
- O revisor de feature testou com 10 mutantes da correção: o oráculo da campanha matou os 10, mas os 7 testes
  permanentes do `test_feature.py` só 6 (sobrevivem: `["bash"…]` literal no `conferir_commit`, posix consultando
  git/SystemRoot, sem o padrão `C:\Windows`) — a régua permanente precisa de um teste de argv[0] (BACKLOG).
- Termo privado (nome do usuário da máquina num caminho de erro) entrou na proposta E2 e só foi pego no commit do
  estado; redigido com nota no HISTORICO por decisão do founder. O `criar propor` deveria rodar o guard (BACKLOG).
- O tech-lead não lançou as etapas intake..plano no motor durante a execução; o `campanha.py fechar` recusou e elas
  foram registradas no fechamento com os dados reais (base = oráculo antes da correção). O `campanha.py fechar` grava
  a remedição sem nota de qualidade e o motor recusa — a nota real (QA) foi registrada à parte (BACKLOG).
- Alias `%LOCALAPPDATA%\Microsoft\WindowsApps\bash.exe` também é o WSL fora do System32 (achado do revisor; falha
  alto, não em silêncio) — candidato a descarte explícito.

## Arquivos da feature
- `.claude/tools/feature.py`
- `.claude/tools/tests/test_feature.py`

## Aceite da Feature
### Aceite QA — ACCEPT
### Aceite Review — APPROVED
<!-- fechar-feature:archive-completo -->
