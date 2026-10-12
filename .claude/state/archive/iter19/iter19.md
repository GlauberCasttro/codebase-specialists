# iter19 — Estado legível em JSON, chaves em inglês, amend refletido no arquivo, cs-state show e migração automática

## Resumo
A 0.11.0 torna o estado de entidade do harness gerado legível e confiável: JSON padrão (indent 2, bytes
determinísticos, ordem de leitura, `_generated_by`), chaves em inglês com aliases pt aceitos na leitura, `cs-state
amend` refletido no arquivo no mesmo evento (history com before/after/reason), `cs-state show` e a migração
`state-format` — no motor (`state.py migrate state-format [--dry-run]`, um evento `arvore.format` encadeado com o mapa
de caminhos, sem reescrever eventos antigos, idempotente) e automática no `cs.py upgrade --apply` (validate --strict
antes e depois, plano pelo dry-run, restauração do backup em falha, eventos antigos como prefixo). Logs JSONL, config
JSON5, memória do cs-mem e chaves do mandato M5 não mudam. Origem: uso real na segunda cobaia .NET (B-14).

## Critérios de aceite
### CA-01 — JSON padrão em ordem de leitura
DADO um alvo em modo árvore, QUANDO o motor grava qualquer entidade
  (task, story, sprint, feature, épico, sessão, projeção), ENTÃO o arquivo é `.json` que `json.loads` aceita, indentado
  com 2 espaços, um item de lista por linha, chaves na ordem de leitura (id, kind, type, title, agent, allowed_paths,
  protected_paths, as_a, i_want, so_that, acceptance_criteria, …, timestamps, internos, history por último), com
  `_generated_by` como campo, e serializar o mesmo estado 2 vezes dá os mesmos bytes; o validate continua verde.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA01`

### CA-02 — chaves em inglês, leitura das antigas
DADO o estado de uma entidade, QUANDO é gravado, ENTÃO nenhuma
  chave de entidade está em português (mapa por caminho: `para` da story → `so_that`, `para` do histórico → `to`),
  exceto as do mandato M5; E QUANDO o motor lê um arquivo com as chaves antigas em pt, ENTÃO entende como as novas.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA02`

### CA-03 — amend refletido no arquivo
DADO uma task iniciada com AC-1 e AC-2, QUANDO `cs-state amend` remove o
  AC-2, ENTÃO o arquivo da task deixa de listar o AC-2, o `history` registra antes, depois e motivo, e um reopen não
  ressuscita o AC-2; e DADO uma task não iniciada, QUANDO o amend muda `acceptance_criteria`, ENTÃO é aceito e refletido.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA03`

### CA-04 — cs-state show
DADO uma entidade existente (id ou alias), QUANDO `cs-state show <id>` roda, ENTÃO imprime
  Markdown com título, agente, escopo, critérios, estado e histórico resumido, sem escrever nada; id inexistente sai
  com erro.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA04`

