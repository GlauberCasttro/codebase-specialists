# 04 — Roteador de modelos (`cs-route`)

Fontes: `scripts/harness/engine/router.py`, `scripts/harness/routing.json5` (copiado para
`.swarm/harness/routing.json5`), ARCHITECTURE §8-undecies, premissa PR-21.

**Objetivo:** delegar cada task ao **modelo mais barato que resolve**, e aprender com o resultado — sem treinar
com execução que nunca aconteceu. A lição que originou o desenho (herdada de outro projeto, citada em
ARCHITECTURE §8-undecies): recomendação que não vira parâmetro do despacho treina o roteador com dados falsos.
Por isso o despacho **tem de** declarar o `model`, e só outcomes com procedência treinam.

## 1. Tiers

`routing.json5`:

| Plataforma | Tiers |
|---|---|
| `claude-code` | `haiku` < `sonnet` < `opus` |
| `cursor`, `copilot`, `codex` | `inherit` (sem seleção de modelo: a recomendação é sempre `inherit`) |

Custo relativo por tier: `0,04 / 0,2 / 1,0`. Recompensa por tier no Thompson sampling: `1,0 / 0,7 / 0,4` (empate
prefere o barato). A configuração em uso tem `platform: "claude-code"`.

## 2. Sinal de complexidade → faixa

Só do **brief estruturado** (nunca palavra-chave em prosa). Código (`router.complexity`):

```text
score = 0,45 × peso_da_classe
      + 0,12 × min(nº allowed_paths / 6, 1)
      + 0,13 × min(LOC dos allowed_paths / 600, 1)
      + 0,10 × hot_path
      + 0,10 × min(nº invariantes escopados / 4, 1)
      + 0,05 × colisão (outro agente em par do_not_parallelize)
      + ajuste_do_ato
score ∈ [0, 1]  →  faixa: baixo (< 0,35) · medio (< 0,65) · alto
```

| Classe | peso | tabela de partida (índice do tier) |
|---|---|---|
| `pergunta` | 0,0 | 0 (haiku) |
| `trivial` | 0,05 | 0 (haiku) |
| `pequena` | 0,3 | 1 (sonnet) |
| `feature` | 0,55 | 1 (sonnet) |
| `risco` | 0,9 | 2 (opus) |

Ajuste por ato (`--act`): `dev` 0,0 · `qa` −0,05 · `review` −0,05 · `arch` +0,1 · `po` 0,0.

## 3. Política

```text
                 sem amostras treináveis na faixa?
                     ┌──────────┴──────────┐
                   sim                     não
                     │                      │
          tabela de partida          Thompson: para cada tier não vetado,
          pela classe                amostra Beta(sucessos+1, falhas+1) × recompensa do tier
                     │               melhor amostra vence; 10% de exploração (seed por delegação)
                     │               veto: tier com ≥5 amostras e média < 0,35
                     └──────────┬──────────┘
                                ▼
                      regras fixas (sempre por último):
                        classe risco, flag security_gate ou nome do agente contendo "security" → topo (opus)
                        retry → sobe 1 tier por retry
                        revisor/gate → nunca abaixo do tier do autor
```

Incerteza reportada: **relativa**, `1 − (melhor − segundo) / (melhor + segundo)`.

Priors = replay do ledger `.swarm/state/model-router.jsonl` (append-only, encadeado): só eventos
`outcome` com `trains: true` e não anulados contam.

## 4. Treino só com procedência

Um outcome (ACCEPTED/REJECTED por verify + review) treina **somente** se a procedência do modelo está em
`trainable_procedencia`: `declarada-no-despacho` (o hook `pre-agent` gravou o `model` do despacho) ou `medida`
(o hook `SubagentStop` leu o modelo real da transcrição). Sem procedência → registra (`trains: false`), não
treina. Abstenção não penaliza o tier. Correção de uma linha errada: `cs-route anular --at <timestamp>
--motivo "…"` — nunca apaga linha.

## 5. Como declarar `model` no despacho

```text
.swarm/bin/cs-route recommend <task-ou-delegação> [--act dev|qa|review|arch|po]
```

Saída (formato do código):

```text
tier: <modelo> (faixa <faixa>, score <x>, incerteza <y>)
motivo: <tabela de partida | Thompson … | regras fixas aplicadas>
despache com: Agent(subagent_type='<agente>', model='<modelo>', description='<id-da-delegação>: ...')
```

No Claude Code, o despacho real precisa:

1. a delegação em **BRIEFED** (`cs-state ready --task <id>`);
2. a `description` do `Agent`/`Task` começando com o **id da delegação** daquele agente;
3. `model` **igual à recomendação** — ou um override registrado:
   `.swarm/bin/cs-route override <delegação> --model <modelo> --reason "…"`.

Sem `model`, o hook `pre-agent` **bloqueia** ("despacho sem model: passe model=… ou registre override com
motivo") — herdar o modelo da sessão é exatamente o defeito que se quer evitar. `model` diferente do
recomendado também bloqueia. No despacho de **revisão**, gate abaixo do tier do autor bloqueia ("verificador mais
fraco confirma ao acaso"). Fora do Claude Code (tiers `inherit`), não há exigência de `model`; sem hook `pre-agent`, o despacho por CLI
é `cs-state dispatch --task <id> --manual [--model <modelo>]` (grava `tool_use_id: "manual:<timestamp>"` e
`dispatch_origin: "manual"`; sem `--manual` o CLI recusa). No Claude Code o guard bloqueia qualquer `cs-state
dispatch` no Bash do principal: o despacho é a ferramenta Agent.

No emit, os agentes do Claude Code saem com `model: inherit` (o tier é decidido por despacho); exceção: gate com
piso configurado em `.swarm/routing.json5` (`floors.<agente>`, `agents.<agente>.floor` ou `gate_floor`)
— `references/platforms.md` §3.

## 6. Outros comandos

| Comando | Faz |
|---|---|
| `cs-route outcome <id> [--success] [--procedencia declarada-no-despacho\|medida]` | registra outcome manual (sem procedência treinável, não treina) |
| `cs-route anular --at <timestamp> --motivo "…"` | anula uma linha do ledger (append de `anulacao`) |
| `cs-route stats` | distribuição de recomendações, taxa de sucesso por faixa×tier, amostras, outcomes não treinados, custo estimado evitado vs. sempre-topo, priors |

## 7. Gate G14

Medido pela suíte da skill (`harness/tests/test_router_session.py -k TestRouter`): task trivial recomendada ao
tier barato; gate ≥ tier do autor; despacho sem `model` bloqueado; outcome sem procedência não altera prior;
retry sobe tier; risco no topo. Limite conhecido (`evals/README.md`): "gate ≥ tier do autor" não é exercido por
cenário de CLI, porque `cs-route recommend` não expõe o tier do autor; a regra é exercida pelo hook `pre-agent`
e pelo `cs.py harness selftest`.
