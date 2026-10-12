# iter22 — cs-state show liberado no guard e varredura subcomandos × guard (0.12.1)

FEATURE-ID: iter22
Nome: cs-state show liberado no guard do alvo, varredura que impede subcomando sem regra no guard, versão 0.12.1

## História
Como dono de um alvo com o harness gerado, quero que o `cs-state show` (entregue na 0.11.0) funcione no Claude Code
do alvo — para o agente principal e, por ser leitura, também para o subagente —, e que nenhum subcomando novo do
cs-state volte a nascer bloqueado pelo guard, para que eu possa ler uma task em Markdown sem contorno.

## Problema / Contexto
Uso real na segunda cobaia .NET (2026-10-12, depois do upgrade 0.10.1→0.12.0): `.swarm/bin/cs-state show SPR-001/04`
→ `cs-guard BLOQUEOU: cs-state show desconhecido`. Medido na E2:
- F1: `scripts/harness/engine/guard.py:330` devolve "cs-state %s desconhecido" para todo subcomando fora de
  STATE_SUB["main"] (`guard.py:262-267`); o `show` nunca foi adicionado. Para subagente cai em `guard.py:345`.
- F2: nenhum teste passa o `show` pelo hook pre-bash (oráculo iter19 e `test_iter19_estado.py` chamam o cs-state
  direto) — por isso oráculo e portão da 0.11.0 ficaram verdes.
- F3: STATE_SUB é escrito à mão, separado do argparse do `state.py` (48 subcomandos: 42 na lista + 5 com regra
  explícita + o `show` sem nada).
- F4: docstring de `notebook_text_problems` (`guard.py:104-105`) descreve o comportamento do selo anterior à iter21.
- F5: `references/migrations.json5` termina em 0.12.0; sem 0.12.1 o upgrade não leva o guard corrigido.
Decisões da E1 (founder, "ok"): incluir a varredura subcomandos × guard; versão 0.12.1 com migração no catálogo.

## Valor de negócio
Destrava a principal melhoria de legibilidade da 0.11.0 nos alvos e fecha a classe de regressão "subcomando novo
bloqueado pelo guard" com um teste que falha na hora.

## Personas / Stakeholders
- Dono do alvo (lê tasks com `cs-state show`).
- Agente principal (orquestrador) e subagentes do alvo (leitura do estado).
- Sessão da segunda cobaia .NET (relatora do B-35).

## Critérios de Aceitação
- **CA-01 — show liberado para o agente principal.** DADO um alvo com o harness instalado (hook pre-bash ativo) e uma
  task existente, QUANDO o agente principal roda `.swarm/bin/cs-state show <id>` pelo hook pre-bash, ENTÃO o guard
  libera (exit 0, sem "desconhecido") e o comando imprime a task em Markdown.
  Prova: `cd campanhas/iter22/oraculo && python3 -m unittest test_iter22.TestCA01`
- **CA-02 — show liberado para subagente (leitura).** DADO o mesmo alvo e um subagente em delegação, QUANDO ele roda
  `cs-state show <id>` pelo hook pre-bash, ENTÃO o guard libera como as demais leituras (board, next, find…), e um
  subcomando que muda estado continua barrado para o subagente.
  Prova: `cd campanhas/iter22/oraculo && python3 -m unittest test_iter22.TestCA02`
- **CA-03 — nenhum subcomando sem regra no guard.** DADO o argparse do `state.py`, QUANDO se compara cada
  subcomando de nível superior com o guard, ENTÃO todo subcomando tem entrada em STATE_SUB ou regra explícita no
  guard; e um subcomando fictício acrescentado ao argparse sem entrada faz o teste FALHAR.
  Prova: `cd campanhas/iter22/oraculo && python3 -m unittest test_iter22.TestCA03`
- **CA-04 — versão 0.12.1 leva a correção aos alvos.** DADO um alvo 0.12.0, QUANDO roda `cs.py upgrade` e
  `upgrade --apply --allow-outside`, ENTÃO o plano lista a migração 0.12.1 (harness), o apply reinstala o guard e
  o `cs-state show` passa pelo hook; VERSION é 0.12.1 com a migração no catálogo; a docstring do caderno descreve o
  comportamento atual; os oráculos iter16/18/19/20/21 seguem inteiros verdes.
  Prova: `cd campanhas/iter22/oraculo && python3 -m unittest test_iter22.TestCA04`

## RNFs
- RNF-01: Python 3.9+ stdlib; verde em `python3` e `/usr/bin/python3`.
- RNF-02: nenhum `def` removido; o guard continua fail-closed para subcomando desconhecido.

## Edge cases
- `cs-state show` sem id ou com id inexistente: o guard libera (é leitura); o erro é do comando, não do guard.
- `cs-state --help` / sem subcomando: comportamento atual mantido.
- Subcomandos com regra explícita (legacy-ack, waive-verify, submit, review, abstain, dispatch) mantêm a regra.

## Dependências
- 0.12.0 entregue (iter21, 7fdb431). Helper de hook pre-bash da suíte harness (`test_autonomy_install.py:104`).

## Escopo IN
- `show` em STATE_SUB["main"] e ["any"]; teste que passa o show pelo hook; varredura argparse × guard; docstring F4;
  VERSION/README/catálogo 0.12.1 e nota em docs/09-upgrade.md.

## Escopo OUT
- O que o show exibe (B-33); add→new (B-28); órfãs (B-19); caderno duplicado (B-36); retract com id curto (B-37);
  cs-mem/cs-session/cs-route; motor embutido `.claude/tools/ac/`.

## Escopo de escrita
- `scripts/harness/engine/guard.py`
- `scripts/harness/tests/test_iter22_*.py`
- `references/migrations.json5`
- `docs/09-upgrade.md`
- `VERSION`
- `README.md`

## Critério de parada
Oráculo iter22 100% verde (CA-01..CA-04) em python3 e /usr/bin/python3; oráculos iter16, iter18, iter19, iter20 e
iter21 inteiros verdes; suítes do produto e harness-dev verdes; 0 `def` removido; VERSION 0.12.1.

## Métrica de sucesso
No alvo da cobaia, depois do upgrade para 0.12.1, `cs-state show SPR-001/04` pelo Claude Code: de bloqueado (hoje) a
liberado; e 0 subcomandos do cs-state sem regra no guard (hoje 1 de 48).

## Aceite da Feature
### Aceite QA — PENDENTE
### Aceite Review — PENDENTE
