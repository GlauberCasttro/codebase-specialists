# harness-evolucao — Harness do produto que classifica, decompõe, fecha, arquiva, persiste em JSON e aprende com correções

FEATURE-ID: harness-evolucao
Nome: Evolução do harness do produto — classificação, ciclo de vida, JSON, memória e aprendizado por correção

## História
Como founder que usa o harness gerado nos alvos, quero que ele classifique a demanda, monte só a estrutura que ela
precisa (épico → sprint → feature → task ou task avulsa), feche e reabra a hierarquia sozinho com validação, persista
tudo em JSON legível, crie e use as memórias do projeto e de cada agente e transforme cada `correct` num aprendizado
com escopo, para que o trabalho dos agentes seja rastreável, confiável e não repita erros já corrigidos.

## Problema / Contexto
Levantamento verificado (E2; `local/levantamento-evolucao-harness/`): de 132 requisitos da demanda, 22 EXISTEM, 52
são PARCIAIS, 50 FALTAM e 8 DIVERGEM do desenho; 22 achados crítico/alto confirmados por verificador independente.
- Classificação é palpite do modelo e não há classe épico (`scripts/harness/machines.json5:10`); os textos mandam o
  modelo para o board legado, onde o épico criado fica invisível (`assets/templates/orchestrator.md:61`).
- Fechar o último filho não fecha o pai (`scripts/harness/engine/tree.py:922`); reabrir com pai fechado é recusado
  (`tree.py:1052`); task reaberta fecha sem validação (`tree.py:896`); `--devolver` pula o aceite (`tree.py:947`);
  pais sem filhos fecham (`tree.py:989`).
- Estado em JSON5 compacto que nenhuma ferramenta JSON lê (`scripts/cslib/json5io.py:285`); renomear para `.json`
  quebra o `validate` porque o caminho vive nos eventos encadeados (`tree.py:25`).
- `init` não cria memória (`scripts/harness/install.py:355`); `--agent` duplicado fura o isolamento
  (`scripts/harness/engine/guard.py:261`); `correct` grava segredos em claro (`scripts/memory/mem.py:955`), não tem
  escopo nem reexecução (`assets/templates/correct.md:5`); lição promovida some (`mem.py:858`); correção contraditória
  se perde (`mem.py:910`); nada prova consulta ou uso (`scripts/harness/engine/engine.py:929`).
- Sem relatório final fora do mandato M5 (`scripts/harness/engine/auto.py:2908`); no Windows nativo nenhum verify
  roda (`engine.py:109`, `/bin/sh` fixo).
Decisões travadas na E1 (aprovação delegada do founder): (1) JSON5 → JSON revoga o §8-decies para documentos de estado,
itens, memória e config do harness, JSONL mantido, migração pelo motor em 2 passos; (2) `correct` com
`--scope agent|project|execution`, revoga o §8-duodecies; (3) propagação automática só com o aceite do pai verde, senão
"pronto para fechar", reabertura em cascata automática; fronteiras: casos B/C e story mantidos, épico proposto por
script e confirmado pelo humano.

## Valor de negócio
O harness é a promessa central do produto: cada alvo recebe um time que trabalha com rastreabilidade. Hoje o ciclo não
fecha sozinho, o estado não é legível por ferramentas, a memória não nasce e o aprendizado vaza segredo e se perde.
Esta feature torna o fluxo épico-a-task confiável de ponta a ponta e auditável, e remove dois riscos de segurança
(segredo em claro e escrita na memória de outro agente).

## Personas / Stakeholders
- founder (dono do produto; aprova a decomposição e o oráculo com a senha)
- dev do alvo que usa o harness (lê o estado, faz `correct`, confirma o épico proposto)
- agentes derivados do alvo (consultam memória, recebem lições, são isolados entre si)
- orquestrador do alvo (classifica, decompõe, fecha e reabre pelo motor)

## Critérios de Aceitação
- **CA-01 — Segredo nunca é gravado.** DADO um `cs-mem correct` ou `cs-mem add` cujo texto contém token (ghp_, gho_,
  github_pat_, AKIA…, xox[bp]-, Bearer/Authorization, chave privada PEM, JWT, `password|secret|token|api_key=valor`),
  QUANDO a lição é gravada, ENTÃO o arquivo do agente, a memória do projeto, o índice de busca e a saída de
  inject/search contêm `[REDACTED:<tipo>]` no lugar do segredo e a saída do comando informa quantos trechos redigiu.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA01`
- **CA-02 — Um agente não escreve na memória de outro.** DADO um subagente X, QUANDO ele roda `cs-mem add|correct` com
  `--agent` repetido (inclusive `--agent=`) ou com um agente que não está no `team.json5` (nem `lead`), ENTÃO o guard
  recusa (exit 2) e o próprio `cs-mem` recusa (exit 1) sem gravar nada.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA02`
