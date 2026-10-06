# Etapa 5 — validate

**Objetivo:** time provado por sonda, harness instalado e gates G1–G16 verdes.

**Por que existe:** especialização é **provada**, não declarada (premissa PR-08). O banco de sondas sai dos fatos
por script, um baseline sem cartão mede o que é "chutável", o examinado responde num clone isolado do alvo sem
acesso ao gabarito, e o `verify` decide GO/NO-GO pelo estado, não pela opinião de ninguém.

```text
 validate.1 (main)          validate.2 (sub)               validate.3 (sub)                       validate.4 (sub, só --full)
 ┌───────────────────┐      ┌──────────────────────┐       ┌────────────────────────────────┐     ┌──────────────────────────┐
 │ emit --dry-run    │      │ probes generate      │       │ probes exam-pack <a> --out …   │     │ reprovado: card revise   │
 │ mostra `outside`  │ ───▶ │ exam-pack <a> --out  │ ────▶ │ GUIADO (lê só <out>/repo)      │ ──▶ │ probes generate --rotate │
 │ OK do usuário     │      │ baseline SEM cartão  │       │ probes check <a> --answers …   │     │   --agent <a>            │
 │ emit              │      │ e SEM repo           │       │ juízes POR-QUÊ (3, maioria)    │     │ reexame (≤2 ciclos)      │
 │  --allow-outside  │      │ baseline-filter <a>  │       │   panel why … → probes check   │     │ sem aprovar: --allow-    │
 └───────────────────┘      └──────────────────────┘       │ FECHADO (só cartão) --closed   │     │  non-specialist → NO-GO  │
  check: emit validate       check: baseline-filter        └────────────────────────────────┘     └──────────────────────────┘
                                    --check                  check: probes check --all --examined  check: probes check --all --final
          │
          ▼
 validate.5 (main)                                     validate.6 (main)
 ┌──────────────────────────────────────────────┐      ┌───────────────────────────────────────────┐
 │ harness install --platforms … --git-hook     │ ───▶ │ cs.py verify  → G1..G16 + enforcement     │
 │   --dry-run  → mostra `outside` → OK         │      │ → .swarm/acceptance.json5 GO|NO-GO  │
 │ harness install … --allow-outside            │      └───────────────────────────────────────────┘
 │ harness selftest                             │        check: verify --recorded
 └──────────────────────────────────────────────┘
  check: harness selftest
```

## Sub-etapas

### validate.1 — emitir os artefatos por plataforma

| | |
|---|---|
| Quem | main (com toque humano para autorizar escrita fora de `.swarm/`) |
| Comandos | `cs.py emit --dry-run` → mostrar o bloco `outside` ao usuário → `cs.py emit --allow-outside` |
| Check | `cs.py emit validate` (gate G7) |
| Lê | `team.json5`, fatos |
| Grava | artefatos nativos (tabela abaixo); `.swarm/emit/manifest.json5`; backups em `.swarm/emit/backups/`; conflitos em `.swarm/emit/conflicts/`; `.swarm/knowledge/tree.json5` e `stack.json5`; `.swarm/playbooks/`, `.swarm/territories/` |

Sem `--allow-outside`, um emit que escreveria fora de `.swarm/` sai com **exit 3** e a lista (nada é escrito
fora). Exit codes do emit: 0 ok · 1 validação falhou · 2 entrada inválida/orçamento estourado · 3 conflito com
conteúdo humano ou escrita fora sem `--allow-outside`. Antes de renderizar, o emit (re)gera `deps.json5` e
`collision.json5` (`team maps`), porque o caminho rápido e os ajustes de roster os deixavam ausentes.

Garantias de escrita (`references/platforms.md` §4): idempotente (sem timestamp); arquivo inteiro gerado leva o
marcador `codebase-specialists:generated`; arquivo humano no mesmo caminho é **conflito** (nada escrito; `--force`
faz backup + diff e sobrescreve); `CLAUDE.md`, `AGENTS.md` e `copilot-instructions.md` só têm o bloco
`<!-- codebase-specialists:begin -->`…`<!-- codebase-specialists:end -->` reescrito, com backup na primeira
inserção; destino symlink ou fora da raiz é recusado.

| Plataforma | O que o emit escreve fora de `.swarm/` |
|---|---|
| Claude Code | `CLAUDE.md` (bloco), `.claude/agents/<n>.md`, `.claude/rules/cs-<n>.md`, `.claude/skills/<n>-playbooks/`, `.claude/orchestrator.md`, comandos em `.claude/skills/` |
| Cursor | `.cursor/rules/cs-*.mdc`, `.cursor/agents/<n>.md` |
| Copilot | `.github/copilot-instructions.md` (bloco), `.github/agents/<n>.agent.md`, `.github/instructions/cs-<n>.instructions.md` |
| Codex | `AGENTS.md` raiz (bloco), `<dir>/AGENTS.md` aninhado, `.codex/agents/<n>.toml` |

