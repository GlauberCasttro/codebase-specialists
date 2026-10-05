Humano aprova a proposta do mandato autônomo. Assina o aceite, a regressão e o ponto seguro.

1. Mostre a proposta por comando: `.swarm/bin/cs-auto status` (objetivo, critérios, nós estimados, orçamento derivado).
2. O orçamento é calculado pelo motor; só o humano o muda, aqui, em: $$ARGUMENTS (`despachos=,tentativas=,replanos=,minutos=`).
3. Confirmado: `.swarm/bin/cs-auto approve --by <nome do humano> [--orcamento <valores>]`.
4. Exit 1 = recusa: mostre a mensagem do motor e pare; não contorne.
5. Depois: `/auto-tick` (o motor pede o plano).
