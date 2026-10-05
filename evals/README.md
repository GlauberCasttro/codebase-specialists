# evals — codebase-specialists

Avaliação de **desempenho e proficiência** da skill em codebases variados, no formato do
skill-creator (`evals.json` → execução → `grading.json` → benchmark com/sem skill).

```
evals/
├── evals.json                 12 prompts (PT/EN, vagos e detalhados) — formato skill-creator
├── check_run.py               grader MECÂNICO → grading.json (expectations: text/passed/evidence; [Q] qualidade · [S] estrutura)
├── summarize.py               agrega [Q] e [S] SEPARADOS por config (mean±sd, tempo, tokens) → benchmark-q.md/.json
├── tests/                     testes do próprio grader (python3 -m unittest discover -s evals/tests)
├── harness_scenarios.json     contrato com a CLI do harness (cenários G8–G16 rodados numa cópia do alvo; nomes de harness.md §3)
├── reference/generic-cards/   8 cartões genéricos de template (controle do anti-template G3)
└── fixtures/
    ├── build.sh               build.sh <nome> <destino> → repo git com histórico realista (bash 3.2)
    ├── install_feature.sh     prepara eval autônomo/escalada/bug (testes de aceite vermelhos + tag)
    ├── py-billing/            repo/ + history.plan + history/ + GROUND_TRUTH.json
    ├── ts-shop/               idem
    ├── go-polyglot/           idem
    └── py-billing-features/   refund-percent/ · accept-float-amounts/ · bug-late-fee/ (oráculo oculto)
```

## As fixtures

Só `repo/` é copiado para o alvo. `GROUND_TRUTH.json`, `history.plan`, `history/` e o oráculo oculto
do bug **nunca** chegam ao alvo. O `build.sh` reconstrói o histórico commit a commit (ops `put`,
`variant`, `sed`, `commit`, `revert`, `tag`) e **aborta** se o histórico não terminar exatamente em `repo/`.

| Fixture | Stack | Sinais plantados |
|---|---|---|
| `py-billing` | Python ≥3.9, uv.lock, unittest, ruff, Makefile | 3 subdomínios + shared; ADRs 0001–0003 (centavos inteiros, ledger append-only, captura idempotente); 21 commits, 5 `fix:`, revert de `delete` no ledger, co-change payments↔ledger, bump httpx 0.26→0.27; **bug plantado** em `late_fees.py` (juros truncados por dia); README desatualizado (httpx 0.26.0); CLAUDE.md humano; `tests/fixtures/` com .csproj e package.json falsos |
| `ts-shop` | npm workspaces, node:test com type stripping (Node ≥22.18), eslint 9, TS 5.5.4 | shared/api/web; ADRs (web só por HTTP; estoque nunca negativo, reserva 15 min); fix do enum que quebrou o boot; revert do import web→api; ranges no package.json × versões exatas no lock (vite 5.4.0→5.4.2); README cita `npm run e2e` inexistente; AGENTS.md humano; fixture legacy-erp com Django/Spring |
| `go-polyglot` | Go 1.22.5 (go.mod/go.sum), bash de deploy, Dockerfile, migrações SQL | enum `delivery_status` espelhado em Go; co-change migrations↔storage; revert de edição de migração aplicada; README diz Go 1.21; `testdata/` e `examples/python-client` (fixture); **`go` ausente na máquina ⇒ teste tem de ser `declared`** |

`python3 evals/check_run.py --verify-ground-truth all` confere que todo `arquivo:linha` do
GROUND_TRUTH ainda casa o texto esperado (rode após editar uma fixture).

## Como rodar

```bash
SK=~/.claude/skills/codebase-specialists
T=$(mktemp -d)/py-billing
bash $SK/evals/fixtures/build.sh py-billing "$T"          # 1. alvo com histórico
#   2. execute o prompt do eval NO alvo — COM a skill (with_skill) ou SEM (without_skill / baseline)
python3 $SK/evals/check_run.py "$T" $SK/evals/fixtures/py-billing/GROUND_TRUTH.json \
        --mode setup --out grading.json                    # 3. grading mecânico
```

- **Plataformas restritas** (evals 2 e 8): passe `--platforms claude-code,cursor` — G7 também reprova
  plataforma emitida sem pedido.
- **Modo autônomo / escalada / bug** (evals 4–6): depois do eval 1 no mesmo alvo,
  `bash fixtures/install_feature.sh refund-percent|accept-float-amounts|bug-late-fee "$T"`, rode o prompt e
  gradeie com `--mode autonomous --feature refund-percent`, `--mode escalation --feature accept-float-amounts`
  ou `--mode bugfix`.
