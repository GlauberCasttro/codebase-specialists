# ESPEC — feature harness-dev: o harness de DESENVOLVIMENTO da skill, comando a comando

Pedido do founder (literal): "Quero todas, inclusive a auto-correcao que seja da própria skill." · "Avalie comando a
comando no harness de referência; o criar-feature é muito rico e você criou extremamente pobre. Refaça o trabalho mal
feito." · "Use scripts mecânicos para apoiar a prosa e reduzir custos, para não depender de prosa de agentes." ·
"Adaptando para a necessidade da nossa skill." · "Tudo isso é para o DESENVOLVIMENTO da skill, não para o motor da
skill." · "Pode manter em português os comandos."

Oráculo: `test_harness_dev.py` (esta pasta), unittest puro, Python 3.9+, 103 testes, nos 2 Pythons.
Rodar: `cd campanhas/harness-dev/oraculo && python3 -m unittest -v test_harness_dev` (idem `/usr/bin/python3`).
Base (projeto atual): 4 passam / 97 falham em cada Python — ver `base.txt`.

Sumário: §0 o que foi lido · §1 escopo e fronteira · §2 comando a comando (a inventário · b distância · c adaptação ·
d script) · §3 contrato mecânico (CLIs, formatos, códigos) · §4 o que o oráculo testa · §5 grupos do corretor ·
§6 portão e critério de parada · §7 mudanças oficiais · §8 decisões para o founder · §9 limites honestos.

---

## §0 O que foi lido (por inteiro, só leitura)

**Harness de referência** (um aplicativo Python de outro projeto do founder; aqui só "harness de referência"):
`CLAUDE.md`, `.claude/settings.json`, `.claude/hooks/{guard-git-destrutivo.sh, guard-local-feature-state.py}`,
`.claude/INSTALLATION.md`, as 8 skills (`carregar-sessao` 287 linhas, `salvar-sessao` 270, `criar-feature` 468 +
`tools/checar-complexidade.py`, `fechar-feature` 382, `tech-lead` 662 + `references/{aprovacao-com-recomendacao,
executor-prompt, reviewer-prompt, linhagem-ruflo}.md` + `tools/custo-despacho.py` + `hooks/exige-modelo.py`,
`rh` 159 + `references/{personas, esqueleto-prompt}.md` + `evals/evals.json` + o workspace de avaliação com `grade.py`,
`revisor-<app>` 38, `e2e-loop` 41), `references/po-task-contract.md`, `tools/{feature_flow.py,
guard-po-task-schema.sh, guard-close-complete.sh, session-stamp.sh, run_project_checks.py}`,
`tools/local_feature_flow/` (motor JSON: `creation.py`, `archive.py` e cabeçalhos dos demais — inativo no app,
mas é de onde vem o vínculo aprovação ↔ sha da proposta), e a árvore real do estado (WORKFLOW, RESUME, BACKLOG,
DECISIONS, LAST_DELIVERY, WORKTREE_PRESERVADO, PLANS/, CURRENT_FEATURE/{FEATURE, INDEX, HISTORICO, CHECKLIST,
TASKS/}, archive/, logs/) — usada só como FORMATO; nenhum conteúdo do app foi copiado.

**Harness atual do projeto**: `.claude/CLAUDE.md`, `settings.json`, as 6 skills (`load-session`, `save-session`,
`new-front`, `close-front`, `package`, `install`), `tools/*` (carimbo, copia, portao, portar, conferir-commit,
script-aprovacao, guard-entrega, guard-git, guard-privacidade, package, instalar, publicar_regras…), o motor
embutido `tools/ac/{ac.py, frase.py, hook_aprovacao.py, references/*.json5, ORIGEM.txt}`, `tools/tests/
test_harness_dev.py` (53 testes) e `.claude/state/*`. **Skill auto-correcao** (`SKILL.md`, `references/*.json5`,
`docs/01..07`).

**Medido**: as 6 skills atuais somam 117 linhas; as 8 do harness de referência somam 2.307 linhas + 7 referências +
3 scripts. O `new-front` atual tem 25 linhas, nenhuma aprovação entre etapas, nenhum checklist, nenhum contrato de
task e nenhuma validação; o `criar-feature` tem 5 portões com aprovação literal registrada, checklist append-only,
investigação medida, contrato validado pelo guard real numa sandbox com sonda negativa, gramática de nome de task,
complexidade checada por script e abertura em 8 escritas ordenadas. É essa distância que esta feature fecha.

---

## §1 Escopo e fronteira (só desenvolvimento)

- Muda só o **harness de desenvolvimento**: `.claude/CLAUDE.md`, `.claude/settings.json`, `.claude/skills/**`,
  `.claude/tools/*.{py,sh,json}`, `.claude/tools/tests/*.py`. Estado (`.claude/state/**`) é escrito pelos scripts em
  uso, não pela feature.
- **Não muda**: o motor embutido `.claude/tools/ac/**` (byte a byte igual à `ORIGEM.txt`; teste
  `Ajuda.test_motor_embutido_intacto`), `.claude/package/**` e **nada do produto**.
- **Produto** (o que o oráculo exige idêntico ao `HEAD`): `SKILL.md`, `MODO-DE-USO.md`, `VERSION`, `LICENSE`,
  `scripts/**`, `assets/**`, `references/**`, `docs/**`, `evals/**`, `.claude/package/**`
  (`Fronteira.test_produto_identico_ao_head`: blob a blob contra o `HEAD` do repositório desta pasta; numa cópia,
  nenhum arquivo novo nessas pastas).
- **Pacote limpo** (`Fronteira.test_pacote_sem_nada_do_harness`): `package.sh --worktree --sem-validar` numa cópia;
  nenhum caminho `.claude/`, nenhum `SKILL.md` fora da raiz, nenhum arquivo (>200 bytes) com o mesmo conteúdo de um
  arquivo de `.claude/`.
- **Suítes do produto verdes**: garantidas pelo portão (§6), não pelo oráculo (o oráculo é rápido: ~70 s).
- **Paralelismo**: a feature iter18 (outra sessão) está em curso com escopo só de produto; os escopos são disjuntos
  (`ac.py --work campanhas/harness-dev overlap --other campanhas/iter18` tem de dar 0 antes de abrir). Nada aqui toca
  `campanhas/iter18/`.

---

## §2 Comando a comando

Formato de cada seção: **(a)** inventário fiel do harness de referência · **(b)** o que existe aqui e a distância ·
**(c)** adaptação MANTÉM / ADAPTA / DESCARTA, com o porquê · **(d)** o que vira script (§3 tem o contrato exato) e o
que fica julgamento do agente.

Regra transversal (D-01 do founder): **Markdown explica, script decide.** Toda decisão mecânica (transição de
estado, checklist, contrato, completude, archive, ficha, plano/modo, régua, frescor, custo, roteamento) é um script
com `--help`, `--dry-run` quando escreve, `--json` e `--brief` (≤ 40 linhas) quando informa. A skill não embute
código (sem heredoc, `python3 -c`, `def`, laço shell — `Skills.test_skills_finas_sem_logica_embutida`) e só chama
scripts que existem com subcomandos que existem (`Skills.test_scripts_citados_existem_e_subcomandos_existem`).
Comandos em português (decisão do founder nesta feature). Os 4 ingleses (`load-session`, `save-session`,
`new-front`, `close-front`) são **substituídos**, sem duplicar.

### 2.1 criar-feature (≙ criar-feature)

**(a) Inventário do criar-feature.**
- Gatilhos e objetivo: demanda solta → feature completa (FEATURE rico + TASKS + INDEX + HISTORICO + WORKFLOW
  IN_PROGRESS) em **5 etapas com aprovação explícita** entre cada uma; retomável; nunca commita.
