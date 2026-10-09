<!-- resume-stamp
FEATURES: win-motor-copia,win-bash
BRANCH: release/version-windows
HEAD: e8a9b93
PRODUTO: e84b0c89b68ed53af35809c0af21103e1f4682f8
ESTADO: 2f8e5de5a70206b04945780e4143baddfd17c434
GATE: PENDENTE
-->

# RESUME — codebase-specialists (desenvolvimento)

## Escopo autorizado e limites
- Autorizado (founder, 2026-10-07/08): tornar a skill e o harness compatíveis com Windows ("atacar todas as frentes
  aqui no Windows, inclusive criar a branch release/version-windows"; "use a /auto-correcao"). Branch de trabalho:
  `release/version-windows`.
- Aceite dado: win-motor-copia ("ok", 2026-10-08). Modo de execução das features: autônomo.
- NÃO autorizado: push (é do founder); hook de aprovação no `~/.claude/settings.json` global (D-18: só por projeto);
  descartar os 2 arquivos sujos do harness (`_comum.sh`, `package.sh`) sem o founder decidir; publicar pacote.
- Aguardando decisão: os 2 arquivos sujos (`$PY` em `_comum.sh`/`package.sh` — recomendação: descartar e fazer a
  troca pela feature B-15); custo da campanha do produto (D-09) antes da medição.

## Onde paramos (2026-10-09)
- Duas features ativas (limite 2/2), na branch `release/version-windows`, NADA commitado ainda:
  - `win-motor-copia` (B-16) — 5/5 tasks DONE/PASS, QA ACCEPT, Review APPROVED, ACEITE DO FOUNDER DADO ("ok").
    Os 6 arquivos já foram PORTADOS ao projeto (motor de `auto-correcao@30e2da6` em `.claude/tools/ac/`, `ORIGEM.txt`,
    `.gitattributes`, matcher `Bash|PowerShell` no `.claude/settings.json`). O `/fechar-feature` PAROU no passo 1:
    `fechar check` reprova só por `conferir_commit` — `feature.py:548` chama `bash` pelo nome e no Windows cai no
    bash do WSL (o `conferir-commit.sh` passa pelo Git Bash: 6 arquivos = portão VERDE).
  - `win-bash` — aberta para destravar isso (D-20): `bash_exe()` em `feature.py`. Oráculo congelado (`72f0ba068049`,
    18 testes, vermelhos no Windows). AGUARDA o founder rodar `local\aprovar-win-bash.ps1` no PowerShell — primeira
    aprovação com o motor embutido novo (prova real da win-motor-copia).

## Próximos passos
1. Founder: `powershell -ExecutionPolicy Bypass -File local\aprovar-win-bash.ps1` (a partir da raiz do projeto).
2. `/tech-lead` (modo autônomo, já escolhido): 02-TASK-BASH na cópia (`bash .claude/tools/copia.sh win-bash`) →
   régua → revisor → 03-TASK-QA (portão no WSL + `feature.py fechar check win-motor-copia` com o feature.py
   corrigido) → 04-TASK-REVIEW → aceite do founder → `/fechar-feature win-bash` (porta antes do gate, então fecha) →
   retomar `/fechar-feature win-motor-copia` do passo 1 (o founder roda a conferência da frase no passo 2).
3. Depois: B-15 (harness no Windows) e B-14 (produto no Windows); custo confirmado com o founder antes (D-09).

## Estado do ambiente (esta máquina: Windows 11)
- Sem `python3` nativo: atalho local `~/bin/python3` (sh → Python 3.12 com `PYTHONUTF8=1`) faz hooks e scripts
  rodarem no Git Bash; NÃO vale para subprocess do Python nem para o PowerShell. WSL Ubuntu (python3 3.10; `make`
  instalado pelo founder em 2026-10-08) roda o portão e a régua — lento sobre `/mnt/c` (~1h30 a régua completa).
- Clone com `core.autocrlf=input`/`core.eol=lf` (local) e arquivos convertidos para LF em 2026-10-08 (conteúdo igual
  ao índice; os `.sh` quebravam no WSL).
- Fora do commit: `.claude/tools/_comum.sh` e `.claude/tools/package.sh` (troca para `$PY`, anterior à sessão;
  convertidos para LF); `.vscode/`; `obj/` da fixture .NET (`evals/fixtures/py-billing/…/legacy-dotnet/obj/`, build da
  IDE, recriado por um processo `dotnet`). Os 6 arquivos portados entram no commit da win-motor-copia.
- Cópia de trabalho `local/work/win-motor-copia/`; portão `local/portao-win-motor-copia/` (VERDE).
- O hook de aprovação NOVO já vale nesta sessão (selftest 135); nega no PowerShell `python -c "…;…"` por "aninhamento
  profundo" (falso positivo) — use script em arquivo.
- Skill não instalada aqui (`~/.claude/skills/codebase-specialists` ausente): `/install` depende de link (B-15).

## Ponteiros
- Auditoria: `local/auditoria-windows-2026-10-07.md` · motor: projeto `auto-correcao`, `campanhas/win-motor` e
  `campanhas/win-hook` (BACKLOG de lá: AC-24/25/26 pendentes).
- Decisões: `DECISIONS.md` (D-17..D-20) · fila: `BACKLOG.md` (B-14..B-18).
- Features: `.claude/state/features/win-motor-copia/`, `.claude/state/features/win-bash/` · custo: `logs/custo.jsonl`.
