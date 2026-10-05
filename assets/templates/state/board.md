Mostra o quadro (épicos, sprints, features, stories, tasks) pelo motor; não leia nem edite arquivos de estado.

1. Leitura humana: `.swarm/bin/cs-state board $$ARGUMENTS`.
2. Leitura para decidir (ids, status, caminho de cada item): `.swarm/bin/cs-state board --json` ou
   `.swarm/bin/cs-state tree --json`. Use o `id` e o `path` que o JSON traz; nunca monte caminho nem id.
3. Procurar um item (inclusive id antigo depois de `move`): `.swarm/bin/cs-state find <texto>`.
4. Responda com o que a saída mostra; para mudar estado, use as skills `/new-*`, `/close-*`, `/move`, `/park`,
   `/reopen` (o motor decide e grava).