### CA-05 — migração automática no upgrade
DADO um alvo 0.10.1 realista (≥ 30 eventos, itens em backlog, state e
  archive, arquivos `.json5`), QUANDO roda `cs.py upgrade` (plano) e depois `upgrade --apply`, ENTÃO o plano lista o
  que muda sem escrever; o apply converte todo `.json5` de estado de entidade para `.json` com a ordem e as chaves
  novas por UM evento encadeado novo com o mapa de caminhos, sem reescrever eventos antigos; validate e cadeia íntegros
  antes e depois; rodar de novo não muda nada; e o commit do resultado passa no pre-commit sem `--no-verify`.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA05`

### CA-06 — o que não muda continua igual
DADO a mudança aplicada, QUANDO se compara com antes, ENTÃO logs JSONL
  (events, ledger, approvals, model-router), arquivos de config JSON5 (team, config, machines, routing, run,
  migrations), memória do cs-mem e chaves do mandato M5 ficam iguais; e VERSION é 0.11.0 com a migração no catálogo.
  Prova: `cd campanhas/iter19/oraculo && python3 -m unittest test_iter19.TestCA06`

## Linha do tempo
- 2026-10-07T11:32:50-0300 · inicio E0
- 2026-10-07T11:33:07-0300 · proposta E1
- 2026-10-07T12:01:06-0300 · aprovacao E1
- 2026-10-07T12:01:22-0300 · proposta E2
- 2026-10-07T12:08:50-0300 · aprovacao E2
- 2026-10-07T12:09:36-0300 · proposta E3
- 2026-10-07T12:14:04-0300 · aprovacao E3
- 2026-10-07T12:15:49-0300 · proposta E4
- 2026-10-07T12:16:52-0300 · aprovacao E4
- 2026-10-07T12:17:09-0300 · proposta E5
- 2026-10-07T12:27:41-0300 · aprovacao E5
- 2026-10-07T12:27:44-0300 · abertura abertura
- [NOTA] 2026-10-07T12:27:44-0300 — Abertura da feature iter19
- [PASS] 01-TASK-ORACULO — 2026-10-07T12:48:13-0300
- [NOTA] 02-TASK-FORMATO-CHAVES — 2026-10-08T19:25:51-0300
- [NOTA] 06-TASK-VERSAO-DOCS — 2026-10-08T19:25:51-0300
- [NOTA] 06-TASK-VERSAO-DOCS — 2026-10-08T19:26:16-0300
- [PASS] 02-TASK-FORMATO-CHAVES — 2026-10-08T20:23:58-0300
- [NOTA] 03-TASK-AMEND-SHOW — 2026-10-08T20:23:59-0300
- [PASS] 03-TASK-AMEND-SHOW — 2026-10-08T21:12:48-0300
- [NOTA] 04-TASK-MIGRAR-ESTADO — 2026-10-08T21:12:49-0300
- [PASS] 04-TASK-MIGRAR-ESTADO — 2026-10-10T13:09:02-0300
- [NOTA] 05-TASK-UPGRADE — 2026-10-10T13:09:03-0300
- [NOTA] 06-TASK-VERSAO-DOCS — 2026-10-11T12:16:46-0300
- [PASS] 05-TASK-UPGRADE — 2026-10-11T13:17:22-0300
- [PASS] 06-TASK-VERSAO-DOCS — 2026-10-11T13:17:22-0300
- [NOTA] 07-TASK-QA — 2026-10-11T13:17:39-0300
- [PASS] 07-TASK-QA — 2026-10-11T20:10:07-0300
- [NOTA] 08-TASK-REVIEW — 2026-10-11T20:10:12-0300
- [PASS] 08-TASK-REVIEW — 2026-10-11T20:13:54-0300

## Tasks
| id | entrega | tipo | grupo | status | gate |
|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da iter19 (CA-01..CA-06), escrito por agente separado | ORACULO | — | DONE | PASS |
| 02-TASK-FORMATO-CHAVES | Estado em JSON, ordem de leitura e chaves em inglês | CORRECAO | G1 | DONE | PASS |
| 03-TASK-AMEND-SHOW | amend refletido no arquivo e cs-state show | CORRECAO | G1 | DONE | PASS |
| 04-TASK-MIGRAR-ESTADO | cs-state migrate (formato) por evento encadeado | CORRECAO | G1 | DONE | PASS |
| 05-TASK-UPGRADE | migração automática no cs.py upgrade --apply | CORRECAO | G2 | DONE | PASS |
| 06-TASK-VERSAO-DOCS | 0.11.0, migração no catálogo e documentação do formato | CORRECAO | G3 | DONE | PASS |
| 07-TASK-QA | Portão e oráculo, CA a CA | QA | — | DONE | PASS |
| 08-TASK-REVIEW | Revisão isolada da feature | REVIEW | — | DONE | PASS |

### Handoff 01-TASK-ORACULO
- Executor: rh-oraculista-01-TASK-ORACULO-1 (general-purpose, opus), ficha conferida (`rh.py conferir` OK).
- Entregue: ESPEC.md, test_iter19.py (39 testes, TestCA01..TestCA06), medir.py, base.txt; alvo realista com 43 eventos.
- Medido pelo tech-lead no HEAD 97a1718: 11/39 (D 0/28, R 11/11), idêntico em python3 3.13 e /usr/bin/python3 3.9.
- Congelado: `oracle freeze` 1083cc4a985e. Lacunas declaradas: board plano pré-0.7.0, mistura .json5/.json só
  indireta, chave desconhecida no fim, mandato selado (exige senha).

### Handoff 02-TASK-FORMATO-CHAVES
- Executor: general-purpose · sonnet (ciclo 1). Revisor: general-purpose · opus, instância isolada · APPROVED (snapshot:
  não escreveu). Independência: instâncias distintas.
- Arquivos: hcore.py (mapa pt→en por caminho ITEM_SCHEMA/SESSION_SCHEMA, item_to_en/item_to_pt, READ_ORDER, write_json,
  write_item_json, read_state, pick_state_file), tree.py, session.py, autonomy.py, validate.py, selftest.py, auto.py;
  tests: test_iter19_estado.py (novo, 9), test_iter20_atestado.py (casos .json).
- Desenho: forma interna e eventos tput seguem com chaves pt; tradução só na borda (gravar/ler); canonical e cadeia
  intactos; mandato M5 com chaves pt, só formato .json.
- Oráculo: TestCA01 7/7; TestCA02 4/6 — os 2 restantes falham só no `cs-state find` (state.py:349, sufixo de alias
  depois do caminho), fora desta task; PASS comprovado em cópia de rascunho com a linha trocada ⇒ RESSALVA: a correção
  vai na 03 e o CA-02 só fecha lá. TestCA06: só version/catálogo falham (task 06).
- Régua do tech-lead (cópia, 2 Pythons): harness 327 OK (16 skip), upgrade 8 OK (7 skip, pré-existentes), memory 14 OK.
  Oráculos iter18 R1–R7 (34) e iter20 (24) verdes (executor). Privacidade: 0.
- Findings do revisor (MENOR) roteados: #3 validate aceita chave pt inserida antes da en e #find + state.py:717 → task 03;
  #1 migrate plano→árvore sem os .json → task 04; #2 OWN_RESIDUE sem selftest.json → task 05; #4 texto
  "autonomy.json5" em validate.py:178-187 → ressalva (cosmético).

### Handoff 03-TASK-AMEND-SHOW
- Executor: general-purpose · sonnet (ciclo 1). Revisor: general-purpose · opus, instância isolada · APPROVED (snapshot:
  não escreveu). Independência: instâncias distintas. Ressalva de método: o executor não observou o RED dos testes
  novos antes de implementar (o RED do oráculo congelado já estava na base: CA-03/CA-04 D falhando).
- Arquivos: tree.py (mirror_amend, ac_view, criterios_of_ac, AMEND_MIRROR, show_md; acceptance_criteria em
  TREE_AMENDABLE; validate estrito para .json), cmds.py (task.amend ganha tput do item no MESMO evento), state.py
  (`show`, `find` terminando no caminho, texto autonomy-report.json), tests/test_iter19_estado.py (13).
- Oráculo: TestCA01..CA04 23/23 nos 2 Pythons (inclui os 2 do CA-02 que ficaram da task 02).
- Régua do tech-lead (cópia, 2 Pythons): harness 331 OK (16 skip), upgrade 8 OK (7 skip), memory 14 OK. Privacidade 0.
- Revisor testou à mão: amend de verification_command/allowed_paths/title/AC pontuado em task iniciada (1 evento,
  tput por último, arquivo e history corretos), validate verde após amend/close/reopen/restart, show sem escrita.
- Findings (MENOR): #1 `after` do history não normalizado (≠ `before` do próximo amend; tree.py:669 e :632) → task 04
  (tree.py); #2 amend em task fechada espelha no arquivo de archive sem reopen → ressalva/decisão de comportamento.

### Handoff 04-TASK-MIGRAR-ESTADO
- Executor: general-purpose · sonnet (ciclo 1), RED observado (10/26 falhando antes). Revisor: general-purpose · opus,
  instância isolada · APPROVED (1ª instância caiu por limite de API; 2ª concluiu). Snapshot pré-revisor: só artefatos
  de build `evals/**/obj/` mudaram (gerados pelas suítes), nenhum código.
- Comando: `python3 <alvo>/.swarm/harness/state.py --root <alvo> migrate state-format [--dry-run]` (kind `state-format`
  para a task 05). Dry-run: "state-format (dry-run): N arquivo(s) … nada foi escrito" + pares; apply: "migrado: N …";
  sem .json5: "nada a migrar: estado já em JSON (idempotente)", exit 0; RECUSADO (exit 1) se o validate não passa antes.
- Arquivos: tree.py (migrate_format, format_plan, path_ident; find/show resolvem caminho antigo; lista plano→árvore com
  .json; `after` normalizado; amend sem mudança não registra), state.py (subcomando), tests/test_iter19_estado.py (26).
- Régua do tech-lead (cópia, 2 Pythons): harness 344 OK (16 skip), upgrade 8 OK, memory 14 OK.
- Revisor: replay do zero == disco byte a byte; dry-run não escreve nada (inclui .git); eventos antigos prefixo byte a
  byte; validate --strict e read_chain OK.
- Ressalva (MENOR, BACKLOG B-29): queda entre gravar os itens e anexar o evento perde o mapa antigo→novo na auditoria
  (operação não afetada). Limites aceitos: post=False; visões/rascunho do mandato não convertidos (leitura dos 2
  formatos); amend sem mudança em task iniciada ainda gera evento M2.

### Handoff 05-TASK-UPGRADE
- Executor: general-purpose · sonnet (ciclo 1, retomada do parcial de um executor anterior da mesma task, interrompido
  com a sessão de 2026-10-10). Nesta retomada não escreveu: conferiu o parcial contra Goal/CA-05. RED limpo não
  observado (o parcial já cobria); a 1ª execução do TestCA05 falhou (7) enquanto a task 06 editava VERSION/migrations
  na cópia — corrida, não reproduziu depois.
- Arquivos: scripts/upgrade/core.py (kind `state-format` em ORDER depois de state-tree e em EXPLICIT_KINDS;
  `_state_format_cmd` chama o motor DA SKILL `state.py --root <alvo> --actor lead migrate state-format [--dry-run]`;
  `_plan_state_format` lista o dry-run no plano; `do_state_format`; validate --strict antes (recusa, exit 3) e
  depois; `events_snapshot`/`events_append_violation` exigem os eventos antigos como prefixo; falha restaura o
  backup), scripts/upgrade/version.py (`state-format` em KINDS, sem parâmetros), tests/test_iter19_upgrade.py (15,
  novo). defs: core.py 54→59, version.py 8→8 (nenhum removido).
- Oráculo (tech-lead): `CS_SKILL_DIR=<cópia> python3 -B -m unittest test_iter19` OK 2× em python3 e 2× em
  /usr/bin/python3 (CA-05: 9 testes).
- Régua do tech-lead sobre a CÓPIA (`CS_DEV_SKILL_DIR=<cópia> e2e.py rodar`, 16 suítes do produto, 2 Pythons):
  VERDE; harness 344 (16 skip) = base; upgrade 23 (7 skip ambientais: $CS_UPGRADE_LEGACY_TARGET ausente). A 1ª
  rodada foi inválida: sem CS_DEV_SKILL_DIR a régua testou o projeto vivo (contagens 318/8 denunciaram); descartada.
- Revisor: general-purpose · sonnet, instância isolada · APPROVED (parecer integral em REVIEWS/05-TASK-UPGRADE.md);
  snapshot pré/pós-revisor sem mudança. Privacidade: 0 achados.
- Ressalvas MENOR: validate prévio pulado em layout legado (.specialists/) — a segurança fica no motor e no verify
  pós; PRESERVED_PATHS não cobre events.jsonl da árvore (guarda real: events_append_violation, testada). Lacuna:
  sem teste de ponta a ponta da violação de prefixo dentro do apply().

### Handoff 06-TASK-VERSAO-DOCS
- Executor: general-purpose · sonnet (ciclo 1). RED não observado (editou antes de rodar) — registrado como limite.
- Arquivos (os 9 do contrato, conferidos por snapshot): VERSION 0.11.0; README.md; references/migrations.json5
  (version 0.11.0; entrada to 0.11.0 com harness, state-format, emit; kind documentado no cabeçalho);
  docs/10-arvore-de-estado.md (seção "Formato do estado em JSON (0.11.0)": bytes determinísticos, ordem de leitura,
  mapa pt→en, o que não muda, show, amend refletido, migrate state-format); docs/09-upgrade.md (Migração 0.11.0 +
  nota B-20 no fim); docs/06-referencia-cli.md; docs/01-conceitos.md; docs/05-sessao-e-retomada.md;
  references/ARCHITECTURE.md (1 linha). Nenhum código.
- Oráculo (tech-lead): TestCA06 OK em python3 e /usr/bin/python3; test_iter19 completo OK 2× em cada.
- Régua do tech-lead sobre a CÓPIA: VERDE nas 16 suítes do produto, 2 Pythons (doctests 19; upgrade 23).
- Revisor: general-purpose · sonnet, instância isolada · APPROVED (parecer integral em REVIEWS/06-TASK-VERSAO-DOCS.md);
  conferiu cada afirmação dos docs no código com path:linha; snapshot sem mudança. Privacidade: 0 achados.
- Ressalvas MENOR: docs/10 cita `verify_cmd` na lista do amend onde o campo do comando é `verification_command`
  (→ verify_cmd no arquivo) — corrigir na QA/REVIEW ou no fechamento; a nota B-20 supõe changed_sha256 desde a
  0.10.0 (não conferido).

### Handoff 07-TASK-QA
- QA: general-purpose · sonnet (instância isolada), 1ª passada: portão VERMELHO só por classes de versão fixa de
  oráculos anteriores (iter18 TestR8Versao; iter20 TestU5Versao/TestU5DeZeroNoveDireto), 8 falhas reproduzidas pelo
  tech-lead; QA não escreveu nada (snapshot). Custo registrado.
- Decisão do founder (2026-10-11): iter18 R1–R7 e iter20 U1–U4; B-32 no BACKLOG.
- 2ª passada pelo tech-lead (mesmo comando, oráculos por classe; lista `local/iter19-arquivos.txt`, 23 arquivos,
  = diff da cópia): `RESULTADO: VERDE` + `FIM`, contagens e oráculos no Aceite QA do FEATURE.md; `oracle verify`
  intacto.
- Pendente para a REVIEW: ressalva MENOR da 06 (`verify_cmd` × `verification_command` na docs/10).

### Handoff 08-TASK-REVIEW
- Revisor: general-purpose · opus, instância isolada que nunca executou nada na feature · APPROVED, sem findings
  novos (parecer integral em REVIEWS/08-TASK-REVIEW.md); snapshot pré/pós sem mudança. Custo registrado.
- CA-01..CA-06 PASS (oráculo rodado pelo revisor nos 2 Pythons) e os 4 focos (cadeia de eventos, idempotência,
  mapa de chaves por caminho, amend atômico) PASS.
- Ressalvas mantidas como MENOR: B-29 vale também para migrate_format (tree.py:1722-1741, .json gravados antes do
  evento); lacuna de teste: dry-run deixar .git byte a byte igual (snapshots ignoram .git).

## Como a feature nasceu
### E0 — Pré-condição · CONCLUÍDA 2026-10-07T11:32:50-0300
- Demanda: "B-14: estado em JSON padrão, ordem de leitura, chaves em inglês, amend refletido no arquivo, cs-state show, migração automática no upgrade"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-07T12:01:06-0300
- Produzido: problema enunciado; FEATURE-ID iter19
- Itens aprovados: 1: mandato M5 fora da tradução (só formato); 2: memória cs-mem fora; 3: migração por evento novo encadeado
- Aprovação: "ok"
- Sha: 2b5df20bdf41883fc4ee2e9291c718374a493bc432fab0a803468b05751148e3
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-07T12:08:50-0300
- Produzido: investigação medida (local/criar-iter19/E2.md)
- Medido: 1324 linhas json5: 77 mudam, 117 config/produto, 21 legado, 20 memória (fora), 14 infra, 495 fábrica, 580 testes; ~16 arquivos de produto
- Aprovação: "ok"
- Sha: e6800c9cbede207dd5c81ff472b16081a78b5e4d16fbbec92bd7a3535623b670
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-07T12:14:04-0300
- Produzido: FEATURE.md com CA-01..CA-06 (contrato PASS)
- Aprovação: "ok"
- Sha: 594d69e946bc67eee73fb4d901f3da6e7d8b50ccd3848ae95dcd475a43349ed3
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-07T12:16:52-0300
- Produzido: 8 tasks (ORACULO, 5 CORRECAO em G1/G2/G3, QA, REVIEW); contrato completo PASS, sonda OK
- Aprovação: "ok"
- Sha: 2e1bf90a7a98dfb3548b71d584c9dab67f37905a4d9be9b8ee35f93d4ef53c58
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-07T12:27:41-0300
- Produzido: plano de abertura
- Aprovação: "ok"
- Sha: 3d9863636cab43a3e0a7c574f713cca72d0f18734a136b5f389d3f2ca41cd6d8
- Próxima: oráculo por agente separado

### Abertura · 2026-10-07T12:27:44-0300
- Campanha: campanhas/iter19
- Tasks: 8 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)

## Campanha
- campanha: campanhas/iter19 · etapa do motor: concluida · rodada: 0
- critério de parada: oráculo iter19 100% verde (CA-01..CA-06) em python3 e /usr/bin/python3; oráculos iter16, iter18 R1–R7 e iter20 verdes; suítes do produto e harness-dev verdes; 0 `def` removido; VERSION 0.11.0.
- escopo: scripts/harness/engine/*.py, scripts/harness/tests/*.py, scripts/upgrade/*.py, scripts/upgrade/tests/*.py, references/migrations.json5, references/*.md, docs/*.md, assets/templates/*.md, assets/templates/state/*.md, VERSION, README.md

## Oráculo
- `campanhas/iter19/oraculo/ESPEC.md`
- `campanhas/iter19/oraculo/test_iter19.py`
- `campanhas/iter19/oraculo/medir.py`
- `campanhas/iter19/oraculo/base.txt`

## Decisões técnicas
- Kind de upgrade `state-format` depois de `state-tree` em ORDER; chama o motor DA SKILL, como `do_state_tree`.
- Mapa pt→en por CAMINHO (o mesmo `para` vira `so_that` na story e `to` no history).
- Migração por UM evento novo com o mapa de caminhos; eventos antigos que citam `.json5` seguem resolvendo por
  find/show (34 de 70 eventos de um alvo real citam `.json5`).
- Chaves do mandato M5 ficam em pt (o selo é hash delas) — B-21.
- Portão da 0.11.0 com iter18 R1–R7 e iter20 U1–U4 (founder, 2026-10-11): classes de versão fixa ficam fora; B-32.

## Aprendizados
- A 1ª régua completa das tasks 05/06 deu VERDE testando o projeto VIVO, não a cópia: `e2e.py rodar` sem
  `CS_DEV_SKILL_DIR` cai na raiz do projeto em silêncio. Só as CONTAGENS denunciaram (harness 318 × 344; upgrade 8 ×
  23). Regra: conferir contagem contra a base, não só o RESULTADO.
- Oráculos congelados com versão fixa envelhecem a cada subida de versão (8 falhas sem defeito) — B-32.
- "Arquivos da feature" = permitidos das CORRECAO, inclusive os não alterados: a lista do portão tem de ser a mesma,
  ou o conferir-commit recusa; custou uma rodada extra de portão. Montar a lista pelos permitidos desde o QA.
- Retomada de executor interrompido: conferir o parcial na cópia contra o Goal antes de redespachar evitou retrabalho
  (task 05 já cobria o CA-05).
- Pareceres integrais dos revisores passaram a ser gravados em `features/<id>/REVIEWS/` (B-31 propõe exigir no gate).
- O hook de aprovação nega heredoc que mencione palavras de aprovação; escrever Handoff pelo Edit.

## Arquivos da feature
- `scripts/harness/engine/hcore.py`
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/session.py`
- `scripts/harness/engine/validate.py`
- `scripts/harness/engine/autonomy.py`
- `scripts/harness/engine/auto.py`
- `scripts/harness/engine/selftest.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/engine/views.py`
- `scripts/harness/tests/test_iter19_estado.py`
- `scripts/harness/tests/test_iter20_atestado.py`
- `scripts/harness/tests/test_workflow_e2e.py`
- `scripts/harness/engine/cmds.py`
- `scripts/harness/engine/state.py`
- `scripts/upgrade/core.py`
- `scripts/upgrade/version.py`
- `scripts/upgrade/tests/test_iter19_upgrade.py`
- `VERSION`
- `README.md`
- `references/migrations.json5`
- `references/ARCHITECTURE.md`
- `docs/01-conceitos.md`
- `docs/05-sessao-e-retomada.md`
- `docs/06-referencia-cli.md`
- `docs/09-upgrade.md`
- `docs/10-arvore-de-estado.md`

