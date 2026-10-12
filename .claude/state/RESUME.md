<!-- resume-stamp
FEATURES: iter24
BRANCH: release/desenv-mac
HEAD: da30e17
PRODUTO: 00207002352f08b04fafad000c8669c8ea88a802
ESTADO: 412edd84321d5ad45cfcdc0f1cef58627462ddb6
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
  founder (intake.3 OK). Execução pelo `/tech-lead --modo autonomo`.
- NÃO autorizado: liberar a troca de branch do principal (fica fora da iter24, D-30/E1); misturar B-48..B-53 ou a
  iter23 na iter24; push; nova prova real `claude -p` sem confirmar custo (D-09); reabrir a iter23 antes de fechar a
  iter24.
- Aguardando decisão: `/install` da 0.12.1; upgrade da cobaia para 0.12.1 (libera o show lá); `git config user.email`
  noreply.

## Onde paramos
- 0.12.1 entregue (iter22, da30e17): `cs-state show` liberado no guard + varredura argparse × guard.
- Auditoria /orquestrar-subagentes da cobaia: 4 auditores + 2 verificadores cegos; 3 críticos e 8 altos confirmados;
  registrados B-44..B-51 (+ B-52 cancelar criação, B-53 guard com symlink). Decisão NO-GO por cobertura de leitura 20%.
- iter24 aberta: 1/5 (01-TASK-ORACULO DONE, base 9/22 nos 2 Pythons). Criação da iter23 SUSPENSA (D-30) em
  local/criar-iter23/criacao-suspensa/ (E1–E5 aprovadas; recriar reaproveitando os textos).

## Próximos passos
1. `/tech-lead --modo autonomo`: iter24 02-GUARD-PORTAS ∥ 03-VERSAO → 04-QA (portão, oráculos iter16..iter22
   inteiros) → 05-REVIEW (tentar reabrir as portas) → aceite → `/fechar-feature iter24` → `/install`.
2. Upgrade da cobaia para 0.12.2 e aviso à sessão de lá.
3. Recriar a iter23 (fluxo da árvore) a partir de local/criar-iter23/ (decidir se B-48, B-49, B-50 entram); depois a
   2ª auditoria focada em leitura do motor.

## Estado do ambiente
- Fora do commit: campanhas/iter24/ (oráculo; entra no fechamento da iter24) e campanhas/README.md. Cópias
  local/work/iter19, iter21 e iter22 (podem ser apagadas); auditoria em scratchpad (efêmera) e missão em
  /var/folders (fora do repo); prova real em ~/cs-prova-iter21/.
- Sessões da cobaia .NET mandam achados por SendMessage para esta sessão (nomes das sessões em local/).

## Ponteiros
- features/iter24/ · archive/iter22/iter22.md · local/criar-iter23/criacao-suspensa/ · BACKLOG B-38, B-44..B-53 ·
  DECISIONS D-29, D-30 · PORTE-WINDOWS.md (0.11.0, 0.12.0)
