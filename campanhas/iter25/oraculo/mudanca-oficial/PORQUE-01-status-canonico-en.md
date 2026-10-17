# PORQUE — mudança oficial 01 do oráculo iter25: `status` gravado em código canônico inglês

## Decisão

D-37 do founder (2026-10-14): o `status` GRAVADO no arquivo de cada item da árvore é o valor CANÔNICO em inglês;
a exibição (`tree.status_of`, `board`/`next`/`show`) continua em português. CA-01 e CA-03 da FEATURE.md já citam a D-37.

Mapa (exibição pt → código gravado), definido NO ORÁCULO (`CANON`/`CANON_MAP` em test_iter25.py), sem depender de
função nova do produto (o nome da função canônica é decisão do corretor):

| exibição | gravado |
|---|---|
| "a fazer" | `TODO` |
| "backlog" | `BACKLOG` |
| "ativo" | `ACTIVE` |
| "fechada"/"fechado" | `DONE` |
| "descartada"/"descartado" | `DROPPED` |
| `<M2>/<despacho>` (ex. `BRIEFED/DISPATCHED`) | igual |

Valor de exibição desconhecido ⇒ `CANON` devolve `None` ⇒ a comparação falha (nunca passa por omissão).

## O que muda (patch `01-status-canonico-en.patch`: test_iter25.py e ESPEC.md)

- `mismatches` (CA-01, CA-03, CA-05) compara o arquivo com `CANON(derivado)` em vez do derivado pt.
- CA-01 `literais_no_arquivo`: `ACTIVE`/`TODO`/`BACKLOG`.
- CA-01 novo R `test_ca01_controle_exibicao_continua_em_portugues`: `board` mostra a task "a fazer" e o backlog
  "backlog", sem `[TODO]`; `show` da task mostra "a fazer" — prova que só o dado gravado mudou.
- CA-02 (2 D): arquivo == `CANON(derivado)` a cada passo (o `<M2>/<despacho>` fica igual).
- CA-03 (4 D): arquivo `DROPPED`/`DONE`, derivado continua "descartada"/"descartado"/"fechada"/"fechado".
- CA-04 D: edição à mão agora é código VÁLIDO e errado (`TODO` → `DONE`); a saída do `validate --strict` tem de citar
  o ID e o valor certo `TODO`.
- CA-04 novo D `test_ca04_status_fora_do_vocabulario_acusado`: "a fazer" gravado no arquivo (fora do vocabulário)
  ⇒ `validate --strict` ≠ 0, citando o ID e `TODO`.
- CA-05: só a mensagem de `mismatches` (via CANON). medir.py não mudou.

## Por que não enfraquece

- Toda asserção antiga continua, com o valor esperado trocado 1:1 pelo mapa da decisão; nenhuma foi removida ou
  afrouxada. O derivado pt continua exigido literalmente em CA-01 (controle) e CA-03 (tupla arquivo/derivado).
- CA-04 fica MAIS estrito: antes "aceita" (inválido em qualquer vocabulário) bastava; agora um código válido porém
  errado tem de ser acusado, e o valor fora do vocabulário vira um D próprio.
- O novo R de exibição fecha a brecha "trocar a exibição para inglês" (mudaria tudo sem cumprir a D-37).
- `CANON` é do oráculo: o corretor não pode passar ajustando uma função do produto que o oráculo importe.

## Base (HEAD 3eed3b4, VERSION 0.13.0; python3 3.13.3 e /usr/bin/python3 3.9.6 idênticos)

- Antes: 19 testes, 7/19 passam; D 0/12 (FAIL por asserção), R 7/7.
- Depois: 21 testes, 8/21 passam; D 0/13 (FAIL por asserção, 0 ERROR), R 8/8.
  Placar: CA-01 2/4, CA-02 1/3, CA-03 0/4, CA-04 1/3, CA-05 4/7. Detalhe em `../base.txt`.
