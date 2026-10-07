# Contrato da frente e das tasks — A LEI + O EXEMPLO

Validador mecânico: `python3 .claude/tools/contrato.py frente|completo|task|etapa|complexidade|--sonda` (stdlib,
Python 3.9+, nos 2 Pythons; exit 0 = PASS, 2 = lacunas listadas por código, 3 = uso/NOT_RUN). Este arquivo é a Lei em
prosa; **o script é a régua**. Se divergirem, o script vence e este arquivo é corrigido.

Por que existe: sem contrato, a frente nasce como título + "melhorar X" e o rigor depende de lembrar de aplicá-lo.
Frente pobre gera oráculo pobre, e oráculo pobre aprova qualquer coisa. O contrato é um script único (sem cópia em
sandbox que derive) e tem **sonda negativa** própria (`--sonda`): uma frente válida tem de passar e a mesma frente
sem o `## Goal` de uma task tem de reprovar. Se a sonda falhar, o contrato não discrimina e nada que ele diga vale
(NOT_RUN, nunca PASS).

## A LEI

### Propostas E1 / E2 / E5 (`contrato.py etapa EN <arquivo>`)

| Etapa | Rótulos obrigatórios (início de linha, como rótulo ou título) | Lacuna extra |
|---|---|---|
| E1 | Demanda · Problema por trás · O que NÃO é · Perguntas abertas · FRENTE-ID | FRENTE-ID ≠ id da criação |
| E2 | Inventário · Classificação · Exclusões · Achados · Enforcement existente | `e2_sem_evidencia`: nenhum `F<n>` com `arquivo:linha` |
| E5 | Ordem · Primeira task · Escopo da campanha · Critério de parada · Git | — |

### Bloco A — `frentes/<id>/FRENTE.md` (`contrato.py frente`)

| Campo | Regra mecânica | Código da lacuna |
|---|---|---|
| `FRENTE-ID: <id>` | gramática `^[a-z][a-z0-9]*(-[a-z0-9]+){0,5}$` (é o nome da campanha) e = id da criação | `id_invalido:<id>` |
| `Nome:` | não vazio | `campo_ausente:Nome` |
| `## História` | `Como … quero … para …` — vira o `--problem` da campanha | `historia_sem_como_quero_para` |
| `## Problema / Contexto` · `## Valor de negócio` · `## Personas / Stakeholders` · `## RNFs` · `## Edge cases` · `## Dependências` · `## Escopo IN` · `## Escopo OUT` · `## Métrica de sucesso` | presentes e não vazias | `campo_ausente:<Seção>` |
| `## Critérios de Aceitação` | ≥ 1 item `- **CA-NN — título.** DADO …, QUANDO …, ENTÃO …` | `sem_ca`, `ca_sem_dado_quando_entao:CA-NN` |
| cada CA | linha `  Prova: \`comando\`` — o critério de aceite tem de RODAR | `ca_sem_prova:CA-NN` |
| `## Escopo de escrita` | itens `- \`glob\`` (viram o `--scope`, um por glob); nunca `*`, `**`, `**/*`, `.`, absoluto ou `..` | `escopo_vazio`, `escopo_amplo:<glob>` |
| `## Critério de parada` | com número (vira o `--stop`) | `parada_sem_numero` |
| `## Aceite da Frente` | `### Aceite QA — PENDENTE|ACCEPT` e `### Aceite Review — PENDENTE|APPROVED` | `aceite_sem_qa_review` |

### Bloco B — `frentes/<id>/TASKS/*.md` (`contrato.py task` · `contrato.py completo`)

Nome do arquivo: `{NN}-{TASK|BUG|GAP|DEBT}-{DESCRICAO}.md` (`task_nome_invalido:<arquivo>`).
Cabeçalho (`campo: valor`, antes da primeira seção): `id` (= nome do arquivo sem `.md`), `frente`, `tipo`
(ORACULO|CORRECAO|QA|REVIEW), `grupo` (G1..G3 em CORRECAO; `—` nos demais), `agente`, `CA`, `depends` (`—` ou
`ID (porquê), ID (porquê)`), `status` (PENDENTE|IN_PROGRESS|DONE), `gate` (PENDENTE|PASS|FAIL) e, opcional,
`complexidade` (baixa|normal). Códigos: `task_cabecalho:<id>:<campo>`, `id_difere_do_arquivo`, `tipo_invalido`.

