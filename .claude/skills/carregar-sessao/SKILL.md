---
name: carregar-sessao
description: >
  Retoma o desenvolvimento da skill codebase-specialists pela âncora em .claude/state/, sem reler o projeto:
  carimbo comparável (FRENTES/BRANCH/HEAD/PRODUTO/ESTADO/GATE) calculado por um script dono da fórmula, frescor por
  regra (bate | cache-miss | produto-mudou), briefing em duas sequências (frentes e tasks, com ← PRÓXIMA e o porquê
  de cada elo) e gate de retomada "Retomo daqui?". Só desce ao log em cache-miss. Frases que disparam: "carregar
  sessão", "/carregar-sessao", "onde paramos", "retoma o contexto", "continua de onde paramos", "o que fizemos na
  última sessão". Só leitura (a única escrita permitida é o self-heal do RESUME em cache-miss).
---

# /carregar-sessao — retomar o trabalho neste projeto

Contraparte do `/salvar-sessao`. O script decide (`.claude/tools/sessao.py`); você enuncia e **para**.

**Meta de custo:** caminho feliz = **1 comando** (`python3 .claude/tools/sessao.py briefing`) — ele lê o RESUME, o
`frentes.json` e, só com frente ativa, as tasks da frente, e calcula o carimbo. **Nunca** leia logs, `SKILL.md` da
raiz, `scripts/`, `docs/` ou as campanhas no caminho feliz: write-once-read-many — o custo foi pago no save.

## Contrato

| Pode | Não pode |
|---|---|
| rodar `sessao.py briefing/frescor/carimbo` e `git` só leitura (`status`, `log`, `rev-parse`) | `git add`, `commit`, `push`, `checkout`, `stash`, `reset` |
| reescrever `.claude/state/RESUME.md` em cache-miss (self-heal: narrativa + `sessao.py carimbo --write`) | escrever qualquer outro arquivo |
| ler o log da frente **só em cache-miss** (as últimas ~40 linhas de `.claude/state/logs/<f>/<f>.md`) | iniciar trabalho sem o gate de retomada |
| `python3 .claude/tools/ac/ac.py --work campanhas/<f> status` de uma campanha ativa | rodar portão, régua ou suítes por conta própria (custa tempo: é decisão do founder) |

