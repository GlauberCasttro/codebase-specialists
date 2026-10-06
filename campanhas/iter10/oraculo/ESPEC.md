# ESPEC — oráculo campanha-iter10: estado do harness como árvore de pastas

Fonte: `codebase-specialists/docs/ROADMAP-rodada-seguinte.md` (§1–§10) e `docs/PONTOS-DO-FOUNDER.md` (B2–B9, D-0-12).
Oráculo: `test_estado_arvore.py` (69 testes, unittest puro, Python 3.9+, repositórios temporários). Base: `base.txt`. Mais `test_upgrade_u1_u2.py` (11 testes, §2.9: defeitos U-1/U-2 do upgrade).
Quem implementa **não edita** o oráculo. Onde a spec deixa espaço, as escolhas estão na seção "Decisões do escritor
do oráculo" no fim deste arquivo, para o founder conferir.

## 0. Como o oráculo observa (nada de mock)
- `cs-state` = `python3 <skill>/scripts/harness/engine/state.py --root <alvo> [--actor X] ...` (subprocesso)
- `cs-session` = `python3 <skill>/scripts/harness/engine/session.py --root <alvo> ...`
- guard = `python3 <skill>/scripts/harness/engine/guard.py <pre-write|pre-bash>` com payload de hook no stdin e
  `CLAUDE_PROJECT_DIR=<alvo>`
- Pasta de estado `SD` = `cslib.paths.STATE_DIR` (basename); se não existir, `.swarm`. O nome antigo só aparece
  para LER o alvo congelado da iteration-4 (é a campanha iter9 que faz o rename).
- Skill: `$CS_SKILL_DIR`, senão `~/.claude/skills/codebase-specialists`.
- Repo de teste: git com `src/billing`, `src/users`, `src/shared`, `tests/test_billing.py` (verde),
  `repro/test_repro.py` (vermelho até existir `src/billing/fixed.py`), `accept/test_accept.py` (vermelho até
  existir `src/billing/discount.py`); `SD/team.json5` (dev-billing, dev-users, qa, po, reviewer, security),
  `SD/facts/*`, `SD/knowledge/collision.json5`; depois `cs-state init` (exit 0).

## 1. Cenários → testes
| Cenário (spec §10) | Teste(s) | Negativo incluído |
|---|---|---|
| TREE-A | `TestArvorePorCaso.test_tree_a_...` | — |
| TREE-B / TREE-C / TREE-D | `test_tree_b_...`, `test_tree_c_...`, `test_tree_d_...` | — |
| TREE-INV | `TestCombinacoesInvalidas.*` (5) | sprint→feature, épico→sprint, task com 2 pais; feature fora de sprint em state/ |
| TREE-TYPE | `TestTiposDeTask.*` (6) | BUG sem repro / com teste verde; FIX sem `fixes`; US sem critério; FIX não fecha com teste do BUG vermelho |
| STORY-1 | `TestStories.*` (3) | 1 agente não cria `stories/` |
| ONE-FEATURE | `TestUmaFeatureAtiva.*` (2) | `start` da 2ª feature recusado até `park`/`close` |
| PARALLEL-1 | `TestParalelismo.*` (3) | arquivo comum e par `do_not_parallelize` → wave 2 + dispatch recusado |
| TREE-GUARD + escritor único | `TestGuard.*` (3) | escrita sem task bloqueada com dica; modelo escrevendo em backlog/state/archive (Write/Edit/Bash) bloqueado |
| TREE-HAND + coerência árvore×eventos×board | `TestIntegridade.*` (5) | edição à mão, órfão e fechado em state/ → validate exit 1 |
| TREE-MOVE | `TestMoveEPlan.*` (2) | nn nunca reaproveitado |
| ARCHIVE-1..6 | `TestFechamento.test_archive_1..6` | ARCHIVE-2/3/6 recusas; `close` sem accept (nenhum atalho para ACCEPTED) |
| D-0-12 | `TestD012FeatureDrop.*` (3) | drop com task em andamento e com story composta em andamento → recusado |
| SESSION-1/2/3 | `TestSessao.*` (3) | `save --check` falha com passo sem comando e com bloco vazio sem "nenhum" |
| MIGRATE-1 | `TestMigracao.*` (3) | idempotência (2ª execução não muda árvore nem eventos) |
| close de story composta (§6 estendido) | `TestCloseStory` (1) | recusa listando as tasks pendentes; nada move |
| CHORE (manutenção técnica) | `TestChore.*` (4) + `TestSkillsEmitidas.test_new_task_cita_chore_e_seu_dor` | sem motivo / sem verify-cmd → check 1 e start recusado; close com verify-cmd vermelho → recusado, nada move |
| Automação mecânica: `--dry-run` | `TestDryRun.*` (4) | dry-run não escreve (hash); dry-run de operação recusada também recusa |
| Automação mecânica: `cs-state check` | `TestCheckDoR.*` (2) | US sem critério, BUG com teste verde, FIX sem fixes, feature com aceite verde → exit 1 |
| Leitura compacta `board/tree --json` | `TestLeituraCompacta` (1) | — |
| §5 skills emitidas (14) + política de invocação + DoR + skills finas | `TestSkillsEmitidas.*` (7) | mudança de estado com `disable-model-invocation: true`; corpo >40 linhas ou com caminho/id montado à mão reprova |

