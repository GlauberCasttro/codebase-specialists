# 02-TASK-MOTOR-SENHA — Senha nos 4 subcomandos do mandato

id: 02-TASK-MOTOR-SENHA
feature: iter19-preauth-senha
tipo: CORRECAO
grupo: G1
agente: corretor (papel; o executor real e o model passado vão para o Handoff)
CA: CA-01, CA-02
depends: 01-TASK-ORACULO (o oráculo congelado é a régua da correção)
status: PENDENTE
gate: PENDENTE
complexidade: normal

<!-- MODELO (gabarito de profundidade). Na feature real, âncoras e linhas vêm da investigação da E2. Outras tasks do
     mesmo conjunto: 01-TASK-ORACULO (tipo ORACULO, grupo —, Arquivos permitidos só em campanhas/<id>/oraculo/),
     03-TASK-QA (tipo QA, depends desta, Arquivos permitidos = o próprio arquivo da task, Verificação com portao.sh),
     04-TASK-REVIEW (tipo REVIEW, depends da QA). -->

## Goal
`amend`, `resolve`, `stop` e `abort` passam a exigir a senha do founder pelo mesmo canal de `approve`
(`human_phrase` + selo). NÃO mudar o formato do ledger, NÃO mudar `approve` e NÃO criar canal novo de senha.

## Contexto
CA-01, CA-02. Âncoras: `scripts/harness/engine/autonomy.py:240` (amend), `:291` (stop); achado F1/F2 da E2: só
`approve` chama o canal humano.

## Subtasks
1. Rodar o oráculo congelado e ver os 4 testes falharem (RED).
2. Chamar o canal humano nos 4 subcomandos, antes de qualquer escrita.
3. Rodar o oráculo e as suítes do pacote nos 2 Pythons (GREEN).

## Invariants
- Recusa não grava nada (estado e ledger intactos, exceto a linha de recusa).
- A senha nunca é impressa. Nenhum `def` existente some.

## Scope IN / OUT
IN: os 4 subcomandos e os testes deles. OUT: `approve`, motor embutido do harness, documentação (outra task).

## Arquivos permitidos
- `scripts/harness/engine/autonomy.py`
- `scripts/harness/tests/test_senha_mandato.py`

## AC
- Os 4 testes do oráculo passam; nenhum teste existente foi enfraquecido.

## DoD
- Régua da task verde (e2e-loop seletivo); diff só nos arquivos permitidos; Handoff preenchido.

## Verificação
```bash
python3 -m unittest discover -s campanhas/iter19-preauth-senha/oraculo
```

## Handoff
