# campanha-iter11 — plano de medição real da `codebase-specialists` 0.6.0

Escrito pelo agente do ORÁCULO (não corrige a skill). Itens de origem: `docs/PONTOS-DO-FOUNDER.md` (pendentes
"Medição final da iteração 4", "Prova do sanitize num init completo nas 3 fixtures; evals 4–6", "Pacotes de entrada
por comando; caminho único das respostas do exame"), `docs/ROADMAP-proxima-rodada.md` (Passo 0, SANITIZE-1..4,
critério de parada), `docs/08-limites-e-defeitos-conhecidos.md` (P1 pacotes) e `iteration-4/RESULTADOS-E-DEFEITOS.json5`.
Lições aplicadas: L01 (calibrar corretor), L02 (qualidade × estrutura), L04 (sistema congelado), L05 (diretório
próprio), L12 (modo barato ao lado), L13 (GO simulado no veredito), L19–L21 (oráculo não sobreajustado; passar
testes ≠ força dos testes; held-out).

Perguntas que a medição responde:
1. **Q1 — vale?** A skill (`--fast`, o padrão) entrega time de qualidade [Q] maior que o Claude sem a skill, por
   item, com IC — e a que custo (tempo, tokens)?
2. **Q2 — o modo caro paga?** `--full` muda [Q] em relação a `--fast` (L12)?
3. **Q3 — o processo fecha limpo?** init completo nas 3 fixtures termina com approve.4 (sanitize) verde, GO e
   zero contornos manuais?
4. **Q4 — o harness entrega?** evals 4 (autônomo), 5 (escalada), 6 (bugfix) — nunca rodados.
5. **Q5 — fechar a iteração 4** (py-billing e go-polyglot pausados) sem refazer o que já existe.

---

## 1. Sistema congelado (L04) — antes da 1ª execução

| O que | Como congela | Onde fica |
|---|---|---|
| Skill sob medição | sha256 da árvore `~/.claude/skills/codebase-specialists` (sem `__pycache__`, `.DS_Store`) + commit do repo `~/.claude/skills` (tech-lead registra; este agente não roda git) | `campanha-iter11/congelado/skill.sha256` |
| Corretor e gabarito | sha256 de `evals/check_run.py`, `evals/summarize.py`, `evals/harness_scenarios.json`, `evals/fixtures/*/GROUND_TRUTH.json`, `evals/fixtures/*/history.plan`, `evals/fixtures/py-billing-features/**`, `evals/reference/**`, `oraculo/pareado.py` | `campanha-iter11/congelado/oraculo.sha256` |

Regra: nenhuma frente de correção escreve na skill enquanto houver execução da campanha em andamento. Antes de
CADA grading o orquestrador confere os dois sha256; divergência ⇒ PARE (a campanha é inválida desde a última
conferência verde). Mudança de corretor só por `ac.py oracle change --why --evidence` e, se houver, **todas** as
execuções são regradeadas com o corretor novo (nunca misturar versões de corretor numa tabela).

A versão medida é a que passar o oráculo deste diretório + as suítes da skill (3.13 e 3.9.6). Medir a 0.6.0
atual sem as correções de §8 é permitido só como "linha de base da campanha" — e U-2 garante, de antemão, que
approve.4 falha em alvo migrado (não afeta init novo).

## 2. Fixtures

| Fixture | Eval (prompt vago, como na iteração 4) | Gabarito | Por que entra |
|---|---|---|---|
| `py-billing` | id 1 — "monta o time de agentes pra esse repo" | `fixtures/py-billing/GROUND_TRUTH.json` | ADRs/invariantes, bug plantado, fixture-armadilha .NET/Jest |
| `ts-shop` | id 7 — "create a team of expert agents for this monorepo" | `fixtures/ts-shop/GROUND_TRUTH.json` | monorepo, ranges × lock, README velho |
| `go-polyglot` | id 10 — "monta o time de agentes especialistas para este repo" | `fixtures/go-polyglot/GROUND_TRUTH.json` | `go` ausente ⇒ `declared`; polyglot |
| `py-billing` + feature | ids 4, 5, 6 (autônomo, escalada, bugfix) | `py-billing-features/<f>/feature.json`, `hidden_test_late_fee.py`, `GROUND_TRUTH.planted_bug` | Q4 |