Trecho real do dry-run (py-billing, iteração 4): `outside: 78 escrita(s) FORA de .swarm/ (exigem
--allow-outside)`, incluindo `append-block CLAUDE.md (arquivo humano sem marcadores; bloco acrescentado ao fim
(backup))`. Depois: `validação G7: ok (100 artefatos)`.

### validate.2 — gerar sondas e filtrar pelo baseline

| | |
|---|---|
| Quem | main gera; sub responde o baseline (1 por agente, lotes ≤3) |
| Comandos (main) | `cs.py probes generate` · `cs.py probes exam-pack <agente> --out <alvo>/.swarm/tmp/exam/<agente>` · `cs.py probes baseline-filter <agente> --answers <alvo>/.swarm/tmp/answers/<agente>.baseline.json5` |
| Subagente baseline | **sem cartão e sem repositório**: lê só o arquivo de perguntas do pacote (nada de Grep/Glob/Bash); grava `{tmp}/answers/<agente>.baseline.json5` |
| Check | `cs.py probes baseline-filter --check` (todo agente com baseline e sondas classificadas) |
| Grava | `probes/bank.json5` (gabarito — **nunca** mostrado a examinados), campos `discriminative` e `baseline` no bank |

Saída real (py-billing, iteração 4):

```text
$ cs probes generate
architect              território=12 cross=8  negativas=3
dev-invoices           território=12 cross=8  negativas=3
…
gravado: .swarm/probes/bank.json5 (180 sondas) — NUNCA mostre a agentes examinados
```

Toda sonda que o baseline acerta vira `discriminative: false` e sai do placar. O gerador garante ≥6 sondas
positivas de território que o baseline não acerta; se o baseline ainda saturar, o placar usa todas as sondas e o
relatório marca `baseline_saturated` ("não medido" ≠ reprovado).

### validate.3 — exame por agente

| | |
|---|---|
| Quem | sub — 1 examinado por agente (lotes ≤3) + 3 juízes POR-QUÊ por agente |
| Pacote | `cs.py probes exam-pack <agente> --out <alvo>/.swarm/tmp/exam/<agente>` = perguntas + `repo/` (clone local do alvo **com histórico git** — `git clone --local --no-hardlinks` — e **sem** `.swarm/`) |
| Guiado | perguntas + leitura **só** dentro de `<out>/repo`; contexto = cartão emitido + núcleo S0; grava `{tmp}/answers/<agente>.guided.json5` |
| Fechado | só o arquivo de perguntas, sem ferramentas; grava `{tmp}/answers/<agente>.closed.json5` |
| Registro (main) | **guiado primeiro**: `cs.py probes check <agente> --answers <abs>/<agente>.guided.json5`; depois `cs.py probes check <agente> --closed --answers <abs>/<agente>.closed.json5` |
| Juízes POR-QUÊ | 3 juízes (modelos diferentes do examinado) por agente julgam as sondas `why` abrindo o `gabarito_fonte`; o orquestrador aplica a maioria: `cs.py panel why <agente> --probe <id> --verdict PASS` e de novo `cs.py probes check <agente>` |
| Check | `cs.py probes check --all --examined` (todo agente examinado nas sondas atuais) |
| Grava | `probes/exams/<agente>.answers.json5`, `probes/reports/<agente>.json5`, `probes/report.json5` (placar, `closed_mode`) |

Regras de resposta do examinado: formato pedido (caminho e linha, comando, sha ≥7, termo canônico, conjunto
ou `NENHUM`); `evidence` ≥1 item que **existe** (`arquivo:linha` ou comando de leitura); evidência inexistente =
alucinação; não citar arquivos gerados pela skill como evidência; abster (`NENHUM` ou `nao_sei`) é melhor que
inventar.

Pontuação (`references/probes.md` §3): placar = acertos ÷ sondas discriminativas; alucinações contam em todas;
G4 por agente = território ≥0,85, cross ≥0,70, 0 alucinação, delta > 0 sobre o baseline. Enquanto houver juiz
pendente, o resultado sai "provisório". Saída real (py-billing, iteração 4):

```text
$ cs probes check dev-invoices --answers …/.swarm/tmp/answers/dev-invoices.guided.json5
dev-invoices: território=1.0 cross=1.0 alucinações=0 delta=0.7 → G4 PASS (provisório: painel pendente)
```

