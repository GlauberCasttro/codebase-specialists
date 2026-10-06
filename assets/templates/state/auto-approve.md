Humano aprova a proposta do mandato autônomo, com a SENHA dele. Assina o aceite, a regressão e o ponto seguro.

1. Mostre a proposta por comando: `.swarm/bin/cs-auto status` (objetivo, critérios, nós estimados, orçamento derivado).
2. O orçamento é calculado pelo motor; só o humano o muda, aqui, em: $$ARGUMENTS (`despachos=,tentativas=,replanos=,minutos=`).
3. Você (modelo) NÃO roda a aprovação: o guard bloqueia e o motor exige a senha digitada no terminal do humano, com o
   eco desligado. Peça ao humano que rode, no **terminal** DELE (fora do chat):
   - só na 1ª vez: `.swarm/bin/cs-auto senha definir` (senha forte; o registro fica fora do repositório, em
     `~/.config/codebase-specialists/senha.json`, só com sais e verificador PBKDF2);
   - `.swarm/bin/cs-auto approve --by <nome do humano> [--orcamento <valores>]` — o comando pede a senha no terminal.
   A senha nunca vai por argumento, variável de ambiente nem pipe, e nunca passa pelo chat: não a peça nem a repita.
4. Exit ≠ 0 = recusa (senha errada, sem terminal, sem senha definida, guarda do motor): mostre a mensagem e pare;
   não contorne.
5. A aprovação grava um selo HMAC (mandato, hash do plano, orçamento) no evento `mandato.approve`; o humano pode
   conferir todos os selos quando quiser com `.swarm/bin/cs-auto conferir` (também no terminal dele, com a senha).
6. Depois: `/auto-tick` (o motor pede o plano).
