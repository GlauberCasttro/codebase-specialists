<!-- resume-stamp
FEATURES: iter19,iter21
BRANCH: release/desenv-mac
HEAD: bacfc07
PRODUTO: 5e08335652440fa31bbba2ce63b205ef2970580c
ESTADO: ff0ac8249589c37a94c295319f0bd56ce260fa08
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
- Autorizado: iter19 (0.11.0, estado em JSON) em /tech-lead modo AUTÔNOMO; iter21 (memória dos agentes) no método
  auto-correção — founder: "provar que o agente fez Y, foi corrigido, a memória foi atualizada e ele não esquece mais";
  decisões técnicas são do tech-lead (provar com números); DEC-1 (caderno = bloco gerado + área livre) aprovada no
  portão plan:DEC-1.
- NÃO autorizado: push (só o founder); mudar git config sem "pode" (e-mail noreply pendente); correção das frentes
  motor/emissao da iter21 antes do commit da iter19 (colisão); B-19/B-28/B-26/B-27 junto destas features.
- Aguardando decisão: configurar `git config user.email` noreply neste repo.

## Onde paramos
- iter19: tasks 01–04 DONE (4/8); 05 (upgrade chama `migrate state-format`) IN_PROGRESS — executor parou com a
  sessão anterior (verificar cópia local/work/iter19 antes de retomar); 06 (versão/docs) depois da 05.
- iter21: intake→plano fechados; base real = aplicação 0/9 depois da correção (brief corta a memória, sem caderno);
  frente memoria ciclo 1 (oráculo 19→41/55); revisor achou F1 (corrigir 2× faz a lição sumir) — ciclo 2 e a mudança
  oficial M14 do oráculo pararam com a sessão anterior (retomar; cópia local/work/iter21 tem trabalho parcial).
- Vazamento do commit 44baf58 limpo: release/desenv-mac reescrita (bacfc07) e publicada pelo founder.

## Próximos passos
1. Retomar os 3 agentes parados: memoria ciclo 2 (local/work/iter21), oráculo mo2 (patch em
   campanhas/iter21/oraculo/mudanca-oficial/), task 05 (local/work/iter19) — conferir o parcial antes.
2. iter19: 05 → 06 → QA (portão) → REVIEW → aceite do founder → /fechar-feature → PORTE-WINDOWS.
3. iter21: depois do commit da iter19, frentes motor e emissao → integração → remedição real (claude -p) → decisão.

## Estado do ambiente
- Fora do commit do estado: obj/ da fixture em evals (gitignored agora); local/work/iter19 e iter21 (cópias); prova real
  em ~/cs-prova-iter21/.
- Branch remota release/version-windows existe (outra sessão; números de decisão conflitam com D-21+ daqui).

## Ponteiros
- PORTE-WINDOWS.md (D-21) · BACKLOG B-19..B-29 · DECISIONS D-17..D-21 · campanhas/iter21/.auto-correcao (local)