- **CA-03 — O init cria e repara as memórias.** DADO um alvo com N agentes no `team.json5` e sem memória, QUANDO roda
  `cs.py harness install` (e de novo depois de apagar um arquivo), ENTÃO existem a memória do projeto (knowledge e
  episodes, vazios e válidos) e a memória de cada agente, o ledger registra `memory_init {created, repaired, kept}`, a
  permissão de escrita é testada, a segunda execução recria só o que faltava e nenhum arquivo existente muda de sha;
  arquivo de memória ilegível gera recusa com backup em `.swarm/backups/memory/`, nunca sobrescrita.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA03`
- **CA-04 — correct com escopo e registro completo.** DADO um `cs-mem correct --scope agent|project|execution --task
  <id>`, QUANDO é registrado, ENTÃO `agent` grava na memória do agente, `project` grava na memória do projeto (kind
  rule/decision, source correct) e `execution` grava só no histórico da task (nunca na memória global nem no índice);
  o registro tem id, scope, agent, project, taskId, originalRequest (copiado da task), incorrectBehavior, correction,
  expectedBehavior, createdAt ISO-8601, source "correct", status "active", confidence e applicationCount; e o motor
  grava o evento `lesson.recorded` no ledger.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA04`
- **CA-05 — Correção contraditória substitui; promovida continua valendo.** DADO uma lição ativa, QUANDO chega uma
  correção com wrong/right invertidos, ENTÃO nasce uma lição nova com `supersedes`, a antiga vira `superseded` (fora do
  inject) com histórico, e nada é promovido; DADO uma lição com count ≥ 2 ainda não aplicada ao cartão, QUANDO roda
  inject ou search, ENTÃO ela continua aparecendo.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA05`
- **CA-06 — Consulta e uso da memória comprovados.** DADO uma task cujo brief injetou lições, QUANDO o subagente
  inicia e depois submete, ENTÃO o ledger tem `memory_injected {task, agent, lesson_ids, hit_ids, omitted}`, a
  submissão sem `lessons_checked` é recusada e cada lição marcada como checada incrementa `applicationCount`.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA06`
- **CA-07 — Classificação por script com justificativa.** DADO os sinais de uma demanda (territórios/domínios, nº de
  entregas, dependências, paralelização, duração, nº estimado de features e tasks, invariantes tocados), QUANDO roda
  `cs-state classify`, ENTÃO devolve a estrutura proposta (avulsa | feature | epico) com a justificativa e os sinais
  gravados em evento; `session triage --class epico` é aceito; e o épico criado a partir dela guarda
  `classificacao {classe, why, sinais}`.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA07`
- **CA-08 — Um caminho só: a árvore.** DADO um alvo em modo árvore, QUANDO o modelo segue os textos emitidos
  (orquestrador, processo de produto, plan-sprint, `next`, `references/harness.md`), ENTÃO nenhum deles manda usar
  `add epic|feature|story`, `sprint plan` ou `add task --quick`; e esses comandos, em modo árvore, recusam com a
  instrução do comando equivalente da árvore, sem criar item invisível.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA08`
- **CA-09 — Task avulsa só quando é pequena e completa.** DADO `new task --avulsa`, QUANDO ela toca invariante escopada,
  área congelada ou mais de um território, ENTÃO é recusada com "suba para estruturado"; DADO uma avulsa válida, QUANDO
  executada, ENTÃO tem status, ≥ 1 critério de aceite (inclusive CHORE), histórico com tentativas e correções, e fecha e
  arquiva sozinha sem criar épico, sprint ou feature.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA09`
- **CA-10 — Cardinalidade.** DADO um épico, sprint ou feature sem nenhum filho, QUANDO roda `close`, ENTÃO recusa; DADO o
  fluxo de épico (sprint com `--epico`), QUANDO uma sprint sem feature ou uma feature sem task tenta fechar, ENTÃO
  recusa; fora do fluxo de épico, os casos B (sprint → feature) e C (sprint → task) continuam válidos.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA10`
- **CA-11 — Dependências, critérios e datas em todo nível.** DADO `new task|feature|sprint --depends-on <id>`, QUANDO o
  dependente tenta `start` com a dependência aberta, ENTÃO recusa (ciclo também recusado); DADO `new epico|sprint
  --aceite <comando>`, QUANDO fecha, ENTÃO o aceite roda e vermelho recusa; e todo item tem `updated_at` e `status`
  persistidos.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA11`
- **CA-12 — Fechamento propaga.** DADO uma feature cuja última task aberta é fechada, QUANDO o aceite da feature passa,
  ENTÃO a feature fecha sozinha (evento `close {auto: true, gatilho}`), e o mesmo sobe para sprint e épico; QUANDO o
  aceite do pai falha, ENTÃO o pai fica "pronto para fechar" no histórico e o `next` mostra.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA12`
