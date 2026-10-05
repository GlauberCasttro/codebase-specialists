# Sonda de maestria — tipos, gabarito, anti-cola e gates

Normativo para `scripts/probes/` (e para quem conduz a fase 6/7 e o aceite). Especialização é
**provada por sonda com gabarito mecânico**, nunca declarada (premissa 5). O banco nasce dos **fatos**
(`.swarm/facts/*.json5`), nunca de LLM; o modelo só responde e (no tipo POR-QUÊ) é julgado por painel.

## 1. Comandos

| Comando | Lê | Escreve | Gate |
|---|---|---|---|
| `cs.py probes generate [--seed S]` | facts, `team.json5` | `probes/bank.json5` | — |
| `cs.py probes generate --rotate --agent <agente>` | bank, facts | sondas NOVAS só de `<agente>` no bank (os outros intactos) | — |
| `cs.py probes exam-pack <agente>` | bank | `probes/exams/<agente>.questions.json5` (sem respostas) | — |
| `cs.py probes exam-pack <agente> --out <dir>` | bank, repo | `<dir>` (`<alvo>/.swarm/tmp/exam/<agente>`): perguntas + clone local do alvo com histórico, **sem** `.swarm/` (exame isolado) | — |
| `cs.py probes check <agente> [--answers F]` | bank, `exams/<agente>.answers.json5`, `panel/<agente>.json5` | `probes/reports/<agente>.json5`, `probes/report.json5` | G4 |
| `cs.py probes baseline-filter <agente> [--answers F]` | bank, `exams/<agente>.baseline.json5` | bank (`discriminative`, `baseline`) | G4 (delta) |
| `cs.py probes anticola [--cards DIR]` | bank, `team.json5`, cartões emitidos | `probes/anticola.json5` | regra 6 |
| `cs.py probes existence` | `team.json5`, facts, repo | `probes/existence.json5` | G2 |
| `cs.py probes antitemplate --control T [--threshold 0.35]` | `team.json5`, team de controle | `probes/antitemplate.json5` | G3 |
| `cs.py probes memory-recall [--mem mem.py]` | bank, busca de memória | `probes/memory-recall.json5` | G8 |

Tudo é determinístico (mesma entrada + semente → mesmos bytes), escrito atomicamente e só dentro de
`<alvo>/.swarm/`. Exit ≠ 0 quando o gate reprova. Leitura e escrita em JSON5 (§8-decies);
entradas `.json` são aceitas como fallback de leitura.

## 2. Banco (`bank.json5`)

Por agente: **20 sondas** — 12 do território (`scope: territory`) e 8 de outros territórios
(`scope: cross`), **≥2 negativas** no território (+1 no cross). Agente sem território de escrita (gates,
po) usa o produto inteiro como "território". Seleção round-robin por tipo com `random.Random("<seed>:<agente>")`.

