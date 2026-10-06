# codebase-specialists — modo de uso

Monta, para um repositório, um time de agentes que **conhece** o código (território de escrita, regras técnicas e de
negócio, termos, histórico, comandos reais) e prova isso numa sonda com gabarito mecânico. Instala um harness com
estado, guards e memória. Emite para Claude Code, Cursor, Copilot e Codex.

## Antes de rodar

| | |
|---|---|
| Repositório | `git status` limpo — a skill escreve em `.swarm/`, `.claude/`, `.cursor/`, `.github/`, `.codex/`, `AGENTS.md`, `CLAUDE.md` (bloco gerenciado, com backup) e `Makefile` (uma linha `include`) |
| Runtime | `python3` ≥ 3.9 (só stdlib). As ferramentas do repo (testes, lint) instaladas melhoram o scan; ausentes viram `unavailable`, sem culpar o repo |
| Tempo | modo padrão: ~20–30 min num repo pequeno/médio; `--full`: ~2× |
| Outro harness | a skill instala **um harness só**. Se o repo já tem outro (v8: `.swarm/instance.json`, `scripts/harness/`, `.claude/kernel/`, hooks de terceiros no `.claude/settings.json`), o `init` **recusa sem escrever** (exit 3) e mostra o plano de substituição — veja "Repo com outro harness" |
| Limite de uso | usa vários subagentes (lotes de até 3). Se a sua janela estiver acabando, encerre a etapa e continue numa sessão nova (veja "Retomar") |

## Rodar — comando

Na sessão do Claude Code aberta **no repositório**:

| Comando | Faz |
|---|---|
| `/codebase-specialists` | monta o time no modo padrão (rápido) |
| `/codebase-specialists --full` | modo certificado (mesa redonda + refino) |
| `/codebase-specialists status` | onde a execução está; não altera nada |
| `/codebase-specialists retomar` | continua de onde parou (outra sessão, limite de uso) |
| `/codebase-specialists uso` | mostra este guia |
| `/codebase-specialists upgrade` | repo já tem o time e a skill evoluiu: mostra o **plano** (`cs.py upgrade`: o que muda, o que fica preservado, o que sai de `.swarm/`; não escreve). Com o seu OK, `cs.py upgrade --apply` (backup em `.swarm/backups/`; se algo falhar, restaura) |

Ou em linguagem natural:

- `monta o time de agentes pra esse repo` → **modo padrão (rápido)**: scan, entrevista, time, cartões, exame,
  harness, gates. Sem mesa redonda e sem refino; agente reprovado sai `nao-especialista`.
- `monta o time ... --full` → **certificado**: inclui mesa redonda (revisão cruzada + cético) e até 2 ciclos de
  refino por agente reprovado. Use quando o time vai operar sozinho por muito tempo.

## Os toques com você (onde você muda o resultado)

1. **Plataformas** (init) — default: as 4.
2. **Entrevista de lacunas** (scan.6) — só o que o código não diz: regras de negócio que nunca quebram, quem decide
   o quê, áreas congeladas, o que é "feito". **Responda de verdade**: cada "não sei" vira um `gap.*` e o agente
   pergunta em vez de supor.
3. **Roster** (specialize.2) — nomes, territórios e porquê. Ajuste pela CLI antes de aprovar:
   `team roster move "<glob>" --to <agente>` · `rename <de> <para>` · `add` · `remove` (globs **sempre entre aspas**).
4. **O que será escrito fora de `.swarm/`** — a skill mostra a lista (`emit --dry-run`, `harness install
   --dry-run`) antes de escrever.
5. **Aprovação final** — GO só se todos os agentes passaram na sonda e os 16 gates estão verdes.
6. **Saneamento** (fim do init, approve.4) — `cs.py sanitize` mostra o plano (tamanhos; não apaga nada) e
   `cs.py sanitize --apply` apaga `.swarm/tmp/` e `__pycache__`, grava `.swarm/.gitignore` e diz o que
   entra no commit. Script deixado em `tmp/` aparece como DEFEITO (contorno manual) — anote para a `auto-correcao`.

