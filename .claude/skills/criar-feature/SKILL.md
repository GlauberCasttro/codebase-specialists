---
name: criar-feature
description: >
  Transforma uma demanda solta do founder numa FEATURE de desenvolvimento da codebase-specialists pronta para
  executar, em 5 etapas com aprovação literal do founder entre cada uma: analisar a demanda → investigação medida →
  FEATURE.md rico (CAs DADO/QUANDO/ENTÃO com Prova executável) → tasks com contrato validado por script e sonda
  negativa → abertura (campanha no motor embutido, INDEX, HISTORICO, WORKFLOW). Use quando o founder disser "cria uma
  feature", "nova feature", "/criar-feature", "quero mudar X na skill", "vamos fazer o item B-0N do backlog", "abre uma
  feature para…", ou trouxer um achado de uso real que vira trabalho. Retomável: rodar de novo continua da etapa em
  que parou. Nunca commita, nunca aprova pela IA.
disable-model-invocation: true
---

# /criar-feature — da demanda solta à feature aberta, em 5 etapas com aprovação

Recebe uma demanda em linguagem natural ("estende a senha pros outros comandos do mandato") e produz, em
`.claude/state/features/<id>/`: `CHECKLIST.md` com as 5 aprovações, `propostas/` (E1, E2, E5), `FEATURE.md` rico,
`TASKS/` decompostas, `INDEX.md` e `HISTORICO.md` — e, fora do estado, a campanha `campanhas/<id>/` no motor
embutido, a feature em `features.json` e no bloco gerado do `WORKFLOW.md`.

**Nenhuma etapa avança sem o "ok" literal do founder.** É a razão de a skill existir: sem os portões, a demanda vira
artefato numa tacada só e o rigor depende de lembrar de aplicá-lo. A feature nasce pobre, o oráculo nasce pobre, e
oráculo pobre aprova qualquer coisa.

**Quem decide é o script.** `python3 .claude/tools/feature.py criar …` é o controlador: confere cada artefato com
`.claude/tools/contrato.py`, registra o **sha** do que foi proposto, só aceita a aprovação se o artefato continuar
idêntico ao proposto, escreve o CHECKLIST (projeção dos eventos) e executa a abertura. O hook
`.claude/tools/guard-estado.py` nega a escrita direta do que é do script. A você cabe o **julgamento**: entender a
demanda, medir, escrever bem, decompor bem e apresentar ao founder com recomendação.

---

## Regras que valem nas 5 etapas

| Regra | Porquê |
|---|---|
| **Até 2 features ativas, uma criação por vez** (`.claude/tools/regras.json`, decisão do founder) | este projeto roda features disjuntas em paralelo (L17); a disjunção é PROVADA por `ac.py overlap` na abertura, não presumida. `feature.py criar iniciar` recusa no limite — sem override; o caminho é `/fechar-feature` |
| **Medir antes de afirmar** | toda afirmação da investigação tem `arquivo:linha` ou contagem — o contrato recusa a E2 sem achado `F<n>` com `arquivo:linha`. "Acho que afeta os scans" é inválido; "afeta 3 de 11 extratores, lista abaixo" é válido |
| **Amostra não é auditoria** | varreu um universo ⇒ declare o que ficou de fora (rótulo `Exclusões`, obrigatório) |
| **Não avançar sem aprovação** | ao fim de cada etapa: propor, apresentar, perguntar e **PARE**. `ok` ⇒ aprovar · `ajustar {o quê}` ⇒ rejeitar e refazer · `pausar` ⇒ o progresso já está no disco; encerre |
| **A aprovação é do founder** | `--palavra` é a fala dele, verbatim, nesta conversa (começa por ok/sim/aprovo/aprovado). Nunca escreva aprovação que ele não deu; nunca deduza "ok" de silêncio ou de outra pergunta |
| **A senha não entra aqui** | E1–E5 são aprovadas pela palavra literal no chat (decisão do founder); a senha só entra no script de aprovação da campanha e na `frase conferir` — que o FOUNDER roda no terminal dele |
| **Nunca commita** | a criação só prepara a feature; checkpoint é `/salvar-sessao`; commit de produto só no `/fechar-feature` |
| **Nada de código de produto** | esta skill monta a feature; a execução é do `/tech-lead`, na cópia de trabalho |