Regras congeladas que o oráculo respeita (não contradiz): ESCALATED/ABSTAINED não terminais (SESSION-1 deixa uma
task ESCALATED como portão humano pendente); nenhum atalho para ACCEPTED (o pipeline do oráculo passa por
dispatch → submit → verify → review → accept → close, e `close` sem accept é recusado); legacy-ack não é tocado.

## 2. Interfaces FIXADAS

### 2.1 Layout (relativo a `SD/`)
```
backlog/ state/ archive/        três zonas; só o motor escreve
events.jsonl                    cadeia append-only (NA RAIZ de SD, não em state/)
INDEX.md                        gerado; contém ids do que está em state/ e dos últimos fechados
state/sessoes/<timestamp>.json5 carimbos de sessão
```
- Épico: `backlog/epicos/EPC-nnn-<slug>/epico.json5`; após `start`: `state/epicos/EPC-nnn-<slug>/epico.json5`.
- Sprint: pasta `SPR-nnn` (SEM slug). Com épico: `state/epicos/<EPC>/sprints/SPR-nnn/sprint.json5`; sem épico:
  `state/sprints/SPR-nnn/sprint.json5`.
- Feature: `.../sprints/SPR-nnn/features/FEA-nnn-<slug>/feature.json5` quando ativa. Feature criada e **não
  iniciada nunca está em `state/`** (fica em `backlog/`, lugar exato livre).
- Task em pai: `<pasta do pai>/tasks/<nn>-<TIPO>-<slug>.json5` (pai = feature, sprint ou story composta).
- Task avulsa: `state/tasks/<aaaa-mm-dd>-<nn>-<TIPO>-<slug>.json5` (criada direto em state/); `--backlog`:
  `backlog/tasks/<nn>-<TIPO>-<slug>.json5`.
- Story composta: `<feature>/stories/<TIPO>-nnn-<slug>/story.json5` + `tasks/01-...json5`, `02-...` (uma por agente).
- Archive = mesma árvore: task fechada dentro de feature vai para `archive/<mesmo caminho depois de state/>`;
  avulsa fechada → `archive/tasks/<aaaa>/<mm>/<mesmo nome de arquivo>`; sprint/épico fechados levam a subárvore.
- Slug: minúsculas, espaços → `-` (o oráculo só usa títulos ASCII: "Checkout v2" → `checkout-v2`).
- `board.json5` não existe mais (nem em `SD/` nem em `SD/state/`).

### 2.2 Ids
`EPC-nnn`, `SPR-nnn`, `FEA-nnn` sequenciais no repositório a partir de 001; story `US|BUG|FIX-nnn`.
Task: `<id do pai>/<nn>` (ex.: `FEA-001/03`, `SPR-001/01`, `US-001/01`); avulsa `<aaaa-mm-dd>-<nn>` (data local ou
UTC de hoje). `nn` sequencial no pai e nunca reaproveitado. Depois de `move`/`promote`, o id antigo continua
resolvendo em `cs-state find <id-antigo>` (stdout contém o novo caminho).

### 2.3 Campos de arquivo de item lidos pelo oráculo
Todo arquivo de item tem `id` (string, citada em algum evento de `events.jsonl`). Task: `title`, `agent`, `wave`
(int ≥1, presente após `start`), `fixes` (FIX). Story composta: `como`, `quero`, `para`, `criterios`. Fechado:
`closed: {at, by, summary, entregue, devolvido, metricas}`. Migrado: `legacy_id`. Motivo de `park`/devolução: o
texto do `--reason` aparece no arquivo do item. Rota (opcional): se houver `route.model` em algum dict do arquivo da
task, o oráculo despacha com esse modelo; senão `sonnet`.

