# HISTORICO — feature harness-evolucao

<!-- APPEND-ONLY: [NOTA] | [PASS] | [REJECT]; escrito pelo feature.py e pelo tech-lead, em série -->

## [NOTA] 2026-10-09T20:29:18-0300 — Abertura da feature harness-evolucao
- campanha: campanhas/harness-evolucao (ac.py init; escopo: scripts/memory/mem.py, scripts/memory/cli.py, scripts/memory/tests/test_evolucao_memoria.py, scripts/harness/engine/guard.py, scripts/harness/engine/brief.py, scripts/harness/install.py, assets/templates/correct.md, assets/templates/memory.md, docs/03-memoria-e-licoes.md, scripts/harness/engine/tree.py, scripts/harness/engine/state.py, scripts/harness/engine/engine.py, scripts/harness/engine/cmds.py, scripts/harness/engine/views.py, scripts/harness/engine/auto.py, scripts/harness/engine/session.py, scripts/harness/engine/autonomy.py, scripts/harness/engine/selftest.py, scripts/harness/engine/classify.py, scripts/harness/engine/report.py, scripts/harness/machines.json5, scripts/harness/tests/test_evolucao_arvore.py, scripts/emit/platforms.py, scripts/emit/render.py, assets/templates/orchestrator.md, assets/templates/plan-sprint.md, assets/templates/product-process.md, assets/templates/state/*.md, references/harness.md, docs/02-harness.md, docs/10-arvore-de-estado.md, scripts/cslib/json5io.py, scripts/cslib/jsonio.py, scripts/cslib/README.md, scripts/cslib/tests/test_jsonio_formato.py, scripts/harness/engine/j5.py, scripts/harness/engine/hcore.py, scripts/emit/j5.py, scripts/upgrade/core.py, scripts/upgrade/tests/test_json_format.py, scripts/cs.py, references/migrations.json5, references/ARCHITECTURE.md, docs/09-upgrade.md)
- tasks: 14 · primeira: 01-TASK-ORACULO
- investigação aprovada (E2):

    # E2 — Investigação medida
    
    Base: levantamento por 6 analistas de responsabilidade única + 2 verificadores cegos-executores (skill
    orquestrar-subagentes, rigor standard, 2026-10-09, HEAD 7aa3cb4). Matriz completa e relatórios em
    `local/levantamento-evolucao-harness/` (MATRIZ.md, SINTESE.md, 6 relatórios, 3 vereditos). Experimentos E2 rodaram
    com os comandos reais (`cs.py init`, `harness install`, `cs-state`, `cs-mem`, `cs-auto`) em alvos de rascunho fora
    do repo; o repo ficou intocado (git status igual antes e depois, conferido 5 vezes).
    
    ## Inventário
    - Requisitos da demanda mapeados: 132 → EXISTE 22 · PARCIAL 52 · FALTA 50 · DIVERGE 8 (script sobre os 6 relatórios).
    - Achados: 79 nos 6 relatórios (A 9, B 15, C 11, D 13, E 14, F 17); 69 após dedupe por script; após verificação: 61 FATO, 7 SUSPEITA reverificadas pelo orquestrador (5 confirmadas, 2
      duplicatas de fatos confirmados), 1 REFUTADO. Crítico/alto confirmados: 22.
    - `.json5` no código do produto: 687 ocorrências em 65 arquivos `.py` fora de testes
      (`grep -ro "\.json5" scripts --include=*.py | grep -v /tests/`); 65 arquivos de teste citam json5; 37 docs
      (`docs/`, `references/`, `SKILL.md`, `README.md`, `MODO-DE-USO.md`).
    - Oráculos congelados que citam json5: 47 arquivos em 13 campanhas (harness-dev 2, iter9 5, iter10 5, iter11 7,
      iter12 3, iter13 5, iter14 2, iter15 2, iter16 3, iter18 2, m5 4, win-harness 3, win-motor-copia 4).
    - Oráculos que exercitam close/reopen/avulsa: 16 arquivos em 7 campanhas (harness-dev 2, iter10 3, iter13 2, iter15 2,
      iter16 2, iter18 2, m5 3).
    - Caminho legado (`add epic|feature|story`, `add task --quick`, `sprint plan`) em textos que guiam o modelo: 17
      ocorrências em 7 arquivos (assets/templates/{orchestrator,plan-sprint,product-process}.md, scripts/emit/
      {platforms,render}.py, scripts/harness/engine/views.py, references/harness.md).
    - `"/bin/sh"` fixo no produto: 3 pontos (engine.py:109, selftest.py:97, mem.py:1027).
    - Testes do produto que cobrem árvore/reopen: 0 arquivos em scripts/harness/tests
      (`grep -rlE "reopen|tree.init|new epico" scripts/harness/tests`); a cobertura existe só nos oráculos iter10/iter13.
    - Suíte do harness do produto: WSL/Linux 306 testes OK; Windows nativo 243 rodados com 64 falhas + 51 erros
      (relatado pelo analista F; minha reexecução estourou 300 s sem resumo — número não confirmado; a causa /bin/sh foi
      confirmada isoladamente).
    
    ## Classificação
    Por área (requisitos EXISTE/PARCIAL/FALTA/DIVERGE; soma 132):
    - Classificação e decomposição (§3–4, analista A): 40 → 3/20/13/4.
    - Ciclo de vida, propagação, reabertura, arquivo (§5–8, analista B): 32 → 10/7/14/1.
    - Persistência JSON5→JSON (§9, analista C): 8 → 1/4/3/0.
    - Memória e init (§10, analista D): 16 → 0/7/8/1.
    - correct e aprendizado (§11, analista E): 21 → 2/10/8/1.
    - Validação ponta a ponta e autocorreção (task final, analista F): 15 → 6/4/4/1.
    - Soma: 132 → 22/52/50/8 (fecha com o total). Roteiro de 23 passos no WSL: PASSA 10, FALHA 11 (1 parcial),
      IMPOSSÍVEL 1, MANUAL 3.
    Por destino nesta feature: muda (FALTA + PARCIAL + DIVERGE resolvidos pela E1) · não muda (EXISTE, salvo regressão) ·
    congelado (oráculos de campanhas anteriores: só por mudança oficial com PORQUE).
    Nota: contagens por área calculadas por script sobre os 6 relatórios (`local/levantamento-evolucao-harness/*.json`).
    
    ## Exclusões
    - Fora do escopo: `.claude/` (harness de desenvolvimento) e `.claude/tools/ac/` (motor embutido; origem em ORIGEM.txt).
    - Não lidos integralmente: `scripts/harness/engine/selftest.py` (0% de cobertura ancorada), ~75% de `auto.py`,
      ~85% de `views.py`, ~89% de `session.py`, ~84% de `cmds.py`. Cobertura ancorada total do escopo declarado: 46%.
      Risco: afirmar "falta" sobre algo implementado num trecho não lido (aconteceu 1 vez: F-R1). Mitigação: os FALTA de
      peso foram provados por execução dos comandos reais, não por leitura.
    - Fluxo do board PLANO legado (máquinas epic/feature/sprint/story de machines.json5): fora, exceto onde os textos
      mandam o modelo para ele (F8).
    - Plataformas sem hook (Cursor/Copilot/Codex): só a parte advisory foi lida.
    - Passos 18 e 21 do roteiro (comportamento do LLM) não são mecanizáveis por inteiro: só a parte mecânica (registro,
      injeção, log) entra nos CAs.
    
    ## Achados
    Segurança e memória:
    - F1 (crítico) — `scripts/memory/mem.py:955` — `correct` grava `--wrong/--why` sem redigir segredos: token `ghp_…`
      literal em `.swarm/state/memory/agents/<a>.json5`, no índice `.swarm/memory/index/docs.jsonl` e no pacote S3 dos
      próximos subagentes. Reproduzido por e-correct, v1-executor e pelo orquestrador.
    - F2 (alto) — `scripts/harness/engine/guard.py:261` — o guard confere só o 1º `--agent` (`_opt`, guard.py:193-199) e
      o argparse usa o último: `cs-mem add --agent eu --agent outro` passa (exit 0) e grava na memória do outro.
      Reproduzido por d-memoria-init, v1-executor e orquestrador.
    - F3 (alto) — `scripts/harness/install.py:355` — `cs.py init` + `harness install` não criam memória do projeto nem
      de agente: só o diretório legado vazio `.swarm/memory/agents/`; a memória real (`.swarm/state/memory/agents/<a>.json5`,
      mem.py:169) nasce na 1ª lição; sem log e sem checagem de permissão. Reproduzido por D, F e v1.
    - F4 (alto) — `scripts/memory/mem.py:910` — correção que contradiz a anterior (wrong/right invertidos) tem Jaccard ≥ 0,5
      e vira recorrência: o texto antigo fica e é promovido. Reproduzido por D e v1.
    - F5 (alto) — `scripts/memory/mem.py:858` — com count ≥ 2 a lição vira `promoted` e some de `inject` (mem.py:1056) e
      de `search` (mem.py:504-505); `promotions.json5` não é consumido por código nenhum. Reproduzido por D, E e v1.
    - F6 (alto) — `assets/templates/correct.md:5` — o fluxo termina no registro ("Mostre a saída … e só então siga"):
      sem reexecução, sem validação; o CLI não tem `--scope`/`--task` (mem.py:1161-1168).
    - F7 (alto) — `scripts/harness/engine/engine.py:929` — `SUBMISSION_KEYS` não inclui `lessons_checked`, documentado
      como obrigatório em `references/brief-schema.json5:52`; nada conta aplicação de lição; a injeção no brief
      (`brief.py:139-160`) não grava log.
    - F8b (médio) — `scripts/memory/mem.py:792` — arquivo de memória corrompido é sobrescrito em silêncio, sem backup.
    - F8c (médio) — `scripts/memory/mem.py:784` — `--agent` só validado por regex: nome errado cria memória órfã.
    - F8d (médio) — `scripts/memory/mem.py:174` — no modo árvore `mem_paths['board']` aponta para o legado
      `.swarm/state/board.json5`; `cs-mem check` sem `--files` fica vazio.
    
    Classificação e hierarquia:
    - F8 (alto) — `assets/templates/orchestrator.md:61` — o kernel do orquestrador, `product-process.md`, `plan-sprint.md`,
      `views.py:30` e `references/harness.md:104` mandam usar o board legado; em modo árvore `cs-state add epic` responde
      "criado: EPIC-1" e o item não aparece em `board`/`tree`/`find`. Reproduzido por A e v2.
    - F9 (alto) — `scripts/harness/machines.json5:10` — classes só pergunta|trivial|pequena|feature|risco; `--class epico`
      recusado; o triage valida só enum e `--why` não vazio (engine.py:437-445); nenhum dos 8 critérios do §3 é calculado.
      Reproduzido por A e v2.
    - F10 (alto) — `scripts/harness/engine/tree.py:989` — épico sem sprint, sprint sem feature e feature sem task fecham
      (o close só procura filhos abertos). Reproduzido por A, F e v2.
    - F11 (médio) — `scripts/harness/engine/tree.py:496` — `new task --avulsa` não roda `quick_problems`
      (engine.py:893-926): toca invariante e arquivo de outro território sem recusa.
    - F12 (médio) — `scripts/harness/engine/tree.py:699` — a M2 da task da árvore nasce com `class: "pequena"` e
      `session: None`: a classe da triagem (risco = 2 gates) nunca chega à árvore.
    - F13 (médio) — `scripts/harness/engine/tree.py:377` — épico (objetivo/métrica) e sprint (meta) sem critério
      verificável; CHORE sem critério (AC-1 fabricado, tree.py:687-689); sem `updated_at` nem status persistido
      (tree.py:226-230, 1182).
    - F14 (médio) — `docs/ROADMAP-rodada-seguinte.md:175` — a "inferência pela triagem" está documentada e não existe
      (`grep -i infer scripts/harness/engine/*.py` vazio); não há passo de decomposição nem revisão da árvore inteira.
    - F-R1 (DESCARTADO por medição: refutado por v2-executor) — "a árvore não tem dependências": falso; `cs-state amend
      <task> --field depends_on` depois do start funciona (cmds.py:873) e o dispatch impõe (engine.py:789-793). Resta a
      lacuna menor: não dá para declarar dependência na criação nem antes do start (tree.amend, tree.py:596-606, só
      aceita allowed_paths).
    
    Ciclo de vida:
    - F15 (alto) — `scripts/harness/engine/tree.py:922` — nenhuma propagação: fechar a última task deixa a feature ativa;
      a última feature deixa a sprint ativa; só o M5 fecha a feature e engole a recusa (auto.py:1177-1183). Reproduzido
      por B, F e v2.
    - F16 (alto) — `scripts/harness/engine/tree.py:1052` — reopen com pai fechado é recusado ("reabra o pai antes"); sem
      cascata. Reproduzido por B, F e v2.
    - F17 (alto) — `scripts/harness/engine/tree.py:896` — task reaberta fecha de novo sem novo dispatch/verify/review/
      accept (close lê a M2 antiga ACCEPTED). Reproduzido por B, v2 e orquestrador.
    - F18 (alto) — `scripts/harness/engine/tree.py:947` — `close <feature> --devolver` pula o aceite (só roda em
      `elif z == "state"`), mesmo sem task a devolver. Reproduzido por B, v2 e orquestrador.
    - F19 (alto) — `scripts/harness/engine/tree.py:955` — sprint e épico fecham sem critério; itens do backlog nunca
      iniciados fecham direto para archive/. Reproduzido por B e v2.
    - F20 (médio) — `scripts/harness/engine/tree.py:1042` — reopen não confere "uma feature ativa por vez": gera estado que
      o `validate` reprova.
    - F21 (médio) — `scripts/harness/engine/tree.py:1182` — task reaberta aparece como `[ACCEPTED/ACCEPTED]`.
    - F22 (médio) — `scripts/harness/engine/tree.py:1033` — `feature drop` arquiva tasks nunca feitas como "fechada".
    - F23 (médio) — `assets/templates/state/close-task.md:11` — promete `close <task> --devolver`, que o motor recusa.
    - F24 (baixo) — `scripts/harness/engine/tree.py:10` — fechar épico não leva aprendizado à memória do projeto.
    
    Persistência:
    - F25 (crítico) — `scripts/harness/engine/tree.py:25` — renomear `.json5`→`.json` quebra `cs-state validate` (o
      `path` vive nos eventos encadeados); trocar só o conteúdo por JSON indentado passa. Reproduzido por C e v1.
    - F26 (alto) — `scripts/cslib/json5io.py:285` — o escritor canônico põe objeto de ≤3 campos e listas de escalares
      numa linha, chaves sem aspas, header `//`, indent 1; mesmo código em `engine/j5.py:125`, `emit/j5.py`,
      `team/_shared_tmp/json5mini.py`; `json.loads` falha em todo arquivo gravado. Reproduzido por C, F e orquestrador.
    - F27 (alto) — `references/ARCHITECTURE.md:403` — §8-decies fixa JSON5 como requisito do founder (revogado na E1, item 1).
    - F28 (médio) — `scripts/cslib/jsonio.py:38` — escrita atômica existe em 3 cópias (jsonio:38, hcore:213, mem:106), mas
      nada valida (roundtrip) antes de salvar.
    - F29 (médio) — `scripts/upgrade/core.py:959` — o upgrade já tem backup, restauração, verificação, preservados e
      histórico, mas não há ação json-format, nem detecção de JSON5 no init, nem `formatVersion`.
    
    Autocorreção, relatório e Windows:
    - F30 (crítico) — `scripts/harness/engine/engine.py:109` — `/bin/sh` fixo: no Windows nativo todo verify/aceite sai
      127 e o roteiro para no passo 5 (B-14). Também em `selftest.py:97` e `mem.py:1027`. Confirmado pelo orquestrador.
    - F31 (alto) — `scripts/harness/engine/auto.py:2908` — não há relatório final fora do mandato M5 (`cs-auto report` →
      "sem mandato"); o relatório do M5 não tem itens, estrutura, correções, retestes, aprendizado nem memória.
      Confirmado pelo orquestrador.
    - F32 (médio) — `scripts/harness/engine/cmds.py:94` — esgotar 3 tentativas deixa a task BLOCKED em silêncio; a escalada
      ao humano é manual; `max_attempts` (machines.json5:8) é decorativo.
    - F33 (médio) — `scripts/memory/mem.py:992` — a lição automática da falha guarda o sintoma (tail do verify), não a
      causa raiz; causa e correção só existem como texto livre em `retry --findings`.
    - F34 (médio) — `scripts/harness/tests/test_workflow_e2e.py:15` — a suíte do produto declara a árvore fora de escopo:
      nenhum teste cobre propagação, reabertura, JSON, init de memória ou relatório.
    
    ## Enforcement existente
    - Oráculo iter10 (`campanhas/iter10/oraculo/test_estado_arvore.py`): cobre árvore, casos A/B/C/D, archive (ARCHIVE-1..6),
      task com dois pais recusada — CONGELADO; esta feature não pode quebrá-lo salvo mudança oficial (os casos B/C ficam,
      E1 fronteira).
    - Oráculo iter13 (swarm-dir), m5 (mandato), iter14 (senha), iter15 (D-07: verbo-objeto das skills geradas), iter16,
      iter18: citam json5 e/ou close/reopen — a troca de formato exige mudança oficial nos que comparam `.json5` por nome.
    - Suíte do produto: memória (`scripts/memory/tests/test_mem.py`, cobre correct/inject/promoção — e confirma o vazio da
      promoção em test_mem.py:131), harness (`scripts/harness/tests`, sem árvore), evals (`evals/harness_scenarios.json`
      G12/G15, no board plano).
    - Régua/portão (`.claude/tools/regua.json`, `portao.sh`): suítes nos 2 Pythons, oráculos passados ao portão, nenhum
      `def` removido, privacidade, pacote sem vazamento — a unificação dos 4 escritores JSON5 não pode remover `def`
      (manter funções antigas como fachada).
    - Nada cobre hoje: propagação, cascata de reabertura, cardinalidade, classify, redação de segredo, `--agent` duplicado,
      init de memória, escopo do correct, log de consulta, relatório fora do M5, migração JSON5→JSON. Esses viram o
      oráculo desta feature (a task de validação de 23 passos da demanda).

## [NOTA] 01-TASK-ORACULO — 2026-10-09T21:43:57-0300
- status: IN_PROGRESS · gate: PENDENTE

## [PASS] 01-TASK-ORACULO — 2026-10-09T22:33:13-0300
- status: DONE · gate: PASS
- oráculo e00cf3c5d927 congelado; RED reexecutado pelo tech-lead: Windows 55/79, WSL 51/79 falhas; 19/19 classes RED; 0 calibração falhando

## [NOTA] 02-TASK-GRAVADOR-JSON — 2026-10-09T23:34:31-0300
- status: IN_PROGRESS · gate: PENDENTE

## [NOTA] 04-TASK-MEMORIA-SEGURANCA — 2026-10-09T23:34:43-0300
- status: IN_PROGRESS · gate: PENDENTE

## [NOTA] 07-TASK-SHELL-PORTAVEL — 2026-10-09T23:34:52-0300
- status: IN_PROGRESS · gate: PENDENTE

## [REJECT] 04-TASK-MEMORIA-SEGURANCA — 2026-10-10T05:10:52-0300
- status: IN_PROGRESS · gate: FAIL
- ciclo 1: revisor CHANGES_REQUESTED — segredo escapa por evidence/source/paths/cmd (CA-01); contradição falso-positivo em repetição; proposta da lição superseded segue applied:false

## [REJECT] 07-TASK-SHELL-PORTAVEL — 2026-10-10T05:10:56-0300
- status: IN_PROGRESS · gate: FAIL
- ciclo 1: régua WSL harness 2F+1E — NameError engine não importado em selftest.py:97 (REGRESSÃO); test_selftest_roda RED no Windows (os.symlink no make_sandbox, aguardando decisão do founder)

## [NOTA] 02-TASK-GRAVADOR-JSON — 2026-10-10T05:24:30-0300
- status: IN_PROGRESS · gate: PENDENTE
- ciclo 1: revisor APPROVED com 3 MENOR·REGRESSÃO (team/run preferindo .json legado em hcore.state_paths; j5.dumps_json grava formatVersion null; README com quebra no trecho em crase) — ciclo curto para corrigir antes da task 11

## [PASS] 02-TASK-GRAVADOR-JSON — 2026-10-10T06:29:03-0300
- status: DONE · gate: PASS
- régua WSL 2 Pythons: cslib 28, emit 55, harness 317 OK; revisor ciclo 2 APPROVED; CA-18 principal RED esperado (05/11)