Seções obrigatórias (`task_campo_ausente:<id>:<Seção>`): `## Goal` (o que muda **e o que NÃO fazer**) ·
`## Contexto` (CA + âncora real) · `## Subtasks` (2–5 passos numerados — `subtasks_fora_de_faixa`) ·
`## Invariants` · `## Scope IN / OUT` · `## Arquivos permitidos` (`- \`path\`` exatos; `arquivos_vazio`,
`arquivo_glob`; o próprio arquivo da task é isento das regras de escopo) · `## AC` · `## DoD` · `## Verificação`
(bloco de código com comando concreto — só ls/echo/TBD/true/cat é `verificacao_trivial`) · `## Handoff` (pode nascer
vazio; DONE exige preenchido — o `guard-estado.py` e o `frente.py task marcar` recusam).

Regras do conjunto (`contrato.py completo`):

| Regra | Código | Porquê |
|---|---|---|
| há uma task ORACULO, e ela só escreve em `campanhas/<id>/oraculo/` | `oraculo_ausente`, `oraculo_fora_da_pasta` | quem testa não constrói; o oráculo é de agente separado |
| há QA e REVIEW | `qa_ausente`, `review_ausente` | o ciclo da campanha: oráculo → correção → portão → revisão |
| depends com o porquê, para ids existentes, sem ciclo | `depends_sem_porque`, `depends_inexistente`, `depends_ciclo` | o grafo é entregue pronto, não deduzido; o porquê é o que o briefing mostra |
| CORRECAO tem grupo G1..G3; no máximo 3 grupos | `grupo_ausente`, `grupos_demais` | ≤ 3 frentes de correção disjuntas é a regra do motor (L09/L17) |
| CORRECAO nunca escreve no oráculo | `correcao_escreve_oraculo` | quem corrige não corrige o oráculo |
| CORRECAO só dentro do Escopo de escrita (fnmatch) | `arquivo_fora_do_escopo` | o escopo da campanha é o que o founder aprovou |
| CORRECAO depende (transitivamente) do ORACULO | `correcao_sem_depender_do_oraculo` | o oráculo nasce e congela antes da correção |
| mesmo arquivo em 2 tasks ⇒ uma depende da outra | `mesmo_arquivo_sem_ordem` | serializar é explícito, nunca paralelo implícito |
| mesmo arquivo em CORRECAO de grupos diferentes ⇒ proibido (mesmo ordenadas) | `grupos_colidem` | grupos têm arquivos disjuntos |
| todo CA coberto por ≥ 1 CORRECAO | `ca_orfao` (só na E4: na E3 ainda não há tasks) | CA órfão não tem quem o entregue |

### Complexidade (`contrato.py complexidade <task>`)

`complexidade: baixa` só vale se, sem contar o próprio arquivo da task: ≤ 2 Arquivos permitidos; nenhum em área
**sensível** (`.claude/tools/ac/`, `scripts/harness/`, nome com guard/hook/frase); nenhum **texto de protocolo**
(`.claude/skills/`, `.claude/CLAUDE.md`, `.claude/state/`, `SKILL.md`, `references/`); Verificação concreta. Exit 2
recusa. É o sinal que roteia o executor em haiku (`tech_lead.py modelo`) — declarar baixa sem cumprir só piora o
roteamento (vira sonnet com o motivo "baixa INVÁLIDA").

## O EXEMPLO

Os modelos preenchidos em `modelos/` (`E1.md`, `E2.md`, `E5.md`, `FRENTE.md`, `TASK.md`) são o gabarito de
profundidade — com exemplo da própria skill, não de outro produto. Consulte-os antes de escrever.

## Limite honesto

O script confere presença, forma e coerência (rótulos, CA por CA, grafo, caminhos, grupos). Não confere se o CA é o
certo, se a âncora é a relevante nem se a Verificação prova o CA — isso é a revisão do founder em cada etapa e,
depois, do QA e do revisor.