Construção: `bash $SK/evals/fixtures/build.sh <fixture> <run>/target` (repositório git com histórico realista;
aborta se divergir de `repo/`). Evals 4–6: alvo = **cópia** do `target` final de `eval-1-py-billing/with_skill_fast/run-1`
(GO) + `bash $SK/evals/fixtures/install_feature.sh <feature> <alvo>`; baseline sem skill dos 4–6 = fixture recém
construída + `install_feature.sh` (sem time).

## 3. Configurações

| Config (nome no disco) | O que roda | Observação |
|---|---|---|
| `without_skill` | mesmo prompt, Claude Code sem a skill (`--disallowedTools Skill` + negar leitura de `~/.claude/skills/codebase-specialists/**`) | baseline; o único jeito de saber se a skill vale o custo (L04) |
| `with_skill_fast` | prompt do eval (a skill entra no padrão `--fast`) | modo padrão — o produto |
| `with_skill_full` | prompt do eval + " --full" | modo certificado; L12 (comparar com o barato) |

Execução sem humano (todas as configs com skill): o prompt recebe o apêndice fixo
"Sem humano: aprovações com `--by eval-sim --simulated`; entrevista respondida pelo que o repositório mostra,
marcando `--simulated`; liste TODO contorno manual em `<run>/notes.md` sob 'CONTORNOS MANUAIS'." O veredito é
registrado como **"GO (simulado)"** (L13).

## 4. Quantas execuções (e por quê)

Variância observada (dados do workspace, corretor atual regradeado nesta escrita — ver `base.txt`):

| Fonte | [Q] | Tempo | Tokens (orquestrador) |
|---|---|---|---|
| sem skill (it.1, n=1/fixture) | 9, 10, 10 /13 | 395–473 s (7 min ± 0,7) | 87–93 k |
| com skill completa (it.2 n=1×3; it.3) | 13/13 em 6/6 execuções (go: 13 real, 11 no corretor) | 1.860–3.496 s (sd 934 s) | 330–398 k + 40+ subagentes não contados |
| com skill `--fast` (it.3 py; it.4 ts) | 13/13 em 2/2 | 21–33 min | 230–269 k + 33–79 subagentes não contados |
| Δ pareado it.2 (`pareado.py`, 39 itens, n=1) | +0,256, IC95% [0,128; 0,410] (itens); [0,231; 0,308] (fixtures) | — | — |

Leitura: com a skill o [Q] está **no teto** (sd ≈ 0 entre execuções); a variância que importa é a da baseline
(nunca medida dentro da mesma fixture: sempre n=1) e o custo (CV ≈ 30 %).

| Config | Execuções por fixture | Total | Justificativa |
|---|---|---|---|
| `without_skill` | **3** = 1 reaproveitada (it.1, regradeada com o corretor congelado; iguais ao histórico) + **2 novas** | 6 novas | barato (~7 min); dá a 1ª estimativa de variância intra-fixture da baseline, que domina o IC |
| `with_skill_fast` | **2** | 6 | no teto, 2×13 itens por fixture: se a taxa real de falha por item fosse ≥10 %, P(0 falhas em 26) = 0,9²⁶ ≈ 6 % ⇒ 94 % de chance de ver a instabilidade; 2 execuções também dão a 1ª leitura de taxa de GO e de contornos |
| `with_skill_full` | **1** | 3 | L12: só para Q2 (equivalência com o fast, já sugerida em it.3); caro (~50 min) — **opcional** (decisão do founder no orçamento) |
| evals 4–6 com skill | 1 cada | 3 | descritivo (nunca rodados); sem IC — declarar n=1 |
| evals 4–6 sem skill | 1 cada | 3 | [Q] de resultado (aceite/oráculo oculto) comparável |

