# codebase-specialists — documentação

Documentação para humanos da skill `codebase-specialists`. Dois leitores:

- o **dono da skill**, que precisa entender por que cada peça existe, o que cada comando faz e onde a skill
  ainda falha;
- **quem vai usá-la num repositório**, que precisa saber o que acontece, onde intervir e o que o resultado
  garante (e o que não garante).

Tudo o que está aqui foi conferido contra o código e os arquivos da própria skill (`SKILL.md`,
`MODO-DE-USO.md`, `references/`, `scripts/`, `evals/`) e contra as saídas reais das rodadas de avaliação internas (não publicadas). Quando algo vem de uma rodada específica, o texto diz de
qual (ex.: "exemplo da fixture py-billing, iteração 4").

## Índice

| Arquivo | Conteúdo |
|---|---|
| [01-conceitos.md](01-conceitos.md) | fatos com evidência, camadas L0–L10, território × conhecimento, cartão = mapa, camadas S0–S5, gates G1–G16, regra de GO, aprovação simulada |
| [fases/00-visao-geral.md](fases/00-visao-geral.md) | as 6 etapas, o ciclo `stage load → sub-etapas → stage done`, quem faz o quê |
| [fases/01-init.md](fases/01-init.md) · [02-scan](fases/02-scan.md) · [03-specialize](fases/03-specialize.md) · [04-round-table](fases/04-round-table.md) · [05-validate](fases/05-validate.md) · [06-approve](fases/06-approve.md) | uma etapa por arquivo: sub-etapas, comandos, checks, arquivos, exemplos e erros comuns |
| [02-harness.md](02-harness.md) | máquinas de estado (sessão M1, delegação M2, task M3, processo), modo autônomo, guards/hooks, enforcement por plataforma, escritas fora de `.swarm/` |
| [03-memoria-e-licoes.md](03-memoria-e-licoes.md) | `cs-mem`: busca BM25, tipos de entrada, lições por agente, teto, decaimento, promoção, `/corrigir` |
| [04-roteador-de-modelos.md](04-roteador-de-modelos.md) | `cs-route`: faixas, tiers, Thompson sampling, regras fixas, como declarar `model` no despacho |
| [05-sessao-e-retomada.md](05-sessao-e-retomada.md) | `cs-session save/load`, retomada da execução da skill (`stage load`), janelas de contexto |
| [10-arvore-de-estado.md](10-arvore-de-estado.md) | estado em árvore (backlog/state/archive), tipos e DoR, `cs-state`, carimbo de sessão, 14 skills, migração 0.7.0 |
| [06-referencia-cli.md](06-referencia-cli.md) | referência de todos os comandos, gerada do `--help` real |
| [07-evals-e-qualidade.md](07-evals-e-qualidade.md) | o oráculo (fixtures, `check_run.py`, `summarize.py`), como rodar, resultados das 4 iterações |
| [08-limites-e-defeitos-conhecidos.md](08-limites-e-defeitos-conhecidos.md) | o que não é garantido, defeitos abertos, custo medido |
| [exemplos/walkthrough-py-billing.md](exemplos/walkthrough-py-billing.md) | uma execução real, do `init` ao GO/NO-GO, com trechos reais |

## O que é

A skill monta, para um repositório-alvo, um **time de agentes especialistas** e prova que eles conhecem o
repositório. Ela:

1. **escaneia** o repositório com scripts (inventário, grafo de imports, arquitetura, convenções, regras,
   histórico git, decisões, comandos executados, versões do lockfile, glossário e regras de negócio, documentos
   do projeto) e grava **fatos com evidência** em `.swarm/facts/`;
2. **entrevista** o dono só no que o código não diz (lacunas), e registra "não sei" como lacuna citável;
3. **deriva o time**: agentes com **território de escrita** limitado (globs disjuntos) e acesso de leitura ao
   resto;
4. manda **subagentes redigirem um cartão por agente**, só a partir dos fatos;
5. **prova** o conhecimento numa **sonda de maestria** com gabarito gerado por script (nunca por LLM);
6. **emite** os artefatos nativos para Claude Code, Cursor, GitHub Copilot e Codex/AGENTS.md;
7. **instala um harness** no alvo: máquinas de estado, guards (hooks no Claude Code), memória com busca BM25,
   roteador de modelos, sessão salvável;