## Onde fica o que a skill gera — `.swarm/`

Tudo o que a skill gera no alvo mora em `.swarm/`: `.swarm/run.json5` (progresso e `skill_version`),
`.swarm/facts/`, `.swarm/state/` (board e eventos), `.swarm/harness/` (motor e guard), `.swarm/bin/cs-*`,
`.swarm/memory/`, `.swarm/tmp/` e `.swarm/backups/`. Fora dela, só os artefatos emitidos (`.claude/`, `.cursor/`,
`.github/`, `.codex/`, `AGENTS.md`, `CLAUDE.md`), o `specialists.mk` com a linha `include` no `Makefile` e o
`.git/hooks/pre-commit` — sempre listados antes (`--dry-run`) e escritos só com `--allow-outside`.

## Repo com outro harness (harness único: `--replace-harness`)

Dois harnesses no mesmo repo brigam pelos mesmos hooks e pelo mesmo estado, então a skill nunca instala ao lado
de outro. Cada sinal sozinho basta para recusar: `.swarm/instance.json` (fábrica v8), `scripts/harness/`,
`.claude/kernel/` ou hook de terceiro no `.claude/settings.json` (um `settings.json` só com `permissions`/`env`
não conta). O `init` e o `harness install` saem com **exit 3 sem escrever nada** e imprimem o plano de
substituição. Para trocar, com o seu OK:

```
python3 ~/.claude/skills/codebase-specialists/scripts/cs.py init --platforms claude-code --replace-harness --allow-outside
```

1. **Backup fiel** (sha256 conferido antes de apagar) de todo arquivo do harness anterior em
   `.swarm/backups/harness-anterior/<caminho original>`, com manifesto.
2. Remove o harness anterior (`scripts/harness/`, `.claude/kernel/`, os hooks dele e o bloco dele no
   `lefthook.yml` e no `Makefile`), preservando o resto do repo byte a byte.
3. **Importa os fatos**: as invariantes de domínio (`DOMAIN_INVARIANTS.yaml`, BIZ-n) viram fatos citáveis em
   `.swarm/facts/`, com evidência apontando para a cópia no backup.
4. Segue o `init` normal. Rodar de novo depois é idempotente e não toca o backup.

`cs.py harness selftest` traz a sonda **harness único**: `FALHA` (exit 1) se sobrar resíduo de outro harness,
`OK` com a instalação limpa.

## Migração do legado (pasta `.specialists/` → `.swarm/`)

Repos gerados antes da versão `0.6.0` (arquivo `VERSION` da skill) têm a pasta antiga `.specialists/`. É o
**mesmo** harness, então não é caso de `--replace-harness`: o `init` recusa (exit 3) e aponta o `upgrade`.

```
python3 ~/.claude/skills/codebase-specialists/scripts/cs.py upgrade
python3 ~/.claude/skills/codebase-specialists/scripts/cs.py upgrade --apply --allow-outside
```

O primeiro só mostra o plano (cita a ação `rename-dir` e o destino `.swarm/`; não escreve). O segundo move
`.specialists/` para `.swarm/`, reescreve os caminhos do mecanismo (hooks, settings, `Makefile`, emitidos,
`.swarm/bin`, `.swarm/harness`) e preserva entrevista, roster, cartões, board, eventos, memória e ledgers (só
acrescentam). Grava `skill_version` = VERSION (`0.7.0`) em `.swarm/run.json5`; um segundo `upgrade` diz `nada a fazer`. Se
já existir um `.swarm/` de OUTRO harness junto do legado, o `upgrade --apply` recusa (exit 3) sem escrever.

## Retomar (sessão caiu, limite de uso, outra janela)

O estado vive em disco (`.swarm/run.json5`). Numa sessão nova, no mesmo repo:

```
python3 ~/.claude/skills/codebase-specialists/scripts/cs.py stage status
python3 ~/.claude/skills/codebase-specialists/scripts/cs.py stage load <etapa-atual>
```

Ou só peça "continua o codebase-specialists" — a skill faz isso. Nada é refeito.