- Regras que valem nas 5 etapas: uma feature ativa por vez (D11, inviolável, sem override); **medir antes de
  afirmar** (arquivo/linha/contagem); **amostra não é auditoria** (declarar exclusões); não avançar sem aprovação
  (`ok` avança · `ajustar` refaz · `pausar` grava e encerra); nunca commitar; nada de código de produto.
- **CHECKLIST.md**: primeira escrita depois da E0; é progresso visível, fonte de retomada e registro de aprovação.
  Caixa E1–E5 só com aprovação **literal** registrada; handoff **append-only** (Produzido · Medido · Aprovação
  literal · Próxima); rejeição registrada sem marcar a caixa; retomada lê o checklist (a primeira caixa vazia é a
  etapa corrente); o checklist sobrevive até o fechamento, que o consome no archive.
- **E0** (gate mecânico): estado existe? (senão salvar-sessao inicializa); WORKFLOW IDLE? (ativo ⇒ ABORTA sem
  escrever nada, nem o checklist); só dois casos válidos: nova criação ou retomada coerente.
- **E1** analisar: Demanda literal · Problema por trás · O que NÃO é · Perguntas abertas (≤3, só as que mudam o
  desenho) · FEATURE-ID (`FEAT-{CODE}-{slug}`). Para.
- **E2** investigação medida: inventário com contagem · classificação com soma fechando · exclusões declaradas ·
  achados F1.. com arquivo:linha (descartados ficam registrados) · enforcement existente. Para.
- **E3** FEATURE.md (Bloco A: ID, nome, história Como/quero/para, problema com evidência, valor, personas, CAs
  DADO/QUANDO/ENTÃO, RNFs, edge cases, dependências, escopo IN/OUT, métrica, aceites PENDENTE) validado pelo **guard
  real** numa sandbox, com **sonda negativa** (board sem Goal tem de ser bloqueado) e Bash ≥ 4; NOT_RUN nunca é PASS;
  na E3 só "CA órfão" pode esperar a E4. Para.
- **E4** tasks: um arquivo por task, gramática `{NN}-{TIPO}-{DESCRICAO}` (`TASK|BUG|GAP|DEBT`, NN nunca
  reutilizado, QA/REVIEW com `feature: QA|REVIEW`); schema completo (cabeçalho + Goal com o que NÃO fazer, Contexto
  com âncora real, Subtasks 2–5, Invariants, Scope IN/OUT, Arquivos permitidos exatos — nunca `src/**`, AC, DoD,
  Verificação concreta — nunca ls/echo/TBD, Handoff); todo CA coberto; mesmo arquivo em 2 tasks ⇒ serializar;
  grafo `depends` entregue; `complexidade: baixa` só se o checador mecânico confirmar. Guard real em exit 0 +
  revisão individual. Para.
- **E5** abertura: apresenta o plano concreto e para; com o ok, escreve **nesta ordem**: INDEX (depends com o
  porquê), HISTORICO ([NOTA] com o medido na E2), log da feature, DECISIONS, BACKLOG, CHECKLIST (E5 OK), WORKFLOW
  IN_PROGRESS, RESUME (carimbo por último). Não chama salvar-sessao, não inicia execução.
- Aprovação com recomendação (referência do tech-lead): cada pergunta vem com `→ recomendo` + motivo (medido ou
  hipótese) + alternativa; `ok` aceita o conjunto, registrado item a item.

**(b) O que existe aqui e a distância.** `new-front` (25 linhas): `ac.py init` + linha no WORKFLOW + oráculo +
script de aprovação + cópia. **Não tem**: nenhuma das 5 aprovações, nenhum checklist, nenhuma investigação, nenhum
documento de feature (o "problema" é uma string no `--problem`), nenhum CA, nenhuma task, nenhum contrato, nenhuma
validação, nenhuma retomada, nenhuma regra de quantas features. A feature nasce numa tacada só — exatamente o defeito
que o criar-feature existe para impedir. Pobre em tudo, menos na campanha.

**(c) Adaptação.**
| item | decisão | porquê |
|---|---|---|
| 5 etapas com aprovação literal, checklist append-only, retomada pelo disco | MANTÉM | é o mecanismo inteiro |
| aprovação ligada ao **sha da proposta** (do motor JSON da referência) | ADAPTA (fica mais forte) | caixa marcada à mão vira detectável; proposta alterada depois do ok bloqueia a abertura |
| medir antes de afirmar, exclusões, achados F1.. | MANTÉM, e E2 validada por script (achado precisa de `arquivo:linha`) | prosa de agente não basta |
| FEATURE.md → **FEATURE.md**, FEAT-ID → id da feature = nome da campanha (`^[a-z][a-z0-9]*(-[a-z0-9]+){0,5}$`, como `iter18`, `harness-dev`) | ADAPTA | a feature É a campanha `campanhas/<id>/` |
| Bloco A | MANTÉM + acrescenta **Prova executável por CA**, **Escopo de escrita** (vira `--scope`), **Critério de parada com número** (vira `--stop`) | o critério de aceite tem de rodar; a campanha nasce do documento |
| tasks | ADAPTA: tipos **ORACULO** (por agente separado, só escreve em `campanhas/<id>/oraculo/`), **CORRECAO** (grupo G1..G3, dentro do escopo, depende do oráculo, nunca toca o oráculo), **QA** (portão + oráculo), **REVIEW** | quem testa não constrói; ≤3 grupos disjuntos é a regra do motor (L09/L17) |
| guard real em Bash ≥4 numa sandbox com nomes canônicos de outro produto | ADAPTA: `contrato.py` em Python stdlib, nos 2 Pythons, com `--sonda` própria | o guard de referência só existe por causa de outro produto; aqui um script único é a Lei (sem cópia que derive) |
| complexidade baixa (≤2 arquivos, sem área sensível, sem texto de protocolo, verificação concreta) | MANTÉM; "sensível" = `.claude/tools/ac/`, guard, hook, frase, `scripts/harness/`; "protocolo" = `.claude/skills/`, `.claude/CLAUDE.md`, `.claude/state/`, `SKILL.md`, `references/` | é o sinal que roteia haiku |
| uma feature ativa por vez (D11) | ADAPTA: **limite em `regras.json`** (`max_features_ativas` ∈ {1,2}; recomendo 2) + uma criação por vez + colisão provada por `ac.py overlap` na abertura | este projeto já roda features disjuntas em paralelo (L17); a disjunção é provada, não presumida — **decisão do founder** (§8) |
| abertura | ADAPTA: `ac.py init` (escopo e parada do FEATURE.md) + overlap + INDEX/HISTORICO/log/features.json/WORKFLOW/README de campanhas, sem commit; o **oráculo** é a task 01 (agente separado), depois `oracle freeze`, depois `script-aprovacao.sh` (que passa a **exigir oráculo congelado**); o founder aprova com a senha no terminal dele; correção só depois disso | é o fluxo de campanha, agora encadeado e verificado |
| DECISIONS/BACKLOG na abertura | MANTÉM como julgamento (o agente escreve à mão) | curadoria |
| cópia Codex (`.agents/`), NORM/held-out do app, navegador, cookies, servidor, `src/` | DESCARTA | é do app de referência |

**(d) Script.** `feature.py criar iniciar|propor|aprovar|rejeitar|abrir`, `feature.py checklist`, `feature.py status`,
`contrato.py feature|completo|etapa|complexidade|--sonda`, `guard-estado.py` (hook). Julgamento do agente: o conteúdo
de cada etapa (análise, investigação, FEATURE.md, tasks), as recomendações, DECISIONS e BACKLOG.

### 2.2 fechar-feature (≙ fechar-feature)

