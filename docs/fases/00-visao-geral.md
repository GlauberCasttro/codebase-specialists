# Fases — visão geral

A execução da skill é dividida em **6 etapas**, cada uma com sub-etapas e um `check` mecânico por sub-etapa. A
fonte única é `references/stages.json5`; quem a lê é `cs.py stage …` (código em `scripts/stage/engine.py`).

```text
init ──▶ scan ──▶ specialize ──▶ round-table-deep-specialize ──▶ validate ──▶ approve
                                  (rt.1–rt.4 puláveis no --fast)   (validate.4 pulável no --fast)
```

| Etapa | Objetivo (`goal` em stages.json5) | Arquivo |
|---|---|---|
| `init` | alvo confirmado, plataformas escolhidas, estado de execução criado | [01-init.md](01-init.md) |
| `scan` | fatos com evidência para todas as camadas L0–L10 + lacunas respondidas | [02-scan.md](02-scan.md) |
| `specialize` | roster aprovado e um cartão por agente, escrito só a partir de fatos e em camadas S0–S5 | [03-specialize.md](03-specialize.md) |
| `round-table-deep-specialize` | cartões criticados por pares e cético, só objeções confirmadas aplicadas | [04-round-table.md](04-round-table.md) |
| `validate` | time provado por sonda, harness instalado e gates G1–G16 verdes | [05-validate.md](05-validate.md) |
| `approve` | founder decide GO/NO-GO com o relatório; estado final gravado | [06-approve.md](06-approve.md) |

## Por que etapas e não "uma conversa só"

A execução não cabe numa janela de contexto e não deve tentar caber: aderência cai com contexto inchado e ao
longo da sessão (premissa PR-11). Cada etapa começa **do disco**, não da conversa:

```text
            ┌───────────────────────────────────────────────────────────────┐
            │                       janela de contexto N                    │
            │                                                               │
 disco ───▶ │ cs.py stage load <etapa>   (pacote ≤2.000 tokens:             │
 run.json5  │   objetivo, checklist com estado, handoff anterior, pendências)│
 handoff    │          │                                                    │
            │          ▼                                                    │
            │ sub-etapas em ordem:                                          │
            │   ctx main → o orquestrador roda o comando                    │
            │   ctx sub  → subagentes (lotes ≤3, em primeiro plano)         │
            │   ctx user → toque humano, resposta literal                   │
            │   cada uma: cs.py stage check <sub>  (ou stage skip, --fast)  │
            │          │                                                    │
            │          ▼                                                    │
            │ cs.py stage done <etapa>  → roda TODOS os checks              │
            │   falhou → exit 1, diz qual, não avança                       │
            │   passou → grava .swarm/stages/<etapa>.handoff.json5    │──▶ disco
            └───────────────────────────────────────────────────────────────┘
                     │
                     ▼  devolve 3–5 linhas de handoff, recomenda /clear ou sessão nova
            janela N+1 começa SEMPRE com cs.py stage load <próxima etapa>
```

Regras do motor de etapas (`scripts/stage/engine.py`):