### O CHECKLIST — criado no arranque, marcado a cada aprovação

`feature.py criar iniciar` cria `.claude/state/features/<id>/CHECKLIST.md` antes de qualquer análise. Ele é ao mesmo
tempo o **progresso visível** para o founder, a **fonte de retomada** entre sessões e o **registro de aprovação** de
cada etapa (palavra literal + sha do artefato aprovado). O CHECKLIST é a **projeção determinística** de
`eventos.jsonl`: a seção `## Handoffs` é append-only (aprovações e rejeições, na ordem); caixa marcada à mão é
detectável (`python3 .claude/tools/feature.py checklist <id>` sai 2) e o hook nega o Edit. Você não edita o
CHECKLIST — o script escreve.

**Retomada:** `feature.py criar iniciar <id> --demanda <a mesma>` com criação em curso não escreve nada: diz a
próxima etapa (e se há proposta pendente de decisão). `python3 .claude/tools/feature.py status --json` mostra o
mesmo (`criacao.proxima`). Cada etapa tem pós-condição no disco — nunca "eu já fiz isso".

### Aprovação com recomendação

Toda pergunta ao founder vem com `→ recomendo` + motivo (medido em `arquivo:linha` ou "hipótese") + alternativa,
no formato de `.claude/skills/tech-lead/references/aprovacao-com-recomendacao.md`. `ok` aceita o conjunto — passe a
lista resolvida em `--itens` para o registro dizer o que foi aprovado item a item.

---

## Etapa 0 (E0) — Pré-condição (gate mecânico, sem aprovação)

```bash
python3 .claude/tools/sessao.py briefing            # âncora: features ativas, criação em curso, git
python3 .claude/tools/feature.py criar iniciar <id> --demanda "<a fala do founder, 1 linha>" [--dry-run]
```

- exit 1 `ABORTADO` ⇒ **fim da execução.** Não escreva nada, não ofereça atalho, não aceite insistência. Motivos:
  `.claude/state/` não existe (inicialize com `/salvar-sessao`), id fora da gramática, id já usado (feature, campanha
  ou archive), outra criação em curso, ou limite de features ativas — "feche uma com `/fechar-feature`".
- `RETOMADA` ⇒ siga da etapa informada.
- O id É o nome da campanha (`^[a-z][a-z0-9]*(-[a-z0-9]+){0,5}$`, como `iter18`, `harness-dev`): é pasta em
  `campanhas/`, `archive/` e `local/work/`. Pense nele na E1 antes de iniciar; se mudar, a criação recomeça.

---

## Etapa 1 (E1) — Analisar a demanda

**Objetivo:** transformar a fala do founder em problema enunciado. **Não** propor solução aqui.

Escreva a proposta (fora do estado, ex. `local/criar-<id>/E1.md`; modelo:
`.claude/skills/criar-feature/references/modelos/E1.md`) com os 5 rótulos:

| Rótulo | Conteúdo |
|---|---|
| **Demanda** (literal) | o que o founder pediu, nas palavras dele |
| **Problema por trás** | a dor, não a solução pedida |
| **O que NÃO é** | fronteira explícita — o campo que mais evita retrabalho |
| **Perguntas abertas** | só as que mudam o desenho (máx. 3), cada uma com `→ recomendo` |
| **FEATURE-ID** | o id da criação |

```bash
python3 .claude/tools/feature.py criar propor <id> --etapa E1 --arquivo local/criar-<id>/E1.md --json
```

O script copia a proposta para `features/<id>/propostas/E1.md` e devolve o `sha`. **➜ Aprovação:** apresente o E1 no
chat. *"Fecha assim o problema? (ok / ajustar {o quê} / pausar)"* — **PARE.**

```bash
python3 .claude/tools/feature.py criar aprovar <id> --etapa E1 --sha <sha> --palavra "<fala literal>" \
  --produzido "problema enunciado; FEATURE-ID <id>" --proxima "E2 — investigação medida" [--itens "1: …"]
python3 .claude/tools/feature.py criar rejeitar <id> --etapa E1 --sha <sha> --motivo "<o que ajustar>"   # se ajustar
```

Mudou a proposta depois de propor? O `aprovar` recusa (sha diferente). Proposta rejeitada não se aprova: refaça,
proponha de novo (sha novo) e reapresente.

---

## Etapa 2 (E2) — Investigação medida