8. roda **16 gates** (G1–G16) e grava a decisão **GO/NO-GO**.

A premissa (em `references/premissas.json5`, PR-01): persona genérica ("você é um engenheiro sênior") não
melhora o agente; o que melhora são **fatos não deriváveis com evidência**, **regras que viram checks** e
**verificação que o agente não consegue burlar**.

## Quando usar

- Você quer agentes/subagentes que "conheçam" um repositório específico: suas regras de negócio, ADRs,
  armadilhas do histórico, comandos que realmente rodam, versões exatas da stack.
- Você quer um harness com estado, gates, guards e memória para trabalhar com esses agentes no dia a dia.
- O time vai operar por bastante tempo no repositório (o investimento inicial se paga).

## Quando não usar

- Tarefa pontual num repositório que você não vai revisitar: o custo medido é ~20–35 min e centenas de milhares
  de tokens só no orquestrador (ver [08-limites-e-defeitos-conhecidos.md](08-limites-e-defeitos-conhecidos.md)).
- Repositório que não é git (o `init` exige a raiz de um repo git: `cs.py init --check-repo`).
- Quando você precisa de garantia de bloqueio em Cursor/Copilot/Codex: nessas plataformas a garantia é
  **instrução + detecção depois** (`verify`, pre-commit), não bloqueio antes. Só o Claude Code tem hook.
- Quando você não pode deixar a skill escrever fora de `.swarm/` (ela escreve `.claude/`, `.cursor/`,
  `.github/`, `.codex/`, `AGENTS.md`, `CLAUDE.md`, `Makefile`…) — mas ela sempre mostra a lista antes e só
  escreve com `--allow-outside`.

## O fluxo inteiro em um diagrama

```text
  /codebase-specialists [--full]                       (sessão aberta NA RAIZ do repositório-alvo)
          │
          ▼
  ┌──────────────┐  alvo é raiz git? plataformas? modo --fast|--full?
  │ 1. init      │  grava .swarm/run.json5
  └──────┬───────┘
         ▼
  ┌──────────────┐  cs.py scan → facts L0..L10 (+ index)           ┌──────────────────────────┐
  │ 2. scan      │  spot-check de 5–10 fatos por subagente  ─────▶ │ entrevista de lacunas    │
  └──────┬───────┘  (fato errado → correção llm_interpretation)    │ (usuário; "não sei" →    │
         │                                                         │  fato gap.<slug>)        │
         ▼                                                         └──────────────────────────┘
  ┌──────────────┐  team derive → roster → ajuste por CLI → aprovação (usuário)
  │ 3. specialize│  1 subagente redator por agente → cartão a partir de fatos
  └──────┬───────┘  core S0 ≤40 linhas; emit budget mede as camadas
         ▼
  ┌──────────────┐  SÓ no --full: 2 revisores adjacentes + 1 cético por cartão,
  │ 4. round-    │  checagem mecânica de existência, consolidação, revisão única do autor
  │    table     │  no --fast: rt.1–rt.4 pulados com `stage skip` (registrado)
  └──────┬───────┘
         ▼
  ┌──────────────┐  emit (dry-run → OK do usuário → --allow-outside)
  │ 5. validate  │  sondas por script → baseline sem cartão → exame guiado (+ fechado, só sinal)
  │              │  [--full: refino ≤2 ciclos]  → harness install → selftest → verify G1–G16
  └──────┬───────┘
         ▼
  ┌──────────────┐  report.md → decisão GO|NO-GO (humana ou --simulated)
  │ 6. approve   │  cs-session save congela o baseline
  └──────────────┘
         │
         ▼
  dia a dia: .swarm/bin/cs-state next · cs-mem search · /corrigir · cs-session save|load
```

