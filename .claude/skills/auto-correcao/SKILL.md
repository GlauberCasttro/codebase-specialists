---
name: auto-correcao
description: >
  Conduz, DENTRO deste projeto, o laço de refinamento medido da codebase-specialists sobre uma frente: oráculo
  confiável escrito por agente separado e congelado, medição do estado atual, diagnóstico com evidência, plano de
  correções em arquivos disjuntos, correção na cópia de trabalho com teste que falha antes e passa depois,
  integração pelo portão (2 Pythons), remedição e decisão parar/continuar/escalar — com o motor EMBUTIDO
  .claude/tools/ac/ac.py, aprovação humana só com a senha do founder no terminal dele e critério de parada fixado
  antes. Use quando o founder pedir "corrige até passar", "refina a skill", "auto corrige", "roda os evals e
  corrige", "itera até o oráculo ficar verde", quando uma frente precisar de mais de uma rodada medida, ou para
  mudar um oráculo congelado (mudança oficial). Não use para bug pontual com teste já falhando (corrija pela frente
  direto) nem para mexer no próprio motor ac/.
disable-model-invocation: true
---

# /auto-correcao — o método da casa sobre uma frente

Toda mudança no produto já é uma **frente = campanha** no motor embutido (`campanhas/<f>/`, estado local em
`campanhas/<f>/.auto-correcao/`). Esta skill é o **método** que roda dentro dela, etapa a etapa. O motor guarda o
estado, confere e recusa; você interpreta e decide; o founder aprova. Método completo, adaptado a este projeto:
`references/metodo.md` desta skill (leia uma vez) e as lições `ac/references/licoes.json5` (no
motor embutido).

**Sempre o caminho LITERAL** `python3 .claude/tools/ac/ac.py --work campanhas/<f> <comando>` — o hook de aprovação
nega variável + palavra de aprovação. Em zsh nunca guarde o comando numa variável. O motor é **cópia** byte a byte
(`ac/ORIGEM.txt`): não se desenvolve aqui.

## As três travas (acima de qualquer pressa)

1. **Sem oráculo confiável, não há laço.** Requisito novo não tem "saída boa conhecida" (L15): o oráculo são testes
   de aceite escritos por um **agente separado** de quem corrige, falhando antes, conferidos pelo founder contra a
   ESPEC. Sistema com estados exige teste de vivacidade + ponta a ponta (L16).
2. **Quem corrige não corrige o oráculo.** Congelado por hash (`oracle freeze` com TODOS os arquivos); mudar é evento
   à parte — **mudança oficial**: patch + PORQUE em `campanhas/<f>/oraculo/mudanca-oficial/`, conferidos pelo
   founder, e só então `oracle change --why --evidence` com todos os arquivos. Nunca para fazer passar.
3. **Portões humanos com a senha do founder.** `gate`, `preauth` e `frase` só no terminal DELE (o hook nega a você).
   Você gera o script (`bash .claude/tools/script-aprovacao.sh <f>` → `local/aprovar-<f>.sh`; recusa sem oráculo
   congelado), avisa e espera. Nunca roda o script, nunca pede a senha no chat, nunca simula. Aprovação simulada, se
   o founder pedir uma, aparece no veredito ("GO (simulado)", L13).

## Onde estou — a etapa pelo motor

```bash
python3 .claude/tools/campanha.py etapa <f> --brief       # etapa corrente, sub-etapas pendentes {id, ctx, do}, próximo
```

As sub-etapas vêm do `ciclo.json5` do motor; `ctx: user` é portão do founder. Sessão caiu? `python3
.claude/tools/sessao.py briefing` e `campanha.py etapa <f>` retomam do disco.

## Ciclo de toda etapa

`python3 .claude/tools/ac/ac.py --work campanhas/<f> load <etapa>` (pacote do disco) → sub-etapas na ordem → `… done
<etapa>` (roda os checks; falha não avança).

`intake → oraculo → base → [rodada n: diagnostico → plano → correcao → integracao → remedicao → decisao]`

