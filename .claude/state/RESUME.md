<!-- resume-stamp
FEATURES: iter27
BRANCH: release/desenv-mac
HEAD: 9e908e0
PRODUTO: 6da785c653a66f951dbbeb4d0d3ff81225315133
ESTADO: 47f9122d4b450482fb5c62325ecaf882e0f2d11e
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
- Autorizado: iter27 (CLI e motor inteiros em inglês — B-72 + B-68 + B-71) ABERTA em 2026-10-19 pelo
  `/criar-feature` (E1 "sim", E2–E5 "ok"; D-47). Próximo trabalho permitido: a task 01-TASK-ORACULO por agente
  separado (persona oraculista via /rh) e o `oracle freeze`; depois GERAR o script de aprovação
  (`script-aprovacao.sh iter27`) para o founder rodar com a senha.
- NÃO autorizado: correção (tasks 02–06) antes da aprovação do founder no script (`ac.py check intake.3`); rodar o
  script de aprovação ou pedir a senha; push; publicar o pacote (B-08); `claude -p` sem confirmar custo (D-09);
  editar a v8 daqui; rodar o portão dentro de subagente (B-70); os subcomandos pt `senha/conferir/anular` (B-73).
- Aguardando decisão: nada pendente além da aprovação do oráculo (depois que ele existir).

## Onde paramos
- iter27 aberta (nada commitado): 8 tasks, CA-01..CA-09, campanha `campanhas/iter27/` em `intake`, 35 globs de
  escopo, alvo VERSION 0.15.0. Proposta e medição: `.claude/state/features/iter27/` (FEATURE.md, TASKS/, propostas/);
  rascunhos em `local/criar-iter27/`.
- E2 mediu: 28 nomes de flag pt sem en (35 linhas), 311 citações pt nos textos, 28 chaves pt + `kind: "epico"` na
  forma interna, cs-auto fora do doctest; oráculos antigos não leem a forma interna (nenhuma mudança oficial prevista
  com alias).
- 0.14.0 (iter26) entregue e instalada; cobaia .NET na 0.14.0 (B-49 ainda não provado no uso real).

## Próximos passos
1. `/tech-lead iter27` → 01-TASK-ORACULO por agente separado (oraculista), conferência e `oracle freeze` (3 arquivos:
   ESPEC.md, test_iter27.py, base.txt).
2. Gerar o script de aprovação (`bash .claude/tools/script-aprovacao.sh iter27`); o founder roda no terminal com a
   senha.
3. Correção: 02 (G1) ∥ 04 (G2) → 03 e 05 → 06 → QA (portão sob o tech-lead com caffeinate) → REVIEW. Depois: iter28
   task melhor; iter29 métricas.

## Estado do ambiente
- Cópias e portões em local/work/iter26, local/portao-iter26, local/tech-lead/iter26, local/mo10, local/mo13,
  local/mo19 (rascunhos de mudança oficial), local/d35, local/d35b (evidências); as antigas local/work/iter19..iter25
  podem ser apagadas.
- Sessões da cobaia .NET mandam achados por SendMessage para esta sessão (nomes em local/).

## Ponteiros
- features/iter27/ · archive/iter26/iter26.md · LAST_DELIVERY.md · BACKLOG B-68..B-73 · DECISIONS D-40..D-47 · PORTE-WINDOWS.md
  (0.13.1, 0.14.0)
