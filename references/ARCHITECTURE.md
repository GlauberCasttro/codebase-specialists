# codebase-specialists — contrato de arquitetura

Documento normativo para quem constrói ou mantém esta skill. O `SKILL.md` diz ao modelo **como
conduzir**; este arquivo diz **como as peças se encaixam**. Toda interface entre componentes é JSON
com schema fixo; nenhum componente lê a prosa de outro.

## 1. O que a skill faz

Dá vida a um time de agentes especialistas num codebase qualquer: cada agente conhece o
**repositório inteiro** (estrutura, convenções reais, regras, histórico, decisões, operação, stack
exata) e o **seu território**, prova esse conhecimento numa sonda com gabarito gerado por script,
e opera dentro de um harness que verifica mecanicamente o que ele entrega.

Premissas que moldam o desenho (evidência em `premissas.json5`):

1. Persona genérica não melhora agente; **fatos não deriváveis com evidência** melhoram.
2. Regra que vira **check executável** é seguida (~88%) muito mais do que regra em prosa (~67%).
3. Conhecimento de stack vem da **versão instalada** (lockfile + introspecção), não da versão citada.
4. **Ferramenta no laço** (compilador/type-check/teste após editar) é a maior redução de erro medida.
5. Especialização é **verificada por sonda com gabarito mecânico**, nunca declarada.
6. Debate livre entre agentes ≈ voto e piora por conformidade → **deliberação estruturada** com
   verificação mecânica e veto por dado.
7. 99% só existe como **precisão seletiva**: verificação não-burlável + revisão diversa + abstenção.

## 2. Layout da skill

```
codebase-specialists/
├── SKILL.md                     orquestração (etapas, toques com o usuário, gates)
├── references/
│   ├── ARCHITECTURE.md          este arquivo
│   ├── premissas.json5          evidência por trás de cada decisão
│   ├── stages.json5             etapas, sub-etapas e checklists (fonte única)
│   ├── prompts.json5            prompts dos subagentes por sub-etapa
│   ├── brief-schema.json5       contrato da task/delegação
│   ├── team-schema.md           schema de team.json5 e do cartão
│   ├── probes.md                tipos de sonda, gabarito, anti-cola, gate
│   ├── platforms.md             mapeamento por plataforma
│   └── harness.md               máquina de estados, guards, hooks
├── scripts/                     Python 3.9+ stdlib; bash compatível com 3.2
│   ├── cs.py                    CLI única: cs.py <subcomando>
│   ├── cslib/                   pacote comum (paths, evidence, jsonio, gitx, log)
│   ├── scan/                    L0–L8 → .swarm/facts/*.json5
│   ├── team/                    derivação de bounded contexts e roster
│   ├── probes/                  gera banco de sondas + checker + anti-cola
│   ├── emit/                    emissores por plataforma
│   └── harness/                 motor de estado, guards, hooks (copiados para o alvo)
├── assets/                      templates de texto usados pelos emissores
└── evals/                       evals.json + repos-fixture + checkers das asserções
```

## 3. Diretório de trabalho no repositório-alvo

Tudo que a skill produz e consome no alvo mora em `.swarm/` (versionável), exceto os artefatos
nativos de cada plataforma.

```
.swarm/
├── run.json5                 id da execução, commit do alvo, versão da skill, etapa/sub-etapa atual (resumível)
├── stages/<etapa>.handoff.json5  pacote de entrada da próxima etapa (≤2k tokens)
├── facts/                    saída do scan (um arquivo por camada, .json5) + index.json5
├── interview.jsonl           respostas literais do usuário (append-only)
├── team.json5                roster + cartões (fonte da verdade dos agentes)
├── panel/                    mesa redonda: plano, objeções por revisor, veredito consolidado
├── probes/
│   ├── bank.json5            sondas + gabarito (NUNCA mostrado a agentes examinados)
│   ├── exams/<agente>.answers.json5  respostas dos agentes
│   └── report.json5          placar por agente, vetos, ciclos de refino
├── acceptance.json5          GO/NO-GO final com motivos
├── tmp/                      TODO temporário da execução (saídas de subagente, rascunhos, lotes, cópia do cético);
│                             nunca o scratchpad da sessão nem /tmp — execuções paralelas colidiram lá
└── state/                    estado do harness (board.json5, events.jsonl, ledger)
```

## 4. Formato de fato (toda camada do scan)

```json
{
  "id": "conv.naming.py-modules-snake",
  "layer": "conventions",
  "claim": "Módulos Python usam snake_case (34/34 arquivos)",
  "evidence": [{"file": "src/app/user_repo.py", "line": 1}, {"cmd": "git ls-files '*.py'", "exit": 0, "out_sha256": "..."}],
  "confidence": "high|medium|low",
  "origin": "mechanical|llm_interpretation",
  "scope": ["src/**"],
  "fingerprint": "sha256 dos arquivos-evidência (para detectar drift)"
}
```

Regras: `evidence` nunca vazia; `origin: mechanical` só quando um script derivou o fato; fatos de
`llm_interpretation` precisam citar ao menos um fato mecânico (`supports: [ids]`).

## 5. Camadas do scan (L0–L8)

