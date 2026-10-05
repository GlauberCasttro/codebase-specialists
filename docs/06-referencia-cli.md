# 06 — Referência da CLI

Esta referência foi **gerada a partir do `--help` real** (argparse) de cada comando, percorrendo a árvore de
subcomandos de `scripts/cs.py` e os parsers de `cs-state` (`scripts/harness/engine/state.py`), `cs-mem`
(`scripts/memory/mem.py`), `cs-session` (`scripts/harness/engine/session.py`) e `cs-route`
(`scripts/harness/engine/router.py`). As linhas `-h, --help` foram omitidas. Para conferir uma flag, o próprio
`--help` é a fonte: `python3 ~/.claude/skills/codebase-specialists/scripts/cs.py <subcomando> --help`.

Para o **porquê** de cada comando, veja as fases ([fases/00-visao-geral.md](fases/00-visao-geral.md)) e os
documentos de harness, memória, roteador e sessão.

## Convenções e comportamento comum

- `cs.py` = `python3 ~/.claude/skills/codebase-specialists/scripts/cs.py`. Raiz do alvo: `--target` (aceito antes
  **ou** depois do subcomando; em vários subcomandos também como `--root`) > `$CLAUDE_PROJECT_DIR` > diretório
  atual. Nunca o diretório da skill.
- Erros da CLI saem como `erro: <mensagem>` + `como resolver: <dica>` e exit ≠ 0 (default 2). Erro de uso do
  argparse também sai com exit 2.
- `emit`: exit 0 ok · 1 validação falhou · 2 entrada inválida/orçamento estourado · 3 conflito com conteúdo humano
  ou escrita fora de `.swarm/` sem `--allow-outside`.
- `probes …`: exit ≠ 0 quando o gate reprova.
- Os bins do harness no alvo (`.swarm/bin/cs-state|cs-mem|cs-session|cs-route`) são wrappers `sh` que
  chamam `python3 .swarm/harness/<motor>.py --root <raiz>`; a raiz é `$CLAUDE_PROJECT_DIR`, senão o projeto
  onde o bin está instalado. `--root` e `cs-state --actor <agente>` (simula o ator do payload em testes) são
  opções globais desses bins.
- Valores com espaço vão entre aspas; **globs sempre entre aspas**.

## Índice por tarefa

| Quero… | Comando |
|---|---|
| saber onde a execução está | `cs.py stage status` |
| retomar uma etapa | `cs.py stage load <etapa>` |
| marcar uma sub-etapa | `cs.py stage check <sub> [--answer "…" \| --note "…"]` |
| pular (só `--fast`) | `cs.py stage skip <sub> --reason "--fast (padrão)"` |
| fechar a etapa | `cs.py stage done <etapa>` |
| escanear | `cs.py scan` |
| corrigir um fato | `cs.py facts interpret … --corrects <id>` + `cs.py facts spotcheck record --verdict wrong …` |
| registrar lacuna | `cs.py interview record --id <q> --answer-unknown` |
| ajustar roster | `cs.py team roster move\|rename\|add\|remove\|set …` |
| aprovar roster | `cs.py team approve --by <quem>` |
| registrar cartão | `cs.py team card set <agente> --file <abs>` |
| medir orçamento | `cs.py emit budget` |
| emitir | `cs.py emit --dry-run` → `cs.py emit --allow-outside` |
| montar exame | `cs.py probes exam-pack <agente> --out <dir>` |
| pontuar exame | `cs.py probes check <agente> --answers <arq>` |
| instalar harness | `cs.py harness install --platforms … --git-hook --dry-run` → `… --allow-outside` |
| rodar gates | `cs.py verify` |
| decidir | `cs.py approve --by <quem> --decision GO\|NO-GO` |
| próximo passo no dia a dia | `.swarm/bin/cs-state next` |
| buscar conhecimento | `.swarm/bin/cs-mem search "<consulta>"` |
| corrigir um agente | `.swarm/bin/cs-mem correct --agent <a> --wrong "…" --right "…" --why "…"` |
| salvar/retomar sessão | `.swarm/bin/cs-session save --did "…" --next "…"` · `.swarm/bin/cs-session load` |
| modelo para o despacho | `.swarm/bin/cs-route recommend <task>` |
| destravar delegação ESCALATED/ABSTAINED | retomar `cs-state retry --task <t> --decision "<decisão>"` · trocar de agente `cs-state reroute --task <t> --agent <a> --decision "…"` · descartar `cs-state drop --task <t> --reason "…"` |
| verify falhou por ambiente | `cs-state reverify --task <t>` · exceção (humano) `cs-state waive-verify --task <t> --by <humano> --reason "…" --evidence "…"` |
| harness hotfixado à mão → motor canônico | `cs-state legacy-ack --reason "…"` |
| destravar mandato autônomo ESCALATED | `cs-state autonomy resume --decision "<decisão>"` · encerrar `cs-state autonomy stop --reason "…"` |

## `cs.py` — CLI da skill

### Raiz

#### `cs.py`

```text
usage: cs.py [-h] [--target TARGET] <subcomando> ...

codebase-specialists CLI

positional arguments:
  <subcomando>
    init           cria .swarm/run.json5 (estado da execução)
    stage          etapas: status | load <etapa> | check <sub> | skip <sub> |
                   done <etapa>
    scan           escaneia o alvo (L0–L10) → .swarm/facts/*.json5
    team           deriva e valida o roster (.swarm/team.json5)
    probes         sonda de maestria e gates G2/G3/G4/G8
    emit           emite agentes/regras/núcleo por plataforma; `emit validate`
                   = G7
    harness        instala/verifica o harness (estado, guards, hooks, memória)
    memory         cs-mem: add|correct|check|inject|archive|search|revalidate|
                   consolidate|stats
    facts          conferência de fatos contra o código e correções
                   llm_interpretation
    interview      entrevista de lacunas: ask | record | status
    panel          mesa redonda: plan | record | status | consolidate | why
    verify         roda G1–G16 e grava .swarm/acceptance.json5
    report         relatório final (decisão, time, garantias por plataforma,
                   lacunas, pulos)
    approve        decisão do founder sobre acceptance.json5 (ou --check)

options:
  --target TARGET  raiz do repositório-alvo (default: $CLAUDE_PROJECT_DIR ou
                   cwd)
```

### Execução: `init` e `stage`

#### `cs.py init`

```text
usage: cs.py init [-h] [--platforms PLATFORMS] [--force] [--check]
                  [--check-repo] [--replace-harness] [--allow-outside]

options:
  --platforms PLATFORMS
                        ex.: claude-code,cursor,copilot,codex
  --force               recria run.json5 (perde o progresso)
  --check               check de init.3: run.json5 válido, criado/mesclado por
                        `cs.py init` explícito
  --check-repo          check de init.1: o alvo é a RAIZ de um repo git
  --replace-harness     substitui OUTRO harness detectado no alvo (backup fiel
                        em .swarm/backups/harness-anterior/; exige --allow-
                        outside)
  --allow-outside       autoriza escrita fora de .swarm/ (exigido por
                        --replace-harness)
```

