<!-- resume-stamp
FEATURES: —
BRANCH: release/desenv-mac
HEAD: 1d3d78d
PRODUTO: a1bfb79f958908cb4e1a07fe350f3f80352c9456
ESTADO: a83547873fb5dda8c8e6fb17752c818796f0f4c8
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
- Autorizado: nenhuma feature em execução (IDLE). A iter25 (0.13.1) foi aceita pelo founder ("sim", 2026-10-16) e
  fechada; commit da feature + commit à parte da mudança oficial 02 do oráculo iter23 (D-39), como na iter10.
- NÃO autorizado: abrir a próxima feature sem o founder escolher; push; publicar o pacote (B-08); `claude -p` sem
  confirmar custo (D-09); troca de branch do principal (resto do B-47); editar a v8 daqui (ajustes vão pela sessão
  da v8, que já recebeu local/ajustes-v8.md).
- Aguardando decisão: próxima feature. Sequência recomendada ao founder (2026-10-14): iter26 canonização + limpeza de
  campos mortos + telemetria barata → iter27 task melhor (brief com contexto/DoD, matriz de casos, vermelho pelo motivo
  certo por caso, checks do revisor por script; story/feature/épico no mesmo padrão) → iter28 métricas (`cs-state
  metrics`) → B-50/B-48/B-49.

## Onde paramos
- 0.13.1 entregue (iter25, B-64): status canônico gravado no arquivo de cada item da árvore, sempre em dia, conferido
  pelo validate, preenchido pelo upgrade (`cs-state migrate item-status`). Oráculo 8/21 → 21/21; portão VERDE nos 2.
- A sessão da cobaia .NET vigia a VERSION instalada e roda o upgrade sozinha ao ver 0.13.1 (autorização do dono lá).
- BACKLOG: B-64 entregue; novos B-65 (menores da 0.13.1), B-66 (sufixo SUBMITTED/RETURNED).

## Próximos passos
1. `/install` (instala a 0.13.1) — a cobaia .NET roda o upgrade e manda divergências por mensagem.
2. Founder escolhe a próxima feature (sequência recomendada acima).

## Estado do ambiente
- Cópias de trabalho e portões em local/work/iter23, local/portao-iter23, local/tech-lead/iter23 (evidências) e as
  antigas local/work/iter19, iter21, iter22, iter24 podem ser apagadas. A linha da iter19 em campanhas/README.md ainda
  diz "em andamento" (não conferida).
- Sessões da cobaia .NET mandam achados por SendMessage para esta sessão (nomes das sessões em local/).

## Ponteiros
- archive/iter24/iter24.md · LAST_DELIVERY.md · local/criar-iter23/criacao-suspensa/ · BACKLOG B-17, B-47..B-58 ·
  DECISIONS D-30, D-31 · PORTE-WINDOWS.md (0.12.1, 0.12.2)