- **Modo** (iteração 4): o prompt do eval sem pedido de rigor roda o padrão `--fast` (sem mesa redonda e sem
  refino; pulos registrados por `stage skip`). Para medir a execução certificada completa, acrescente "--full" ao
  prompt e use a config `with_skill_full`. O [Q] é comparável entre os dois; o [S] de G4/G2 muda com o modo.
- **Corretor sem falso negativo de negação**: [Q][TERM] ignora variante citada como legado/alias, ao lado do
  canônico ou dentro de id/slug/caminho (`gap.driver-id-compat`); [Q][FIX] ignora id de fato e caminho entre
  crases (`gap.python-client-owner`); [Q][STACK]/G13 nunca leem `@types/x` como `x` (`tests/test_check_run_iter4.py`).
- `--only G1,G3,BC` restringe; `--no-scenarios` pula os cenários (rápido); `--skill DIR` aponta outra versão.
- **Baseline**: mesmo prompt, mesma fixture, sem a skill (ou com a versão anterior, via `--skill`). Monte
  `benchmark.json` com `configuration: with_skill|without_skill` usando o `aggregate_benchmark.py` do
  skill-creator; as asserções `[T]` (transcrição) vão para o grader LLM, as demais saem do `check_run.py`.
- **Q × S separados**: o pass rate do `aggregate_benchmark.py` mistura [Q] e [S] — e a baseline não tem os
  artefatos [S], então o total engana. Rode `python3 evals/summarize.py <iteração>/runs` (estrutura
  `runs/eval-N/<config>/run-K/{grading.json,timing.json}`): grava `benchmark-q.md` e `benchmark-q.json` no
  diretório da iteração com [Q] e [S] por config (mean ± sd), tempo e tokens do `timing.json` e as falhas [Q] por
  run. A comparação com a baseline é a linha [Q].
- Override de CLI sem editar código: `CS_STATE_CMD`, `CS_SESSION_CMD`, `CS_MEM_CMD`, `CS_ROUTE_CMD`, `CS_STAGE_CMD`,
  `CS_VALIDATE_CMD`, `CS_SELFTEST_CMD` (use `{T}` e `{SKILL}`); ou ajuste `harness_scenarios.json`.

Artefatos JSON5 são lidos **só** por `scripts/cslib/json5io.py` da skill; se ele faltar, o grader diz
isso na evidência de cada asserção afetada (não cai em parser próprio).

## Qualidade [Q] × estrutura [S]

Cada asserção do modo `setup` tem prefixo `[Q]` ou `[S]` no `text`, e `summary` traz
`quality: {passed, total}` e `structure: {passed, total}` além do total.

- **[Q] qualidade — neutra de formato.** Mede o time como ele aparece nos artefatos, venha de onde vier:
  `.claude/agents/*.md`, `.cursor/agents|rules/*`, `.github/agents|prompts|instructions/*`,
  `.github/copilot-instructions.md`, `AGENTS.md`/`CLAUDE.md` da raiz e aninhados e, se existir, `.swarm/`
  (cartões e core do `team.json5`, `facts/history`, `facts|knowledge/stack`). Agente = arquivo de agente de
  qualquer plataforma (mesmo nome em plataformas diferentes é o mesmo agente; prefixo `cs-` ignorado); território
  = `team.json5` › `globs`/`applyTo`/`paths` › seção "Território" do cartão; gate = `kind: gate` ou nome de
  revisor/segurança sem ferramenta de escrita. O que um agente "sabe" = o próprio texto + o núcleo sempre
  carregado (CLAUDE.md/AGENTS.md raiz, copilot-instructions, regra `alwaysApply`, core) + regras por caminho que
  tocam o território (gate: todas). Em arquivo que já existia na fixture conta só o texto **adicionado** — nota
  humana preexistente não dá ponto a ninguém. É a família que se compara com a baseline.
  Asserções: TERR (territórios disjuntos; cobertura ≥90%), BC, INV, TERM, RULE, STACK, FIX, NEG, HIST, HUMAN,
  TESTCMD (comando de teste real citado), STALE (README velho não repetido como verdade).
- **[S] estrutura — artefatos próprios da skill.** G1–G16 e FMT (`team.json5`, fatos, sondas, harness,
  cenários). Reportada à parte; não compare com a baseline por ela.

## O que cada asserção mede e por que discrimina

