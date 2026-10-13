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
- Autorizado: nenhuma feature em execução (IDLE). A iter24 foi aceita pelo founder ("ok", 2026-10-13), fechada e
  instalada (0.12.2).
- NÃO autorizado: abrir a próxima feature sem o founder escolher; liberar a troca de branch do principal (D-30/E1,
  resto do B-47); push; publicar o pacote (B-08); `claude -p` sem confirmar custo (D-09).
- Aguardando decisão: próxima feature — recriar a iter23 (e se B-48, B-49, B-50 entram) ou um hotfix 0.12.3 com B-54;
  B-56 (`--force-with-lease` em branch própria) mantido como está no aceite.

## Onde paramos
- 0.12.2 entregue (iter24, b757d1f) e instalada nesta máquina (dist, origem b757d1f): guard sem portas laterais;
  oráculo 9/22 → 22/22; 02 em 3 ciclos (a revisão da feature reabriu portas por variantes). Estado IDLE.
- BACKLOG: B-44/45/46 entregues; B-47 parcial; B-17 subiu a P1; novos B-54..B-58.
- `campanhas/README.md` atualizado depois do commit da feature (iter22 da30e17 GO, iter24 b757d1f GO) — fora do estado.

## Próximos passos
1. Upgrade da cobaia para 0.12.2 (`cs.py upgrade` e `upgrade --apply --allow-outside` lá) e aviso à sessão de lá.
2. Founder escolhe a próxima: `/tech-lead` (IDLE ⇒ pergunta) — recriar a iter23 a partir de local/criar-iter23/ ou
   hotfix B-54.
3. Commitar `campanhas/README.md` (não é do save: entra no próximo commit de feature ou à parte, a pedido).

## Estado do ambiente
- Fora do commit: `campanhas/README.md` (linhas de entrega iter22/iter24; a linha da iter19 ainda diz "em andamento",
  não conferida). Cópias local/work/iter19, iter21, iter22, iter24 e local/portao-iter24 podem ser apagadas.
  Evidências da iter24 em local/tech-lead/iter24/ e local/fechar-iter24/.
- Sessões da cobaia .NET mandam achados por SendMessage para esta sessão (nomes das sessões em local/).

## Ponteiros
- archive/iter24/iter24.md · LAST_DELIVERY.md · local/criar-iter23/criacao-suspensa/ · BACKLOG B-17, B-47..B-58 ·
  DECISIONS D-30, D-31 · PORTE-WINDOWS.md (0.12.1, 0.12.2)