## O carimbo (dono único: `sessao.py`)

    <!-- resume-stamp
    FRENTES: {ids das frentes ativas em frentes.json | —}
    BRANCH: {branch}
    HEAD: {sha curto na gravação}
    PRODUTO: {sha1 do conteúdo do produto: SKILL.md MODO-DE-USO.md VERSION LICENSE scripts assets references docs evals .claude/package}
    ESTADO: {sha1 de frentes.json + frentes/**}
    GATE: {VERDE | PENDENTE | —}
    -->

Só campos comparáveis entram (data e contagens não: mudam sem que o contexto mude). **Nunca reimplemente um campo**
(nem "só o PRODUTO para conferir"): uma fórmula paralela produz um carimbo que nenhum carregar reproduz ⇒ cache-miss
falso, silencioso. Por isso a fórmula tem um dono só; o `carimbo.sh` do SessionStart é âncora informativa e delega o
carimbo comparável ao `sessao.py`.

- **HEAD por REGRA, não por igualdade:** o `/salvar-sessao` commita, e um arquivo não contém o hash do commit que o
  contém. Bate se igual, ou se avançou só com commits que tocaram `.claude/state/` e `campanhas/` (o carve-out).
  Commit que tocou outra coisa, outra branch, rebase ⇒ não bate.
- **PRODUTO** é o campo mais caro de descobrir tarde: mudou ⇒ o produto vivo não é mais o que foi testado. Estado,
  campanhas, `.claude/` (fora `package/`) e `local/` não entram: salvar sessão nunca invalida a régua.
- **GATE = VERDE** só com evidência no disco: cada frente ativa com `local/portao-<f>/portao.out` terminando em
  `RESULTADO: VERDE` + `FIM`. Qualquer outra coisa é PENDENTE.

## Fluxo

```bash
python3 .claude/tools/sessao.py briefing          # o briefing pronto (≤ 40 linhas) com o veredito de frescor
python3 .claude/tools/sessao.py frescor --json    # detalhe: campos divergentes, salvo × atual
```

| Veredito | Ação | Custo |
|---|---|---|
| `sem-state` | diga que o estado nunca foi inicializado e ofereça `/salvar-sessao` (cria a árvore). **Pare.** | 1 stat |
| `sem-carimbo` | RESUME sem bloco `resume-stamp`: enuncie o que há e sugira `/salvar-sessao` (ou `sessao.py carimbo --write`) | 1 comando |
| `bate` | confie no RESUME e enuncie o briefing. **Não leia o log.** | 1 comando |
| `cache-miss` (FRENTES, BRANCH, HEAD por regra ou ESTADO divergem) | leia as últimas ~40 linhas do log da frente; **julgamento:** reconstrua "Onde paramos" e "Próximos passos" do RESUME a partir dele; `python3 .claude/tools/sessao.py carimbo --write`; rodapé de uma linha `_contexto reconstruído do log_` | +1 leitura, +1 escrita |
| `produto-mudou` (só PRODUTO/GATE divergem) | **não é cache-miss de contexto**: o produto mudou desde o save. Mantenha a âncora e **avise que a régua está PENDENTE** (portão / `/e2e-loop` antes de commit de produto ou pacote) | 0 escrita |

Cache-miss é **self-healing, não erro**: âncora defasada → reconstruída. Nunca reporte como falha.

Campanha ativa no briefing? Se o RESUME diz algo que o `ac.py status` contradiz (etapa que andou, commit que já
entrou), **vale o script**: diga a divergência e corrija o estado no próximo `/salvar-sessao`. Máquina nova: se
`bash .claude/tools/guard-privacidade.sh --termos` avisar que falta `local/termos-privados.txt`, diga ao founder. Se o
SessionStart sugeriu `/install` (pacote desatualizado, travas que faltavam), proponha.

## Formato da resposta — briefing em DUAS sequências

O `briefing` já renderiza; você copia, completa só o que a regra abaixo exigir, e **para**.

    Estado: {IDLE | IN_PROGRESS} · frentes ativas: {ids}
    Git: {branch} @ {HEAD} · {N} arquivo(s) sujo(s) · carimbo: {veredito}
    {Autorizado / NÃO autorizado / Aguardando decisão — do RESUME, seção "Escopo autorizado e limites"}
    Onde paramos: {1–3 linhas do RESUME}

    Sequência de frentes (macro):
    - [x] {última entregue} — entregue {data}
    - [ ] 1. {frente ativa} — {nome} · {k}/{t} tasks   ← VOCÊ ESTÁ AQUI
          ({origem, aberta em …})
    - [ ] criação em curso: {id} · próxima etapa {EN}

    Sequência de tasks (micro) — {frente} · {sequencial | paralelo} · {k}/{t}:
    - [x] 01-TASK-ORACULO — {o que a task faz}
    - [ ] 02-TASK-UM — {o que a task faz} (01-TASK-ORACULO: {por que depende})   ← PRÓXIMA

    Próximos passos: {1–3, do RESUME}
    Retomo daqui? (sim / ajustar)

### Regras do briefing

| Regra | Porquê |
|---|---|
| **Nome + o que é**, nunca só o id | `iter18` só significa algo para quem já sabe |
| Task com `depends` mostra o **porquê do elo** entre parênteses | sem isso "sequencial" é afirmação; com isso é cadeia conferível |
| Só a **última** entregue aparece na macro | é fila, não histórico (o histórico vive em `archive/` e `campanhas/README.md`) |
| `{k}/{t} tasks` é obrigatório | único número que responde "quanto falta" sem abrir nada |
| Nunca marque `[x]` em task que não está DONE | checklist que se auto-aprova é decoração |
| IDLE: só a macro, com a próxima do BACKLOG; sem bloco micro | não há frente para ler |

### Gate de retomada — obrigatório

**Pare depois de enunciar e espere.** `sim` → siga pelo passo 1 dos Próximos passos. `ajustar` → o founder corrige
o ponto de partida antes de qualquer trabalho. Sem o gate, a IA presume contexto e alucina continuidade; retomar do
lugar errado custa mais que uma pergunta.

## Git — reportar, nunca agir

| Reportar (só leitura) | Nunca |
|---|---|
| branch atual e se difere da do carimbo (diga as duas e pergunte qual vale) | trocar de branch |
| HEAD e commits desde o salvo (`git log --oneline {HEAD_salvo}..HEAD`) | commitar, push, stash |
| arquivos sujos (o briefing conta) | limpar o worktree |
| GATE VERDE/PENDENTE; se PENDENTE, que portão ou `/e2e-loop` precisa rodar antes de commit de produto | rodar a régua por conta própria |

## Ponteiros (sob demanda — NÃO ler eager)

- Log da frente: `.claude/state/logs/<f>/<f>.md` · índice das sessões: `.claude/state/logs/sessoes.jsonl`
- Decisões: `.claude/state/DECISIONS.md` · fila: `BACKLOG.md` · última entrega: `LAST_DELIVERY.md`
- Frentes encerradas: `.claude/state/archive/<f>/<f>.md` · ativas: `python3 .claude/tools/frente.py status --brief`
- Trio de sessão: `/carregar-sessao` (este) · `/salvar-sessao` (checkpoint) · `/fechar-frente` (encerrar → IDLE)
