<!-- resume-stamp
FEATURES: —
BRANCH: release/version-windows
HEAD: b2498c5
PRODUTO: 92c3871b35c062482ab2ee8097c855d6739f1e0a
ESTADO: 8aa451afacbf1d538bce2658715769e3bead6a4f
GATE: —
-->

# RESUME — codebase-specialists (desenvolvimento)

## Escopo autorizado e limites
- Autorizado (founder, 2026-10-07/08): tornar a skill e o harness compatíveis com Windows ("atacar todas as frentes
  aqui no Windows, inclusive criar a branch release/version-windows"; "use a /auto-correcao"). Branch de trabalho:
  `release/version-windows`.
- NÃO autorizado: push (é do founder); hook de aprovação no `~/.claude/settings.json` global (D-18: só por projeto);
  descartar os 2 arquivos sujos do harness (`_comum.sh`, `package.sh`) sem o founder decidir; publicar pacote.
- Aguardando decisão: os 2 arquivos sujos (`$PY` em `_comum.sh`/`package.sh` — recomendação: descartar e fazer a
  troca pela feature B-15); custo da campanha do produto (D-09) antes da medição.

## Onde paramos (2026-10-08)
- HEAD em `master` = `b2498c5` (0.10.0: iter17 e iter18 entregues; "frente" virou "feature" no harness). Nesta
  máquina Windows, a branch `release/version-windows` foi criada a partir dele.
- Auditoria de compatibilidade Windows feita (3 auditores, só leitura): 8 temas T1–T8 em harness, produto e motor.
  Detalhe em `local/auditoria-windows-2026-10-07.md` (não versionado).
- O MOTOR (projeto irmão `auto-correcao`, branch `release/version-windows`, já publicada pelo founder) foi corrigido
  por duas campanhas: `win-motor` (frase no console do Windows, cp1252, CRLF, suíte sem pty) e `win-hook` (hook de
  aprovação vê a ferramenta PowerShell, `python.exe`/`py`, indireções, `-EncodedCommand`). Ambas PARAR, com prova
  real do founder no PowerShell. A cópia embutida aqui (`.claude/tools/ac/`) AINDA é a antiga (ORIGEM `da3ea45`).

## Próximos passos
1. B-16: recopiar o motor corrigido para `.claude/tools/ac/` (+ `ORIGEM.txt`), pelo fluxo `/criar-feature`.
2. B-15 (harness no Windows) e B-14 (produto no Windows), cada um uma feature (`/criar-feature` → `/tech-lead`),
   com oráculo rodando no Windows nativo e no WSL. Confirmar o custo com o founder antes da medição.
3. Depois: B-08 (pacote 0.10.x com suporte a Windows) e B-13.

## Estado do ambiente (esta máquina: Windows 11)
- Sem `python3` nativo: atalho local `~/bin/python3` (sh → Python 3.12 com `PYTHONUTF8=1`) faz os hooks e scripts
  rodarem no Git Bash; NÃO vale para subprocess do Python nem para o PowerShell. WSL Ubuntu (python3 3.10) é usado
  para os rituais que chamam `bash`/`/usr/bin/python3`.
- Fora do commit (de terceiros/pendentes): `.claude/tools/_comum.sh` e `.claude/tools/package.sh` modificados
  (troca para `$PY`, origem anterior a esta sessão); `.vscode/` não rastreado.
- `local/termos-privados.txt` criado nesta máquina (guard de privacidade: 0 achados).
- Skill não instalada aqui (`~/.claude/skills/codebase-specialists` ausente): `/install` depende de link, que no
  Windows exige junction (parte da B-15).

## Ponteiros
- Auditoria: `local/auditoria-windows-2026-10-07.md` · motor: projeto `auto-correcao`, `campanhas/win-motor` e
  `campanhas/win-hook` (BACKLOG de lá: AC-24/25/26 pendentes).
- Decisões: `DECISIONS.md` (D-17, D-18 desta sessão) · fila: `BACKLOG.md` (B-14..B-16).
