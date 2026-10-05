Planeja a próxima sprint chamando só o script; não leia nem edite o board à mão.

1. Rode `.swarm/bin/cs-state board` e liste as stories com DoR (READY) por feature.
2. Proponha ao usuário, numa mensagem: meta da sprint (1 linha), orçamento e as stories comprometidas.
3. Aprovado: `.swarm/bin/cs-state sprint plan --goal "<meta>" --budget <orçamento> --stories <US-1,BUG-2,...> $$ARGUMENTS`.
4. Se o script recusar uma story por DoR, mostre o motivo e devolva-a ao PO; não contorne.
5. Mostre a saída do script e pare. Início: `.swarm/bin/cs-state sprint start`.
