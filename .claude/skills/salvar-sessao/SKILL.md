---
name: salvar-sessao
description: >
  Salva o contexto de desenvolvimento da codebase-specialists em .claude/state/: regrava o carimbo comparável do
  RESUME.md (FRENTES/BRANCH/HEAD/PRODUTO/ESTADO/GATE), apensa a sessão em logs/sessoes.jsonl (e no log da frente),
  atualiza RESUME/WORKFLOW/BACKLOG/DECISIONS (julgamento) e, com --commit, COMMITA só .claude/state/** num índice
  temporário, depois do guard de privacidade (terceiros intactos; nunca push). Auto-teste: um carregar imediato tem
  de dar "bate". Também INICIALIZA o .claude/state/ quando ele não existe. Frases que disparam: "salvar sessão",
  "/salvar-sessao", "salva o contexto", "registra onde paramos", "fecha a sessão", "checkpoint".
disable-model-invocation: true
---

# /salvar-sessao — registrar onde paramos

Contraparte do `/carregar-sessao`. **Write-once-read-many:** o custo vai para esta escrita rara (1× por sessão) para
que a leitura frequente (todo início de sessão) custe um comando. O mecânico é do script
(`python3 .claude/tools/sessao.py salvar`); o que é julgamento (o texto do RESUME, o que é decisão do founder, o que
entra no BACKLOG) é seu.

| Artefato | Operação | Quem |
|---|---|---|
| `RESUME.md` | **sobrescrever** o texto (snapshot "você está aqui"; cache regenerável) | carimbo: script · texto: você |
| `logs/sessoes.jsonl` | **apensar** (1 linha: evento, data, resumo, branch, HEAD, frentes) | script |
| `logs/<f>/<f>.md` | **apensar** (≤ 20 linhas por sessão; nunca reescrever bloco antigo) | script (`--frente F --feito …`) |
| `WORKFLOW.md` | o bloco gerado é do `frente.py`; fora dele: sequência de frentes, entregas | você (copie números de scripts) |
| `DECISIONS.md` | **apensar**: só decisão DO FOUNDER, com o porquê | você |
| `BACKLOG.md` | itens novos (inclusive achados de outras sessões) com origem e critério de pronto | você |
| `frentes.json`, `frentes/<f>/` | **não é deste ritual**: é do `/criar-frente`, do `/tech-lead` e do `/fechar-frente` | — |

## Contrato

| Pode | Não pode |
|---|---|
| escrever em `.claude/state/**` (o que o `guard-estado.py` deixa) | escrever no produto, no harness ou em `campanhas/` |
| **commitar só o estado** (`--commit`: `.claude/state/**`, índice temporário) | `push`, `tag`, `checkout`, `reset --hard`, `stash`, `add -A` |
| criar a árvore do estado que faltar (o `salvar` cria RESUME/WORKFLOW/BACKLOG/DECISIONS/logs) | apagar log, reescrever bloco antigo, editar o carimbo à mão |
| reportar a régua PENDENTE | **rodar** portão/régua sem o founder pedir |
| registrar o estado das frentes ativas | **encerrar** frente (é do `/fechar-frente`) ou abrir frente |

**Pós-condição (auto-teste):** um `/carregar-sessao` imediato dá **bate**. O `salvar` confere isso sozinho e sai com
exit 1 e "O SAVE ESTÁ ERRADO" se não der. Código da sessão nunca entra por aqui: entra pela frente (portão →
`/fechar-frente`).

## Passos

### 1. Coletar (só leitura)

```bash
python3 .claude/tools/sessao.py frescor --brief
python3 .claude/tools/frente.py status --brief
```

Campanha ativa: `python3 .claude/tools/ac/ac.py --work campanhas/<f> status` (copie a etapa; não estime).

### 2. Texto do RESUME (julgamento; Edit no corpo, NUNCA no bloco resume-stamp)

    ## Escopo autorizado e limites
    - Autorizado: {o resultado que o founder pediu, 1–2 linhas, com data/frase literal da autorização}
    - NÃO autorizado: {o que está fora — inclusive o "óbvio" de fazer junto}
    - Aguardando decisão: {— | o que precisa de aval}

    ## Onde paramos (1–3 linhas concretas)
    ## Próximos passos (1–3, executáveis sem reler nada, com comando pronto)
    ## Estado do ambiente (o que ficou fora do commit e de quem; cópias de trabalho/portões em local/)
    ## Ponteiros

**O NÃO autorizado importa mais que o autorizado:** é a metade que não se deduz do trabalho feito. Sem ela a sessão
seguinte amplia escopo em silêncio. Nada privado: nomes reais e caminhos absolutos vão para `local/` (o guard de
privacidade recusa o commit).

### 3. WORKFLOW, DECISIONS, BACKLOG (julgamento)

- WORKFLOW (fora do bloco gerado): a sequência de frentes em checklist (`- [x]` entregue · `- [ ] n. <id> — <o que
  entrega>` com o porquê da ordem na 2ª linha) e "Últimas entregas" (commit e data do `git log`, não da memória).
- DECISIONS: `| D-nn | data | decisão | porquê | onde vale |` — só o que o FOUNDER decidiu nesta sessão.
- BACKLOG: achados novos com origem e "pronto quando" verificável.

### 4. Salvar (o script faz o mecânico, nesta ordem)

```bash
python3 .claude/tools/sessao.py salvar --resumo "<1 frase>" [--frente <f> --feito "<o que mudou>"] --dry-run
python3 .claude/tools/sessao.py salvar --resumo "<1 frase>" [--frente <f> --feito "<o que mudou>"] --commit --mensagem local/msg-sessao.txt
```

`salvar` = (cria o estado se faltar) → carimbo no RESUME → linha em `logs/sessoes.jsonl` (+ bloco no log da frente)
→ com `--commit`: guard de **privacidade** nos arquivos do estado e na mensagem (achou ⇒ exit 1, nada commitado) →
commit **só** de `.claude/state/**` num índice temporário a partir do HEAD (o stage de terceiros fica onde está) →
auto-teste (frescor = bate). Mensagem sempre em arquivo. `--dry-run` mostra sem escrever. Data, HEAD e contagens vêm
do relógio e do git, nunca de você.

Alteração de **terceiros** (fora do estado, mesmo em stage): nem commite nem descarte — o commit do save só leva o
estado. Liste no relatório (seção "Estado do ambiente").

### 5. Reportar (curto)

    Sessão salva{ e commitada: {sha}} · frentes ativas: {ids} · {k}/{t} tasks
    Git: {branch} @ {sha} · fora do commit: {— | N caminhos de terceiros, intactos}
    Régua: {VERDE | PENDENTE — portão/e2e-loop antes de commit de produto ou pacote}
    autoteste (carregar imediato): bate

## Git deste projeto

- O commit do save é só de estado: **nunca** invalida a régua (o estado não entra no PRODUTO) e o carimbo segue
  batendo (o HEAD é comparado por regra: commit só em `.claude/state/` é carve-out).
- `push` é do founder. Branch protegida: avise antes de qualquer publicação.
- O pre-commit do harness (guard de privacidade) vale também aqui; recusa ⇒ limpe o termo e repita.

## Ponteiros

- Trio: `/carregar-sessao` · `/salvar-sessao` (este) · `/fechar-frente` (encerrar → IDLE, archive, LAST_DELIVERY)
- Fórmula do carimbo (dono único): `.claude/tools/sessao.py` (`carimbo.sh --write` a chama)
