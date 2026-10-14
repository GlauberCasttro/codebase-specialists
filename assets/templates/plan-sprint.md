Planeja a próxima sprint chamando só o script; não leia nem edite o board à mão.

1. Rode `.swarm/bin/cs-state board` e liste as stories com DoR (READY) por feature.
2. Proponha ao usuário, numa mensagem: meta da sprint (1 linha), orçamento e as stories comprometidas.
3. Aprovado: crie a sprint com `.swarm/bin/cs-state new sprint --meta "<meta>" [--epico EPC-nnn]` e planeje cada item com `.swarm/bin/cs-state plan <story|task> --sprint SPR-nnn $$ARGUMENTS` (uma chamada por item). Item que não vale mais: `.swarm/bin/cs-state drop <id> --reason "<motivo>"`.
4. Se o script recusar um item por DoR, mostre o motivo e devolva-o ao PO; não contorne.
5. Mostre a saída do script e pare. Início: `.swarm/bin/cs-state sprint start`.
