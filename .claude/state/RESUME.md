<!-- resume-stamp
FEATURES: —
BRANCH: release/desenv-mac
HEAD: b757d1f
PRODUTO: 0806f860ab8a14de6608e84dac0048174b7026b5
ESTADO: cb80f20eeb6e87b5ab516a0ccd874f09dd7f26a7
GATE: —
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
- Autorizado: nenhuma feature em execução (IDLE). A iter23 (0.13.0) foi aceita pelo founder ("ok", 2026-10-14) e
  fechada; commit da feature + commit da mudança oficial do oráculo iter10 (D-35) autorizados ("ok", 2026-10-14).
- NÃO autorizado: abrir a próxima feature sem o founder escolher; push; publicar o pacote (B-08); `claude -p` sem
  confirmar custo (D-09); troca de branch do principal (resto do B-47).
- Aguardando decisão: próxima feature (candidatas: B-50 P0 perda de dados + B-48/B-49; B-61 oráculos antigos; B-54).

## Onde paramos
- 0.13.0 entregue (iter23): fluxo da árvore sem beco sem saída (D1–D6 da cobaia .NET). Oráculo 16/41 → 41/41; portão
  VERDE nos 2 Pythons; iter10/iter15 sem regressão (D-35). Estado IDLE.
- BACKLOG: B-19, B-28, B-39..B-43, B-59, B-60 entregues; novos B-61 (oráculos antigos vermelhos), B-62 (menores),
  B-63 (fechar sprint com task BRIEFED).

## Próximos passos
1. `/install` (instala a 0.13.0 nesta máquina) e avisar a sessão da cobaia .NET: upgrade, depois `drop` das duplicadas,
   `amend`/start das completáveis, aceitar/escalar SPR-001/07 e /08 (B-63) e fechar a SPR-001; `drop` da SPR-002.
2. Founder escolhe a próxima feature.

## Estado do ambiente
- Cópias de trabalho e portões em local/work/iter23, local/portao-iter23, local/tech-lead/iter23 (evidências) e as
  antigas local/work/iter19, iter21, iter22, iter24 podem ser apagadas. A linha da iter19 em campanhas/README.md ainda
  diz "em andamento" (não conferida).
- Sessões da cobaia .NET mandam achados por SendMessage para esta sessão (nomes das sessões em local/).

## Ponteiros
- archive/iter24/iter24.md · LAST_DELIVERY.md · local/criar-iter23/criacao-suspensa/ · BACKLOG B-17, B-47..B-58 ·
  DECISIONS D-30, D-31 · PORTE-WINDOWS.md (0.12.1, 0.12.2)