> zsh: não guarde o comando numa variável (não divide palavras). Use uma função:
> `cs() { python3 ~/.claude/skills/codebase-specialists/scripts/cs.py "$@"; }`

## O estado é uma árvore de pastas (0.7.0)

O trabalho do time mora em `.swarm/` como **árvore de arquivos** — épico → sprint → feature → task —, em três
zonas: `backlog/` (ainda não começou), `state/` (em execução) e `archive/` (fechado, mesma árvore). A cadeia
`events.jsonl` fica na raiz de `.swarm/`; `INDEX.md` é gerado. **Só o `cs-state` escreve nas três zonas**: o
guard bloqueia o modelo (Write, Edit ou Bash `mv`/`cp`/`rm`) e `cs-state validate` reprova edição à mão, arquivo
órfão e item fechado em `state/`. Os ids são `EPC-nnn`, `SPR-nnn`, `FEA-nnn` e, nas stories, `US|BUG|FIX-nnn`;
task é `<id do pai>/<nn>` (o `nn` nunca é reaproveitado).

- **Stories simples e compostas.** Um agente só: a story vira **uma task tipada** em `tasks/`. Dois ou mais
  agentes: **story composta** (pasta com `story.json5` e uma task por agente, cada uma no território do agente).
  `cs-state promote <task>` converte uma simples em composta; `cs-state close <story>` só passa com todas as
  tasks fechadas e, senão, lista as pendentes sem mover nada.
- **Tipos de task e o DoR de cada um** (decidido por `cs-state check <id>`, só leitura; `start` usa a mesma regra):

| Tipo | Pronto para começar quando |
|---|---|
| `US` | tem `--como --quero --para` e ao menos um `--criterio` |
| `BUG` | tem `--reproducao` (teste que **falha hoje**; se já passa, o `check` reprova) |
| `FIX` | tem `--fixes` (id do BUG) e `--teste`; só fecha com o teste do BUG verde |
| `CHORE` | manutenção sem valor de usuário: tem `--motivo` e `--verify-cmd`; o `close` roda o verify de novo |

  A feature só nasce com `--aceite` (teste de aceite que ainda não passa); épico pede `--objetivo`, sprint `--meta`.
- **Uma feature ativa por vez.** `cs-state start` da segunda é recusado até `park` (volta ao `backlog/` com motivo)
  ou `close`. `cs-state feature drop` descarta a feature e recusa se houver task ou story em andamento.
- **Tasks paralelas sem colisão.** No `start` o motor calcula a `wave`: tasks que dividem arquivo ou formam par
  `do_not_parallelize` ficam em ondas diferentes, e o despacho da segunda com a primeira em voo é recusado.

### `cs-state` — os subcomandos da árvore

Todos recusam com exit 1 e mensagem acionável (nada é escrito); os que mudam estado aceitam `--dry-run`, que
imprime JSON `{ids, criar, mover, eventos}` e **não escreve nada** (uma operação recusada também recusa no dry-run).

| Comando | O que faz |
|---|---|
| `cs-state new epico --title T --objetivo O --dry-run` | cria épico (também `new sprint --meta M`, `new feature --title T --sprint SPR-001 --aceite "<cmd>"`, `new task --tipo US ...`, `new story --tipo US --feature FEA-001 --agents a,b ...`); saída `criado <ID> em <caminho>` |
| `cs-state start <id>` | `backlog/` → `state/` (move a subárvore) ou início de task, conferindo o DoR |
| `cs-state plan <task> --sprint SPR-001` | task do backlog entra numa sprint |
| `cs-state move <id> --to <pai>` · `move <id> --avulsa` | troca o pai; sprint→feature e épico→sprint são recusados; o id antigo continua resolvendo em `find` |
| `cs-state park FEA-001 --reason R` | feature ativa volta ao `backlog/` com motivo |
| `cs-state promote <task>` | story simples → composta |
| `cs-state close <id> --summary S` | confere o DoD, arquiva; `--devolver --reason R` devolve em vez de aceitar. Não há atalho: sem `accept` o `close` é recusado |
| `cs-state reopen <id> --reason R` | `archive/` → `state/`, mesmo caminho |
| `cs-state feature drop --id FEA-001 --reason R` | descarta a feature (recusa com trabalho em andamento) |
| `cs-state find <texto>` | acha um item pelo id (inclusive o antigo) ou texto |
| `cs-state tree --json` · `cs-state board --json` | leitura compacta; JSON puro, todo item tem `id` (e `path` no `tree`) |
| `cs-state validate` · `cs-state check <id>` | integridade da árvore · DoR do item |
| `cs-state migrate state-tree` | converte o board plano legado em árvore (idempotente, com backup) |