**(a) Inventário.** Contrato de artefatos e "pode/não pode"; **definição de archive completo** (existe, >0 bytes,
único na pasta, `### CA-NN` por CA, as duas linhas de aceite, marcador na última linha); E0 detecção (nada a fazer /
normal / retomada; FEATURE-ID resolvido sem adivinhar); **E1 gate bloqueante sem escrita**: completude cruzada
`N_index == N_disco == N_done`, aceite QA ACCEPT e Review APPROVED, `[GATE] PASS` por task; E2 documento único
(resumo, CAs, linha do tempo, tasks, como nasceu — do checklist, decisões, aprendizados, **Arquivos da feature**,
aceite, marcador em escrita separada; fontes baratas primeiro; fallback se o log sumiu); E3 LAST_DELIVERY com
`**Feature-ID:**` na primeira linha do corpo; E4 BACKLOG (julgamento); E5 limpeza **só com archive validado**; E6 log
removido; E7 gate G2 real numa sandbox + IDLE em **escrita única** + RESUME; **commit só da feature** num índice
temporário (stage de terceiros intocado; DECISIONS só explícito); E8 sinalizar; idempotente por pós-condição.

**(b) Distância.** `close-front` (31 linhas): portão → portar → conferir-commit → privacidade → commit → fechar a
campanha → WORKFLOW/README → install. **Não tem**: gate de aceite (QA/Review), completude cruzada, archive,
LAST_DELIVERY, limpeza, transição de estado verificável, idempotência por pós-condição, retomada, commit em índice
temporário (hoje `git add` no índice real: stage de terceiros entraria). Tem o que o de referência não tem: portão,
conferir-commit, campanha, install.

**(c) Adaptação.** MANTÉM: gate sem escrita, completude cruzada, archive único com marcador, nada apagado antes do
substituto validado, LAST_DELIVERY, IDLE por último, commit só da feature em índice temporário, nunca push,
idempotência. ADAPTA: o gate inclui **portão VERDE** (`local/portao-<id>/portao.out`), **conferir-commit** e a
**aprovação do founder na campanha** (`ac.py check intake.3`); o commit exige a **pré-autorização** (`ac.py check
integracao.3`) e roda a privacidade; o archive ganha `## Campanha` e `## Oráculo`; "Arquivos da feature" = arquivos
das tasks CORRECAO (o oráculo e o estado entram no commit por lista própria); o fechamento da campanha
(`campanha.py fechar` + `frase conferir` do founder) faz parte do ritual; ao fim, `install`. DESCARTA: sandbox
sandbox de nomes canônicos e tradução de vocabulário (o G2 aqui é o próprio script), held-out/NORM do app.

**(d) Script.** `feature.py fechar plano|check|archive|entrega|limpar|idle|commit`. Julgamento: notas do archive
(Resumo, Decisões técnicas, Aprendizados), curadoria do BACKLOG, mensagem do commit.

### 2.3 carregar-sessao (≙ carregar-sessao)

**(a)** Âncora primeiro (2 leituras no caminho feliz, +INDEX com feature ativa; nunca logs); **carimbo** só com
campos comparáveis (FEATURE, BRANCH, HEAD, NORM, FEAT, GATE) saído de **um script dono da fórmula**; **HEAD por
regra** (igual, ou avançou só com commit do carve-out); veredito bate / cache-miss (self-heal do RESUME, rodapé de
1 linha) / só NORM-GATE mudou (avisa held-out PENDENTE); briefing em **duas sequências** (macro features com o porquê
na 2ª linha; micro tasks com `← PRÓXIMA`, porquê do elo entre parênteses, `[x]` só para DONE, `k/t` obrigatório);
**gate "Retomo daqui?"**; git só leitura; branch divergente é sinal.

**(b)** `load-session` (19 linhas): carimbo (informativo, não comparável), lê RESUME/WORKFLOW, `ac.py status`,
portão, "VALE o script". **Não tem**: carimbo comparável, veredito de frescor, HEAD por regra, self-heal, briefing
macro/micro, `← PRÓXIMA`, gate de retomada, meta de custo.

**(c)** MANTÉM tudo do protocolo. ADAPTA os campos: FEATURES (ativas), BRANCH, HEAD, **PRODUTO** (hash da árvore do
produto — é o que o portão mede), **ESTADO** (hash de `features.json` + `features/**`), GATE (portão VERDE das ativas);
carve-out do HEAD = `.claude/state/` e `campanhas/`. O `carimbo.sh` atual continua como âncora informativa do
SessionStart (texto passa a apontar `carregar-sessao`). DESCARTA: Codex, NORM do app, `tests/runs/HELD_OUT.ok`.

**(d)** `sessao.py frescor|briefing|carimbo`. Julgamento: nenhum além de responder e parar.

### 2.4 salvar-sessao

**(a)** Papéis distintos (RESUME sobrescreve; log apensa ≤20 linhas; WORKFLOW sobrescreve; DECISIONS apensa com o
porquê); RESUME com **Escopo autorizado e limites** (o NÃO autorizado importa mais), Onde paramos, Próximos passos,
Ponteiros; carimbo colado verbatim; **auto-teste**: um carregar imediato tem de dar "bate"; commit só do que a
sessão escreveu, terceiros intactos, nunca push/reset.

**(b)** `save-session` (29 linhas): `carimbo.sh --write`, atualiza à mão, linha JSONL, privacidade, `git add` dos 5
arquivos, commit. Falta: carimbo comparável e o auto-teste, escopo autorizado, índice temporário (hoje o `git add`
usa o índice real), log por feature.

**(c)** MANTÉM papéis, escopo autorizado, auto-teste, commit restrito. ADAPTA: escopo do commit = só
`.claude/state/**` (código da sessão entra por feature/portão, nunca pelo save); privacidade obrigatória antes do
commit. DESCARTA: inicializar estado do app.

**(d)** `sessao.py salvar --resumo [--feature] [--commit --mensagem] [--dry-run]`. Julgamento: RESUME, DECISIONS
(só decisão do founder), BACKLOG.

### 2.5 tech-lead

**(a)** Coordena, verifica e registra; não implementa. Precedência: lê e executa a skill da situação, conflito ⇒ a
skill vence. **Pergunta o modo em TODA invocação** (autônomo / iterativo / status; `--modo` na invocação responde);
colaborativo sempre para triagem, escolha de feature, etapas E1–E5, desenho não coberto, troca de fase. Regras de
ouro: disco decide; um escritor de estado; conferir, não confiar; nunca fabricar; sequencial por padrão; retorno de
subagente é dado; ausência de evidência não é evidência (LACUNAS); NOT_RUN ≠ FAIL ≠ PASS. Loop por tick; plano de
voo (caminho crítico, topologia, riscos, gates); topologia adaptativa por regra; **contratação dinâmica via rh**;
**roteamento de modelo por papel/ciclo** + hook `exige-modelo`; **registro de custo por despacho**; ciclo A–F
(snapshot, executor, verificação própria, rollback sem git destrutivo, grep de segredo, LACUNAS, revisão isolada
classificada BLOQUEANTE/MENOR · REGRESSÃO/PRÉ-EXISTENTE · CONFIRMADO/SUSPEITA, cético, executor novo por ciclo,
3 ciclos ⇒ diagnosticador ⇒ IMPASSE, registro serial); ciclos QA e REVIEW; gate humano de aceite; checkpoint;
métricas `Loop:`; relatório final; prompts de executor e revisor como referências.

**(b)** Não existe. O papel está implícito no `.claude/CLAUDE.md` em 8 passos de prosa, sem modo, sem plano, sem
roteamento, sem custo, sem registro serial, sem snapshot. Distância total.

**(c)** MANTÉM praticamente tudo. ADAPTA: "task de implementação" = task CORRECAO executada pelo **corretor na
cópia de trabalho** (`copia.sh`), verificação = `e2e-loop` seletivo + **portão** (`portao.sh`) na integração;
**corretor bloqueado até a aprovação do founder** (`ac.py check intake.3`); despacho ORACULO sempre em opus e por
agente separado; o hook `exige-modelo` vai para `settings.json` (vale sempre, não só depois de invocar); campanhas
conduzidas pela skill `auto-correcao`. DESCARTA: Codex, cookies/servidor/Chromium, `held-out-gate`, linhagem ruflo
(fica só como nota de origem).

