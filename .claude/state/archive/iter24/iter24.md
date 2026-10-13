# iter24 — Hotfix de segurança do guard do harness gerado — fechar as portas confirmadas pela auditoria da cobaia (B-44, B-45, B-46, B-47)

## Resumo
Hotfix de segurança 0.12.2 do guard do harness gerado (B-44..B-47): fecha as portas que a auditoria da cobaia .NET
confirmou (F1–F8). Harness chamado por caminho indireto (`sh|bash`, `python3 -m`, `-W/-X`, `cd .swarm/harness`, caminho
por variável/`~` normalizado), hardlink de protegido (`ln`/`cp -l` e escrita por hardlink preexistente), registros
humanos (approvals.jsonl, team-approvals.jsonl, acceptance.json5, run.json5, team.json5) não graváveis pelo agente,
escritores com flag de saída (git --output, curl -o, wget -O, tar -C, unzip -d, dotnet -o), inline/stdin fail-closed,
e git que desliga proteção (core.hooksPath, --no-verify e abreviações, push forçado/refspec `+`/protegido, branch -D
em protegida, remote set-url|add, reflog expire). Oráculo 9/22 → 22/22 nos 2 Pythons; oráculos iter16..iter22 verdes.

## Critérios de aceite
### CA-01 — harness só pelo caminho direto
DADO um subagente com delegação ativa e o agente principal, QUANDO
  chamam o cs-state/cs-auto por `sh|bash <script>`, `python3 -m state|auto`, `python3 -W|-X <v> …/state.py` ou
  `cd .swarm/harness && python3 …`, ENTÃO o guard aplica as MESMAS regras do caminho direto (ato humano recusado a
  ambos; ato do principal recusado ao subagente; submit/review alheio recusado); e `bash scripts/build.sh` (script que
  não é do harness) segue como hoje.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA01`

### CA-02 — hardlink não fura a proteção
DADO um subagente com delegação ativa, QUANDO roda `ln <protegido>
  <allowed_path>` ou `cp -l …`, ou escreve (Write/Edit/redirect) num arquivo do próprio allowed_path que é hardlink de
  arquivo protegido, ENTÃO o guard recusa e o arquivo protegido fica intacto.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA02`

### CA-03 — registros humanos não são graváveis pelo agente
DADO o agente principal (e o subagente), QUANDO tenta
  escrever por Write/Edit/MultiEdit ou redirect em `.swarm/approvals.jsonl`, `.swarm/team-approvals.jsonl`,
  `.swarm/acceptance.json5`, `.swarm/run.json5` ou `.swarm/team.json5`, ENTÃO o guard recusa; o motor e os comandos
  humanos que os gravam continuam funcionando.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA03`

### CA-04 — escritores com flag de saída
DADO um alvo protegido, QUANDO o comando é `git diff|show|log --output=X`,
  `curl -o X`, `wget -O X`, `tar -C X`, `unzip -d X` ou `dotnet … -o X`, ENTÃO X é conferido como destino de escrita
  (protegido ⇒ recusa; permitido ⇒ passa).
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA04`

### CA-05 — inline e stdin fail-closed
DADO um interpretador com código inline por flags combinadas (`-Sc`, `-Ic`,
  `-uc`, `-ne`, `-pe`) ou lendo de stdin (`-`, `/dev/stdin`, `| sh -`), QUANDO o guard analisa, ENTÃO recusa como já
  recusa `python3 -c`; script de arquivo dentro do projeto segue como hoje.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA05`

### CA-06 — git não desliga proteção nem reescreve remoto protegido
DADO o principal e o subagente, QUANDO rodam
  `git config core.hooksPath …` (ou `-c core.hooksPath`), push para branch protegida por refspec (`HEAD:main`,
  `+x:main`, `:master`), `push -f|--force|--delete|--mirror`, `commit --no-verify|-n`, `branch -D|-f` em branch
  protegida, `remote set-url|add`, `reflog expire`, ENTÃO o guard recusa (subagente: todo git não-leitura como hoje);
  leituras de git (status/log/diff sem --output/show) seguem liberadas.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA06`

