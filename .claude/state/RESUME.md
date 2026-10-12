<!-- resume-stamp
FEATURES: iter22
BRANCH: release/desenv-mac
HEAD: d2e07ff
PRODUTO: 35d6171ce3ec09d42ae2ac773183fb923aa56213
ESTADO: 12c9ea8416ec83f94b386181408c134fc29f7ab2
GATE: PENDENTE
-->

<!-- carimbo:inicio (gerado por tools/carimbo.sh --write; não edite à mão) -->
```
carimbo: 2026-10-06 16:17 -03 · branch master · HEAD 4dd7cf2 harness: /install instala o pacote dist validado (iter17)
skill: codebase-specialists · VERSION viva 0.9.0 (HEAD: 0.9.0) · último commit da skill: 4dd7cf2 2026-10-06 harness: /install instala o pacote dist validado (iter17)
campanhas ativas: nenhuma
arquivos sujos da skill: 4
  (lista: git status --porcelain)
```
<!-- carimbo:fim -->

# RESUME — codebase-specialists (desenvolvimento)

## Escopo autorizado e limites
- Autorizado: iter22 (hotfix 0.12.1, B-35: `cs-state show` liberado no guard + varredura argparse × guard) — E1–E5
  aprovadas pelo founder ("ok") em 2026-10-12; oráculo congelado (524416ebaf44).
- NÃO autorizado: corrigir antes de o founder rodar o script de aprovação da iter22 (o corretor fica bloqueado até
  intake.3); misturar na iter22 qualquer item da feature "fluxo da árvore" (B-19, B-28, B-38..B-43); push; nova prova
  real `claude -p` sem confirmar o custo (D-09).
- Aguardando decisão: founder rodar `sh local/aprovar-iter22.sh` no terminal dele; B-38 (nomes curtos estilo v8) junto
  da feature "fluxo da árvore" (recomendado) ou separado; `git config user.email` noreply.

## Onde paramos
- 0.12.0 entregue (iter21, 7fdb431) e instalada; cobaia .NET atualizada para 0.12.0 (commits 29723e4 e 93df5ff lá;
  pre-commit sem --no-verify OK).
- iter22 aberta: 1/5 (01-TASK-ORACULO DONE, base 3/9). Próximas: 02-GUARD-SHOW ∥ 03-VERSAO → 04-QA → 05-REVIEW.
- Uso real na cobaia gerou B-35..B-43 (B-35 em iter22; B-19, B-39, B-40, B-42, B-43 travam o fluxo diário lá).

## Próximos passos
1. Founder roda o script de aprovação da iter22 → `/tech-lead --modo autonomo` (02 ∥ 03 → QA → REVIEW → aceite →
   /fechar-feature → /install → upgrade da cobaia para 0.12.1).
2. Depois: `/criar-feature` "fluxo da árvore" (B-19, B-43, B-42, B-39, B-40, B-28 e, se aprovado, B-38).

## Estado do ambiente
- Fora do commit (da iter22; entram no fechamento): campanhas/iter22/ (oráculo) e campanhas/README.md (linha da
  abertura). Cópias local/work/iter19 e iter21 (podem ser apagadas); prova real em ~/cs-prova-iter21/.
- Sessões da cobaia .NET mandam achados por SendMessage para esta sessão (nomes das sessões em local/).

## Ponteiros
- features/iter22/ (FEATURE.md, TASKS, CHECKLIST) · archive/iter21/iter21.md · BACKLOG B-33..B-43 · DECISIONS
  D-22..D-29 · PORTE-WINDOWS.md (0.11.0, 0.12.0)