**Objetivo:** substituir achismo por número, **antes** de escrever a feature. Só o que a demanda exigir.

Proposta com os 5 rótulos (modelo: `references/modelos/E2.md`):

1. **Inventário** — `grep -rn`/`rg -n` do universo afetado (produto: `scripts/`, `references/`, `SKILL.md`,
   `evals/`…; harness: `.claude/`), com contagem por arquivo.
2. **Classificação** — cada ocorrência num balde (muda / não muda / congelado), soma fechando com o total.
3. **Exclusões** — o que ficou fora e por quê (amostra não é auditoria).
4. **Achados** — `F1`, `F2`…, cada um com `arquivo:linha` e o mecanismo. Achado descartado por medição **fica**
   registrado como descartado.
5. **Enforcement existente** — que teste, suíte ou oráculo de campanha anterior (`campanhas/*/oraculo/`) já cobre ou
   deixa de cobrir o assunto.

```bash
python3 .claude/tools/feature.py criar propor <id> --etapa E2 --arquivo local/criar-<id>/E2.md --json   # exit 2 sem F<n> com arquivo:linha
```

**➜ Aprovação:** *"A investigação cobre o suficiente? (ok / investigar mais {o quê} / pausar)"* — **PARE.** Depois
`feature.py criar aprovar <id> --etapa E2 … --medido "<números>"`. A E2 inteira vai para o `[NOTA]` de abertura do
HISTORICO e para o archive.

---

## Etapa 3 (E3) — Escrever o `FEATURE.md` (Bloco A)

Só depois da E2 aprovada (antes disso o `guard-estado.py` nega a escrita). **Consulta obrigatória antes de
escrever:** a Lei em `.claude/skills/criar-feature/references/contrato-feature.md` e o gabarito
`references/modelos/FEATURE.md`. Escrever "de cabeça" é a origem documentada da feature pobre.

Escreva `.claude/state/features/<id>/FEATURE.md` (nome fixo; a identidade é a linha `FEATURE-ID:`):

```
FEATURE-ID · Nome · ## História (Como…quero…para — vira o --problem da campanha) · ## Problema / Contexto (com a
evidência da E2) · ## Valor de negócio · ## Personas / Stakeholders · ## Critérios de Aceitação (CA-NN em
DADO/QUANDO/ENTÃO + linha "Prova: `comando`") · ## RNFs · ## Edge cases · ## Dependências · ## Escopo IN ·
## Escopo OUT · ## Escopo de escrita (globs estreitos — vira o --scope) · ## Critério de parada (com número — vira o
--stop) · ## Métrica de sucesso · ## Aceite da Feature (### Aceite QA — PENDENTE / ### Aceite Review — PENDENTE)
```

```bash
python3 .claude/tools/contrato.py feature .claude/state/features/<id>/FEATURE.md     # exit 0 PASS · 2 lacunas listadas
python3 .claude/tools/feature.py criar propor <id> --etapa E3 --json                # roda o mesmo contrato e registra o sha
```

- exit 2 ⇒ o script **lista** as lacunas por código (`campo_ausente:RNFs`, `ca_sem_prova:CA-02`,
  `escopo_amplo:**`…): corrija e rode de novo. Na E3 só "CA órfão" pode esperar a E4 (ainda não há tasks).
- Limite honesto: o contrato confere presença, forma e coerência; não confere se o CA é o certo nem se a Prova prova
  o CA. Isso é a revisão do founder.

**➜ Aprovação:** apresente o FEATURE.md e o resultado do contrato. *"Aprova a feature? (ok / ajustar {campo} /
pausar)"* — **PARE.** Depois `feature.py criar aprovar <id> --etapa E3 …`.

---

## Etapa 4 (E4) — Decompor em tasks (Bloco B)

Uma task = um arquivo em `.claude/state/features/<id>/TASKS/` (só depois da E3 aprovada). Gabarito:
`references/modelos/TASK.md`.

**Nome:** `{NN}-{TASK|BUG|GAP|DEBT}-{DESCRICAO}.md` (NN nunca reutilizado). **O ciclo da campanha vira tasks
obrigatórias, por tipo:**

