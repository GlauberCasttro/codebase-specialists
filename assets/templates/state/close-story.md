Fecha uma story composta pelo motor: ele confere o DoD, move o item e grava o evento. Você não move arquivo.

1. Contexto: `.swarm/bin/cs-state board --json` (id real e status; não leia arquivos de estado).
2. Extraia o id e o resumo de: $$ARGUMENTS. Sem resumo do que foi entregue → pergunte ao usuário.
3. Mostre antes, por script:
   `.swarm/bin/cs-state close <US|BUG|FIX id> --summary "<resumo>" --dry-run`
   e apresente `mover` e `eventos` do JSON ao usuário.
4. Confirmado, rode o mesmo comando sem a flag de simulação:
   `.swarm/bin/cs-state close <US|BUG|FIX id> --summary "<resumo>"`
5. Exit 1 = recusa: o motor lista o que falta (cada task da story ainda pendente). Mostre a lista e pare; não contorne.
6. A story só fecha com todas as suas tasks fechadas: feche-as antes com `/close-task`.