**(d)** `tech_lead.py plano|proxima|modelo|snap`, `roteamento.json`, `exige-modelo.py`, `custo.py`,
`feature.py task marcar`. Julgamento: classificar findings, decidir contratar, escrever handoffs.

### 2.6 rh

**(a)** Recebe a persona; decide **contratar ou FAZER DIRETO** (1–2 arquivos, já lido, ≥3 auxiliares ativos);
**verifica o elenco** (tipo inexistente vira genérico em silêncio — declarar substituição); permissão (auxiliar =
SOMENTE LEITURA; executor só com paths exatos); prompt pelo esqueleto (missão em uma pergunta, contexto com comandos
exatos, escopo e exclusões, regras, retorno é dado, trava contra invenção CONFIRMADO/SUSPEITA, REGRESSÃO/
PRÉ-EXISTENTE, retorno fechado com LACUNAS); confere a ficha (sem placeholder, tipo no elenco, permissão coerente,
grep de segredo, Modelo, nome com ID da task); bases de persona; evals com grader mecânico.

**(b)** Não existe. Distância total.

**(c)** MANTÉM tudo. ADAPTA: "recusar tipo inexistente" é o padrão (exit 2); substituição só com
`--aceitar-substituicao`, declarada na linha Tipo; personas da skill (diagnosticador, cético, investigador de
ambiente, especialista de segurança — guards/hooks/senha, explorador, executor); regras do prompt citam
`.claude/state/` e o oráculo como proibidos. DESCARTA: cookies, URLs assinadas como foco (o grep de segredo fica).

**(d)** `rh.py elenco|ficha|conferir`, `personas.json`, `elenco.json`. Julgamento: a necessidade e o material.

### 2.7 revisor (≙ revisor-<app>)

**(a)** Pacote de revisão (critérios congelados, diff, veredito do executor, evidências); confere gate; CAs/escopo
mudados sem decisão; diff contra a arquitetura; matriz CA → evidência → PASS/FAIL/NOT_RUN; APPROVED |
CHANGES_REQUESTED; quem aceita é o humano; autorrevisão declarada; não corrige, não commita.

**(b)** Não existe (o portão faz parte do trabalho, sem parecer).

**(c)** MANTÉM. ADAPTA: critérios do checklist do prompt de revisor da referência viram os da skill (escopo =
Arquivos permitidos, CAs com Prova rodada, nenhum `def` removido, oráculo intacto, privacidade, regressão contra a
régua); frontmatter `allowed-tools` **sem** Write/Edit/MultiEdit/NotebookEdit; o tech-lead confere por
`tech_lead.py snap`. DESCARTA: arquitetura do app.

**(d)** Sem script próprio (é julgamento); o mecânico é `snap` e a régua.

### 2.8 e2e-loop

**(a)** Pré-condições (dependência ausente = NOT_RUN); régua comum; ler o resultado; diagnóstico por falha;
corrigir só se autorizado; rodar o afetado e a régua; ≤3 ciclos sem progresso; reportar CAs e limites; integridade
(marcador só pelo runner, hash estável).

**(b)** Não existe; o portão roda **todas** as suítes sempre (dezenas de minutos), sem seleção, e **não roda a
suíte do próprio harness** (`.claude/tools/tests`).

**(c)** MANTÉM o protocolo. ADAPTA: **régua listada por script** (suíte `harness-dev` = `.claude/tools/tests`, cada
`scripts/<x>/tests`, `evals/tests`; 2 Pythons; verificações def-removido, privacidade, pacote sem vazamento);
**seleção por arquivo tocado** (mapa em `regua.json`; arquivo desconhecido ⇒ completa, por segurança); **completa
só no fechamento** (`--fechamento`) e no portão; o portão passa a rodar a suíte `harness-dev`. DESCARTA: navegador,
Chromium, servidor, `held-out-gate`.

**(d)** `e2e.py regua|selecionar|rodar`, `regua.json`, `portao.sh` (suíte harness-dev).

### 2.9 auto-correcao (skill do próprio harness)

**(a) Método da auto-correcao** (skill global): laço medido intake → oraculo → base → diagnostico → plano →
correcao → integracao → remedicao → decisao; 3 travas (sem oráculo confiável não há laço; quem corrige não corrige o
oráculo — mudança só por `oracle change --why --evidence`; portões humanos com tty + frase do founder, que a IA
nunca digita); `load/done` por etapa; calibração (vazio ≈ 0, bom passa; L15: requisito novo = testes de agente
separado conferidos pelo humano); qualidade × estrutura; defeitos classificados; features disjuntas com contrato de
nomes; integração em todos os runtimes; sistema congelado na remedição; decisão parar/continuar/escalar; lições
L01–L18.

**(b)** O motor está embutido (`tools/ac/`), mas **não há skill** que conduza o método: o `new-front`/`close-front`
chamam meia dúzia de comandos soltos; nada guia etapa, sub-etapa, calibração, mudança oficial ou conferência.

**(c)** MANTÉM o método inteiro, adaptado: motor pelo caminho literal `python3 .claude/tools/ac/ac.py --work
campanhas/<f>` (o hook de aprovação nega variável + palavra de aprovação); oráculo por **agente separado** em
`campanhas/<f>/oraculo/` + `oracle freeze`; **mudança oficial** = patch + PORQUE em `mudanca-oficial/` antes do
`oracle change` (com TODOS os arquivos — lição local); aprovação = `script-aprovacao.sh` gera e o founder roda no
terminal dele; fechamento com `frase conferir` do founder antes do `done decisao`. O tech-lead a usa para conduzir
as campanhas. DESCARTA: `$AC` apontando para a skill global, `~/.claude/skills/auto-correcao`.

**(d)** `campanha.py etapa|mudanca-oficial|fechar` (nunca roda gate/preauth/frase; `--help` só oferece os três).

### 2.10 package e install

Ficam (não há equivalente na referência; o founder autorizou). Ganham `disable-model-invocation: true` (mudam
estado/instalação). Texto passa a citar `fechar-feature`/`salvar-sessao`.

### 2.11 Hooks, guards e ligações

| referência | aqui | decisão |
|---|---|---|
| `guard-git-destrutivo.sh` (reset/checkout --/clean/stash/push com held-out) | `guard-git.sh` + `guard_git.py` já cobrem e mais (add -A, commit -a, push sempre) | MANTÉM o atual |
| `guard-po-task-schema.sh` (G-PO) | `contrato.py` + regra de schema no `guard-estado.py` | ADAPTA (Python, 2 Pythons) |
| `guard-close-complete.sh` (G2) | `feature.py fechar idle` (recusa) + `guard-estado.py` (archive único) | ADAPTA |
| `guard-local-feature-state.py` (motor JSON, inativo lá) | `guard-estado.py`: `features.json`, `CHECKLIST.md`, `eventos.jsonl`, `propostas/` só por script; FEATURE.md só após E2; TASKS só após E3; nome de task; DONE só com gate PASS e Handoff; archive só `<id>.md` | ADAPTA (ativo aqui) |
| `exige-modelo.py` (frontmatter do tech-lead) | `.claude/tools/exige-modelo.py` em `settings.json` (`Agent|Task`) | ADAPTA |
| `session-stamp.sh` | `sessao.py carimbo` (dono único da fórmula) | ADAPTA |
| `checar-complexidade.py` | `contrato.py complexidade` | ADAPTA |
| `custo-despacho.py` | `custo.py medir|registrar|resumo` | ADAPTA |
| `run_project_checks.py`, `held-out-gate.sh`, NORM | `portao.sh` + `e2e.py` | DESCARTA (app) |
| `feature_flow.py` + `local_feature_flow/` | — | DESCARTA o motor; MANTÉM a ideia do vínculo aprovação ↔ sha |
| Codex (`.agents/`), INSTALLATION/protocol-install | — | DESCARTA |