Ampliação condicional: se o IC de Q1 sair INCONCLUSIVO, ou se alguma execução fast tiver [Q] < 13, acrescente
+1 `with_skill_fast` e +1 `without_skill` por fixture **antes** de decidir (decisão de ampliar registrada antes de
ver o resultado da ampliação).

## 5. Diretórios e procedimento por execução (L05)

```
campanha-iter11/
├── oraculo/                       ESTE diretório (ESPEC, testes, pareado.py, base.txt) — congelado
├── congelado/                     skill.sha256, oraculo.sha256, settings-executor.json, settings-baseline.json
├── iter4-fechamento/<fixture>/    §10 (cópias dos alvos pausados; o histórico nunca é tocado)
├── runs/eval-<id>-<fixture>/<config>/run-<k>/
│   ├── target/                    alvo (build.sh) — a execução escreve SÓ aqui e em ./tmp/
│   ├── tmp/                       temporários da execução (TMPDIR aponta para cá)
│   ├── transcript.jsonl           stream-json do executor
│   ├── timing.json                {total_duration_seconds, total_tokens, tokens_by_kind, total_cost_usd, subagents}
│   ├── grading.json               check_run.py (corretor congelado)
│   ├── notes.md                   CONTORNOS MANUAIS (executor)
│   └── audit.json                 auditoria do gabarito (§6) e contagem mecânica de contornos
└── resultados/                    benchmark-q.{md,json} (summarize.py), pareado-*.json, adjudicacao.jsonl, RELATORIO.md
```

Passos (um por vez, nunca duas execuções simultâneas — ROADMAP "UMA POR VEZ"):
1. `bash $SK/evals/fixtures/build.sh <fixture> <run>/target`
2. `cd <run>/target && TMPDIR=<run>/tmp claude -p "<prompt>" --output-format stream-json --verbose --settings <congelado/settings-*.json> > ../transcript.jsonl`
   — sessão nova por execução; retomada só pelo disco (`/codebase-specialists retomar`), nunca do zero (L07).
3. `timing.json` a partir da mensagem `result` do stream: `duration_ms`, `usage` (input, output, cache_read,
   cache_creation), `total_cost_usd`, `num_turns`. **Calibração do custo na 1ª execução com skill:** conferir se o
   total inclui os subagentes (somar `usage` de todas as mensagens, inclusive as de sidechain); se não incluir,
   o total oficial é a soma. Nunca mais "orquestrador apenas" (as iterações 2–4 subcontaram 40–79 subagentes).
4. Auditoria do gabarito (§6) → `audit.json`; reprovada ⇒ execução INVÁLIDA (descarta e refaz; conta no custo).
5. `python3 $SK/evals/check_run.py <run>/target $SK/evals/fixtures/<fixture>/GROUND_TRUTH.json --mode setup --out <run>/grading.json`
   (evals 4–6: `--mode autonomous|escalation|bugfix [--feature <f>]`; ids 2/8 não entram).
6. Contornos manuais = união de (a) itens de `notes.md` 'CONTORNOS MANUAIS' e (b) scripts relatados como DEFEITO
   por `sanitize` (`.swarm/sanitize.json5`) — o (b) é mecânico e vale mesmo se o executor esquecer o (a).
7. GO/NO-GO de `.swarm/acceptance.json5` + `approve.2` (rótulo "GO (simulado)").
8. Depois das execuções da fase: `python3 $SK/evals/summarize.py campanha-iter11/runs --out-dir campanha-iter11/resultados`
   e `python3 oraculo/pareado.py campanha-iter11/runs --a with_skill_fast --b without_skill --json resultados/pareado-fast-vs-sem.json`
   (idem `--a with_skill_full --b with_skill_fast`).

## 6. Gabarito oculto

