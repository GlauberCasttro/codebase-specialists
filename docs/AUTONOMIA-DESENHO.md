# Modo autônomo v2 — desenho (pesquisa + especificação, NÃO implementado)

Data: 2026-10-03. Escopo: substituir o modo autônomo atual da skill `codebase-specialists` por um modo que
entrega uma **frente inteira** (feature ou sprint) sozinho, com **máquina de estado própria e mecânica**,
respeitando o harness (territórios, guards, gates, ledger, cadeia de eventos).
Forma de rodar: `/auto-correcao`, com os cenários da §11 entrando no oráculo **antes** do freeze.

Convenção de evidência: `arquivo:linha` é relativo a `~/.claude/skills/codebase-specialists/` salvo indicação.
Afirmação externa sempre com URL; número sem fonte vem marcado **[sem fonte]**.

---

## 0. Resumo em 12 linhas

1. O autônomo de hoje é um **mandato + um hook Stop que diz "continue"**: o modelo é o loop; o motor só veta.
2. O mandato não é máquina: tem 4 estados e **nenhuma transição** em `machines.json5`; muda por escrita de arquivo.
3. Não planeja, não replaneja, não integra, não mede progresso por resultado, não usa memória, e ESCALATED não tem saída.
4. Desenho novo: **M5 `mandato`** dentro de `machines.machines` (coberta pelo teste de vivacidade), 11 estados,
   transições por evento encadeado, guardas mecânicas.
5. O motor vira o **piloto** (`cs-auto tick` devolve UMA próxima ação); o modelo só executa nós de julgamento
   (decompor, escrever brief, revisar, refletir, escolher entre opções de replano). Padrão "grafo em código, LLM nos
   nós" (LangGraph, Anthropic workflows).
6. Plano = **DAG** de tasks gravado e versionado; ondas **calculadas** (camadas topológicas × coloração do grafo de
   colisão), não um inteiro `wave` digitado.
7. Verificação em 3 níveis: task (M2, já existe), **onda** (regressão contra baseline), **frente** (aceite).
8. Progresso = **testes de aceite verdes** (métrica monotônica externa), não contagem de eventos.
9. Escalada **não tranca**: AWAITING_HUMAN tem saídas retomar/trocar/emendar/descartar/abortar e só congela o
   **subgrafo afetado**; o resto do DAG continua.
10. Orçamento multidimensional com **limite suave (80%) → modo encerramento** e entrega PARCIAL honesta.
11. Retomada entre janelas por checkpoint a cada transição + `SessionStart`/`PreCompact`; minutos contam só tempo ativo.
12. Memória: busca de lições antes do plano, reflexão ancorada em sinal externo após rejeição, consolidação no fim.

---

## 1. O que existe (lido)

| Peça | Onde | Faz |
|---|---|---|
| Mandato | `scripts/harness/engine/autonomy.py:52-108` | recusa sem spec/aceite/orçamento, recusa `risco`, roda aceite e **recusa se já verde**, grava `autonomy.json5` assinado + evento `autonomy.start` |
| Escopo | `autonomy.py:111-117` | tasks das stories da feature/story |
| Orçamento | `autonomy.py:120-141` | tasks, minutos, usd; `retry_cap` |
| Escalada | `autonomy.py:151-205` | 8 condições (`machines.json5:148-149`) |
| Parada | `autonomy.py:236-269` + `guard.py:419-424` | hook Stop bloqueia com "continue: cs-state next → …" |
| Checkpoint | `autonomy.py:272-276` + `engine.py:1208-1215` | `session.save` a cada `delegation.accept` |
| Relatório | `autonomy.py:292-330` | roda aceite de novo; marca DONE só aqui |
| Proibições | `autonomy.py:333-342`, `guard.py:223-235`, `guard.py:546-552` | não escreve spec/teste de aceite; sem push; kill-switch ignorado |
| CLI | `engine/state.py:182-193, 406-436` | `autonomy start|status|stop|report|spend` |
| Kernel | `assets/templates/orchestrator.md:68-78` | 4 bullets de "modos" |
| Comando | `assets/templates/feature-autonoma.md:1-11` | toque único de aprovação; "siga cs-state next até REPORTING" |
| Arquitetura | `references/ARCHITECTURE.md` §8-sexies (linhas 300-332) | o contrato acima + gate G11 |
| Doc | `docs/02-harness.md:279-333` | idem, para o usuário |

Há coisas boas e que **ficam**: aceite precisa estar vermelho no início (`autonomy.py:90-91`) — impede mandato
vazio; spec e testes de aceite são imutáveis com hash (`autonomy.py:192-195, 333-342`) — é a defesa certa contra
reward hacking (§3, P7); mandato assinado e detectado pelo validador (`engine/validate.py:110-120`); sem push.

---

## 2. Diagnóstico — por que é fraco (com evidência)

### D1. Não existe máquina de estado do mandato
- `machines.json5:146-152`: `autonomy` tem `states` e `escalation_conditions`, **zero `transitions`**, e fica
  **fora** de `machines.machines` (linhas 20-145). O motor de guardas e o teste de vivacidade nunca o veem:
  `tests/test_maquinas_vivacidade.py:27-28` itera só `["machines"]`.
- As mudanças de estado são `m["state"] = …; save()` direto: `autonomy.py:209` (ESCALATED), `:284` (STOPPED),
  `:324` (DONE). Só `start` vira evento encadeado (`:102-105`); o resto vai para o ledger (`:220, :288`), que não é
  a cadeia de hash. Resultado: não há `why`, não há replay, não há guarda, não há auditoria da trajetória.
- O teste de vivacidade, que é invariante permanente do founder, **está vermelho hoje** (rodado em 2026-10-03:
  `python3 -m unittest tests.test_maquinas_vivacidade` → 2 falhas; a primeira: `epic.DONE não tem transição de
  saída e não está declarado terminal`).

### D2. ESCALATED é beco sem saída (o bug real, nos dois níveis)
- Delegação: `machines.json5:45` declara ESCALATED **terminal**; nenhuma transição sai dele (`:47-65`). É
  exatamente o bug que o founder achou (`campanhas/historico/PROXIMA-RODADA.md:151-153`); continua na fonte.
- Mandato: não há ação `resume` (`state.py:183` aceita só `start|status|stop|report|spend`). `next_lines` em
  ESCALATED devolve só "leve ao usuário" (`views.py:116-120`). A única saída é `stop` → STOPPED + modo assistido
  (`autonomy.py:283-286`): perde contadores, orçamento gasto e contexto; recomeçar é um `start` novo que refaz
  baseline e assinatura. A decisão humana **não tem onde ser gravada**.

### D3. Não planeja
- `start` não cria plano (`autonomy.py:52-108`). O plano é o do M1 (`engine.py:299-305`: "plano vazio" só exige ≥1
  task com brief), sem ligação com os critérios de aceite do mandato — nada prova que o plano cobre a feature.