---

## §3 Contrato mecânico (o que os testes exercitam)

Todos os scripts: em `.claude/tools/`, stdlib, Python 3.9+; raiz do projeto = `$CS_DEV_SKILL_DIR` (padrão: dois
níveis acima do script); motor = `$CS_DEV_AC` (**variável de teste**, como `CS_DEV_SKILL_DIR`; padrão
`.claude/tools/ac/ac.py`; o `--json` de `status`, `abrir`, `etapa` mostra o motor usado). `--help` exit 0 e cita os
subcomandos. Saídas `--brief` ≤ 40 linhas. Exit: 0 ok · 1 recusa (pré-condição/ordem/aprovação/gate) · 2 lacunas
(contrato) ou pergunta pendente (plano sem modo) · 3 uso.

### 3.1 Estado (`.claude/state/`)
```
features.json                  {"schema":1,"ativas":[{"id","origem":"criar-feature|legado","aberta_em","campanha"}],
                               "entregues":[{"id","fechada_em","archive"}]}      (só scripts escrevem)
WORKFLOW.md                   bloco gerado entre <!-- features:inicio ... --> e <!-- features:fim --> com
                              "**Estado:** IDLE|IN_PROGRESS"; o resto é humano e é preservado
features/<id>/eventos.jsonl    {"seq","ts","tipo":"inicio|proposta|aprovacao|rejeicao|abertura","etapa","sha",...}
features/<id>/CHECKLIST.md     projeção determinística dos eventos (ver 3.3)
features/<id>/propostas/E1.md|E2.md|E5.md
features/<id>/FEATURE.md        Bloco A (E3)        features/<id>/TASKS/{NN}-{TIPO}-{DESC}.md   Bloco B (E4)
features/<id>/INDEX.md         "Progresso: k/t · próxima: X" + tabela "| id | entrega | tipo | grupo | CAs | depends | status |"
features/<id>/HISTORICO.md     append-only: "## [NOTA] ts — Abertura…", "## [PASS] <task> — ts", "## [REJECT] <task> — ts"
logs/<id>/<id>.md             log da feature     logs/sessoes.jsonl     logs/custo.jsonl
archive/<id>/<id>.md          documento único     LAST_DELIVERY.md ("**Feature-ID:** <id>" 1ª linha do corpo)
RESUME.md                     <!-- resume-stamp\nFEATURES: …\nBRANCH: …\nHEAD: …\nPRODUTO: …\nESTADO: …\nGATE: …\n-->
```

### 3.2 FEATURE.md (Bloco A) e task (Bloco B)
FEATURE.md: `FEATURE-ID: <id>`, `Nome:`, seções `## História` (Como…quero…para) · `## Problema / Contexto` ·
`## Valor de negócio` · `## Personas / Stakeholders` · `## Critérios de Aceitação` (itens `- **CA-NN — …** DADO …,
QUANDO …, ENTÃO …` + linha `  Prova: \`comando\``) · `## RNFs` · `## Edge cases` · `## Dependências` · `## Escopo IN`
· `## Escopo OUT` · `## Escopo de escrita` (itens `- \`glob\``; vira `--scope`) · `## Critério de parada` (com
número; vira `--stop`) · `## Métrica de sucesso` · `## Aceite da Feature` (`### Aceite QA — PENDENTE|ACCEPT`,
`### Aceite Review — PENDENTE|APPROVED`). A `## História` vira o `--problem`.
Task: título `# <id> — <entrega>`; cabeçalho `id`, `feature`, `tipo` (ORACULO|CORRECAO|QA|REVIEW), `grupo`
(G1..G3 em CORRECAO, `—` nos demais), `agente`, `CA`, `depends` (`—` ou `ID (porquê), ID (porquê)`), `status`
(PENDENTE|IN_PROGRESS|DONE), `gate` (PENDENTE|PASS|FAIL), `complexidade` (baixa|normal, opcional); seções `## Goal`
· `## Contexto` · `## Subtasks` (2–5 passos numerados) · `## Invariants` · `## Scope IN / OUT` · `## Arquivos
permitidos` (`- \`path\``; o próprio arquivo da task é isento) · `## AC` · `## DoD` · `## Verificação` (bloco de
código com comando que não seja só ls/echo/TBD/true/cat) · `## Handoff` (pode nascer vazio; DONE exige preenchido).

### 3.3 `contrato.py` (códigos das lacunas, em `--json`: `{"ok", "lacunas":[{"codigo","msg"}]}`)
`feature`: `id_invalido:<id>`, `campo_ausente:<Seção>`, `historia_sem_como_quero_para`, `sem_ca`,
`ca_sem_dado_quando_entao:CA-NN`, `ca_sem_prova:CA-NN`, `escopo_vazio`, `escopo_amplo:<glob>` (`*`, `**`, `**/*`,
`.`, absoluto, `..`), `parada_sem_numero`, `aceite_sem_qa_review`.
`completo` (= feature + tasks): `task_nome_invalido:<arquivo>`, `task_cabecalho:<id>:<campo>`,
`id_difere_do_arquivo:<arquivo>`, `tipo_invalido:<id>`, `task_campo_ausente:<id>:<Seção>`,
`subtasks_fora_de_faixa:<id>`, `arquivos_vazio:<id>`, `arquivo_glob:<id>:<path>`, `verificacao_trivial:<id>`,
`oraculo_ausente`, `oraculo_fora_da_pasta:<id>:<path>`, `qa_ausente`, `review_ausente`,
`depends_inexistente:<id>:<dep>`, `depends_sem_porque:<id>:<dep>`, `depends_ciclo`, `grupo_ausente:<id>`,
`correcao_escreve_oraculo:<id>:<path>`, `arquivo_fora_do_escopo:<id>:<path>` (fnmatch nos globs),
`correcao_sem_depender_do_oraculo:<id>` (transitivo), `grupos_demais`, `mesmo_arquivo_sem_ordem:<path>`,
`grupos_colidem:<path>` (mesmo arquivo em CORRECAO de grupos diferentes, mesmo ordenadas), `ca_orfao:CA-NN`.
`etapa E1|E2|E5`: `etapa_campo_ausente:<EN>:<rótulo>` (E1: Demanda, Problema por trás, O que NÃO é, Perguntas
abertas, FEATURE-ID · E2: Inventário, Classificação, Exclusões, Achados, Enforcement existente · E5: Ordem, Primeira
task, Escopo da campanha, Critério de parada, Git) e `e2_sem_evidencia` (nenhum `F<n>` com `arquivo:linha`).
`complexidade <task>`: 0 se não é `baixa` ou se as 4 condições valem; senão 2. `--sonda`: monta uma feature válida
(tem de passar) e tira o Goal de uma task (tem de reprovar com lacuna de Goal); 0 = sonda ok, 3 = NOT_RUN.

