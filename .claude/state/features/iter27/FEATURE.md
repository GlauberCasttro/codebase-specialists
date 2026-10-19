# iter27 — CLI e motor inteiros em inglês

FEATURE-ID: iter27
Nome: CLI e motor inteiros em inglês (B-72 + B-68 + B-71)

## História
Como founder que opera os alvos (e como agente que lê as skills emitidas), quero que toda flag da CLI do harness
(cs-state, cs-auto, cs-route, cs.py) e toda chave do item da árvore em memória sejam em inglês, com o português aceito
só como alias depreciado, para que um alvo fale um vocabulário só e a iter28 (task melhor) não reabra os mesmos
arquivos com dois idiomas.

## Problema / Contexto
A 0.14.0 (iter26) deixou o inglês pela metade, medido na E2 (HEAD 9e908e0):
- 28 nomes de flag pt sem equivalente en em 35 linhas de argparse: `scripts/harness/engine/state.py:226-278` (9),
  `scripts/harness/engine/auto.py:3150-3210` (16), `scripts/harness/engine/router.py:279,282` (2), e
  `--allow-outside` em `scripts/cs.py:88`, `scripts/upgrade/cli.py:31`, `scripts/harness/cli.py:98`,
  `scripts/emit/cli.py:246`. O alias da iter26 cobre só `new task|story` (`state.py:814-850`) (F1).
- O `--allow-outside` dispara o classificador de "safety bypass" do auto mode e o `upgrade --apply` é negado na cobaia
  .NET (B-71 a, F10). O plano do upgrade cita "(.swarm/state/board.json5, events.jsonl)" — o log é
  `.swarm/events.jsonl` (`scripts/upgrade/core.py:64`, F9).
- 311 citações de flag pt em textos do produto (dicas e recusas no código 126, docs 94, assets 38, references 26,
  MODO-DE-USO 18, SKILL 9); a recusa do DoR cita `--criterio` (`tree.py:473,612`); a skill emitida auto-plan cita
  `--tipo/--cobre/--motivo/--evidencia` (`assets/templates/state/auto-plan.md:4,6`) e nenhum teste confere o cs-auto
  contra o parser (`scripts/doctests/tests/test_commands_parse.py:78-83`, F8).
- Um aviso de depreciação por flag (`state.py:840,844`, F2); o `--dry-run` não mostra o item (`tree.py:263-264`, F3).
- O motor guarda o item em memória com 28 chaves pt e `kind: "epico"` (`hcore.py:254-310`, F4); os eventos `tput`
  gravados carregam essa forma (`tree.py:192`), então o replay tem de ler pt para sempre. A migração preserva
  `kind: "epico"` no disco (`tree.py:1964`, F5). A fronteira mandato → árvore é `node_spec` (`auto.py:1127-1143`, F6).
- Oráculos: 728 citações de flag pt em 52 arquivos; nenhum lê chave pt da forma interna (F7) ⇒ com alias, nenhuma
  mudança oficial prevista.

## Valor de negócio
Um vocabulário só no alvo: o operador e o agente digitam o que leem, a skill emitida ensina o que o parser aceita, o
auto mode deixa o upgrade passar, e a iter28 começa sobre um modelo fechado.

## Personas / Stakeholders
- founder (opera os alvos; decidiu a D-46)
- agente do alvo (lê as skills emitidas e chama a CLI)
- cobaia .NET e repositório-piloto (projeto-legado) — alvos com histórico pt que não pode quebrar
- iter28 (consome o modelo canônico)

## Critérios de Aceitação
- **CA-01 — cs-state com flags en em todos os subcomandos da árvore.** DADO um alvo em árvore, QUANDO
  `new epic|sprint|feature|task|story`, `move` e `close` recebem as flags en (`--objective`, `--metric`, `--goal`,
  `--epic`, `--accept-cmd`, `--proving-test`, `--criterion`, `--standalone`, `--return`), ENTÃO criam/movem/fecham
  igual ao nome pt de hoje; e o nome pt segue aceito como alias depreciado, com aviso no stderr, fora do `--help`.
  Prova: `cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA01`
