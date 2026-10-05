Cria uma story pelo motor (1 agente → task tipada; 2+ agentes → story composta, uma task por agente).
Você não monta caminho nem id e não cria arquivo à mão.

DoR por tipo (o texto orienta; a DECISÃO é do `cs-state check`):
- US: `--como --quero --para` (como / quero / para) e ao menos um critério:
  `--criterio 'AC-1|Dado…Quando…Então…|<test-id>'`.
- BUG: `--reproducao <test-id>`: o teste de reprodução precisa FALHAR hoje.
- FIX: `--fixes <id do BUG>` (fixes) e `--teste <test-id>`.
Todos: `--title "<título>" --feature <FEA> --agents <a>[,<b>] --verify-cmd "<cmd>"`.

1. Contexto: `.swarm/bin/cs-state board --json` (features e agentes com ids reais).
2. Extraia tipo, feature, agentes e dados do DoR de: $$ARGUMENTS. Faltou dado → pergunte; não invente.
3. Mostre antes, por script:
   `.swarm/bin/cs-state new story --tipo <US|BUG|FIX> <flags acima> --dry-run`
   e apresente `ids` e `criar` do JSON ao usuário.
4. Confirmado, rode o mesmo comando sem a flag de simulação:
   `.swarm/bin/cs-state new story --tipo <US|BUG|FIX> <flags acima>`
5. Confira o DoR pelo script: `.swarm/bin/cs-state check <id criado>` (para cada id da saída).
   Exit 1 lista o que falta (`critério`, `passa`, `fixes`) → mostre ao usuário; não contorne.
6. Começar é outro passo: `.swarm/bin/cs-state start <id>`.