### 3.4 `feature.py`
`status [--json|--brief]` → `{"estado","ativas":[{"id","origem","progresso":"k/t"|"—"}],"criacao":null|{"id",
"proxima"},"entregues","workflow_em_dia","motor"}`.
`criar iniciar <id> --demanda TXT [--dry-run]` (E0): recusa (1, nada escrito) se `.claude/state/` não existe
(mensagem cita `salvar-sessao`), id inválido, outra criação em andamento, id já existe (feature, campanha, archive)
ou `len(ativas) >= max_features_ativas`; mesma id + mesma demanda = **retomada** (0, imprime a próxima etapa);
demanda diferente = 1. Escreve `eventos.jsonl` + `CHECKLIST.md` com E0 `[x] … OK` e E1..E5 `[ ]`.
`criar propor <id> --etapa EN [--arquivo ARQ] [--json]` → `{"feature","etapa","sha","ok"}`; só a etapa corrente;
recusa (1) proposta pendente sem decisão; E1/E2/E5 validam `contrato.py etapa` e guardam em `propostas/`; E3 valida
Bloco A (CA órfão pode esperar) e o FEATURE-ID = id; E4 exige `--sonda` ok, contrato completo e complexidade das
`baixa`; lacuna = exit 2 listando os códigos.
`criar aprovar <id> --etapa EN --sha SHA --palavra TXT --produzido TXT --proxima TXT [--medido] [--itens]`: só a
etapa corrente; o sha tem de ser o da **última proposta ainda não decidida** e o artefato atual tem de ter o mesmo
sha; palavra precisa começar com `ok|sim|aprovo|aprovado`; marca a caixa e apensa o handoff `### EN — <nome> ·
CONCLUÍDA ts` com `- Aprovação: "<palavra>"`. A decisão vale para o **evento** de proposta (re-propor o mesmo
conteúdo depois de rejeitado cria proposta nova).
`criar rejeitar … --motivo TXT`: apensa `### EN — REJEITADA ts · motivo: …`; caixa continua vazia.
`checklist <id> [--json]`: 0 se o arquivo é exatamente a projeção dos eventos; 2 se adulterado.
`criar abrir <id> [--dry-run] [--json]`: exige E1–E5 aprovadas, checklist íntegro, artefatos com o sha aprovado,
contrato completo; **overlap** contra cada ativa (campanha temporária com os mesmos globs + `ac.py overlap`;
colisão = 1, nada escrito); então `ac.py --work campanhas/<id> init --target . --scope … --problem <História>
--stop <Critério de parada>`, INDEX, HISTORICO (`[NOTA]` com o E2), log, `features.json`, WORKFLOW, linha em
`campanhas/README.md`, handoff `### Abertura`; **nunca commita** e não gera o script de aprovação. JSON
`{"feature","campanha","aberta":true,"tasks","primeira","motor"}`.
`adotar <id> [--dry-run]`: campanha existente e não concluída entra em `ativas` como `legado` (idempotente).
`task marcar <id> <task> --status S --gate G [--nota]`: DONE exige gate PASS e Handoff preenchido (senão 1);
atualiza cabeçalho, INDEX e apensa no HISTORICO.
`fechar plano <id> --json` → `{"etapas":[{"id":"archive|entrega|limpar|idle","feita":bool}]}` por pós-condição.
`fechar check <id> [--json]` → `{"ok","falhas":[{"codigo","msg"}]}`, exit 1 se falhar, **nunca escreve**; códigos:
`completude_divergente`, `task_aberta:<id>`, `aceite_ausente:qa|review`, `gate_ausente:<id>`, `portao_nao_verde`,
`conferir_commit`, `campanha_sem_aprovacao`.
`fechar archive <id> --notas ARQ` (notas com `## Resumo`, `## Decisões técnicas`, `## Aprendizados`): exige check
ok; escreve só `archive/<id>/<id>.md` com `## Resumo`, `## Critérios de aceite` (`### CA-NN`), `## Linha do tempo`,
`## Tasks`, `## Como a feature nasceu` (handoffs do checklist), `## Campanha`, `## Oráculo`, `## Decisões técnicas`,
`## Aprendizados`, `## Arquivos da feature` (só CORRECAO), `## Aceite da Feature` e, em escrita separada, a última
linha `<!-- fechar-feature:archive-completo -->`; completo ⇒ 0 sem escrever.
`fechar entrega|limpar|idle <id>`: LAST_DELIVERY; remover `features/<id>/` e `logs/<id>/` só com archive completo;
IDLE só com archive completo e único, limpeza feita e LAST_DELIVERY — tira a feature de `ativas`, põe em
`entregues`, regrava o bloco do WORKFLOW (IDLE se nenhuma ativa). Reexecutar não muda nada.
`fechar commit <id> --mensagem ARQ [--decisions ARQ] [--dry-run] [--json]`: exige `ac.py check integracao.3`,
`conferir-commit.sh` ok e privacidade limpa; `paths` = Arquivos da feature + `campanhas/<id>/oraculo` +
`campanhas/README.md` + estado da feature (archive, features/<id>, logs/<id>, LAST_DELIVERY, WORKFLOW, features.json,
RESUME, BACKLOG) que tiverem mudança; DECISIONS só com `--decisions`; commit num **índice temporário** a partir do
HEAD; stage de terceiros fica em stage e fora; nunca push.

### 3.5 `guard-estado.py` (hook Edit|Write|MultiEdit|NotebookEdit)
Saída de negar igual à do `guard-entrega.py` (JSON `permissionDecision: deny`, exit 0); permitir = sem saída; payload
inválido = nega. Regras em §2.11.

### 3.6 `tech_lead.py`, `exige-modelo.py`, `roteamento.json`
`plano [--modo autonomo|iterativo|status] [--feature] [--json|--brief]`: sem modo ⇒ exit 2 e `{"precisa_modo":true,
"opcoes":["autonomo","iterativo","status"],"pergunta"}` (texto cita "autônomo" e "iterativo"). Com modo:
`{"modo","features":[{"id","progresso","proxima","elegiveis","bloqueio","topologia","caminho_critico","gates_humanos",
"despacho":{"papel","modelo","motivo","task"}}]}`; `caminho_critico` = cadeia mais longa de depends até a REVIEW;
`gates_humanos` inclui `aprovacao_founder` (enquanto `ac.py check intake.3` falha), `aceite_humano`, `frase_conferir`.
`proxima [--json]` → `{"feature","elegiveis","bloqueio","topologia"}`: CORRECAO não é elegível sem a aprovação do
founder (`bloqueio: aprovacao_founder`); `paralelo` só com ≥2 elegíveis de arquivos disjuntos e sem `Execução:
sequencial` no FEATURE.md.
`modelo --papel P [--ciclo N] [--task ARQ] [--json]` → `{"papel","modelo","motivo"}`: executor c1 sonnet; executor
c1 com `complexidade: baixa` **válida** haiku (inválida ⇒ sonnet); executor ciclo ≥2 opus; revisor sonnet, opus se
a task toca área sensível; qa sonnet; review opus; oraculo opus; `rh:<persona>` = `personas.json`; papel
desconhecido ⇒ 2.
`snap --out ARQ` / `snap --comparar ARQ [--json]` → `{"mudou":[paths]}`, exit 1 se mudou (dirty/untracked por hash).
`exige-modelo.py`: description com ID de task (`NN-TASK-…`, `TASK|BUG|GAP|DEBT-…`) e `model` ausente/vazio/`inherit`
⇒ exit 2 citando o ID e nunca o prompt; todo o resto (inclusive JSON inválido) ⇒ 0.

### 3.7 `custo.py`
`medir <agentId> [--transcript] [--projects-dir] [--json]` → turnos, contexto_primeiro_turno, contexto_somado
(input + cache criação + cache leitura por turno), cache_leitura, cache_escrita, saida, modelos, linhas_invalidas;
nunca imprime conteúdo; 0 ou 2+ transcripts ⇒ exit ≠0. `registrar <agentId> --feature --task --papel --modelo` apensa
em `logs/custo.jsonl` (`status: OK` com os números, ou `NOT_RUN` com `motivo` e sem números; exit 0). `resumo
--feature F --json` → `{"por_modelo":{"<modelo pedido>":{"turnos","contexto_somado",…}},"not_run"}`.