- **CA-02 — cs-auto e cs-route com flags en.** DADO um mandato e o roteador, QUANDO `propose`, `approve|amend`,
  `resolve`, `plan add-node|edit-node|submit`, `reflect`, `escalate`, `pause` (cs-auto) e `outcome`, `anular`
  (cs-route) recebem as flags en (`--objective`, `--nodes`, `--criterion`, `--regression`, `--class`, `--gate`,
  `--budget`, `--escalation`, `--type`, `--covers`, `--proving-test`, `--reason`, `--evidence`, `--text`,
  `--condition`, `--node`, `--provenance`), ENTÃO o efeito é o mesmo do nome pt de hoje; o pt segue como alias
  depreciado, com aviso, fora do `--help`. As chaves internas do mandato não mudam (D-20).
  Prova: `cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA02`
- **CA-03 — um aviso por chamada, en vence.** DADO uma chamada com N flags pt, QUANDO ela roda, ENTÃO o stderr tem
  UMA linha de depreciação listando as N (`pt → en`); se o nome en também veio, o en vale e a linha diz que o pt foi
  ignorado.
  Prova: `cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA03`
- **CA-04 — `--include-emitted` no lugar de `--allow-outside`.** DADO `emit`, `harness install`, `upgrade --apply`
  e `init --replace-harness`, QUANDO recebem `--include-emitted`, ENTÃO escrevem fora de `.swarm/` como hoje; a
  recusa sem a flag cita `--include-emitted`; `--allow-outside` segue aceito como alias depreciado (com aviso); o
  plano do upgrade cita `.swarm/events.jsonl` como o log de eventos.
  Prova: `cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA04`
- **CA-05 — nenhum texto do produto ensina flag pt.** DADO os textos emitidos num alvo (skills, orquestrador,
  CLAUDE.md), SKILL.md, MODO-DE-USO.md, references/ (fora o histórico em `references/migrations.json5`), docs/ e as
  dicas/recusas do código (fora as tabelas de alias), QUANDO varridos, ENTÃO 0 citação de flag pt; a recusa do DoR
  cita `--criterion`.
  Prova: `cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA05`
- **CA-06 — toda flag citada parseia, inclusive no cs-auto.** DADO o doctest de comandos, QUANDO roda, ENTÃO o
  cs-auto está entre os bins conferidos e todo comando citado nos textos parseia contra o argparse real.
  Prova: `cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA06`
- **CA-07 — o dry-run mostra o item.** DADO `new epic|sprint|feature|task|story --dry-run`, QUANDO roda, ENTÃO a
  saída JSON mantém `{ids, criar, mover, eventos}` e traz também o item que seria gravado (chaves en, a mesma forma do
  arquivo), e nada é escrito.
  Prova: `cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA07`
- **CA-08 — o motor pensa em inglês.** DADO um alvo com itens, sessões e eventos gravados pela 0.14.0 (chaves pt nos
  `tput` e `kind: "epico"`), QUANDO o motor carrega o board, ENTÃO nenhum item da árvore nem sessão em memória tem
  chave pt de `ITEM_SCHEMA`/`SESSION_SCHEMA` nem `kind: "epico"`; o replay do histórico pt dá o mesmo estado; os
  eventos novos gravam o item com chaves en; o arquivo do item gravado é byte a byte o mesmo de hoje para a mesma
  operação; nenhum `def` é removido.
  Prova: `cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA08`
- **CA-09 — 0.15.0 chega aos alvos sem regressão.** DADO um alvo na 0.14.0 com `kind: "epico"` no disco, QUANDO
  `upgrade --apply --include-emitted` roda, ENTÃO sai 0, o disco passa a `kind: "epic"`, `validate --strict` passa,
  `events.jsonl` fica byte a byte intacto e os textos emitidos não citam flag pt; VERSION = 0.15.0.
  Prova: `cd campanhas/iter27/oraculo && python3 -m unittest test_iter27.TestCA09`

## RNFs
- RNF-01: Python 3.9+ stdlib; verde em `python3` e `/usr/bin/python3` (o portão roda os dois).
- RNF-02: compatibilidade para trás — todo nome pt de hoje continua funcionando (alias), e alvos com histórico pt
  (eventos, `.json5`, `kind: "epico"`) seguem legíveis; nenhum oráculo antigo que passa no HEAD passa a falhar (D-35).
- RNF-03: nenhum `def` removido (portão); as funções de tradução antigas (`item_to_pt`, `session_to_pt`) ficam,
  mesmo que só para compatibilidade.
- RNF-04: a prosa segue em português (D-07); só nomes de flag e chave mudam.
- RNF-05: o motor instalado no alvo continua sendo a lista de `ENGINE_FILES` (`scripts/harness/install.py:29`) —
  módulo novo só se entrar nela.