#### `cs.py stage`

```text
usage: cs.py stage [-h] <ação> ...

positional arguments:
  <ação>
    status    etapa/sub-etapa atual e pendências
    load      pacote de entrada ≤2k tokens; retoma na sub-etapa pendente
    check     roda o check de uma sub-etapa e marca feito/falhou
    skip      pulo explícito de sub-etapa (caminho --fast), com motivo
              registrado
    done      roda todos os checks; sucesso grava handoff e avança
```

#### `cs.py stage status`

```text
usage: cs.py stage status [-h]
```

#### `cs.py stage load`

```text
usage: cs.py stage load [-h] stage

positional arguments:
  stage
```

#### `cs.py stage check`

```text
usage: cs.py stage check [-h] [--answer ANSWER] [--note NOTE] substage

positional arguments:
  substage

options:
  --answer ANSWER  resposta literal do usuário (ctx: user)
  --note NOTE      registro manual para item sem check
```

#### `cs.py stage skip`

```text
usage: cs.py stage skip [-h] --reason REASON substage

positional arguments:
  substage

options:
  --reason REASON
```

#### `cs.py stage done`

```text
usage: cs.py stage done [-h] stage

positional arguments:
  stage
```

### Scan

#### `cs.py scan`

```text
usage: cs.py scan [-h] [--layers LAYERS] [--no-exec] [--no-introspect]
                  [--timeout TIMEOUT] [--max-commits MAX_COMMITS]
                  [--max-deps MAX_DEPS] [--max-exec MAX_EXEC] [--check]

`cs.py scan` — roda camadas L0–L10 e grava
<alvo>/.swarm/facts/<camada>.json5 + index.json5. Tudo é computado ANTES
de qualquer escrita: se uma camada falha, nada é gravado (exceto blobs de
evidência de comandos executados, que são endereçados por conteúdo e
idempotentes).

options:
  --layers LAYERS       camadas separadas por vírgula (default: todas). Ex.:
                        L0,L1,L5
  --no-exec             não executa comandos do alvo (L7 fica declared; L8 sem
                        introspecção)
  --no-introspect       L8 sem introspecção de API
  --timeout TIMEOUT     timeout por comando executado (s)
  --max-commits MAX_COMMITS
                        commits lidos em L5/L6
  --max-deps MAX_DEPS   dependências críticas introspectadas (L8)
  --max-exec MAX_EXEC   máximo de comandos executados (L7)
  --check               não escaneia: confere que as camadas pedidas já
                        existem, válidas e indexadas
```

### Time: `team`

#### `cs.py team`

```text
usage: cs.py team [-h]
                  {derive,validate,maps,approve,approved,card,facts,card-status,roster,core} ...

positional arguments:
  {derive,validate,maps,approve,approved,card,facts,card-status,roster,core}
    derive              propõe o roster a partir dos fatos
    validate            aplica as 8 regras do team-schema.md
    maps                deps.json5 (matriz/ciclos) e collision.json5 (não
                        paralelizar)
    approve             grava a aprovação do roster atual (sha256)
    approved            check: aprovação gravada e roster inalterado desde
                        então
    card                grava/revisa cartão devolvido por subagente
    facts               fatos de um agente calculados NA LEITURA (território +
                        reads + citados)
    card-status         estado dos cartões; check com --all-drafted|--all-
                        revised
    roster              ajusta o roster (revalida e invalida a aprovação)
    core                grava core.lines (S0): set --file | from-panel
```

#### `cs.py team derive`

```text
usage: cs.py team derive [-h] [--target TARGET] [--force]

options:
  --target, --root TARGET
  --force               sobrescreve team.json5 com cartões
```

#### `cs.py team validate`

```text
usage: cs.py team validate [-h] [--target TARGET]
                           [--stage {auto,derive,final}]

options:
  --target, --root TARGET
  --stage {auto,derive,final}
```

#### `cs.py team maps`

```text
usage: cs.py team maps [-h] [--target TARGET] [--threshold THRESHOLD]

options:
  --target, --root TARGET
  --threshold THRESHOLD
```

#### `cs.py team approve`

```text
usage: cs.py team approve [-h] --by BY [--note NOTE] [--simulated]
                          [--target TARGET]

options:
  --by BY
  --note NOTE
  --simulated           sem humano (eval/CI): registra approval=simulated
                        (como `cs.py approve --simulated`)
  --target, --root TARGET
```

#### `cs.py team approved`

```text
usage: cs.py team approved [-h] [--target TARGET]

options:
  --target, --root TARGET
```

#### `cs.py team card`

```text
usage: cs.py team card [-h] <set|revise> ...

positional arguments:
  <set|revise>
    set         valida o cartão contra o schema e grava em team.json5
    revise      marca a revisão única do autor após o painel
```

#### `cs.py team card set`

```text
usage: cs.py team card set [-h] --file FILE [--by BY] [--force]
                           [--target TARGET]
                           agent

positional arguments:
  agent

options:
  --file, --from FILE   saída do subagente ({card, camadas, ...}) ou só o
                        card; relativo ao alvo
  --by BY
  --force               grava mesmo rascunho mais velho que o registrado
  --target, --root TARGET
```

#### `cs.py team card revise`

```text
usage: cs.py team card revise [-h] [--file FILE] [--note NOTE]
                              [--target TARGET]
                              agent

positional arguments:
  agent

options:
  --file, --from FILE
  --note NOTE
  --target, --root TARGET
```

#### `cs.py team facts`

```text
usage: cs.py team facts [-h] [--out OUT] [--target TARGET] agent

positional arguments:
  agent

options:
  --out OUT             grava o pacote (JSON5) neste caminho (em
                        .swarm/tmp/)
  --target, --root TARGET
```

#### `cs.py team card-status`

```text
usage: cs.py team card-status [-h] [--all-drafted | --all-revised]
                              [--target TARGET]

options:
  --all-drafted
  --all-revised
  --target, --root TARGET
```

#### `cs.py team roster`

```text
usage: cs.py team roster [-h] <move|rename|add|remove|set> ...

positional arguments:
  <move|rename|add|remove|set>
    move                move os arquivos de um glob para o território de um
                        agente
    rename              renomeia um agente
    add                 cria agente (território tirado de quem tinha os
                        arquivos)
    remove              remove agente (--to herda o território)
    set                 substitui o roster inteiro por um JSON5
                        {agents:[{name,kind,territory,reads}]}
```

#### `cs.py team roster move`

```text
usage: cs.py team roster move [-h] --to TO [--target TARGET] glob

positional arguments:
  glob

options:
  --to TO
  --target, --root TARGET
```

#### `cs.py team roster rename`

```text
usage: cs.py team roster rename [-h] [--target TARGET] old new

positional arguments:
  old
  new

options:
  --target, --root TARGET
```

#### `cs.py team roster add`