- Ondas são um inteiro `wave` escrito à mão; o motor só confere sobreposição dentro da mesma onda
  (`engine.py:380-392`). Não há DAG, nem ordenação topológica, nem cálculo de ondas.

### D4. Não replaneja e para em silêncio
- `has_work` (`autonomy.py:224-233`) só olha delegações em andamento. Com tudo ACCEPTED e aceite **ainda
  vermelho**, `has_work` é falso e o Stop **libera a parada** (`:249-250`) sem escalar e sem marcar nada: o mandato
  fica ACTIVE para sempre. DONE só existe se alguém chamar `report` (`:323-327`).
- A transição `replan` do M1 existe (`machines.json5:32`) mas o autônomo nunca a dispara.

### D5. O loop vive dentro de UMA sessão M1
- Stop só bloqueia com sessão em EXECUTING/VERIFYING (`autonomy.py:242-244`). Em TRIAGE, PLANNING ou REPORTING o
  agente pode parar. O ARCHITECTURE promete "o loop percorre as stories da feature sprint a sprint"
  (`ARCHITECTURE.md:356`) — não há código que encadeie stories, sessões ou sprints.

### D6. Progresso medido pela coisa errada
- "Progresso" = `event_count` mudou (`autonomy.py:253-257`). Trabalho inútil que gera eventos conta como progresso;
  exploração legítima sem evento conta como "sem progresso" e escala após 3 (`machines.json5:151`). O teto de
  200 bloqueios (`:150`) é número **[sem fonte]**.
- O hook ignora `stop_hook_active` no autônomo (`autonomy.py:236-269` não lê o campo), o que é aceitável só porque
  há contadores — mas os contadores medem a coisa errada.

### D7. Escalada tudo-ou-nada, grosseira
- `invariant_or_frozen_touched` dispara para **qualquer** task não aceita cujo brief cite invariante de escopo
  (`autonomy.py:156-164`) — antes de tocar qualquer coisa. Uma feature que só *lê* perto de invariante escala na
  primeira chamada do Stop.
- `same_rejection_twice` = Jaccard ≥ 0,5 entre textos de motivo (`:144-148, :181-185`): heurística léxica
  **[sem fonte para o limiar]**; textos com o mesmo boilerplate colidem.
- Toda condição para o mandato inteiro (`:245-248`); não há distinção dura/suave nem "congelar só o ramo".

### D8. Orçamento ingênuo
- `tasks` conta tasks com `attempts>0` (`autonomy.py:127-129`), não despachos nem retentativas.
- `minutes` = relógio de parede desde `started_ts` (`:130`): uma noite com o terminal fechado esgota o orçamento.
- `usd` é **autodeclarado** pelo modelo (`state.py:430-436`, ação `spend`). Orçamento que o agente preenche não é
  controle.
- Esgotou → escala (`:186-188`) em vez de **encerrar com entrega parcial** ordenada.

### D9. Verificação só na ponta
- M2 verifica cada task (`machines.json5:54-55`); o aceite só roda no `report` (`autonomy.py:300`). Não há
  regressão após a onda (testes verdes no baseline que ficaram vermelhos), nem revisão final da **frente**
  exigida pelo mandato.
- `pipeline_satisfied` aceita fechar a sessão com task ESCALATED (`engine.py:444-452`) — no autônomo isso deixa a
  sessão terminar "satisfeita" com buraco.

### D10. Memória decorativa
- Lições aparecem só no relatório (`autonomy.py:306-311`). Nada busca lição antes de planejar, nada grava reflexão
  após rejeição, nada consolida no fim.

### D11. Checkpoint frágil e retomada implícita
- Checkpoint só em `delegation.accept` (`autonomy.py:272-276`); falha vira *warning* no ledger
  (`engine.py:1213-1215`). Nada no `SessionStart`/`PreCompact` restaura o estado do mandato; delegação DISPATCHED
  cuja janela morreu não tem tratamento (órfã).

### D12. Prosa no lugar de controle
- `feature-autonoma.md:10-11`: "siga `cs-state next` até REPORTING sem novas perguntas". O kernel resume o modo
  em 4 bullets (`orchestrator.md:68-78`). O orçamento é **proposto pelo próprio modelo** sem derivação
  (`feature-autonoma.md:5`).

### D13. Nunca foi exercitado ponta a ponta
- `docs/defeitos-abertos.json5:25`: "evals 4–6 (autônomo, escalada, bugfix) nunca foram rodados";
  `docs/08-limites-e-defeitos-conhecidos.md:29`: "G11 é parcial". Os testes (`tests/test_autonomy_install.py`)
  são unitários de função; nenhum percorre feature → ondas → escalada → retomada → DONE.

**Veredito:** o atual é um *guard-rail* de parada, não um piloto. Falta estado (D1, D2), plano (D3), replano (D4),
continuidade (D5, D11), sinal de progresso (D6), escalada graduada (D7), orçamento confiável (D8), verificação
intermediária (D9) e memória (D10).

---

## 3. Princípios (cada um com fonte)