**Onde:** `~/.claude/skills/codebase-specialists/evals/` — `fixtures/*/GROUND_TRUTH.json`, `history.plan`,
`history/`, `py-billing-features/bug-late-fee/hidden_test_late_fee.py`, `py-billing-features/*/feature.json`,
`check_run.py`, `harness_scenarios.json`, `reference/**` (inclui a futura `reference/good/*/apply.sh`) — e
`campanha-iter11/oraculo/` + `campanha-iter11/resultados/adjudicacao.jsonl`. O `build.sh` copia só `repo/`; o
`install_feature.sh` nunca leva o oráculo oculto (teste `test_gabarito_presente` + checagem de não-vazamento).

**Quem NÃO pode ler:** o executor de qualquer config e todos os subagentes dele (inclusive o orquestrador da
skill); a frente que escreve a saída boa de referência não lê `hidden_test_late_fee.py` (escreve contra
`bug.md` + `feature.json`, L15/L19); quem adjudica a amostra manual não é o executor nem o autor do corretor.
Quem pode: o passo de grading (orquestrador da campanha, depois que a execução terminou), o adjudicador e o
humano.

**Como se garante (não só por instrução):**
1. `congelado/settings-executor.json` e `settings-baseline.json` negam `Read`/`Grep`/`Glob` em
   `~/.claude/skills/codebase-specialists/evals/**` e em `campanha-iter11/{oraculo,resultados}/**` (baseline: a skill
   inteira).
2. Auditoria pós-execução (mecânica, `audit.json`): busca em `transcript.jsonl` por `evals/fixtures`, `GROUND_TRUTH`,
   `hidden_test_`, `check_run`, `evals/reference`, `campanha-iter11/oraculo`, `py-billing-features`; qualquer
   ocorrência em chamada de ferramenta ⇒ execução INVÁLIDA. Baseline: também `skills/codebase-specialists`.
3. sha256 do gabarito conferido antes de cada grading (§1).

## 7. Corretor e calibração (L01)

Calibração obrigatória ANTES da 1ª execução paga e de novo se o corretor mudar:

| Ponto | Setup (ids 1/7/10) | Evals 4–6 |
|---|---|---|
| Saída vazia ⇒ 0 | fixture recém-construída: **0/13 [Q], 0/15 [S]** nas 3 (conferido nesta escrita) ✔ | `build.sh` + `install_feature.sh`: escalation 0/4 ✔, bugfix 0/5 ✔, **autonomous 1/11 ✘** (C-1) — teste `test_saida_vazia_da_zero` |
| Saída boa conhecida ⇒ ≥0,9 | ts-shop it.4 migrado (`upgrade`): **[Q] 12/13** (STALE = falso positivo de negação já conhecido; real 13/13) ✔ | **não existe** — `evals/reference/good/<f>/apply.sh` (contrato em `test_evals_4_6.py`) ✘ |
| Baseline conhecida | it.1 sem skill regradeada: **9, 10, 10 /13** = histórico ✔ | — |
| Saída ruim conhecida | — | atalho "trocar o teste de aceite" reprova a asserção do sha ✔ |

**Amostra manual (por execução):** sorteio determinístico (seed = `run_id` do `run.json5`; baseline = nome do
diretório) de **2 asserções [Q]** + **todas** as [Q] reprovadas das execuções com skill + todas as asserções
sensíveis a negação (STALE, NEG, FIX) — conferidas contra o alvo por um adjudicador (humano ou agente que não
executou nem escreveu o corretor). Registro em `resultados/adjudicacao.jsonl`:
`{run, item, corretor: bool, manual: bool, evidencia: "arq:linha", nota}`.
A tabela oficial é a do corretor; a coluna "adjudicada" vai ao lado. Se, numa config, corretor e manual
discordarem em > 1 item/execução em média, o corretor é corrigido (oracle change) e TUDO é regradeado.

## 8. Métricas

