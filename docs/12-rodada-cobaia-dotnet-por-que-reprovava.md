# Rodada cobaia .NET (2026-10-05) — por que o time não "especializava"

Registro de por que o `/codebase-specialists` precisou de várias sessões para aprovar os agentes do repositório
cobaia .NET (C#/.NET, Roslyn Source Generator), e das correções feitas na skill por causa disso.

## Resumo

Os agentes **sabiam** o código. Quem reprovava era a **prova**: as sondas cobravam convenções que a pergunta não
dizia, e o pré-check mecânico media o número da linha em vez do conteúdo. Quando o critério de uma sonda foi
escrito no cartão (um fato e uma regra), os três agentes reprovados passaram de uma vez:

| agente | ciclo 1 (território / cross) | ciclo 2 (território / cross) |
|---|---|---|
| dev-core-runtime | 0,78 / 0,86 — FAIL | 1,0 / 1,0 — PASS |
| dev-roslyn | 0,78 / 0,50 — FAIL | 1,0 / 0,71 — PASS |
| security | 0,75 / 0,50 — FAIL | 1,0 / 1,0 — PASS |

Os três ficaram com zero alucinação. Resultado final: 8/8 `especialista`, G1–G16 verdes, `verify` GO.

## De onde vinham as falhas

As falhas do ciclo 1 dos três agentes somam 16 sondas. Classificadas pela causa:

| causa | sondas | era falta de conhecimento? |
|---|---|---|
| A. `dependency`: o critério de "importa" não estava escrito na pergunta | 8 | não |
| B. `why`: o pré-check exigia ±3 linhas do título/Status/Decisão do ADR | 5 | não (o painel aprovou o mérito no ciclo 2) |
| C. `why` gerada de cabeçalho genérico de log ("Por que O que foi feito?") | 2 | não (não existe resposta certa) |
| D. `prohibition`: regra do `.editorconfig` na seção `[*]` | 1 | sim |

**15 das 16 falhas vinham do desenho da sonda.** No ciclo 2 sobraram 2 falhas, ambas de gabarito errado (causa E).

### A. "Importa" sem critério na pergunta

- **O que acontecia:** a pergunta dizia "Quais arquivos fora de `src/SwiftMap/**` importam
  `src/SwiftMap/Configuration/SwiftMapOptions.cs`?".
- **O que o gabarito considerava:** o grafo de imports do L1, ou seja, os arquivos com
  `using SwiftMap.Configuration;`. É um critério em nível de **namespace**.
- **O que o agente fazia:** respondia como um dev C# responderia, buscando o **uso do tipo**
  (`grep -w SwiftMapOptions`), e incluía exemplos de `samples/`.
- **Resultado:** NENHUM ou listas parciais, com pontuação zero.
- **Por que é defeito da prova:** as duas leituras são legítimas, e a pergunta não dizia qual valia. Só passou
  quando o dono do repositório ditou a regra e ela foi para o cartão.
- **Correção:** `scripts/probes/generate.py` agora acrescenta o critério à pergunta (`IMPORT_CRITERION`, por
  extensão). Para `.cs`: "o arquivo tem `using <namespace declarado em X>;` no topo, antes da 1ª declaração de
  tipo — nível namespace, mesmo sem usar o símbolo; menção em string/comentário não conta". As outras linguagens
  recebem o critério genérico de import em nível de arquivo.

### B. `why` corrigida pela linha, não pelo conteúdo

- **O que acontecia:** sem `key_terms`, o pré-check só aceitava citação a ±3 linhas das `sources` do gabarito,
  que eram o título, o Status e o início da Decisão do ADR.
- **O que o agente fazia:** explicava o motivo certo citando o parágrafo de Contexto, por exemplo
  `ADR-002…md:15`. Levava "fonte não citada" e a sonda nem chegava ao painel.
- **Por que é defeito da prova:** o pré-check só existe para garantir que a resposta cita o documento certo. Quem
  decide o mérito é o painel de 3 juízes, e a linha exata não mede compreensão.
- **Correção:** `scripts/probes/exam.py` (`Checker.score_one`, tipo `why`): sem `key_terms`, basta citar
  **qualquer linha** do documento-fonte. A sonda continua `panel_pending`, e o painel julga o mérito.

### C. `why` gerada de cabeçalho genérico

- **O que acontecia:** o gerador criou "Por que O que foi feito?" a partir de um log de sessão. Esse cabeçalho se
  repete em dezenas de logs de `agents/Mapper/**`, e o gabarito apontava um deles arbitrariamente.
- **O que o agente fazia:** os dois examinados responderam `nao_sei`, que era a resposta honesta, e foram
  reprovados.
- **Correção:** `scripts/probes/generate.py` descarta tópicos `why` que estão em `GENERIC_TOPICS` ("o que foi
  feito", "resumo", "contexto", "próximos passos", "summary", "overview"…, normalizados sem acento e caixa).
  Descarta também tópicos que se repetem em 3 ou mais fatos de rationale: um cabeçalho repetido não tem *um*
  porquê.

### D. Falta de conhecimento real

- **O caso:** a regra do `.editorconfig` que vale para `**` fica na seção `[*]` no topo do arquivo. O agente
  security citou a seção `[*.{xml,csproj}]`.
- **Como foi resolvido:** pelo refino normal, com a regra no cartão. Nenhuma mudança na skill.

### E. `using` dentro de string literal contado como import (ciclo 2)

- **O que acontecia:** testes do source generator embutem código-fonte C# em raw strings. A regex `CS_USING`
  (`^\s*using …;`) aceitava linhas indentadas, então um `using SwiftMap.Configuration;` **dentro da string**
  virava import do arquivo de teste.
- **Resultado:** o gabarito de 2 sondas do dev-roslyn listava `MergeImmutableDestTests.cs` e
  `NestedSubMapperCtorTests.cs`, que não têm esse `using` no cabeçalho. O agente respondeu certo e perdeu as duas.
- **Correção:** `scripts/scan/l1_graph.py` (`CS_FIRST_TYPE`): em C#, só contam os `using` **antes da primeira
  declaração de tipo**. Em C#, todo `using` de arquivo vem antes de qualquer tipo, seja na compilation unit ou
  dentro de um bloco `namespace`; depois disso, um "using X;" só aparece dentro de uma string.

## Defeitos de processo que custaram sessões

| defeito | efeito | correção |
|---|---|---|
| `probes check` apagava `<exam>/repo` logo após pontuar | o painel why precisa ler o repo nessa cópia, que tinha de ser recriada à mão | `scripts/probes/exam.py`: com `panel_pending`, a cópia **fica**; ela sai no `check` seguinte, depois de o painel registrar |
| motivo de `stage skip` desatualizado | o relatório dizia "refino encerrado" depois de um 2º ciclo que aprovou todos | sem mudança de código: rodar `cs.py stage skip <id> --reason "…"` de novo sobrescreve o motivo. Feito no cobaia .NET |
| no `--fast`, reprovado vira `nao-especialista` sem diagnóstico | o ciclo 1 terminou com `allow-non-specialist` sem isolar a causa comum | só procedimento: antes de aceitar `nao-especialista`, agrupe as falhas por **tipo de sonda**. Se um tipo domina vários agentes, suspeite do gabarito antes do cartão |

As sessões anteriores também corrigiram bugs que zeravam ou distorciam o grafo: BOM UTF-8 em 71 arquivos `.cs`,
`PATH_RE` com `.editorconfig`, pergunta de history ambígua, e `card revise` recusando refino no `--fast`.

## Custo

- **Cada subagente custou ~40k tokens antes de trabalhar.** O baseline, que só lê um arquivo e responde sem
  ferramentas, gastou ~46k. Esse custo fixo vem do contexto carregado na máquina: ~400 skills, instruções de
  servidores MCP e o CLAUDE.md global.
- **Por que isso pesa:** o fluxo exige subagentes isolados (redator, baseline, examinado, juiz). Com 9 a 12
  subagentes por ciclo, o custo fixo domina o gasto.
- **O que reduz:** desligar MCPs e plugins sem uso antes de rodar a skill. O painel why também pode rodar com
  3 juízes cobrindo vários agentes num lote só. A maioria de 3 continua valendo por sonda, e o custo cai cerca de 3×.

## Verificação

| suíte | resultado |
|---|---|
| probes | 78 testes OK (6 novos em `scripts/probes/tests/test_iter6_cobaia_dotnet.py`) |
| scan | 90 OK |
| sanitize | 8 OK |
| stage | 51 OK |
| team | 61 OK |
| verify | 13 OK |
| doctests | 19 OK |

Rode o `verify` com `python3 -m unittest discover -s verify/tests` (sem `-t`), porque os testes importam
`helpers` do próprio diretório.

**Teste ajustado:** `sanitize/tests/test_sanitize.py` → `ExamCopyRemovedAfterCheck`. O novo contrato é: a cópia
fica enquanto houver painel pendente, e sai no `check` depois que o painel registra os vereditos.

## Pendências (não feitas nesta rodada)

- **`global using` é ignorado pelo scanner C#.** A regex exige a linha começando por `using`. Um repositório que
  centraliza imports em `GlobalUsings.cs` teria o grafo subestimado. Isso vem de antes desta rodada.
- **Para C#, "importa" continua em nível namespace.** Gerar o gabarito pelo uso do tipo seria mais fiel ao que
  um dev C# entende por dependência, mas exige análise de símbolos. Por ora, o critério fica explícito na
  pergunta.
- **Os bancos de sondas já emitidos não mudam.** A pergunta com critério vale para sondas geradas daqui em diante
  (`probes generate`, `--rotate`).
