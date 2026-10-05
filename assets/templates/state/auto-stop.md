Humano manda o mandato encerrar com relatório (WRAPPING_UP, gatilho stop_humano).

1. Estado atual: `.swarm/bin/cs-auto status --brief`.
2. Motivo em: $$ARGUMENTS. Sem motivo → pergunte ao usuário.
3. Confirmado: `.swarm/bin/cs-auto stop --by <nome do humano> --reason "<motivo>"`.
4. Exit 1 = recusa: mostre a mensagem do motor e pare.
5. Depois: `/auto-tick` conduz o encerramento e `/auto-report` mostra o relatório.
