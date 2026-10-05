Salve a sessão chamando só o script; não leia nem edite arquivos de estado.

1. Escreva 1 linha para cada campo a partir desta conversa: feito, próximo passo, bloqueio (se houver).
2. Rode exatamente: `.swarm/bin/cs-session save --did "<feito>" --next "<próximo>" [--blocked "<bloqueio>"] $$ARGUMENTS`
3. Mostre a saída do script e pare. O script coleta board, eventos, git, gates e memória sozinho.