- `stage load <etapa>` **recusa** se a etapa anterior não fechou ("etapa '<x>' não pode começar: '<y>' não
  fechou") e retoma na sub-etapa pendente. O pacote tem limite de 2.000 tokens (`limits.handoff_max_tokens`); se
  não couber nem truncado, falha.
- `stage check <sub>` roda o `check` daquele item e marca feito/falhou em `.swarm/run.json5`. Item
  `ctx: "user"` exige `--answer "<resposta literal>"` (sem usuário: `--answer "[sem usuário] …"`). Item
  `ctx: "main"` sem check mecânico exige `--note "<feito>"`.
- `stage skip <sub> --reason "…"` só aceita sub-etapas `skippable: true` (`rt.1`–`rt.4`, `validate.4`); outra
  sub-etapa recusa listando as puláveis. O pulo fica em `run.json5` e aparece em `stage status` e no relatório.
- `stage done <etapa>` roda cada check; qualquer falha → exit 1 com o item. Sucesso grava o handoff
  (`commit`, `goal`, `notes`, `numbers`, `pending`, `produced`) e avança `run.json5`.
- Cada `check` prova o **efeito** da sub-etapa, não só que um comando rodou (iteração 3, auditoria 1.4;
  `scripts/stage/tests/test_check_audit.py` tem um cenário por check).

## Todas as sub-etapas

| id | o que faz | ctx | check | pulável |
|---|---|---|---|---|
| init.1 | confirmar que o alvo é a RAIZ de um repo git | main | `cs.py init --check-repo` | — |
| init.2 | confirmar plataformas e mostrar o que será criado (4–6 linhas) | user | (resposta literal) | — |
| init.3 | `cs.py init --platforms <as escolhidas>` | main | `cs.py init --check` | — |
| scan.1 | L0 inventário, L1 grafo, L2 arquitetura, L3 convenções | main | `cs.py facts check --layers L0,L1,L2,L3` | — |
| scan.2 | L4 configs/CI/testes, L5 git, L6 racional | main | `cs.py facts check --layers L4,L5,L6` | — |
| scan.3 | L7 comandos executados, L8 versões instaladas | main | `cs.py facts check --layers L7,L8` | — |
| scan.4 | L9 glossário/regras de negócio, L10 docs + mapas | main | `cs.py facts check --layers L9,L10` | — |
| scan.5 | conferir 5–10 fatos contra o código | sub | `cs.py facts spotcheck --min 5` | — |
| scan.6 | entrevista de lacunas | user | `cs.py interview status --no-pending` | — |
| specialize.1 | derivar roster | main | `cs.py team validate --stage derive` | — |
| specialize.2 | ajustar roster por comando e aprovar | user | `cs.py team approved` | — |
| specialize.3 | redigir cartão (1 subagente por agente) | sub | `cs.py team card-status --all-drafted` | — |
| specialize.4 | separar em camadas (core, cartão, por caminho, playbook, memória) | main | `cs.py emit budget --require-core` | — |
| rt.1 | 2 revisores adjacentes + 1 cético por cartão | sub | `cs.py panel status --all-reviewed` | sim |
| rt.2 | conferir existência de cada afirmação citada | main | `cs.py probes existence --feed` | sim |
| rt.3 | consolidar e subir regras ao core | main | `cs.py panel consolidate --check --core` | sim |
| rt.4 | autor revisa uma vez | sub | `cs.py team card-status --all-revised` | sim |
| validate.1 | emitir artefatos por plataforma | main | `cs.py emit validate` | — |
| validate.2 | gerar sondas e filtrar pelo baseline sem cartão | sub | `cs.py probes baseline-filter --check` | — |
| validate.3 | exame por agente (guiado, depois fechado) | sub | `cs.py probes check --all --examined` | — |
| validate.4 | refino do reprovado (≤2 ciclos) | sub | `cs.py probes check --all --final` | sim |
| validate.5 | instalar harness, semear memória, selftest | main | `cs.py harness selftest` | — |
| validate.6 | rodar gates | main | `cs.py verify --recorded` | — |
| approve.1 | relatório | main | `cs.py report --check` | — |
| approve.2 | decisão GO/NO-GO | user | `cs.py approve --check --recorded` | — |
| approve.3 | salvar sessão e congelar baseline | main | `cs-session save --check` | — |

## Quem faz o quê: main, sub, user

- **main** — o orquestrador (o agente principal da sessão) roda o comando da CLI.
- **sub** — subagentes. Regras de despacho, iguais para todas as sub-etapas (`references/prompts.json5` →
  `execucao`):
  - todo subagente é `general-purpose` (os agentes do time ainda não existem como `subagent_type`; o cartão de
    um agente entra no prompt como **dado**);
  - **lotes de até 3, em primeiro plano**; o próximo lote só sai quando o anterior terminou (redespachar antes
    duplicou redator e sobrescreveu rascunho na iteração 2);
  - o prompt recebe **caminhos de arquivo** (`{fatos_path}`, `{pack_dir}`, `{exam_dir}`…), nunca fatos inline;
  - o subagente grava **só o próprio arquivo** em `<alvo>/.swarm/tmp/<tipo>/<nome>.json5` e devolve uma
    linha (`gravado: <caminho>` + contagens); nunca grava nem "conserta" o arquivo de outro (iteração 3: um
    revisor regravou 5 saídas alheias);
  - o orquestrador confere o arquivo e registra pela CLI, **em série**;
  - recebeu 429 ou "limite de subagentes": não reenvie o lote inteiro; espere os que estão em voo; reduza a
    concorrência (3→2→1); registre uma linha em `.swarm/tmp/dispatch.jsonl`
    (`{quando, etapa, sub_etapa, lote, concorrencia_antes, concorrencia_depois, motivo}`); reenvie só o que falhou.
- **user** — toque humano. A resposta literal fica em `run.json5` (e, na entrevista, em
  `.swarm/interview.jsonl`).

Todo temporário mora em `<alvo>/.swarm/tmp/` — nunca no scratchpad da sessão nem em `/tmp` (execuções
paralelas colidiram lá). Caminhos passados em `--file` são absolutos.

## Arquivos de controle da execução

| Arquivo | Papel |
|---|---|
| `.swarm/run.json5` | `run_id`, alvo, commit, plataformas, etapa atual, estado de cada sub-etapa (feito/falhou/pulado), respostas de toque humano |
| `.swarm/stages/<etapa>.handoff.json5` | pacote de entrada da próxima etapa (≤2.000 tokens) |
| `.swarm/state/ledger.jsonl` | log do `cs.py` (init, merges, `allow_non_specialist`…) |
| `.swarm/tmp/` | saídas brutas de subagentes, pacotes de entrada, cópias isoladas |

## Estado e retomada

`cs.py stage status` mostra a etapa/sub-etapa atual e as pendências. `/codebase-specialists retomar` faz
`stage status` → `stage load <etapa atual>` e segue da sub-etapa pendente. Ver
[../05-sessao-e-retomada.md](../05-sessao-e-retomada.md).
