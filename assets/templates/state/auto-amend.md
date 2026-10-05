Humano emenda o mandato: ele volta a PROPOSED e exige nova aprovação.

1. Estado atual: `.swarm/bin/cs-auto status`.
2. Extraia de $$ARGUMENTS o motivo e, se houver, o orçamento. Sem motivo → pergunte ao usuário.
3. Confirmado: `.swarm/bin/cs-auto amend --by <nome do humano> --reason "<motivo>" [--orcamento despachos=,tentativas=,replanos=,minutos=]`.
4. Exit 1 = recusa: mostre a mensagem do motor e pare.
5. Mostre a proposta nova por `.swarm/bin/cs-auto status` e peça a aprovação (`/auto-approve`).
