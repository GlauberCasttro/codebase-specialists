# iter19-preauth-senha — Senha nos comandos que mudam o mandato

FRENTE-ID: iter19-preauth-senha
Nome: Senha nos comandos que mudam o mandato

## História
Como founder, quero que encerrar, emendar ou abortar um mandato exija a minha senha, para que nenhum agente mude a
autonomia de um alvo sem mim.

## Problema / Contexto
Só `approve` passa pelo canal humano (`scripts/harness/engine/autonomy.py:212`); `amend` (`:240`), `resolve`
(`:268`), `stop` (`:291`) e `abort` (`:318`) gravam direto (E2: 4 de 9 subcomandos mudam o mandato sem senha).

## Valor de negócio
O portão humano do mandato vale do começo ao fim, não só na abertura — é a promessa do harness gerado.

## Personas / Stakeholders
- founder (dono da senha; único que muda o mandato)
- agente do alvo (passa a receber recusa auditável)

## Critérios de Aceitação
- **CA-01 — amend exige senha.** DADO um mandato ativo, QUANDO `amend` roda sem o canal humano, ENTÃO recusa e não
  grava nada além da linha de recusa no ledger.
  Prova: `python3 -m unittest test_preauth_senha.TestAmend`
- **CA-02 — stop, resolve e abort exigem senha.** DADO um mandato ativo, QUANDO cada um roda sem o canal humano,
  ENTÃO recusa como no CA-01.
  Prova: `python3 -m unittest test_preauth_senha.TestDemais`

## RNFs
- RNF-01: Python 3.9+ stdlib; verde em `python3` e `/usr/bin/python3` (o portão roda os dois).
- RNF-02: a senha nunca é impressa nem gravada.

## Edge cases
- tty ausente: recusa (não cai para pergunta no chat).
- senha errada 3 vezes: recusa sem gravar.

## Dependências
- nenhuma frente bloqueante (a iter14 já entregou o canal humano).

## Escopo IN
- os 4 subcomandos do mandato e os testes deles.

## Escopo OUT
- `approve` (iter14), o formato do ledger, o motor embutido do harness de desenvolvimento.

## Escopo de escrita
- `scripts/harness/engine/autonomy.py`
- `scripts/harness/tests/test_senha_mandato.py`

## Critério de parada
oráculo 4/4 verde em python3 e /usr/bin/python3; suítes do produto verdes; 0 `def` removido.

## Métrica de sucesso
4 de 4 subcomandos que mudam o mandato recusam sem a senha (hoje: 0 de 4).

## Aceite da Frente
### Aceite QA — PENDENTE
### Aceite Review — PENDENTE