- **[Q] qualidade** (13 asserções neutras de formato no setup; comparável com a baseline): por execução,
  passadas/13; por item, fração de execuções que passaram. Coluna corretor + coluna adjudicada.
- **[S] estrutura** (G1–G16, FMT, cenários): reportada à parte, **nunca** somada ao [Q] (L02); baseline não tem [S].
- **Evals 4–6**: hoje o corretor marca tudo [S] (C-2). Contrato fixado em `test_evals_4_6.py`: são [Q] os resultados
  — autônomo: aceite verde, aceite sem alterar teste, regressão verde, protegidos intactos; escalada: invariante
  intocado, aceite vermelho e inalterado, regressão verde; bugfix: teste falha antes/passa depois, oráculo oculto,
  código corrigido + regressão. O resto (board, eventos, tiers, sessão, relatório) é [S].
- **Custo**: tempo de parede (s), tokens totais **incluindo subagentes** (input/output/cache separados),
  `total_cost_usd`, nº de subagentes. Sempre ao lado da qualidade (L04).
- **Processo**: decisão GO/NO-GO (simulado), contornos manuais (nº e lista), approve.4 verde, tamanho de `.swarm/`.

## 9. Critério de decisão

Comparação **pareada por item** (unidade = fixture × asserção [Q]; 39 itens no setup): para cada item,
d = p(com) − p(sem); estatística = média de d; IC95% por bootstrap percentil reamostrando itens (10.000, seed 11),
com sensibilidade reamostrando fixtures. Implementado em `oraculo/pareado.py` (congelado com o corretor).

| Pergunta | Conta como … | Regra |
|---|---|---|
| Q1 fast × sem skill | **GANHO** | IC95% (itens) com limite inferior > 0 **e** [Q] médio fast ≥ sem skill em CADA fixture **e** nenhum item com d ≤ −0,5 |
| | sem ganho | qualquer outra coisa (INCONCLUSIVO ⇒ ampliação condicional de §4, uma vez) |
| Q1 custo | informação para o humano | razão tempo e tokens (com/sem) e "itens [Q] ganhos por Mtoken extra"; o corretor não decide se vale |
| Q2 full × fast | **EQUIVALENTE** ⇒ fast segue padrão | IC95% de d(full − fast) inteiro em [−0,05; +0,05] |
| | full melhor | limite inferior > 0 ⇒ escalar ao founder (custo × ganho) |
| Q3 processo | **fecha limpo** | por fixture, ≥1 execução fast com approve.4 verde (teste `TestSanitizeInitCompletoCampanha`) e GO; zero contornos manuais em todas |
| Q4 evals 4–6 | **entrega** | todas as [Q] do modo passam (n=1, descritivo); escalada: evento de escalada presente |
| Critério de parada do ROADMAP | **CUMPRIDO** | ≥ 2/3 das execuções fast GO; ZERO contornos; [Q] ≥ baseline nas 3 fixtures; oráculo deste diretório verde; suítes da skill verdes em 3.13 e 3.9.6 |

Teto: com a skill o [Q] satura (13/13); o instrumento não mede ganho acima disso — o IC de Q1 é dominado pelas
falhas da baseline (TERR cobertura, STACK, HIST, INV). Ganho em [S] não é ganho de qualidade.

## 10. Retomar py-billing e go-polyglot sem refazer (Q5)

Estado real (lido do disco): ambos com `current_stage: validate` em layout legado `.specialists/`; scan,
specialize e (pulada no --fast) round-table feitos. py-billing: `validate.3` guiado + 27 juízes feitos, modo
fechado lote 1 em andamento. go-polyglot: `validate.2` baseline feito, guiado começando.

**Caminho oficial (fecha a iteração 4 sem misturar sistemas — L04):**
1. Copiar cada alvo: `cp -R iteration-4/<f>-setup-vague/with_skill/{target,outputs} campanha-iter11/iter4-fechamento/<f>/`
   (o histórico fica intocado; L05).
