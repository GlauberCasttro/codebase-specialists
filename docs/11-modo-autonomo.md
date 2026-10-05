# Modo autônomo (0.8.0)

O modo autônomo deixa o time entregar uma feature (ou uma sprint) sem você a cada passo, com um **mandato** que
você assina. Regra de ouro: **o modelo só executa tasks; o script decide**. O piloto é `.swarm/bin/cs-auto`
(`motor: scripts/harness/engine/auto.py`); cada transição é um evento encadeado em `events.jsonl`
(`mandato.<transição>`).

## O mandato

Objetivo + critérios de aceite executáveis (`--criterio 'AC-n|texto|<teste ou comando>'`) + regressão (`--regressao`)
+ nós do plano + orçamento. Na proposta, o motor recusa: critério já verde (não prova entrega), classe trivial ou
`--nos` menor que 2 ("task avulsa"), spec ausente, mandato já aberto. O **orçamento é derivado do tamanho do plano**
(despachos, tentativas, replanos, minutos) e só o humano o altera, na aprovação (`cs-auto approve --orcamento`) ou
numa emenda (`cs-auto amend --orcamento`).

## Fluxo

1. `cs-auto propose` (`--feature FEA-nnn` ou `--sprint SPR-nnn`, `--spec`, `--objetivo`, `--nos`, `--criterio`,
   `--regressao`, `--classe`, `--portao`, `--rigor lean|standard|paranoid`) imprime `MAN-nnn`.
2. Humano: `cs-auto status` para ler, `/auto-approve` (com a senha) para assinar. Aprovar assina o aceite, a
   regressão e o ponto seguro.
3. Plano: o modelo monta com `cs-auto plan add-node` / `edit-node` / `reset` e entrega com `cs-auto plan submit`.
   O motor valida: DAG sem ciclo, nós no território do agente, cobertura dos critérios, plano dentro do orçamento,
   ondas calculadas, lições consultadas.
4. Execução: `cs-auto tick` em laço (`/auto-tick`). Cada chamada retorna uma única ação; o modelo a executa e chama
   `tick` de novo. Verificar, aceitar e fechar task são trabalho do script, nunca do modelo. Cada task é verificada
   pelo próprio teste; o aceite da feature é medido só ao fechar cada onda.
5. Apoio a `tick`: `cs-auto reflect <task> --texto … --evidencia …` (reflexão de task), `cs-auto orphan <task>`
   (subagente morreu: sem mudança no disco a task volta à fila; com mudança vai direto à verificação),
   `cs-auto final-review --by … --verdict …` (revisão final), `cs-auto spend --usd …` (custo registrado),
   `cs-auto escalate --condicao …` (escalada com pacote de opções).
6. `/auto-report` (`cs-auto report`): critérios verdes, verificações com hash, itens devolvidos.

## Máquina de 12 estados

- **PROPOSED**: proposta feita, aguardando humano (`approve`, `amend`, `abort`).
- **CHARTERED**: aprovado e assinado; falta o plano.
- **PLANNING**: plano sendo montado/submetido (também a porta de entrada da próxima feature de um mandato de sprint).
- **RUNNING**: ondas em execução via `tick`.
- **INTEGRATING**: onda fechada; o motor avalia, nesta ordem, concluir, seguir para a próxima onda ou replanejar.
- **REPLANNING**: replano com evidência citada, nós aceitos intocados.
- **AWAITING_HUMAN**: nada mais pode rodar; pacote de escalada aberto.
- **PAUSED**: pausa (manual, ou pelo hook PreCompact); retomada volta ao estado de origem.
- **WRAPPING_UP**: encerrando com entrega parcial (gatilhos: orçamento aos 80%/100%, sem progresso, stop humano,
  critérios órfãos, encerrar).
- **DONE**: todos os critérios verdes e revisão final aprovada. Terminal.
- **HANDED_BACK**: entrega parcial, relatório gerado, pendências devolvidas ao backlog. Terminal.
- **ABORTED**: abortado pelo humano com motivo. Terminal.

## Portão humano

`approve`, `amend`, `resolve`, `stop` e `abort` exigem `--by <humano>` e o guard bloqueia o modelo de rodá-los
(nas skills: `/auto-approve`, `/auto-amend`, `/auto-resolve`, `/auto-stop`, `/auto-abort`). As 4 skills do modelo são
`/auto-status`, `/auto-plan`, `/auto-tick`, `/auto-report`. `cs-auto resolve --choice` aceita `retomar`,
`trocar-agente` (com `--agent`), `emendar`, `descartar-ramo`, `encerrar`, `abortar`, sempre com `--decision`.

## Orçamento e corte

Aos **80%** o corte é suave: com 5 despachos, o 4º ainda sai e termina, o 5º nunca sai; o mandato entra em
WRAPPING_UP e entrega parcial, devolvendo o restante ao backlog. Sem progresso (rodadas que não avançam o aceite) o
motor replaneja **uma vez**; se continuar parado, encerra com entrega parcial em vez de escalar por contagem.

## Ramo travado

Task que precisa de área congelada (ou foi escalada) trava só o seu ramo e quem depende dele. O mandato vai a
AWAITING_HUMAN apenas quando não sobra nenhum nó executável. As opções do `resolve` estão no pacote da escalada.

## Pausa e retomada

`cs-auto pause [--motivo …]` marca o que está em voo; `cs-auto resume` volta exatamente ao estado anterior
(confere o carimbo). O PreCompact pausa um mandato em andamento sozinho (sem mandato, não faz nada). O tempo pausado
não consome o orçamento de minutos.

## Fora de escopo nesta versão

Promoção de lições no fim, diário, modelo do verificador maior ou igual ao do autor, revisão cega, custo medido
pelo roteador e modo semiautônomo para plataformas sem hook.

Migração: veja [09-upgrade.md](09-upgrade.md) (Migração 0.8.0).
