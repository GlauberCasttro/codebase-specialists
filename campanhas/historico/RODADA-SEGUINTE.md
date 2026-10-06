# Rodada seguinte (depois da PROXIMA-RODADA) — trabalho como árvore navegável

Decisões do founder em 2026-10-03 (revisadas e confirmadas na mesma data — esta versão SUBSTITUI qualquer rascunho
anterior). Depende de duas entregas da próxima rodada: task avulsa (3 faixas) e pasta `.swarm/`.
Rodar com `/auto-correcao`; aqui ficam requisito, contrato e cenários de aceite (oráculo). Nada aqui é opcional.

## 0. Aprendizado do v8 — é EVOLUÇÃO, não cópia (founder, 2026-10-03)
Isto é uma evolução: o desenho desta especificação PREVALECE. O v8 (instalado em o repositório do harness anterior (v8)) entra
como fonte de APRENDIZADO — o que ele já resolveu bem, os erros que já cometeu e as armadilhas operacionais — nunca
como molde. Estude só lendo; para cada ponto abaixo registre no PLANO.json5 uma linha "aprendemos X do v8 → aqui
fica Y (igual | melhor porque…)". Não copie estrutura, nome ou formato do v8 só porque existe lá. Pontos a mapear (registre em PLANO.json5 o que adotar e o que divergir, e por quê):
- **Estado por sprint em pastas**: `docs/state/sprints/SPRINT-02/{sprint.json, tasks/, events.jsonl}` e o arquivamento
  em `docs/state/archive/sprints/SPRINT-01/` (como fecha e move).
- **Stories e tasks**: `docs/refinamentos/STORY-*.json`, `docs/state/padrao/templates/{STORY,SPRINT,BRIEF-*}-TEMPLATE.json`,
  `scripts/harness/{add-story.py, add-task.py, sprint.py, set-sprint-meta.py}`.
- **Transições e eventos**: `scripts/harness/transition.py`, `validate-state.sh`, `check-events-coherence.sh`.
- **Task ativa e retomada**: `docs/state/.active-task.json`, `RESUME.md` + `rotate-resume.py`, `checkpoint.py`,
  `estado.py`, `render-sprint-md.py` (visões geradas).
- **Paralelismo/waves e colisão**: como o kernel do v8 (`.claude/kernel/tech-lead.md`) define waves e o que os
  scripts conferem.
- Já decidido aqui e que PREVALECE sobre o v8 (não reabrir): hierarquia épico → sprint → feature → task, story
  simples/composta, `state/` só com o ativo e `backlog/`/`archive/`, uma feature ativa por vez, JSON5, pasta `.swarm/`
  e harness único.

## 1. Hierarquia (fonte: founder)

```
épico → sprint → feature → task
```
- **A sprint fica dentro do épico; a feature fica dentro da sprint; a task fica dentro da feature.**
- **Toda feature mora dentro de uma sprint.** Não existe feature solta em execução. Abrir uma feature sem sprint
  ativa cria a sprint junto (ou pede para escolher uma ativa).
- **Story em duas formas — o harness escolhe** (founder, 2026-10-03: "os dois se encaixam, o harness identifica"):
  - **simples** (um agente resolve): a story é só o TIPO da task — arquivo `<nn>-US|BUG|FIX-<slug>.json5` direto em
    `tasks/` da feature (ou da sprint);
  - **composta** (precisa de >1 agente, ex.: dev + QA): pasta `stories/<US|BUG|FIX>-<nnn>-<slug>/` com `story.json5`
    (o "quê": como/quero/para, critérios, reprodução, `fixes`) e `tasks/` dentro (o "como", uma task por agente).
  - Regra mecânica: `cs-state new story` com 1 agente → task tipada; com `--agents a,b` (ou quando o plano da triagem
    exige >1 território) → pasta de story. Promover simples→composta: `cs-state promote <task>` (move e registra).
  - Os tipos e regras valem nas duas formas:
  - `US`: traz `como / quero / para` e critérios de aceite.
  - `BUG`: só fica pronta para começar com um teste que falha hoje (reprodução).
  - `FIX`: obrigatoriamente aponta o BUG que corrige (`fixes: <id>`), com o teste que prova.
  - PENDENTE DE DECISÃO (perguntar ao founder antes de implementar): tipo para manutenção técnica sem valor de
    usuário (ex.: subir versão de lib, ajustar timeout). Sugestão a validar: `CHORE`.