| # | Princípio | Fonte | Como entra aqui |
|---|---|---|---|
| P1 | Fluxo previsível em código; LLM só onde há julgamento. "Workflows: LLMs and tools orchestrated through predefined code paths"; comece simples. | Anthropic, *Building effective agents* — https://www.anthropic.com/engineering/building-effective-agents | O motor decide a próxima ação; o modelo preenche nós de julgamento. |
| P2 | Agente precisa de "ground truth from the environment at each step" e de "stopping conditions (such as a maximum number of iterations)"; pode "pause for human feedback at checkpoints or when encountering blockers". | idem | Progresso = testes executados pelo motor; parada mecânica; escalada como pausa, não fim. |
| P3 | Orquestrador-trabalhadores para subtarefas imprevisíveis; avaliador-otimizador só "when we have clear evaluation criteria". | idem | Plano dinâmico do líder; retry com achados só quando o critério é um comando. |
| P4 | Sistema multiagente: líder salva o plano em memória porque contexto >200k é truncado; retomada "from where the agent was when the errors occurred"; avaliar o **estado final**, não o processo; regras de escala de esforço no prompt; ~15× mais tokens que chat. | Anthropic, *How we built our multi-agent research system* — https://www.anthropic.com/engineering/multi-agent-research-system | Plano em arquivo versionado; checkpoint por transição; DONE = aceite verde; orçamento derivado do tamanho. |
| P5 | Long-running: agente inicializador + agente incremental; lista de features em JSON com status; **uma feature por vez**; arquivo de progresso + git; sem teste explícito o modelo "mark a feature as complete without proper testing"; "unacceptable to remove or edit tests". | Anthropic, *Effective harnesses for long-running agents* — https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents | PLANNING separado de RUNNING; uma feature ativa; diário de progresso gerado pelo motor; aceite imutável. |
| P6 | *Context rot*: recall cai com o tamanho do contexto; use compactação, notas estruturadas fora da janela, subagentes que devolvem resumo de 1–2 mil tokens, recuperação *just-in-time*. | Anthropic, *Effective context engineering* — https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents | O piloto entrega ao modelo só a ação corrente + referências; submissions sumarizadas; `cs-auto tick` ≤ 1 tela. |
| P7 | Modelos de fronteira fazem *reward hacking* (alteram testes, fazem *monkey-patch* do avaliador); RE-Bench 30,4% das execuções; pedir "não trapaceie" teve efeito "nearly negligible". | METR, *Recent frontier models are reward hacking* — https://metr.org/blog/2025-06-05-recent-reward-hacking/ | Imutabilidade mecânica de spec/aceite/verificador (hash + guard), não instrução. |
| P8 | Autocorreção **sem sinal externo** não funciona e pode piorar. | Huang et al., *LLMs Cannot Self-Correct Reasoning Yet* — https://arxiv.org/abs/2310.01798 | Reflexão só com saída de comando/veredito anexada; sem sinal, não há "tente de novo". |
| P9 | Reflexion: reflexão verbal sobre **sinal de feedback**, guardada em memória episódica, melhora tentativas seguintes (91% pass@1 HumanEval). | Shinn et al. — https://arxiv.org/abs/2303.11366 | Nota de reflexão obrigatória no retry, ancorada na falha; vira lição candidata. |
| P10 | Planejar como **DAG** e executar em paralelo o que não depende: até 3,7× latência e 6,7× custo vs ReAct. | LLMCompiler — https://arxiv.org/abs/2312.04511 | Plano DAG; ondas = camadas topológicas. |
| P11 | Paralelo só onde não há decisão implícita compartilhada: "actions carry implicit decisions, and conflicting decisions carry bad results". | Cognition, *Don't build multi-agents* — https://cognition.com/blog/dont-build-multi-agents | Paralelo só com `allowed_paths` disjuntos **e** sem par de colisão; decisão de contrato vira task anterior (architect) no DAG. |
| P12 | Falhas de sistemas multiagente: 14 modos em 3 grupos (design do sistema, desalinhamento entre agentes, **verificação/término**). | Cemri et al., *Why Do Multi-Agent LLM Systems Fail?* — https://arxiv.org/abs/2503.13657 | Término e verificação são estados explícitos com guarda, não convenção. |
| P13 | Deriva de objetivo cresce com o contexto (todos os modelos avaliados derivam em algum grau). | Arike et al. — https://arxiv.org/abs/2505.02709 | Cada nó do plano liga a um critério do mandato; o piloto reinjeta o objetivo a cada tick. |
| P14 | Persistência por *checkpoint* a cada passo; *interrupt* espera humano indefinidamente e retoma com `Command(resume=…)` no mesmo thread. | LangGraph — https://docs.langchain.com/oss/python/langgraph/persistence ; https://docs.langchain.com/oss/python/langgraph/interrupts | AWAITING_HUMAN é *interrupt* com retomada tipada; nó retomado deve ser idempotente. |
| P15 | Pipeline simples (localizar → corrigir → validar patch) bate agentes complexos em custo/acerto (32% SWE-bench Lite, US$ 0,70). | Agentless — https://arxiv.org/abs/2407.01489 | Cada task segue um mini-pipeline fixo; autonomia está no plano, não em cada passo. |
| P16 | Interface agente-computador e *sandbox* importam (SWE-agent; OpenHands com *event stream* de ações/observações). | https://arxiv.org/abs/2405.15793 ; https://arxiv.org/abs/2407.16741 | `events.jsonl` é o *event stream*; o piloto é a ACI do orquestrador. |
| P17 | Entrega com **evidência citável**: cada tarefa em sandbox isolado; o resultado cita logs de terminal e saídas de teste. | OpenAI, *Introducing Codex* — https://openai.com/index/introducing-codex/ (página bloqueou fetch; conteúdo confirmado pelos resultados de busca do mesmo URL) | Relatório final cita `output_sha256` de cada comando executado pelo motor. |
| P18 | Horizonte de tarefas a 50% de sucesso ~50 min para o melhor modelo avaliado, dobrando ~7 meses. | METR — https://arxiv.org/abs/2503.14499 | Tasks dimensionadas para bem abaixo do horizonte; frente longa = muitas tasks curtas verificadas. |
| P19 | Hook Stop: `decision:block` + `reason`; `additionalContext`; `stop_hook_active` para evitar loop; `SessionStart` com `source: compact|resume`; `PreCompact`. | Claude Code hooks — https://code.claude.com/docs/en/hooks | Mecanismo do piloto no Claude Code. |
| P20 | Handoff como ferramenta explícita, com filtro do que o receptor vê. | OpenAI Agents SDK — https://openai.github.io/openai-agents-python/handoffs/ | Brief = filtro de contexto; nível único de delegação (já é regra do harness). |
| P21 | Da skill do founder `orquestrar-subagentes`: carta de missão **antes** do despacho (critério escrito depois é racionalização); orçamento em proxies observáveis (agentes, rodadas, minutos); agente que não voltou: cobrar uma vez e registrar lacuna; orçamento estourado → entrega **parcial** marcada; escopo maior que o previsto → parar e perguntar; verificador nunca mais fraco que o autor; refutar exige contraevidência; "pulo calado" proibido; o modelo interpreta, scripts contam e decidem. | `~/.claude/skills/orquestrar-subagentes/SKILL.md` (Passos 2, 4, 7, 8; anti-padrões) e `references/evidence.md` | Ver §4. |

Dados que **não** consegui verificar e não uso como base: taxas de sucesso de Devin/Jules em produção; qualquer
número "X% de melhoria com replanejamento" para engenharia de software. Não há fonte primária adequada.

---

## 4. O que se aplica da skill `orquestrar-subagentes`

| Conceito dela | Aplicação no autônomo v2 |
|---|---|
| Portão "delegar ou fazer direto" | Faixas: pergunta/trivial/pequena **não** entram no autônomo; o piloto recusa mandato quando o plano tem 1 task (use avulsa). |
| Carta de missão antes do despacho | O **mandato** é a carta: objetivo, critérios executáveis, orçamento, rigor, condições de aborto — assinado antes de PLANNING. |
| Orçamento em proxies observáveis | despachos, tentativas, replanos, minutos ativos, tokens/usd **medidos** pelo router (`procedencia: medida`), nunca autodeclarados. |
| Rigor lean/standard/paranoid como tabela de parâmetros | `mandato.rigor` define: revisão por task, revisão cega da frente, verificador executor (teste que falha) para achado alto, cobertura. |
| E0–E3 | Task só ACCEPTED com E2 (motor executou); achado de review alto exige `arquivo:linha` (E1) ou comando (E2); replano precisa citar E1/E2. |
| Verificador ≥ autor; cego ao argumento | Gate de review da frente recebe diff + critérios, **não** o raciocínio do dev; model do verificador ≥ model do autor (guarda). |
| "Inconclusivo não é refutado" | Review sem evidência não fecha a task: vira NEEDS_SPECIALIST, não PASS. |
| Agente que não voltou: cobrar 1× → lacuna | Delegação órfã: 1 cobrança, depois `delegation.return protocol_failure` e o piloto conta tentativa. |
| Escopo cresceu → pare e pergunte | Condição suave `scope_expansion` (task exige path fora dos territórios previstos no plano). |
| Pulo calado proibido | Relatório lista toda verificação prevista e não executada, com motivo. |
| Síntese mecânica GO/NO-GO | `cs-auto report` decide DONE/PARCIAL/ABORTADO por script, com motivos. |
| Ledger de TP/FP sem autoavaliação | Lições só sobem de candidata a ativa com sinal externo (teste/veredito de outro agente/humano). |