## Aceite da Feature
### Aceite QA — ACCEPT
### Aceite Review — APPROVED

## Pareceres dos revisores (transcrição integral)

### Parecer — 05-TASK-UPGRADE (revisão pontual, tentativa 1)

Registrado pelo tech-lead em 2026-10-11, transcrição integral do retorno do revisor. Snapshot pré/pós-revisor da
cópia: nenhum arquivo mudou (fora artefatos `evals/**/obj/`). Custo registrado em `logs/custo.jsonl`.

```
REVISOR: Claude Code · general-purpose · model: sonnet (passado pelo tech-lead) · instância isolada
BASE: HEAD 7b490df + cópia local/work/iter19/codebase-specialists · arquivos examinados: 3 (core.py, version.py e o teste novo, mais references/migrations.json5 da cópia para contexto)

MATRIZ: CA-05 → PASS
- `python3 -B -m unittest scripts.upgrade.tests.test_iter19_upgrade -q` na cópia: 15 testes OK.
- Plano sem escrever: test_plano_lista_json_e_nao_escreve (snapshot antes/depois; cada par antigo → .json5 → no texto).
- Apply: test_apply_converte_todo_o_estado (nenhum .json5 de estado sobra; cada par antigo virou .json).
- Evento novo: test_um_evento_novo_e_antigos_prefixo_byte_a_byte (bytes antigos de events.jsonl são prefixo; um único arvore.format).
- Segunda execução: test_segunda_execucao_nao_muda_nada.
- Commit: test_commit_pelo_hook_sem_no_verify.
- Validate antes (core.py ~1063-1070, retorna 3 sem escrever) e depois (verify existente).
- O apply verifica o prefixo de events.jsonl (core.py ~1102-1105) e esse caminho restaura o backup.

(a) Falha restaura o backup: todo ok=False cai em restore_backup e retorna 1 (motor, exceção, verify, prefixo).
    TestFalhaDaAcaoRestaura simula exit 1 do motor: snapshot idêntico e "backup restaurado" na saída.
(b) Sem .json5 o upgrade não escreve além do habitual: dry-run "nada a migrar"; --apply repetido deixa snapshot idêntico.
(c) Nenhum def removido: core.py 54 (HEAD) → 59 (cópia; novos _state_format_cmd, _plan_state_format,
    do_state_format, events_snapshot, events_append_violation); version.py 8 → 8.
(d) Chama o motor da SKILL como do_state_tree (V.HERE/harness/engine/state.py, mesmo --root/--actor lead,
    CLAUDE_PROJECT_DIR, CS_GUARD_OFF removido, CMD_TIMEOUT).
Privacidade: guard-privacidade.sh nos 3 arquivos: 0 achados.

FINDINGS:
- [MENOR] [REGRESSÃO] [SUSPEITA] scripts/upgrade/core.py:~1063 — alvo em layout legado (.specialists/) com migração
  que traz state-format → o validate --strict ANTES é pulado (not plan["layout_legacy"]); a segurança vem do motor
  (recusa se validate falha) e do verify depois com restauração. Sem cenário concreto de dano.
- [MENOR] [REGRESSÃO] [CONFIRMADO] scripts/upgrade/core.py:1075-1108 — PRESERVED_PATHS só cobre state/events.jsonl e
  state/board.json5 (layout plano); na árvore a guarda real de eventos é events_append_violation (correta e testada).

VEREDITO: APPROVED
LIMITES: leu o diff completo e o teste; rodou só o teste novo e o guard; não rodou oráculo, régua nem /usr/bin/python3.
LACUNAS: nenhum teste exercita o validate ANTES reprovado em layout legado, nem a violação de prefixo dentro do
apply() de ponta a ponta; o motor (state.py migrate state-format) é das tasks 02–04 e não foi revisado aqui.
```