O resultado do exame fica ligado ao **hash do cartão examinado** (`card_sha256` no ciclo, gravado quando chegam
respostas novas; repontuar as mesmas respostas não troca o hash). Cartão alterado depois do exame ⇒ G4 daquele
agente **PENDENTE** (reexame): `probes check --all --examined|--final` falha e o `verify` decide NO-GO.

Na mesma rodada, o primeiro `stage check validate.3` **falhou** porque os vereditos dos juízes ainda não
estavam gravados; depois de 22 `panel why … --verdict PASS` e um `probes check` por agente, passou.

### validate.4 — refino do reprovado (só `--full`)

| | |
|---|---|
| Quem | sub — 1 por agente reprovado; ≤2 ciclos |
| Entrada | `{tmp}/in/<agente>.refine-<ciclo>.json5` = cartão atual + **só** as sondas que errou, com a evidência correta |
| Saída | `{tmp}/cards/<agente>.refine-<ciclo>.json5` com `diagnostico[{probe_id, causa: onde_procurar\|alucinacao\|evidencia_inexistente\|desconhecia\|gabarito_errado, correcao, facts}]` |
| Ordem (main) | `cs.py team card revise <agente> --file <abs> --note "validate.4 ciclo N"` → `cs.py emit` → `cs.py probes generate --rotate --agent <agente>` → `cs.py probes anticola --cards .claude/agents` → novo `exam-pack`, baseline e exame **dele** → só então `cs.py probes check <agente>` |
| Check | `cs.py probes check --all --final` |

Rotacione **só** o reprovado: os outros mantêm banco e placar, e `probes check --all` não repontua quem já
passou num banco anterior. Nunca rode `probes check` antes do reexame — registraria um ciclo com respostas velhas
e esgotaria o agente. O refino corrige a **lacuna** (onde procurar, regra de checar antes de afirmar), não decora
respostas: o próximo exame usa sondas novas, e o `anticola` reprova `arquivo:linha` do gabarito, comando exato de
sonda COMANDO ou sha copiados para o cartão. Gabarito errado não se "corrige" no cartão: reporte
(`causa: gabarito_errado`).

Sem aprovar (2 ciclos no `--full`, rotação esgotada, ou validate.4 pulado no `--fast`):

```text
cs.py probes check <agente> --allow-non-specialist --reason "…"
```

ou, para todos, `cs.py probes check --all --final --allow-non-specialist --reason "…"`. O agente fica
`nao-especialista`, isso é dito ao usuário, e o `verify` decide **NO-GO** (regra de GO).

### validate.5 — instalar o harness

| | |
|---|---|
| Quem | main (com toque humano para escrita fora) |
| Comandos | `cs.py harness install --platforms claude-code,cursor,copilot,codex --git-hook --dry-run` → mostrar `outside` → `cs.py harness install --platforms claude-code,cursor,copilot,codex --git-hook --allow-outside` |
| Check | `cs.py harness selftest` (gate G6: sondas negativas contra os guards **instalados**, integridade do motor por sha256 × `MANIFEST.json5`) |
| Grava | `.swarm/harness/`, `.swarm/bin/`, `.swarm/state/`, `.swarm/memory/`; fora: `.claude/settings.json` (merge; backup em `.swarm/backups/settings/settings.json.bak-<ts>`), `.claude/hooks/cs-guard.sh`, `specialists.mk` + bloco `include specialists.mk` no `Makefile`, `.git/hooks/pre-commit` (com `--git-hook`) |

Use as **mesmas plataformas do init**: sem `--platforms`, os adapters de Cursor/Copilot/Codex não são
instalados e essas plataformas ficam só com a prosa do cartão, sem o usuário saber. `--git-hook` sempre que o alvo
é git. Opções: `--no-settings`, `--no-makefile`, `--path-env` (grava `env.PATH` com `.swarm/bin` — desligado
por padrão). Detalhes do que é instalado em [../02-harness.md](../02-harness.md).

### validate.6 — gates

| | |
|---|---|
| Quem | main |
| Comando | `cs.py verify` (`--control <T>` muda o controle do G3; `--json` para saída JSON) |
| Check | `cs.py verify --recorded` — o verify já rodou sobre o estado **atual** (GO ou NO-GO); não roda os gates de novo |
| Grava | `.swarm/acceptance.json5` |

NO-GO também **fecha** validate: a decisão (inclusive o NO-GO formal) é do dono em approve.

## Exemplo real