2. Skill CONGELADA da iteração 4: worktree de `~/.claude/skills` no commit em uso em 2026-10-03 16:35
   (tech-lead identifica: `git -C ~/.claude/skills log -1 --until="2026-10-03 16:35" -- codebase-specialists`;
   PONTOS C5 cita `deefa36`) em `campanha-iter11/congelado/skill-iter4/`.
3. Um subagente por execução, uma por vez: "No repositório `<cópia>/target`, retome com
   `python3 <skill-iter4>/codebase-specialists/scripts/cs.py stage load validate` seguindo o SKILL.md DESSA cópia;
   sem humano: `--by eval-sim --simulated`; liste TODO contorno manual em `<cópia>/outputs/notes.md` sob
   'CONTORNOS MANUAIS'." `stage load` retoma na sub-etapa pendente — nada de scan/cartões/baseline é refeito.
4. Grading com o corretor DAQUELE commit (`<skill-iter4>/.../evals/check_run.py`, que lê `.specialists/`) — o
   corretor atual lê `.swarm/` e daria zeros falsos. Resultado vai à tabela da iteração 4 (3/3 concluídas), não à
   da campanha.

**Caminho alternativo (só depois de U-1 e U-2 corrigidos):** `upgrade --apply --allow-outside` na cópia e retomar
com a 0.6.x. Mistura duas versões numa execução ⇒ rótulo "híbrido", fora de qualquer tabela comparativa; serve como
teste funcional de "legado pausado → upgrade → retomada → sanitize" (é o que `TestSanitizeProxyIter4` exige).

## 11. Ordem, custo estimado e checkpoints

| Fase | Execuções | Tempo (parede) | Tokens (estimativa, inclui subagentes¹) |
|---|---|---|---|
| 0 calibração mecânica (§7) + congelamento | 0 LLM | ~15 min | ~0 |
| 1 fechamento it.4 (§10) | 2 retomadas | ~40 min | ~2–3 M |
| 2a baseline | 6 `without_skill` | ~45 min | ~0,6 M |
| 2b fast | 6 `with_skill_fast` | ~3 h | ~9–18 M |
| 2c full (opcional) | 3 `with_skill_full` | ~2 h 45 | ~9–12 M |
| 3 evals 4–6 | 3 com skill + 3 sem | ~1 h 30 | ~3–4 M |
| **Total** | 23 (20 sem o full) | **~9 h** (~6 h 15 sem o full) | **~24–38 M** (~15–26 M sem o full) |

¹ Base: orquestrador medido (fast 230–269 k; completa 330–398 k; sem skill ~90 k) + 33–79 subagentes por execução
com skill × ~25–40 k cada (não medido até hoje — a 1ª execução fast calibra; refaça esta tabela com o número real).
Janela de uso de 5 h: checkpoint em disco ao fim de cada execução; parar e perguntar ao passar ~50 % da janela;
fases 2b e 2c atravessam janelas (uma execução nunca é dividida sem `retomar`).

Ordem: 0 → 1 → 2a → 2b (alternando fixtures: py, ts, go, py, ts, go) → decisão Q1 → 2c (se o founder quiser) → 3.
As frentes de correção (§12) rodam ANTES da fase 2 (sistema congelado durante 2–3).

## 12. Testes mecânicos deste diretório (requisitos para as frentes de correção)

`cd campanha-iter11/oraculo && python3 -m unittest -v test_pacotes_entrada test_sanitize_init_completo test_evals_4_6`
(também com `/usr/bin/python3` 3.9.6). Base contra a 0.6.0 em `base.txt`: 29 testes, 28 falhas (esperado).

