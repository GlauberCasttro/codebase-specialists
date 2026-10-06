# 01 — Conceitos

Os conceitos abaixo aparecem em todas as etapas. Fontes: `references/ARCHITECTURE.md` (§4, §5, §8-bis,
§8-ter, §8-nonies, §9), `references/team-schema.md`, `references/probes.md`, `scripts/verify/gates.py`.

## 1. Fato com evidência

Tudo que a skill sabe sobre o repositório é um **fato**: um registro JSON5 em `.swarm/facts/<camada>.json5`,
indexado em `.swarm/facts/index.json5`. Formato (ARCHITECTURE §4):

| Campo | O que é |
|---|---|
| `id` | identificador estável, com prefixo por tipo (ex.: `brule.limit.late_fine_bp`, `gloss.money`, `ops.lint.make-lint`, `rat.adr.<arquivo>`, `hist.fix.<sha12>`, `docs.stale.<arquivo>.<linha>`, `rules.never.*`, `gap.<slug>`) |
| `layer` | camada que o produziu (`inventory`, `graph`, …, `business_rules`, `glossary`, `project_docs`, `gap`) |
| `claim` | a afirmação, em uma frase |
| `evidence` | lista **nunca vazia** de `{file, line}` ou `{cmd, exit, out_sha256}` |
| `confidence` | `high` \| `medium` \| `low` |
| `origin` | `mechanical` (um script derivou) \| `llm_interpretation` (o modelo afirmou, citando fatos mecânicos) |
| `scope` | globs que o fato toca — é por aqui que o fato chega ao agente dono do território |
| `fingerprint` | sha256 dos arquivos de evidência, para detectar drift |
| `data` | campos específicos da camada (ex.: `subject`, `value`, `test` numa regra de negócio) |

Exemplo real (fixture py-billing, iteração 4 — `.swarm/facts/business_rules.json5`):

```json5
{
 claim: "Limite LATE_FINE_BP = 200 (business) em src/billing/invoices/late_fees.py:12; coberto por tests/test_late_fees.py:15 (…)",
 confidence: "medium",
 data: {class: "business", coverage: "asserted", expr: "200", kind: "limit", source: "code",
        subject: "LATE_FINE_BP", test: "tests/test_late_fees.py:15", value: "200"},
 evidence: [{file: "src/billing/invoices/late_fees.py", line: 12}, {file: "tests/test_late_fees.py", line: 15}],
 fingerprint: "d40daaa89fab8159ab90bf86cc2c910adbe1ba6f11ca22232c5784c626391575",
 id: "brule.limit.late_fine_bp",
 layer: "business_rules",
 origin: "mechanical",
 scope: ["src/billing/invoices/late_fees.py", "tests/test_late_fees.py"]
}
```

### `llm_interpretation` — quando o modelo afirma algo

O modelo não escreve fato "solto". O que ele conclui e nenhum script derivou entra por
`cs.py facts interpret`, que exige `--supports` (ids de fatos **mecânicos** que apoiam a afirmação) e
`--evidence` (arquivo[:linha] conferido no código). É assim que se corrige um fato errado no spot-check:

```text
cs.py facts interpret --id <novo> --claim "…" --supports <ids> --evidence <arq:linha> --corrects <fato>
cs.py facts spotcheck record --fact <fato> --verdict wrong --note "…"
```

A ordem importa: a CLI recusa `--verdict wrong` sem a correção já gravada (`references/prompts.json5`,
scan.5 → `gravacao.ordem`). Regra geral (ARCHITECTURE §4): fato `llm_interpretation` precisa citar ao menos um
fato mecânico.

### `gap.<slug>` — lacuna citável

Quando o dono não sabe responder uma pergunta da entrevista, `cs.py interview record --id <q> --answer-unknown`
grava o fato `gap.<slug>` em `.swarm/facts/gaps.json5` com `data: {answer: "unknown", gap: true, question}`.
Exemplo real (py-billing, iteração 4):

```json5
{claim: "Lacuna declarada currencies: Há plano de suportar outras moedas além das de SUPPORTED_CURRENCIES? (…) — o dono não soube responder (unknown); não é conhecimento",
 id: "gap.currencies", layer: "gap", origin: "mechanical", scope: ["src/billing/shared/**"], …}
```

