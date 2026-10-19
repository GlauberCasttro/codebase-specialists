# 01-TASK-ORACULO — Oráculo da iter27 (CA-01..CA-09), escrito por agente separado

id: 01-TASK-ORACULO
feature: iter27
tipo: ORACULO
grupo: —
agente: oraculista (persona via /rh; nunca o corretor)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07, CA-08, CA-09
depends: —
status: PENDENTE
gate: PENDENTE

## Goal
Escrever a ESPEC e os testes de `campanhas/iter27/oraculo/` que provam CA-01..CA-09 contra a CLI REAL (subprocess nos
bins do alvo e no `cs.py`), e que FALHAM no HEAD 9e908e0 pelos motivos certos. NÃO tocar em código de produto, NÃO
ler a solução de ninguém (não há), NÃO enfraquecer o que os oráculos antigos afirmam, NÃO exigir nomes que a
FEATURE.md não fixou (os nomes en estão nos CA-01/02/04).

## Contexto
CA-01..CA-09 da FEATURE.md. Âncoras da E2: flags em `scripts/harness/engine/state.py:226-278`, `auto.py:3150-3210`,
`router.py:279,282`, `--allow-outside` em `scripts/cs.py:88`, `scripts/upgrade/cli.py:31`, `scripts/harness/cli.py:98`,
`scripts/emit/cli.py:246`; forma interna em `hcore.py:254-310`; dry-run em `tree.py:263-264`; aviso em
`state.py:840,844`; plano do upgrade em `scripts/upgrade/core.py:64`; doctest `test_commands_parse.py:78-83`.
Padrão de fixture: o da iter26 (`campanhas/iter26/oraculo/test_iter26.py`, alvo criado pela skill sob teste; pessoa
"Ana"). CA-08: medir a forma interna via `hcore.load_board` do motor instalado no alvo (chaves pt proibidas = as de
`ITEM_SCHEMA`/`SESSION_SCHEMA` da 0.14.0, listadas literalmente no teste, não importadas). CA-09: alvo na 0.14.0
criado pelo `git worktree`/cópia do HEAD 9e908e0, com um épico `kind: "epico"` no disco.

## Subtasks
1. ESPEC.md: CA → classe de teste (TestCA01..TestCA09) → o que cada teste afirma e por que falha no HEAD.
2. test_iter27.py: os testes, stdlib, nos 2 Pythons; alvos em diretório temporário; nenhum acesso à rede.
3. Rodar contra o HEAD nos 2 Pythons e gravar `base.txt` (todos os CA vermelhos pelo motivo descrito na ESPEC).
4. Entregar a lista de arquivos ao tech-lead para o `oracle freeze` (todos).

## Invariants
- Quem testa não constrói: só escreve em `campanhas/iter27/oraculo/`.
- Nenhum teste depende de ordem de execução nem de relógio; nada fora do temporário é escrito.

## Scope IN / OUT
IN: ESPEC, testes e base do oráculo da iter27. OUT: código do produto, oráculos de outras campanhas, o harness.

## Arquivos permitidos
- `campanhas/iter27/oraculo/ESPEC.md`
- `campanhas/iter27/oraculo/test_iter27.py`
- `campanhas/iter27/oraculo/base.txt`

## AC
- 9 classes TestCA01..TestCA09, cada uma com ≥ 1 teste; todas vermelhas no HEAD pelo motivo da ESPEC; nenhuma
  vermelha por erro de fixture.

## DoD
- base.txt com a saída nos 2 Pythons; o tech-lead congela com `oracle freeze` passando os 3 arquivos.

## Verificação
```bash
cd campanhas/iter27/oraculo && python3 -m unittest -v test_iter27 2>&1 | tail -40; /usr/bin/python3 -m unittest test_iter27 2>&1 | tail -5
```

## Handoff