- **CA-13 — Reabertura em cascata.** DADO uma task arquivada cujos pais estão fechados, QUANDO roda `reopen <task>
  --reason`, ENTÃO feature, sprint e épico voltam para em andamento no mesmo evento, cada um com o motivo e `cascata_de`,
  só os afetados saem do archive, outra feature ativa é estacionada com motivo e o `validate` passa.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA13`
- **CA-14 — Nada fecha sem validação.** DADO uma task reaberta, QUANDO roda `close` sem nova M2 ACCEPTED, ENTÃO recusa;
  DADO `close <feature> --devolver`, QUANDO o aceite está vermelho, ENTÃO recusa; DADO item do backlog nunca iniciado,
  QUANDO roda `close`, ENTÃO recusa e aponta `drop`; DADO `feature drop`, ENTÃO as tasks não feitas ficam como
  descartadas (não fechadas); e a task reaberta aparece como reaberta no board.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA14`
- **CA-15 — Comandos rodam no Windows nativo.** DADO o Windows sem `/bin/sh`, QUANDO o motor roda verify, aceite,
  selftest ou `cs-mem check`, ENTÃO o comando executa com o exit real (127 só se o programa não existe) e o DoR da
  feature não aceita 127 como "aceite vermelho".
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA15`
- **CA-16 — Relatório final sem mandato.** DADO um épico (ou uma janela de eventos) executado fora do modo autônomo,
  QUANDO roda `cs-state report [--epico ID]`, ENTÃO sai um relatório só leitura com cenários, itens criados, estrutura,
  resultados de testes, falhas, correções, retestes, aprendizado, memória atualizada, não resolvidos e evidências
  (comandos, sha das saídas, ids de evento).
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA16`
- **CA-17 — Autocorreção com causa e limite.** DADO uma task que falha no verify, QUANDO roda `retry`, ENTÃO exige
  `--esperado --obtido --causa --correcao` estruturados; a lição de falha só é gravada no ACCEPTED pós-falha e guarda a
  causa e a correção (falha de ambiente não vira lição); ao esgotar 3 tentativas a task vai para ESCALATED
  automaticamente e entra no relatório como não resolvida; `max_attempts` = `max_retries` + 1 é conferido.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA17`
- **CA-18 — Estado do harness em JSON legível e válido.** DADO qualquer documento de estado, item de trabalho, memória,
  sessão ou config gravado pelo harness, QUANDO é salvo, ENTÃO é `.json` válido (`json.loads`), indent 2, uma
  propriedade por linha, UTF-8 com `\n` final, validado por roundtrip antes do replace atômico e com `formatVersion`;
  JSONL (events, ledger, knowledge, episodes) segue igual; e arquivos `.json5` legados continuam legíveis.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA18`
- **CA-19 — Migração JSON5 → JSON segura.** DADO um alvo 0.10.0 com estado em JSON5, QUANDO o init/install detecta e o
  `cs.py upgrade --apply` roda, ENTÃO há backup, cada arquivo é convertido e validado, o original só sai depois do
  sucesso, o caminho dos itens é reescrito por evento do motor (cadeia de hash íntegra), o registro lista arquivo a
  arquivo, o `validate` passa, uma segunda execução não muda nada, e uma falha no meio restaura o estado anterior.
  Prova: `python -m unittest discover -s campanhas/harness-evolucao/oraculo -p "test_*.py" -k CA19`

## RNFs
- RNF-01: Python 3.9+ stdlib; verde em `python3` e `/usr/bin/python3` (o portão roda os dois) e no Windows nativo.
- RNF-02: nenhum `def` removido (o portão confere): os 4 escritores JSON5 viram fachada do gravador único.
- RNF-03: nenhum segredo, token ou dado pessoal em memória, ledger, relatório ou fixture (pessoa = "Ana").
- RNF-04: escrita de estado só pelo motor (guards fail-closed preservados); cadeia de hash do `events.jsonl` íntegra.
- RNF-05: o motor instalado no alvo continua autocontido (sem depender de `scripts/cslib` no alvo).

## Edge cases
- alvo meio migrado com `x.json` e `x.json5` do mesmo item: `.json` vence e o `validate` aponta o duplicado.
- motor antigo num alvo já migrado: o upgrade reinstala o motor antes de converter.
- reopen em cascata com outra feature ativa: a ativa é estacionada com motivo, nunca duas ativas.
- correct sem `--task` com `--scope execution`: recusa.
- token partido em duas linhas ou dentro de JSON aninhado: redigido mesmo assim.
- aceite do pai que dá 127 (comando inexistente): não conta como vermelho nem como verde; vira erro de ambiente.
- 3 tentativas esgotadas por falha de ambiente: não grava lição, escala com `failure_kind: env`.

