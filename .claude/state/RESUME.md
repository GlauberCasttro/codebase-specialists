<!-- resume-stamp
FEATURES: win-harness
BRANCH: release/version-windows
HEAD: 94a8e5d
PRODUTO: 867383f46128b616aab13225d9057503bd310632
ESTADO: 3743d6b49c4f163b94b80ac6e825d04c2b03d455
GATE: PENDENTE
-->

# RESUME — codebase-specialists (desenvolvimento)

## Escopo autorizado e limites
- Autorizado (founder, 2026-10-07/08): tornar a skill e o harness compatíveis com Windows ("atacar todas as frentes
  aqui no Windows, inclusive criar a branch release/version-windows"; "use a /auto-correcao"). Branch de trabalho:
  `release/version-windows`.
- Feature `win-harness` (B-15) aberta em 2026-10-09 com E1–E5 aprovadas ("ok" em cada etapa; D-21); campanha
  aprovada pelo founder com a senha (`intake.3` ok). `/tech-lead` em modo AUTÔNOMO (founder: "autonomo") até a
  feature fechar — para só nos gates humanos (aceite final, `frase conferir`) e em decisão de desenho.
- NÃO autorizado: push (é do founder); hook de aprovação no `~/.claude/settings.json` global (D-18: só por projeto);
  descartar os 2 arquivos sujos do harness (`_comum.sh`, `package.sh`) — viram base da cópia de trabalho da
  `win-harness` (F15, D-21); publicar pacote; portar/commitar antes do aceite do founder; adicionar ao BACKLOG os
  candidatos abaixo sem o founder decidir.
- Aguardando decisão: custo da campanha do produto (D-09) antes da medição da B-14; candidatos ao BACKLOG vindos das
  revisões (no fim da feature): guard-git PowerShell ainda deixa passar `{ git push }`, `$x = git push`, `` g`it ``,
  `iex`, `Start-Process git`, `cmd /c git push`, `-EncodedCommand` (mesma classe que `{ git push; }` no Bash, PRÉ-
  EXISTENTE); `portao.sh --pythons` com caminho com espaço; `copia.sh` com `CS_DEV_SKILL_DIR` em barra invertida.

## Onde paramos (2026-10-09)
- Feature ativa `win-harness`: 5/8 tasks DONE/PASS — 01 oráculo (`540e1eccf037`, 55 testes), 02 lançador/hooks
  (2 ciclos: CS_DEV_PY inválido deixava os hooks abertos), 03 scripts shell (`.ps1`, junção), 04 estado/encoding
  (2 ciclos: `def dentro_sys32` removido), 05 régua/portão. 06 (suíte harness-dev) IN_PROGRESS: executor DONE
  (Windows sem atalho 108 testes OK, 1 skip de symlink; WSL 108 OK nos 2 Pythons), conferência do tech-lead ok
  (escopo, def, asserções, privacidade); faltam a régua completa do tech-lead (`local/tech-lead/win-harness/regua-06.out`)
  e a revisão isolada. Tudo na cópia `local/work/win-harness/codebase-specialists/` — nada portado, nada commitado.
- Antes, duas features entregues na branch `release/version-windows` (não publicada):
  - `win-bash` — commit `0bac550`: `feature.py` usa o bash do Git no Windows (`bash_exe()`); destravou o fechamento.
    Oráculo com mudança oficial de privacidade no `ESPEC.md` (recongelado `8a501fcaa794`, teste inalterado).
  - `win-motor-copia` (B-16) — commit `835dcde`: motor embutido = `auto-correcao@30e2da6`, `.gitattributes`, matcher
    `Bash|PowerShell`. Prova real: as aprovações da win-bash foram feitas no PowerShell com este motor.
- As duas campanhas concluídas no motor (intake..plano registrados no fechamento com os dados reais; remedição com a
  nota do QA). Archives em `.claude/state/archive/`.

## Próximos passos
1. `/tech-lead` (autônomo): ler `local/tech-lead/win-harness/regua-06.out` (régua completa: harness-dev e oráculo
   inteiro no Windows sem atalho e no WSL; oráculos win-bash/win-motor-copia); se verde, revisor isolado da 06
   (prompt montado por `local/tech-lead/win-harness/montar_revisor.py`), Handoff e `feature.py task marcar … DONE`.
2. 07-TASK-QA: portão no Windows (`--suites harness-dev` + 3 oráculos, lista = os 28 arquivos) e portão completo no
   WSL (~1h30); depois 08-TASK-REVIEW (opus, modo feature) → pacote de aceite → FOUNDER aceita → `/fechar-feature`.
3. Founder: push da branch quando quiser. Levar B-18 (1)(2) ao BACKLOG do `auto-correcao`. `/install` nesta máquina
   depois da `win-harness` (junção, CA-10).

## Estado do ambiente (esta máquina: Windows 11)
- Sem `python3` nativo: atalho local `~/bin/python3` (sh → Python 3.12 com `PYTHONUTF8=1`) faz hooks e scripts
  rodarem no Git Bash; NÃO vale para subprocess do Python nem para o PowerShell. WSL Ubuntu (python3 3.10; `make`
  instalado pelo founder em 2026-10-08) roda o portão e a régua — lento sobre `/mnt/c` (~1h30 a régua completa).
- Clone com `core.autocrlf=input`/`core.eol=lf` (local) e arquivos convertidos para LF em 2026-10-08 (conteúdo igual
  ao índice; os `.sh` quebravam no WSL).
- Fora do commit: `.claude/tools/_comum.sh` e `.claude/tools/package.sh` (troca para `$PY`, anterior à sessão;
  convertidos para LF); `.vscode/`; `obj/` da fixture .NET (`evals/fixtures/py-billing/…/legacy-dotnet/obj/`, build da
  IDE, recriado por um processo `dotnet`).
- Feature em curso: cópia de trabalho `local/work/win-harness/codebase-specialists/` (HEAD 94a8e5d + base F15 + tasks
  02–06), temporários dos executores em `local/work/win-harness/tmp-02/`, `tmp-06/`; prompts, retornos, réguas e
  snapshots em `local/tech-lead/win-harness/`. O carimbo PRODUTO muda pelo `obj/` da fixture .NET (build da IDE em
  `evals/`), não por código: régua PENDENTE até o portão da feature.
- Sobras locais das features fechadas (podem ser apagadas): `local/work/win-motor-copia/`, `local/work/win-bash/`,
  `local/portao-win-motor-copia/`, `local/portao-win-bash/`.
- O hook de aprovação NOVO já vale nesta sessão (selftest 135); nega no PowerShell `python -c "…;…"` por "aninhamento
  profundo" (falso positivo) — use script em arquivo.
- Skill não instalada aqui (`~/.claude/skills/codebase-specialists` ausente): `/install` depende de link (B-15).

## Ponteiros
- Auditoria: `local/auditoria-windows-2026-10-07.md` · motor: projeto `auto-correcao`, `campanhas/win-motor` e
  `campanhas/win-hook` (BACKLOG de lá: AC-24/25/26 pendentes).
- Decisões: `DECISIONS.md` (D-17..D-21) · fila: `BACKLOG.md` (B-14..B-18).
- Features entregues: `.claude/state/archive/win-motor-copia/`, `.claude/state/archive/win-bash/` · custo:
  `logs/custo.jsonl`.