```text
usage: cs.py team roster add [-h] --kind {dev,gate,design,product,ops}
                             [--territory [TERRITORY ...]]
                             [--reads [READS ...]] [--target TARGET]
                             name

positional arguments:
  name

options:
  --kind {dev,gate,design,product,ops}
  --territory [TERRITORY ...]
  --reads [READS ...]
  --target, --root TARGET
```

#### `cs.py team roster remove`

```text
usage: cs.py team roster remove [-h] [--to TO] [--target TARGET] name

positional arguments:
  name

options:
  --to TO
  --target, --root TARGET
```

#### `cs.py team roster set`

```text
usage: cs.py team roster set [-h] --file FILE [--target TARGET]

options:
  --file, --from FILE
  --target, --root TARGET
```

#### `cs.py team core`

```text
usage: cs.py team core [-h] <set|from-panel> ...

positional arguments:
  <set|from-panel>
    set             grava core.lines de um JSON5 {lines:[{text, facts}]} (≤40)
    from-panel      core = atual + candidatas do painel + camadas.s0_core dos
                    cartões
```

#### `cs.py team core set`

```text
usage: cs.py team core set [-h] --file FILE [--target TARGET]

options:
  --file, --from FILE
  --target, --root TARGET
```

#### `cs.py team core from-panel`

```text
usage: cs.py team core from-panel [-h] [--target TARGET]

options:
  --target, --root TARGET
```

### Sondas e gates de conhecimento: `probes`

#### `cs.py probes`

```text
usage: cs.py probes [-h]
                    {generate,exam-pack,check,anticola,baseline-filter,existence,antitemplate,memory-recall} ...

positional arguments:
  {generate,exam-pack,check,anticola,baseline-filter,existence,antitemplate,memory-recall}
    generate            gera probes/bank.json5 a partir dos fatos
    exam-pack           pacote do exame SEM respostas (--out: cópia isolada do
                        alvo sem .swarm/)
    check               pontua respostas e decide G4 (<agente> ou --all
                        [--final])
    anticola            resposta canônica literal em team.json5/cartões
                        reprova
    baseline-filter     marca sondas acertadas pelo baseline sem cartão
                        (<agente> | --check)
    existence           Existence Ratio (G2)
    antitemplate        similaridade com cartões do repo de controle (G3)
    memory-recall       recall@5 e p95 da busca de memória (G8)
```

#### `cs.py probes generate`

```text
usage: cs.py probes generate [-h] [--target TARGET] [--seed SEED_EXPLICIT]
                             [--rotate] [--agent AGENT]

options:
  --target, --root TARGET
  --seed SEED_EXPLICIT  semente (default cs-probes-v1; rotação: <semente>-rN)
  --rotate              refino: troca só as sondas de --agent por sondas novas
  --agent AGENT
```

#### `cs.py probes exam-pack`

```text
usage: cs.py probes exam-pack [-h] [--target TARGET] [--out OUT] agent

positional arguments:
  agent

options:
  --target, --root TARGET
  --out OUT             <alvo>/.swarm/tmp/exam/<agente> ou diretório
                        fora do alvo: <out>/repo/ (clone local com histórico,
                        sem .swarm/) + <out>/questions.json5
```

#### `cs.py probes check`

```text
usage: cs.py probes check [-h] [--target TARGET] [--answers ANSWERS] [--all]
                          [--final] [--allow-non-specialist] [--reason REASON]
                          [--closed] [--examined]
                          [agent]

positional arguments:
  agent

options:
  --target, --root TARGET
  --answers ANSWERS
  --all                 todos os agentes do banco
  --final               aplica a regra de 2 refinos (nao-especialista)
  --allow-non-specialist
                        aceita o(s) nao-especialista(s) sem refino possível —
                        ciclos esgotados, validate.4 pulado (--fast) ou
                        rotação esgotada; por agente ou com --all --final
                        (exige --reason; registrado)
  --reason REASON
  --closed              pontua o exame em MODO FECHADO (só cartão, sem repo):
                        sinal em report.json5 closed_mode, fora do G4
  --examined            com --all: check de validate.3 — todo agente examinado
                        nas sondas atuais (reprovado vai ao refino)
```

#### `cs.py probes anticola`

```text
usage: cs.py probes anticola [-h] [--target TARGET] [--cards CARDS]

options:
  --target, --root TARGET
  --cards CARDS         arquivo/diretório de cartões emitidos
```

#### `cs.py probes baseline-filter`

```text
usage: cs.py probes baseline-filter [-h] [--target TARGET] [--answers ANSWERS]
                                    [--check]
                                    [agent]

positional arguments:
  agent

options:
  --target, --root TARGET
  --answers ANSWERS
  --check               check: todo agente com baseline e sondas classificadas
```

#### `cs.py probes existence`

```text
usage: cs.py probes existence [-h] [--target TARGET] [--feed]

options:
  --target, --root TARGET
  --feed                check de rt.2: antes da revisão do autor, falta medida
                        e entregue ao autor (consolidado) basta; depois de
                        rt.4 vale o G2 (ratio 1,0)
```

#### `cs.py probes antitemplate`

```text
usage: cs.py probes antitemplate [-h] [--target TARGET] [--control CONTROL]
                                 [--threshold THRESHOLD]

options:
  --target, --root TARGET
  --control CONTROL     team.json5, repo ou dir de cartões .md (default:
                        evals/reference/generic-cards da skill)
  --threshold THRESHOLD
```

#### `cs.py probes memory-recall`

```text
usage: cs.py probes memory-recall [-h] [--target TARGET] [--mem MEM]

options:
  --target, --root TARGET
  --mem MEM
```

### Emissão: `emit`

#### `cs.py emit`

```text
usage: cs.py emit [-h] [--platforms PLATFORMS] [--dry-run] [--diff] [--force]
                  [--json] [--allow-outside] [--require-core]
                  [{run,validate,budget}]

cs.py emit — gera os artefatos nativos por plataforma a partir de .swarm/team.json5.

    cs.py emit [--platforms claude-code,cursor,copilot,codex] [--dry-run] [--diff] [--force] [--allow-outside]
    cs.py emit validate [--platforms ...] [--json]        # gate G7
    cs.py emit budget [--platforms ...] [--json]          # orçamento por camada (specialize.4); não escreve

Executável direto: python3 scripts/emit/cli.py [validate] --target <repo> ...
Exit: 0 ok · 1 validação falhou · 2 entrada inválida/orçamento estourado · 3 conflito com conteúdo humano
      ou escrita fora de .swarm/ sem --allow-outside (o plano lista o bloco `outside`).

positional arguments:
  {run,validate,budget}
                        run (padrão) emite; validate confere os artefatos
                        (gate G7); budget mede as camadas

options:
  --platforms PLATFORMS
                        lista separada por vírgula (padrão:
                        team.json.platforms ou todas)
  --dry-run             mostra o plano sem escrever
  --diff                inclui diff unificado no plano
  --force               sobrescreve arquivo humano no caminho de um artefato
                        (com backup + diff)
  --json                saída JSON (validate)
  --allow-outside       autoriza escrever FORA de .swarm/ (.claude/,
                        .cursor/, .github/, AGENTS.md, CLAUDE.md…)
  --require-core        budget: falha se core.lines está vazio (specialize.4)
```

