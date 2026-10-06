# 05 — Sessão e retomada

Há **dois** mecanismos de retomada, para duas coisas diferentes:

| O que se retoma | Mecanismo | Estado em disco |
|---|---|---|
| a **execução da skill** (montar o time) | `cs.py stage status` / `cs.py stage load <etapa>` / `/codebase-specialists retomar` | `.swarm/run.json5` + `.swarm/stages/*.handoff.json5` |
| o **trabalho do dia a dia** com o time (tasks, sprints, delegações) | `.swarm/bin/cs-session save` / `load` (`/save-session`, `/load-session`) | `.swarm/session/resume.json5` + estado do harness |

Princípio comum (premissa PR-11, ARCHITECTURE §8-quater): **o disco é a âncora**. Retomar não é reler a conversa
nem deixar o modelo abrir arquivos de estado: um script monta um pacote pequeno e o modelo segue dali.

## 1. Retomar a execução da skill

A execução atravessa várias janelas de contexto por desenho (uma por etapa). Se a sessão caiu, a janela encheu
ou o limite de uso acabou, numa sessão nova, no mesmo repositório:

```text
cs.py stage status
cs.py stage load <etapa-atual>
```

Ou peça `/codebase-specialists retomar` ("continua o codebase-specialists"): a skill faz exatamente isso.

- `stage load` retoma na **sub-etapa pendente** (`limits.substage_resume: true`); nada que fechou é refeito.
- O pacote tem ≤2.000 tokens (`limits.handoff_max_tokens`): objetivo, checklist com estado, handoff da etapa
  anterior, pendências. Exemplo real (py-billing, iteração 4): `// pacote de entrada da etapa scan (~385 tokens)`.
- Se o contexto do orquestrador pesar no meio de uma etapa: grave o que voltou dos subagentes, rode `cs.py stage
  status` e encerre; a próxima sessão começa com `stage load <etapa>` (`references/prompts.json5 →
  execucao.janela`).
- Ao fim de cada etapa, o orquestrador devolve 3–5 linhas de handoff e recomenda `/clear` ou sessão nova
  (`limits.stage_new_window: true`).

Gate G16 (suíte `scripts/stage/tests/`): `stage load` de cada etapa cabe em 2k tokens; `stage done` com check
falhando não avança; retomada no meio de uma etapa recomeça na sub-etapa certa sem repetir as feitas.

Exemplo de uso real: as rodadas da iteração 4 de py-billing e go-polyglot ficaram **pausadas** em validate.3 e
validate.2; o plano da próxima rodada (`campanhas/historico/PROXIMA-RODADA.md`) as retoma com
`/codebase-specialists retomar`, nunca do zero.

## 2. `cs-session save` — salvar o trabalho

```text
.swarm/bin/cs-session save --did "<1 linha>" --next "<1 linha>" [--blocked "<1 linha>"] [--decision "<texto>"] [--commit]
```

O modelo fornece só o que o script não tem como saber (o que fez, o próximo passo, o bloqueio). O resto é
coletado: board (tasks por status, sessão M1 ativa, tentativas), últimos eventos, git (branch, HEAD, arquivos
sujos por área/território), gates (último verify e selftest), lições novas desde o último save, fase da
execução (`run.json5`), e o comando do próximo passo.

- Grava `.swarm/session/resume.json5` com **carimbo** = sha256(board + hash do último evento + HEAD +
  fase).
- Apensa um episódio na memória ("sessão salva: fez …; próximo …").
- `--commit` faz commit **só** de `.swarm/session` e `.swarm/state` — nunca de produto.
- `--check` (usado em approve.3) só confere que o save existe e o carimbo bate (exit 0/1), e **reprova** se o
  save é anterior à última decisão registrada em `.swarm/approvals.jsonl` ("congelar o baseline DEPOIS da
  decisão do founder").
- No modo autônomo, o save é automático a cada delegação ACCEPTED (checkpoint).

## 3. `cs-session load` — retomar o trabalho

```text
.swarm/bin/cs-session load [--brief]
```

```text
                      recalcula o carimbo
                             │
          ┌──────────────────┴──────────────────┐
     bate (ou o HEAD avançou só com              não bate
     commits em .swarm/)                    │
          │                                       ▼
          ▼                              "DELTA desde o save:"
   briefing do save                        eventos novos · commits novos por área ·
   (≤30 linhas, ≤2.000 tokens)             tasks que mudaram · gates que mudaram · fase
          │                                + 5 linhas do briefing anterior
          └──────────────────┬──────────────────┘
                             ▼
              "próximo passo: …"  +  "comando: …"
```

- Sempre termina com o próximo passo e o comando exato. Sem save: "nenhuma sessão salva." e
  `próximo passo: cs-state next`.
- Limites: 30 linhas, 2.000 tokens estimados (caracteres ÷ 3,5); o excedente é truncado preservando as duas
  linhas finais.
- `--brief` = saída JSON para o hook `SessionStart` (o hook injeta `.claude/orchestrator.md` + o load).
- Nunca despeja o estado inteiro.

### Comandos emitidos (Claude Code)

| Comando | Faz (template em `assets/templates/`) |
|---|---|
| `/save-session` | escreve 1 linha para feito/próximo/bloqueio e roda `.swarm/bin/cs-session save --did "<feito>" --next "<próximo>" [--blocked "<bloqueio>"]`; mostra a saída e para |
| `/load-session` | injeta a saída de `` !`.swarm/bin/cs-session load` `` antes do modelo ler qualquer coisa; "use só este briefing; não abra arquivos de estado" |

Nas outras plataformas, o núcleo S0 instrui a rodar os mesmos scripts no terminal.

Gate G9 (suíte `harness/tests/test_router_session.py -k TestSession`): `load` com carimbo batendo imprime ≤2.000
tokens; após um evento novo, `load` detecta o delta; round-trip save→load é idempotente.

## 4. Janelas de contexto — resumo prático

| Situação | Faça |
|---|---|
| Terminou uma etapa da skill | `cs.py stage done <etapa>`; handoff curto; `/clear` ou sessão nova; `cs.py stage load <próxima>` |
| Contexto pesando no meio de uma etapa | registre o que voltou; `cs.py stage status`; nova sessão; `cs.py stage load <etapa>` |
| Limite de uso / sessão caiu durante a execução | `/codebase-specialists retomar` |
| Fim do dia trabalhando com o time | `/save-session` (ou `.swarm/bin/cs-session save --did … --next …`) |
| Começo do dia | `/load-session` (ou `.swarm/bin/cs-session load`); o hook `SessionStart` já injeta o load no Claude Code |
| Código mudou muito | `cs.py harness selftest --drift`; re-rode `cs.py scan` e as etapas scan → approve para os territórios tocados |
