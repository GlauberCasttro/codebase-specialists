Monta o plano do mandato em PLANNING/REPLANNING. O motor valida; você só descreve os nós.

1. Contexto: `.swarm/bin/cs-auto tick` (traz feature, critérios a cobrir e lições; use o que ele imprime).
2. Para cada nó: `.swarm/bin/cs-auto plan add-node --id <ID> --tipo <US|BUG|FIX> --agent <A> --title "<T>" --path <P>... --cobre AC-1[,AC-2] [--deps a,b]`.
3. Ajustar: `.swarm/bin/cs-auto plan edit-node --id <ID> ...`; recomeçar: `.swarm/bin/cs-auto plan reset`.
4. Entregar: `.swarm/bin/cs-auto plan submit` (replano: `--motivo "<M>" --evidencia <REF>`).
5. Exit 1 = recusa com `guarda X:`; mostre a mensagem do motor, corrija o nó e submeta de novo. Não contorne.
6. Mostre o plano aceito por comando: `.swarm/bin/cs-auto status --json`; depois `/auto-tick`.