Uma lacuna **pode** ser citada num cartão em `lacunas` ou como motivo de cautela numa recusa ("não decida X sem
perguntar: ninguém sabe"). **Nunca** vira conhecimento: `team card set` recusa `knows` que cita só `gap.*`, o
`cs-mem` não indexa `gaps.json5` (`NOT_KNOWLEDGE = ("gaps",)` em `scripts/memory/mem.py`) e o gerador de sondas
não cria sonda a partir de lacuna (`references/probes.md` §10).

## 2. Camadas do scan (L0–L10)

`cs.py scan` roda todas as camadas (ou `--layers L0,L1,…`) e só grava se todas derem certo (exceto blobs de
evidência de comandos executados, que são endereçados por conteúdo). Arquivos reais gerados numa execução
(py-billing, iteração 4):

| Camada | Arquivo em `.swarm/facts/` | Técnica (mecânica) |
|---|---|---|
| L0 inventário | `inventory.json5` | `git ls-files`, linguagens, manifestos **e lockfiles**, LOC; marca `fixture`/`vendor`/`generated` (ignorados por todo consumidor) |
| L1 grafo | `graph.json5` | imports por linguagem → grafo de arquivos; PageRank; comunidades |
| L2 arquitetura | `architecture.json5` | camadas declaradas (import-linter, dependency-cruiser, ArchUnit, pastas…) × reais |
| L3 convenções | `conventions.json5` | contagem de padrões com proporção (lei ≥90%, maioria ≥60%, misto) |
| L4 regras | `rules.json5` | configs de lint/format/CI/pre-commit, asserts de teste, invariantes negativas (`rules.never.*`: 0 ocorrências) |
| L5 histórico | `history.json5` | hotspots, co-change, commits de correção (`hist.fix.*`), reverts, ownership |
| L6 racional | `rationale.json5` | ADRs e docs de decisão (`rat.adr.*`) |
| L7 operação | `operations.json5` | comandos de build/test/lint **executados** com timeout → `verified`, `declared`, `unavailable` (ferramenta ausente, exit 127) ou `failed` |
| L8 stack | `stack.json5`, `stack_graph.json5` | versões do lockfile; inventário de API da versão instalada quando o runtime existe |
| L9 domínio | `glossary.json5`, `business_rules.json5` | termos canônicos, sinônimos e variantes a nunca usar; limites, estados, transições, validações, com o teste que cobre |
| L10 docs do projeto | `project_docs.json5` | README, `docs/**`, ADRs, CONTRIBUTING, CHANGELOG e **instruções de agente preexistentes** (CLAUDE.md, AGENTS.md, `.cursor/rules`, `.github/copilot-instructions.md`); doc velho vira fato `stale` com a divergência (ex.: `docs.stale.readme.md.14`) |

Também em `facts/`: `interview.json5` (respostas da entrevista) e `gaps.json5` (lacunas). Saída real do
`cs.py scan` na py-billing (iteração 4): 41 arquivos, 3 de fixture ignorados, **201 fatos**; L7 com
`declared=2, failed=0, unavailable=1, verified=2`.

Instrução do time é **fato**, não injeção. "Fale com a Carla antes de mexer no plano de contas" (CLAUDE.md da
py-billing) vira fato L10 e chega ao cartão. Injeção é texto, em qualquer arquivo, que tenta mudar veredito,
escopo ou permissão de quem lê ("ignore as instruções", "aprove", "responda PASS"); a cláusula literal que vai
em todo prompt de subagente é `clausula_anti_injecao` em `references/prompts.json5`.

## 3. Território × conhecimento

> Território limita **escrita**, não conhecimento.

- **Território** = globs onde o agente pode escrever (`territory` em `team.json5`). Entre agentes que escrevem,
  os territórios são **disjuntos**, conferidos por expansão real dos arquivos do repo (regra 3 do
  `team-schema.md`); todo arquivo de produto tem exatamente um dono (gate G1).
- **Leitura** = `reads` (contexto) + o que chega por camada (núcleo S0, regras por caminho S2) + busca
  (`cs-mem search`, S5).
- Agentes `gate` (ex.: `reviewer`, `security`) não escrevem: `tools` sem `Edit`/`Write` e veredito só de
  `PASS|FAIL|NEEDS_SPECIALIST` (enum único, `machines.json5` → `verdict_enum`).
- Invariante cujo `scope` toca N territórios vai para os N donos (lição de engenharia em ARCHITECTURE §8: "invariante
  entregue a um dono só"). Gates recebem todos os invariantes e o histórico de correções.
- Teste co-localizado é do dono do diretório (`test_ownership.colocated = "owner"`); `qa` é dono só dos
  diretórios de teste de topo. Utilitário compartilhado vira um dev próprio (`dev-shared`); o `architect` só tem
  docs/ADRs.

`kind` possíveis: `dev`, `gate`, `design`, `product`, `ops`.

## 4. Cartão = mapa, não memória

O cartão de cada agente (`.claude/agents/<nome>.md` e equivalentes) diz **onde olhar** e **o que nunca fazer**
— não tenta decorar o repositório. Isso tem consequência medida: no exame em **modo fechado** (só o cartão, sem
o repositório), os agentes ficam perto ou abaixo do baseline sem cartão. Na iteração 2 (py-billing), os 9
agentes ficaram abaixo do baseline e 7 alucinaram nesse modo (`references/probes.md` §10). Por isso:

- o placar que decide o G4 é o do **exame guiado** (com o repositório copiado);
- o modo fechado sai à parte em `probes/report.json5 → closed_mode` como **sinal**: alucinação ali indica
  regra de "checar antes de afirmar" faltando no cartão.

Seções de um cartão emitido (exemplo real, `dev-ledger` da py-billing, iteração 4): missão, Território (escreve
/ lê), Fatos deste repositório, Termos do domínio, Recusas (cada uma com "porque…"), Feito quando (comando
verificado + condição), Onde está o resto (regra por caminho, playbooks, âncoras, mapas), Memória e
autocorreção. Ver o trecho em [exemplos/walkthrough-py-billing.md](exemplos/walkthrough-py-billing.md).

## 5. Camadas de carregamento S0–S5 (steering)

O conhecimento é profundo; o contexto carregado é pequeno. Nenhum conteúdo aparece em duas camadas; o emissor
mede cada camada e **falha** se estourar (`cs.py emit budget`).

| Camada | Leva | Quando entra | Claude Code | Cursor | Copilot | Codex | Orçamento |
|---|---|---|---|---|---|---|---|
| S0 núcleo | comandos verificados, invariantes globais, mapa de agentes | sempre | bloco gerenciado em `CLAUDE.md` | `.cursor/rules/cs-core.mdc` (`alwaysApply`) | bloco em `.github/copilot-instructions.md` | bloco em `AGENTS.md` raiz | ≤40 linhas |
| kernel do orquestrador | protocolo do agente principal | sempre | `.claude/orchestrator.md` (injetado pelo hook `SessionStart`) | `.cursor/rules/cs-orchestrator.mdc` | mesmo bloco do S0 | mesmo bloco do S0 | ≤80 |
| S1 cartão | missão, território, recusas, feito-quando, top termos/regras | quando o agente é invocado | `.claude/agents/<n>.md` | `.cursor/agents/<n>.md` | `.github/agents/<n>.agent.md` | `.codex/agents/<n>.toml` | ≤80 |
| S2 por caminho | termos, regras, armadilhas de um diretório | ao ler/editar arquivo do caminho | `.claude/rules/cs-<n>.md` (`paths:`) | `.cursor/rules/cs-<n>.mdc` (`globs`) | `.github/instructions/cs-<n>.instructions.md` (`applyTo`) | `<dir>/AGENTS.md` aninhado ou `.swarm/territories/<n>.json5` | ≤60 por arquivo |
| S3 por fase da task | checklist implementar/verificar/revisar + lições + top-k da memória | no `SubagentStart` (Claude Code) ou `cs-state brief` | hook injeta `additionalContext` | `cs-state brief` | `cs-state brief` | `cs-state brief` | ≤10.000 caracteres |
| S4 playbooks | receitas longas | quando o agente precisa | `.claude/skills/<n>-playbooks/SKILL.md` | `.swarm/playbooks/<n>.json5` | idem | idem | sem limite (fora do contexto até ser lido) |
| S5 memória | o resto dos fatos e tudo o que foi aprendido | por consulta | `.swarm/bin/cs-mem search` | idem | idem | idem | top-k |

Comandos emitidos para o Claude Code (como skills com `disable-model-invocation: true`): `/save-session`,
`/load-session`, `/correct`, `/feature-autonoma`, `/plan-sprint`. Orçamento: sessão ≤15 linhas,
comandos ≤25 (`scripts/emit/budget.py`). Saída real do `cs.py emit budget` (py-billing, iteração 4):

```text
CMD      máx  10 /  25 linhas (.claude/skills/feature-autonoma/SKILL.md)
ORCH     máx  60 /  80 linhas (.claude/orchestrator.md)
S0       máx  29 /  40 linhas (.cursor/rules/cs-core.mdc)
S1       máx  77 /  80 linhas (.claude/agents/reviewer.md)
S2       máx  56 /  60 linhas (.claude/rules/cs-qa.md)
orçamento por camada: ok
```

## 6. Sonda de maestria (resumo)

Detalhe em `references/probes.md` e em [fases/05-validate.md](fases/05-validate.md). O essencial:

- O banco (`.swarm/probes/bank.json5`) nasce **dos fatos, por script** — nunca de LLM. Por agente:
  **20 sondas**, 12 do território e 8 de outros territórios, ≥2 negativas no território.
- Tipos: `location`, `existence`, `command`, `prohibition`, `dependency`, `history`, `why`, `term`,
  `business_rule`.
- Negativas perguntam por coisas que **não existem**; afirmar existência = **alucinação = veto**. Citar
  evidência inexistente também conta como alucinação.
- Um **baseline sem cartão e sem repositório** responde as mesmas perguntas; sonda que o baseline acerta vira
  `discriminative: false` e sai do placar.
- Sondas `why` têm pré-check mecânico e **mérito decidido por painel de 3 juízes** (maioria).

## 7. Gates G1–G16

`cs.py verify` roda os 16 gates e grava `.swarm/acceptance.json5` com `{gates[], decision, at, commit,
enforcement, inputs, non_specialist}`. Gate que não dá para medir neste alvo sai `passed: false` com
`evidence: "não medido: …"` — nunca é omitido.

| Gate | Medida | Limiar | O que o `verify` executa |
|---|---|---|---|
| G1 cobertura | todo arquivo de produto tem 1 dono de escrita; escritores disjuntos | 100% / 0 sobreposição | `cs.py team validate --stage final` (regra 3) |
| G2 existência | todo path/símbolo/comando citado em `team.json5` existe/roda | Existence Ratio = 1,0 (e ≥1 citação) | `cs.py probes existence` |
| G3 anti-template | similaridade de cada cartão com o cartão do mesmo papel do repo de controle | ≤ 0,35 | `cs.py probes antitemplate --control <T>` (default: `evals/reference/generic-cards` da skill) |
| G4 maestria | território, cross, alucinação, delta sobre baseline — por agente | território ≥0,85; cross ≥0,70; 0 alucinação; delta > 0 | `cs.py probes check --all --final` + regra de GO (abaixo) |
| G5 operação | ≥1 comando de teste `verified` ou ausência/declaração explícita | — | leitura de `facts/operations.json5` (`unavailable` por ferramenta ausente conta como declaração explícita) |
| G6 harness | validador do estado verde; guards bloqueiam sondas negativas | 100% | `cs.py harness selftest` |
| G7 plataformas | artefatos de cada plataforma escolhida passam no validador de formato | 100% | `cs.py emit validate` |
| G8 memória | busca devolve a entrada certa para sondas TERMO/REGRA | recall@5 ≥ 0,9 e p95 < 200 ms | `cs.py probes memory-recall` |
| G9 sessão | `load` ≤2k tokens, detecta delta, round-trip idempotente | — | suíte da skill `harness/tests/test_router_session.py -k TestSession` |
| G10 delegação | transição inválida recusada; despacho sem brief ou com colisão bloqueado | — | suítes `test_machines.py -k TestM2M3`, `-k TestM1`, `test_guards.py -k TestAgentGuard` |
| G11 autonomia | loop, escalada e proibições do modo autônomo | — | suíte `test_autonomy_install.py -k TestAutonomy` (marcado **parcial**: o eval end-to-end não roda no verify) |
| G12 processo | DoR/DoD; Bug sem teste não fica READY; rollup | — | suíte `test_machines.py -k TestProcess` |
| G13 mapas | árvore com todo diretório de produto; stack × lockfile; deps × grafo; colisão | — | `emit.maps.check_maps` (parte do `emit validate`) |
| G14 roteamento | trivial → tier barato; gate ≥ autor; sem `model` bloqueia | — | suíte `test_router_session.py -k TestRouter` |
| G15 autocorreção | lição injetada; check reprova; promoção; teto | — | suíte `memory/tests/test_mem.py -k TestLessons` |
| G16 etapas | `stage load` ≤2k; `done` não avança com check falho; retomada | — | leitura de `run.json5` (init…round-table fechadas) + suíte `stage/tests/test_*.py` |

**Atenção (honestidade):** G9, G10, G11, G12, G14 e G15 são propriedades do **motor da skill** (o mesmo código
que é instalado no alvo) e são medidos pelas suítes de teste **da skill**, não por uma execução no alvo
(docstring de `scripts/verify/gates.py`). Eles dizem "o motor faz isso", não "este time fez isso".

`verify` também grava `enforcement: {<plataforma>: hook|instructions}`: `hook` só para `claude-code` quando
`.claude/settings.json` contém `cs-guard.sh` e o wrapper `.claude/hooks/cs-guard.sh` existe; todas as outras
plataformas saem `instructions`. Ver [02-harness.md](02-harness.md).

O acceptance fica **velho** se `team.json5`, `probes/bank.json5`, `emit/manifest.json5`, `facts/index.json5` ou
`harness/MANIFEST.json5` mudarem depois do verify (campo `inputs`); `cs.py verify --recorded` e o approve
recusam acceptance velho.

## 8. Regra de GO

> GO exige **todos** os agentes `especialista` **e** todos os gates verdes. Qualquer `nao-especialista` —
> aceito com `--allow-non-specialist` ou não — faz o `verify` decidir **NO-GO**, sempre, em qualquer alvo.

(ARCHITECTURE §9, premissa PR-28.) No código (`scripts/verify/gates.py → verify`): os agentes de
`probes/report.json5` com `status != "especialista"` tornam o G4 vermelho com a evidência `regra_go: …` e a
decisão é `NO-GO`. Registrar um agente como `nao-especialista` (`cs.py probes check <agente>
--allow-non-specialist --reason "…"`) serve para **fechar a etapa com honestidade**, não para chegar a GO.

Status possíveis de um agente no relatório: `especialista`, `em-refino`, `nao-especialista` (e `reprovado`
quando há decisão sem status).

## 9. Aprovação humana × simulada

| | Humana | Simulada |
|---|---|---|
| Quando | o dono leu o relatório e decidiu | não há usuário na sessão (eval, CI) |
| Roster | `cs.py team approve --by <dono>` | `cs.py team approve --by <quem> --simulated` |
| Decisão final | `cs.py approve --by <dono> --decision GO` (ou `NO-GO --note "<motivo>"`) | `cs.py approve --by <quem> --decision GO --simulated` |
| `acceptance.json5` | `approval: human` | `approval: simulated` |
| Relatório | `GO` | `GO (simulado)` — o dono ainda precisa aprovar |

Sem usuário, as respostas de toque humano são registradas com o prefixo `[sem usuário]` (ex.:
`cs.py stage check init.2 --answer "[sem usuário] …"`) e a entrevista usa `--answer-unknown`. Aprovação simulada
**nunca** é apresentada como do dono (`references/harness.md` §8).
