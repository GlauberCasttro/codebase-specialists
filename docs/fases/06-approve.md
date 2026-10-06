# Etapa 6 — approve

**Objetivo:** o dono decide GO/NO-GO com o relatório; pasta saneada; estado final gravado.

**Por que existe:** o `verify` mede; a decisão de colocar o time em uso é humana. Esta etapa produz o relatório
na ordem que interessa a quem decide, registra a decisão (humana ou simulada, sem ambiguidade) e congela o
baseline da sessão para detectar drift depois.

```text
 approve.1 (main)              approve.2 (user)                          approve.4 (main)                     approve.3 (main)
 ┌─────────────────────────┐   ┌─────────────────────────────────┐       ┌──────────────────────────────┐     ┌──────────────────────────────────┐
 │ cs.py report            │──▶│ cs.py approve --by <dono>       │──────▶│ cs.py sanitize   (plano)     │────▶│ .swarm/bin/cs-session save │
 │ → .swarm/report.md│   │   --decision GO|NO-GO [--note]  │       │ cs.py sanitize --apply       │     │   --did "…" --next "…"           │
 └─────────────────────────┘   │ sem usuário: … --simulated      │       └──────────────────────────────┘     └──────────────────────────────────┘
  check: report --check        └─────────────────────────────────┘        check: sanitize --check               check: cs-session save --check
                                check: approve --check --recorded
```

## Sub-etapas

### approve.1 — relatório

| | |
|---|---|
| Quem | main |
| Comando | `cs.py report` |
| Check | `cs.py report --check` — `report.md` gerado sobre o acceptance **atual** |
| Lê | `acceptance.json5`, `probes/report.json5`, `run.json5` (pulos), `facts/gaps.json5`, `team.json5` |
| Grava | `.swarm/report.md` (primeira linha: `<!-- cs-report acceptance=<sha> -->`) |

Ordem do relatório (SKILL.md): (1) modo (`--fast`\|`--full`) e GO/NO-GO em uma linha; (2) tabela agente ·
território · placar · status (modo fechado à parte, como sinal); (3) garantia por plataforma (hook × instrução,
do `verify`) e o que **não** é garantido; (4) lacunas (`gap.*`), pulos (`stage skip`) e desvios, inclusive
reduções de lote por 429; (5) como usar: `.swarm/bin/cs-state next`, `.swarm/bin/cs-mem search`,
`/correct`, `.swarm/bin/cs-session save|load`, modos assistido e autônomo.

### approve.2 — decisão (toque humano)

| | |
|---|---|
| Quem | user |
| Comandos | humano: `cs.py approve --by <dono> --decision GO` ou `cs.py approve --by <dono> --decision NO-GO --note "<motivo>"`; sem usuário: `cs.py approve --by <quem> --decision GO --simulated` |
| Check | `cs.py approve --check --recorded` — decisão GO\|NO-GO registrada sobre o acceptance atual |
| Grava | `approval` em `.swarm/acceptance.json5` (`human` ou `simulated`); `.swarm/approvals.jsonl` |

O NO-GO formal é sempre alcançável: validate não fechou, ou fechou com qualquer `nao-especialista` → registre
`cs.py approve --by <quem> --decision NO-GO --note "<motivo>"`. Aprovação simulada aparece no relatório como
`GO (simulado)` (ou `NO-GO (simulado)`) e nunca é apresentada como do dono.

### approve.4 — sanitize (antes do save final)

| | |
|---|---|
| Quem | main |
| Comandos | `cs.py sanitize` (plano: lista o que apaga, com tamanhos; **não escreve**) → `cs.py sanitize --apply` |
| Check | `cs.py sanitize --check` — `.swarm/tmp/` ausente ou vazio, `.swarm/.gitignore` com `tmp/`, `memory/index/`, `__pycache__/`, `backups/`, e nenhum `.git` aninhado fora de `tmp/` |
| Grava | apaga `.swarm/tmp/` inteiro e todo `__pycache__` sob `.swarm/`; grava `.swarm/.gitignore` (mescla: só acrescenta o que falta) e `.swarm/sanitize.json5` (registro); evento `sanitize` no ledger |

Ordem: o id é `approve.4` (sub-etapa nova), mas em `stages.json5` ela vem ANTES de `approve.3` — o save final
congela o baseline já com a pasta saneada.

Por que existe (DEC-SANITIZE, 2026-10-03): no repositório-piloto (projeto-legado) o init deixou 91 MB de lixo em
`.swarm/tmp/` — 15 cópias de exame com `.git` próprio (86 MB), pacotes de entrada, rascunhos, 4 scripts
de contorno do executor — mais `harness/__pycache__`, e nenhum `.gitignore`: um `git add .` commitaria 91 MB e 15
repositórios aninhados.