### CA-07 — 0.12.2 chega aos alvos sem regressão
DADO um alvo 0.12.1, QUANDO roda `cs.py upgrade` e
  `upgrade --apply --allow-outside`, ENTÃO o plano lista 0.12.2 (harness), o apply reinstala o guard e as portas de
  CA-01..CA-06 ficam fechadas no alvo; VERSION 0.12.2 com a migração no catálogo; oráculos iter16..iter22 inteiros verdes.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA07`

## Linha do tempo
- 2026-10-12T15:42:21-0300 · inicio E0
- 2026-10-12T15:42:40-0300 · proposta E1
- 2026-10-12T15:43:00-0300 · aprovacao E1
- 2026-10-12T15:43:28-0300 · proposta E2
- 2026-10-12T15:44:09-0300 · aprovacao E2
- 2026-10-12T15:44:49-0300 · proposta E3
- 2026-10-12T15:45:50-0300 · aprovacao E3
- 2026-10-12T15:45:50-0300 · proposta E4
- 2026-10-12T15:46:40-0300 · aprovacao E4
- 2026-10-12T15:46:41-0300 · proposta E5
- 2026-10-12T15:47:22-0300 · aprovacao E5
- 2026-10-12T16:58:55-0300 · abertura abertura
- [NOTA] 2026-10-12T16:58:55-0300 — Abertura da feature iter24
- [NOTA] 01-TASK-ORACULO — 2026-10-12T16:59:00-0300
- [PASS] 01-TASK-ORACULO — 2026-10-12T17:11:21-0300
- [NOTA] 02-TASK-GUARD-PORTAS — 2026-10-12T17:15:50-0300
- [NOTA] 03-TASK-VERSAO — 2026-10-12T17:15:50-0300
- [PASS] 02-TASK-GUARD-PORTAS — 2026-10-12T18:02:36-0300
- [PASS] 03-TASK-VERSAO — 2026-10-12T18:02:36-0300
- [NOTA] 04-TASK-QA — 2026-10-12T18:02:47-0300
- [PASS] 04-TASK-QA — 2026-10-12T18:45:28-0300
- [NOTA] 05-TASK-REVIEW — 2026-10-12T18:45:33-0300
- [REJECT] 02-TASK-GUARD-PORTAS — 2026-10-12T18:49:19-0300
- [REJECT] 02-TASK-GUARD-PORTAS — 2026-10-12T18:53:40-0300
- [PASS] 02-TASK-GUARD-PORTAS — 2026-10-12T19:45:16-0300
- [PASS] 05-TASK-REVIEW — 2026-10-12T19:48:55-0300

## Tasks
| id | entrega | tipo | grupo | status | gate |
|---|---|---|---|---|---|
| 01-TASK-ORACULO | Oráculo da iter24 (CA-01..CA-07), escrito por agente separado | ORACULO | — | DONE | PASS |
| 02-TASK-GUARD-PORTAS | fechar as portas do guard (harness indireto, hardlink, registros humanos, saída, inline, git) | CORRECAO | G1 | DONE | PASS |
| 03-TASK-VERSAO | 0.12.2 com migração no catálogo e nota de upgrade | CORRECAO | G2 | DONE | PASS |
| 04-TASK-QA | Portão e oráculos, CA a CA | QA | — | DONE | PASS |
| 05-TASK-REVIEW | Revisão isolada da feature (segurança) | REVIEW | — | DONE | PASS |

### Handoff 01-TASK-ORACULO
- Executor: rh-oraculista-01-TASK-ORACULO-1 (general-purpose, opus), agente separado (não leu local/work).
- Entregue: ESPEC.md, test_iter24.py (22 testes: 13 D, 9 R de controle do caminho legítimo), medir.py, base.txt.
  Fixture: alvo instalado, hook real pre-bash/pre-write, subagente com delegação DISPATCHED (US avulsa de dev-billing).
- Ciclo 2 (pedido do tech-lead): a fixture não resolvia o temporário; com TMPDIR /var/folders (symlink) a base dava
  11/22 com D passando pelo motivo errado. Corrigido com realpath; defeito de produto registrado como B-53.
- Medido pelo tech-lead no HEAD da30e17: 9/22 (D 0/13, R 9/9) em python3 3.13 e /usr/bin/python3 3.9 (oraculista:
  idem com TMPDIR padrão e com o scratchpad). Calibração: mutação mínima ⇒ 12/22, R verdes; a correção parcial NÃO
  satisfaz o D do principal no CA-06. Congelado: `oracle freeze` 37f3042c76ae (4 arquivos).
- Lacunas declaradas: `dotnet -o` sem teste; MultiEdit não coberto; CA-07 confere só a porta do CA-01 depois do
  upgrade; os D afirmam só o exit 2 (os R protegem contra "bloquear tudo").

### Handoff 02-TASK-GUARD-PORTAS
- Executor: Claude Code · general-purpose · model sonnet (ciclo 1) + executor novo sonnet para o ajuste de test_guards.py:57 (decisão do founder, opção 1).
- Arquivos (cópia local/work/iter24): scripts/harness/engine/{bashscan,guard,hcore,auto}.py; scripts/harness/tests/test_iter24_guard.py (novo, 12 testes); scripts/harness/tests/test_guards.py (team.json5 espera 2; .swarm/knowledge/notas-da-ana.md espera 0).
- RED: oráculo CA01..06 19 testes, 11 falhas (exit 0 em vez de 2). GREEN: oráculo test_iter24 inteiro 22 OK em python3 e /usr/bin/python3.
- Régua completa (tech-lead, 17 suítes × 2 Pythons): VERDE; harness 384 OK (16 skips pré-existentes) nos 2.
- Escopo por snapshot: só arquivos permitidos; projeto vivo intocado pelo executor. Privacidade: 0 achados.
- Revisor: instância isolada general-purpose · opus · APPROVED, sem findings; ~40 variantes de bypass sondadas e recusadas. Independência: instâncias distintas.
- Limites: hardlink detectado só sob prefixos literais de `protected`/HUMAN_RECORDS; refspec cobre main/master e refs/heads/…; efeito colateral: subagente não cria branch nem `git config <k> <v>`. Script auxiliar do executor em local/work/iter24/run_or.sh (fora do produto).
- Ciclo 2 (05-REVIEW CHANGES_REQUESTED): executor novo opus — `$PWD/~` no caminho do harness, refspec `+`, abreviações `--no-veri/--forc/--mi/--de` (_long_abbrev). Revisor pontual opus: CHANGES_REQUESTED (`$PWD/.swarm//harness`, `/./`).
- Ciclo 3: executor novo opus — normpath antes do regex; `.swarm` expansível não resolvido ⇒ inanalisável; `--` encerra opções no commit. Revisor pontual opus: APPROVED (MENOR: `.SWARM` maiúsculo e variável opaca pré-existentes; `$PWD/.swarm/knowledge/x.py` inanalisável).
- Portão do ciclo 3 (local/portao-iter24/portao.out): RESULTADO VERDE + FIM; 17 suítes × 3.13/3.9.6; oráculos iter24 22, iter16 48, iter18 38, iter19 39, iter20 24, iter21 64, iter22 9 OK nos 2; 0 FAIL/ERROR.

