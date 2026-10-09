<!-- resume-stamp
FEATURES: —
BRANCH: release/version-windows
HEAD: 5c571de
PRODUTO: 5305e061d87a13267592d05a82b75611670fe01a
ESTADO: 89b12323386ed0912cc10f6be5ee8f3992a3a2f5
GATE: —
-->

# RESUME — codebase-specialists (desenvolvimento)

## Escopo autorizado e limites
- Autorizado (founder, 2026-10-07/08): tornar a skill e o harness compatíveis com Windows ("atacar todas as frentes
  aqui no Windows, inclusive criar a branch release/version-windows"; "use a /auto-correcao"). Branch de trabalho:
  `release/version-windows`.
- Aceites dados e features fechadas: win-motor-copia e win-bash (2026-10-09). A autorização de execução terminou com
  elas: a próxima feature (B-15 ou B-14) é escolha do founder.
- NÃO autorizado: push (é do founder); hook de aprovação no `~/.claude/settings.json` global (D-18: só por projeto);
  descartar os 2 arquivos sujos do harness (`_comum.sh`, `package.sh`) sem o founder decidir; publicar pacote.
- Aguardando decisão: os 2 arquivos sujos (`$PY` em `_comum.sh`/`package.sh` — recomendação: descartar e fazer a
  troca pela feature B-15); custo da campanha do produto (D-09) antes da medição.

## Onde paramos (2026-10-09)
- IDLE. Duas features entregues na branch `release/version-windows` (não publicada):
  - `win-bash` — commit `0bac550`: `feature.py` usa o bash do Git no Windows (`bash_exe()`); destravou o fechamento.
    Oráculo com mudança oficial de privacidade no `ESPEC.md` (recongelado `8a501fcaa794`, teste inalterado).
  - `win-motor-copia` (B-16) — commit `835dcde`: motor embutido = `auto-correcao@30e2da6`, `.gitattributes`, matcher
    `Bash|PowerShell`. Prova real: as aprovações da win-bash foram feitas no PowerShell com este motor.
- As duas campanhas concluídas no motor (intake..plano registrados no fechamento com os dados reais; remedição com a
  nota do QA). Archives em `.claude/state/archive/`.

## Próximos passos
1. Founder: push da branch `release/version-windows` (este repositório) quando quiser.
2. Escolher a próxima feature: B-15 (harness no Windows — inclui os achados B-18 (3)–(8)) ou B-14 (produto no
   Windows). Custo confirmado antes da medição (D-09). Levar B-18 (1)(2) ao BACKLOG do `auto-correcao`.
3. `/install` nesta máquina só depois da B-15 (link → junction no Windows).

## Estado do ambiente (esta máquina: Windows 11)
- Sem `python3` nativo: atalho local `~/bin/python3` (sh → Python 3.12 com `PYTHONUTF8=1`) faz hooks e scripts
  rodarem no Git Bash; NÃO vale para subprocess do Python nem para o PowerShell. WSL Ubuntu (python3 3.10; `make`
  instalado pelo founder em 2026-10-08) roda o portão e a régua — lento sobre `/mnt/c` (~1h30 a régua completa).
- Clone com `core.autocrlf=input`/`core.eol=lf` (local) e arquivos convertidos para LF em 2026-10-08 (conteúdo igual
  ao índice; os `.sh` quebravam no WSL).
- Fora do commit: `.claude/tools/_comum.sh` e `.claude/tools/package.sh` (troca para `$PY`, anterior à sessão;
  convertidos para LF); `.vscode/`; `obj/` da fixture .NET (`evals/fixtures/py-billing/…/legacy-dotnet/obj/`, build da
  IDE, recriado por um processo `dotnet`).
- Sobras locais das features fechadas (podem ser apagadas): `local/work/win-motor-copia/`, `local/work/win-bash/`,
  `local/portao-win-motor-copia/`, `local/portao-win-bash/`.
- O hook de aprovação NOVO já vale nesta sessão (selftest 135); nega no PowerShell `python -c "…;…"` por "aninhamento
  profundo" (falso positivo) — use script em arquivo.
- Skill não instalada aqui (`~/.claude/skills/codebase-specialists` ausente): `/install` depende de link (B-15).

## Ponteiros
- Auditoria: `local/auditoria-windows-2026-10-07.md` · motor: projeto `auto-correcao`, `campanhas/win-motor` e
  `campanhas/win-hook` (BACKLOG de lá: AC-24/25/26 pendentes).
- Decisões: `DECISIONS.md` (D-17..D-20) · fila: `BACKLOG.md` (B-14..B-18).
- Features entregues: `.claude/state/archive/win-motor-copia/`, `.claude/state/archive/win-bash/` · custo:
  `logs/custo.jsonl`.