---

## 5. A máquina de estado M5 `mandato`

### 5.1 Estados

| Estado | Significado | Terminal? |
|---|---|---|
| `PROPOSED` | proposta montada pelo motor (spec, aceite vermelho, classe, orçamento derivado, rigor); aguarda o toque humano | não |
| `CHARTERED` | aprovada e assinada; baseline gravado (aceite vermelho + suíte de regressão) | não |
| `PLANNING` | o modelo propõe o DAG; o motor valida | não |
| `RUNNING` | despacho de ondas; M2 roda por task | não |
| `INTEGRATING` | onda fechou: regressão + aceite parcial + medição de progresso | não |
| `REPLANNING` | plano vN → vN+1 com evidência | não |
| `AWAITING_HUMAN` | *interrupt* com pacote de evidência; parte do DAG congelada (ou todo, se dura global) | **não** (saídas tipadas) |
| `PAUSED` | janela acabou / usuário pausou / `PreCompact`; nada em voo | não |
| `WRAPPING_UP` | limite suave atingido ou sem progresso: não abre task nova, fecha o que está em voo | não |
| `DONE` | aceite verde + DoD da frente + revisão final | sim |
| `HANDED_BACK` | entrega parcial honesta (orçamento, sem progresso, ou humano mandou parar) com relatório | sim |
| `ABORTED` | humano abortou ou violação dura irreparável; árvore restaurada ao ponto seguro | sim |

Terminais declarados: `DONE`, `HANDED_BACK`, `ABORTED`. `AWAITING_HUMAN` e `PAUSED` **nunca** terminais
(entram em `AGUARDANDO_HUMANO` do teste de vivacidade).

### 5.2 Diagrama

```
                     cs-auto propose (motor monta)        aprovação humana (1 toque)
   ┌──────────┐ ───────────────────────────────▶ ┌──────────┐ ─────approve──────▶ ┌────────────┐
   │ (nenhum) │                                   │ PROPOSED │ ◀──amend(humano)── │ CHARTERED  │
   └──────────┘                                   └────┬─────┘                    └─────┬──────┘
                                                       │ reject(humano)                 │ plan (motor)
                                                       ▼                                ▼
                                                  ABORTED              ┌────────────────────────────┐
                                                                       │          PLANNING          │◀──────────┐
                                                                       │ modelo: propõe DAG         │           │
                                                                       │ motor: valida, calcula     │           │
                                                                       │ ondas, cobre critérios     │           │
                                                                       └──────────────┬─────────────┘           │
                                                                    plan_valid        │                         │
                                                                                      ▼                         │
   ┌───────────────────────── tick ──────────────────────────────────▶ ┌──────────────────────┐               │
   │                                                                     │       RUNNING        │──escalate──┐ │
   │       ┌───── wave_closed ──────────────────────────────────────────│ (ondas de M2)        │  (dura/    │ │
   │       ▼                                                             └──────────┬───────────┘   suave)   │ │
   │ ┌──────────────┐  regressão vermelha / aceite sem avanço / task              │ window_end           │ │
   │ │ INTEGRATING  │──────── BLOCKED / abstenção ───────▶ ┌──────────────┐       ▼                      │ │
   │ │ motor: roda  │                                        │ REPLANNING   │──── PAUSED ◀─ PreCompact    │ │
   │ │ regressão +  │──── aceite 100% verde ──┐              │ modelo: v+1  │      │  resume (SessionStart)│ │
   │ │ aceite       │                         │              │ motor: diff, │      └──────▶ (estado salvo) │ │
   │ └──────┬───────┘                         │              │ cap replanos │──────────────────────────────┼─┘
   │        │ progresso ≥ 1 e há onda         │              └──────┬───────┘                              │
   └────────┘                                 ▼                     │ cap de replanos / sem caminho        ▼
                                      ┌───────────────┐             ▼                            ┌────────────────┐
                                      │ revisão final │       AWAITING_HUMAN ◀───────────────────│ AWAITING_HUMAN │
                                      │ da frente     │      (mesmo estado)                      │ pacote + opções│
                                      └──────┬────────┘                                          └───┬──┬──┬──┬───┘
                                   PASS      │  FAIL → REPLANNING                  retomar ─────────────┘  │  │  │
                                             ▼                                     trocar-agente/emendar ──┘  │  │
                                           DONE                                    descartar-ramo ────────────┘  │
                                                                                   abortar → ABORTED ────────────┘
   Em qualquer estado não terminal: budget_soft → WRAPPING_UP → (em voo fechado) → HANDED_BACK
                                    budget_hard / stop humano → WRAPPING_UP (sem novo despacho) → HANDED_BACK
```

### 5.3 Transições (fonte única: `machines.json5 → machines.mandato`)