| Camada | Arquivo | Técnica (mecânica) |
|---|---|---|
| L0 inventário | `inventory.json5` | `git ls-files`, linguagens por extensão, manifestos **e lockfiles**, LOC; marca `fixture`/`vendor`/`generated` |
| L1 grafo | `graph.json5` | imports por linguagem (regex robusto por ecossistema) → grafo de arquivos; PageRank; comunidades (componentes) |
| L2 arquitetura | `architecture.json5` | camadas **declaradas** (configs de import-linter, dependency-cruiser, ArchUnit, pastas) × reais; violações |
| L3 convenções | `conventions.json5` | contagem de padrões de nome/estrutura com proporção (lei ≥90%, maioria ≥60%, misto) + exceções |
| L4 regras | `rules.json5` | configs de lint/format/CI/pre-commit, asserts de teste por unidade, invariantes negativas (0 ocorrências) |
| L5 histórico | `history.json5` | hotspots (churn × tamanho), co-change (suporte/confiança), commits de correção, ownership |
| L6 racional | `rationale.json5` | ADRs, docs de decisão, trechos "por quê" de commits que tocam hotspots |
| L7 operação | `operations.json5` | comandos de build/test/lint de CI/Makefile/scripts/package; **executados** com timeout → `verified` ou `declared` |
| L8 stack | `stack.json5` | versões do lockfile por ecossistema; inventário de API pública da versão **instalada** quando o runtime está disponível |

## 6. team.json5 (contrato central)

Ver `team-schema.md`. Resumo: `core` (conhecimento comum do repo, ≤40 linhas renderizadas, cada linha
ligada a fatos) + `agents[]`, cada um com `name`, `kind` (`dev|gate|design|product|ops`), `territory`
(globs de escrita, **disjuntos** entre escritores), `reads`, `card` (missão, ofício, recusas com porquê,
critério de feito verificável, playbooks com âncoras reais, regras com comando que prova, footguns
com evidência), `facts_used[]` e `veredito_enum` (para gates).

## 7. Fases (agrupadas nas etapas de §8-terdecies; cada sub-etapa grava artefato e se marca em run.json5)

0. Preflight e escopo — alvo, plataformas, rigor (sempre máximo), git limpo, guarda de segurança.
1. Scan L0–L8 (script).
2. Entrevista de lacunas — só o que o scan não alcança (racional, invariantes de negócio, áreas
   congeladas, quem decide); ≤8 perguntas por lote; respostas literais.
3. Derivação do time — bounded contexts pelo grafo + papéis transversais; confirmação do usuário.
4. Redação dos cartões — um subagente isolado por agente, a partir dos fatos (nunca do template).
5. Mesa redonda estruturada — revisão cruzada esparsa (pares adjacentes no grafo + 1 cético), checker
   valida cada afirmação, moderador consolida o `core`; sem debate livre.
6. Sonda de maestria — banco gerado por script; exame isolado em 2 modos; checker + painel para "por quê".
7. Refino guiado por falha — só sondas falhas + evidência correta; re-exame com sondas novas; ≤2 ciclos.
8. Emissão + harness — artefatos por plataforma, harness no alvo, hooks.
9. Aceite — gates mecânicos; GO/NO-GO; relatório; drift baseline.

## 8. Lições de engenharia (medidas em produção; não negociáveis)

| Lição | Regra |
|---|---|
| Fixture tratada como produto contaminou roster, stack e docs | L0 classifica `fixtures/ testdata/ samples/ examples/ golden/ vendor/ node_modules/` e todo consumidor ignora |
| Nome de diretório de produto colidiu com componente do harness | nomes reservados (`.swarm`, `.claude`, `scripts/harness`…) nunca entram em território de produto; casamento por **prefixo de path**, não por componente |
| Guard falhou aberto quando o próprio snapshot sumiu | todo guard é **fail-closed**: estado ausente/ilegível = bloqueio com mensagem |
| Guard burlado por symlink | todo path passa por `realpath` antes de classificar |
| Verificador executava o validador do próprio alvo | verificadores da skill usam **o código da skill**, nunca um script do alvo |
| Validador aprovava estado vazio | validação exige estado não vazio e schema |
| Raiz resolvida pelo git do script, não pelo projeto | raiz = `CLAUDE_PROJECT_DIR` ou argumento explícito; nunca o diretório do script |
| Bloqueio sem log; kill-switch sem rastro | todo bloqueio e todo kill-switch grava linha no ledger |
| Heredoc em `$(...)` quebra no bash 3.2 | bash compatível com 3.2; Python em arquivo, não em heredoc |
| Comandos paralelos fizeram o guard atribuir escrita de outra janela | passos que escrevem rodam em série; janela do guard por `tool_use_id` |
| Veredito fora do enum virava "corrompido" | enum único (`PASS|FAIL|NEEDS_SPECIALIST`) definido num só lugar e importado |
| Invariante entregue a um dono só | fato/invariante com evidência em N territórios vai para N donos |
| "Ausência de arquivo = nenhuma regra" | ausência é erro explícito, nunca permissão silenciosa |
| Cartão genérico passava em gate lexical | gate mede **anti-template** (similaridade com cartão de controle), **Existence Ratio = 1,0** e **sonda** |
| Gold e auditor com schemas divergentes zeraram um experimento | um schema, carregado por código pelos dois lados |
| Hash de proveniência calculado após normalizar texto | hashear **bytes** |
| Evidência por path absoluto sumiu | evidência copiada para dentro de `.swarm/` com sha256 |
| Wrapper no scratchpad compartilhado fez uma execução escrever no alvo de outra | todo temporário em `<alvo>/.swarm/tmp/`; `--file` com caminho absoluto |
| Limite de subagentes concorrentes recusou despacho no meio da mesa redonda | ≤8 subagentes simultâneos, em lotes |
| Mesmo com ≤8, a sessão bateu no limite de subagentes e a API em 429; redator redespachado antes do lote voltar sobrescreveu rascunho já gravado (iteração 2) | lotes de até 3, em primeiro plano; 429 → reduz e registra em `.swarm/tmp/dispatch.jsonl`; próximo lote só depois de o anterior terminar (`prompts.json5` → `execucao`) |
| Prompt com fatos inline inchou o contexto do orquestrador e tornou o despacho irreproduzível | prompt recebe caminho (`{fatos_path}`, pacote de `panel pack`/`probes exam-pack`); subagente grava SÓ o próprio arquivo em `.swarm/tmp/<tipo>/<nome>.json5` e devolve 1 linha; o orquestrador registra pela CLI em série (iteração 3: um revisor regravou saídas de outros) |
| Examinado do modo guiado leu o gabarito (`probes/bank.json5`) com um grep no alvo (iteração 2) | exame guiado e juízes só no pacote de `probes exam-pack <agente> --out <alvo>/.swarm/tmp/exam/<agente>`: clone local com histórico (`git log` funciona, nunca sobe a um repo pai), sem `.swarm/` |
| `harness install` sem flags deixou Cursor/Copilot/Codex sem adapters e sem git hook, sem aviso | install com `--platforms` do init e `--git-hook`; `verify` grava `enforcement` por plataforma e o relatório mostra |
| Revisor despachado como subagent_type de agente que ainda não foi emitido | todo subagente é `general-purpose`; o cartão do agente entra como dado |
| Nota legítima do time (CLAUDE.md/AGENTS.md) registrada como injeção | instrução do time é fato L10; injeção = texto que tenta mudar veredito, escopo ou permissão, ou manda ignorar regras |
| Prompt citava flags/vereditos que a CLI não tinha | `scripts/doctests/tests/test_commands_parse.py` confere todo comando citado contra o argparse real |