| Arquivo | Prova | Contrato fixado |
|---|---|---|
| `test_pacotes_entrada.py` | os 4 comandos existem e produzem pacotes corretos num alvo real (ts-shop it.4 migrado); maioria dos juízes; recusas; exame com UM caminho de respostas | `facts spotcheck pack --out [--n] [--batch K/M]`, `team core pack --out`, `panel why pack <a> --out`, `panel why tally <a> --from` (formatos no docstring) |
| `test_sanitize_init_completo.py` | A) proxy: os 3 alvos da it.4 migrados → `sanitize --apply` → limpo (tmp vazio, .gitignore, sem `.git` aninhado, ≤ 5 MB, git status só manifesto/gerenciados, SANITIZE-2/3/4, approve.4 só fecha limpo). B) prova real: execução COMPLETA da campanha nas 3 fixtures, como entregue | layout `runs/eval-<id>-<fixture>/with_skill_<fast|full>/run-<k>/target` |
| `test_evals_4_6.py` | evals 4–6 definidos com prompt/gabarito/check; gates de evals.json = gates do corretor; calibração vazio ⇒ 0, referência boa ⇒ ≥ 0,9, atalho reprova; [Q]×[S] nos modos | `evals/reference/good/<feature>/apply.sh <alvo>` (determinístico, sem LLM) |
| `pareado.py` | ferramenta de decisão (§9), não teste | congelada com o corretor |

Anti-sobreajuste (L19–L21): os testes miram a CLASSE do defeito (comando ausente, 2º caminho de resposta, ponto
grátis, lixo no backup), não uma saída exata; a prova B do sanitize só passa com execução real. Antes de GO das
frentes: verificador cego com shell + mutação independente (L20), feitos por agente que não é este nem o corretor.

## 13. Achados desta escrita (entram como defeitos da rodada)

| Id | Defeito | Evidência | Impacto |
|---|---|---|---|
| U-1 | `upgrade --apply` de alvo legado PAUSADO antes da etapa harness falha no selftest (exige pre-commit; reinstala sem `--git-hook`) e restaura | py-billing e go-polyglot da it.4: "FALHA pre-commit → cs-precommit … G6 VERMELHO" | bloqueia a retomada pela 0.6.0 (caminho alternativo de §10) |
| U-2 | backup do upgrade copia `tmp/` do legado (10 clones de exame com `.git` + `outside/.git`) para `.swarm/backups/`; `sanitize` não limpa; `sanitize --check` fica vermelho para sempre | ts-shop it.4 migrado: `.swarm/` 20 MB; `--check`: ".git aninhado fora de tmp/: .swarm/backups/upgrade-…/specialists/tmp/exam/*/repo/.git" | approve.4 inalcançável em todo alvo legado migrado (inclui a cobaia do founder se tiver tmp/ sujo) |
| C-1 | modo autonomous: saída vazia aprova "[G11] nenhuma escrita fora de território" | `git diff` vazio ⇒ lista "fora" vazia ⇒ passa | ponto grátis (L01) |
| C-2 | modos 4–6 sem [Q] | `summary.quality.total = 0` | sem comparação com baseline (L02) |
| P-1 | 3 caminhos de resposta do exame | `<out>/questions.json5` → `<out>/answers.json5`; `.swarm/probes/exams/<a>.questions.json5` → `.swarm/probes/exams/<a>.answers.json5`; `prompts.json5` → `{tmp}/answers/<a>.guided.json5`; `probes check --answers <qualquer>` copia em silêncio | executor escreve script/cópia (contorno) |
| P-2 | sem `facts spotcheck pack`, `team core pack`, `panel why pack`, `panel why tally` | `.specialists/tmp/why-majority.sh`, `tmp/spotcheck/`, `tmp/in/*.facts.json5` no ts-shop it.4 | 4 dos 5 contornos manuais da it.4 |

O que o oráculo pode estar favorecendo: (a) [Q] no teto favorece a skill só pelos erros da baseline — itens
difíceis para ambos não existem no instrumento; (b) a amostra manual mira negação (falso positivo conhecido),
não falso negativo; (c) baseline com `--disallowedTools Skill` ainda vê o CLAUDE.md/AGENTS.md humanos da fixture —
igual ao histórico, mantido por comparabilidade.