### Harness: `harness` e `memory`

#### `cs.py harness`

```text
usage: cs.py harness [-h] <install|selftest|validate|status> ...

positional arguments:
  <install|selftest|validate|status>
    install             instala motor, hooks, wrappers, Makefile e estado no
                        alvo
    selftest            gate G6: sondas negativas contra os guards instalados
```

#### `cs.py harness install`

```text
usage: cs.py harness install [-h] [--platforms PLATFORMS] [--no-settings]
                             [--no-makefile] [--path-env] [--git-hook]
                             [--dry-run] [--allow-outside] [--target TARGET]
                             [--replace-harness]

options:
  --platforms PLATFORMS
                        adapters advisory: cursor,copilot,codex
  --no-settings
  --no-makefile
  --path-env            grava env.PATH com .swarm/bin no settings.json
                        (desligado por padrão)
  --git-hook            liga .git/hooks/pre-commit → cs-precommit
  --dry-run             só lista o que seria escrito, com o bloco `outside`
                        (escritas fora de .swarm/)
  --allow-outside       permite escrever fora de .swarm/ (.claude/, Makefile,
                        specialists.mk, .git/hooks); mostre a lista do --dry-
                        run ao usuário antes
  --target TARGET
  --replace-harness     substitui OUTRO harness detectado no alvo (backup fiel
                        em .swarm/backups/harness-anterior/; exige --allow-
                        outside)
```

#### `cs.py harness selftest`

```text
usage: cs.py harness selftest [-h] [--drift] [--target TARGET]

options:
  -h, --help       show this help message and exit
  --drift
  --target TARGET
```

#### `cs.py harness validate`

```text
usage: cs.py harness validate [-h] [--strict] [--allow-empty]
                              [--target TARGET]

options:
  --strict
  --allow-empty
  --target TARGET
```

#### `cs.py harness status`

```text
usage: cs.py harness status [-h] [--target TARGET]

options:
  --target TARGET
```

#### `cs.py memory`

```text
usage: cs.py memory [-h] ...

positional arguments:
  mem_args
```

### Fatos e entrevista: `facts` e `interview`

#### `cs.py facts`

```text
usage: cs.py facts [-h] <spotcheck|interpret|check> ...

positional arguments:
  <spotcheck|interpret|check>
    spotcheck           check: --min N; registro: spotcheck record ...
    interpret           grava fato llm_interpretation (ex.: correção de fato
                        errado)
    check               check de scan.1–4: camadas presentes, válidas e
                        FRESCAS (código não mudou)
```

#### `cs.py facts spotcheck`

```text
usage: cs.py facts spotcheck [-h] [--min MIN] [record] ...

positional arguments:
  [record]
    record    registra a conferência de um fato

options:
  --min MIN   mínimo de fatos conferidos (check)
```

#### `cs.py facts spotcheck record`

```text
usage: cs.py facts spotcheck record [-h] --fact FACT --verdict {ok,wrong}
                                    --note NOTE [--by BY]

options:
  --fact FACT
  --verdict {ok,wrong}
  --note NOTE
  --by BY
```

#### `cs.py facts interpret`

```text
usage: cs.py facts interpret [-h] --id ID --claim CLAIM --supports SUPPORTS
                             --evidence EVIDENCE [--corrects CORRECTS]
                             [--scope SCOPE] [--confidence {high,medium,low}]

options:
  --id ID
  --claim CLAIM
  --supports SUPPORTS   ids mecânicos (vírgula ou repetido)
  --evidence EVIDENCE   arquivo[:linha] conferido no código
  --corrects CORRECTS
  --scope SCOPE
  --confidence {high,medium,low}
```

#### `cs.py facts check`

```text
usage: cs.py facts check [-h] --layers LAYERS

options:
  --layers LAYERS  ex.: L0,L1,L2,L3
```

#### `cs.py interview`

```text
usage: cs.py interview [-h] <ask|record|status> ...

positional arguments:
  <ask|record|status>
    ask                registra pergunta de lacuna (lote ≤8 pendentes)
    record             registra a resposta literal (ou --answer-unknown)
    status             perguntas, respostas e pendências
    sync               regrava facts/interview.json5 e facts/gaps.json5 a
                       partir do log
```

#### `cs.py interview ask`

```text
usage: cs.py interview ask [-h] --id ID --question QUESTION
                           [--context CONTEXT] [--scope SCOPE]

options:
  --id ID
  --question QUESTION
  --context CONTEXT
  --scope SCOPE
```

#### `cs.py interview record`

```text
usage: cs.py interview record [-h] --id ID (--answer ANSWER |
                              --answer-unknown) [--by BY]
                              [--question QUESTION] [--context CONTEXT]
                              [--scope SCOPE]

options:
  --id ID
  --answer ANSWER
  --answer-unknown
  --by BY
  --question QUESTION  cria a pergunta se ainda não existe
  --context CONTEXT
  --scope SCOPE
```

#### `cs.py interview status`

```text
usage: cs.py interview status [-h] [--no-pending] [--json]

options:
  --no-pending  check: falha se há pergunta sem resposta
  --json
```

#### `cs.py interview sync`

```text
usage: cs.py interview sync [-h]
```

### Mesa redonda: `panel`

#### `cs.py panel`

```text
usage: cs.py panel [-h] <plan|record|status|consolidate|why|pack> ...

positional arguments:
  <plan|record|status|consolidate|why|pack>
    plan                2 revisores adjacentes (deps.json5) + 1 cético por
                        agente
    record              grava objeções JSON5 de um revisor
    status              revisões gravadas × plano
    consolidate         confirma objeções mecanicamente; grava
                        panel/<agente>.json5
    why                 mérito de sonda POR-QUÊ (formato lido por probes
                        check)
    pack                cópia isolada do alvo sem .swarm/ + cartão como
                        dado (cético)
```

#### `cs.py panel plan`

```text
usage: cs.py panel plan [-h]
```

#### `cs.py panel record`

```text
usage: cs.py panel record [-h] [--card CARD] --reviewer REVIEWER [--role ROLE]
                          --file FILE
                          [agent]

positional arguments:
  agent

options:
  --card CARD          agente revisado (alternativa ao posicional)
  --reviewer REVIEWER
  --role ROLE          cetico|adjacente (conferido contra o plano)
  --file, --from FILE  JSON5 do revisor (schema do prompt rt.1 ou o interno);
                       relativo ao alvo
```

#### `cs.py panel status`

```text
usage: cs.py panel status [-h] [--all-reviewed]

options:
  --all-reviewed  check: falha se falta alguma revisão
```

#### `cs.py panel consolidate`