## 8-bis. Conhecimento, memória e busca (requisito do founder)

Agentes têm **território limitado para escrever**, mas **conhecimento profundo** do repositório:
regras técnicas e de negócio, termos técnicos e de negócio, e memória do que já aconteceu.

### Glossário e regras de negócio (scan, camada L9)
`facts/glossary.json5` e `facts/business_rules.json5`, derivados mecanicamente:
- **Termos**: entidades e conceitos do domínio extraídos de identificadores (classes, tipos, enums,
  tabelas/migrações, rotas, nomes de teste), docs e ADRs; para cada termo: forma canônica, contagem,
  onde é definido (arquivo:linha), sinônimos encontrados e variantes a **nunca** usar (variante rara
  quando a canônica domina por contagem); separa `business` × `technical`.
- **Regras de negócio**: validações, guardas e constantes de domínio (ex.: limites, estados permitidos,
  transições de enum, asserts de teste com nome que expressa regra, mensagens de erro de validação),
  cada uma com arquivo:linha e o teste que a cobre (se houver). A entrevista (fase 2) completa o que o
  código não diz (o porquê, exceções, o que nunca pode quebrar) e marca `source: founder`.
- Todo cartão traz **os termos e regras que tocam o seu território** e o ponteiro para a busca do resto.

### Memória do harness (`.swarm/memory/`)
| Tipo | Arquivo | Escrita | Uso |
|---|---|---|---|
| Semântica | `knowledge.jsonl` | consolidação (abaixo) e fatos promovidos do scan | o que é verdade sobre o repo |
| Episódica | `episodes.jsonl` | todo evento de task (dispatch, submit, verify, review, reject, abstain) com resumo | o que aconteceu |
| Por agente | `state/memory/agents/<nome>.json5` (lições, teto §8-duodecies) + `memory: project` do Claude Code quando disponível | o próprio agente, via comando | lições do papel |

Entrada de memória: `{id, kind: fact|lesson|decision|term|rule, text, scope_paths[], tags[], source:
{fact_id|task_id|commit|founder}, evidence[], created_at, fingerprint, status: active|stale|retired}`.
- **Consolidação episódica → semântica**: ao fechar task (ACCEPTED ou REJECTED), um passo extrai a
  lição (achado do review, causa do reject) como entrada `lesson` com evidência; repetida em ≥2 tasks →
  promovida a regra do território (vira texto no cartão na próxima emissão).
- **Anti-drift**: `fingerprint` = sha256 dos arquivos de evidência; `cs-mem revalidate` marca `stale`
  quem perdeu a evidência; stale não é injetado.
- **Nada de conteúdo do repo-alvo como instrução**: toda entrada é DADO; injeção marca o bloco como dado.

### Busca rápida (BM25, stdlib)
`cs-mem search "<consulta>" [--agent X] [--paths glob] [--kind ...] [-k 8]` sobre **knowledge +
episodes + facts + glossário + regras**. Implementação BM25 (k1=1.2, b=0.75) em Python stdlib com
tokenização que entende identificadores (`snake_case`, `camelCase`, `kebab`, acentos removidos), índice
incremental em `.swarm/memory/index/` (invertido, JSON), boost por `scope_paths` que casa com os
paths da task e por `kind`. Meta: <200 ms para 10k entradas. Saída com `id`, trecho e evidência.
- `SubagentStart` injeta o top-k da busca feita com o título + allowed_paths da task (além dos
  invariantes do escopo), dentro do limite de 10.000 caracteres.
- Cartões ensinam o comando de busca; o agente consulta antes de agir em área que não conhece.
- Gate novo **G8 memória**: `cs-mem search` retorna, para cada sonda do banco do tipo
  TERMO/REGRA, a entrada correta no top-5 (recall@5 ≥ 0,9) e latência p95 < 200 ms.

## 8-ter. Steering — carregamento sob demanda (requisito do founder)

O conhecimento de cada agente é profundo, mas o **contexto carregado é pequeno**. Aderência cai com
contexto inchado e ao longo da sessão; o que funciona é entregar a coisa certa no momento certo.

