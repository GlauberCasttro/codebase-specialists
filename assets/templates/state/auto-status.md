Mostra o estado do mandato autônomo pelo motor; não leia nem edite arquivos de estado.

1. Resumo: `.swarm/bin/cs-auto status --brief $$ARGUMENTS` (objetivo, estado e o comando do primeiro passo).
2. Para decidir (orçamento, aceite, plano, escaladas): `.swarm/bin/cs-auto status --json`; use os ids que ele traz.
3. Proposta ou plano: mostre a saída do comando ao usuário; não a reescreva em prosa.
4. Sem mandato (`mandato: null`): diga isso e pare.
5. Agir: `/auto-tick` (modelo); os atos de decisão do mandato são só do humano e têm skill própria (`/auto-*`).
