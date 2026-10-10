<!-- resume-stamp
FEATURES: win-harness,harness-evolucao
BRANCH: release/version-windows
HEAD: 7aa3cb4
PRODUTO: d2ca7ff1eb9542bb28457db5f95696dcb3113b8e
ESTADO: e56c1d8197fd6711399d35b71ce323840c44ceae
GATE: PENDENTE
-->

# RESUME — codebase-specialists (desenvolvimento)

## Escopo autorizado e limites
- Autorizado (founder, 2026-10-07/08): tornar a skill e o harness compatíveis com Windows ("atacar todas as frentes
  aqui no Windows, inclusive criar a branch release/version-windows"; "use a /auto-correcao"). Branch de trabalho:
  `release/version-windows`.
- Feature `win-harness` (B-15) aberta em 2026-10-09 (D-21), `/tech-lead` AUTÔNOMO em OUTRA sessão; a D-23 reabriu
  03 e 05–08 para corrigir os MENOR de regressão da REVIEW antes do aceite (3/8 hoje). Esta sessão NÃO mexe nela.
- Feature `harness-evolucao` (B-19, D-22) aberta em 2026-10-09 com E1–E5 por DELEGAÇÃO literal do founder; executa
  EM PARALELO com a win-harness (D-24, 2026-10-10), `/tech-lead` em modo AUTÔNOMO ("ok"). Oráculo `e00cf3c5d927`
  (79 testes, 19 CAs) congelado e aprovado pelo founder com a senha (`intake.3` ok). Corretor liberado.
- NÃO autorizado: push (é do founder); hook de aprovação no `~/.claude/settings.json` global (D-18); descartar os
  sujos da win-harness (`_comum.sh`, `package.sh`); publicar pacote; portar/commitar produto antes do aceite do
  founder; mexer em arquivo fora dos `Arquivos permitidos` de cada task (revisão de plano é do founder); editar o
  `.gitignore` fora de uma feature (B-20); mudar o oráculo congelado sem mudança oficial.
- Aguardando decisão do founder (harness-evolucao — travam a execução):
  1. incluir `scripts/memory/tests/test_mem.py` nos Arquivos permitidos da task 06 para atualizar a asserção da
     linha 131 (afirma que lição promovida some do inject — o oposto do CA-05 aprovado); sem isso a suíte memory
     nunca fica verde. → recomendação: sim.
  2. symlink do selftest no Windows (`make_sandbox`, `scripts/harness/engine/selftest.py:89`, WinError 1314): tratar
     na task 07 (arquivo já permitido) reportando o cenário X-01 como "PULADO: symlink indisponível" e selftest exit
     0; a task 07 dizia "symlink fora do escopo" pensando no symlink do install (B-14). → recomendação: sim.
  Também (D-09): custo da campanha do produto antes da medição da B-14; candidatos ao BACKLOG das revisões da
  win-harness (guard-git PowerShell `{ git push }` etc.; `portao.sh --pythons` com espaço; `copia.sh` com barra).

## Onde paramos (2026-10-10)
- `harness-evolucao`: 2/14. 01-TASK-ORACULO DONE (oráculo pelo oraculista; RED medido pelo tech-lead: Windows 55/79,
  WSL 51/79 falhas; 19/19 classes RED). 02-TASK-GRAVADOR-JSON DONE/PASS (2 ciclos; revisor APPROVED; régua WSL 2
  Pythons cslib 28, emit 55, harness 317 OK). 04-TASK-MEMORIA-SEGURANCA (2 ciclos; revisor do ciclo 2 APPROVED com 5
  MENOR) e 07-TASK-SHELL-PORTAVEL (2 ciclos; revisor APPROVED) prontas MAS IN_PROGRESS: a 04 espera a decisão 1
  (memory 39 testes, 1 falha = test_mem.py:131), a 07 espera a decisão 2 (CA-15 4/5 no Windows).
- Tudo na cópia `local/work/harness-evolucao/codebase-specialists/` (HEAD 7aa3cb4 + tasks 02/04/07) — nada portado,
  nada commitado de produto. 3 arquivos que um executor gravou em CRLF (engine.py, selftest.py, tree.py) já foram
  normalizados para LF pelo tech-lead (só fim de linha; testes rerodados OK).

## Próximos passos
1. `/carregar-sessao` → `/tech-lead` (autônomo, só a harness-evolucao). Pergunte ao founder as decisões 1 e 2 acima
   (`ok` aceita as duas) e:
   - decisão 2 = sim ⇒ ciclo 3 da 07 (opus): symlink do `make_sandbox` como PULADO no Windows + endurecer
     `resolve_shell` (só `.exe`, sem diretório atual; MENOR do revisor) + teste do ramo 127 em `g_feat_dor` + tearDown
     dos temporários; depois régua (harness WSL 2 Pythons) + oráculo `-k CA15` no Windows + revisor → DONE.
   - decisão 1 = sim ⇒ marcar a 04 DONE só com a régua memory verde, o que exige a task 06 (test_mem.py:131). Até lá
     a 04 fica IN_PROGRESS; registrar a pendência no Handoff.
2. Próxima onda (depois da 04 e da 07): 05-TASK-MEMORIA-INIT (G1; levar os 5 MENOR da 04 em
   `local/tech-lead/harness-evolucao/04-TASK-MEMORIA-SEGURANCA/menores-para-05-06.txt`) e 08-TASK-CLASSIFY-TEXTOS (G2).
   Todo prompt de executor: "grave em LF" (o Write do agente no Windows gerou CRLF).
3. Founder: push da branch quando quiser. `/install` depois da win-harness.

## Estado do ambiente (esta máquina: Windows 11)
- Sem `python3` nativo: atalho `~/bin/python3` vale no Git Bash, NÃO para subprocess nem PowerShell (lá use
  `python`). Oráculo e testes: `PYTHONDONTWRITEBYTECODE=1 python -B`; oráculo contra a cópia com
  `CS_DEV_SKILL_DIR=<cópia>`. WSL Ubuntu (python3 = /usr/bin/python3 3.10) roda a régua "2 Pythons": harness ~18–27
  min por Python; no Windows nativo a suíte harness passa de 25 min e tem falhas de B-14 (encoding cp1252, termios).
- Aprovação da campanha no Windows: o founder roda os 3 comandos do `local/aprovar-<f>.sh` direto no PowerShell com
  `python` (o `sh` não existe no PowerShell).
- Clone com `core.autocrlf=input`/`core.eol=lf`. `.git/info/exclude` local ignora `evals/fixtures/**/obj/` e
  `**/bin/` (B-20 para versionar). O carimbo PRODUTO ainda muda pelo `obj/` da fixture .NET (não por código).
- Fora do commit (terceiros/locais): `.claude/tools/_comum.sh`, `.claude/tools/package.sh` (da win-harness),
  `.vscode/`, `campanhas/harness-evolucao/` (oráculo congelado; entra no commit da feature),
  `campanhas/win-harness/`, `campanhas/README.md` (linhas das 2 campanhas).
- harness-evolucao: cópia `local/work/harness-evolucao/codebase-specialists/`; retornos, réguas, snapshots, fichas
  e saídas do oráculo em `local/tech-lead/harness-evolucao/`; levantamento em `local/levantamento-evolucao-harness/`;
  propostas da criação em `local/criar-harness-evolucao/`.
- win-harness: cópia `local/work/win-harness/codebase-specialists/` e `local/tech-lead/win-harness/` (da outra sessão).
- Sobras locais das features fechadas (podem ser apagadas): `local/work/win-motor-copia/`, `local/work/win-bash/`,
  `local/portao-win-motor-copia/`, `local/portao-win-bash/`.
- Hook de aprovação: nega comando com a palavra `--gate` junto de muitos outros comandos no mesmo Bash; rode
  `feature.py task marcar` em comando isolado.

## Ponteiros
- harness-evolucao: `.claude/state/features/harness-evolucao/` (FEATURE.md com 19 CAs e decisões da E1; TASKS/;
  HISTORICO; CHECKLIST) · oráculo `campanhas/harness-evolucao/oraculo/` (ESPEC.md tem os nomes fixados por CA).
- Decisões: `DECISIONS.md` (D-17..D-24) · fila: `BACKLOG.md` (B-14..B-20).
- Features entregues: `.claude/state/archive/win-motor-copia/`, `.claude/state/archive/win-bash/` · custo:
  `logs/custo.jsonl`.