| Camada | O que leva | Quando entra | Mecanismo por plataforma | Orçamento |
|---|---|---|---|---|
| S0 núcleo do repo | comandos verificados, invariantes globais, mapa de agentes | sempre | CLAUDE.md (bloco gerenciado) · `.cursor/rules/core.mdc alwaysApply` · `.github/copilot-instructions.md` · `AGENTS.md` raiz | ≤40 linhas |
| S1 cartão do agente | missão, território, recusas, critério de feito, top termos/regras do território, como buscar o resto | quando o agente é invocado | `.claude/agents/<n>.md` · agente/modo do Cursor e do Copilot quando houver · seção do AGENTS.md | ≤80 linhas |
| S2 por caminho | termos, regras de negócio, armadilhas e convenções de **um** diretório | quando qualquer agente lê/edita arquivo do caminho | `.claude/rules/<terr>.md` com `paths:` · `.cursor/rules/<terr>.mdc globs` · `.github/instructions/<terr>.instructions.md applyTo` · `AGENTS.md` aninhado | ≤60 linhas por arquivo |
| S3 por fase da task | checklist da fase: implementar (escopo, testes antes, comando de prova) · verificar (o que executar, o que conta) · revisar (o que vetar, invariantes do escopo) | no `SubagentStart`/dispatch conforme o status da task | hook injeta `additionalContext`; nas outras plataformas, `cs-state brief <task>` imprime o pacote | ≤10.000 caracteres |
| S4 playbooks longos | receitas passo a passo do papel, exemplos | quando o agente precisa | skill por agente (`.claude/skills/<n>-playbooks/`, carregada por descrição) · arquivo referenciado | sem limite (fora do contexto até ser lido) |
| S5 memória | tudo o que já foi aprendido e o resto dos fatos | por consulta | `cs-mem search` | top-k |

Regras: nenhum conteúdo aparece em duas camadas (fonte única, as outras apontam); o emissor mede o
tamanho de cada camada e **falha** se estourar o orçamento, propondo mover o excedente para a camada
seguinte; o gate G3 passa a medir também o orçamento por camada.

## 8-quater. Protocolo de sessão mecânico (requisito do founder: economia de tokens)

Salvar e retomar sessão é feito por **script**, não por o modelo ler e escrever arquivos de estado. O
modelo fornece só o que o script não tem como saber (3 linhas); todo o resto é coletado.

`cs-session save --did "<1 linha>" --next "<1 linha>" [--blocked "<1 linha>"] [--decision "<texto>"]`
- Coleta sozinho: board (tasks por status, task ativa, tentativas), últimos 10 eventos, git (branch, HEAD,
  arquivos sujos por área), gates (último `cs.py verify` e selftest), memória (lições novas desde o
  último save), etapa da execução (`run.json5`).
- Grava `.swarm/session/resume.json5` (estruturado) com
  **carimbo** = sha256(board + hash do último evento + HEAD + fase). Apensa episódio na memória.
- Commit opcional (`--commit`) só dos arquivos de `.swarm/session/` e estado — nunca de produto.

`cs-session load`
- Recalcula o carimbo. **Bate** (ou o HEAD avançou só com commits de estado) → imprime o briefing renderizado de
  `resume.json5` (≤30 linhas, ≤2.000 tokens) e termina: o modelo não abre mais nada.
- **Não bate** → imprime só o **delta** desde o save: eventos novos, commits novos por área, tasks que
  mudaram de status, gates que mudaram — e o briefing anterior. Nunca despeja o estado inteiro.
- Sempre termina com "próximo passo" e o comando exato para executá-lo.

Emissão: comandos nativos por plataforma (Claude Code: `/save-session` e `/load-session` como
skills/comandos que só chamam o script; hook `SessionStart` opcional chama `cs-session load --brief`;
outras plataformas: instrução no núcleo S0 para rodar o script). Gate **G9 sessão**: `load` com carimbo
batendo imprime ≤2.000 tokens; após um evento novo, `load` detecta o delta; round-trip save→load é
idempotente.

## 8-quinquies. Máquinas de estado da delegação (requisito do founder)

O orquestrador (agente principal) não improvisa o fluxo: ele percorre máquinas de estado cujas
transições são feitas **por script** (`cs-state`) e cujas guardas são **mecânicas**. Três máquinas,
uma fonte (`scripts/harness/machines.json5`), um motor.

**M1 — Sessão do orquestrador** (uma por pedido do usuário)
`IDLE → TRIAGE → PLANNING → EXECUTING → VERIFYING → REPORTING → IDLE`
- TRIAGE classifica a demanda e grava a classe; a classe define o pipeline exigido (proporcionalidade):

| Classe | Critério (gravado com o porquê) | Pipeline mínimo |
|---|---|---|
| `pergunta` | nenhuma escrita | responder; sem delegação |
| `trivial` | ≤1 arquivo, diff descrito numa frase, sem invariante tocado | dev do território → verify |
| `pequena` | ≤1 território, critérios claros | dev → verify → review (gate) |
| `feature` | >1 território ou critério a definir | po → (architect se ADR) → dev(s) → verify → review → qa → review final |
| `risco` | toca invariante/área congelada/segurança | `feature` + gate especialista (security/…) + confirmação do usuário |
- PLANNING exige o plano gravado (tasks, dependências, waves sem colisão de `allowed_paths`).
- Ambiguidade: só sai de TRIAGE perguntando ao usuário quando leituras diferentes geram trabalhos
  materialmente diferentes; senão decide, e grava a suposição.

