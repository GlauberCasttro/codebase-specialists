# PORQUE — mudança oficial 01 do oráculo iter23 (decisão do founder, 2026-10-13, "ok")

`item()` lia o arquivo do item com chaves em português (`motivo`, `reproducao`, `como`, `quero`, `para`, `teste`),
mas o contrato de disco desde a 0.11.0 (B-14; `scripts/harness/engine/hcore.py:276-278`, ITEM_SCHEMA) grava essas
chaves em inglês (`reason`, `failing_test`, `as_a`, `i_want`, `so_that`, `proving_test`). O `amend` grava certo e o
`start` aceita, mas `test_ca02_amend_campos_do_dor_e_start_aceita` nunca via o campo (falso vermelho, defeito do
oráculo, não do produto). Alternativa rejeitada: gravar em português (quebra o B-14 e o oráculo da iter19).
Efeito: a leitura traduz en→pt sem sobrescrever chave pt existente; nenhuma asserção muda de alvo; controles
continuam valendo. Base do HEAD 21c6164 segue 16/41 (as D seguem falhando: o HEAD não tem amend desses campos).