```text
usage: cs.py panel consolidate [-h] [--check] [--core]

options:
  --check     check: consolidado presente e fresco
  --core      com --check: exige também a promoção ao core registrada (`team
              core from-panel`)
```

#### `cs.py panel why`

```text
usage: cs.py panel why [-h] --probe PROBE --verdict {PASS,FAIL} agent

positional arguments:
  agent

options:
  --probe PROBE
  --verdict {PASS,FAIL}
```

#### `cs.py panel pack`

```text
usage: cs.py panel pack [-h] --role {cetico,adjacente} --out OUT
                        [--reviewer REVIEWER]
                        agent

positional arguments:
  agent

options:
  --role {cetico,adjacente}
  --out OUT             fora do alvo ou em <alvo>/.swarm/tmp/
  --reviewer REVIEWER   adjacente: inclui o cartão do revisor
```

### Gates, relatório e decisão: `verify`, `report`, `approve`

#### `cs.py verify`

```text
usage: cs.py verify [-h] [--control CONTROL] [--json] [--recorded]

options:
  --control CONTROL  team.json5 (ou repo) de controle para G3
  --json
  --recorded         check de validate.6: verify já rodou sobre o estado atual
                     (GO ou NO-GO); não roda os gates
```

#### `cs.py report`

```text
usage: cs.py report [-h] [--check]

options:
  --check     check de approve.1: report.md gerado sobre o acceptance atual
```

#### `cs.py approve`

```text
usage: cs.py approve [-h] [--by BY] [--decision {GO,NO-GO}] [--note NOTE]
                     [--check] [--simulated] [--recorded]

options:
  --by BY
  --decision {GO,NO-GO}
  --note NOTE
  --check
  --simulated           sem humano (eval/CI): registra approval=simulated; o
                        relatório mostra `GO (simulado)`
  --recorded            com --check (approve.2): decisão GO|NO-GO registrada
                        sobre o acceptance atual
```

## `.swarm/bin/cs-state` — estado, máquinas e processo

#### `cs-state`

```text
usage: cs-state [-h] [--root ROOT] [--actor ACTOR]
                {init,add,epic,feature,story,sprint,session,ready,dispatch,submit,return,verify,review,accept,reject,retry,escalate,block,reroute,abstain,delegate,amend,brief,drop,reverify,waive-verify,legacy-ack,ask,consult,status,board,next,why,autonomy} ...

cs-state — único dono das transições (épico, feature, sprint, story, sessão
M1, delegação M2, task M3, consulta M4).

positional arguments:
  {init,add,epic,feature,story,sprint,session,ready,dispatch,submit,return,verify,review,accept,reject,retry,escalate,block,reroute,abstain,delegate,amend,brief,drop,reverify,waive-verify,legacy-ack,ask,consult,status,board,next,why,autonomy}
    legacy-ack          HUMANO: reconhece na cadeia o histórico de motor
                        antigo/hotfix (validate --strict)
    ask                 faixa consulta: delegação SÓ LEITURA a um
                        especialista, sem task/story

options:
  --root ROOT
  --actor ACTOR
```

#### `cs-state init`

```text
usage: cs-state init [-h]
```

#### `cs-state add`

```text
usage: cs-state add [-h] {epic,feature,sprint,story,task} ...

positional arguments:
  {epic,feature,sprint,story,task}
```

#### `cs-state add epic`

```text
usage: cs-state add epic [-h] --title TITLE --objective OBJECTIVE
                         [--metric METRIC]

options:
  --title TITLE
  --objective OBJECTIVE
  --metric METRIC
```

#### `cs-state add feature`

```text
usage: cs-state add feature [-h] --epic EPIC --title TITLE [--spec SPEC]
                            [--accept-cmd ACCEPT_CMD]
                            [--accept-file ACCEPT_FILE]

options:
  --epic EPIC
  --title TITLE
  --spec SPEC
  --accept-cmd ACCEPT_CMD
  --accept-file ACCEPT_FILE
```

#### `cs-state add sprint`

```text
usage: cs-state add sprint [-h] --goal GOAL [--budget BUDGET]

options:
  --goal GOAL
  --budget BUDGET
```

#### `cs-state add story`

```text
usage: cs-state add story [-h] --type {us,bug,fix} [--feature FEATURE]
                          --title TITLE [--as-a AS_A] [--i-want I_WANT]
                          [--so-that SO_THAT] [--failing-test FAILING_TEST]
                          [--severity SEVERITY] [--environment ENVIRONMENT]
                          [--fixes FIXES] [--proving-test PROVING_TEST]
                          [--regression REGRESSION] [--reopens REOPENS]
                          [--criterion CRITERION] [--repro REPRO]

options:
  --type {us,bug,fix}
  --feature FEATURE
  --title TITLE
  --as-a AS_A
  --i-want I_WANT
  --so-that SO_THAT
  --failing-test FAILING_TEST
  --severity SEVERITY
  --environment ENVIRONMENT
  --fixes FIXES
  --proving-test PROVING_TEST
  --regression REGRESSION
  --reopens REOPENS
  --criterion CRITERION
  --repro REPRO
```

#### `cs-state add task`

```text
usage: cs-state add task [-h] [--quick] [--work-type {us,bug,fix}]
                         [--from FROM_FILE] [--id ID] [--story STORY]
                         [--agent AGENT] [--title TITLE] [--goal GOAL]
                         [--type TYPE] [--sprint SPRINT] [--session SESSION]
                         [--class KLASS] [--wave WAVE]
                         [--depends-on DEPENDS_ON]
                         [--allowed-path ALLOWED_PATH]
                         [--protected-path PROTECTED_PATH]
                         [--verify-cmd VERIFY_CMD] [--ac AC] [--ref REF]
                         [--in SCOPE_IN] [--out SCOPE_OUT] [--subtask SUBTASK]
                         [--assume ASSUME] [--context CONTEXT] [--dod DOD]
                         [--hot-path] [--security-gate] [--readonly]
                         [--handoff-to HANDOFF_TO] [--scenario SCENARIO]
                         [--ready]

options:
  --quick               faixa avulsa: sessão trivial|pequena, story implícita
                        STORY-AVULSA-<sessão>, já BRIEFED
  --work-type {us,bug,fix}
                        tipo da task avulsa (padrão us)
  --from FROM_FILE      brief em JSON5 (brief-schema.json5)
  --id ID
  --story STORY
  --agent AGENT
  --title TITLE
  --goal GOAL
  --type TYPE
  --sprint SPRINT
  --session SESSION
  --class KLASS
  --wave WAVE
  --depends-on DEPENDS_ON
  --allowed-path ALLOWED_PATH
  --protected-path PROTECTED_PATH
  --verify-cmd VERIFY_CMD
  --ac AC               'AC-
                        n|critério|verification_command|test:<id>|reviewer'
  --ref REF
  --in SCOPE_IN
  --out SCOPE_OUT
  --subtask SUBTASK
  --assume ASSUME
  --context CONTEXT
  --dod DOD
  --hot-path
  --security-gate
  --readonly
  --handoff-to HANDOFF_TO
  --scenario SCENARIO
  --ready
```

