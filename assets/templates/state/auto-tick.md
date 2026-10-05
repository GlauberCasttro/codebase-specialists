Pede ao motor a próxima ação do mandato e executa só ela. Integrar, verificar, aceitar e fechar são do script.

1. `.swarm/bin/cs-auto tick --json $$ARGUMENTS` e leia `acao`, `alvo`, `agente`, `model`, `comando`.
2. PLAN/REPLAN: use `/auto-plan`. DISPATCH: ferramenta Agent com `agente` e `model` do tick, e o `alvo` na description.
3. REVIEW/FINAL_REVIEW: despache o gate indicado; veredito com `cs-auto final-review`. REFLECT: `cs-auto reflect`
   com `evidencia` do tick. ANSWER_ORPHAN: `cs-auto orphan <task>`. RESUME: `cs-auto resume`.
4. Nunca rode verify, escreva brief nem edite a pasta do mandato à mão: o motor faz.
5. ASK_HUMAN: mostre `por_que` e `opcoes` do tick e pare; a decisão é só do humano (`/auto-*`).
6. REPORT: `/auto-report`. FIM: encerre. Depois de cada ação, rode o tick de novo.