### 3.8 `rh.py`
`elenco [--json]` → `{"tipos":[…]}` (`elenco.json` + `.claude/agents/*.md`). `ficha --persona P --task T --motivo M
[--tipo X [--aceitar-substituicao]] [--arquivos …] [--contratados N] [--json]`: persona fora de `personas.json` ⇒ 2;
tipo fora do elenco ⇒ 2 ("inexistente"), ou substituição declarada na linha `Tipo:`; `--contratados ≥3` ⇒ FAZER
DIRETO sem prompt; executor sem `--arquivos` ⇒ 2. Ficha: `FICHA DE CONTRATAÇÃO`, `Decisão:`, `Persona:`, `Nome do
agente: rh-<persona>-<task>-<n>`, `Tipo:`, `Modelo:`, `Permissão:` (SOMENTE LEITURA | ESCRITA em …), `Critério de
descarte:`, `Linha de log:`, bloco `--- PROMPT ---` … `--- FIM DO PROMPT ---` sem `{placeholder}`, com DADO, LACUNAS,
CONFIRMADO/SUSPEITA. JSON: `decisao, persona, nome, tipo, no_elenco, substituicao, modelo, permissao`. `conferir
<ficha>`: 2 se placeholder, sem LACUNAS, sem descarte, sem Modelo, nome sem ID, tipo fora do elenco sem
substituição, segredo (grep), permissão incoerente.

### 3.9 `e2e.py`, `regua.json`, `portao.sh`
`regua [--json|--brief]` → `{"suites":[{"nome","dir"}],"pythons":["python3","/usr/bin/python3"],"verificacoes"}`
com `harness-dev` (`.claude/tools/tests`), cada `scripts/<x>` que tem `tests/`, e `evals`. `selecionar (--arquivos
…|--lista ARQ) [--fechamento] [--json]` → `{"suites","completa"}`: `.claude/**` ⇒ só `harness-dev`;
`scripts/<x>/**` ⇒ `x` (não todas); desconhecido ou `--fechamento` ⇒ todas, `completa: true`. `rodar --suites a,b
[--pythons] [--dry-run]` (dry-run imprime os comandos nos 2 Pythons). `portao.sh`: roda também a suíte
`harness-dev` (`.claude/tools/tests`) nos 2 Pythons; o `--dry-run` cita `harness-dev`.

### 3.10 `campanha.py`
`etapa <f> [--json|--brief]` → `{"feature","motor","etapa","pendentes":[{"id","ctx","do"}],"proximo"}` (sub-etapas
lidas do `ciclo.json5` do motor, feitas = `ac.py check <sub>` ok). `mudanca-oficial <f> --porque --evidencia
[--dry-run]`: exige `*.patch` e `PORQUE*.md` em `campanhas/<f>/oraculo/mudanca-oficial/`; monta `oracle change
--why --evidence` com **todos** os `--file` congelados. `fechar <f> --relatorio --config --decisao [--dry-run]
[--concluir]`: front report → done correcao → set integration.tests_green → done integracao → run record →
done remedicao → linha do FOUNDER `frase conferir` → (`--concluir`) done decisao. Subcomandos só esses três.

### 3.11 Ligações
`script-aprovacao.sh`: sem campanha ⇒ erro citando `criar-feature`; **oráculo não congelado ⇒ recusa** (cita
"congel…"). `guard-entrega.py`: a mensagem cita `criar-feature`. `carimbo.sh --brief`: cita `carregar-sessao`, ≤40
linhas. `settings.json`: `guard-estado.py` em `Edit|Write|MultiEdit|NotebookEdit` e `exige-modelo.py` em
`Agent|Task`. Skills: exatamente `auto-correcao, carregar-sessao, criar-feature, e2e-loop, fechar-feature, install,
package, revisor, rh, salvar-sessao, tech-lead`; `disable-model-invocation: true` em auto-correcao, criar-feature,
fechar-feature, install, package, salvar-sessao, tech-lead (e não nas só-leitura); `revisor` com `allowed-tools` sem
escrita; `CLAUDE.md` cita os 11; nenhum `new-front`/`close-front`/`skill load-session`/`/save-session`… em `.claude/`
fora de `state/` e `tools/tests/`. Riqueza mínima por skill: termos exigidos em `Skills.test_*_rica` (etapas, scripts,
regras) — a prosa do processo (o "porquê" de cada regra, como na referência) é do corretor; o teste só garante que
nada essencial falta.

---

## §4 O que o oráculo testa (103 testes, 14 classes)

| classe | n | o quê |
|---|---|---|
| Fronteira | 3 | produto idêntico ao HEAD; pacote sem nada do harness; validador acusa skill de dev no pacote |
| Skills | 16 | conjunto exato, substituídas ausentes, frontmatter, disable-model-invocation, finas, scripts/subcomandos existem, riqueza de cada skill, revisor sem escrita, auto-correcao no motor embutido, CLAUDE.md, nomes ingleses fora, settings |
| Ajuda | 3 | todos os scripts com `--help`/subcomandos/`--json`/`--brief`; dados JSON válidos; motor embutido intacto |
| Contrato | 20 | válido passa; sonda; sem Goal/AC; glob; fora do escopo; verificação trivial; CA órfão; QA/REVIEW; oráculo ausente/fora; correção no oráculo; correção antes do oráculo; mesmo arquivo sem ordem; grupos colidem; depends sem porquê/inexistente; nome inválido; CA sem prova/sem DADO; Bloco A e id; etapas E1/E2/E5; complexidade |
| CriarFeature | 22 | E0 (sem estado, só checklist, dry-run, id inválido, segunda criação, limite, adotar); ordem; sha + palavra literal; checklist append-only; rejeição; adulteração; E2 sem evidência e Bloco A pobre; E3/E4; retomada; alteração depois do ok; abrir dry-run; abertura completa sem commit; colisão; script de aprovação exige oráculo congelado; status/WORKFLOW; compatibilidade: state com rótulos antigos (`frentes.json`, `frentes/`, marcadores e `FRENTES:`) é lido e reescrito com os novos |
| TechLead | 7 | plano exige o modo; caminho crítico e despacho; marcar exige gate e handoff; corretor bloqueado até a aprovação; roteamento por papel; exige-modelo; snap |
| Custo | 2 | medir só usage (sem vazar conteúdo); registrar OK/NOT_RUN e resumo por modelo |
| RH | 3 | ficha válida e conferida (placeholder e segredo reprovam); tipo inexistente recusado/substituído; FAZER DIRETO e executor com paths |
| E2E | 4 | régua; seleção por arquivo; desconhecido/fechamento = tudo; rodar dry-run |
| FecharFeature | 8 | gate reprova cada falta sem escrever; limpar sem archive; archive único e idempotente; archive com gate reprovado; fechamento completo e retomável; IDLE recusa intruso; commit só da feature; commit exige pré-autorização |
| Guards | 4 | arquivos do script; artefato só após aprovação; DONE sem gate/handoff (Write e Edit); archive único |
| Sessao | 5 | carimbo e frescor; HEAD por regra; salvar (dry-run, log, bate); commit só do estado + privacidade; briefing |
| AutoCorrecao | 3 | etapa pelo motor embutido; mudança oficial com todos os arquivos; fechar segue o ciclo e deixa o humano ao founder |
| Ligacoes | 3 | carimbo `--brief`; guard-entrega e script de aprovação citam criar-feature; portão roda a suíte harness-dev |

Isolamento: cópia temporária (`.claude/` do projeto + `VERSION`, `SKILL.md`, `a/um.py`, `a/dois.py`,
`campanhas/README.md`; estado zerado; repositório git novo, identidade "Ana"), `HOME`/`XDG_CONFIG_HOME` temporários,
`GIT_CONFIG_NOSYSTEM=1`, `CS_*`/`GIT_*` do ambiente removidos, stdin fechado. Aprovações humanas **nunca** são
simuladas pelo motor real: onde o teste precisa de `check intake.3`/`integracao.3` verde usa um motor falso via
`CS_DEV_AC` que **recusa** `gate|preauth|frase` (exit 9) e registra as chamadas — os testes conferem que nenhum
script chamou essas três.