Com `--quick` (faixa **avulsa**, só em sessão `trivial|pequena`): sem `--story/--sprint`; a task vai para a story
implícita `STORY-AVULSA-<sessão>` e nasce BRIEFED (a sessão em TRIAGE passa a PLANNING). `--allowed-path` e
`--verify-cmd` são obrigatórios; `--goal` (padrão = título), `--ref`, `--out` e `--ac` (padrão: AC-1 pelo
`verification_command`) são opcionais. >1 território/agente, invariante escopado ou `frozen_paths` → exit 1 com
"suba a classe: `cs-state session triage --class feature|risco`".

`--protected-path` não acrescenta nada ao `--verify-cmd`: o motor prova no `verify` que ESTA delegação não alterou
os protected (reprova com `protected_path alterado por esta delegação: <arquivo>`); trabalho de task-irmã em voo
não conta. `--verify-cmd` com checagem crua da árvore sobre protected (`git status --porcelain`, `git diff
--quiet`) é recusado pelo `brief_valid` (D-1-03).

#### `cs-state epic`

```text
usage: cs-state epic [-h] --id ID [--reason REASON] {activate,done,drop}

positional arguments:
  {activate,done,drop}

options:
  --id ID
  --reason REASON
```

#### `cs-state feature`

```text
usage: cs-state feature [-h] --id ID [--reason REASON] {ready,start,done,drop}

positional arguments:
  {ready,start,done,drop}

options:
  --id ID
  --reason REASON
```

#### `cs-state story`

```text
usage: cs-state story [-h] --id ID [--reason REASON]
                      {ready,start,review,done,reject,requeue}

positional arguments:
  {ready,start,review,done,reject,requeue}

options:
  --id ID
  --reason REASON
```

#### `cs-state sprint`

```text
usage: cs-state sprint [-h] [--id ID] [--goal GOAL] [--budget BUDGET]
                       [--stories STORIES] [--add ADD] [--reason REASON]
                       {plan,start,review,close}

positional arguments:
  {plan,start,review,close}

options:
  --id ID
  --goal GOAL
  --budget BUDGET
  --stories STORIES
  --add ADD
  --reason REASON
```

#### `cs-state session`

```text
usage: cs-state session [-h] [--request REQUEST] [--mode {assistido,autonomo}]
                        [--class KLASS] [--why WHY] [--assume ASSUME]
                        [--note NOTE] [--by BY] [--verdict VERDICT]
                        [--findings FINDINGS]
                        {start,triage,confirm,answer,plan,execute,replan,verify,review,report,close,status}

positional arguments:
  {start,triage,confirm,answer,plan,execute,replan,verify,review,report,close,status}

options:
  --request REQUEST
  --mode {assistido,autonomo}
  --class KLASS
  --why WHY
  --assume ASSUME
  --note NOTE
  --by BY
  --verdict VERDICT
  --findings FINDINGS
```

#### `cs-state ready`

```text
usage: cs-state ready [-h] [--task TASK] [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
```

#### `cs-state dispatch`

No **Claude Code** não é comando do agente principal: o despacho legítimo é a ferramenta **Agent** com o id da
delegação BRIEFED na `description` — o hook `pre-agent` faz a transição e grava o `tool_use_id`; o guard bloqueia
`cs-state dispatch` no Bash do principal (exit 2) em qualquer forma, inclusive com `--manual`, porque o despacho só
de estado não lança subagente e gastaria a tentativa (despacho fantasma, D-1-02). **Fora do Claude Code** (Cursor,
Copilot, Codex — sem hook `pre-agent`) o caminho é `cs-state dispatch --task T --manual [--model M]`: declara a
execução, grava `tool_use_id: "manual:<timestamp>"` e `dispatch_origin: "manual"` e consome a tentativa
normalmente. Sem `--tool-use-id` e sem `--manual` o CLI recusa (exit 1, depois das guardas). Delegação legada
DISPATCHED sem `tool_use_id`: `cs-state return --task T --reason "despacho fantasma"` + `cs-state retry --task T
--findings "..."` devolvem a tentativa.

```text
usage: cs-state dispatch [-h] [--task TASK] [--model MODEL]
                         [--tool-use-id TOOL_USE_ID] [--manual]
                         [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
  --model MODEL
  --tool-use-id TOOL_USE_ID
                        id do tool_use do Agent que lançou o subagente (o hook
                        pre-agent passa); sem ele (e sem --manual) o CLI
                        recusa: despache pela ferramenta Agent com o id da
                        delegação na description
  --manual              plataforma SEM hook pre-agent (Cursor, Copilot,
                        Codex): declara a execução do subagente; grava
                        tool_use_id manual:<timestamp> e dispatch_origin
                        manual (no Claude Code o guard bloqueia: use a
                        ferramenta Agent)
```

#### `cs-state submit`

```text
usage: cs-state submit [-h] [--task TASK] [--files-changed FILES_CHANGED]
                       [--check CHECK] [--risk RISK]
                       [--handoff-notes HANDOFF_NOTES] [--from FROM_FILE]
                       [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
  --files-changed FILES_CHANGED
  --check CHECK
  --risk RISK
  --handoff-notes HANDOFF_NOTES
  --from FROM_FILE
```

#### `cs-state return`

```text
usage: cs-state return [-h] [--task TASK] [--reason REASON] [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
  --reason REASON
```

#### `cs-state verify`

```text
usage: cs-state verify [-h] [--task TASK] [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
```

#### `cs-state review`

```text
usage: cs-state review [-h] [--task TASK] --by BY --verdict VERDICT
                       [--findings FINDINGS]
                       [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
  --by BY
  --verdict VERDICT
  --findings FINDINGS
```

#### `cs-state accept`

```text
usage: cs-state accept [-h] [--task TASK] [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
```

#### `cs-state reject`

```text
usage: cs-state reject [-h] [--task TASK] [--reason REASON] [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
  --reason REASON
```

#### `cs-state retry`

De `REJECTED` consome tentativa (`--findings` ou o `reject_reason`). De `ESCALATED`/`ABSTAINED` é a **retomada por
decisão humana**: exige `--decision` (ou `--findings`), não consome tentativa e tira a task do bloqueio (→ READY).

```text

```

#### `cs-state escalate`

```text
usage: cs-state escalate [-h] [--task TASK] [--reason REASON] [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
  --reason REASON
```

#### `cs-state block`

```text
usage: cs-state block [-h] [--task TASK] [--reason REASON] [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
  --reason REASON
```

#### `cs-state reroute`

Também sai de `ESCALATED`/`ABSTAINED` (saída "trocar de agente"); `--decision` vale como motivo.

```text

```

#### `cs-state abstain`

```text
usage: cs-state abstain [-h] [--task TASK] [--reason REASON] [--kind KIND]
                        [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
  --reason REASON
  --kind KIND
```