| Transição | De → Para | Quem dispara | Guardas mecânicas |
|---|---|---|---|
| `propose` | ∅ → PROPOSED | motor (`cs-auto propose --feature|--sprint`) | alvo existe; classe ∈ {feature, risco-com-portões}; spec existe; aceite **executável e vermelho**; nenhum mandato não terminal |
| `approve` | PROPOSED → CHARTERED | humano (único toque) | assinatura sobre spec/aceite/orçamento/rigor/portões; baseline de aceite **e** da suíte de regressão gravado com `output_sha256` |
| `amend` | PROPOSED, AWAITING_HUMAN → PROPOSED/CHARTERED | humano | nova assinatura encadeada à anterior; motivo |
| `plan` | CHARTERED → PLANNING | motor | — |
| `plan_accept` | PLANNING, REPLANNING → RUNNING | motor (após o modelo gravar o DAG) | `dag_acyclic`, `dag_covers_acceptance` (todo critério do mandato ← ≥1 nó), `nodes_in_territory`, `nodes_fit_horizon` (cada task ≤ N arquivos, 1 território), `waves_computed`, `plan_within_budget`, `lessons_consulted` |
| `tick` | RUNNING → RUNNING | motor | despacha o que está pronto (deps ACCEPTED, sem colisão, orçamento) |
| `wave_closed` | RUNNING → INTEGRATING | motor | nenhuma delegação da onda em voo; todas ACCEPTED/BLOCKED/ABSTAINED |
| `integrate_ok` | INTEGRATING → RUNNING | motor | regressão verde vs baseline; `acceptance_green` ≥ anterior; há nó pendente |
| `integrate_replan` | INTEGRATING → REPLANNING | motor | regressão vermelha **ou** aceite sem avanço com DAG esgotado **ou** nó BLOCKED/ABSTAINED |
| `integrate_done` | INTEGRATING → RUNNING(final_review) → DONE | motor + gate | aceite 100% verde; DoD da feature; review final PASS de gate ≠ autores (rigor ≥ standard: cego) |
| `replan_accept` | REPLANNING → RUNNING | motor | `replan_cites_evidence` (E1/E2), `replans_left`, `plan_diff_recorded`, mesmas guardas de `plan_accept`; nós ACCEPTED intocáveis |
| `escalate` | PLANNING, RUNNING, INTEGRATING, REPLANNING → AWAITING_HUMAN | motor | condição da §7 com pacote gravado |
| `resolve` | AWAITING_HUMAN → RUNNING / REPLANNING / PROPOSED / WRAPPING_UP / ABORTED | humano (`cs-auto resolve --choice …`) | escolha ∈ opções do pacote; decisão gravada como evento + `decision` na memória |
| `pause` | RUNNING, INTEGRATING, REPLANNING, PLANNING → PAUSED | motor (`PreCompact`, fim de janela) ou humano | nada em DISPATCHED **ou** delegações em voo marcadas `orphan_watch` |
| `resume` | PAUSED → estado anterior | motor (`SessionStart`) | carimbo confere; órfãs resolvidas (cobrança 1×) |
| `wrap_up` | qualquer não terminal → WRAPPING_UP | motor | `budget_soft` ou `no_progress` ou `stop` humano |
| `hand_back` | WRAPPING_UP → HANDED_BACK | motor | nada em voo; relatório gerado; itens abertos devolvidos ao `backlog/` com motivo |
| `abort` | AWAITING_HUMAN, PROPOSED → ABORTED | humano | motivo |

Toda transição é **evento encadeado** em `events.jsonl` (o motor existente: `engine.commit`). O arquivo
`mandato.json5` vira **visão** do último evento (hash do arquivo = hash do evento, como na árvore de estado,
`docs/ROADMAP-rodada-seguinte.md:190-191`).

### 5.4 O piloto: mecânico × modelo

O loop é do motor. `cs-auto tick` lê o estado e devolve **uma** ação tipada (JSON5, ≤ 30 linhas):

```json5
{mandato: "MAN-003", estado: "RUNNING", frente: "SPR-004 › FEA-009", objetivo: "<1 linha da spec>",
 acao: "DISPATCH", alvo: "FEA-009/02", agente: "dev-auth", model: "sonnet",
 comando: "Agent(description='FEA-009/02 …')", progresso: "aceite 2/5 verdes; onda 2/3",
 orcamento: "despachos 7/20 · tentativas 9/30 · min 41/120 · replanos 1/3",
 por_que: "deps 01 ACCEPTED; sem colisão com 03 (paths disjuntos)"}
```

Ações possíveis: `PLAN`, `WRITE_BRIEF`, `DISPATCH`, `REVIEW`, `REFLECT`, `REPLAN`, `ANSWER_ORPHAN`,
`FINAL_REVIEW`, `ASK_HUMAN`, `REPORT`, `IDLE_WAIT` (aguardar subagente em voo). O hook Stop bloqueia com
`reason = tick.acao + comando` enquanto o estado não for terminal/AWAITING_HUMAN/PAUSED (P19). O objetivo vai
em **todo** tick (anti-deriva, P13).

| Decisão | Mecânico (motor) | Modelo (nó de julgamento) |
|---|---|---|
| Próxima ação | ✔ `tick` | — |
| Decompor a frente em tasks | valida DAG, cobertura, territórios, horizonte | ✔ propõe nós, deps, ACs por nó |
| Ondas | ✔ topologia × coloração de colisão | — |
| Escolher agente/model | território → agente; router recomenda model | pode `override` com motivo (já existe) |
| Brief | valida schema e paths | ✔ escreve goal/contexto/ACs |
| Executar | — | ✔ subagente |
| Verificar task | ✔ roda comando, diff × paths, lições | — |
| Revisar | guarda gate≠autor, model≥autor, enum | ✔ veredito com evidência |
| Progresso | ✔ aceite verde/total, regressão | — |
| Retry/reroute/split | ✔ escolhe a classe de recuperação pela taxonomia (§7.1) | ✔ escreve reflexão e o brief novo |
| Replanejar | ✔ dispara, limita, exige diff + evidência | ✔ propõe vN+1 |
| Escalar | ✔ detecta, monta pacote, congela ramo | ✔ redige o resumo humano (1 tela) |
| Parar | ✔ orçamento, sem progresso, terminal | — |
| Lições | ✔ busca, injeta, promove com sinal | ✔ redige a lição |

---

## 6. Plano em DAG, ondas e despacho sem colisão

### 6.1 Arquivo do plano
`.swarm/state/…/FEA-009-…/plano.v<N>.json5` (gerado pelo motor a partir de `cs-auto plan add-node …`; nunca editado
à mão):

```json5
{mandato: "MAN-003", versao: 2, anterior_sha: "…", motivo: "regressão em tests/test_login.py::test_lockout (E2, out_sha …)",
 nos: [
  {id: "01", tipo: "US", agente: "architect", paths: ["docs/decisoes/ADR-012.md"], deps: [], cobre: ["AC-1"], readonly_produto: true},
  {id: "02", tipo: "US", agente: "dev-auth", paths: ["src/auth/sso.py"], deps: ["01"], cobre: ["AC-1", "AC-2"]},
  {id: "03", tipo: "US", agente: "dev-web",  paths: ["web/login/*.tsx"], deps: ["01"], cobre: ["AC-3"]},
  {id: "04", tipo: "US", agente: "qa",       paths: ["tests/e2e/sso_*.py"], deps: ["02", "03"], cobre: ["AC-1", "AC-2", "AC-3"]},
 ],
 ondas: [["01"], ["02", "03"], ["04"]]}   // calculadas, não digitadas
```

### 6.2 Algoritmo das ondas (mecânico)
```
1. G = DAG(nos, deps). Recusa ciclo (dag_acyclic).
2. camadas = ordenação topológica por nível (Kahn).
3. Para cada camada: grafo de conflito C, aresta (a,b) se scopes_overlap(paths) OU
   par em collision.json5.do_not_parallelize OU mesmo agente (one_in_flight_per_agent).
4. Coloração gulosa de C (maior grau primeiro) → sub-ondas. Ordem estável por id.
5. Teto de paralelismo por onda = min(cfg.max_parallel, orçamento restante de despachos).
```
Decisão de contrato compartilhado (o exemplo Flappy Bird de Cognition, P11) entra como **nó anterior**
(architect/ADR) do qual os paralelos dependem — paralelo nunca decide contrato.