Escrever produto sem task em andamento é bloqueado e a mensagem do guard já traz o comando
(`cs-state new task --tipo FIX --avulsa ...`).

### Carimbo de sessão de 8 blocos

`cs-session save` imprime (≤ 2.000 tokens) e grava em `state/sessoes/` um carimbo com 8 blocos fixos: 1 Fechado
nesta sessão · 2 Frente atual (`SPR-nnn › FEA-nnn`, `fechadas/total`) · 3 Tasks da frente atual · 4 Em andamento ·
5 Próximos passos · 6 Backlog imediato · 7 Decisões e pendências humanas · 8 Integridade (HEAD). Bloco sem conteúdo
diz `nenhum`; todo próximo passo traz um comando `cs-state`/`cs-session` executável. `cs-session save --check`
reprova (exit 1) passo sem comando ou bloco vazio sem `nenhum`; `cs-session load` mostra o carimbo e o que mudou
desde o save.

### As 14 skills e quem pode chamar

Em Claude Code o `emit` cria 14 skills finas (≤ 40 linhas; só chamam o `cs-state`, nunca montam caminho ou id):

| Skills | Invocação |
|---|---|
| `/board`, `/new-epic`, `/new-sprint`, `/new-feature`, `/new-task`, `/new-story` | o **modelo pode chamar sozinho**; as de criação mostram antes com `--dry-run` e checam o DoR com `cs-state check` |
| `/close-task`, `/close-feature`, `/close-sprint`, `/close-epic`, `/close-story`, `/reopen`, `/park`, `/move` | **só o humano** (`disable-model-invocation: true`): mudam o estado |

As 14 skills de estado e as 9 do mandato também saem para Cursor (`.cursor/skills/`), Copilot (`.github/skills/`) e Codex (`.agents/skills/`); no Codex a skill humana diz "Só o humano executa".

### Todas as skills geradas

Tabela gerada do código (`scripts/emit/platforms.py`): `cs.py skills-guide --write` regenera e `cs.py skills-guide --check` reprova divergência. As de sessão, `/correct`, `/plan-sprint` e `/feature-autonoma` saem só no Claude Code; as de estado e do mandato saem nas 4 plataformas.