| tipo | grupo | quem | o que entrega |
|---|---|---|---|
| `ORACULO` | `—` | **agente separado** (nunca o corretor) | ESPEC + testes em `campanhas/<id>/oraculo/` que falham antes; o tech-lead congela (`oracle freeze`) |
| `CORRECAO` (1+) | `G1`..`G3` (≤ 3 grupos, arquivos **disjuntos** entre grupos) | corretor, na cópia de trabalho | a mudança, nos `Arquivos permitidos` exatos, dentro do Escopo de escrita; depende (transitivamente) do ORACULO; nunca toca o oráculo |
| `QA` | `—` | QA | portão + oráculo, CA a CA (fase fechamento do `/e2e-loop`) |
| `REVIEW` | `—` | revisor isolado (`/revisor`) | parecer APPROVED / CHANGES_REQUESTED |

**Conteúdo — schema completo, sem exceção:** título `# <id> — <entrega>`; cabeçalho `id`, `feature`, `tipo`, `grupo`,
`agente`, `CA`, `depends` (`—` ou `ID (porquê), ID (porquê)`), `status: PENDENTE`, `gate: PENDENTE`, opcional
`complexidade`; seções `## Goal` (o que muda **e o que não fazer**) · `## Contexto` (CA + âncora real) ·
`## Subtasks` (2–5 passos numerados) · `## Invariants` · `## Scope IN / OUT` · `## Arquivos permitidos` (paths
exatos, nunca glob; o próprio arquivo da task é isento) · `## AC` · `## DoD` · `## Verificação` (bloco de código com
comando concreto — nunca só ls/echo/TBD/true/cat) · `## Handoff` (nasce vazio; DONE exige preenchido).

**Regras de decomposição (todas conferidas pelo contrato):** todo CA coberto por task CORRECAO; mesmo arquivo em 2
tasks ⇒ serializar por `depends`; mesmo arquivo em grupos diferentes ⇒ proibido (grupos são disjuntos); depends
sempre com o porquê, sem ciclo, só para ids existentes; QA depende das correções; REVIEW depende da QA. A união dos
`Arquivos permitidos` das CORRECAO É a lista do portão, do `conferir-commit.sh` e do commit do fechamento — pense
nela com cuidado.

**Complexidade (opcional):** `complexidade: baixa` só se o checador aceitar
(`python3 .claude/tools/contrato.py complexidade <task.md>`, exit 2 recusa: > 2 arquivos, área sensível, texto de
protocolo ou verificação trivial). É o sinal que o `/tech-lead` usa para rotear o executor em haiku.

```bash
python3 .claude/tools/contrato.py --sonda                                   # 0 = o contrato discrimina; 3 = NOT_RUN
python3 .claude/tools/contrato.py completo .claude/state/features/<id>       # exija exit 0
python3 .claude/tools/feature.py criar propor <id> --etapa E4 --json         # sonda + completo + complexidades; registra o sha
```

NOT_RUN da `--sonda` (o contrato não reprova uma task sem Goal) **bloqueia** — nunca troque por avaliação manual.
Revise também cada task individualmente: rótulos presentes não provam que a Verificação prova o CA.

**➜ Aprovação:** apresente a tabela (id · tipo · grupo · agente · CAs · depends com o porquê) + o resultado do
contrato. *"Aprova a decomposição? (ok / ajustar {task} / pausar)"* — **PARE.** Depois
`feature.py criar aprovar <id> --etapa E4 …`. O sha da E4 cobre FEATURE.md + TASKS: qualquer mudança depois do ok
bloqueia a abertura.

---

## Etapa 5 (E5) — Abrir a feature

Proposta de abertura com os 5 rótulos (modelo: `references/modelos/E5.md`): **Ordem** (cadeia de tasks, com a
aprovação do founder entre o oráculo e a correção), **Primeira task**, **Escopo da campanha** (os globs do Escopo de
escrita), **Critério de parada** (o número), **Git** (o que será escrito; nada commitado).

```bash
python3 .claude/tools/feature.py criar propor <id> --etapa E5 --arquivo local/criar-<id>/E5.md --json
python3 .claude/tools/feature.py criar abrir <id> --dry-run --json      # o que será feito/escrito, sem escrever
```

Apresente: FEATURE-ID, tasks/CAs, primeira task sem dependência, ordem, o escopo exato da campanha (`--scope` por
glob), problema e critério de parada, as features ativas com que colidiria (se alguma) e a situação do git.

