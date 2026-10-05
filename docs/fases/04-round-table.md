# Etapa 4 — round-table-deep-specialize (mesa redonda)

**Objetivo:** cartões criticados por pares e cético, só objeções confirmadas aplicadas.

**Só roda no `--full`.** No `--fast` (padrão), as quatro sub-etapas são puladas com `stage skip` e a etapa
fecha assim mesmo.

**Por que existe:** debate livre entre agentes converge para o erro por conformidade (premissa PR-06). A mesa
redonda é **crítica independente com checagem mecânica**: cada revisor trabalha isolado num pacote próprio, e
só entra no consolidado a objeção que a checagem confirma. O autor revisa **uma vez**, só com objeções
confirmadas.

```text
 rt.1 (sub)                                  rt.2 (main)               rt.3 (main)                  rt.4 (sub)
 ┌─────────────────────────────────────┐     ┌──────────────────┐      ┌──────────────────────┐     ┌──────────────────────┐
 │ cs.py panel plan → pares            │     │ cs.py probes     │      │ cs.py panel          │     │ autor revisa UMA vez │
 │ por cartão:                         │ ──▶ │ existence        │ ──▶  │ consolidate          │ ──▶ │ só objeções          │
 │  2 adjacentes (panel pack --role    │     │ (faltas viram    │      │ cs.py team core      │     │ confirmadas          │
 │    adjacente --reviewer R)          │     │  objeção do      │      │ from-panel           │     │ team card revise     │
 │  1 cético (panel pack --role cetico)│     │  consolidado)    │      └──────────────────────┘     └──────────┬───────────┘
 │ panel record <a> --reviewer R --file│     └──────────────────┘                                            │
 └─────────────────────────────────────┘                                          rt.2 de novo (existência só vale depois do rt.4)
  check: panel status --all-reviewed      check: probes existence --feed   check: panel consolidate --check --core   check: team card-status --all-revised
```

## Sub-etapas

### rt.1 — revisão por pares adjacentes e cético

| | |
|---|---|
| Quem | sub — por cartão: 2 revisores adjacentes no grafo + 1 cético (de preferência outro modelo; registre o modelo) |
| Antes (main) | `cs.py panel plan` (gera `knowledge/deps.json5` se faltar) e, por revisão, `cs.py panel pack <agente> --role adjacente --reviewer <revisor> --out <alvo>/.swarm/tmp/pack/<agente>.<revisor>` ou `cs.py panel pack <agente> --role cetico --out <alvo>/.swarm/tmp/pack/<agente>.cetico` |
| Pacote | `repo/` (cópia do alvo **sem** `.swarm/`), `card.json5` (cartão + fatos), `facts.json5`; o adjacente recebe também `reviewer.json5` (cartão do revisor, como dado). O cético não vê `lacunas` nem notas do autor e nunca abre o alvo |
| Saída do subagente | `{tmp}/panel/<agente>.<revisor>.json5` (ou `.cetico.json5`) com `revisao: {afirmacoes_sem_evidencia, conflitos_com_meu_territorio, regras_cross_cutting_faltando}` + `injection_attempts` |
| Registro (main) | `cs.py panel record <agente> --reviewer <revisor> --file <abs>` (o cético: `--reviewer cetico`); `--role cetico\|adjacente` é conferido contra o plano |
| Check | `cs.py panel status --all-reviewed` |
| Grava | `.swarm/panel/` (plano, objeções por revisor) |

`panel record` recusa arquivo de outro par (agente, revisor). Objeção sem evidência não entra; listas vazias
são resposta válida. Prompts completos: `references/prompts.json5 → "rt.1-adjacente"` e `"rt.1-cetico"`.

### rt.2 — checagem de existência

| | |
|---|---|
| Quem | main |
| Comando | `cs.py probes existence` |
| Check | `cs.py probes existence --feed` — antes do rt.4, basta a falta estar medida e entregue ao autor no consolidado; depois do rt.4 vale o G2 (ratio 1,0) |
| Grava | `.swarm/probes/existence.json5` |

Extrai de `team.json5` todo path/glob, símbolo (entre crases) e comando citado e confere: arquivo existe (linha
≤ tamanho), glob casa ≥1 arquivo, símbolo existe no grafo ou no produto, comando é `verified` em
`operations.json5` (ou a regra está marcada `unverified: true`). Cada falta vai ao autor como objeção confirmada.