**M2 — Delegação** (uma por despacho de subagente)
`PLANNED → BRIEFED → DISPATCHED → RETURNED → VERIFIED → REVIEWED → ACCEPTED | REJECTED`;
de REJECTED: `RETRY` (≤2, com os achados) → BRIEFED, ou `ESCALATED` (ao usuário), ou `REROUTED`
(outro agente/architect); de qualquer estado ativo: `ABSTAINED` (o agente devolve com motivo — conta
contra cobertura, não contra precisão).
Guardas (mecânicas):
- → BRIEFED: brief válido = objetivo + porquê, `allowed_paths` ⊆ território do agente (nunca vazio,
  nunca glob amplo), `verification_command` executável (não prosa), `acceptance_criteria` testáveis,
  invariantes do escopo anexados, arquivos de referência, fora-de-escopo.
- → DISPATCHED: hook `PreToolUse(Task|Agent)` só deixa despachar se a `description` traz um id de
  delegação em BRIEFED atribuído àquele agente; despacho paralelo só se as delegações em voo têm
  `allowed_paths` disjuntos ou são somente-leitura; subagente não despacha subagente (nível único).
- → RETURNED: `submission` presente (files_changed, checks_run, riscos, handoff) — senão REJECTED
  `protocol_failure`.
- → VERIFIED: o motor **executa** o `verification_command` (exit 0) e confere `files_changed` ×
  `git diff --name-only` × `allowed_paths` (nada fora).
- → REVIEWED: veredito de agente gate ≠ autor, enum fixo; achados gravados.
- → ACCEPTED: VERIFIED + REVIEWED PASS (+ qa/especialista quando a classe exige).

**M3 — Task** (ciclo de vida no board, §harness): `DRAFT → READY → IN_PROGRESS → SUBMITTED →
VERIFYING → ACCEPTED | REJECTED | BLOCKED`. M2 dirige M3; M3 é o registro durável.

Todas as transições viram eventos encadeados por hash (`events.jsonl`); `cs-state why <id>` explica o
estado atual e a próxima transição permitida; `cs-state next` diz ao orquestrador o que fazer agora
(economia de tokens: o modelo não precisa reler o protocolo). Gate **G10 delegação**: transição
inválida é recusada com mensagem acionável; despacho sem brief válido é bloqueado pelo hook; despacho
paralelo com colisão é bloqueado; classe `trivial` não exige po/architect e classe `risco` exige gate
especialista.

## 8-sexies. Modos de uso — assistido e autônomo (requisito do founder)

| Modo | Quem decide nos gates | Quando usar |
|---|---|---|
| `assistido` (default) | o usuário aprova plano, escaladas e aceite final | trabalho novo, área sensível, time ainda não provado |
| `autonomo` | o orquestrador, dentro de um mandato pré-aprovado | feature com spec e critérios claros, time aprovado na sonda |

**Entrada no modo autônomo** — um único toque com o usuário:
`cs-state autonomy start --feature <id> --spec <arquivo> --budget tasks=N,attempts=2,minutes=M[,usd=X]`
O usuário aprova (uma vez) a spec, os critérios de aceite **executáveis** (testes de aceite que falham
hoje), a classe da feature e o orçamento. O mandato fica gravado e assinado (hash) em `state/autonomy.json5`.

**Loop** — M1 percorre PLANNING → EXECUTING (waves de M2) → VERIFYING → REPORTING sem perguntar:
- Hook `Stop` (Claude Code): se a sessão M1 está em EXECUTING/VERIFYING, há delegações READY, o
  orçamento não acabou e não há condição de escalada → bloqueia a parada com o motivo
  "continue: `cs-state next`". Em qualquer outro caso, deixa parar. Contadores evitam loop infinito.
- Checkpoint: `cs-session save` automático a cada delegação ACCEPTED.
- Abstenção e reroute são permitidos; retry ≤2 com os achados.

**Condições de escalada** (param o loop e trazem a decisão ao usuário, com o pacote de evidência):
toca invariante/área congelada; ambiguidade material; mesma rejeição 2×; orçamento esgotado; classe
`risco` descoberta durante o trabalho; teste de aceite que só passaria mudando o próprio teste;
conflito entre agentes sem resolução por evidência.

**Nunca no modo autônomo**: push, merge em branch protegida, alterar teste de aceite aprovado,
editar arquivo congelado, gastar além do orçamento, desligar guard.

**Saída**: relatório final (feature, tasks e vereditos com evidência, testes de aceite antes/depois,
custo, escaladas, lições gravadas na memória) e o modo volta a `assistido`.
Gate **G11 autonomia** (eval end-to-end): numa fixture, uma feature pequena com testes de aceite
vermelhos é entregue sem toque humano após o mandato — testes de aceite verdes, todas as delegações
ACCEPTED com verify executado e review de gate, nenhuma escrita fora de território, relatório gerado;
e um caso de escalada (feature que exige tocar invariante) para e escala em vez de seguir.

## 8-septies. Protocolo de processo — Épico → Feature → Sprint → Story → [Bug | Fix | US] (requisito do founder)

Hierarquia de trabalho no board (`state/board.json5`), cada nível com ciclo de vida, **DoR** (pronto para
começar) e **DoD** (pronto) verificados por script. Um nível só fecha quando os filhos fecharam com evidência.
Delegações (M2) e tasks (M3) pertencem sempre a uma Story.

