Estaciona uma feature ativa pelo motor: ela sai de execução com o motivo gravado. Você não move arquivo.

1. Contexto: `.swarm/bin/cs-state board --json` (id real da feature ativa).
2. Extraia o id da feature e o motivo de: $$ARGUMENTS. Sem motivo → pergunte ao usuário.
3. Mostre antes, por script:
   `.swarm/bin/cs-state park <FEA> --reason "<motivo>" --dry-run`
   e apresente `mover` e `eventos` do JSON ao usuário.
4. Confirmado, rode o mesmo comando sem a flag de simulação:
   `.swarm/bin/cs-state park <FEA> --reason "<motivo>"`
5. Exit ≠0 = recusa: mostre a mensagem do motor e pare; não contorne.
6. Retomar depois: `.swarm/bin/cs-state start <FEA>`.
