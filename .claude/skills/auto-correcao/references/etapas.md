# Etapas — comandos literais deste projeto

`AC` abaixo é só abreviação de leitura: **digite sempre** `python3 .claude/tools/ac/ac.py --work campanhas/<feature>`
(o hook de aprovação nega variável + palavra de aprovação; zsh não faz word-split). Ordem fixa em
`.claude/tools/ac/references/ciclo.json5`; `load` recusa etapa anterior aberta; `done` roda os checks.
`ctx`: main = você · sub = subagente (protege a janela) · user = founder no terminal dele.

## intake (rodada 0) — via `/criar-feature`

```
AC init --target . --scope 'scripts/x/*.py' --scope 'scripts/x/tests/*.py' \
        --problem "<problema>" --stop "<oráculo N/N; suítes verdes em python3 e /usr/bin/python3; nenhum def removido>" \
        --max-rounds 2 --max-hours 6 --max-parallel 3
AC overlap --other campanhas/<outra-ativa>           # colisão = exit 1: serialize
bash .claude/tools/script-aprovacao.sh <feature> --criterio '<texto>' --oraculo '<texto>'   # GERA; o founder roda
AC done intake                                        # depois que o founder avisar
```

`intake.3` (user) só passa com o `gate stop` aprovado pelo founder. Um `--scope` por glob (vírgula é recusada).
`--max-rounds` não conta a rodada 0.

## oraculo (rodada 0)

1. Despache o AUTOR DO ORÁCULO (agente separado) com `prompts.md` → "autor do oráculo". Ele escreve
   `campanhas/<feature>/oraculo/{ESPEC.md,test_<feature>.py,base.txt}`.
2. `AC set oracle.command "cd campanhas/<feature>/oraculo && python3 -m unittest test_<feature>"`
3. Calibração em modo requisito (ver `oraculo.md`): `base.txt` = rodada no produto atual (0% dos testes do
   requisito passam); conferência do founder dos testes × ESPEC (`gate oracle:requisito`, no script dele).
4. `AC set oracle.split '{"quality":"...","structure":"..."}'`
5. `AC oracle freeze --file campanhas/<feature>/oraculo/ESPEC.md --file campanhas/<feature>/oraculo/test_<feature>.py`
   (TODOS os arquivos, um `--file` cada) → `AC done oraculo`

## base (rodada 0)

```
AC run record --round 0 --config sistema --alvo projeto --grading <grading.json> --minutes N --tokens N
AC run waive --round 0 --config baseline --why "<por que não há baseline sem a mudança>"
AC done base
AC round new
```

## diagnostico → plano (rodada n)

```
AC load diagnostico     # escreva .auto-correcao/rounds/<n>/DEFEITOS.json5 (formatos.json5)
AC defects check
AC done diagnostico
AC load plano           # PLANO.json5: decisoes, contrato, frentes {nome, escreve, defeitos, criterio}  (chave do motor ac/, não renomeada — compat)
AC plan check           # disjunção + nenhuma feature escreve no oráculo
AC plan gates           # decisão de produto ⇒ portão plan:<id> do founder
AC done plano
```

## correcao

```
bash .claude/tools/copia.sh <feature>          # local/work/<feature>/codebase-specialists
# despacho pelo /tech-lead (prompt "corretor" de prompts.md); ≤ 5 agentes; cada um só no seu `escreve`
AC front report <nome> --file local/work/<feature>/relatorio-<nome>.md
AC done correcao
```

## integracao

```
bash .claude/tools/portao.sh <feature> --oraculo campanhas/<feature>/oraculo:test_<feature> -- <arquivos>   # background
tail -3 local/portao-<feature>/portao.out      # RESULTADO: VERDE + FIM
AC set integration.tests_green true           # só com o portão VERDE nos 2 Pythons
AC oracle verify
AC done integracao                            # integracao.3 = preauth commit do founder
```

Commit pelo `/fechar-feature` (portar → conferir-commit → commit só da feature). Houve merge no `portar.sh` ⇒ rode
o portão de novo com `--src .`.

## remedicao

```
AC run record --config sistema --alvo projeto --grading <grading.json> --decision GO --minutes N --tokens N
AC done remedicao
```

O produto fica congelado enquanto mede (L04). AC-09: registro no mesmo segundo do `done correcao` é recusado —
registre de novo.

## decisao

```
AC results compare
AC set decision "<parar|continuar|escalar — motivo em números>"
AC set report "<relatório curto ou caminho>"
# o founder roda no terminal dele: frase conferir
AC done decisao
AC round new                                   # só se continuar
```

Parar ⇒ `/fechar-feature` (aceite, archive, LAST_DELIVERY) e `/install`. Escalar ⇒ documente os limites e
devolva ao founder. Depois de qualquer saída: `/salvar-sessao`.