<!-- skills:begin -->
<!-- gerado por `cs.py skills-guide --write` a partir de scripts/emit/platforms.py; não edite à mão (`cs.py skills-guide --check` reprova divergência) -->
| Skill | Para que serve | Quem roda | Argumento |
|---|---|---|---|
| `/save-session` | Salva a sessão via `.swarm/bin/cs-session save` (feito/próximo/bloqueio em 1 linha cada). | só o humano | `[--commit]` |
| `/load-session` | Retoma a sessão: injeta o briefing de `.swarm/bin/cs-session load` sem ler arquivos de estado. | só o humano | — |
| `/correct` | Registra a correção do usuário como lição do agente que errou (`.swarm/bin/cs-mem correct`). | só o humano | `<agente> <o que estava errado> -> <o certo>, porque <porquê>` |
| `/plan-sprint` | Planeja a próxima sprint com stories que passam no DoR, via `.swarm/bin/cs-state sprint plan`. | só o humano | `[--dry-run]` |
| `/feature-autonoma` | Inicia o modo autônomo de uma feature: aprovação única de spec, testes de aceite, classe e orçamento; depois `.swarm/bin/cs-state next` até o relatório. | só o humano | `<feature-id> <arquivo-spec>` |
| `/board` | Mostra o quadro de trabalho (épicos, sprints, features, stories, tasks) via `cs-state board`/`tree --json`. | o modelo pode chamar sozinho | `[--json]` |
| `/new-epic` | Cria um épico via `cs-state new epico` (mostra antes com --dry-run). Use quando o usuário pedir um épico novo. | o modelo pode chamar sozinho | `<título> -- <objetivo> [-- <métrica>]` |
| `/new-sprint` | Cria uma sprint via `cs-state new sprint` (mostra antes com --dry-run). Use quando o usuário pedir uma sprint nova. | o modelo pode chamar sozinho | `<meta> [<EPC>]` |
| `/new-feature` | Cria uma feature via `cs-state new feature` com teste de aceite (mostra antes com --dry-run; DoR por `cs-state check`). | o modelo pode chamar sozinho | `<título> <SPR\|--backlog> <comando de aceite>` |
| `/new-task` | Cria uma task US/BUG/FIX/CHORE via `cs-state new task` (mostra antes com --dry-run; DoR por `cs-state check`). Use antes de qualquer alteração de produto sem task em andamento. | o modelo pode chamar sozinho | `<US\|BUG\|FIX\|CHORE> <pai> <título>` |
| `/new-story` | Cria uma story (1 agente: task tipada; 2+: story composta) via `cs-state new story` (dry-run antes; DoR por `cs-state check`). | o modelo pode chamar sozinho | `<US\|BUG\|FIX> <FEA> <agentes> <título>` |
| `/close-task` | Fecha uma task via `cs-state close` (o motor confere o DoD e arquiva). | só o humano | `<id da task> <resumo>` |
| `/close-feature` | Fecha uma feature via `cs-state close` (o motor confere o DoD e arquiva). | só o humano | `<FEA> <resumo>` |
| `/close-sprint` | Fecha uma sprint via `cs-state close` (o motor confere o DoD e arquiva). | só o humano | `<SPR> <resumo>` |
| `/close-epic` | Fecha um épico via `cs-state close` (o motor confere o DoD e arquiva). | só o humano | `<EPC> <resumo>` |
| `/close-story` | Fecha uma story composta via `cs-state close` (só com todas as tasks fechadas). | só o humano | `<US\|BUG\|FIX id> <resumo>` |
| `/reopen` | Reabre um item fechado via `cs-state reopen` (volta ao mesmo caminho, com motivo). | só o humano | `<id> <motivo>` |
| `/park` | Estaciona uma feature ativa via `cs-state park` (sai de execução com motivo). | só o humano | `<FEA> <motivo>` |
| `/move` | Troca o pai de um item via `cs-state move` (o id antigo continua resolvendo em `find`). | só o humano | `<id> <novo pai\|--avulsa>` |
| `/auto-status` | Mostra o estado do mandato autônomo via `cs-auto status` (objetivo, estado, orçamento, aceite e próximo comando). | o modelo pode chamar sozinho | `[--brief]` |
| `/auto-plan` | Monta e submete o plano do mandato via `cs-auto plan` (o motor valida; recusa traz a guarda e o que falta). | o modelo pode chamar sozinho | `<add-node\|edit-node\|reset\|submit> ...` |
| `/auto-tick` | Pede ao motor a próxima ação do mandato via `cs-auto tick` e executa só ela (o motor decide, integra e para). | o modelo pode chamar sozinho | `[--json]` |
| `/auto-report` | Mostra o relatório do mandato via `cs-auto report` (critérios verdes, verificações com hash, devolvidos). | o modelo pode chamar sozinho | `[--json]` |
| `/auto-approve` | Humano aprova a proposta do mandato via `cs-auto approve` (mostra a proposta por `cs-auto status`). | só o humano | `[despachos=,tentativas=,replanos=,minutos=]` |
| `/auto-amend` | Humano emenda o mandato via `cs-auto amend` (volta a PROPOSED para nova aprovação). | só o humano | `<motivo> [orçamento]` |
| `/auto-resolve` | Humano resolve uma escalada do mandato via `cs-auto resolve` (escolhe uma das opções do pacote). | só o humano | `<retomar\|trocar-agente\|emendar\|descartar-ramo\|encerrar\|abortar> <decisão>` |
| `/auto-stop` | Humano manda o mandato encerrar com relatório via `cs-auto stop`. | só o humano | `<motivo>` |
| `/auto-abort` | Humano aborta o mandato via `cs-auto abort` (o relatório traz o comando para restaurar o ponto seguro). | só o humano | `<motivo>` |
<!-- skills:end -->

