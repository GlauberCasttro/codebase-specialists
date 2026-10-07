# codebase-specialists — harness de desenvolvimento (projeto)

Você está DESENVOLVENDO a skill `codebase-specialists` (não usando-a num alvo). Este repositório é o PROJETO: a raiz
é a skill (SKILL.md na raiz), mais `.claude/` (este harness), `campanhas/` (oráculos) e `local/` (só nesta máquina,
gitignored). **Markdown explica; script decide.** Nunca fabrique aprovação, execução, contagem ou data: elas vêm de
script, relógio e git. Só DESENVOLVIMENTO passa por aqui; o harness nunca entra no pacote (`dist/`).

## Comandos (skills em `.claude/skills/<nome>/SKILL.md` — leia a skill INTEIRA ao ser invocada)

| Comando | Para quê | Scripts (`.claude/tools/`) |
|---|---|---|
| `/carregar-sessao` | retomar: carimbo comparável, frescor por regra, briefing em duas sequências, "Retomo daqui?" | `sessao.py frescor/briefing` |
| `/salvar-sessao` | checkpoint: carimbo no RESUME, log append-only, decisões; `--commit` SÓ do estado; inicializa o estado | `sessao.py salvar` |
| `/criar-frente` | formalizar demanda: E0–E5 com aprovação literal registrada (sha), FRENTE.md + tasks, contrato com sonda, abertura | `frente.py criar`, `contrato.py` |
| `/tech-lead` | orquestrar a frente: plano, PERGUNTA o modo (autônomo/iterativo/status), executor na cópia, conferência, revisão isolada, registro serial, modelo e custo por despacho | `tech_lead.py`, `custo.py`, `frente.py task` |
| `/rh` | contratar subagente auxiliar (ou FAZER DIRETO): elenco verificado, ficha conferida | `rh.py` |
| `/revisor` | revisar isolado (sem escrita) contra os critérios de aceite, o diff e as evidências | — (o tech-lead confere por `tech_lead.py snap`) |
| `/e2e-loop` | régua: seletiva pelo arquivo tocado durante a frente, completa no fechamento e no portão (2 Pythons + harness-dev) | `e2e.py`, `portao.sh` |
| `/fechar-frente` | encerrar: gate de aceite + completude cruzada, campanha fechada, archive único, LAST_DELIVERY, IDLE, commit SÓ da frente | `frente.py fechar`, `campanha.py fechar` |
| `/auto-correcao` | o método: laço de refinamento medido sobre a campanha da frente, com o motor embutido | `ac/ac.py`, `campanha.py` |
| `/package` | gerar e VALIDAR o pacote `dist/` (publicar é decisão do founder) | `package.sh` |
| `/install` | instalar nesta máquina: travas do git + link para o pacote validado | `instalar.sh` |

Todos os scripts: Python 3.9+ stdlib (ou bash), `--help`; os que escrevem têm `--dry-run`; os que informam,
`--json`/`--brief` (≤ 40 linhas). Exit 0 ok · 1 recusa · 2 lacunas/pergunta pendente · 3 uso. Dados que decidem:
`regras.json` (até 2 frentes ativas), `roteamento.json` (modelo por papel), `personas.json`, `elenco.json`,
`regua.json`. Lógica comum: `estado_lib.py`.

## Âncora e estado

- Âncora informativa: `bash .claude/tools/carimbo.sh` (o SessionStart injeta `--brief`: branch, HEAD, VERSION,
  campanhas, sujos, frescor). O carimbo COMPARÁVEL do RESUME (FRENTES/BRANCH/HEAD/PRODUTO/ESTADO/GATE) tem UM dono:
  `sessao.py` — nunca o recalcule à mão.
- `.claude/state/`: `frentes.json` (ativas/entregues — só scripts escrevem), `frentes/<id>/` (eventos.jsonl,
  CHECKLIST, propostas/, FRENTE.md, TASKS/, INDEX, HISTORICO), `archive/<id>/<id>.md` (documento único),
  `LAST_DELIVERY.md`, `logs/<id>/<id>.md` + `logs/sessoes.jsonl` + `logs/custo.jsonl`, RESUME (âncora), WORKFLOW
  (bloco gerado entre `<!-- frentes:inicio -->`/`<!-- frentes:fim -->`; o resto é humano), BACKLOG, DECISIONS (só do
  founder, append-only).
- Editável direto (guard-entrega): `.claude/state/**`, `campanhas/**`, `local/**`, `dist/**`. Dentro do estado, o
  `guard-estado.py` nega o que é do script (frentes.json, CHECKLIST, eventos, propostas), FRENTE.md antes da E2,
  TASKS antes da E3, task DONE sem gate PASS e Handoff, e archive que não seja o documento único.
- **Até 2 frentes ativas** (decisão do founder), uma criação por vez, colisão de escopo provada por `ac.py overlap` na
  abertura. Campanha antiga entra como ativa `legado` por `frente.py adotar <id>`. Gate de retomada: ao carregar,
  enuncie e PARE até o founder dizer `sim`.

## Fluxo de entrega (frente = campanha no motor embutido)

Motor: `.claude/tools/ac/ac.py` (cópia da auto-correcao; origem em `ac/ORIGEM.txt`; não se edita aqui). Sempre o
caminho LITERAL `python3 .claude/tools/ac/ac.py --work campanhas/<frente> ...` — o hook de aprovação nega variável +
palavra de aprovação.
1. `/criar-frente`: E1–E5 aprovadas pela palavra LITERAL do founder no chat (registrada com o sha da proposta); a
   abertura faz `ac.py init` (um `--scope` por glob do Escopo de escrita), INDEX, HISTORICO, WORKFLOW. Nunca commita.
