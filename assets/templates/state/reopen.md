Reabre um item fechado pelo motor: ele o devolve ao mesmo caminho e grava o evento. Você não move arquivo.

1. Contexto: `.swarm/bin/cs-state find <texto>` ou `.swarm/bin/cs-state tree --json` (id real do item fechado).
2. Extraia o id e o motivo de: $$ARGUMENTS. Sem motivo → pergunte ao usuário; o motivo é obrigatório.
3. Mostre antes, por script:
   `.swarm/bin/cs-state reopen <id> --reason "<motivo>" --dry-run`
   e apresente `mover` e `eventos` do JSON ao usuário.
4. Confirmado, rode o mesmo comando sem a flag de simulação:
   `.swarm/bin/cs-state reopen <id> --reason "<motivo>"`
5. Exit ≠0 = recusa: mostre a mensagem do motor e pare; não contorne.