## Migrar para 0.7.0 (estado em árvore) e correções do upgrade

O `cs.py upgrade --apply` de um alvo anterior à 0.7.0 aplica a migração `state-tree` depois de instalar o harness
novo e antes do `emit`: o board plano vira árvore, a cadeia `events.jsonl` é preservada (só acrescenta), o
`board.json5` antigo fica em backup e cada item migrado guarda o `legacy_id`. Rodar de novo não muda nada. Duas
correções do mesmo upgrade: **alvo pausado** no meio do init (ex.: antes da instalação do pre-commit em `validate.5`)
é atualizado sem restaurar o backup e **retoma do ponto onde parou** (`cs.py stage status`); e o **backup** deixa de
copiar `.git` aninhado e `tmp/` (listados em `excluded` no `manifest.json5`; o hook `pre-commit` é guardado sob
outro nome).

## Modo autônomo (0.8.0)

O **mandato** é um contrato que você assina: um objetivo, critérios de aceite executáveis (hoje vermelhos), os
nós do plano e um orçamento. Depois de aprovado, o modelo só executa tasks; **quem decide o próximo passo, verifica,
aceita, integra e encerra é o script** (`cs-auto`).

1. `cs-auto propose --feature FEA-nnn --spec <arquivo> --objetivo "…" --nos N --criterio 'AC-1|texto|<teste>'`
   (ou `--sprint SPR-nnn`). Recusa se algum critério já está verde, se a classe é trivial ou se já há mandato aberto.
2. **Você** lê a proposta (`cs-auto status`) e aprova com `/auto-approve`: no **seu terminal** (fora do chat),
   `cs-auto senha definir` só na 1ª vez e depois `cs-auto approve --by <você>`, que pede a senha com o eco desligado
   (nunca por argumento, variável ou pipe). A aprovação grava um selo HMAC; o piloto não avança sem selo válido
   para o plano atual, e `cs-auto conferir` (seu, com a senha) recalcula as HMACs — o `tick` não pode verificá-las
   sem a senha. O orçamento (despachos, tentativas, replanos, minutos) é calculado pelo motor a partir do tamanho
   do plano; só você o muda, na aprovação ou numa emenda.
3. O modelo monta o plano com `cs-auto plan add-node … ` e `cs-auto plan submit` (o motor valida DAG, território e
   cobertura dos critérios), e então roda `cs-auto tick` em laço (`/auto-tick`): cada chamada devolve **uma** ação
   (despachar uma task, integrar uma onda, replanejar…); o modelo executa só ela e chama `tick` de novo.
4. Ao fim, `/auto-report` (`cs-auto report`): critérios verdes, verificações com hash e o que foi devolvido.

**Só do humano** (exigem `--by <humano>`; o guard bloqueia o modelo): `approve` (com a senha), `amend`, `resolve`,
`stop`, `abort` (`/auto-approve`, `/auto-amend`, `/auto-resolve`, `/auto-stop`, `/auto-abort`), além de
`senha definir` e `conferir`. Detalhes e limites: `docs/11-modo-autonomo.md`.

**Regras que você vai ver:**
- **Corte aos 80% do orçamento**: com 5 despachos, o 4º ainda termina; o 5º nunca sai. Você recebe entrega parcial,
  com o que sobrou devolvido ao backlog.
- **Ramo travado não para o resto**: uma task que precisa mexer em área congelada espera você junto das que dependem
  dela; o resto segue. O mandato só chama você (`AWAITING_HUMAN`) quando nada mais pode rodar. Você responde com
  `/auto-resolve` (`retomar`, `trocar-agente`, `emendar`, `descartar-ramo`, `encerrar` ou `abortar`).