2. Oráculo pela task ORACULO, por um agente SEPARADO (quem testa não constrói), em `campanhas/<frente>/oraculo/`,
   congelado (`oracle freeze` com todos os arquivos). Mudança só oficial: patch + PORQUE em `mudanca-oficial/` →
   `campanha.py mudanca-oficial`.
3. Aprovação humana: `bash .claude/tools/script-aprovacao.sh <frente>` GERA `local/aprovar-<frente>.sh` (recusa sem
   oráculo congelado); o FOUNDER roda no terminal dele, com a senha. A senha só entra aí e na `frase conferir`.
   Nunca peça a senha no chat; nunca rode o script; nunca aprove pela IA.
4. `/tech-lead`: corretor bloqueado até a aprovação do founder (`ac.py check intake.3`); só na cópia de trabalho
   (`bash .claude/tools/copia.sh <frente>` → `local/work/<frente>/`); revisão isolada (`/revisor`); régua seletiva
   (`/e2e-loop`); `frente.py task marcar` exige gate PASS e Handoff.
5. Portão: `bash .claude/tools/portao.sh <frente> [--oraculo campanhas/<frente>/oraculo:<mod>]... --lista <arq>`
   (cópia limpa = HEAD + só os arquivos da frente; suítes do produto e `harness-dev` em `python3` e `/usr/bin/python3`;
   oráculos; nenhum `def` removido). Saída em `local/portao-<frente>/portao.out` (`RESULTADO:` e `FIM`). Background.
6. `/fechar-frente`: `portar.sh` (merge de 3 vias; para em conflito) → gate (`frente.py fechar check`) → campanha
   (`campanha.py fechar`; o founder roda `frase conferir`) → archive → LAST_DELIVERY → limpeza → IDLE → commit SÓ da
   frente num índice temporário (exige o `preauth commit` do founder, `conferir-commit.sh` e privacidade).
7. Depois do commit da frente, `/install`; ao fechar a versão, `/package`. Achados de uso real vindos de outras
   sessões chegam por mensagem e viram item do BACKLOG ou frente (D-11).

## Git e privacidade

- Repo próprio (branch `master`, remoto público). `git add` arquivo a arquivo; nunca `-A`/`.`/`-a`. Mensagem de
  commit SEMPRE em arquivo. Autor: `GlauberCasttro <GlauberCasttro@users.noreply.github.com>`.
- Proibido (hook `guard-git.sh`): reset --hard, checkout --/restore do worktree, clean -f, stash, push (push só pelo
  humano), add -A/--all/., commit -a. Os commits do harness (salvar-sessao, fechar-frente) usam índice temporário:
  alteração de terceiros nunca é commitada nem descartada (mesmo em stage).
- O repositório é PÚBLICO. Termos privados em `local/termos-privados.txt`, pares de limpeza em
  `local/regras-privadas.json5` (gitignored). `bash .claude/tools/guard-privacidade.sh` (projeto), `--staged`,
  `--msg ARQ`, `--git-log`; o pre-commit do harness roda o guard no índice e na mensagem. Em teste/fixture,
  pessoa = "Ana"; cobaia = "repositório-piloto (projeto-legado)" ou "cobaia .NET"; caminhos com `~` ou variável.

## Custo e agentes

- Máx. 5 agentes simultâneos (3 se der 429); cada subagente grava só o próprio escopo; o estado é gravado em série
  pelo agente principal. Modelo por papel (`tech_lead.py modelo`; o hook `exige-modelo.py` bloqueia despacho de task
  sem `model`) e custo medido por despacho (`custo.py registrar`).
- Confirme o custo com o founder antes de medição pesada (D-09). Cópias de trabalho e portões em `local/`, nunca
  em /tmp.

## Lições (curtas)

- zsh não faz word-split de `$VAR`: passe arquivos explícitos ou `--lista ARQ` nos tools.
- AC-09: `run record` no mesmo segundo do `done` não registra; re-registre (o `campanha.py fechar` espera 1 s).
- `oracle change --file X` SUBSTITUI a lista inteira de arquivos do oráculo: passe sempre TODOS.
- Só entra no commit o que o portão testou (`conferir-commit.sh`). Depois de merge no `portar.sh`, rode de novo
  o portão com `--src .`.
- Comandos DESTE harness em português (pedido do founder). A D-07 (inglês verbo-objeto) vale para as skills que o
  PRODUTO gera nos alvos — guardada pelo oráculo da iter15, que o portão roda. Não confundir os dois.

## O que NÃO existe (não alegue)

- `guard-entrega.py` e `guard-estado.py` só veem Edit/Write/MultiEdit/NotebookEdit. Escrita por Bash não é bloqueada
  — é por Bash que os scripts escrevem; `frente.py checklist` e o sha das propostas detectam a adulteração depois.
- A palavra de aprovação E1–E5 é registrada pelo agente: o script garante ordem, vínculo ao sha e literalidade, não
  que o founder disse. A senha só entra no script de aprovação e na conferência.
- `guard-git.sh`, `hook_aprovacao.py` e `exige-modelo.py` são filtros, não sandbox. O pre-commit só existe depois de
  `tools/instalar-hooks-git.sh`, `/install` ou do SessionStart (o `.git/hooks/` não é versionado).
- Os hooks só valem com o Claude aberto NESTA pasta. Os ledgers das campanhas (`campanhas/*/.auto-correcao/`) são
  locais: numa máquina nova o histórico das campanhas é só o que está em `campanhas/` (oráculos + README).
- A régua e o portão não medem qualidade de uso real; medem suítes, oráculos, pacote e remoção de `def`. A seleção do
  `e2e.py` é um mapa por caminho, não um grafo de import.
