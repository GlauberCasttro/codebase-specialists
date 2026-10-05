# team.json5 — schema (contrato entre derivação, redação, sonda, emissão e harness)

Arquivo: `<alvo>/.swarm/team.json5` (JSON5; exemplo abaixo em JSON, que é JSON5 válido). Fonte única da verdade dos agentes. Emissores e harness
**leem** este arquivo; ninguém edita os artefatos emitidos à mão.

```json
{
  "schema_version": 1,
  "repo": {"name": "...", "commit": "sha", "root": "abs path no momento do scan"},
  "platforms": ["claude-code", "cursor", "copilot", "codex"],
  "veredito_enum": ["PASS", "FAIL", "NEEDS_SPECIALIST"],
  "test_ownership": {"top_level": "qa", "colocated": "owner"},
  "core": {
    "lines": [
      {"text": "Testes: `python3 -m unittest discover -s tests` (exit 0 em 4,2 s)", "facts": ["ops.test.unittest"]}
    ]
  },
  "agents": [
    {
      "name": "dev-billing",
      "kind": "dev",
      "territory": ["src/billing/**"],
      "reads": ["src/shared/**"],
      "tools": ["Read", "Grep", "Glob", "Bash", "Edit", "Write"],
      "model": "inherit",
      "card": {
        "description": "Quando delegar (gatilho orientado a ação, ≤300 caracteres).",
        "mission": "1–2 frases: o ofício neste repo.",
        "knows": [{"text": "fato não derivável que ele precisa", "facts": ["id"]}],
        "refuses": [{"text": "nunca faz X", "why": "porque Y", "facts": ["id"]}],
        "done_when": "critério de feito verificável (comando + condição)",
        "playbooks": [{"title": "...", "steps": ["passo com arquivo/comando real"]}],
        "rules": [{"text": "regra", "check": "comando que prova (opcional)", "facts": ["id"]}],
        "footguns": [{"text": "armadilha real", "facts": ["hist.fix.abc123"]}],
        "anchors": ["caminho real de alto sinal"]
      },
      "camadas": {
        "s0_core": [{"text": "candidato ao core", "facts": ["id"]}],
        "s2_por_caminho": [{"paths": ["glob"], "text": "vale para quem toca o caminho", "facts": ["id"]}],
        "s5_memoria": [{"kind": "term|rule|fact", "text": "chega por cs-mem search", "facts": ["id"]}]
      },
      "facts_used": ["id", "..."],
      "invariants": ["id de fato da camada rules com scope que toca o território"]
    },
    {"name": "security", "kind": "gate", "gate_scope": "security", "territory": [], "...": "..."}
  ]
}
```

## Regras de validação (`cs.py team validate`, `cs.py probes ...` e `cs.py emit validate` conferem)

1. `name`: `^[a-z][a-z0-9-]{1,40}$`, único.
2. `kind ∈ {dev, gate, design, product, ops}`. Agentes `gate` têm `tools` sem `Edit`/`Write` e todo
   veredito citado no cartão ∈ `veredito_enum`.
3. Territórios de escrita **disjuntos** entre agentes (checados por expansão real de arquivos do repo,
   não por comparação de strings); todo arquivo de produto (L0 sem `fixture/vendor/generated`) tem
   exatamente 1 dono.
4. Todo `facts[]` referencia um fato existente em `.swarm/facts/index.json5`.
5. Todo caminho em `anchors`, `playbooks.steps`, `rules`, `knows` existe no repo (Existence Ratio = 1,0);
   todo comando em `check`/`done_when` está em `operations.json5` como `verified` ou é marcado `unverified`.
6. Nenhum texto do cartão contém resposta canônica do banco de sondas (anti-cola).
7. `core.lines` ≤ 40; cartão renderizado ≤ 150 linhas.
8. Invariante (fato de `rules.json5` ou da entrevista) cujo `scope` toca N territórios aparece em N agentes
   (`reads` entra em `facts_used` como contexto, não como invariante);
   agentes `gate` recebem todos os invariantes + decisões de ADR (`rationale`) e o histórico de correções em
   `facts_used`; gate com `gate_scope: "security"` recebe só os de segurança **mais todos os invariantes negativos
   medidos (`rules.never.*`: eval/exec/shell=True/pickle/unsafe/curl|sh…, cujo texto não tem palavra de segurança)**. Precedência entre gates sobre os
   mesmos caminhos: qualquer `FAIL` vence; `NEEDS_SPECIALIST` roteia para outro gate e trava o aceite até ele.

## Territórios e dono de teste
Territórios são globs de diretório (arquivo novo já nasce com dono). Teste co-localizado (`x_test.go`,
`a.test.ts`, `pkg/tests/`) é do dono do diretório (`test_ownership.colocated = "owner"`); `qa` é dono só dos
diretórios de teste de topo (`tests/**`, `e2e/**`…). Utilitário compartilhado por nome (`shared/`, `utils/`…)
vira um dev próprio (`dev-shared`); núcleo de domínio por fan-in continua bounded context de um dev; o
`architect` só tem docs/ADRs.

