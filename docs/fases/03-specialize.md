# Etapa 3 — specialize

**Objetivo:** roster aprovado e um cartão por agente, escrito só a partir de fatos e em camadas S0–S5.

**Por que existe:** é aqui que o conhecimento vira agente. Duas decisões são humanas (quem existe e onde cada
um escreve) e duas são mecânicas (cada cartão cita fatos; cada camada cabe no orçamento). O redator de cada
cartão trabalha isolado, sem ver os outros cartões — independência antes da mesa redonda.

```text
 specialize.1 (main)        specialize.2 (user)                    specialize.3 (sub, 1 por agente)       specialize.4 (main)
 ┌────────────────┐         ┌───────────────────────────────┐      ┌────────────────────────────────┐     ┌──────────────────────┐
 │ cs.py team     │ ──────▶ │ revisar com julgamento        │ ───▶ │ cs.py team facts <a> --out …   │ ──▶ │ core S0 ≤40 linhas   │
 │ derive         │         │ ajustar SÓ pela CLI:          │      │ redator grava                  │     │ team core from-panel │
 │ → team.json5   │         │  team roster move|rename|add| │      │ {tmp}/cards/<a>.draft.json5    │     │ ou team core set     │
 └────────────────┘         │  remove|set (invalida aprov.) │      │ main: team card set <a> --file │     │ cs.py emit budget    │
  check: team validate      │ team approve --by <quem>      │      └────────────────────────────────┘     └──────────────────────┘
         --stage derive     └───────────────────────────────┘        check: team card-status              check: emit budget
                              check: team approved                          --all-drafted                    --require-core
```

## Sub-etapas

### specialize.1 — derivar o roster

| | |
|---|---|
| Quem | main |
| Comando | `cs.py team derive` (`--force` sobrescreve um `team.json5` que já tem cartões) |
| Check | `cs.py team validate --stage derive` |
| Lê | fatos (inventário, grafo, comunidades, histórico) |
| Grava | `.swarm/team.json5`, `.swarm/team-derivation.json5`, `.swarm/team-validation.json5` |

O derive propõe bounded contexts pelo grafo + papéis transversais. Saída real (py-billing, iteração 4):

```text
$ cs team derive
dev-invoices           dev      scripts/**, src/billing/*, src/billing/invoices/**
dev-ledger             dev      src/billing/ledger/**
dev-payments           dev      src/billing/payments/**
dev-shared             dev      src/billing/shared/**
reviewer               gate     (sem escrita)
security               gate     (sem escrita)
qa                     dev      tests/**
architect              design   .gitignore, Makefile, README.md, docs/**, pyproject.toml, ruff.toml, uv.lock
po                     product  (sem escrita)
gravado: .swarm/team.json5 e .swarm/team-derivation.json5
```

`team validate` aplica as 8 regras de `references/team-schema.md` (nome válido e único; `kind` válido; gate sem
Edit/Write; territórios disjuntos por expansão real; fatos existentes; existência; anti-cola; invariante em N
donos).

### specialize.2 — ajustar e aprovar o roster (toque humano)

| | |
|---|---|
| Quem | user (o orquestrador mostra nomes, territórios e porquê; ajusta pela CLI) |
| Comandos de ajuste | `cs.py team roster move "<glob>" --to <agente>` · `cs.py team roster rename <de> <para>` · `cs.py team roster add <agente> --kind dev --territory "<glob>" [--reads "<glob>"]` · `cs.py team roster remove <agente> --to <herdeiro>` · `cs.py team roster set --file <abs>` |
| Aprovação | `cs.py team approve --by <quem>` (sem usuário: `cs.py team approve --by <quem> --simulated`) |
| Check | `cs.py team approved` — aprovação gravada **e** roster inalterado desde então |
| Grava | `team.json5`; `.swarm/team-approvals.jsonl` (com sha do roster) |

Cada comando de roster **revalida** (regras 1–4 e 8; inválido = nada gravado), recalcula `invariants` e
`facts_used` e **invalida a aprovação**. `roster set --file` recebe `{agents:[{name, kind, territory, reads,
tools?, model?}]}`.

Critérios de julgamento (SKILL.md): núcleo de domínio **não** é do architect; kernel compartilhado vai para um
dev (os outros o têm em `reads`); o nome diz o território; 3–8 devs; territórios por glob; dono explícito para
teste co-localizado. Exemplos (categoria `example`) ficam fora da cobertura obrigatória, mas podem ter dono:
`cs.py team roster add dev-exemplos --kind dev --territory "examples/**"`.

Ajuste real (py-billing, iteração 4) — o checker de dinheiro da ADR 0001 e o pacote raiz foram para o núcleo
compartilhado:

```text
$ cs team roster move scripts/** --to dev-shared
1 arquivo(s) de scripts/** → dev-shared
  …
revalidado (regras 1–4, 8); aprovação INVALIDADA → `cs.py team approve --by <nome>`
$ cs team approve --by eval-sim --simulated
roster aprovado (simulado) por eval-sim (9 agentes; sha f37ec497f74a) → .swarm/team-approvals.jsonl
```

(No log o glob saiu sem aspas porque o executor usou uma função que já citava os argumentos; digitando no zsh,
use `"scripts/**"`.)

### specialize.3 — redigir os cartões (1 subagente por agente)