### Handoff 03-TASK-VERSAO
- Executor: Claude Code · general-purpose · model sonnet.
- Arquivos (cópia): VERSION 0.12.2; README "Versão: **0.12.2**"; references/migrations.json5 (version 0.12.2 + uma entrada to 0.12.2 ação harness); docs/09-upgrade.md (seção "Migração 0.12.2").
- TestCA07: 3 OK nos 2 Pythons depois do guard (task 02); oráculo inteiro 22 OK. Régua completa VERDE (upgrade 23 OK/7 skip, doctests 19 OK) nos 2.
- Escopo por snapshot: só os 4 arquivos. Privacidade: 0.
- Revisor: instância isolada general-purpose · sonnet · APPROVED. Ressalva MENOR: o texto diz "branch -D" sem "de branch protegida" (para o principal só a protegida é recusada).
- Limites: RED não foi rodado antes da edição (executor declarou); a falha anterior era trivialmente VERSION 0.12.1.

### Handoff 04-TASK-QA
- QA: Claude Code · general-purpose · model sonnet · ACCEPT. Não escreveu (snapshot da cópia e do vivo).
- Portão: local/portao-iter24/portao.out → RESULTADO: VERDE, FIM; 17 suítes × 2 Pythons; oráculos iter24 (22), iter16 (48), iter18 (38), iter19 (39), iter20 (24), iter21 (64), iter22 (9) OK nos 2.
- oracle verify: intacto. Matriz CA-01..CA-07 PASS no FEATURE.md (Aceite QA).
- Limites: o portão mede suítes/oráculos/def, não uso real; matriz por teste vem de execução -v em python3.
- Re-QA após ciclo 3 da 02: sonnet · ACCEPT; portão do ciclo 3 VERDE; test_iter24 22 e test_iter24_guard 17 OK nos 2 Pythons; oracle verify intacto.