### Parecer — 06-TASK-VERSAO-DOCS (revisão pontual, tentativa 1)

Registrado pelo tech-lead em 2026-10-11, transcrição integral do retorno do revisor. Snapshot pré/pós-revisor da
cópia: nenhum arquivo mudou (fora artefatos `evals/**/obj/`). Custo registrado em `logs/custo.jsonl`.

```
REVISOR: Claude Code · general-purpose · model: sonnet (passado pelo tech-lead) · instância isolada
BASE: HEAD 7b490df + cópia local/work/iter19/codebase-specialists · arquivos examinados: 9 (diff contra HEAD) +
código: engine/hcore.py, tree.py, state.py, session.py, cmds.py e upgrade/core.py, version.py

MATRIZ: CA-06 → PASS
- VERSION e README em 0.11.0.
- migrations.json5: version "0.11.0" e entrada to "0.11.0" com actions harness, state-format, emit; bate com
  version.py:26 (KINDS com state-format, sem parâmetros: version.py:124) e core.py:45 (ORDER harness → state-tree →
  state-format → emit). why no estilo das anteriores.
- Diff só em docs e catálogo, sem código. format_plan (tree.py:1682) só converte itens da árvore, sessões e .engine
  (projection, autonomy, selftest, autonomy-report): config, memória e M5 ficam de fora.

Afirmações dos docs conferidas no código, sem divergência:
- Mapa pt→en (docs/10) = ITEM_SCHEMA, _CLOSED, _CLOSED_METRICS, _CRITERIA, _HISTORY, SESSION_SCHEMA (hcore.py:~250-272);
  caso `para` (so_that na story, to no history) correto.
- Ordem de leitura = READ_ORDER (hcore.py:276); history por último em order_item.
- Bytes determinísticos: json_text (hcore.py:~345) indent 2 e \n final; _generated_by é campo do JSON.
- Sessões .json com blocks/title/lines (session.py:461-467); resume.json5 segue JSON5 (session.py:147).
- migrate state-format [--dry-run]: argparse state.py:289-291; evento arvore.format tree.py:1741; "nada a migrar"
  tree.py:1714; recusa se validate falha tree.py:1707-1709 com exit 1 (state.py:762); dry-run não escreve.
- Upgrade: motor da skill (core.py:886-891); plano pelo dry-run (core.py:902-918); conflito recusa --apply
  (core.py:910, 1056); state-tree já grava .json (tree.py:358).
- show: read-only (state.py:362); saída tree.py:1308-1347.
- amend refletido: mirror_amend (tree.py:636-658) regrava no mesmo evento e acrescenta history action=amend com
  before/after/reason; campo não espelhável ou emenda sem mudança deixa o evento como está; task não iniciada
  (tree.py:661+, state.py:315).
- Órfão .json5 ao lado do .json e .json com chave pt acusados como edição à mão: tree.py:1470-1499.
- B-20: cmds.py:603-614 — sem changed_sha256, _invalidate_reviews_if_changed move as reviews para reviews_invalidated.

FINDINGS:
- [MENOR] [REGRESSÃO] [CONFIRMADO] docs/10-arvore-de-estado.md (seção "cs-state show e o amend refletido", bullet do
  amend) — a lista "(acceptance_criteria, allowed_paths, verify_cmd, title)" mistura nomes: verify_cmd é a chave do
  arquivo; o campo passado ao cs-state amend é verification_command (tree.py:632-633, AMEND_MIRROR). Sugestão:
  "(verification_command → verify_cmd no arquivo)". Não bloqueia.
- [MENOR] [SUSPEITA] docs/09-upgrade.md (nota B-20) — "verifies feitos já na 0.10.0 ou depois guardam o hash"
  depende de changed_sha256 ter entrado exatamente na 0.10.0; não conferido.

VEREDITO: APPROVED
LIMITES: revisão estática por grep e leitura; não rodou oráculo nem guard (usou os resultados do tech-lead).
LACUNAS: versão em que changed_sha256 entrou (finding 2); docs/10 e docs/09 lidos só no diff.
```

