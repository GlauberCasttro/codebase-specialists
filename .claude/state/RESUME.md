<!-- resume-stamp
FEATURES: iter24
BRANCH: release/desenv-mac
HEAD: 92f5cf2
PRODUTO: 00207002352f08b04fafad000c8669c8ea88a802
ESTADO: e6c20362aca1e2a333b8f51a05d0f8cc12443e12
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
- Autorizado: iter24 (hotfix de segurança 0.12.2: B-44, B-45, B-46, B-47 — fechar as portas do guard confirmadas pela
  auditoria da cobaia) — E1–E5 aprovadas ("ok", 2026-10-12); oráculo congelado (37f3042c76ae); campanha aprovada pelo
  founder (intake.3 OK). Execução pelo `/tech-lead --modo autonomo` (2026-10-12); D-31 (test_guards.py na 02).
- NÃO autorizado: liberar a troca de branch do principal (D-30/E1); misturar B-48..B-53 ou a iter23 na iter24; push;
  `claude -p` sem confirmar custo (D-09); reabrir a iter23 antes de fechar a iter24; pôr no BACKLOG sozinho os MENOR
  da revisão (são candidatos: decisão do founder no aceite).
- Aguardando decisão: (a) candidatos ao BACKLOG vindos das revisões — `git --config-env=core.hooksPath`/`GIT_CONFIG_*`
  desligam hooks pelo principal; `git stash list` bloqueado (pré-existente); `.SWARM` maiúsculo passa no macOS
  (pré-existente); variável opaca/symlink para dentro de .swarm (`$H/state.py`) passa; `python3 $PWD/.swarm/knowledge/x.py`
  vira inanalisável (falso bloqueio raro); texto da 0.12.2 diz "branch -D" sem "de branch protegida". (b) `/install`.

## Onde paramos
- iter24 3/5. 03-VERSAO DONE/PASS. 02-GUARD-PORTAS reaberta pela 05-REVIEW (CHANGES_REQUESTED: `$PWD/.swarm/...`,
  `push +HEAD`, `--no-veri`); ciclo 2 (opus) corrigiu; revisor do ciclo 2 achou `.swarm//` e `/./` por variável; ciclo 3
  (opus) corrigiu e o revisor do ciclo 3 deu APPROVED. A 02 segue IN_PROGRESS/FAIL até o portão do ciclo 3 sair VERDE.
- 04-QA está DONE com o Aceite QA do ciclo 1 no FEATURE.md: a matriz ficou VELHA (o guard mudou depois) — refazer.
- Portão do ciclo 3 em local/portao-iter24/portao.out (o do ciclo 1 em local/tech-lead/iter24/portao-ciclo1.out).

## Próximos passos
1. `tail -3 local/portao-iter24/portao.out` — VERDE+FIM ⇒ Handoff da 02 (ciclos 2–3) e `python3 .claude/tools/feature.py
   task marcar iter24 02-TASK-GUARD-PORTAS --status DONE --gate PASS --nota "..."`; VERMELHO ⇒ ciclo/diagnóstico.
2. `/tech-lead --modo autonomo`: re-QA (atualizar o Aceite QA com o portão do ciclo 3) → 05-REVIEW nova (opus) → aceite
   do founder (decidir os candidatos ao BACKLOG) → `/fechar-feature iter24` → `/install` → upgrade da cobaia.
3. Recriar a iter23 a partir de local/criar-iter23/ (decidir se B-48, B-49, B-50 entram).

## Estado do ambiente
- Fora do commit: campanhas/iter24/ e campanhas/README.md (entram no fechamento). Cópia da feature em
  local/work/iter24/codebase-specialists (bashscan/guard/hcore/auto, test_iter24_guard, test_guards, VERSION, README,
  migrations, docs/09); lista do portão local/iter24-arquivos.txt; evidências em local/tech-lead/iter24/. Cópias
  local/work/iter19, iter21, iter22 podem ser apagadas. Sondas dos revisores no scratchpad (efêmero).
- Sessões da cobaia .NET mandam achados por SendMessage para esta sessão (nomes das sessões em local/).

## Ponteiros
- features/iter24/ · archive/iter22/iter22.md · local/criar-iter23/criacao-suspensa/ · BACKLOG B-38, B-44..B-53 ·
  DECISIONS D-29, D-30 · PORTE-WINDOWS.md (0.11.0, 0.12.0)