**➜ Aprovação:** *"Aprova abrir esta feature? (ok / ajustar / pausar)"* — **PARE.** Depois:

```bash
python3 .claude/tools/feature.py criar aprovar <id> --etapa E5 --sha <sha> --palavra "<fala literal>" --produzido "plano de abertura" --proxima "oráculo por agente separado"
python3 .claude/tools/feature.py criar abrir <id> --json
```

`abrir` recusa (exit 1, nada escrito) se faltar aprovação, se o CHECKLIST foi adulterado, se algum artefato mudou
depois do ok (sha), se o contrato completo tem lacuna, no limite de features ativas ou se há **colisão** de escopo com
uma feature ativa (campanha temporária com os mesmos globs + `ac.py overlap`). Passou, escreve **nesta ordem**:
`ac.py --work campanhas/<id> init --target . --scope … --problem <História> --stop <Critério de parada>` → INDEX
(depends com o porquê) → HISTORICO (`[NOTA]` com a E2) → log da feature → `features.json` → bloco do WORKFLOW
(IN_PROGRESS) → linha em `campanhas/README.md` → handoff `### Abertura` no CHECKLIST. **Não commita** e **não**
gera o script de aprovação.

Depois do `abrir`, é **julgamento seu** (o script não decide):

1. `DECISIONS.md` — apense as decisões travadas nas 5 etapas, com o porquê (só decisão do founder).
2. `BACKLOG.md` — marque o item como "em feature <id>".
3. `RESUME.md` — escopo autorizado, sequência, próximos passos (o carimbo é do `/salvar-sessao`).

**A sequência depois da abertura (não pule):**

1. **Oráculo pela task 01, por agente separado** (persona `oraculista` via `/rh`) em `campanhas/<id>/oraculo/`;
   o tech-lead confere e congela com `python3 .claude/tools/ac/ac.py --work campanhas/<id> oracle freeze --file …`
   (TODOS os arquivos).
2. **Aprovação do founder:** `bash .claude/tools/script-aprovacao.sh <id>` GERA `local/aprovar-<id>.sh` — e recusa
   se o oráculo não estiver congelado (quem testa não constrói: o founder aprova vendo o oráculo). **O FOUNDER roda
   no terminal dele, com a senha.** Você não roda, não pede a senha, não simula.
3. Só então correção: `/tech-lead` (o corretor fica bloqueado até `ac.py check intake.3` passar).

**Sinalize:**

    Feature {id} aberta (nada commitado). Tasks: {N} · CAs cobertos: {N}/{N} · primeira: {01-TASK-ORACULO}
    Campanha: campanhas/{id}/ · escopo: {k} glob(s) · parada: {critério}
    Próximo: oráculo por agente separado → oracle freeze → script-aprovacao.sh (o founder roda com a senha)
    → /tech-lead (pergunta o modo: autônomo ou iterativo)

---

## Invariantes

1. Nenhuma etapa avança sem a aprovação literal do founder **registrada pelo script** com o sha do artefato aprovado.
2. Antes da E2 aprovada, em `features/<id>/` só existem eventos, CHECKLIST e `propostas/`; FEATURE.md só depois da E2;
   TASKS só depois da E3 (hook). Rascunho não é feature aberta: só o `abrir` põe a feature em `features.json`.
3. Afirmação de investigação sem `arquivo:linha`/contagem é inválida.
4. A abertura exige contrato completo em exit 0 com sonda negativa válida. NOT_RUN nunca conta como PASS.
5. Até 2 features ativas, uma criação por vez; colisão de escopo provada pelo motor recusa a abertura.
6. A skill não commita, não dá push, não roda o script de aprovação, não pede nem digita senha.

## Ponteiros

- Controlador: `.claude/tools/feature.py` (`--help`) · Lei: `.claude/tools/contrato.py` (`--help`) · hook:
  `.claude/tools/guard-estado.py`
- A Lei em prosa + gabaritos: `.claude/skills/criar-feature/references/` (`contrato-feature.md`, `modelos/`)
- Motor: `.claude/tools/ac/ac.py` · aprovação: `.claude/tools/script-aprovacao.sh` · cópia: `.claude/tools/copia.sh`
- Par: `/fechar-feature` · execução: `/tech-lead` · método da campanha: `/auto-correcao` · sessão:
  `/carregar-sessao`, `/salvar-sessao`