#### `cs-state delegate`

```text
usage: cs-state delegate [-h] [--task TASK] [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
```

#### `cs-state drop`

Descarta a task por decisão humana: delegação `ESCALATED`/`ABSTAINED`/`REJECTED` → `DROPPED` e task → `DROPPED`
(fechada; não segura `session verify`/`report`). `--reason` obrigatório; `DROPPED` é terminal.

```text

```

#### `cs-state reverify`

REJECTED (falha de AMBIENTE) ou ESCALATED → RETURNED e roda o verify de novo, sem novo despacho (não consome
tentativa). Falha de código de REJECTED é recusada (use `retry`).

```text
usage: cs-state reverify [-h] [--task TASK] [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
```

#### `cs-state waive-verify`

Exceção de AMBIENTE com portão humano: REJECTED/ESCALATED → VERIFIED com `verify_waiver`. Só quando o último verify
da tentativa foi classificado `environment` (nunca teste/asserção); `--by` tem de ser o humano (≠ ator, ≠ agente do
time, ≠ lead); `--evidence` cita a ferramenta ausente. O guard bloqueia o comando para agentes: o usuário roda no
terminal dele. Review de gate continua obrigatória.

```text
usage: cs-state waive-verify [-h] [--task TASK] [--by BY]
                             [--evidence EVIDENCE] [--reason REASON]
                             [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
  --by BY              o HUMANO que assume a exceção (nunca o orquestrador nem
                       um agente do time)
  --evidence EVIDENCE  saída do verify mostrando a falha de AMBIENTE
                       (ferramenta/módulo ausente)
  --reason REASON
```

#### `cs-state legacy-ack`

Reconhece na cadeia de eventos o histórico de um harness hotfixado à mão (transições hoje ilegais, ACCEPTED sem
gate), para `validate --strict` voltar a passar sem legalizar o atalho para eventos novos. Ato do humano.

```text
usage: cs-state legacy-ack [-h] --reason REASON

options:
  --reason REASON
```

#### `cs-state amend`

```text
usage: cs-state amend [-h] [--task TASK] --field FIELD --after AFTER
                      --reason REASON [--found-by FOUND_BY]
                      [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
  --field FIELD
  --after AFTER        valor em JSON5 (ou texto simples)
  --reason REASON
  --found-by FOUND_BY
```

#### `cs-state brief`

```text
usage: cs-state brief [-h] [--task TASK] [--phase {implement,verify,review}]
                      [--agent AGENT]
                      [task_pos]

positional arguments:
  task_pos

options:
  --task TASK
  --phase {implement,verify,review}
  --agent AGENT
```

#### `cs-state ask`

Faixa **consulta** (classe `pergunta`): cria a consulta `ASK-n` já BRIEFED (sem task, sem story) e imprime a
linha `Agent(...)` com o id para a `description`. O guard despacha, bloqueia toda escrita do subagente e fecha a
consulta (ANSWERED) no SubagentStop. Consulta é descartável: o mesmo id não serve para outro despacho.

```text
usage: cs-state ask [-h] [--paths PATHS [PATHS ...]] agent question

positional arguments:
  agent
  question

options:
  --paths PATHS [PATHS ...]
                        globs onde o especialista deve olhar
```

#### `cs-state consult`

Cancela uma consulta que não vai voltar (BRIEFED/DISPATCHED → CANCELLED, `--reason` obrigatório).

```text
usage: cs-state consult [-h] --id ID [--reason REASON] {cancel}

positional arguments:
  {cancel}

options:
  --id ID
  --reason REASON
```

#### `cs-state status`

```text
usage: cs-state status [-h] [--task TASK]

options:
  --task TASK
```

#### `cs-state board`

```text
usage: cs-state board [-h]
```

#### `cs-state next`

```text
usage: cs-state next [-h]
```

#### `cs-state why`

```text
usage: cs-state why [-h] id

positional arguments:
  id
```

#### `cs-state autonomy`

`resume --decision "…"`: mandato `ESCALATED` → `ACTIVE` (a decisão vai para a cadeia de eventos; a mesma evidência não
reescala). `stop`: `ACTIVE`/`ESCALATED` → `STOPPED`.

```text

```

## `.swarm/bin/cs-mem` — memória e lições

#### `cs-mem`

```text
usage: cs-mem [-h] [--root ROOT]
              {add,correct,inject,archive,check,search,revalidate,consolidate,stats} ...

memória do harness (BM25, stdlib)

positional arguments:
  {add,correct,inject,archive,check,search,revalidate,consolidate,stats}
    add                 entrada semântica (--text) ou lição de agente (--agent
                        --rule)
    correct             correção humana → lição do agente que errou
    inject              lições do agente para o escopo (≤5, ≤1.500 chars; sem
                        archived/stale)
    archive             aplica decaimento e teto (idempotente)
    check               lições × arquivos alterados → checklist ≤5; executa
                        checks

options:
  --root ROOT
```

#### `cs-mem add`

```text
usage: cs-mem add [-h] [--kind {fact,lesson,decision,term,rule}] [--text TEXT]
                  [--rule RULE] [--why WHY] [--check CHECK] [--scope SCOPE]
                  [--paths PATHS] [--tag TAG] [--evidence-file EVIDENCE_FILE]
                  [--task TASK] [--fact FACT] [--commit COMMIT]
                  [--founder FOUNDER] [--agent AGENT]
                  [--source {human,review,reject,brief}] [--promote]

options:
  --kind {fact,lesson,decision,term,rule}
  --text TEXT
  --rule RULE
  --why WHY
  --check CHECK         comando que prova a lição (executado no verify)
  --scope SCOPE
  --paths PATHS
  --tag TAG
  --evidence-file EVIDENCE_FILE
  --task TASK
  --fact FACT
  --commit COMMIT
  --founder FOUNDER
  --agent AGENT
  --source {human,review,reject,brief}
  --promote
```

#### `cs-mem correct`

```text
usage: cs-mem correct [-h] --agent AGENT --wrong WRONG --right RIGHT --why WHY
                      [--paths PATHS] [--check CHECK] [--evidence EVIDENCE]

options:
  --agent AGENT
  --wrong WRONG
  --right RIGHT
  --why WHY
  --paths PATHS
  --check CHECK
  --evidence EVIDENCE  arquivo:linha (fingerprint p/ obsolescência)
```

#### `cs-mem inject`

```text
usage: cs-mem inject [-h] --agent AGENT [--paths PATHS] [--title TITLE]
                     [--json]

options:
  --agent AGENT
  --paths PATHS
  --title TITLE
  --json
```

#### `cs-mem archive`

```text
usage: cs-mem archive [-h]
```

#### `cs-mem check`

```text
usage: cs-mem check [-h] --agent AGENT [--files FILES] [--no-run]

options:
  --agent AGENT
  --files FILES
  --no-run
```

#### `cs-mem search`