**Calibração** (L15, requisito novo): vazio = 4/101 (medido antes da mudança 02) no projeto atual (só os de fronteira e o motor intacto, que já
valem); "bom" = um protótipo de calibração escrito pelo autor do oráculo numa pasta descartável (não entregue ao
corretor) passa 103/103 em 3.13 e 3.9 — prova que o contrato é satisfazível e coerente. **Força**: 12 mutações do
protótipo, todas pegas (ver `base.txt`). Falta a conferência humana do founder: testes × este ESPEC.

---

## §5 Grupos do corretor (≤ 3, arquivos disjuntos)

Ordem: **G1 primeiro**; G2 e G3 em paralelo depois de G1 DONE (G2 lê o estado no formato de §3.1/3.2 e pode
importar a biblioteca de G1, sem editá-la). Cada grupo escreve seus testes de regressão no arquivo de teste dele.

| grupo | arquivos (exatos) | testes do oráculo que fecha |
|---|---|---|
| **G1 — motor da feature e sessão** | `.claude/tools/feature.py`, `.claude/tools/contrato.py`, `.claude/tools/guard-estado.py`, `.claude/tools/sessao.py`, `.claude/tools/estado_lib.py` (biblioteca comum, opcional), `.claude/tools/regras.json`, `.claude/tools/script-aprovacao.sh`, `.claude/tools/tests/test_feature.py` | Contrato, CriarFeature, FecharFeature, Guards, Sessao, parte de Ajuda |
| **G2 — orquestração, campanha e régua** | `.claude/tools/tech_lead.py`, `.claude/tools/exige-modelo.py`, `.claude/tools/roteamento.json`, `.claude/tools/custo.py`, `.claude/tools/rh.py`, `.claude/tools/personas.json`, `.claude/tools/elenco.json`, `.claude/tools/e2e.py`, `.claude/tools/regua.json`, `.claude/tools/campanha.py`, `.claude/tools/portao.sh`, `.claude/tools/tests/test_orquestracao.py` | TechLead, Custo, RH, E2E, AutoCorrecao, Ligacoes (portão), parte de Ajuda |
| **G3 — prosa e ligações** | `.claude/skills/**` (cria os 9 novos com `references/` quando couber; remove `load-session`, `save-session`, `new-front`, `close-front`; edita `package`, `install`), `.claude/CLAUDE.md`, `.claude/settings.json`, `.claude/tools/carimbo.sh`, `.claude/tools/guard-entrega.py` (só o texto), `.claude/tools/tests/test_harness_dev.py` (aplica a mudança oficial 01; acrescenta testes de ligação) | Skills, Ligacoes (carimbo, guard-entrega), Fronteira |

Prosa rica é do G3 e é o que o founder cobrou: cada SKILL.md explica o processo **com o porquê** de cada regra (como
a referência), mas toda decisão mecânica aponta para o script. Referências recomendadas: `criar-feature/references/
contrato-feature.md` (A LEI + O EXEMPLO, com exemplo de skill, não do app), `tech-lead/references/{executor-prompt,
revisor-prompt, aprovacao-com-recomendacao}.md`, `rh/references/{esqueleto-prompt, personas}.md` (espelho legível de
`personas.json`), `auto-correcao/references/metodo.md` (as 9 etapas, travas e lições aplicadas a este projeto).

Escopo da campanha (`--scope`, um por glob): `.claude/CLAUDE.md`, `.claude/settings.json`, `.claude/skills/*/SKILL.md`,
`.claude/skills/*/references/*`, `.claude/skills/*/evals/*`, `.claude/tools/*.py`, `.claude/tools/*.sh`,
`.claude/tools/*.json`, `.claude/tools/tests/*.py`. Fora: `.claude/tools/ac/**`, `.claude/package/**`, produto.

---

## §6 Portão e critério de parada

Portão (o corretor entrega na cópia `local/work/harness-dev/`):
```
bash .claude/tools/portao.sh harness-dev --lista <arquivos-da-feature> \
  --oraculo campanhas/harness-dev/oraculo:test_harness_dev \
  --oraculo campanhas/iter15/oraculo:test_iter15.TestR1FontesDaSkill
```
**Critério de parada (numérico):** oráculo 103/103 em `python3` e `/usr/bin/python3`; suítes do produto e a suíte
`harness-dev` verdes nos 2 Pythons; iter15 R1 verde; 0 `def` removido (testes com corpo trocado só pela mudança
oficial 01); `conferir-commit` OK; `guard-privacidade` vazio; `Fronteira` verde (produto intacto, pacote limpo).

---

## §7 Mudanças oficiais (`mudanca-oficial/`)

- `01-suite-harness-nomes-pt.patch` + `PORQUE.md`: a suíte do harness (`.claude/tools/tests/test_harness_dev.py`,
  que não é oráculo congelado de campanha, mas é guarda — trocar corpo de teste é enfraquecer, por isso vai oficial)
  muda 4 testes: lista de skills nova; `test_nomes_antigos_de_skill_ausentes` deixa de varrer `.claude/` atrás dos
  nomes em português (que agora SÃO os comandos do harness) e passa a varrer atrás dos ingleses substituídos;
  `ScriptAprovacao` cita `criar-feature` e exige o oráculo congelado. Medido: o `TestR1FontesDaSkill` da iter15 (o
  guarda da D-07 no produto) **não** varre `.claude/` — `SOURCE_GLOBS_ROOT`/`SOURCE_DIRS` = SKILL.md, MODO-DE-USO.md,
  assets/templates, references, docs, scripts —, então não precisa de mudança; o único teste que estendia a D-07 ao
  harness era o da suíte do harness. Nada sobre o produto é afrouxado: a varredura do produto continua na iter15 e o
  portão passa a rodá-la (§6).
- A emenda da **D-07** (escopo "produto e este harness" → "produto") é decisão do founder (§8), não patch.

---

## §8 Decisões para o founder

1. **Emendar a D-07**: "nomes em inglês" vale para as skills que o PRODUTO gera; o harness de dev usa comandos em
   português (D-17 nova; a linha de lição do `.claude/CLAUDE.md` muda junto). Recomendo: sim — é o que você pediu.
2. **Features ativas ao mesmo tempo** (`regras.json max_features_ativas`): 1 (regra da referência, D11) ou 2 (o que
   este projeto já faz com overlap provado). Recomendo: 2, com uma criação por vez e colisão provada na abertura.
3. **Adoção da iter18** depois da entrega: `feature.py adotar iter18` (vira ativa `legado`, sem checklist).
   Recomendo: sim, só depois do commit desta feature.
4. **Aprovação E1–E4 no chat** (palavra literal registrada) e **senha só no script de aprovação** (gate stop +
   oracle:requisito + preauth commit) e na `frase conferir`. Recomendo manter: senha a cada etapa custaria 5 idas ao
   terminal por feature sem ganho, porque a abertura já exige a senha antes de qualquer correção.
5. Conferir à mão este ESPEC × testes (L15) antes do `oracle freeze`.

---

## §9 Limites honestos

- A palavra de aprovação E1–E4 é registrada pelo agente: o script garante ordem, vínculo ao sha e literalidade, não
  que o founder disse — a senha só entra no script de aprovação e na conferência.
- `guard-estado.py`, como o `guard-entrega.py`, só vê Edit/Write; escrita por Bash no estado não é bloqueada (é por
  Bash que os scripts escrevem). O `feature.py checklist` e o sha das propostas detectam a adulteração depois.
- `CS_DEV_AC` é variável de teste (como `CS_DEV_SKILL_DIR`); quem a usa troca o motor — os comandos mostram o motor
  no `--json`.
- O oráculo mede a mecânica e a presença do essencial na prosa; a qualidade do texto das skills é da revisão
  (REVIEW) e do founder.
- A seleção de suítes do `e2e.py` é um mapa por caminho, não um grafo de import: arquivo de `scripts/<x>` usado por
  outra suíte só é pego na régua completa (fechamento/portão).