| Etapa | O que garantir aqui (comandos em `references/etapas.md`) |
|---|---|
| intake | aberta pelo `/criar-frente`: `init --target . --scope <glob>` (um por glob), problema (a História), **critério de parada em números** (o Critério de parada do FRENTE.md) e orçamento (`set budget …`). Portão `stop` = founder (script de aprovação). |
| oraculo | **agente separado** escreve `campanhas/<f>/oraculo/` (ESPEC.md + testes; caminhos por variável; nada privado). Calibre: vazio ≈ 0 medido; bom = conferência do founder (modo requisito, L15). `oracle freeze --file …` com TODOS os arquivos. Ver `references/oraculo.md`. |
| base | mede o produto atual com o oráculo congelado (`run record --round 0 --config sistema …`); baseline sem a mudança ou `run waive --why`. |
| diagnostico | `DEFEITOS.json5` (formato em `ac/references/formatos.json5`): evidência literal, P0–P3, **classe** sistema/oráculo/ambiente/executor. Só `sistema` vira correção (L08). |
| plano | `PLANO.json5`: decisões (produto ⇒ portão `plan:<id>` do founder), **contrato de nomes**, frentes com escrita disjunta que não tocam o oráculo (≤ 3 grupos — os `grupo` G1..G3 das tasks CORRECAO). `plan check` + `overlap --other` contra outra campanha viva. |
| correcao | corretor(es) só na cópia de trabalho (`bash .claude/tools/copia.sh <f>`), prompt em `references/prompts.md`; cada defeito com teste que falha antes e passa depois; despacho, modelo e custo pelo `/tech-lead`. `front report <nome> --file …`. |
| integracao | **você** roda o portão: `bash .claude/tools/portao.sh <f> --oraculo campanhas/<f>/oraculo:<mod> --lista …` (cópia limpa, 2 Pythons, suíte harness-dev, oráculos, nenhum def removido; background) e o `/e2e-loop`. VERDE ⇒ `set integration.tests_green true`; `oracle verify`; commit só com o `preauth commit` do founder, pelo `/fechar-frente`. |
| remedicao | mesmo oráculo congelado, produto congelado durante a medição; `run record … --decision GO|NO-GO` posterior ao `done correcao` (AC-09: no mesmo segundo não conta — repita). |
| decisao | `results compare` × critério: **parar** (cumprido → `/fechar-frente`), **continuar** (orçamento + progresso medido → `round new`), **escalar** (2 rodadas sem progresso ou orçamento esgotado → devolva ao founder). Antes de `done decisao` o founder roda `frase conferir` no terminal dele. Nunca "mais uma" às cegas. |

## Os três atalhos mecânicos (`campanha.py`)

```bash
python3 .claude/tools/campanha.py etapa <f> --json
python3 .claude/tools/campanha.py mudanca-oficial <f> --porque "<o erro do oráculo>" --evidencia "<conferência>" --dry-run
python3 .claude/tools/campanha.py fechar <f> --relatorio <rel.md> --config sistema --decisao GO --dry-run
```

- `mudanca-oficial` recusa sem `*.patch` e `PORQUE*.md` em `campanhas/<f>/oraculo/mudanca-oficial/`, e monta o
  `oracle change` com **todos** os `--file` congelados (passar só um substituiria a lista inteira — lição local).
- `fechar` segue o ciclo: `front report` → `done correcao` → `set integration.tests_green true` → `done integracao`
  → `run record` → `done remedicao` → `set decision`/`set report` → **linha do FOUNDER** (`frase conferir`, no
  terminal dele) → com `--concluir`, `done decisao`. Nunca roda gate, preauth nem frase.

## O que é seu (julgamento) e o que é do script

- **Script:** estado, ordem das etapas, checks, hash do oráculo, disjunção de escopos (`plan check`, `overlap`),
  portão (suítes, oráculos, defs), carimbo e régua (`sessao.py`, `e2e.py`), commit só do que o portão testou.
- **Você:** classificar defeitos, escrever o contrato de nomes, ler o relatório do corretor contra o diff, dizer o
  que o oráculo pode estar favorecendo (mesmo contra o produto), decidir parar/continuar/escalar e explicar.
- **Founder:** critério de parada, decisões de produto, aprovações (senha), conferência, push, publicar o pacote.

## Relatório ao founder (a cada rodada, curto)

Decisão numa linha; tabela qualidade × estrutura × custo (baseline ao lado); o que o oráculo pode estar favorecendo;
defeitos da próxima rodada por prioridade; o que precisa de decisão dele. Números, não adjetivos. Depois,
`/salvar-sessao`.

## Referências (sob demanda)

- `references/metodo.md` — o método adaptado (frente = campanha, papéis, as 9 etapas, travas, lições aplicadas)
- `references/etapas.md` — cada etapa com os comandos literais deste projeto
- `references/oraculo.md` — modo requisito, calibração, freeze, mudança oficial
- `references/prompts.md` — prompts de corretor, executor de medição e verificador
- `references/limites.md` — o que o motor não faz e defeitos conhecidos
- motor: `ac/references/{ciclo,licoes,formatos,prompts}.json5` (fonte única; não editar: é cópia — `ac/ORIGEM.txt`)