## Dependências
- `win-harness` (ativa, escopo `.claude/**`): disjunta desta (escopo em `scripts/`, `assets/`, `references/`, `docs/`);
  colisão será provada por `ac.py overlap` na abertura.
- B-14 (Produto no Windows): esta feature absorve só a parte do shell do motor (`/bin/sh` em engine, selftest e mem);
  o resto do B-14 segue no BACKLOG.
- Oráculos congelados de campanhas anteriores que comparam `.json5` por nome ou o board legado: só por mudança oficial
  (`campanha.py mudanca-oficial` com PORQUE), nunca editados.

## Escopo IN
- harness do produto: motor (`scripts/harness/engine/`), máquinas, install, memória (`scripts/memory/`), gravador e
  leitor JSON (`scripts/cslib/`, `engine/j5.py`, `hcore.py`), upgrade e migrações, templates emitidos do harness,
  `references/harness.md`, `references/ARCHITECTURE.md` (§8-decies, §8-duodecies, §8-septies), docs do harness.
- testes novos do produto para árvore, memória, JSON e migração.

## Escopo OUT
- `.claude/` (harness de desenvolvimento) e `.claude/tools/ac/` (motor embutido).
- artefatos do PIPELINE da skill gravados no alvo fora do harness (facts, team, knowledge/maps, panel, probes,
  `run.json5`, manifest do emit): continuam JSON5 nesta feature (lidos pelo harness, não gravados por ele).
- estrutura `.harness/` e agentes fixos da demanda (conceituais); `.swarm/` e agentes derivados ficam.
- senha do mandato (D-04/D-05), `approve`, publicação, push, bump de versão (é do `/package`).
- o resto do B-14 (pty/termios nos testes, symlink, lock por fcntl).

## Escopo de escrita
- `scripts/memory/mem.py`
- `scripts/memory/cli.py`
- `scripts/memory/tests/test_evolucao_memoria.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/engine/brief.py`
- `scripts/harness/install.py`
- `assets/templates/correct.md`
- `assets/templates/memory.md`
- `docs/03-memoria-e-licoes.md`
- `scripts/harness/engine/tree.py`
- `scripts/harness/engine/state.py`
- `scripts/harness/engine/engine.py`
- `scripts/harness/engine/cmds.py`
- `scripts/harness/engine/views.py`
- `scripts/harness/engine/auto.py`
- `scripts/harness/engine/session.py`
- `scripts/harness/engine/autonomy.py`
- `scripts/harness/engine/selftest.py`
- `scripts/harness/engine/classify.py`
- `scripts/harness/engine/report.py`
- `scripts/harness/machines.json5`
- `scripts/harness/tests/test_evolucao_arvore.py`
- `scripts/emit/platforms.py`
- `scripts/emit/render.py`
- `assets/templates/orchestrator.md`
- `assets/templates/plan-sprint.md`
- `assets/templates/product-process.md`
- `assets/templates/state/*.md`
- `references/harness.md`
- `docs/02-harness.md`
- `docs/10-arvore-de-estado.md`
- `scripts/cslib/json5io.py`
- `scripts/cslib/jsonio.py`
- `scripts/cslib/README.md`
- `scripts/cslib/tests/test_jsonio_formato.py`
- `scripts/harness/engine/j5.py`
- `scripts/harness/engine/hcore.py`
- `scripts/emit/j5.py`
- `scripts/upgrade/core.py`
- `scripts/upgrade/tests/test_json_format.py`
- `scripts/cs.py`
- `references/migrations.json5`
- `references/ARCHITECTURE.md`
- `docs/09-upgrade.md`

## Critério de parada
oráculo da feature 19/19 CAs verde no Windows nativo e no WSL; suítes do produto com 0 falhas e 0 erros no WSL em
python3 e /usr/bin/python3; no Windows nativo, 0 falhas por `/bin/sh` (WinError 2 ou exit 127); oráculos das campanhas
anteriores verdes ou com mudança oficial registrada; 0 `def` removido; no máximo 3 tentativas por falha antes de
escalar ao founder.

## Métrica de sucesso
Roteiro de 23 passos da demanda: de 10 PASSA / 11 FALHA / 1 IMPOSSÍVEL / 3 MANUAL (hoje, WSL) para ≥ 21 PASSA, 0 FALHA,
0 IMPOSSÍVEL (os passos 18 e 21 mantêm só a parte de LLM como manual). Matriz da demanda: de 22 para ≥ 120 dos 132
requisitos em EXISTE, os demais como DIVERGE documentado.

## Aceite da Feature
### Aceite QA — PENDENTE
### Aceite Review — PENDENTE