```text
usage: cs-mem search [-h] [-k K] [--paths PATHS] [--kind KIND] [--agent AGENT]
                     [--include-stale] [--json]
                     query

positional arguments:
  query

options:
  -k K
  --paths PATHS
  --kind KIND
  --agent AGENT
  --include-stale
  --json
```

#### `cs-mem revalidate`

```text
usage: cs-mem revalidate [-h]
```

#### `cs-mem consolidate`

```text
usage: cs-mem consolidate [-h] [--task TASK] [--agent AGENT]

options:
  --task TASK
  --agent AGENT
```

#### `cs-mem stats`

```text
usage: cs-mem stats [-h]
```

## `.swarm/bin/cs-session` — sessão

#### `cs-session`

```text
usage: cs-session [-h] [--root ROOT] {save,load} ...

positional arguments:
  {save,load}

options:
  --root ROOT
```

#### `cs-session save`

```text
usage: cs-session save [-h] [--did DID] [--next NEXT_] [--blocked BLOCKED]
                       [--decision DECISION] [--commit] [--check]

options:
  --did DID
  --next NEXT_
  --blocked BLOCKED
  --decision DECISION
  --commit
  --check              só confere se o save existe e o carimbo bate (exit 0/1)
```

#### `cs-session load`

```text
usage: cs-session load [-h] [--brief]

options:
  --brief     saída JSON para o hook SessionStart
```

## `.swarm/bin/cs-route` — roteador de modelos

#### `cs-route`

```text
usage: cs-route [-h] [--root ROOT]
                {recommend,override,outcome,anular,stats} ...

positional arguments:
  {recommend,override,outcome,anular,stats}
    outcome             registra outcome manual (sem procedência não treina)

options:
  --root ROOT
```

#### `cs-route recommend`

```text
usage: cs-route recommend [-h] [--act ACT] id

positional arguments:
  id

options:
  --act ACT
```

#### `cs-route override`

```text
usage: cs-route override [-h] --model MODEL --reason REASON id

positional arguments:
  id

options:
  --model MODEL
  --reason REASON
```

#### `cs-route outcome`

```text
usage: cs-route outcome [-h] [--success] [--procedencia PROCEDENCIA] id

positional arguments:
  id

options:
  --success
  --procedencia PROCEDENCIA
```

#### `cs-route anular`

```text
usage: cs-route anular [-h] --at AT --motivo MOTIVO

options:
  --at AT
  --motivo MOTIVO
```

#### `cs-route stats`

```text
usage: cs-route stats [-h]
```

## `.swarm/bin/cs-precommit`

Script `sh` sem argumentos (template `scripts/harness/templates/bin/cs-precommit`), instalado como hook
`pre-commit` do git com `cs.py harness install --git-hook`. Roda o validador do estado
(`.swarm/harness/validate.py --root <raiz>`) e depois `guard.py check-diff --staged` (arquivos staged ×
território). É o enforcement **E2** (depois do fato) para plataformas sem hook.

## Alvos `make` (`specialists.mk`)

Camada fina: cada alvo chama o script e nada mais. Variáveis: `ID=<task>`, `FEAT=<feature>`, `Q=<consulta>`,
`ARGS='<flags>'`. Alvo cujo nome já existe no Makefile do alvo ganha prefixo `cs-`.

| Alvo | Executa |
|---|---|
| `next` | `cs-state next` |
| `board` | `cs-state board` |
| `add-epic` / `add-feature` / `add-story` | `cs-state add epic $(ARGS)` / `cs-state add feature $(ARGS)` / `cs-state add story $(ARGS)` |
| `sprint-plan` / `sprint-start` / `sprint-review` / `sprint-close` | `cs-state sprint plan $(ARGS)` / `cs-state sprint start $(ARGS)` / `cs-state sprint review $(ARGS)` / `cs-state sprint close $(ARGS)` |
| `brief ID=` | `cs-state brief --task $(ID) $(ARGS)` |
| `dispatch ID=` | `cs-state dispatch --task $(ID) --manual $(ARGS)` (plataforma sem hook `pre-agent`; no Claude Code despache pela ferramenta Agent) |
| `verify ID=` | `cs-state verify --task $(ID)` |
| `review ID=` | `cs-state review --task $(ID) $(ARGS)` |
| `accept ID=` | `cs-state accept --task $(ID)` |
| `reject ID=` | `cs-state reject --task $(ID) $(ARGS)` |
| `abstain ID=` | `cs-state abstain --task $(ID) $(ARGS)` |
| `session-save` / `session-load` | `cs-session save $(ARGS)` / `cs-session load` |
| `mem Q=` | `cs-mem search "$(Q)"` |
| `autonomy-start FEAT=` | `cs-state autonomy start --feature $(FEAT) $(ARGS)` |
| `autonomy-status` | `cs-state autonomy status` |
| `selftest` | `python3 .swarm/harness/selftest.py --root .` |
| `validate` | `python3 .swarm/harness/validate.py --strict --allow-empty --root .` |
| `drift` | `python3 .swarm/harness/selftest.py --drift --root .` |
| `help` | lista os alvos |

## Scripts de avaliação (só na skill)

Detalhe em [07-evals-e-qualidade.md](07-evals-e-qualidade.md).

```text
usage: check_run.py [-h] [--mode {setup,autonomous,escalation,bugfix}]
                    [--feature FEATURE] [--platforms PLATFORMS]
                    [--skill SKILL] [--only ONLY] [--no-scenarios] [--out OUT]
                    [--verify-ground-truth VERIFY_GROUND_TRUTH]
                    [target] [ground_truth]
```

```text
usage: summarize.py [-h] [--out-dir OUT_DIR] runs_dir
```

```text
usage: build.sh <nome> <destino>          (evals/fixtures/build.sh — repo git com histórico realista)
usage: install_feature.sh refund-percent|accept-float-amounts|bug-late-fee <alvo>   (evals/fixtures/install_feature.sh)
```

## Observações sobre o próprio `--help`

Divergências encontradas ao gerar esta referência (o código é a fonte; a lista é para quem mantém a skill):

- O resumo de `cs.py --help` diz `interview … ask | record | status`, mas existe também `interview sync`; e
  `panel … plan | record | status | consolidate | why`, mas existe também `panel pack`.
- `cs.py harness --help` só descreve `install` e `selftest`; `validate` e `status` existem, sem texto de ajuda.
- `cs.py harness install --platforms` diz "adapters advisory: cursor,copilot,codex", enquanto o SKILL.md e o
  `references/harness.md` passam `claude-code,cursor,copilot,codex`. O valor `claude-code` é aceito e
  ignorado na geração de adapters (os hooks do Claude Code são instalados de qualquer forma, salvo
  `--no-settings`).
- `cs-route --help` só descreve `outcome`; `recommend`, `override`, `anular` e `stats` não têm texto de ajuda.
- Vários parâmetros de `cs-state` não têm texto de ajuda; o significado está em `references/harness.md` §3 e em
  [02-harness.md](02-harness.md).