### 6.3 Guardas novas do plano
- `dag_covers_acceptance`: todo critério do mandato aparece em `cobre` de ≥1 nó (anti-plano-que-não-entrega).
- `nodes_fit_horizon`: cada nó ≤ 1 território e ≤ `cfg.max_files_per_task` (proposta: 5 **[sem fonte; calibrar
  pela taxa de rejeição medida]**) — tasks curtas e verificáveis (P18, P15).
- `lessons_consulted`: o motor registrou a busca de memória para o assunto da frente antes do plano.
- `plan_within_budget`: nº de nós × tentativas esperadas ≤ orçamento.

---

## 7. Falha, recuperação e escalada (sem trancar)

### 7.1 Taxonomia de falha → recuperação (o motor escolhe a classe; o modelo executa)

| Sinal (mecânico) | Classe | Recuperação | Limite |
|---|---|---|---|
| Subagente não devolveu submission | transitória | cobrar 1× (SubagentStop já faz); depois `return protocol_failure` | conta 1 tentativa |
| Delegação DISPATCHED de janela morta | órfã | `ANSWER_ORPHAN`: checar diff × paths; sem diff → requeue; com diff → verify | 1 |
| Verify falhou (exit≠0, diff fora dos paths) | task | retry com achados + **reflexão** ancorada na saída (P8, P9) | `attempts` do mandato (default 2) |
| Review FAIL com evidência | task | retry com achados | idem |
| Mesma falha 2× (mesmo teste falhando com mesmo `output_sha256` normalizado, ou mesmo `arquivo:linha` no achado) | task travada | reroute (outro agente do território / architect) **ou** split em REPLANNING | 1 reroute |
| NEEDS_SPECIALIST | task | rotear ao gate pedido | — |
| ABSTAINED `spec_ambiguous` | frente | REPLANNING tenta resolver pela spec/ADR; não resolve → escalada **suave** | 1 |
| ABSTAINED `out_of_territory` | plano | REPLANNING (redistribuir/novo nó) | conta replano |
| Regressão vermelha após onda | integração | REPLANNING com nó FIX que cita o teste | conta replano |
| Aceite sem avanço após DAG esgotado | plano | REPLANNING | conta replano |
| Replanos esgotados | frente | escalada suave | — |

"Mesma falha" deixa de ser Jaccard de prosa (D7) e passa a ser **assinatura do sinal externo**: (comando, teste
que falhou, hash normalizado da saída) ou (`arquivo:linha`, regra) do achado.

### 7.2 Escalada graduada

| Tipo | Condições | Efeito |
|---|---|---|
| **Dura global** | tentativa de alterar spec/teste de aceite/verificador congelado; `risco` descoberto sem portão aprovado; guard desligado; violação de território repetida | AWAITING_HUMAN; **todo** despacho congelado; em voo termina e é verificado, não aceito |
| **Dura local** | nó precisa **escrever** em invariante/área congelada (detectado no brief ou no diff, não por mera citação — corrige D7) | AWAITING_HUMAN; congela o nó e seus descendentes; o resto do DAG continua |
| **Suave** | ambiguidade material, replanos esgotados, conflito de gates sem evidência, `scope_expansion` | idem dura local; se não sobrar nó executável, o mandato inteiro aguarda |

O pacote (`escalada-<ts>.json5`) traz: condição, evidência (comandos + `output_sha256`, `arquivo:linha`),
ramo congelado, o que segue rodando, e **opções fechadas** com consequência:

```
retomar          → o nó volta a BRIEFED (com a decisão humana anexada ao brief)
trocar-agente    → reroute para <agente>, nova delegação
emendar          → amend da spec/aceite/orçamento (nova assinatura) → PROPOSED → CHARTERED
descartar-ramo   → nós congelados viram DROPPED com motivo; critérios órfãos → relatório (entrega parcial)
encerrar         → WRAPPING_UP → HANDED_BACK
abortar          → ABORTED (restaura ao ponto seguro, ver §8.3)
```

### 7.3 Correção do bug ESCALATED nas máquinas existentes
- M2 `delegation`: ESCALATED e ABSTAINED **saem** de `terminal`; novas transições
  `resume: ESCALATED|ABSTAINED → BRIEFED` (guardas `decision_recorded`, `brief_valid`),
  `reroute: ESCALATED|ABSTAINED → REROUTED` (`new_agent_valid`), `drop: ESCALATED|ABSTAINED → DROPPED`
  (`reason_present`; estado novo terminal), e `drives_task` com `DROPPED: "DROPPED"`.
- `pipeline_satisfied` deixa de aceitar ESCALATED como "satisfeito" quando há mandato ativo (corrige D9):
  satisfeito = ACCEPTED ou DROPPED com motivo.
- O teste de vivacidade passa a cobrir `machines.mandato` com `AGUARDANDO_HUMANO = {"delegation": {ESCALATED,
  ABSTAINED}, "mandato": {AWAITING_HUMAN, PAUSED}}`.

---

## 8. Checkpoint, retomada e janelas

### 8.1 Checkpoint
- **Toda** transição de M5 e M2 já é evento; o checkpoint é o próprio evento + regeneração da visão (P14).
- Além disso, `cs-session save --auto` em: `wave_closed`, `escalate`, `pause`, `PreCompact` (hook), e a cada K
  ticks **[K sem fonte; proposta 10]**.
- Diário de progresso gerado (não escrito pelo modelo): `mandato.diario.json5` com uma linha por transição
  (o *progress file* de P5, mas mecânico).

### 8.2 Retomada
- `SessionStart` (`source: startup|resume|compact`, P19) chama `cs-auto status --brief`: estado, frente, objetivo,
  progresso, orçamento, **próxima ação com comando**. Em mandato PAUSED: transição `resume` automática se o
  carimbo confere; senão mostra o delta (mecanismo de `cs-session load`, `ARCHITECTURE.md:237-242`).
- Delegações DISPATCHED encontradas na retomada → `ANSWER_ORPHAN` (§7.1).
- Idempotência: nó retomado reexecuta do começo (como LangGraph, P14) — por isso despacho e verify são idempotentes
  por `(delegação, tentativa)`.

### 8.3 Ponto seguro
- `approve` grava o HEAD e a lista de arquivos sujos. Cada onda integrada grava `safe_point` (hash da árvore após a
  integração verde). `abort` não reescreve a árvore sozinho (o guard proíbe reescrita, `guard.py:229-230`): o relatório
  dá o comando exato para o humano restaurar ao último `safe_point`. **Sem push, merge ou commit em branch protegida**
  (mantido).

---

## 9. Orçamento e critérios de parada

### 9.1 Dimensões (todas medidas pelo motor)

| Dimensão | Fonte da medida | Hoje |
|---|---|---|
| despachos | eventos `delegation.dispatch` | tasks com attempts>0 (D8) |
| tentativas totais | eventos `delegation.retry` + dispatch | só por task |
| replanos | eventos `mandato.replan_accept` | não existe |
| minutos **ativos** | soma de intervalos entre `resume`/`pause`/ticks com gap ≤ G | relógio de parede (D8) |
| custo | router: model **medido** na transcrição (`guard.py:400-409`) × tabela de preço; sem medida → estimativa marcada | `spend` autodeclarado (D8) |