Fixture py-billing, `--fast`, iteração 3 (`with_skill_fast/target/.swarm/report.md`) — 9 agentes, 4
`especialista`, 5 `em-refino` (validate.4 pulado), G2 0,9803 e G4 vermelho → NO-GO:

```text
| agente | kind | território | território (sonda) | cross | alucinações | delta | status | modo fechado (sinal) |
| dev-ledger | dev | `src/billing/ledger/**` | 0.8889 | 0.8333 | 0 | 0.65 | especialista | 0.2 / 1 aluc. |
| qa | dev | `tests/**` | 0.7143 | 0.8333 | 0 | 0.5 | em-refino | 0.25 / 0 aluc. |
```

Fixture ts-shop, `--fast`, iteração 4: 10/10 `especialista`, primeiro `verify` NO-GO com G2 = 0,9723 (13
faltas em 7 cartões), conserto manual, segundo `verify` GO.

## Erros comuns e como resolver

| Sintoma | Origem | Resolução |
|---|---|---|
| G2 vermelho no `verify` (comando `rg …` em `rules.check` fora de `verified`, `npm run e2e` entre crases, caminho inexistente) | iteração 4: no `--fast` nada media existência antes do verify | corrigido na iteração 5: `cs.py probes existence` é o check de specialize.5 em **todos** os modos; cada falta volta ao autor em `.swarm/probes/existence-fix/<agente>.json5` e o autor grava o conserto com `cs.py team card revise <agente> --file <cartão> --note "conserto de existência"` — aceito **sem painel consolidado** (registrado em `existence_fixes`, não conta como revisão rt.4) e recusado se o cartão novo ainda tiver falta. Depois do conserto: `emit` de novo e **reexame** do agente (ver a linha abaixo) |
| `G4 PENDENTE (reexame)` / `status: pendente-reexame` no `probes check --all --final` ou no `verify` | iteração 4: G4 era aceito com cartão alterado depois do exame; corrigido na iteração 5 | o ciclo de exame (`probes/cycles.json5`) guarda `card_sha256`, o hash do cartão examinado; cartão mudou (`card set`, `card revise`, conserto de existência) ⇒ G4 daquele agente fica pendente e o verify dá NO-GO. Repontuar as mesmas respostas não resolve: refaça `exam-pack` + exame + `probes check <agente> --answers …` sobre o cartão atual. Ciclo antigo sem hash: pendente se algum registro do cartão em `cards/status.json5` é posterior ao exame |
| `questions.json5` manda gravar em `<out>/answers.json5`, mas o prompt manda `{tmp}/answers/<a>.guided\|closed.json5` | **defeito aberto P1** (iteração 4) | siga `references/prompts.json5` e passe o caminho explícito em `--answers` |
| não há comando para montar o pacote dos juízes nem para a maioria | **defeito aberto P1** (iteração 4: faltam `panel why pack` e `panel why tally`) | o orquestrador monta `{tmp}/in/why.<agente>.json5` lendo o bank e aplica a maioria chamando `panel why` por sonda |
| `KeyError: 'decision'` ao pontuar o guiado depois do fechado | defeito da iteração 3 | ordem documentada: **guiado antes do fechado** |
| `--allow-non-specialist só vale com --all --final` | comportamento da iteração 3 | hoje vale por agente (`probes check <a> --allow-non-specialist --reason …`) quando o agente reprovou |
| sondas de sha sem resposta (`nao_sei`) no guiado | iteração 3: o pacote excluía `.git/` | corrigido na iteração 4: o pacote é um clone local com histórico; sem git no alvo, `exam.json5` diz `history.mode: none` |
| examinado leu o gabarito com `grep` no alvo | iteração 2 | exame só no pacote do `exam-pack`; limite remanescente: com `--out` dentro de `.swarm/tmp/`, o bank é alcançável por `../../..` (só a instrução impede) — para certificação estrita, use `--out` fora do alvo |
| `harness install` sem flags deixou Cursor/Copilot/Codex sem adapter | iteração 2 | `--platforms` do init e `--git-hook`; o `verify` grava `enforcement` por plataforma |

## O que muda no `--fast`

- validate.4 é pulado: `cs.py stage skip validate.4 --reason "--fast (padrão)"`. Reprovado no exame sai
  `nao-especialista` (`--allow-non-specialist`), e o `verify` decide NO-GO.
- Todo o resto roda: emit, sondas, baseline, exame guiado + fechado, juízes POR-QUÊ, harness, verify.
- Sem a mesa redonda, a existência é conferida em specialize.5 (`cs.py probes existence`, todos os modos) e o
  conserto volta ao autor por `team card revise --file` sem painel — ver "Erros comuns".