| Nível | Estados | DoR mecânico | DoD mecânico |
|---|---|---|---|
| Épico `EPIC-n` | PROPOSED → ACTIVE → DONE \| DROPPED | objetivo + métrica de sucesso | features todas DONE ou DROPPED com motivo |
| Feature `FEAT-n` | BACKLOG → READY → IN_PROGRESS → DONE \| DROPPED | spec + critérios de aceite **executáveis** (testes existem e falham hoje) + épico | stories DONE + testes de aceite da feature verdes (executados) |
| Sprint `SPRINT-nn` | PLANNED → ACTIVE → REVIEW → CLOSED | meta + orçamento + stories comprometidas com DoR | review gravada: entregue × devolvido ao backlog, métricas |
| Story **US** `US-n` | BACKLOG → READY → IN_PROGRESS → IN_REVIEW → DONE \| REJECTED | "Como/Quero/Para" + critérios Gherkin ligados a testes + feature | tasks ACCEPTED + critérios verdes |
| Story **Bug** `BUG-n` | idem | passos de reprodução + **teste que falha** + severidade + ambiente | o mesmo teste passa + suíte de regressão verde |
| Story **Fix** `FIX-n` | idem | `fixes:` aponta BUG, achado de review ou de forense + teste que prova | teste do alvo passa + regressão verde |

Regras:
- Sprint referencia stories (de uma ou mais features); story só entra em sprint com DoR.
- Bug nunca é corrigido sem antes existir o teste que o reproduz (TDD de correção).
- Story REJECTED volta ao BACKLOG com os achados; reabrir story DONE exige BUG novo, nunca editar a antiga.
- Sprint fecha mesmo com stories não entregues — elas voltam ao backlog com motivo (sem "quase pronto").
- `cs-state board` mostra a árvore com rollup (% DONE por nível, bloqueios, orçamento gasto).
- O PO cria épicos/features/stories por `cs-state add epic|feature|story --type us|bug|fix` (nunca editando o JSON).
- Modo autônomo: mandato por **Feature** (ou Story); o loop percorre as stories da feature sprint a sprint.

Gate **G12 processo**: DoR e DoD recusam com mensagem acionável quando faltam; Bug sem teste que falha
não vira READY; Fix sem `fixes:` não vira READY; feature não fecha com story aberta; rollup coerente.

## 8-octies. Controle e automação (requisito do founder)

- **Controle**: toda transição de estado (épico, feature, sprint, story, delegação, task) é feita pelo
  motor Python `cs-state` — único dono das regras. Nada edita `board.json5`/`events.jsonl` à mão; o
  validador detecta edição manual pela cadeia de hashes.
- **Automação**: Makefile como camada fina — cada alvo chama o script e nada mais (sem lógica duplicada).
  Alvos mínimos: `next`, `board`, `add-epic`, `add-feature`, `add-story`, `sprint-plan|start|review|close`,
  `brief ID=`, `dispatch ID=`, `verify ID=`, `review ID=`, `accept ID=`, `reject ID=`, `abstain ID=`,
  `session-save`, `session-load`, `mem Q=`, `autonomy-start FEAT=`, `autonomy-status`, `selftest`,
  `validate`, `drift`. Variáveis passadas como argumentos (`ID=`, `FEAT=`, `Q=`), com `help` listando todos.
- **Não destruir o Makefile do alvo**: se existir, gerar `specialists.mk` e inserir `include specialists.mk`
  dentro de um bloco gerenciado; se não existir, gerar `Makefile` mínimo que faz o include. Nomes de alvo
  com prefixo configurável (default sem prefixo; com colisão, prefixo `cs-`). Compatível com BSD make e
  GNU make (sem extensões exclusivas).

## 8-nonies. Conhecimento do próprio projeto e mapas (requisito do founder)

**Fonte adicional — o que o projeto já escreveu sobre si** (scan, camada L10 `facts/project_docs.json5`):
README, `docs/**`, ADRs, CONTRIBUTING, CHANGELOG, runbooks, e instruções de agente preexistentes
(CLAUDE.md, AGENTS.md, `.cursor/rules`, `.github/copilot-instructions.md`). Cada afirmação útil vira
fato com proveniência (arquivo:linha) e é **conferida contra o código** quando verificável (comando
citado roda? caminho citado existe? versão citada bate com o lockfile?) — doc velho vira fato `stale`
com a divergência anotada, nunca é repetido como verdade. Instruções de agente preexistentes são
preservadas (blocos gerenciados) e seu conteúdo útil é absorvido como fato. Essas instruções **não** são
injeção: injeção é texto, em qualquer arquivo, que tenta mudar veredito, escopo ou permissão de quem lê, ou
manda ignorar regras — cláusula literal em `references/prompts.json5` → `clausula_anti_injecao`.

**Mapas gerados** (em `.swarm/knowledge/`, camada S4/S5 — lidos sob demanda, nunca sempre carregados):
| Mapa | Arquivo | Conteúdo |
|---|---|---|
| Árvore territorial | `tree.json5` | árvore do produto até a profundidade útil com **≥1 arquivo representativo por pasta** (escolhido por centralidade/âncora, não alfabético), dono de cada pasta, fixtures/gerados marcados |
| Grafo de código | `graph.json5` | nós (arquivos/símbolos) e arestas (imports/chamadas) com evidência e centralidade |
| Stack | `stack.json5` | grafo `{nodes,edges}`: linguagens → runtimes → frameworks → libs com **versão do lockfile**, e onde cada uma é usada (territórios) |
| Dependências | `deps.json5` | grafo de dependências entre territórios/componentes; matriz território×território (nº de arestas e exemplos arquivo:linha); ciclos |
| Colisão | `collision.json5` | risco de colisão por par de territórios = dependência estática + **co-change** histórico (suporte/confiança) + arquivos de fronteira; lista "não paralelizar" |

