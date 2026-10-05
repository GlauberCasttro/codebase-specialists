Humano resolve uma escalada do mandato (AWAITING_HUMAN). As opções vêm do pacote, não da sua memória.

1. Pacote e opções: `.swarm/bin/cs-auto status --json` (`escaladas[].opcoes`, `pacote`) ou `.swarm/bin/cs-auto tick`.
2. Extraia de $$ARGUMENTS a escolha (`retomar|trocar-agente|emendar|descartar-ramo|encerrar|abortar`) e a decisão.
   Sem decisão escrita → pergunte ao usuário.
3. Confirmado: `.swarm/bin/cs-auto resolve --choice <escolha> --by <nome do humano> --decision "<decisão>" [--agent <A>] [--escalada <ID>]`.
4. Exit 1 = recusa (escolha fora do pacote, p. ex.): mostre a mensagem do motor e pare.
5. Depois: `/auto-tick`.
