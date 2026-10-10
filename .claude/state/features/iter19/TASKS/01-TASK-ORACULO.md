# 01-TASK-ORACULO — Oráculo da iter19 (CA-01..CA-06), escrito por agente separado

id: 01-TASK-ORACULO
feature: iter19
tipo: ORACULO
grupo: —
agente: oraculista (agente separado; nunca o corretor)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06
depends: —
status: DONE
gate: PASS

## Goal
Escrever o oráculo em `campanhas/iter19/oraculo/`: ESPEC.md (CA → testes, critérios), `test_iter19.py` com as classes
`TestCA01`..`TestCA06` (as Provas do FEATURE.md), `medir.py` (placar D/R por CA) e `base.txt` (medição no HEAD nos 2
Pythons). Testes de defeito FALHAM hoje; testes de não-regressão PASSAM hoje. NÃO tocar produto, NÃO rodar git add.

## Contexto
CA-01..CA-06 do FEATURE.md; âncoras da E2: j5.py:124-141 (ordem/indent), cmds.py:903-909 e tree.py:683-686 (amend),
state.py:437 (sem show), hcore.py:325-337 (cadeia), upgrade/core.py:52, 820-845 (upgrade). Fixture: alvo realista
gerado (≥ 30 eventos, itens em backlog/state/archive), skill por `$CS_SKILL_DIR` como nos oráculos iter18/iter20.

## Subtasks
1. Ler FEATURE.md, a E2 (`propostas/E2.md`) e os oráculos iter18/iter20 (mecanismo `$CS_SKILL_DIR`, fixture).
2. Escrever ESPEC.md e `test_iter19.py` (TestCA01..TestCA06), comportamento e não formato interno.
3. Escrever `medir.py`; medir no HEAD nos 2 Pythons e gravar `base.txt`.
4. Rodar o guard de privacidade sobre a pasta (vazio).

## Invariants
- Python 3.9 compatível; só stdlib; caminhos por variável de ambiente; pessoa = "Ana"; sem nomes privados.
- Cada teste D falha pelo motivo do CA, não por fixture quebrada.

## Scope IN / OUT
IN: `campanhas/iter19/oraculo/`. OUT: produto, estado, outras campanhas.

## Arquivos permitidos
- `campanhas/iter19/oraculo/ESPEC.md`
- `campanhas/iter19/oraculo/test_iter19.py`
- `campanhas/iter19/oraculo/medir.py`
- `campanhas/iter19/oraculo/base.txt`

## AC
- Os 6 CAs têm classe de teste; base.txt mostra D falhando e R passando, igual nos 2 Pythons.

## DoD
- Tech-lead confere e congela com `ac.py oracle freeze` (todos os arquivos) antes de qualquer correção.

## Verificação
```bash
cd campanhas/iter19/oraculo && python3 medir.py && /usr/bin/python3 medir.py
```

## Handoff
- Executor: rh-oraculista-01-TASK-ORACULO-1 (general-purpose, opus), ficha conferida (`rh.py conferir` OK).
- Entregue: ESPEC.md, test_iter19.py (39 testes, TestCA01..TestCA06), medir.py, base.txt; alvo realista com 43 eventos.
- Medido pelo tech-lead no HEAD 97a1718: 11/39 (D 0/28, R 11/11), idêntico em python3 3.13 e /usr/bin/python3 3.9.
- Congelado: `oracle freeze` 1083cc4a985e. Lacunas declaradas: board plano pré-0.7.0, mistura .json5/.json só
  indireta, chave desconhecida no fim, mandato selado (exige senha).