### 2.4 `cs-state` — subcomandos e flags
| Comando | Contrato |
|---|---|
| `init` | exit 0 num repo com `SD/team.json5` |
| `new epico --title T --objetivo O [--metrica M]` | cria em backlog/epicos/ |
| `new sprint --meta M [--epico EPC-nnn]` | cria (backlog/ ou dentro do épico) |
| `new feature --title T (--sprint SPR-nnn \| --backlog) --aceite <cmd>` | cria fora de state/ |
| `new task --tipo US\|BUG\|FIX --agent A --title T (--feature F \| --sprint S \| --story US-nnn \| --avulsa \| --backlog) --allowed-path P... --verify-cmd C` + US: `--como --quero --para [--criterio 'AC-n\|Dado…Quando…Então…\|<test-id>']...`; BUG: `[--reproducao <test-id>]`; FIX: `[--fixes <id do BUG>] --teste <test-id>` | dois pais (`--feature`+`--sprint`, `--avulsa`+qualquer pai) → exit ≠0 e nada criado |
| `new task --tipo CHORE --agent A --title T <pai> --allowed-path P... --verify-cmd C --motivo M` | manutenção técnica sem valor de usuário: SEM `--como/--quero/--para`; arquivo `<nn>-CHORE-<slug>.json5` com campo `motivo`. DoR (no `check` e no `start`): `motivo` e `verify-cmd` presentes (a falta é listada com as palavras `motivo` / `verify`). `close` roda o verify-cmd de novo e recusa (exit 1, citando o comando) se estiver vermelho |
| `new story --tipo US --title T --feature F --agents a[,b] --como --quero --para --criterio ... --verify-cmd C` | 1 agente → task tipada em `tasks/`; ≥2 → pasta de story, uma task por agente (allowed_paths = território do agente) |
| saída de todo `new` | uma linha por item criado, exatamente `criado <ID> em <caminho relativo ao alvo>` (aceita `criada`) |
| `start <id>` | backlog→state (move a subárvore) ou início de task; confere DoR por tipo (task) |
| `plan <task> --sprint SPR-nnn` | task do backlog → `.../SPR-nnn/tasks/<nn>-...` |
| `move <id> --to <pai>` / `move <id> --avulsa` | troca de pai; recusa sprint→feature e épico→sprint (exit 1, nada move) |
| `park <FEA> --reason R` | feature ativa → backlog/ com motivo |
| `promote <task>` | simples → composta (`stories/<TIPO>-nnn-<slug>/`), MOVE a task, evento cita o id antigo |
| `close <id> --summary S [--devolver --reason R]` | ver §6 da spec; recusa = exit 1 listando o que falta; nada se move |
| `reopen <id> --reason R` | archive → state, mesmo caminho |
| `feature drop --id FEA --reason R` | D-0-12: recusa (exit 1, cita a task/story) se houver task/story em andamento |
| `find <texto>` · `tree` · `board` | exit 0; `tree`/`board` listam os ids do disco |
| `board --json` · `tree --json` | JSON puro no stdout; todo item é um dict com `id` (em qualquer profundidade); no `tree --json` cada item traz `path` (relativo ao alvo, igual ao do `criado`) |
| `close <US\|BUG\|FIX-nnn>` (story composta) | todas as tasks da story fechadas → a pasta da story vai para `archive/<mesmo caminho>` com `closed`; senão exit 1 listando cada task pendente, nada move |
| `check <id>` | SÓ LEITURA. DoR/pré-condições por script: exit 0 pronto; exit 1 listando o que falta (task: US `crit…`, BUG `passa` quando o teste de reprodução já passa, FIX `fixes`; feature: `aceite` quando o teste de aceite já passa). `check` 0 ⇒ `start` passa (mesma regra) |
| `--dry-run` em `new *`, `start`, `close`, `move`, `park`, `reopen`, `promote` | exit 0 e stdout = JSON `{ids: [..], criar: [caminhos], mover: [{id, de, para}], eventos: [..não vazio..]}`; NADA escrito (árvore e events.jsonl iguais por hash). `ids`/`criar` = exatamente o que o `new` real cria; `mover.de` some e `mover.para` passa a existir no comando real. Operação que seria recusada → exit 1 também no dry-run |
| `validate` | exit 0 íntegro; exit 1 com edição à mão (cita arquivo ou id), órfão (cita o nome), fechado em state/ |
| `migrate state-tree` | board plano legado `SD/state/{board.json5,events.jsonl}` → árvore; idempotente; com backup |
| `dispatch <task> --manual --model M`, `submit <task> --files-changed F --check C --risk R --handoff-notes N` (actor = agente), `verify <task>`, `review <task> --by reviewer --verdict PASS --findings X`, `accept <task>`, `escalate <task> --reason R` | os subcomandos de M2 que já existem, aceitando o id da árvore (posicional) |