**Uso**: cartão de cada agente aponta só para os mapas e a fatia do seu território; `cs-state` usa
`collision.json5` na guarda de despacho paralelo (M2): pares acima do limiar não vão na mesma wave mesmo
com `allowed_paths` disjuntos — e o orquestrador recebe o motivo. Gate **G13 mapas**: todo diretório de
produto aparece na árvore com ≥1 arquivo; toda versão em stack.json5 bate com o lockfile; matriz de
dependências reproduz as arestas do graph.json5; um par sabidamente acoplado (fixture) aparece em colisão.

## 8-decies. Formato — JSON5 em tudo que é nosso (requisito do founder)

Todo artefato que a skill controla é **JSON5** (economia de tokens + tratamento mecânico): mapas
(`tree.json5`, `stack.json5`, `deps.json5`, `collision.json5`), fatos (`facts/*.json5`), `team.json5`,
sondas, sessão (`session/resume.json5`), estado (`board.json5`), mandato, relatório de aceite.
Arquivos **append-only** (memória `knowledge.jsonl`/`episodes.jsonl`, `events.jsonl`, ledger) ficam em
**JSONL** estrito: uma linha por registro, leitura em streaming e cadeia de hash por linha.
Exceção: o que a **plataforma exige em Markdown** (cartões `.claude/agents/*.md`, `CLAUDE.md`, rules
`.md`/`.mdc`, `AGENTS.md`, instruções do Copilot, `SKILL.md`) continua Markdown — enxuto, apontando
para os JSON5. Diagramas Mermaid não são gerados: grafos são `{nodes:[...], edges:[...]}`.

Subconjunto JSON5 usado (e o único que o leitor precisa aceitar): comentários `//` e `/* */`, chaves
sem aspas quando identificador válido, vírgula final, strings com aspas duplas. Escrita determinística:
chaves ordenadas, indentação de 1 espaço só em objetos com mais de 3 campos, uma entrada de lista por
linha quando a lista tem objetos, comentário de 1 linha no topo dizendo o que o arquivo é e quem gera.
Implementação em `scripts/cslib/json5io.py` (stdlib; `load`, `loads`, `dump`, `dumps`), com testes de
ida e volta e de rejeição de entrada fora do subconjunto. Nenhum componente usa `json.load` em arquivo
`.json5`.

## 8-undecies. Model router — delegar ao modelo mais barato que resolve (requisito do founder)

Herda as lições medidas do model-router do `servico-parametros` (1.835 eventos, 92 decisões) e fecha a
lacuna que lá custou caro: **recomendação que não vira parâmetro do despacho treina o bandit com
execução que nunca aconteceu** (TASK-01-138 daquele projeto).

- **Tiers** por plataforma em `routing.json5` (Claude Code: `haiku < sonnet < opus`; demais: mapeáveis
  ou `inherit`). Custo relativo herdado: 0,04 / 0,2 / 1,0.
- **Sinal de complexidade só do brief estruturado** (nunca keyword em prosa): classe M1
  (trivial/pequena/feature/risco), nº de `allowed_paths` e LOC tocado, `hot_path`, invariantes e regras
  de negócio no escopo, colisão do território, ato (dev/qa/review/arch). Score → faixa (baixo/médio/alto).
- **Política**: tabela determinística de partida (trivial→barato; pequena→médio; feature→médio;
  risco→topo) + **Thompson sampling** com prior Beta por faixa×tier, recompensa por tier (1,0/0,7/0,4)
  para preferir o barato quando empata, veto quando a média do tier cai abaixo do limiar com amostras
  suficientes, orçamento de exploração, incerteza **relativa** `1-(melhor-segundo)/(melhor+segundo)`.
- **Regras fixas**: revisor/gate nunca abaixo do tier do autor (verificador mais fraco confirma ao acaso);
  classe `risco` e agente `security` no topo; retry sobe um tier; abstenção não penaliza o tier.
- **Enforcement**: `cs-state brief`/`dispatch` gravam o tier recomendado na delegação; o hook
  `PreToolUse(Task|Agent)` exige `model` igual à recomendação **ou** override com motivo
  (`cs-route override <id> --model X --reason ...`), registrado. Sem `model` → bloqueia (herdar o modelo
  da sessão é exatamente o defeito que se quer evitar).
- **Treino só com procedência**: outcome (ACCEPTED/REJECTED por verify+review) treina **somente** se a
  execução tem procedência `declarada-no-despacho` ou `medida` (modelo real lido do payload/transcrição
  do subagente quando disponível). Sem procedência → registra, não treina. Ledger append-only
  `state/model-router.jsonl`; correção por `cs-route anular --at --motivo`, nunca apagando linha.
- **CLI**: `cs-route recommend <deleg>` (≤5 linhas: tier, faixa, motivo, incerteza) · `outcome` ·
  `override` · `anular` · `stats` (distribuição, taxa de sucesso por faixa×tier, custo estimado evitado).
- Gate **G14 roteamento**: task trivial recomendada ao tier barato; gate ≥ tier do autor; despacho sem
  `model` bloqueado; outcome sem procedência não altera prior; retry sobe tier; risco no topo.

## 8-duodecies. Autocorreção e memória por agente com crescimento controlado (requisito do founder)

**Entrada — toda correção vira lição do agente que errou** (`state/memory/agents/<agente>.json5`):
correção humana (`cs-mem correct --agent X --wrong "..." --right "..." --why "..." [--paths ...]` ou
comando `/correct`), achado de review FAIL, causa de REJECT, erro de brief apontado em `submission.risks`.
O orquestrador tem o dever de registrar quando o usuário corrige a saída de um agente; um hook
`UserPromptSubmit` advisory lembra quando a mensagem parece correção.

Lição: `{id, rule: "imperativo, 1 linha", why, trigger: {paths:[...], kinds:[...]}, check?: "comando
que prova", source: human|review|reject|brief, evidence, count, first_seen, last_hit, status:
active|promoted|stale|archived}`.