| | |
|---|---|
| Quem | sub — 1 redator por agente, lotes ≤3, só leitura, sem ver os outros cartões |
| Antes (main) | `cs.py team facts <agente> --out <alvo>/.swarm/tmp/in/<agente>.facts.json5` e `{tmp}/in/core.json5` (linhas do core já gravadas; vazio na primeira rodada) |
| Saída do subagente | `{tmp}/cards/<agente>.draft.json5` = `{agent, card, camadas, facts_used, lacunas, injection_attempts}` |
| Registro (main) | `cs.py team card set <agente> --file <alvo>/.swarm/tmp/cards/<agente>.draft.json5` |
| Check | `cs.py team card-status --all-drafted` |
| Grava | `card` e `camadas` em `team.json5`; identidade do rascunho em `.swarm/cards/status.json5` |

`team facts <agente>` calcula o pacote **na leitura**: fatos do território + `reads` + citados + lacunas do
escopo, mais, para todo agente, instrução do time (`docs.instr.*`), decisões de ADR (`rat.adr.*`) e fatos de
escopo `**`; para gate/design/product/ops e `qa`, todos os comandos (`ops.*`) e todo o rationale; para gate,
todos os `rules.never.*`.

Regras de redação (prompt `references/prompts.json5 → prompts["specialize.3"]`, resumo):

1. Só a partir dos fatos: toda entrada de `knows`, `refuses`, `rules`, `footguns` cita `facts: [ids]`.
2. Sem adjetivos de persona ("sênior", "especialista"…); `mission` = o ofício neste repo em 1–2 frases.
3. `description` ≤300 caracteres, gatilho de delegação orientado a ação.
4. Toda recusa traz `why` (ADR, invariante, entrevista, instrução do time ou incidente).
5. `done_when` verificável: comando `verified` + condição observável; comando não verificado vai em
   `rules[].check` com `unverified: true`, nunca entre crases em `done_when`/`playbooks`.
6. `footguns` vêm do histórico (correções, reverts, co-change).
7. Separar por camada desde já: `camadas.s0_core` (≤3 linhas candidatas ao core), `camadas.s2_por_caminho`,
   `card.playbooks` (S4), `camadas.s5_memoria`.
8. Nunca copiar resposta de sonda (evitar `arquivo:linha` no texto); `gap.*` só em `lacunas`/cautela.
9. Globs em comandos sempre entre aspas; caminhos a partir da raiz.

`team card set` aceita a saída inteira do subagente ou só o `card`; registra sha256 do arquivo, `draft.id` e
`draft.at`, e **recusa rascunho mais velho que o registrado** (redator atrasado/duplicado), salvo `--force`.
Cartão que não cita nenhum fato não conta como redigido.

### specialize.4 — separar em camadas e medir o orçamento

| | |
|---|---|
| Quem | main |
| Comandos | `cs.py team core from-panel` (sem painel consolidado = caminho rápido só com os `s0_core` dos cartões) **ou** `cs.py team core set --file <abs>` (`{lines:[{text, facts}]}`, ≤40); depois `cs.py emit budget` |
| Check | `cs.py emit budget --require-core` (falha se `core.lines` vazio ou alguma camada estoura) |
| Grava | `core.lines` em `team.json5`; `.swarm/panel/core-promotion.json5` (`promoted[]`, `refused[{text, why}]`) |

O core recusa, linha a linha, referência inexistente (classificador `scripts/cslib/refs.py`), deduplica (texto
igual, Jaccard ≥0,6, fatos contidos ou fato em comum com ≥30% das palavras) e respeita o espaço do S0.
`emit budget` não escreve nada: renderiza em memória e mede S0 ≤40, S1 ≤80, S2 ≤60, kernel ≤80, sessão ≤15,
comandos ≤25.

Saída real (py-billing, iteração 4):

```text
$ cs team core from-panel
core.lines gravado: 9 linha(s) (sem painel consolidado: só s0_core dos cartões)
registro: .swarm/panel/core-promotion.json5
```

### Fechamento

```text
cs.py stage done specialize
```

## Erros comuns e como resolver

| Sintoma | Origem | Resolução |
|---|---|---|
| `cs.py team: error: argument team_cmd: invalid choice: 'show'` | não existe `team show` (log da iteração 4) | para ver o roster: a saída de `team derive`/`team roster …`, `cs.py team validate` ou `cs.py team card-status` |
| `{tmp}/in/core.json5` sem comando que o gere | defeito aberto (iteração 4, P1: falta `team core pack`) | o orquestrador grava `{lines: []}` (ou as linhas atuais) à mão; o registro do core continua pela CLI |
| pacote de fatos do gate só com `gap.*` (cartão de security com 0 knows) | defeito da iteração 3 | corrigido na iteração 4 (`team facts` inclui `rules.never.*`, ADRs, `ops.*` para gates); se ainda acontecer, reporte |
| `core from-panel` juntou 3 versões da mesma regra | defeito da iteração 3 | dedup atual (Jaccard ≥0,6 etc.); confira `panel/core-promotion.json5` |
| rascunho sobrescrito por redator duplicado | redespacho antes do lote terminar | não redespache; `team card set` recusa o rascunho mais velho |
| `roster add` não herdou `reads` | observado na iteração 4 (ts-shop) | ajuste `reads` com `team roster set --file` |
| glob expandido pelo zsh em `roster move` | glob sem aspas | `"src/billing/**"` |

## O que muda no `--fast`

Nada nesta etapa. A diferença é **depois**: sem mesa redonda, o core vem só dos `s0_core` dos cartões, e
nenhuma checagem de existência roda antes do `verify` — causa do defeito P0 descrito em
[05-validate.md](05-validate.md) e [../08-limites-e-defeitos-conhecidos.md](../08-limites-e-defeitos-conhecidos.md).