- **Qualquer alteração no repositório exige pelo menos uma task — e nada além disso é obrigatório.**
- **`state/` executa UMA feature por vez.** Abrir/iniciar outra feature exige fechar a atual (`/close-feature`) ou
  devolvê-la ao `backlog/` (`cs-state park <FEA> --reason`). Tasks avulsas e tasks da sprint fora de feature não
  contam como "feature ativa".
- **Dentro da feature ativa, tasks rodam em PARALELO quando não há colisão de arquivos** (guarda M2
  `no_parallel_collision` + `knowledge/collision.json5`; mesmo arquivo ou par em `do_not_parallelize` → waves
  seguintes). Tasks com dependência (`depends_on`) esperam a anterior.

### Combinações válidas (todas e somente estas)
| # | Cadeia | Quando |
|---|---|---|
| A | épico → sprint → feature → task | objetivo grande, várias sprints |
| B | sprint → feature → task | feature sem épico |
| C | sprint → task | trabalho da sprint que não pertence a feature (ex.: bugs da sprint) |
| D | task | task avulsa (classe trivial/pequena) — o mínimo |

Inválidas (o motor recusa): feature sem sprint em execução; sprint dentro de feature; task com dois pais; épico
dentro de sprint.

## 2. Três lugares, três papéis
| Pasta | Papel | Quem escreve |
|---|---|---|
| `.swarm/backlog/` | planejado, esperando (READY/BACKLOG) | só o motor |
| `.swarm/state/` | **somente o que está executando agora** | só o motor |
| `.swarm/archive/` | fechado; somente leitura | só o motor |

Um item atravessa os três por comando mecânico (nunca à mão, nunca pelo modelo movendo arquivo):
`backlog/ ──start/plan──▶ state/ ──close──▶ archive/` · `archive/ ──reopen──▶ state/` ·
`state/ ──(sprint fecha com sobra)──▶ backlog/` (com motivo).

## 3. Árvores por caso (cirúrgico)

### Caso A — com épico (todas as camadas)
```
.swarm/state/
└── epicos/
    └── EPC-001-checkout-v2/
        ├── epico.json5                       ← objetivo, métrica, status, DoR/DoD
        ├── README.md                         ← gerado (nunca editado à mão)
        └── sprints/
            └── SPR-003/
                ├── sprint.json5              ← meta, orçamento, datas, status
                ├── features/                 ← UMA feature ativa por vez em state/
                │   └── FEA-007-pagamento-pix/
                │       ├── feature.json5     ← objetivo, testes de aceite, status
                │       ├── tasks/            ← stories SIMPLES (1 agente) = task tipada
                │       │   ├── 01-US-confirmar-pagamento.json5
                │       │   ├── 02-BUG-qr-expira-cedo.json5
                │       │   └── 03-FIX-qr-expira-cedo.json5     ← fixes: 02
                │       └── stories/          ← stories COMPOSTAS (>1 agente)
                │           └── US-001-pagar-com-pix/
                │               ├── story.json5               ← como/quero/para, critérios
                │               └── tasks/
                │                   ├── 01-TASK-BE-endpoint-pix.json5
                │                   └── 02-TASK-QA-cenarios-pix.json5
                └── tasks/
                    └── 01-BUG-erro-tela-resumo.json5           ← task da sprint sem feature (caso C dentro do A)
```

### Caso B — sprint com feature, sem épico
```
.swarm/state/
└── sprints/
    └── SPR-004/
        ├── sprint.json5
        └── features/
            └── FEA-009-login-sso/
                ├── feature.json5
                └── tasks/
                    ├── 01-US-entrar-com-google.json5
                    └── 02-US-entrar-com-microsoft.json5
```

### Caso C — sprint só com tasks
```
.swarm/state/
└── sprints/
    └── SPR-005/
        ├── sprint.json5
        └── tasks/
            ├── 01-BUG-erro-tela.json5
            └── 03-BUG-erro-rota-pessoas.json5
```

### Caso D — task avulsa
```
.swarm/state/
└── tasks/
    └── 2026-10-04-01-FIX-ajusta-timeout.json5
```