### rt.3 — consolidar e subir regras ao core

| | |
|---|---|
| Quem | main |
| Comandos | `cs.py panel consolidate` e `cs.py team core from-panel` |
| Check | `cs.py panel consolidate --check --core` (consolidado presente e fresco **e** promoção ao core registrada) |
| Grava | `.swarm/panel/<agente>.json5` (objeções confirmadas), `panel/core-candidates.json5`, `panel/core-promotion.json5`, `core.lines` |

### rt.4 — revisão única do autor

| | |
|---|---|
| Quem | sub — só agentes com objeção confirmada; lotes ≤3 |
| Entrada | `{tmp}/in/<agente>.rt4.json5` = `{cartao, objecoes_confirmadas, regras_promovidas, fatos}` |
| Saída | `{tmp}/cards/<agente>.revised.json5` com o cartão **completo** e `respostas[{objecao, acao: corrigida\|removida\|incluida\|contestada, evidencia}]` |
| Registro | `cs.py team card revise <agente> --file <abs> --note "rt.4: objeções confirmadas tratadas"` |
| Check | `cs.py team card-status --all-revised` |

A revisão é **única por consolidação** ("já revisou uma vez para este painel"). Toda revisão roda o
`probes existence` no cartão novo e **recusa** referência inexistente ou comando fora de `verified` sem
`[unverified]` — nada é gravado. Depois do rt.4, rode `cs.py probes existence` de novo: as revisões podem ter
trocado caminhos citados.

## Exemplo real

As rodadas `--full` da iteração 3 rodaram a mesa redonda (py-billing completa: 10/10 agentes provados, NO-GO
por "1 ref inválida em 504" — `iteration-3/RESULTADOS.json5`). Nas notas do go-polyglot (iteração 3) há o caso
que motivou a regra de escrita: "Mesa redonda: um revisor adjacente rodou um script de validação sobre
`panel/raw/*.json` inteiro e regravou 5 saídas".

## Erros comuns e como resolver

| Sintoma | Origem | Resolução |
|---|---|---|
| `panel plan` sem grafo de dependências | defeito da iteração 2 ("`panel plan` exige `team maps` antes") | hoje o `panel plan` gera `knowledge/deps.json5` se faltar; se não houver grafo L1, rode `cs.py team maps` |
| revisor regravou saídas de outros | violação da regra de escrita | cada revisor grava só `{tmp}/panel/<agente>.<revisor>.json5`; `panel record` recusa arquivo de outro par |
| laço `for p in $pairs` em zsh gerou pacote com nome lixo | zsh não divide string | itere sobre o plano em JSON ou escreva um comando por par |
| 429 / limite de subagentes | concorrência | reduza o lote (3→2→1), registre em `.swarm/tmp/dispatch.jsonl`, reenvie só o que falhou |
| `team card revise` recusa segunda revisão | revisão única por painel | trate todas as objeções numa revisão; a do refino (validate.4) é outra |
| rt.2 só passa depois das revisões | ordem | rode `probes existence` de novo depois do rt.4 |

## O que muda no `--fast`

A etapa inteira é pulada:

```text
cs.py stage skip rt.1 --reason "--fast (padrão)"
cs.py stage skip rt.2 --reason "--fast (padrão)"
cs.py stage skip rt.3 --reason "--fast (padrão)"
cs.py stage skip rt.4 --reason "--fast (padrão)"
cs.py stage done round-table-deep-specialize
```

Saída real (py-billing, iteração 4): `pulada rt.1: … — motivo registrado (aparece em `stage status` e no
relatório)` e `etapa round-table-deep-specialize fechada → …; próxima: validate`.

**Consequência conhecida:** o rt.2 era a única checagem de existência antes do `verify`. No `--fast`, cartão
com comando fora de `verified` ou caminho inexistente só é pego no `verify` (G2 vermelho), e a via documentada de
conserto (`team card revise --file`) **recusa** sem painel consolidado ("painel de <a> não consolidado") — defeito
aberto P0 da iteração 4. Ver [05-validate.md](05-validate.md).
