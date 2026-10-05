Troca o pai de um item pelo motor: ele move, mantém o id antigo resolvendo em `find` e grava o evento.
Você não move arquivo nem calcula id.

1. Contexto: `.swarm/bin/cs-state board --json` (ids reais do item e do novo pai).
2. Extraia o id e o destino (novo pai, ou avulsa) de: $$ARGUMENTS.
3. Mostre antes, por script:
   `.swarm/bin/cs-state move <id> (--to <pai> | --avulsa) --dry-run`
   e apresente `mover` e `eventos` do JSON ao usuário.
4. Confirmado, rode o mesmo comando sem a flag de simulação:
   `.swarm/bin/cs-state move <id> (--to <pai> | --avulsa)`
5. Exit 1 = recusa (ex.: sprint para dentro de feature, épico para dentro de sprint): mostre e pare.