### Handoff 05-TASK-REVIEW
- Rodada 1: Claude Code · general-purpose · opus · CHANGES_REQUESTED (3 BLOQUEANTE confirmados e reproduzidos pelo tech-lead) ⇒ 02 reaberta (ciclos 2–3).
- Rodada 2: instância nova general-purpose · opus · APPROVED; matriz CA-01..07 PASS no FEATURE.md (Aceite Review). Não escreveu (snapshot).
- MENOR ao founder: force-with-lease em branch não protegida bloqueado; custo do hardlink com padrão `**`; `feature/x:MAIN` (case).

## Como a feature nasceu
### E0 — Pré-condição · CONCLUÍDA 2026-10-12T15:42:21-0300
- Demanda: "hotfix de segurança do guard (B-44, B-45, B-47) antes da iter23"
- Próxima: E1 — Analisar a demanda

### E1 — Analisar a demanda · CONCLUÍDA 2026-10-12T15:43:00-0300
- Produzido: problema enunciado; FEATURE-ID iter24
- Itens aprovados: 1: B-46 entra; 2: recusar harness por forma indireta + inline/stdin fail-closed; 3: troca de branch fica fora
- Aprovação: "ok"
- Sha: e608f9cc630beb9a616b959ba273651045cfb991038dd70ce3fe98a93db10613
- Próxima: E2 — investigação medida

### E2 — Investigação medida · CONCLUÍDA 2026-10-12T15:44:09-0300
- Produzido: investigação F1–F9
- Medido: 8 portas confirmadas às cegas; 0 oráculos/testes cobrem essas formas
- Aprovação: "ok"
- Sha: e58555f43b9f7db380fa1219e2f65f8ff683c84c04a9f59594282b7603150cc9
- Próxima: E3 — FEATURE.md

### E3 — FEATURE.md (Bloco A) · CONCLUÍDA 2026-10-12T15:45:50-0300
- Produzido: FEATURE.md (7 CAs, contrato PASS)
- Aprovação: "ok"
- Sha: 5d91513f4ffcb75bcf584ec87220ff1f85b4e311950653de7df8f6a1e4525967
- Próxima: E4 — tasks

### E4 — Tasks (Bloco B) · CONCLUÍDA 2026-10-12T15:46:40-0300
- Produzido: 5 tasks (ORACULO, 2 CORRECAO G1/G2, QA, REVIEW)
- Aprovação: "ok"
- Sha: fd5ae1e76bf9ec796638c19a6c3a4ec90b53c2fb4f249c84469f73cb134e4e16
- Próxima: E5 — abertura

### E5 — Abertura · CONCLUÍDA 2026-10-12T15:47:22-0300
- Produzido: plano de abertura (após fechar iter22)
- Aprovação: "ok"
- Sha: d99d9b717f88e5521256676adeb5ed8f93cd5ca84ea9c5aca1536877ca87e376
- Próxima: abrir após /fechar-feature da iter22; oráculo por agente separado