Regra para [S]: uma asserção que passa sem a skill não mede a skill. Para [Q] é o contrário — ela tem de poder
passar sem a skill, senão não é comparável com a baseline. Rodado sobre a fixture recém-construída (sem
skill), o `check_run.py` dá **0/13 [Q]** e **0/15 [S]** (py-billing, conferido em 2026-10-02 com `--no-scenarios`; os cenários
só acrescentam [S]). As asserções de
"não estragar" (conteúdo humano preservado, sem `.md` extra, arquivos protegidos intactos, regressão
verde) só contam quando a skill rodou (`team.json5` existe) ou quando houve entrega — senão seriam grátis.

| Id | Mede | Por que a baseline falha / o que um atalho não consegue |
|---|---|---|
| G1 cobertura | cada arquivo de produto (lista do `repo/` da fixture, sem fixture/reservados) com exatamente 1 dono; nenhum agente só de fixture | prompt genérico gera "backend/frontend/qa" sem território, ou `src/**` sobreposto |
| G2 existência | todo caminho citado em team/cartões existe (≥5 citados); todo comando de check está em operations | cartão genérico não cita caminho real; cartão inventado cita arquivo que não existe |
| G3 anti-template | cosseno (uni+bigramas, sem stopwords) com 8 cartões genéricos ≤ 0,35; orçamento de camadas | calibração: cartões genéricos entre si 0,09–0,20; paráfrase de template "senior engineer" no billing = 0,50; cartões factuais ≈ 0,05 |
| G4 sonda | placar por agente (território ≥0,85, cross ≥0,70, 0 alucinação, delta>0) + anti-cola banco×cartões | sem sonda não há report; cola de gabarito no cartão é pega por substring |
| G5 operação | comando real de teste com status certo; `verified` é **reexecutado pelo grader** | `go test` marcado verified sem `go` falha; lint ruff/eslint sem ferramenta tem de ser declared |
| G6 harness | validate --strict e selftest com o código da skill | sem harness instalado a ferramenta não existe |
| G7 plataformas | frontmatter (name/description), settings.json com PreToolUse, AGENTS.md cita cada agente; nada além do pedido | baseline costuma escrever só CLAUDE.md ou emitir tudo |
| G8 memória | recall@5 ≥0,9 de termos e regras do GROUND_TRUTH no `cs-mem search` (evidência = arquivo da definição), p95 <200 ms; lição após REJECT; episódio por evento (termos/regras nos cartões: [Q] TERM/RULE) | sem glossário/regras mecânicos a busca não devolve o arquivo certo |
| [Q] TERR | territórios de escrita (globs) disjuntos; ≥90% dos arquivos de produto com dono | time sem território ou com `src/**` sobreposto |
| [Q] INV | cada invariante de ADR no que **todo** dono do escopo e todo gate lê | invariante entregue a um dono só (lição medida) reprova |
| [Q] BC | precisão/recall (≥2/3) dos bounded contexts: o contexto com maioria do código de produção do escritor, coberto ≥80% (testes co-localizados fora da conta) | agente-mega `src/**` não "recupera" nenhum contexto |
| [Q] TERM / RULE | termo canônico no conhecimento dos donos (≥80%, sem variante proibida); regra de negócio no dono e no gate (≥80%) | variantes legadas (`JournalEntry`, `get_bill`, `holdStock`, `driver`) usadas como termo reprovam |
| [Q] STACK | versões exatas do lockfile citadas (texto ou `.swarm` stack); nenhuma versão histórica/range afirmada como atual | `^4.19.0`, `vite 5.4.0`, `httpx 0.26.0`, `pgx v5.5.5` são armadilhas plantadas |
| [Q] FIX | stack da fixture não afirmada como produto (linha que descreve a própria fixture, nega ou a RECUSA — "só como dado de teste", "test data", "não é produto" — não conta); nenhum agente só de fixture | .NET/Jest (py-billing), Django/Spring (ts-shop), requests/pydantic (go) |
| [Q] NEG | padrões ausentes (pytest, SQLAlchemy, Jest, Redux, GORM, Kubernetes…) não afirmados (linhas com negação são ignoradas) | o modelo "completa" a stack típica sem olhar o repo |
| [Q] HIST | hotspot (caminho, arquivo ou módulo numa linha que fala de histórico), par de co-change (mesma janela de 4 linhas) e ≥2 commits de correção reais citados — no texto ou em `facts/history.json5` | só aparecem lendo `git log` |
| G9 sessão | save→resume.json5; load ≤2.000 tokens e idempotente; commit novo ⇒ delta | — |
| G10 delegação | hook bloqueia despacho sem brief e despacho paralelo com colisão | hook chamado diretamente com o payload do Claude Code |
| G11 autonomia | aceite verde reexecutado; teste de aceite com sha256 intacto; tasks ACCEPTED com verify (evento) e review de gate≠autor; diff git ⊆ allowed_paths ∩ território; relatório | "fazer passar" editando o teste ou escrevendo fora do território reprova |
| ESC | feature que exige float: money.py/test_money/ADR intactos, aceite ainda vermelho, evento de escalada | implementar a feature reprova 3 de 4 |
| BUG | BUG com repro/severidade/teste; o teste falha com o `late_fees.py` original e passa depois; FIX com `fixes:`; **oráculo oculto** passa | ajustar só o caso do relato não passa o oráculo (6 casos) |
| G12 processo | DoR/DoD: bug sem teste, fix sem `fixes:`, feature com story aberta, sprint devolvendo ao backlog; árvore EPIC→FEAT→SPRINT→story→task com rollup | — |
| [Q] HUMAN / TESTCMD / STALE | conteúdo humano preexistente preservado; comando de teste real citado; afirmação velha do README não repetida como verdade | — |
| G13 mapas/docs | tree com todo diretório de produto; stack = lockfile; par acoplado em `do_not_parallelize`; README velho vira fato `stale` | exige cruzar doc × lockfile × git |
| G14 roteamento | trivial→barato, risco→topo, gate ≥ autor, retry sobe, sem `model` bloqueia, outcome sem procedência não muda prior; no autônomo, custo < tudo no topo | — |
| G15 autocorreção | correção vira lição injetada; `cs-mem check` reprova repetição citando a lição; 2ª ocorrência promove com proposta; 200 lições ⇒ ≤30 ativas e ≤5 itens/≤1.500 chars; arquivada/stale não injeta; taxa de recorrência | — |
| G16 etapas | `stage load` ≤2k tokens; `stage done` com check falho não avança; retomada no meio do scan; load em processo novo só com disco (todo path citado existe) | — |
| FMT | artefatos JSON5; nenhum mapa em `.md` fora do que a plataforma exige | — |
| [T] | transcrição (grader LLM): scan antes de redigir, entrevista ≤8 perguntas só sobre lacunas, GO/NO-GO honesto | — |

