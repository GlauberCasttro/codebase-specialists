# iter24 — guard sem portas laterais: harness, hardlink, registros humanos, escritores, inline e git (0.12.2)

FEATURE-ID: iter24
Nome: Hotfix de segurança do guard do harness gerado — fechar as portas confirmadas pela auditoria da cobaia (B-44, B-45, B-46, B-47)

## História
Como dono de um alvo com o harness gerado, quero que o guard barre de verdade o que ele promete barrar — o subagente
não executa atos humanos nem do principal por nenhuma forma de chamar o harness, nenhum agente escreve em arquivo
protegido por hardlink, por flag de saída ou por código inline, ninguém desliga os hooks pelo git e os registros de
aprovação humana não são graváveis pelo agente — para que "o agente não se auto-aprova" e "o humano decide no portão"
voltem a ser verdade.

## Problema / Contexto
Auditoria /orquestrar-subagentes da cobaia .NET 0.12.0 (2026-10-12), verificada às cegas com reprodução (E2). Medido
na E2 (`E/` = `scripts/harness/engine/`):
- F1/F2/F3: chamadas ao harness por `sh|bash <script>` (E/bashscan.py:202), `python3 -m state|auto` (:215) e opções
  com valor `-W/-X` (:208-215) não são identificadas ⇒ subagente roda `waive-verify`/`accept`/`submit` alheio;
  principal roda ato humano; E/auto.py:3045 só reconhece o basename.
- F4: `ln`/`cp -l` só validam o destino (E/bashscan.py:299) e decide_write compara caminho (E/guard.py:177-183) ⇒
  hardlink de `.claude/settings.json` no allowed_path do subagente desliga os hooks.
- F5: `lead_write_allow` libera `.swarm/` inteiro e `protected` não lista os registros humanos (E/hcore.py:830-831).
- F6: `git diff|show|log --output=`, `curl -o`, `wget -O`, `tar -C`, `unzip -d`, `dotnet -o` não modelados (E/bashscan.py:28, :325).
- F7: inline com flags combinadas (`-Sc`, `-Ic`, `-uc`) e stdin (`-`, `/dev/stdin`), `ruby -ne`, `node -pe` passam (E/bashscan.py:18, :209).
- F8: push protegido por token literal (E/guard.py:383-388); `config`/`branch`/`tag`/`remote`/`reflog` em GIT_READONLY ⇒
  `git config core.hooksPath /dev/null` passa até para subagente.
Decisões da E1 (founder, "ok"): B-46 entra; comando que chama o harness por forma indireta é recusado e inline/stdin é
fail-closed (sem bloquear `bash scripts/build.sh` legítimo); liberar a troca de branch do principal fica FORA.

## Valor de negócio
Restaura as garantias de que dependem todas as aprovações humanas do harness (portões, aceite, mandato) nos alvos.

## Personas / Stakeholders
- Dono do alvo (aprovações humanas, portões).
- Agente principal e subagentes do alvo (sujeitos ao guard).
- Founder da skill (as features da skill também confiam nessas garantias nos alvos).

## Critérios de Aceitação
- **CA-01 — harness só pelo caminho direto.** DADO um subagente com delegação ativa e o agente principal, QUANDO
  chamam o cs-state/cs-auto por `sh|bash <script>`, `python3 -m state|auto`, `python3 -W|-X <v> …/state.py` ou
  `cd .swarm/harness && python3 …`, ENTÃO o guard aplica as MESMAS regras do caminho direto (ato humano recusado a
  ambos; ato do principal recusado ao subagente; submit/review alheio recusado); e `bash scripts/build.sh` (script que
  não é do harness) segue como hoje.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA01`
- **CA-02 — hardlink não fura a proteção.** DADO um subagente com delegação ativa, QUANDO roda `ln <protegido>
  <allowed_path>` ou `cp -l …`, ou escreve (Write/Edit/redirect) num arquivo do próprio allowed_path que é hardlink de
  arquivo protegido, ENTÃO o guard recusa e o arquivo protegido fica intacto.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA02`
- **CA-03 — registros humanos não são graváveis pelo agente.** DADO o agente principal (e o subagente), QUANDO tenta
  escrever por Write/Edit/MultiEdit ou redirect em `.swarm/approvals.jsonl`, `.swarm/team-approvals.jsonl`,
  `.swarm/acceptance.json5`, `.swarm/run.json5` ou `.swarm/team.json5`, ENTÃO o guard recusa; o motor e os comandos
  humanos que os gravam continuam funcionando.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA03`
- **CA-04 — escritores com flag de saída.** DADO um alvo protegido, QUANDO o comando é `git diff|show|log --output=X`,
  `curl -o X`, `wget -O X`, `tar -C X`, `unzip -d X` ou `dotnet … -o X`, ENTÃO X é conferido como destino de escrita
  (protegido ⇒ recusa; permitido ⇒ passa).
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA04`
- **CA-05 — inline e stdin fail-closed.** DADO um interpretador com código inline por flags combinadas (`-Sc`, `-Ic`,
  `-uc`, `-ne`, `-pe`) ou lendo de stdin (`-`, `/dev/stdin`, `| sh -`), QUANDO o guard analisa, ENTÃO recusa como já
  recusa `python3 -c`; script de arquivo dentro do projeto segue como hoje.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA05`
- **CA-06 — git não desliga proteção nem reescreve remoto protegido.** DADO o principal e o subagente, QUANDO rodam
  `git config core.hooksPath …` (ou `-c core.hooksPath`), push para branch protegida por refspec (`HEAD:main`,
  `+x:main`, `:master`), `push -f|--force|--delete|--mirror`, `commit --no-verify|-n`, `branch -D|-f` em branch
  protegida, `remote set-url|add`, `reflog expire`, ENTÃO o guard recusa (subagente: todo git não-leitura como hoje);
  leituras de git (status/log/diff sem --output/show) seguem liberadas.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA06`