Cada etapa roda numa **janela de contexto própria**: começa com `cs.py stage load <etapa>` (pacote ≤2.000
tokens montado do disco) e termina com `cs.py stage done <etapa>`, que roda os checks e grava o handoff.
Detalhe em [fases/00-visao-geral.md](fases/00-visao-geral.md).

## Modos: `--fast` (padrão) e `--full`

| | `--fast` (padrão) | `--full` (só a pedido explícito) |
|---|---|---|
| Quando | sempre que o usuário não pedir rigor | o usuário pede "completo", "certificado", "com mesa redonda" ou `--full` |
| Mesa redonda (rt.1–rt.4) | pulada com `cs.py stage skip <id> --reason "--fast (padrão)"` | roda |
| Refino do reprovado (validate.4) | pulado; reprovado sai `nao-especialista` | até 2 ciclos com sondas novas |
| Exame, spot-check, entrevista, roster, emit, harness, verify | rodam | rodam |
| Tempo (MODO-DE-USO.md) | ~20–30 min num repo pequeno/médio | ~2× |
| Relatório | diz o modo e lista os pulos | diz o modo |

As sub-etapas puláveis são exatamente as marcadas `skippable: true` em `references/stages.json5`:
`rt.1`, `rt.2`, `rt.3`, `rt.4` e `validate.4`. Qualquer outra recusa o `stage skip`. O orquestrador **nunca**
escolhe `--full` sozinho (SKILL.md).

Por que `--fast` é o padrão: nas rodadas de avaliação, a qualidade medida do time foi a mesma com e sem mesa
redonda (iteração 3, py-billing: 13/13 [Q] nos dois modos); mesa redonda e refino mudam a **certificação**
(G2/G4), não a qualidade (premissa PR-26).

## Comandos da skill

| Comando | Faz |
|---|---|
| `/codebase-specialists` | roda no modo padrão (`--fast`) no repositório atual, desde `init` |
| `/codebase-specialists --full` | roda certificado (mesa redonda + refino) |
| `/codebase-specialists status` | só `cs.py stage status` + `cs.py team card-status`; resume em 5 linhas; não altera nada |
| `/codebase-specialists retomar` | `stage status` → `stage load <etapa atual>` e segue dali, sem refazer o que fechou |
| `/codebase-specialists uso` | mostra o `MODO-DE-USO.md` resumido e para |

A skill também dispara por linguagem natural ("monta o time de agentes pra esse repo", "cria os agentes
especialistas"…), conforme a `description` do `SKILL.md`.

### Convenções usadas nesta documentação

- `cs.py` abrevia `python3 ~/.claude/skills/codebase-specialists/scripts/cs.py`. Passe `--target <repo>` se
  você não estiver na raiz do alvo (a raiz é `--target`, senão `$CLAUDE_PROJECT_DIR`, senão o diretório atual;
  nunca o diretório da skill).
- Em zsh, **não** guarde o comando numa variável (`C="python3 …"; $C stage status` não divide palavras). Use uma
  função: `cs() { python3 ~/.claude/skills/codebase-specialists/scripts/cs.py "$@"; }`.
- **Glob sempre entre aspas**: `cs.py team roster move "src/billing/**" --to dev-billing`. Sem aspas o zsh
  expande ou falha com "no matches found".
- No alvo, o harness é chamado pelo caminho: `.swarm/bin/cs-state`, `.swarm/bin/cs-mem`,
  `.swarm/bin/cs-session`, `.swarm/bin/cs-route` (o `env.PATH` no `settings.json` vem desligado por
  padrão; ver [02-harness.md](02-harness.md)).

## Onde intervir (os toques humanos)

1. **Plataformas e modo** (init.2) — default: as 4 plataformas e `--fast`.
2. **Entrevista de lacunas** (scan.6) — responda de verdade; cada "não sei" vira `gap.*` e o agente pergunta em
   vez de supor.
3. **Roster** (specialize.2) — nomes, territórios e porquê; ajuste pela CLI antes de aprovar.
4. **Escritas fora de `.swarm/`** (validate.1 e validate.5) — a skill mostra o bloco `outside` antes.
5. **Decisão final** (approve.2) — GO só com todos os agentes `especialista` e os 16 gates verdes.