Códigos: sucesso 0; recusa semântica 1 (mensagem acionável); estado incoerente 2. Exceção: combinações
estruturalmente inválidas no `new` (flag de pai inexistente) aceitam qualquer exit ≠0, desde que nada seja criado.
"Começar" uma task = `cs-state start <task>`: BUG exige `--reproducao` cujo teste FALHA hoje (o motor roda);
FIX exige `fixes`; US exige critério. `close` de FIX exige o teste do BUG verde (a recusa cita o test-id).

### 2.5 Guard
- Escrita de produto sem task em andamento (principal OU subagente) → exit 2 com o texto
  `cs-state new task --tipo FIX --avulsa` na saída.
- Com 1 task avulsa iniciada e despachada: escrita do agente da task dentro do `allowed_path` → exit 0; fora → 2.
- Write/Edit em `SD/{backlog,state,archive}/**` por principal ou subagente → 2; Bash `mv`/`cp`/`rm`/`>` nessas
  zonas → 2.

### 2.6 `cs-session`
- `save` (sem argumentos obrigatórios) imprime ≤2.000 tokens (chars/3,5) com exatamente 8 cabeçalhos, nesta ordem,
  no formato `## N. Título`:
  `1. Fechado nesta sessão` · `2. Frente atual` · `3. Tasks da frente atual` · `4. Em andamento` ·
  `5. Próximos passos` · `6. Backlog imediato` · `7. Decisões e pendências humanas` · `8. Integridade`.
- Nenhum bloco vazio; sem conteúdo → a palavra `nenhum`. Bloco 1 cita os ids fechados e `archive/`; bloco 2 a cadeia
  `SPR-nnn › FEA-nnn` (separador `›`) e o progresso `fechadas/total` (ex.: `2/4`); bloco 3 uma linha por task;
  bloco 4 task e agente da delegação em voo; bloco 7 a task ESCALATED; bloco 8 o HEAD (7 primeiros chars).
- Bloco 5: toda linha é um passo `N. ...` com um comando entre crases começando por `cs-state` ou `cs-session`
  (basename), sem `<` nem `...`; o passo 1 é executável como está.
- Grava `state/sessoes/<timestamp>.json5` com `blocos`: lista de 8 objetos `{titulo, linhas: [str]}`.
- `save --check`: exit 0 íntegro; exit 1 se um passo não tem comando (saída cita `Próximos passos` e `comando`) ou
  se um bloco ficou vazio sem `nenhum` (saída cita o título do bloco e `nenhum`).
- `load`: imprime o carimbo (8 blocos); se o estado mudou desde o save, mostra o delta (cita o item novo).

### 2.7 Upgrade e emit
`upgrade.version.KINDS` contém `state-tree` (fora de `RESERVED_KINDS`); `references/migrations.json5` tem uma
migração com action `{kind: "state-tree"}`; `upgrade/core.py` `ORDER` inclui `"state-tree"`. 

**Skills emitidas** — testadas nos ARTEFATOS: o oráculo grava os dados do fixture de `scripts/emit/tests/fixture.py`
em `SD/` de um alvo temporário e roda `python3 scripts/cs.py --target <alvo> emit --platforms claude-code
--allow-outside` (exit 0); lê `.claude/skills/<nome>/SKILL.md` (frontmatter `---` + corpo).