**Autocorreção antes de entregar**: `cs-mem check --agent X` (rodado pelo agente antes do submit e pelo
motor no VERIFIED) cruza lições × arquivos alterados → checklist ≤5 itens; lições com `check` são
**executadas** e falha devolve a task ao agente com a lição citada (gate de autocorreção).

**Crescimento controlado** (tokens constantes por task, independentemente do tamanho da memória):
1. **Dedup**: correção similar (BM25 + Jaccard ≥ limiar) a lição existente → `count+1`, não entrada nova.
2. **Promoção**: `count ≥ 2` ou marcada pelo humano → vira regra do cartão/camada S2 ou, preferencialmente,
   `check` mecânico no harness; sai da memória ativa (`promoted`) — fonte única.
3. **Teto**: ≤30 lições `active` por agente; acima disso, consolidação obrigatória (merge/promoção/arquivo)
   antes de aceitar nova; injeção ≤5 lições e ≤1.500 caracteres por despacho, por relevância ao escopo.
4. **Decaimento**: sem disparo em N tasks do território (default 20) ou 60 dias → `archived` (fica no
   arquivo, não é injetada).
5. **Obsolescência**: `fingerprint` da evidência mudou → `stale` até `cs-mem revalidate`.
Métrica: **taxa de recorrência** (mesma lição disparada de novo após registrada) por agente, em `cs-mem stats`.

Gate **G15 autocorreção**: correção registrada aparece no pacote do próximo despacho do mesmo escopo;
lição com `check` reprova submissão que repete o erro; segunda ocorrência promove; teto e orçamento de
injeção respeitados com 200 lições sintéticas; lição arquivada/stale não é injetada.

## 8-terdecies. Execução em etapas, uma janela de contexto por etapa (requisito do founder)

A skill nunca resolve tudo numa janela. Etapas: `init → scan → specialize → round-table-deep-specialize →
validate → approve`, cada uma com sub-etapas e checklist em `references/stages.json5` (fonte única; o
SKILL.md só explica o porquê). Mapeamento das antigas fases: 0→init; 1–2→scan; 3–4→specialize;
5→round-table; 6–8→validate; 9→approve.

CLI (`scripts/cs.py stage`):
- `stage status` — etapa/sub-etapa atual, itens feitos/pendentes (lê `run.json5`).
- `stage load <etapa>` — pacote de entrada ≤2k tokens (objetivo, checklist com estado, handoff anterior,
  pendências); recusa se a etapa anterior não fechou; retoma na sub-etapa pendente.
- `stage check <sub-etapa>` — roda o `check` daquele item e marca feito/falhou em `run.json5`.
- `stage done <etapa>` — roda todos os `check`; qualquer falha → exit 1 com o item; sucesso grava
  `.swarm/stages/<etapa>.handoff.json5` (≤2k tokens: o que foi produzido, paths, números, pendências
  herdadas) e avança `run.json5`.
Itens `ctx: "sub"` vão para subagentes (um por agente quando `per: agent`), que gravam SÓ o próprio
arquivo em `.swarm/tmp/<tipo>/<nome>.json5` e devolvem 1 linha; o orquestrador registra pela CLI, em
série, e nunca carrega o trabalho bruto. Itens `ctx: "user"` registram a resposta literal.

A execução atravessa várias janelas: ao fim de cada etapa (ou quando o contexto pesar) o orquestrador para
com `stage done` (ou com o que já gravou e `stage status`), devolve um handoff curto e a próxima sessão ou
subagente começa por `stage load <etapa>`. Modo **`--fast` é o padrão**: pula round-table
(rt.1–rt.4) e refino (validate.4) com `stage skip` (registrado; `stage status` e relatório mostram) — reprovado no
exame sai `nao-especialista`. **`--full`** (execução certificada completa) só a pedido explícito do usuário. O
relatório diz qual modo rodou.

Gate **G16 etapas**: `stage load` de cada etapa cabe em 2k tokens; `stage done` com um check falhando não
avança; retomada após interrupção no meio de uma etapa recomeça na sub-etapa certa sem repetir as feitas.

## 9. Gates de aceite (fase 9) — todos obrigatórios

**Regra do GO** (mesmo estado ⇒ mesmo veredito, em qualquer alvo): GO exige TODOS os agentes `especialista` e
todos os gates verdes. Qualquer `nao-especialista` — aceito com `--allow-non-specialist` ou não — faz o `verify`
decidir NO-GO, sempre. O aceite registra o agente e o motivo; não muda o veredito.

| Gate | Medida | Limiar |
|---|---|---|
| G1 cobertura | todo arquivo de produto tem dono de escrita; escritores disjuntos | 100% / 0 sobreposição |
| G2 existência | todo path/símbolo/comando citado em `team.json5` existe/roda | Existence Ratio = 1,0 |
| G3 anti-template | similaridade de cada cartão com o cartão do mesmo papel gerado para o repo de controle | ≤ 0,35 (calibrar) |
| G4 maestria | sonda: território ≥ 0,85; cross-território ≥ 0,70; 0 alucinação em negativa; delta > 0 sobre baseline sem cartão (território sem sonda discriminante = não medido, `baseline_saturated: true`, não reprovação) | todos |
| G5 operação | ≥1 comando de teste `verified` (executado com exit 0) ou declaração explícita de ausência | — |
| G6 harness | validador do estado verde; guards respondem a sonda negativa (bloqueiam o que devem) | 100% |
| G7 plataformas | artefatos emitidos para cada plataforma escolhida passam no validador de formato | 100% |