## Comandos que escrevem team.json5 (nunca edite à mão)
- `cs.py team derive [--force]` — roster inicial.
- `cs.py team roster move <glob> --to <agente>` · `roster rename <de> <para>` ·
  `roster add <nome> --kind K --territory G… [--reads G…]` · `roster remove <nome> [--to <herdeiro>]` ·
  `roster set --file f.json5` ({agents:[{name, kind, territory, reads, tools?, model?}]}). Todos recalculam
  `invariants`/`facts_used`, revalidam (regras 1–4 e 8; inválido = nada gravado) e invalidam a aprovação.
- `cs.py team card set <agente> --file f.json5 [--force]` (alias `--from`; caminho relativo ao alvo): aceita a saída
  do subagente `{agent, draft: {id, at}, card, camadas, ...}` ou só o `card`; persiste `card` e `camadas`. Registra a
  identidade do rascunho (sha256 do arquivo, `draft.id` = id da delegação, `draft.at`) em `cards/status.json5` e
  **recusa rascunho mais velho que o registrado** (redator atrasado/duplicado), salvo `--force`. Cartão que não cita
  nenhum fato não conta como redigido; `knows` que cita só `gap.*` é recusado (lacuna não é conhecimento).
- `cs.py team card revise <agente> [--file f] --note "..."` — uma revisão por consolidação do painel (rt.4); no
  refino (validate.4) cada exame reprovado em `probes/cycles.json5` libera mais uma (`refines[]`). Toda revisão roda
  o `probes existence` no cartão (o novo, com `--file`; o atual, sem) e **recusa** caminho/símbolo/glob inexistente
  ou comando fora de `operations.json5` `verified` sem `[unverified]` — nada é gravado e a revisão continua livre.
  **Conserto de existência**: com a revisão travada (ex.: reexame aprovado), `revise --file` ainda é aceito quando o
  cartão atual tem falta de existência e o novo a zera (`existence_fixes[]`; não consome ciclo).
- `cs.py team card-status [--all-drafted|--all-revised]` — compara o cartão com a revisão **mais recente** entre
  `revised`, `refines[]` e `existence_fixes[]` (campo `seq`), não com o último refino.
- `cs.py team facts <agente> [--out f.json5]` — fatos do agente calculados NA LEITURA (território + `reads` +
  citados no cartão + lacunas `gap.*` do escopo) **mais**: para todo agente, a instrução do time (`docs.instr.*`,
  L10) que toca o escopo, as decisões de ADR (`rat.adr.*`) e os fatos de escopo `**`/sem escopo das camadas
  rules/rationale/operations/project_docs; para gate/design/product/ops e `qa`, todos os comandos (`ops.*`, com o
  status `verified|declared|unavailable` do scan) e todo o rationale; para gate, todos os `rules.never.*`.
  Entrada do redator (o prompt recebe o caminho). Reviewer/security nunca recebem só `gap.*`.
- `cs.py team approve --by <nome> [--note ...] [--simulated]` — `--simulated` (eval/CI, sem humano) grava
  `approval: simulated` e o `team approved` mostra `[simulado]`.
- `cs.py team core set --file f.json5` ({lines:[{text, facts}]}, ≤40, cada linha com fato e existência) ·
  `cs.py team core from-panel` (linhas atuais + `panel/core-candidates.json5` + `camadas.s0_core`; sem painel
  consolidado = caminho rápido só com s0_core). Cada candidata perde `arquivo:linha`, é deduplicada (texto igual,
  mesmos fatos ou Jaccard ≥0,6) e conferida pelo classificador único `scripts/cslib/refs.py`
  (path|symbol|command|glob|package|prose): referência inexistente RECUSA só aquela linha, com motivo. Duplicata =
  texto normalizado igual (sem acento/pontuação), Jaccard ≥0,6, fatos contidos (qualquer direção com a linha já
  aceita) ou fato em comum com ≥30% das palavras — a mesma regra em outra redação soma os fatos, não a linha. O total
  respeita o espaço do S0 (≤40 menos mapa de agentes e linhas operacionais). Ambos gravam
  `panel/core-promotion.json5` {promoted[], refused[{text, why}]} — o check de rt.3/specialize.4 exige esse registro.

## Exemplos (`examples/**`, `samples/**` fora de teste)
Categoria `example`: fora da análise e da cobertura obrigatória (regra 3 vale só para produto), mas **pode ter dono**:
`cs.py team roster add dev-exemplos --kind dev --territory "examples/**"` (glob sempre entre aspas).

## Entrevista: escopo
`cs.py interview ask|record --scope <glob>` recebe **um glob por flag** (repita a flag: `--scope a/** --scope b/**`);
vírgula é recusada (o log é append-only e um glob "a/**,b/**" não casa nada — a lacuna não chegaria ao dono).

## Lacunas (`gap.<id>`)
`cs.py interview record --id Q --answer-unknown` grava o fato `gap.<id>` {question, answer: "unknown"} em
`facts/gaps.json5`: citável em `refuses`/`footguns`, nunca conhecimento (cs-mem não indexa) nem sonda.