| Skill | Comando real citado (corpo ou `allowed-tools`) | Invocação |
|---|---|---|
| `board` | `cs-state board` | consulta: model-invocable (sem `disable-model-invocation: true`) |
| `new-epico` `new-sprint` `new-feature` `new-task` `new-story` | `cs-state new <epico\|sprint\|feature\|task\|story>` | criação: model-invocable; mostra antes via `--dry-run` |
| `close-task` `close-feature` `close-sprint` `close-epico` `close-story` | `cs-state close` | mudança de estado: `disable-model-invocation: true` |
| `reopen` `park` `move` | `cs-state reopen` / `park` / `move` | mudança de estado: `disable-model-invocation: true` |

- `name` do frontmatter = nome da pasta.
- Criação "mostra antes" por SCRIPT: no corpo há uma linha com `cs-state new <x> … --dry-run` ANTES da primeira
  linha com `cs-state new <x>` sem `--dry-run` (nada de descrever em prosa).
- `new-task` cita também o tipo `CHORE` e o DoR dele (`--motivo`, `--verify-cmd`).
- `new-task`, `new-story`, `new-feature` citam `cs-state check` (a decisão do DoR é do script; o texto pode listar o
  checklist).
- DoR no texto: `new-epico` cita `--objetivo`; `new-sprint` `--meta`; `new-feature` `--aceite`; `new-task` e
  `new-story` citam `--como --quero --para --criterio --reproducao --fixes --teste`, os tipos `US`, `BUG`, `FIX` e
  as palavras `como`, `quero`, `para`, `critério`, `reprodução`, `fixes`.
- **Skills finas**: corpo (sem frontmatter) com **≤ 40 linhas**, cita o comando do motor, e NÃO contém:
  caminho de zona (`backlog/`, `state/`, `archive/` como segmento de caminho), linha começando por
  `mv|cp|mkdir|rm|touch`, nem cálculo de id (`nn`, `nnn`, `<nn>`, "próximo número"). A política vale para as 14
  skills desta campanha (as de sessão/corrigir/etc. são de outras rodadas).

### 2.8 Migração (MIGRATE-1)
Entrada congelada: `legacy_flat/{board.json5,events.jsonl}` (gerada pelo motor ATUAL: EPIC-1 ACTIVE, FEAT-1
IN_PROGRESS sem sprint, US-1 DONE com T-1 ACCEPTED, US-2 BACKLOG, sessão S-1). Depois de `migrate state-tree`:
`SD/events.jsonl` começa com os bytes do events.jsonl legado e é maior; `SD/state/board.json5` sumiu e há uma cópia
de `board.json5` em algum lugar de `SD/` (backup); um item com `legacy_id` para EPIC-1 (épico em state/), FEAT-1
(feature em state/ dentro de `sprints/SPR-nnn/features/`), US-1 (task `-US-` em archive/), US-2 (task `-US-` em
state/ ou backlog/); `validate` exit 0; 2ª execução exit 0 sem mudar árvore nem eventos. Também roda (ou pula se
ausente) o alvo real `iteration-4/ts-shop-setup-vague/with_skill/target`.

### 2.9 Upgrade de alvo legado: U-1 e U-2 (`test_upgrade_u1_u2.py`)
Origem: achados da medição da iter11 (`campanha-iter11/oraculo/ESPEC.md` §13). Alvos: os 3 da iteration-4
(`py-billing` e `go-polyglot` pausados em `validate` antes de validate.5; `ts-shop` finished com git hook), sempre
COPIADOS para temporário; um `cs.py --target <cópia> upgrade --apply --allow-outside` por alvo.
- **U-1 (pausado)**: upgrade exit 0 sem "backup restaurado"; `run.json5` em `SD/` com `skill_version` = VERSION;
  `cs.py harness selftest` exit 0 (não exige o pre-commit que validate.5 ainda não instalou); "retoma do ponto
  onde parou" = `current_stage`, status de cada etapa e de cada subetapa iguais aos do legado (validate.5 NÃO vira
  `done`), `cs.py stage status` exit 0 citando a etapa, `cs.py stage load <etapa>` exit 0.
- **U-1 anti-atalho (ts-shop finalizado)**: o upgrade reinstala `.git/hooks/pre-commit`; sem ele o selftest fica
  vermelho citando `pre-commit`. (Passa hoje — é guarda de regressão, não requisito novo.)