O relatório (plano e `--apply`) traz, nesta ordem: o que apaga (com tamanho por item de `tmp/` e por
`__pycache__`); o `.gitignore` a gravar; **DEFEITO** para todo script deixado em `tmp/` (contorno manual do
executor — listado ANTES de apagar e guardado em `sanitize.json5`; cópias de repositório dentro de `tmp/` não
contam); **DEFEITO** para `.git` aninhado fora de `tmp/`; aviso para arquivo alterado fora do esperado (o esperado
é `.swarm/`, os caminhos do manifesto do emit, `Makefile`, `CLAUDE.md`, `specialists.mk`,
`.claude/settings.json` e `.claude/hooks/cs-guard.sh`); o tamanho que fica; e o que entra no commit
(`git status --porcelain -uall` já com o `.gitignore` novo). `--json` dá o mesmo relatório em JSON.

Produto alterado é aviso, não falha do check: o repositório pode ter trabalho do dono não commitado (init.1 só
recomenda working tree limpo). `__pycache__` recriado depois (por um `cs-*` rodado no alvo) também é aviso: está
coberto pelo `.gitignore`.

A causa do acúmulo também foi fechada: `probes check <agente>` apaga a cópia de exame daquele agente
(`<out>/repo/`, criada por `probes exam-pack --out`) logo depois de pontuar — só o que tem o `exam.json5` do mesmo
agente, nunca o alvo.

### approve.3 — salvar a sessão e congelar o baseline

| | |
|---|---|
| Quem | main |
| Comando | `.swarm/bin/cs-session save --did "…" --next "…"` |
| Check | `cs-session save --check` (o save existe e o carimbo bate) |
| Grava | `.swarm/session/resume.json5` |

O carimbo do save (sha256 de board + último evento + HEAD + fase) é o baseline contra o qual a próxima
`cs-session load` calcula o delta. Ver [../05-sessao-e-retomada.md](../05-sessao-e-retomada.md).

### Fechamento

```text
cs.py stage done approve
```

## Exemplo real

Primeira seção do `report.md` gerado pela CLI (py-billing, `--fast`, iteração 3):

```text
Decisão: NO-GO (simulado) — gates NO-GO; decidido por eval-sim em 2026-10-03T15:58:16+00:00 (sem humano: aprovação SIMULADA, não vale como aceite do dono)

## Pulos (caminho --fast)

Modo --fast: sem mesa redonda e/ou com sondas reduzidas — time NÃO certificado como especialista.

- `rt.1` (round-table-deep-specialize): --fast pedido pelo usuário
…
## Garantia por plataforma

| plataforma | enforcement | o que garante |
|---|---|---|
| claude-code | hook | hook: bloqueia ANTES da escrita/despacho (guards cs-guard.sh); programa arbitrário só é pego depois (verify) |
| codex | instructions | instruções + estado por CLI; nada impede a escrita na hora — `cs-state verify` e o pre-commit (`cs-precommit`) detectam e reprovam DEPOIS |
```

Relatório final do executor (ts-shop, `--fast`, iteração 4, `outputs/report.md`): "**Modo `--fast` · GO
(simulado)**: todos os gates G1–G16 estão verdes e os 10 agentes são `especialista`." — com a ressalva de que o
primeiro `verify` deu NO-GO e os exames foram pontuados sobre os cartões de antes do conserto.

## Erros comuns e como resolver

| Sintoma | Origem | Resolução |
|---|---|---|
| `approve --check` recusa | acceptance velho (algo mudou depois do `verify`: team, bank, manifest do emit, índice de fatos, manifest do harness) | rode `cs.py verify` de novo, depois `cs.py report` e `cs.py approve` |
| `team approve` sem `--simulated` | defeito da iteração 3 | corrigido: `cs.py team approve --by <quem> --simulated` existe |
| `sanitize --check` falha com `tmp/ não está vazio` ou `.gitignore ausente` | `--apply` não rodou, ou algo escreveu em `tmp/` depois | `cs.py sanitize --apply` de novo (idempotente) |
| `DEFEITO (contorno manual do executor …)` no relatório | o executor deixou um script próprio em `tmp/` em vez de usar a CLI | registre o contorno como defeito da execução; o script é apagado com `tmp/` |
| GO esperado, NO-GO registrado | algum agente `nao-especialista` ou `em-refino` | regra de GO: só todos `especialista` e gates verdes dão GO |

## O que muda no `--fast`

Nada na execução. O relatório lista os pulos e diz "time NÃO certificado como especialista".