### Abertura · 2026-10-12T16:58:55-0300
- Campanha: campanhas/iter24
- Tasks: 5 · primeira: 01-TASK-ORACULO
- Próxima: oráculo pelo agente separado → oracle freeze → script-aprovacao.sh (founder)

## Campanha
- campanha: campanhas/iter24 · etapa do motor: concluida · rodada: 0
- critério de parada: Oráculo iter24 100% verde (CA-01..CA-07) em python3 e /usr/bin/python3; oráculos iter16, iter18, iter19, iter20, iter21 e iter22 inteiros verdes; suítes do produto e harness-dev verdes; 0 `def` removido; VERSION 0.12.2.
- escopo: scripts/harness/engine/bashscan.py, scripts/harness/engine/guard.py, scripts/harness/engine/hcore.py, scripts/harness/engine/auto.py, scripts/harness/tests/test_iter24_*.py, references/migrations.json5, docs/09-upgrade.md, VERSION, README.md

## Oráculo
- `campanhas/iter24/oraculo/ESPEC.md`
- `campanhas/iter24/oraculo/test_iter24.py`
- `campanhas/iter24/oraculo/medir.py`
- `campanhas/iter24/oraculo/base.txt`

## Decisões técnicas
- HUMAN_RECORDS e `hardlink_of_protected` ficam em código (hcore), não no DEFAULT_CONFIG: valem em alvos com config
  antiga e não afetam o check-diff.
- `git_effect(sub, args=None)`: assinatura antiga preservada; branch/remote/config/reflog mutáveis contam como "lead"
  (subagente recusado), listagens seguem "read". Efeito colateral aceito: subagente não cria branch nem `git config k v`.
- `git_problem` novo concentra as regras de git perigoso; `_long_abbrev` casa abreviações de opção longa que o git
  aceita (`--no-veri`, `--forc`, `--mi`, `--de`); refspec com `+` = force; `--` encerra opções no commit.
- Script do harness por variável/`~`: `normpath` antes do regex; `.swarm` expansível que não resolve para o harness
  ⇒ inanalisável (fail-closed). Script expansível sem `.swarm` segue como antes.
- D-31: `test_guards.py:57` contradizia o CA-03 (principal gravava team.json5); passou a esperar recusa, e
  `.swarm/knowledge/notas-da-ana.md` prova a escrita do principal.
- Migração 0.12.2 `{kind: harness}` reinstala o guard nos alvos pelo `cs.py upgrade`.

## Aprendizados
- A letra dos CAs não basta para segurança: o portão ficou VERDE no ciclo 1 e a revisão da feature reabriu 3 portas
  por variantes (`$PWD/.swarm/...`, `push +HEAD`, `--no-veri`); a revisão pontual do ciclo 2 achou mais 2 (`.swarm//`,
  `/./`). Revisor adversarial em opus com sonda pronta (s3.py) custou pouco e achou o que os testes não cobriam.
- Normalize antes de casar padrão de caminho; prefira fail-closed para o que não resolve.
- Abreviação de opção longa do git é uma classe de bypass: toda regra sobre flag longa precisa de prefixo.
- O `campanha.py fechar` não é idempotente na retomada (regrava execução sem nota e trava remedicao.2) e a campanha
  ficou parada no intake até o fechamento: registrar as etapas do motor durante a execução, não só no fim.
- Hook de aprovação dá falso positivo em `python3 -` com heredoc que contém "Aceite"; escrever pelo Edit.
- Custo medido: opus 9 despachos, sonnet 6; 0 NOT_RUN.

## Arquivos da feature
- `scripts/harness/engine/bashscan.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/engine/hcore.py`
- `scripts/harness/engine/auto.py`
- `scripts/harness/tests/test_iter24_guard.py`
- `scripts/harness/tests/test_guards.py`
- `VERSION`
- `README.md`
- `references/migrations.json5`
- `docs/09-upgrade.md`

## Aceite da Feature
### Aceite QA — ACCEPT
### Aceite Review — APPROVED
<!-- fechar-feature:archive-completo -->
