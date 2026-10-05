Conduz o toque único de aprovação do modo autônomo para a feature `$$0` (spec em `$$1`).

1. Leia a spec `$$1` e os testes de aceite que ela cita; rode-os e mostre que falham hoje.
2. Classifique a feature (pequena, feature, risco). Classe `risco` não entra no autônomo: pare e diga por quê.
3. Proponha o mandato pelo motor, que deriva o orçamento do tamanho do plano (você não propõe números):
   `.swarm/bin/cs-auto propose --feature $$0 --spec $$1 --objetivo "<objetivo>" --nos <N estimado> --criterio 'AC-1|<texto>|<test-id>' --regressao "<comando>"`.
   Recusa (exit 1) traz a guarda (critério já verde, spec ausente, classe fora do autônomo): mostre-a e pare.
4. Mostre a proposta por comando, não por prosa: `.swarm/bin/cs-auto status`. Peça uma única aprovação.
5. Só o humano aprova (`/auto-approve`, no terminal dele); você nunca aprova. Recusado ou com ressalva:
   `/auto-amend`, ou fique no modo assistido.
6. Aprovado, o loop é do motor: repita `.swarm/bin/cs-auto tick` e execute só a ação que ele pedir
   (planejar, despachar, revisar). Pare em `ASK_HUMAN` e traga `por_que` e `opcoes`; relatório: `/auto-report`.
