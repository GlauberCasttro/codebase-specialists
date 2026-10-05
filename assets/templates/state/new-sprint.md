Cria uma sprint pelo motor. Você não monta caminho nem id e não cria arquivo à mão.

DoR da sprint: `--meta` (uma linha, verificável) e, se pertencer a um épico, `--epico <EPC>`.

1. Contexto: `.swarm/bin/cs-state board --json` (épicos e sprints existentes, ids reais).
2. Extraia meta e épico de: $$ARGUMENTS. Faltou a meta → pergunte ao usuário; não invente.
3. Mostre antes, por script:
   `.swarm/bin/cs-state new sprint --meta "<meta>" [--epico <EPC>] --dry-run`
   e apresente `ids` e `criar` do JSON ao usuário.
4. Confirmado, rode o mesmo comando sem a flag de simulação:
   `.swarm/bin/cs-state new sprint --meta "<meta>" [--epico <EPC>]`
5. Mostre a linha `criado <ID> em <caminho>` da saída. Exit ≠0 → mostre a mensagem do motor e pare.
6. Iniciar a sprint é outro passo: `.swarm/bin/cs-state start <id>` (só quando o usuário pedir).