### Parecer — 08-TASK-REVIEW (modo feature, tentativa 1)

Registrado pelo tech-lead em 2026-10-11, transcrição do retorno do revisor. Snapshot pré/pós-revisor da cópia: nenhum
arquivo mudou. Custo registrado em `logs/custo.jsonl`.

```
REVISOR: Claude Code · general-purpose · model: opus (passado pelo tech-lead) · instância isolada · modo feature
BASE: 7b490df + cópia local/work/iter19/codebase-specialists · arquivos examinados: 23 (lista; defs comparados nos .py,
leitura dirigida de state.py, tree.py migrate_format/amend/mirror_amend, hcore.py mapa de chaves)

MATRIZ:
CA-01 → test_iter19.TestCA01 rodado pelo revisor: OK em python3 e /usr/bin/python3 → PASS
CA-02 → TestCA02 (historico_para_vira_to_por_caminho, le_chaves_pt_e_grava_em_ingles); mapa por caminho hcore.py:244-276 → PASS
CA-03 → TestCA03 (AC some do arquivo, history before/after/reason, reopen não traz o AC-2) + tree.mirror_amend: tput no MESMO evento → PASS
CA-04 → TestCA04 + test_iter19_estado (show inexistente só lê; find/show resolvem o caminho antigo .json5) → PASS
CA-05 → TestCA05 + upgrade/test_iter19_upgrade, 2 Pythons (um evento novo, antigos prefixo byte a byte, 2ª execução não muda nada, pre-commit passa) → PASS
CA-06 → TestCA06 (VERSION, catálogo e config em json5, JSONL canônico, memória e mandato) → PASS
Foco 1 cadeia de eventos → migrate_format: 1 evento arvore.format com tput + data.paths; replay checado em tree.py:1446; antigos prefixo byte a byte; find/show do .json5 antigo (test_iter19_estado:457) → PASS
Foco 2 idempotência → "nada a migrar" sem evento (estado:445; upgrade:148; oráculo ca05_segunda_execucao); dry-run do motor retorna antes de qualquer escrita (tree.py:1716); ".git intocado" verificado pelo código, sem teste dedicado → PASS
Foco 3 mapa de chaves → para: so_that na story × to no history; aliases pt lidos; config/JSONL/memória/mandato intocados (ca06 + estado:487) → PASS
Foco 4 amend atômico → ops tput anexado ao evento do amend; reopen sem ressuscitar o AC → PASS
Extras: oracle verify "oráculo intacto"; nenhum def removido; guard-privacidade 0 achados; nenhum TODO/stub em scripts/** fora de tests.

FINDINGS: —
(As ressalvas MENOR já registradas continuam MENOR. B-29 vale também para migrate_format: os .json são gravados dentro
do build antes de o evento ser anexado (tree.py:1722-1741); queda no meio deixa .json sem evento; sem perda de eventos
antigos e a re-execução refaz o plano ⇒ não promovida a BLOQUEANTE.)

VEREDITO: APPROVED
LIMITES: não reproduziu queda real no meio de amend/migração (só análise); não reexecutou as suítes completas (confiou
no portão do QA); sem alvo sintético próprio além das fixtures dos testes.
LACUNAS: nenhum teste prova que o dry-run (motor e upgrade) deixa .git byte a byte igual (snapshots ignoram .git);
sugestão para iteração futura, não bloqueia.
```

<!-- fechar-feature:archive-completo -->
