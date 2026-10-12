<!-- resume-stamp
FEATURES: iter21
BRANCH: release/desenv-mac
HEAD: c2b74ae
PRODUTO: 0278c8073e381b8177c9807cba69a33ad9c9ae64
ESTADO: 14ec5d10e375a83d3962f90d16aa7011c390ac23
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
- Autorizado: iter21 (memória dos agentes) no método auto-correção — founder: "provar que o agente fez Y, foi
  corrigido, a memória foi atualizada e ele não esquece mais"; decisões técnicas são do tech-lead (provar com números);
  DEC-1 aprovada (plan:DEC-1); mo2 do oráculo oficializada (D-23). Founder liberou /orquestrar-subagentes "se precisar".
- NÃO autorizado: push (só o founder); mudar git config sem "pode"; remedição real com `claude -p` sem confirmar o
  custo com o founder (D-09); abrir feature nova; B-19/B-28/B-26/B-27/B-30/B-31/B-32 junto da iter21.
- Aguardando decisão: configurar `git config user.email` noreply neste repo; /install da 0.11.0 (sugerido).

## Onde paramos
- iter19 ENTREGUE: 0.11.0 commit c2b74ae (portão VERDE nos 2 Pythons, QA ACCEPT, Review APPROVED, campanha GO).
- iter21: etapa correção (rodada 0). Frente memória ciclos 1–3 revisados e APPROVED na cópia local/work/iter21
  (F1–F8 + M14.5); oráculo recongelado com mo2 (64 asserções): 49/64 nos 2 Pythons (base 19/55). As 15 falhas
  restantes são das frentes motor e emissão (brief, guard/pre-commit do caderno, upgrade, consultei, skill /correct),
  agora desbloqueadas (a colisão com a iter19 acabou).

## Próximos passos
1. `/install` (instala a 0.11.0 nesta máquina).
2. iter21: atualizar a cópia local/work/iter21 com o HEAD c2b74ae (a 0.11.0 mudou o motor) sem perder a frente
   memória; despachar as frentes motor e emissão (disjuntas; /orquestrar-subagentes) contra as 15 falhas do oráculo.
3. iter21: integração (suítes 2 Pythons + oráculos) → confirmar custo com o founder → remedição real (prova_real.py,
   claude -p) → decisão.

## Estado do ambiente
- Fora do commit: cópias local/work/iter19 (entregue; pode ser apagada) e local/work/iter21 (frente memória, NÃO
  portada); portões e notas em local/; prova real em ~/cs-prova-iter21/; ledgers .auto-correcao locais.
- campanhas/iter21 (oráculo mo2, PORQUE, revisoes/) modificados e ainda não commitados (não é estado: entram no commit
  da iter21).
- Branch remota release/version-windows existe (outra sessão; números de decisão conflitam com D-21+ daqui).

## Ponteiros
- archive/iter19/iter19.md · PORTE-WINDOWS.md (0.11.0 com a lista de cherry-pick) · BACKLOG B-17 (2 ocorrências no
  fechamento da iter19), B-29..B-32 · DECISIONS D-22..D-25 · campanhas/iter21/revisoes/memoria-ciclo2.md