### Visão geral (os quatro casos convivendo)
```
.swarm/
├── backlog/
│   ├── epicos/EPC-002-…/epico.json5                 (ainda não começou)
│   ├── features/FEA-010-…/feature.json5             (esperando uma sprint)
│   └── tasks/04-BUG-….json5                         (esperando)
├── state/                                           (SÓ o que executa agora)
│   ├── epicos/EPC-001-…/sprints/SPR-003/features/FEA-007-…/tasks/…
│   ├── sprints/SPR-004/features/FEA-009-…/tasks/…
│   ├── sprints/SPR-005/tasks/…
│   ├── tasks/2026-10-04-01-FIX-….json5
│   └── sessoes/2026-10-04T14-02.json5               (sessão M1 corrente)
├── archive/                                         (fechado, mesma árvore)
│   ├── epicos/…  sprints/…  features/…
│   └── tasks/2026/10/2026-10-02-01-FIX-….json5      (avulsas por ano/mês)
├── events.jsonl                                     (auditoria encadeada por hash; append-only)
└── INDEX.md                                         (gerado: backlog + state + últimos fechados)
```

## 4. Nomes e ids
- Pasta/arquivo = `<ID>-<slug-do-título>`; ids: `EPC-nnn`, `SPR-nnn`, `FEA-nnn` (sequenciais no repositório).
- Task dentro de pai: `<nn>-<TIPO>-<slug>.json5`, `nn` sequencial dentro do pai (01, 02…; nunca reaproveitado).
- Task avulsa: `<aaaa-mm-dd>-<nn>-<TIPO>-<slug>.json5`.
- O id completo da task (para comandos) = `<pai>/<nn>` ou o id avulso; `cs-state find <texto>` resolve.

## 5. Comandos (CLI + skills), todos mecânicos
| Skill | CLI | Faz |
|---|---|---|
| `/new-epico` | `cs-state new epico --title --objetivo [--metrica]` | cria em `backlog/epicos/` |
| `/new-sprint` | `cs-state new sprint --meta [--epico EPC-…] [--orcamento …]` | cria em `backlog/` (ou dentro do épico) |
| `/new-feature` | `cs-state new feature --title --sprint SPR-…|--backlog --aceite <cmd>…` | cria na sprint (ou no backlog) |
| `/new-task` | `cs-state new task --tipo US|BUG|FIX --agent --title [--feature|--sprint|--avulsa] …` | cria a task |
| — | `cs-state start <id>` / `cs-state plan <FEA|task> --sprint SPR-…` | backlog → state (move a subárvore) |
| `/close-task` `/close-feature` `/close-sprint` `/close-epico` | `cs-state close <id>` | confere DoD, grava resumo, move para `archive/` |
| — | `cs-state reopen <id> --reason` | archive → state |
| — | `cs-state move <id> --to <pai>` | troca de pai (ex.: task avulsa → sprint) |
| — | `cs-state tree [<id>]`, `cs-state board`, `INDEX.md` | visões geradas |
O harness também INFERE pela triagem: `trivial`/`pequena` → task (avulsa ou na sprint ativa, se houver);
`feature` → feature numa sprint (cria a sprint se não houver); épico só quando pedido.

## 6. Fechamento (regras exatas)
| Fechar | Exige | Move para `archive/` | Sobra |
|---|---|---|---|
| task | verify + revisão conforme a classe; FIX com o teste do BUG verde | o arquivo da task | — |
| feature | todas as tasks fechadas; testes de aceite da feature verdes | a pasta da feature com as tasks | não fecha; lista o que falta |
| sprint | features e tasks fechadas **ou** devolvidas ao `backlog/` com motivo | a pasta da sprint (com features/tasks fechadas) | itens abertos → `backlog/` com motivo |
| épico | todas as sprints fechadas; DoD do objetivo | a pasta do épico inteira | não fecha; lista o que falta |
Cada fechamento grava `closed: {at, by, summary, entregue[], devolvido[], metricas}` no arquivo do item, registra o
evento e regenera `INDEX.md` — tudo numa operação atômica. Falhou → nada se move e a mensagem diz o que falta.

## 7. Integridade
- Fonte da verdade = um arquivo por item; `board.json5` deixa de existir (visões são geradas).
- `cs-state validate`: todo arquivo tem evento; cadeia de hash íntegra; nenhum órfão; hash do arquivo = hash do
  último evento (edição à mão é acusada); nada fechado dentro de `state/`; nada aberto dentro de `archive/`.
- Guard: escrita em arquivo de produto sem task em andamento → bloqueio com a dica
  `cs-state new task --tipo FIX --avulsa ...` (o mínimo; nada mais é exigido).

