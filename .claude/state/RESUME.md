<!-- resume-stamp
FEATURES: iter27
BRANCH: release/desenv-mac
HEAD: 291635c
PRODUTO: 6da785c653a66f951dbbeb4d0d3ff81225315133
ESTADO: 932314aba6ba3b1f8f5b574a957c446e2c669715
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
- Autorizado: iter27 (CLI e motor inteiros em inglês — B-72 + B-68 + B-71), aberta em 2026-10-19 (D-47), em execução
  pelo `/tech-lead` no modo **autônomo** (escolha do founder em 2026-10-19: "autonomo"). Feito: 01-TASK-ORACULO
  (oráculo congelado f482a969021e) e o script de aprovação GERADO (`local/aprovar-iter27.sh`).
- NÃO autorizado: correção (tasks 02–06) antes de o founder rodar o script (`ac.py check intake.3` ainda falha); rodar
  o script ou pedir a senha; mudar o oráculo congelado (só mudança oficial); push; publicar o pacote (B-08); `claude
  -p` sem confirmar custo (D-09); editar a v8 daqui; rodar o portão dentro de subagente (B-70); os subcomandos pt
  `senha/conferir/anular` (B-73); implementar B-79..B-82 (são BACKLOG; viram feature só por decisão do founder);
  editar `.claude/CLAUDE.md` direto (guard-entrega; a linha do autor muda pelo B-82); amend/reescrita de commit já
  publicado.
- Aguardando decisão: (1) o founder rodar `sh local/aprovar-iter27.sh` (gate stop + gate oracle:requisito + preauth
  commit); (2) a frente "lixo de criação e retenção no alvo" (B-80) vira feature (iter28 alternativa ou junto do B-76)
  ou fica no BACKLOG; (3) ordem da iter28 (B-76 recomendada; B-79 é entrada dela, D-48); (4) como alinhar o branch
  com o remoto antes do próximo push (ver Estado do ambiente).

## Onde paramos
- iter27 1/8: 01-TASK-ORACULO DONE/PASS — 84 testes (TestCA01..09), no HEAD 62 D FAIL / 0 ERROR / 22 R OK nos 2
  Pythons, refeito pelo tech-lead; campanha em `intake` 2/3 (budget e oracle.command/split/calibration gravados;
  falta intake.3 = gate stop do founder). Próxima elegível depois da aprovação: 02-TASK-FLAGS-EN (G1) ∥
  04-TASK-INCLUDE-EMITTED (G2).
- Nesta sessão também: análise arquivo a arquivo do `.swarm/` da cobaia .NET (B-80, B-81; relatório em
  `local/frente-lixo-alvo/RELATORIO.md`) e o B-79 (status de story/feature/épico pela pasta × rollup da v8, com prova
  em `local/b79-prova/`).

## Próximos passos
1. Founder: `sh local/aprovar-iter27.sh` no terminal dele (com a senha). Depois: `python3 .claude/tools/ac/ac.py
   --work campanhas/iter27 check intake.3` deve dar ok → `done intake`, `done oraculo` e a etapa `base` (`run record
   --round 0`) pelo `/tech-lead`.
2. `/tech-lead` (modo autônomo): cópia de trabalho (`bash .claude/tools/copia.sh iter27`) → 02 (G1) ∥ 04 (G2) → 03 e 05
   → 06 → QA (portão sob o tech-lead com caffeinate) → REVIEW → aceite do founder.
3. Decidir o destino do B-80 (frente da cobaia) e a ordem da iter28 (B-76 + B-77(a), entrada B-79).

## Estado do ambiente
- **Git divergente do remoto (decisão do founder: "deixa como está")**: local `release/desenv-mac` está ahead 1 /
  behind 1 do `origin`. O commit do oráculo (`campanhas/iter27/oraculo/` + linha do `campanhas/README.md`) existe em
  duas versões de árvore IDÊNTICA: `c393c17` no remoto (autor noreply) e `291635c` local (autor gmail, por amend feito
  sem conferir que já estava publicado). Push normal será recusado: o founder publica com `git push
  --force-with-lease`, ou alinha com `git reset --soft c393c17` (o auto mode nega à IA). NÃO rodar `git pull`.
- Autor dos commits = o `user.email` global do founder (D-49; corrigido nesta sessão); nunca forçar `--author`.
- local/: `local/tech-lead/iter27/` (ficha, snapshot, verificações), `local/aprovar-iter27.sh`,
  `local/frente-lixo-alvo/` (RELATORIO.md + cópia de 34 MB da cobaia que pode ser apagada), `local/b79-prova/`
  (scripts da prova; `tmp/` vazio). Antigas: local/work/iter19..iter26, local/portao-iter26, local/mo*, local/d35*
  podem ser apagadas.
- Sessões da cobaia .NET mandam achados por SendMessage para esta sessão (nomes em local/).

## Ponteiros
- features/iter27/ · archive/iter26/iter26.md · LAST_DELIVERY.md · BACKLOG B-68..B-82 (B-76 state/ do alvo; B-79 ciclo
  de vida; B-80 lixo/retenção no alvo; B-81 consolidate em árvore e bin/ ignorado; B-82 autor no CLAUDE.md) ·
  DECISIONS D-40..D-49 ·
  PORTE-WINDOWS.md (0.13.1, 0.14.0)
