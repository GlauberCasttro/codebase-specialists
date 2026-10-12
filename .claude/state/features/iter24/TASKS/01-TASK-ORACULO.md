# 01-TASK-ORACULO — Oráculo da iter24 (CA-01..CA-07), escrito por agente separado

id: 01-TASK-ORACULO
feature: iter24
tipo: ORACULO
grupo: —
agente: oraculista (rh; agente separado que nunca vê a cópia do corretor)
CA: CA-01, CA-02, CA-03, CA-04, CA-05, CA-06, CA-07
depends: —
status: DONE
gate: PASS

## Goal
ESPEC.md + test_iter24.py (+ medir.py, base.txt) em `campanhas/iter24/oraculo/` que FALHAM no HEAD (0.12.1 depois da
iter22) e passam com a entrega, exercitando o guard INSTALADO num alvo pelo hook (pre-bash/pre-write) com payloads do
agente principal e de subagente com delegação ATIVA, usando os mesmos payloads da auditoria. NÃO tocar produto.

## Contexto
CA-01..CA-07. Âncoras da E2: bashscan.py:202, :208-215, :299, :18, :28, :325; guard.py:177-183, :383-388;
hcore.py:830-831; auto.py:3045.

## Subtasks
1. Fixture de alvo instalado com hook, uma task delegada ativa ao subagente e arquivos protegidos.
2. Um teste por porta (CA-01..CA-06), com CONTROLE do caminho legítimo (bash scripts/build.sh, leitura de git, script
   de arquivo) que tem de seguir passando.
3. CA-07: upgrade de um alvo 0.12.1 (skill antiga por `git archive`), versão sempre relativa (≥).
4. Calibrar: base no HEAD falha por asserção; mutação para ao menos 2 portas.

## Invariants
- Oráculo só em `campanhas/iter24/oraculo/`.

## Scope IN / OUT
IN: oráculo. OUT: produto.

## Arquivos permitidos
- `campanhas/iter24/oraculo/ESPEC.md`
- `campanhas/iter24/oraculo/test_iter24.py`
- `campanhas/iter24/oraculo/medir.py`
- `campanhas/iter24/oraculo/base.txt`

## AC
- 7 CAs com teste; base no HEAD medida e registrada em base.txt.

## DoD
- Oráculo congelado (`oracle freeze` com todos os arquivos); Handoff preenchido.

## Verificação
```bash
cd campanhas/iter24/oraculo && python3 medir.py
```

## Handoff
- Executor: rh-oraculista-01-TASK-ORACULO-1 (general-purpose, opus), agente separado (não leu local/work).
- Entregue: ESPEC.md, test_iter24.py (22 testes: 13 D, 9 R de controle do caminho legítimo), medir.py, base.txt.
  Fixture: alvo instalado, hook real pre-bash/pre-write, subagente com delegação DISPATCHED (US avulsa de dev-billing).
- Ciclo 2 (pedido do tech-lead): a fixture não resolvia o temporário; com TMPDIR /var/folders (symlink) a base dava
  11/22 com D passando pelo motivo errado. Corrigido com realpath; defeito de produto registrado como B-53.
- Medido pelo tech-lead no HEAD da30e17: 9/22 (D 0/13, R 9/9) em python3 3.13 e /usr/bin/python3 3.9 (oraculista:
  idem com TMPDIR padrão e com o scratchpad). Calibração: mutação mínima ⇒ 12/22, R verdes; a correção parcial NÃO
  satisfaz o D do principal no CA-06. Congelado: `oracle freeze` 37f3042c76ae (4 arquivos).
- Lacunas declaradas: `dotnet -o` sem teste; MultiEdit não coberto; CA-07 confere só a porta do CA-01 depois do
  upgrade; os D afirmam só o exit 2 (os R protegem contra "bloquear tudo").
