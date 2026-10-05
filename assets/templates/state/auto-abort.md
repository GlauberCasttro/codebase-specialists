Humano aborta o mandato (ABORTED). Nada é desfeito sozinho; o relatório traz o comando de restauração.

1. Estado atual: `.swarm/bin/cs-auto status --brief`.
2. Motivo em: $$ARGUMENTS. Sem motivo → pergunte ao usuário.
3. Confirmado: `.swarm/bin/cs-auto abort --by <nome do humano> --reason "<motivo>"`.
4. Exit 1 = recusa: mostre a mensagem do motor e pare.
5. Depois: `.swarm/bin/cs-auto report` e mostre o comando `restaurar`; só o humano o executa.
