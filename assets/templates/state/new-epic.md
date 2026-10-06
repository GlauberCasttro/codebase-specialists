Cria um épico pelo motor. Você não monta caminho nem id e não cria arquivo à mão.

DoR do épico: título, `--objetivo` (o resultado de negócio) e, se houver, `--metrica` (como medir).

1. Contexto: `.swarm/bin/cs-state board --json` (épicos existentes; evite duplicar).
2. Extraia título, objetivo e métrica de: $$ARGUMENTS. Faltou o objetivo → pergunte ao usuário; não invente.
3. Mostre antes, por script:
   `.swarm/bin/cs-state new epico --title "<título>" --objetivo "<objetivo>" [--metrica "<métrica>"] --dry-run`
   e apresente `ids` e `criar` do JSON ao usuário.
4. Confirmado, rode o mesmo comando sem a flag de simulação:
   `.swarm/bin/cs-state new epico --title "<título>" --objetivo "<objetivo>" [--metrica "<métrica>"]`
5. Mostre a linha `criado <ID> em <caminho>` da saída. Exit ≠0 → mostre a mensagem do motor e pare.
6. Iniciar o épico é outro passo: `.swarm/bin/cs-state start <id>` (só quando o usuário pedir).