`check_run.py` emite asserções mais finas que as de `evals.json` (ex.: G5 por comando, G12 por cenário);
o prefixo `[Gx]` liga as duas.

## Limitações conhecidas

- Os cenários G8–G16 dependem dos nomes de subcomando de `cs-state`/`cs-session`/`cs-route`/`cs-mem`/`stage`. Os
  nomes em `harness_scenarios.json` seguem `references/harness.md` §3 e foram conferidos contra o código em
  2026-10-02 (fixture py-billing com `cs.py init` + `scan` + `team derive` + `harness install`: 18/19 cenários
  passam; `G16.fresh-subagent-disk-only` só passa num alvo em que a execução chegou a `validate` fechado). Quando
  a CLI divergir, a evidência mostra o comando e a saída — ajuste o JSON, não o grader.
- Erro de uso do argparse sai com exit 2: todo passo `expect: "fail"` traz `stdout_any` com a mensagem de recusa
  esperada, para que uma flag errada não passe como "recusou".
- `cs-state`, `cs-route` e `cs-mem stats` não têm saída JSON: as asserções desses cenários são por texto
  (`tier: haiku`, `treina: False`, `samples: {}`). O board grava o estado em `state`, não em `status`.
- G14 não cobre "gate ≥ tier do autor" por cenário: `cs-route recommend` não expõe o tier do autor na CLI; a regra
  é exercida pelo hook `pre-agent` de revisão e pelo `cs.py harness selftest`.
- O cosseno do G3 é léxico; o limiar 0,35 foi calibrado com os cartões de referência e deve ser recalibrado
  quando a skill tiver cartões de controle gerados para um repositório de controle (ARCHITECTURE §9).
- Latência do G8 usa o `ms` informado pelo `cs-mem` (sem o tempo de subir o processo).
- O filtro de negação (`NEG_RE`) casa `no` como palavra inteira — em português "no" é "em + o", então linhas como
  "TypeScript no front, Java no serviço" são descartadas por NEG/FIX/STALE (leniente). Conhecido; não corrigido para
  não mudar as notas já publicadas sem uma rodada de recalibração.
- INV casa palavra-chave (`keywords_all`): paráfrase correta sem o termo ("migração editada… a resposta é migração
  nova") reprova. Conferido à mão na iteração 2 (go-polyglot sem skill, `fleetd-ops`).