## 8. Salvar e carregar sessão — carimbo cirúrgico, zero dúvida
`cs-session save` (`/salvar-sessao`) monta o carimbo SOZINHO a partir do disco (o modelo passa no máximo 1 linha).
Grava `.swarm/state/sessoes/<timestamp>.json5` e imprime ≤2.000 tokens com, nesta ordem:
1. **Fechado nesta sessão** — cada item com o resumo de fechamento e para onde foi em `archive/`.
2. **Frente atual** — cadeia completa (ex.: `EPC-001 › SPR-003 › FEA-007`), caminho em `state/`, critério de pronto,
   progresso (tasks fechadas/total).
3. **Tasks da frente atual** — 1 linha por task: id, tipo, status, agente, resumo de 1 frase, bloqueio, último veredito.
4. **Em andamento** — delegação em voo (agente, task, desde quando); arquivos sujos no git por território.
5. **Próximos passos** — a sequência exata; CADA passo com o comando pronto para copiar; o 1º é o que a próxima
   sessão roda primeiro.
6. **Backlog imediato** — próximas frentes (de `backlog/`, READY primeiro) e por que nessa ordem.
7. **Decisões e pendências humanas** — portões aguardando, perguntas abertas (`gap.*`) que bloqueiam.
8. **Integridade** — carimbo (hash do estado + HEAD + último evento).
`save --check` FALHA se faltar bloco (vazio só com "nenhum" explícito) ou se um passo não tiver comando.
`cs-session load` (`/carregar-sessao`) imprime o carimbo; se não bate, mostra só o delta desde o save e reordena
os próximos passos. A sessão nova executa o passo 1 sem reler nada.

## 9. Migração (`upgrade`, `kind: state-tree`)
`board.json5` legado → árvore: épico/sprint/feature/task nos lugares das seções 2–3; story legada vira task do tipo
correspondente (US/BUG/FIX) preservando id antigo em `legacy_id`; fechados vão para `archive/`, abertos para
`state/` ou `backlog/` conforme o status; cadeia de `events.jsonl` preservada e estendida; idempotente; com backup.

## 10. Cenários de aceite (oráculo — entram antes do freeze)
- TREE-A/B/C/D: cada combinação da seção 1 cria exatamente a árvore da seção 3.
- TREE-INV: feature sem sprint em execução, sprint dentro de feature, épico dentro de sprint → recusados.
- TREE-TYPE: BUG sem teste que falha não começa; FIX sem `fixes` não começa; US sem critério não começa.
- STORY-1: story com 1 agente → task tipada em `tasks/`; com 2 agentes → pasta `stories/<id>/` com `story.json5` e
  uma task por agente; `promote` converte simples→composta mantendo id e histórico.
- ONE-FEATURE: com uma feature em `state/`, `start` de outra é recusado até `close` ou `park` da atual.
- PARALLEL-1: duas tasks da feature ativa sem arquivos em comum despacham em paralelo; com arquivo comum (ou par em
  `do_not_parallelize`) a segunda vai para a wave seguinte.
- TREE-GUARD: alteração de produto sem task → bloqueada com a dica; com 1 task avulsa → liberada.
- TREE-HAND: arquivo de item editado à mão → `validate` acusa.
- TREE-MOVE: `plan`/`move` levam itens entre backlog/state e entre pais, mantendo id e histórico.
- ARCHIVE-1: `close sprint` com tudo fechado move a sprint (com features/tasks) para `archive/`; nada dela em `state/`.
- ARCHIVE-2: `close sprint` com task aberta e `--devolver` → task vai para `backlog/` com motivo; sprint arquivada.
- ARCHIVE-3: `close feature` com task aberta → recusa listando; nada movido.
- ARCHIVE-4: task avulsa fechada → `archive/tasks/<ano>/<mês>/`.
- ARCHIVE-5: `reopen` devolve ao `state/` com histórico e cadeia de eventos válidos.
- ARCHIVE-6: `close épico` só com todas as sprints fechadas; move a árvore inteira.
- SESSION-1: `save` com 2 tasks fechadas, 1 delegação em voo e 1 portão pendente gera os 8 blocos; todo passo tem
  comando; ≤2.000 tokens.
- SESSION-2: `save --check` falha com bloco vazio sem "nenhum" explícito ou passo sem comando.
- SESSION-3: sessão nova (subagente sem histórico), só com `load`, executa o passo 1 corretamente.
- MIGRATE-1: alvo com `board.json5` legado (use um alvo de iteration-4/) → árvore equivalente, stories viram tasks
  com `legacy_id`, cadeia de eventos válida.
- Nenhuma escrita em `backlog/`, `state/` ou `archive/` feita pelo modelo em nenhum cenário (só pelo motor).