- **U-2 (os 3 alvos)**: dentro de `SD/backups/` não há nenhum `.git` (dir ou arquivo, inclusive o backup de
  `.git/hooks/pre-commit`, que precisa ser guardado sob outro nome) nem pasta `tmp`; algum `manifest.json5` do
  backup tem `excluded: [caminhos]` com um item cujo segmento é `tmp` e um com segmento `.git`; depois de
  `cs.py sanitize --apply`, `cs.py sanitize --check` exit 0.

## 3. Decisões do escritor do oráculo (para o founder conferir)
1. **Onde mora events.jsonl**: em `SD/events.jsonl` (como o diagrama "Visão geral" da §3), não em `state/` — senão
   `state/` deixaria de ser "só o que executa".
2. **Feature não iniciada fica em backlog/**, mesmo criada com `--sprint` de uma sprint já em state/ ("UMA feature
   ativa por vez em state/" prevalece sobre "cria na sprint"). O lugar exato no backlog é livre.
3. **Feature sem sprint**: o oráculo aceita as duas leituras da §1 (recusa, ou cria a sprint junto) e exige só o
   invariante "feature em state/ sempre dentro de `sprints/SPR-nnn/features/`".
4. **Task avulsa nasce em `state/tasks/`** (Caso D) — é o mínimo da dica do guard; `--backlog` existe para a task
   "esperando" da Visão geral.
5. **"Começar" = `cs-state start <task>`**; é nele que as regras de tipo valem. O oráculo não abre sessão M1
   antes de despachar ("qualquer alteração exige pelo menos uma task — e nada além disso").
6. **Flags dos tipos** em português, como o resto do `new`: `--como/--quero/--para/--criterio`, `--reproducao`,
   `--fixes/--teste`. BUG exige só o teste vermelho (a spec não pede severidade/ambiente).
7. **Ids de task**: `<pai>/<nn>`; como `move`/`promote` mudam o pai, "manter id" = o id antigo continua resolvendo
   por `find` e o histórico (eventos) é preservado. Sprint sem slug (`SPR-nnn`), como nas árvores da §3.
8. **Task fechada dentro de feature vai para archive/ já no `close task`** (§6: "move o arquivo da task"), no mesmo
   caminho relativo; `close feature/sprint` depois leva o resto.
9. **Wave**: campo `wave` no arquivo da task, calculado pelo motor no `start`; colisão (arquivo comum ou par
   `do_not_parallelize`) → a 2ª task fica na wave 2 e o despacho dela com a 1ª em voo é recusado (exit 1 citando a 1ª).
10. **Portão humano pendente** (SESSION-1) = delegação ESCALATED (não terminal, espera decisão).
11. **Formato do carimbo**: cabeçalhos `## N. Título` com os títulos da §8; arquivo de sessão com `blocos`
    (`titulo`, `linhas`) para o `--check` poder ser provado contra corrupção.
12. **D-0-12 na árvore**: continua sendo `cs-state feature drop --id FEA-nnn --reason`; "em andamento" = task
    simples iniciada/despachada ou task de story composta iniciada. Sem nada em andamento o drop passa e a feature
    sai de state/ (destino livre).
13. **Migração**: comando de motor `cs-state migrate state-tree` (o `cs.py upgrade` chama pela action
    `kind: state-tree`). Legado = `SD/state/board.json5` (onde fica depois do rename da iter9). Feature legada sem
    sprint ganha uma sprint na migração (toda feature mora numa sprint).
14. **`close <story>`** (não estava na §10): fecha a story composta só com todas as tasks fechadas, recusa
    listando as pendentes, move a pasta da story para archive/ no mesmo caminho (coerente com §6).
15. **Automação mecânica** (pedido do founder, 2026-10-04): `--dry-run` com JSON de chaves fixas
    `ids/criar/mover/eventos`; `cs-state check <id>` como o nome do verificador de DoR; `board/tree --json`;
    limite de 40 linhas por corpo de skill. O `find` não ganhou skill (não exigido).
16. **CHORE adotado** (sugestão registrada; pedido de fechar pendências): tipo `CHORE`, só em task (não em story
    composta); `close` reconfere o verify-cmd porque não há teste de aceite/BUG que prove a manutenção.
17. **U-1/U-2**: "retomar" é provado pelo `run.json5` preservado + `stage status`/`stage load` (não pela
    execução da etapa, que exige LLM); `excluded` é o nome do campo novo no `manifest.json5` que o backup já grava.
18. **Fora do oráculo** (não testado aqui): inferência pela triagem (§5), `amend` de épico/feature, `depends_on`.