- **CA-07 — 0.12.2 chega aos alvos sem regressão.** DADO um alvo 0.12.1, QUANDO roda `cs.py upgrade` e
  `upgrade --apply --allow-outside`, ENTÃO o plano lista 0.12.2 (harness), o apply reinstala o guard e as portas de
  CA-01..CA-06 ficam fechadas no alvo; VERSION 0.12.2 com a migração no catálogo; oráculos iter16..iter22 inteiros verdes.
  Prova: `cd campanhas/iter24/oraculo && python3 -m unittest test_iter24.TestCA07`

## RNFs
- RNF-01: Python 3.9+ stdlib; verde em `python3` e `/usr/bin/python3`.
- RNF-02: nenhum `def` removido; payload ilegível continua fail-closed; nenhuma mensagem imprime segredo.
- RNF-03: sem falso bloqueio novo nas leituras do dia a dia (cat/grep/ls/git log/git diff/dotnet build/dotnet test).

## Edge cases
- `bash scripts/build.sh` (fora do harness) e `python3 tools/x.py` dentro do projeto: liberados como hoje.
- Hardlink criado ANTES da correção: a escrita por ele é recusada pelo nlink/inode.
- `git diff > arquivo` (redirect) já é tratado; `--output` passa a ser.
- Comando do humano no terminal dele não passa pelo guard (fora do hook): não muda.

## Dependências
- iter22 (0.12.1) fechada antes da abertura (colisão em guard.py, VERSION, README, catálogo, docs/09).
- Helpers de teste com hook pre-bash/pre-write (suíte harness).

## Escopo IN
- bashscan e guard (formas indiretas do harness, hardlink, flags de saída, inline/stdin, git), config padrão de
  protegidos, reconhecimento de ato humano no auto, testes de regressão, versão/catálogo 0.12.2 e nota de upgrade.

## Escopo OUT
- Liberar troca de branch do principal (parte "falso bloqueio" do B-47); falsos bloqueios do B-51; escrita por Bash
  em geral (limite declarado); assinatura/selo dos registros humanos no pre-commit (o motor e o humano gravam e o
  agente commita — distinguir autor no commit exige selo: candidato a item novo); B-48, B-49, B-50; iter23.

## Escopo de escrita
- `scripts/harness/engine/bashscan.py`
- `scripts/harness/engine/guard.py`
- `scripts/harness/engine/hcore.py`
- `scripts/harness/engine/auto.py`
- `scripts/harness/tests/test_iter24_*.py`
- `references/migrations.json5`
- `docs/09-upgrade.md`
- `VERSION`
- `README.md`

## Critério de parada
Oráculo iter24 100% verde (CA-01..CA-07) em python3 e /usr/bin/python3; oráculos iter16, iter18, iter19, iter20,
iter21 e iter22 inteiros verdes; suítes do produto e harness-dev verdes; 0 `def` removido; VERSION 0.12.2.

## Métrica de sucesso
Das 8 portas confirmadas pela auditoria (F1–F8), 0 abertas num alvo atualizado para 0.12.2 (hoje 8), medidas pelos
mesmos payloads da auditoria.

## Aceite da Feature
### Aceite QA — ACCEPT
QA: Claude Code · general-purpose · sonnet (instância isolada; não escreveu — snapshot vazio). Portão `local/portao-iter24/portao.out`
(cópia limpa HEAD 92f5cf2 + 10 arquivos de local/iter24-arquivos.txt; 17 suítes × python3 3.13 e /usr/bin/python3 3.9.6):
`RESULTADO: VERDE` + `FIM`; 0 linhas FAIL/ERROR. `ac.py oracle verify`: oráculo intacto.

| CA | Evidência | Resultado |
|---|---|---|
| CA-01 | test_iter24.TestCA01 (4) | PASS |
| CA-02 | TestCA02 (3) | PASS |
| CA-03 | TestCA03 (3) | PASS |
| CA-04 | TestCA04 (3) | PASS |
| CA-05 | TestCA05 (3) | PASS |
| CA-06 | TestCA06 (3) | PASS |
| CA-07 | TestCA07 (3) + oráculos iter16 48, iter18 38, iter19 39, iter20 24, iter21 64, iter22 9 OK nos 2 Pythons | PASS |
### Aceite Review — PENDENTE