```json5
{id: "P-dev-billing-03", agent: "dev-billing", type: "location", scope: "territory",
 question: "Onde está definido o símbolo (function) com assinatura `___(invoice, card)`, em `src/billing/**`?",
 answer: {exists: true, path: "src/billing/invoice.py", line: 10, symbol: "charge_customer"},
 atomic_facts: ["symbol charge_customer defined at src/billing/invoice.py:10"],
 negative: false, must_cite_evidence: true, discriminative: null}
```

| Tipo | Pergunta | Gabarito (fonte) | Pontuação |
|---|---|---|---|
| LOCALIZAÇÃO `location` | onde fica X — descrição **sem o nome-chave** (assinatura/doc com o nome mascarado `___`, ou "importado por …") | `path`+`line` (símbolos do L1; fallback: definições por regex) | path igual e linha ±3 |
| EXISTÊNCIA `existence` | existe X entre territórios / ocorrência de padrão proibido? | arestas do grafo; `rules.never.*` (re-verificado por grep: se aparece, a sonda não entra) | positiva: cita ≥1 arquivo do gabarito; negativa: NENHUM |
| COMANDO `command` | qual comando prova Y | `operations` com `status: verified` (exclui comando já presente em cartão) | string normalizada igual |
| PROIBIÇÃO `prohibition` | que regra mecânica vale em Z e onde é imposta | fatos de `rules` com evidência arquivo:linha | cita arquivo da imposição (linha ±3 se dada) |
| DEPENDÊNCIA `dependency` | quem fora do território importa X | arestas do grafo | conjunto igual (vazio = negativa) |
| HISTÓRIA `history` | qual commit corrigiu "assunto" | `history.fixes` | sha citado é prefixo (≥7) do gabarito |
| POR-QUÊ `why` | por que D? cite a fonte | `rationale` (ADR/decisão com arquivo:linha) | pré-check mecânico: cita arquivo:linha existente cuja janela ±3 contém o termo-chave (ou a fonte); **mérito vai ao painel** |
| TERMO `term` | onde é definido / termo canônico para Y / variante a nunca usar | `glossary` | local ±3; canônico como token; ≥1 variante proibida citada |
| REGRA-DE-NEGÓCIO `business_rule` | qual o limite/estado/validação de Z e onde é imposto | `business_rules` | arquivo:linha ±3 **e** valor citado |

**Negativas** (padrões que NÃO existem): par de territórios sem aresta; invariante `count = 0`
re-verificada; arquivo sem importador externo; símbolo/termo/regra **fabricados** a partir de tokens
reais do território e confirmados ausentes (palavra inteira, case-insensitive) em todos os arquivos.
Resposta correta: `NENHUM`/`none`/`não existe`. Afirmar existência = **alucinação = veto**.

## 3. Exame e pontuação (`check`)

- O examinado recebe **só** `exams/<agente>.questions.json5` (nunca o bank). Responde
  `exams/<agente>.answers.json5` = `[{id, answer, evidence: ["arquivo:linha" | "comando"]}]`.
- `must_cite_evidence`: sem evidência → sonda falha. Evidência tem de existir: arquivo do repo com
  linha dentro do arquivo, ou comando de `operations.json5`, ou comando de inspeção (`git`, `grep`, `rg`,
  `ls`, `find`, `cat`, `sed`, `head`, `tail`, `wc`, `awk`, `cs.py`, `cs-mem`). Evidência inexistente
  conta como **alucinação** (veto) — inventar fonte é o mesmo erro que inventar fato.
- Score território / cross = acertos ÷ sondas **discriminativas** (`discriminative != false`).
  Alucinações contam em todas as sondas (inclusive não-discriminativas).
- POR-QUÊ: o pré-check mecânico decide provisoriamente; `panel/<agente>.json5` = `{id: "PASS"|"FAIL"}`
  sobrepõe. Enquanto houver pendência, o relatório sai `provisional: true`.
- **G4** (ARCHITECTURE §9): território ≥ 0,85; cross ≥ 0,70; 0 alucinação; delta > 0 sobre o baseline
  (score bruto em todas as sondas − score bruto do baseline). Sem baseline → FAIL ("delta não medido").

## 4. Baseline sem cartão (`baseline-filter`)

Rode o mesmo pacote num agente **sem cartão e sem repo** e grave `exams/<agente>.baseline.json5`.
O checker pontua sem exigir evidência; toda sonda que o baseline acerta vira `discriminative: false` e
sai do score (ex.: negativas acertadas por chute "NENHUM"). Guarda `baseline[<agente>].score` para o delta.

## 5. Anti-cola (`anticola`, regra 6 do team-schema)

Reprova se uma resposta canônica aparece literal em texto de `team.json5` (todas as strings, exceto
chaves de referência `facts`, `facts_used`, `invariants`, `id`) ou em cartões emitidos (`--cards`):
`path:linha` (±3, também `path#Lnn`), comando exato normalizado, prefixo ≥7 de sha. Id de fato com
prefixo de sha (`hist.fix.<sha12>`) gera **aviso**: não renderize ids no cartão. Para não colidir com
`done_when`/`rules.check`, o gerador não cria sonda COMANDO para comando já presente em cartão.

## 6. Existence Ratio (`existence`, G2)

Extrai de `team.json5` (territory/reads, core.lines e cartões: anchors, playbooks, rules, knows,
refuses, footguns, mission, description, done_when) todo path/glob, símbolo (`Identificador` entre
crases) e comando (trecho entre crases iniciado por executável conhecido). Existe = arquivo/diretório
do repo (linha ≤ tamanho), glob que casa ≥1 arquivo, símbolo do grafo ou palavra presente no produto,
comando `verified` em operations (ou regra marcada `unverified: true`). G2 exige ratio = 1,0 e ≥1
citação (team vazio não passa).

## 7. Anti-template (`antitemplate`, G3)

Por agente, contra o cartão do mesmo papel (mesmo `name`; senão mesmo `kind`, pior caso) do repo de
controle: `line_jaccard` (linhas normalizadas) e `shingle_jaccard` (5-shingles de palavras);
`similarity = max`. Passa se ≤ 0,35 (calibrar com 2–3 repos de controle).

## 8. Memória (`memory-recall`, G8)

Para cada sonda TERMO/REGRA positiva, consulta `scripts/memory/cli.py` ou `mem.py`
(`--root <alvo> search "<pergunta>" -k 5 --json`) e verifica se `atomic_facts[0]` (id do fato do
glossário/regra) está no top-5. Gate: recall@5 ≥ 0,90 e p95 < 200 ms (latência = `ms` reportado pela
busca; a de parede, com partida do interpretador, também é registrada). Busca ausente = erro explícito.

## 9. Contrato de consumo dos fatos

Toda leitura passa por `scripts/team/_shared_tmp/factsio.py` (único ponto que conhece a forma interna
das camadas; o integrador troca por cslib). Campos usados além do §4:
`inventory.files[{path, category}]`, `inventory.manifests`; `graph.edges[[src, dst, w]]`,
`graph.nodes[{path, community, pagerank}]`, `graph.communities[{id, members}]`, `graph.symbols[]`
(opcional; senão regex); `rules.negative_checks[]` + fatos `rules.never.*`; `operations.commands[{cmd,
kind, status, source}]`; `history.fixes[{sha, subject, files}]`, `history.cochange[{a, b, support,
conf_a_b, conf_b_a}]`; `rationale` (ADR com evidência arquivo:linha; `data.key_terms` opcional);
`glossary` (`data.{canonical|term, category, synonyms, never_use, definition}`, evidência = definição);
`business_rules` (`data.{subject, kind, value, test}`, evidência = imposição).

## 10. Exame isolado, refino, modo fechado, juízes e lacunas

- **Exame isolado.** O exame guiado (e o painel de juízes) roda só na cópia de
  `cs.py probes exam-pack <agente> --out <alvo>/.swarm/tmp/exam/<agente>`: perguntas + clone local do alvo
  (`git clone --local --no-hardlinks`, com histórico: sondas de sha respondíveis e `git log` nunca sobe a um repo
  pai) **sem** `.swarm/`, então o gabarito (`probes/bank.json5`) fica inalcançável. O examinado grava as
  respostas SÓ em `.swarm/tmp/answers/<agente>.guided|closed.json5`. Na iteração 2 um `grep` do examinado
  no alvo imprimiu linhas do bank — por isso o examinado nunca abre o alvo. Prompt: `references/prompts.json5` → validate.3.
- **Refino só do reprovado.** `cs.py probes generate --rotate --agent <agente>` troca as sondas SÓ desse agente;
  `cs.py probes check --all` não repontua quem já passou num banco anterior. Ordem: revisa o cartão → rotaciona →
  novo exam-pack/baseline/exame → só então `probes check <agente>` (check antes do reexame registraria um ciclo
  com respostas velhas).
- **Modo fechado ≠ score certificado.** `probes/report.json5` traz `closed_mode: {score, hallucinations}` por
  agente. É **sinal**: o cartão é um mapa (onde procurar, o que nunca fazer), não memória do repositório — ficar
  perto ou abaixo do baseline sem ferramentas é esperado (iteração 2, py-billing: os 9 agentes abaixo do
  baseline, 7 com alucinação). Não entra no G4; o relatório mostra à parte e não o chama de placar. Alucinação
  no modo fechado é o dado útil: indica regra de "checar antes de afirmar" faltando no cartão.
- **Juízes (POR-QUÊ).** Cada sonda `why` traz `answer.source` — no item do juiz, `gabarito_fonte` (arquivo:linha
  do ADR/decisão/commit). O prompt manda abrir e citar o `gabarito_fonte`; veredito é por id único (sonda nova
  não herda veredito de sonda antiga com o mesmo id).
- **Lacuna citável (`gap.<slug>`).** `cs.py interview record --id <q> --answer-unknown` grava o fato
  `gap.<slug>` = `{question, answer: "unknown"}`. Cartão pode citá-lo em `lacunas` ou como motivo de cautela;
  **nunca** vira conhecimento (`knows`/`rules`) nem fonte de gabarito: o gerador não cria sonda a partir de gap.

## 11. Iteração 4 — exame com histórico, não medido, regra de GO

- **Histórico no exame:** `probes exam-pack <a> --out <alvo>/.swarm/tmp/exam/<a>` cria um clone local do alvo
  (sem `.swarm/`, sem remote); `git log/show` funcionam e nunca sobem para um repositório pai. Sem git no alvo
  (ou `.swarm/` versionado), a cópia ganha um `git init` vazio e `exam.json5` diz `history.mode: none`.
- **Limite conhecido:** com `--out` dentro de `.swarm/tmp/`, o banco de sondas fica alcançável por `../../..`;
  a instrução do exame proíbe sair da cópia, mas não há bloqueio mecânico. Para certificação estrita, use um `--out`
  fora do alvo.
- **Não medido ≠ reprovado:** o gerador garante ≥6 sondas positivas de território que o baseline sem cartão não
  acerta (completando com `reads` e depois com o produto, campo `source`); se o baseline ainda saturar, o score usa as
  sondas sem filtro e o relatório marca `baseline_saturated`.
- **Regra de GO:** qualquer agente diferente de `especialista` (aceito ou não) ⇒ G4 vermelho e NO-GO. Para registrar
  o não-especialista: `cs.py probes check <a> --allow-non-specialist --reason "..."` (vale após os ciclos de refino,
  com validate.4 pulado no `--fast`, ou com a rotação sem sondas novas).
