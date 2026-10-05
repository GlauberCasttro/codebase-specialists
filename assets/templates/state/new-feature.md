Cria uma feature pelo motor. Você não monta caminho nem id e não cria arquivo à mão.

DoR da feature: título, pai (`--sprint <SPR>` ou `--backlog`) e `--aceite <cmd>`: o comando do teste de
aceite, que precisa FALHAR hoje. Quem decide se o DoR passa é o `cs-state check`, não você.

1. Contexto: `.swarm/bin/cs-state board --json` (sprints e features existentes, ids reais).
2. Extraia título, sprint e comando de aceite de: $$ARGUMENTS. Faltou o aceite → pergunte; não invente.
3. Mostre antes, por script:
   `.swarm/bin/cs-state new feature --title "<título>" (--sprint <SPR> | --backlog) --aceite "<cmd>" --dry-run`
   e apresente `ids` e `criar` do JSON ao usuário.
4. Confirmado, rode o mesmo comando sem a flag de simulação:
   `.swarm/bin/cs-state new feature --title "<título>" (--sprint <SPR> | --backlog) --aceite "<cmd>"`
5. Confira o DoR pelo script: `.swarm/bin/cs-state check <id criado>`.
   Exit 1 lista o que falta (ex.: `aceite` quando o teste já passa) → mostre e resolva com o usuário.
6. Iniciar é outro passo: `.swarm/bin/cs-state start <id>` (o motor reconfere o mesmo DoR).