## Edge cases
- pt e en da mesma flag na mesma linha: o en vence, o pt é ignorado com aviso (CA-03).
- flag pt com `=` (`--objetivo=x`) e sem (`--objetivo x`).
- `--no` do `escalate` (= nó) não pode ser confundido com prefixos `--no-*` de outros comandos.
- `--criterion` já existe no `add story` legado (`state.py:74`): o mesmo nome com o mesmo significado.
- evento antigo com item pt e evento novo com item en no mesmo `events.jsonl` (replay misto).
- `.json5` legado com chaves pt e `kind: "epico"` (lido como hoje).
- skill emitida antiga (antes do upgrade) chamando as flags pt num alvo já na 0.15.0.

## Dependências
- nenhuma feature ativa; a iter26 (0.14.0) entregue é a base. A iter28 depende desta.

## Escopo IN
- B-72 (a–e): flags en com alias pt em cs-state, cs-auto e cs-route; aviso agregado; dry-run com o item.
- B-68: forma interna do item e da sessão em inglês; leitura pt → en na entrada (disco legado e replay);
  `kind: "epico"` normalizado na migração do upgrade.
- B-71 (a, b): `--include-emitted` com alias `--allow-outside`; caminho exato do log no plano do upgrade.
- textos do produto (skills emitidas, SKILL, MODO-DE-USO, references, docs, dicas do código) citando só flags en;
  cs-auto no doctest; VERSION 0.15.0 com a migração.

## Escopo OUT
- subcomandos com nome pt (`cs-auto senha definir`, `cs-auto conferir`, `cs-route anular`) — superfície da senha e
  do guard; vira B-73.
- chaves e valores do mandato M5 (`PLANO_KEYS`, nós do plano, critérios, escaladas, `resolve --choice`) — D-20/B-21.
- o contrato de saída do dry-run `{ids, criar, mover:{de,para}, eventos}` (só ganha campo; afirmado pela iter10).
- prosa em português; reescrever events.jsonl/archive dos alvos; a entrada histórica de `references/migrations.json5`.
- `.claude/` deste harness (inclusive `.claude/tools/ac/`); a iter28 e a iter29; B-49, B-69, B-70.

## Escopo de escrita
- `scripts/harness/engine/state.py`
- `scripts/harness/engine/auto.py`
- `scripts/harness/engine/router.py`
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/hcore.py`
- `scripts/harness/engine/session.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/cli.py`
- `scripts/harness/install.py`
- `scripts/harness/replace.py`
- `scripts/cs.py`
- `scripts/upgrade/cli.py`
- `scripts/upgrade/core.py`
- `scripts/emit/cli.py`
- `scripts/emit/apply.py`
- `scripts/emit/platforms.py`
- `scripts/harness/tests/*.py`
- `scripts/emit/tests/*.py`
- `scripts/stage/tests/test_iter4_stages.py`
- `scripts/upgrade/tests/*.py`
- `scripts/doctests/tests/test_commands_parse.py`
- `assets/templates/*.md`
- `assets/templates/state/*.md`
- `SKILL.md`
- `MODO-DE-USO.md`
- `README.md`
- `VERSION`
- `references/harness.md`
- `references/platforms.md`
- `references/stages.json5`
- `references/ARCHITECTURE.md`
- `references/migrations.json5`
- `docs/*.md`
- `docs/fases/*.md`
- `docs/exemplos/*.md`

## Critério de parada
Oráculo iter27 100% verde (CA-01..CA-09) em python3 e /usr/bin/python3; oráculos iter13, iter16, iter18..iter26
inteiros verdes; iter10/iter15 sem regressão contra o HEAD (D-35); suítes do produto e harness-dev verdes; 0 `def`
removido; VERSION 0.15.0. Teto: 3 ciclos de correção por task antes de escalar ao founder.

## Métrica de sucesso
- flags pt sem nome en: 28 → 0 (e `--allow-outside` → `--include-emitted`).
- chaves pt na forma interna do item/sessão: 28 + `kind: "epico"` → 0.
- citações de flag pt nos textos do produto: 311 → 0.
- bins com flags conferidas pelo doctest: 4 → 5 (cs-auto).
- linhas de aviso por chamada com N flags pt: N → 1.

## Aceite da Feature
### Aceite QA — PENDENTE
### Aceite Review — PENDENTE