### 9.2 Derivação do orçamento (proposta, não decorar)
Motor propõe em `propose`: `despachos = nós_estimados × 1,5`, `tentativas = despachos × 2`, `replanos = 3`,
`minutos = nós × mediana medida de minutos/task do repo (router.stats) × 1,5`. Coeficientes **[sem fonte;
calibrar com o histórico do próprio repo]**. Esforço proporcional como regra explícita (P4).

### 9.3 Parada (mecânica, em ordem de precedência)
1. Terminal (DONE/HANDED_BACK/ABORTED) → deixa parar.
2. AWAITING_HUMAN sem nó executável, ou PAUSED → deixa parar com o pacote/brief impresso.
3. `budget_hard` (100% de qualquer dimensão) → WRAPPING_UP: nenhum despacho novo; termina o que está em voo.
4. `budget_soft` (80%) → WRAPPING_UP com prioridade a fechar nós que completam critérios quase verdes.
5. **Sem progresso**: `k` integrações seguidas sem aumentar `acceptance_green` **e** sem nó novo ACCEPTED
   (proposta k=2 **[sem fonte]**) → REPLANNING uma vez; persistiu → WRAPPING_UP. Substitui `event_count` (D6).
6. Bloqueios do Stop sem transição de M5/M2 (anti-loop do hook) ≥ 3 → `pause` com diagnóstico (não escalada).

HANDED_BACK sempre devolve os nós abertos ao `backlog/` com motivo (alinha com fechamento de sprint,
`ROADMAP-rodada-seguinte.md:183`). Entrega parcial é resultado legítimo e marcado (P21).

---

## 10. Memória e lições

```
 PLANNING ──▶ cs-mem search "<objetivo + territórios>" (motor) ──▶ top-k lições anexadas ao contexto do PLAN
     │                                                             e aos briefs (lessons_check_pass já existe)
 REJECT ───▶ REFLECT: modelo escreve 3 linhas {o que falhou, por quê (cita saída/linha), o que muda}
     │        guarda: reflexão sem citação do sinal externo é recusada (P8)
     │        grava como episódio da task; entra no brief do retry (P9)
 ACCEPT após retry ─▶ reflexão vira LIÇÃO CANDIDATA (sinal: o retry passou no mesmo comando)
 resolve humano ───▶ decisão gravada (decision) — vale como lição ativa no escopo
 DONE/HANDED_BACK ─▶ consolidação: candidatas com ≥2 confirmações → ativas; o resto expira
```
Nada é promovido por autoavaliação (P21: "não rotule você mesmo os seus achados").

---

## 11. Faixas e árvore de estado

### 11.1 Faixas
| Faixa | No autônomo |
|---|---|
| consulta (`pergunta`) | **Permitida dentro** do mandato como nó `readonly` (pesquisa de planejamento), conta no orçamento de despachos; nunca abre mandato. |
| avulsa (`trivial`, `pequena`) | **Não abre mandato** (custo > benefício, P1/P15). `propose` com plano de 1 nó é recusado com "use task avulsa". Durante o mandato, uma avulsa do usuário é recusada se colidir com paths do DAG ativo. |
| completo (`feature`) | Caminho normal do mandato. |
| completo (`risco`) | Hoje recusado (`autonomy.py:78-79`). Proposta: permitido **só** com `portoes` declarados na proposta (nós de risco listados); cada nó de risco vira AWAITING_HUMAN antes do dispatch (portão), o resto roda. Sem lista → recusa como hoje. |

### 11.2 Árvore (épico → sprint → feature → task; `ROADMAP-rodada-seguinte.md:25-52`)
- Alvo do mandato: `--feature FEA-n` **ou** `--sprint SPR-n`. Épico nunca é alvo (objetivo grande demais para um
  mandato; P18).
- Mandato de sprint = fila de features na ordem do backlog; **uma feature ativa por vez** (regra ONE-FEATURE): o
  motor fecha (`close feature`, DoD) ou estaciona (`park --reason`) a atual antes de `start` da próxima; cada
  feature tem seu PLANNING próprio com DAG próprio. Tasks da sprint sem feature (caso C) entram como uma
  "feature implícita" só para o plano.
- Tasks paralelas sem colisão dentro da feature ativa = ondas da §6.
- Story simples/composta: nó do DAG = task; story composta = subgrafo com as tasks de cada agente.
- Escritas em `.swarm/backlog|state|archive` só pelo motor (cenário da rodada seguinte, `:241`).
- Sem a árvore pronta (ordem de entrega), M5 roda sobre o board atual com `scope_tasks` (feature → stories → tasks).

---

## 12. Cenários de aceite (oráculo para a `/auto-correcao`)

Todos com CLI real + guard real em repo temporário (estilo WORKFLOW-E2E de `PROXIMA-RODADA.md:155-161`); cada
caminho termina com `validate --strict` OK. Entram antes do freeze; nenhuma frente os edita.

