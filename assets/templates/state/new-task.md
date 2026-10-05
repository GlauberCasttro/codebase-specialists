Cria uma task pelo motor. Você não monta caminho nem id e não cria arquivo à mão.

DoR por tipo (o texto orienta; a DECISÃO é do `cs-state check`):
- US: `--como --quero --para` (como / quero / para) e ao menos um critério:
  `--criterio 'AC-1|Dado…Quando…Então…|<test-id>'`.
- BUG: `--reproducao <test-id>`: o teste de reprodução precisa FALHAR hoje.
- FIX: `--fixes <id do BUG>` (fixes) e `--teste <test-id>`; o close exige o teste do BUG verde.
- CHORE: manutenção sem valor de usuário: `--motivo "<por quê>"` e `--verify-cmd "<cmd>"`; sem como/quero/para.
Todos: `--agent <agente> --title "<título>" --allowed-path <glob>... --verify-cmd "<cmd>"` e UM pai:
`--feature <FEA>` | `--sprint <SPR>` | `--story <US>` | `--avulsa` | `--backlog`.

1. Contexto: `.swarm/bin/cs-state board --json` (pais e agentes com ids reais).
2. Extraia tipo, pai e dados do DoR de: $$ARGUMENTS. Faltou dado → pergunte ao usuário; não invente.
3. Mostre antes, por script:
   `.swarm/bin/cs-state new task --tipo <US|BUG|FIX|CHORE> <flags acima> --dry-run`
   e apresente `ids` e `criar` do JSON ao usuário.
4. Confirmado, rode o mesmo comando sem a flag de simulação:
   `.swarm/bin/cs-state new task --tipo <US|BUG|FIX|CHORE> <flags acima>`
5. Confira o DoR pelo script: `.swarm/bin/cs-state check <id criado>`.
   Exit 1 lista o que falta (`critério`, `passa`, `fixes`, `motivo`, `verify`) → mostre; não contorne.
6. Começar é outro passo: `.swarm/bin/cs-state start <id>` (o motor reconfere o DoR e calcula a wave).