- **Sem progresso**: se as rodadas não avançam o aceite, o mandato replaneja **uma vez**; parado de novo, encerra com
  entrega parcial. Não fica pedindo ajuda por contagem de tentativas.
- **Pausa e retomada**: `cs-auto pause` / `cs-auto resume` voltam exatamente ao estado anterior; o hook PreCompact
  pausa o mandato sozinho antes de compactar. O tempo pausado não gasta o orçamento de minutos.
- O modelo nunca roda verificar/aceitar/fechar task nem escreve o brief à mão; subagente que morre no meio é
  tratado pelo script olhando o disco (`cs-auto orphan`).

Detalhe e a máquina de 12 estados: [docs/11-modo-autonomo.md](docs/11-modo-autonomo.md).

## Depois do GO — o dia a dia

A classe da triagem (`cs-state session triage --class …`) escolhe a **faixa**; `cs-state next` diz qual é.

| Para | Use |
|---|---|
| Ver o próximo passo permitido (e a faixa) | `.swarm/bin/cs-state next` |
| **Perguntar** algo a um especialista (classe `pergunta`) | `.swarm/bin/cs-state ask <agente> "<pergunta>" [--paths "<glob>"]` → despache o Agent com a linha impressa (id `ASK-n`). Só leitura, sem task/story; fecha sozinha |
| **Mudança pequena** (classe `trivial` ou `pequena`) | `.swarm/bin/cs-state add task --quick --agent <a> --title "…" --allowed-path <arq> --verify-cmd "<cmd>"` → `cs-state session execute` → Agent. Sem épico/feature/story (story implícita `STORY-AVULSA-<sessão>`); `--goal`/`--ref`/`--out` opcionais; `pequena` exige 1 revisão de gate. Tocou 2 territórios, invariante ou área congelada → recusa "suba a classe" |
| Criar épico/feature/story/bug e tasks (classe `feature`/`risco`) | `.swarm/bin/cs-state add ...` (ou `/plan-sprint`) |
| Buscar conhecimento do time | `.swarm/bin/cs-mem search "<termo>"` |
| Corrigir um agente (vira lição dele) | `/correct` |
| Salvar / retomar a sessão de trabalho | `/save-session` · `/load-session` |
| Entregar uma feature inteira | `/feature-autonoma <id> <spec>` |
| Delegação parada (ESCALATED/ABSTAINED: `cs-state next` mostra as saídas com comando pronto) | retomar `.swarm/bin/cs-state retry --task <id> --decision "…"` · trocar de agente `cs-state reroute --task <id> --agent <a> --decision "…"` · descartar `cs-state drop --task <id> --reason "…"` |
| Verify falhou por **ambiente** (ferramenta/módulo ausente, exit 127) | `cs-state reverify --task <id>` depois de instalar; ou `cs-state waive-verify --task <id> --by <você> --reason "…" --evidence "…"` — **só humano** (o guard bloqueia agentes), review de gate obrigatória depois; nunca para teste vermelho |
| Skill atualizada | `/codebase-specialists upgrade` (plano) → `cs.py upgrade --apply` |
| Código mudou muito | `cs.py harness selftest --drift` e re-rodar as etapas dos territórios afetados |

## O que é garantido (e o que não é)

| Plataforma | Território e despacho |
|---|---|
| Claude Code | **bloqueado** por hook antes da escrita |
| Cursor, Copilot, Codex | **instrução** — o modelo pode ignorar; `cs-state verify` e o pre-commit pegam depois |

- O cartão é **mapa, não memória**: o agente acerta porque sabe onde olhar no código, não porque decorou.
- Aprovação simulada aparece como `GO (simulado)` — não é aprovação humana.

## Quando algo der errado

Anote o comando exato e o erro literal (e qualquer contorno que você precisou fazer). Isso alimenta a
`auto-correcao` para a próxima rodada de melhoria da skill.