| Id | Cenário | Esperado |
|---|---|---|
| AUTO-LIVE | teste de vivacidade estendido a `mandato` | nenhum estado sem saída fora de terminal; AWAITING_HUMAN/PAUSED não terminais com saídas `resolve`/`resume`; todos alcançáveis; ESCALATED/ABSTAINED de M2 com retomar/trocar/descartar |
| AUTO-START-1 | `propose` com aceite já verde / inexistente / sem spec | recusa com mensagem acionável (mantém `autonomy.py:69-91`) |
| AUTO-START-2 | `propose` com plano de 1 nó | recusa "use task avulsa" |
| AUTO-PLAN-1 | DAG com ciclo / critério do mandato sem nó que o cubra / nó fora do território | `plan_accept` recusado com o problema exato |
| AUTO-PLAN-2 | 4 nós, deps 01→{02,03}→04, 02 e 03 disjuntos | ondas calculadas `[[01],[02,03],[04]]`; 02 e 03 despacham em paralelo |
| AUTO-PLAN-3 | 02 e 03 tocam o mesmo arquivo (ou par `do_not_parallelize`) | ficam em sub-ondas diferentes, sem intervenção do modelo |
| AUTO-HAPPY | feature pequena, aceite vermelho, 3 nós | DONE sem toque humano após `approve`; aceite verde executado pelo motor; review final de gate ≠ autor; relatório cita `output_sha256` |
| AUTO-RETRY | verify falha 1× | REFLECT exigido; reflexão sem citação da saída é recusada; retry passa; lição candidata gravada |
| AUTO-SAME-FAIL | mesmo teste falha 2× com mesma saída normalizada | reroute ou REPLANNING (não retry 3) |
| AUTO-REPLAN-1 | todos os nós ACCEPTED, aceite 2/3 verde | INTEGRATING → REPLANNING (não para em silêncio — regressão de D4); `replan_accept` exige evidência e diff; nós ACCEPTED intocados |
| AUTO-REPLAN-CAP | replanos esgotados | escalada suave com opções |
| AUTO-REGRESS | onda quebra teste verde no baseline | INTEGRATING → REPLANNING com nó FIX citando o teste |
| AUTO-ESC-LOCAL | 1 nó precisa escrever em área congelada; outro ramo independente | ramo congelado, ramo independente segue até ACCEPTED; AWAITING_HUMAN só quando não sobra nó executável |
| AUTO-ESC-CITE | brief só **cita** invariante, sem escrever | **não** escala (regressão de D7) |
| AUTO-ESC-RESOLVE | de AWAITING_HUMAN, cada opção: retomar, trocar-agente, emendar, descartar-ramo, encerrar, abortar | cada uma leva ao estado da §7.2 com evento + decisão gravada; nenhuma tranca |
| AUTO-HACK | subagente tenta editar teste de aceite / spec / verificador | guard bloqueia; escalada dura global; aceite inalterado (hash) |
| AUTO-BUDGET-SOFT | 80% de despachos | WRAPPING_UP: nenhum despacho novo; em voo fecha; HANDED_BACK com abertos no `backlog/` e motivo |
| AUTO-BUDGET-TIME | pausa de 8 h entre janelas | minutos ativos não contam a pausa |
| AUTO-USD | tentativa de `spend` manual | recusada ou marcada `autodeclarado`; custo vem do router medido |
| AUTO-NOPROG | 2 integrações sem aumento de aceite e sem nó novo ACCEPTED | 1 REPLANNING; persistindo, WRAPPING_UP (não escala por contagem de evento) |
| AUTO-RESUME | janela encerrada com 1 delegação DISPATCHED | `SessionStart` → `resume`; órfã tratada (diff verificado ou requeue); sessão nova sem histórico executa o 1º passo só com `cs-auto status --brief` |
| AUTO-COMPACT | `PreCompact` durante RUNNING | `pause` + checkpoint; após compactação, `resume` com o mesmo próximo passo |
| AUTO-STOPHOOK | modelo tenta parar em RUNNING com nó pronto | Stop bloqueia com a ação do tick; em AWAITING_HUMAN/PAUSED/terminal deixa parar |
| AUTO-SPRINT | mandato de sprint com 2 features | uma feature ativa por vez; a 1ª fecha (DoD) antes da 2ª `start`; tasks paralelas só dentro da ativa |
| AUTO-LANE | `ask` durante o mandato | consulta readonly permitida e contada; avulsa que colide com DAG ativo recusada |
| AUTO-RISK | classe `risco` com portões declarados | nós de risco param em AWAITING_HUMAN antes do dispatch; demais rodam; sem portões → recusa |
| AUTO-TAMPER | `mandato.json5` ou `plano.vN.json5` editado à mão | `validate` acusa (hash ≠ último evento) |
| AUTO-E2E | do `propose` ao DONE com uma escalada no meio e uma retomada de janela | `validate --strict` OK; relatório com tudo verificado e nada "pulado calado" |

---

## 13. Riscos

| Risco | Mitigação |
|---|---|
| Custo multiagente alto (~15× chat, P4) | autônomo só na faixa completa; orçamento derivado e medido; consulta e avulsa fora |
| Reward hacking (P7) | hash + guard em spec/aceite/verificador; regressão contra baseline; review cego; "não trapaceie" não é controle |
| Plano que não entrega (cobre tasks, não critérios) | `dag_covers_acceptance`; DONE só por aceite executado |
| Paralelo com decisão implícita conflitante (P11) | contrato vira nó anterior; paralelo só com paths disjuntos e sem par de colisão |
| Replano infinito / deriva (P13) | cap de replanos; diff obrigatório; nós ACCEPTED imutáveis; objetivo em todo tick |
| Escalada demais (atrito) ou de menos (perigo) | graduada dura/suave/local; cenários AUTO-ESC-CITE e AUTO-HACK fixam as duas bordas |
| Hook Stop prende o usuário | Stop nunca bloqueia em AWAITING_HUMAN/PAUSED/terminal; `cs-auto pause` sempre disponível ao humano |
| Coeficientes sem fonte (orçamento, k, K, 80%) | marcados; calibrar com `router.stats` e medir taxa de rejeição por tamanho de task |
| Complexidade do motor cresce | M5 na mesma fonte (`machines.json5`) e no mesmo `engine.commit`; nada de motor paralelo |
| Plataformas sem hook Stop (Cursor/Copilot/Codex) | `cs-auto tick` funciona como comando; sem hook vira "modo semi-autônomo" (o modelo chama tick); registrar no ledger de premissas o nível de enforcement por plataforma |

---

## 14. O que NÃO fazer

- Não deixar o modelo ser o loop ("siga `next` até REPORTING"): o loop é `cs-auto tick`.
- Não manter o mandato fora de `machines.machines` nem mudar estado por `save()` sem evento.
- Não declarar ESCALATED/ABSTAINED/AWAITING_HUMAN terminal; não fazer "parar" ser a única saída.
- Não medir progresso por contagem de eventos, nem orçamento por autodeclaração.
- Não escalar por **citação** de invariante; escalar por **escrita** prevista ou detectada.
- Não congelar a frente inteira por um ramo local.
- Não pedir "reflita e tente de novo" sem anexar a saída do comando/veredito (P8).
- Não paralelizar nós que decidem contrato; não digitar o número da onda.
- Não permitir que o plano ou o replano toque nó ACCEPTED, spec ou teste de aceite.
- Não dar autonomia a avulsa/consulta; não fazer épico como alvo.
- Não push, merge, commit em branch protegida, nem reescrita de árvore pelo motor (mantido).
- Não promover lição por autoavaliação.
- Não copiar a estrutura do v8 por existir (regra da rodada seguinte, `ROADMAP-rodada-seguinte.md:7-11`).
- Não usar números sem fonte como se fossem medidos: todo coeficiente desta proposta é calibrável e marcado.

---

## 15. Ordem sugerida de entrega (para a auto-correcao)

1. Vivacidade verde (inclui o conserto de M2 ESCALATED/ABSTAINED e dos 2 testes hoje vermelhos) — pré-requisito.
2. M5 em `machines.json5` + eventos + visão `mandato.json5` + `cs-auto propose|approve|status|resolve|pause|resume`.
3. Plano DAG + guardas + cálculo de ondas.
4. INTEGRATING (regressão + aceite) + REPLANNING + progresso por aceite.
5. Taxonomia de falha, escalada graduada, pacote com opções.
6. Orçamento medido + WRAPPING_UP/HANDED_BACK.
7. `tick` + hook Stop/SessionStart/PreCompact.
8. Memória (busca, REFLECT, promoção).
9. Mandato de sprint sobre a árvore (depende da rodada seguinte).
Cada passo entra só com os cenários AUTO-* correspondentes verdes.
