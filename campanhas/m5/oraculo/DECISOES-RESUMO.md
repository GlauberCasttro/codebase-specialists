# Decisões do oráculo M5 — resumo para o founder

Estas são as 18 decisões do `ESPEC.md` §3, uma linha cada. Marquei com ★ as cinco que mais mudam o comportamento que você vai ver.

1. ★ **A máquina do mandato fica junto das outras máquinas do harness.** Ela passa pelos mesmos testes de "nenhum estado trancado" e de cobertura 100%. Para isso estendi esses testes oficiais com um patch revisável; nenhuma checagem existente foi afrouxada.
2. São 12 estados, não 11: o resumo do desenho dizia 11, mas a tabela lista 12, e valeu a tabela.
3. Cada saída da espera humana virou um caminho com nome próprio. "Retomar" volta exatamente para onde o mandato estava antes de parar.
4. Existe um passo novo, "próxima feature", para que o mandato de sprint passe da feature 1 para a 2.
5. ★ **Um ramo travado não para o resto.** Se uma task precisa mexer em área congelada, só ela e as que dependem dela esperam você. O mandato só para e chama você quando não sobra mais nada que possa rodar.
6. Se algum critério de aceite já passa antes de começar, o mandato é recusado, porque um critério já verde não prova entrega.
7. Cada task é verificada pelo próprio teste dela. O aceite da feature inteira é medido só ao fechar cada onda, então uma task não é reprovada por um critério que depende de outras tasks.
8. O modelo nunca roda "verificar" nem escreve o brief à mão: verificar, aceitar e fechar task são trabalho do script.
9. Nas tasks do mandato não se exige uma task de PO antes do dev, porque a spec e os critérios assinados por você já cumprem esse papel.
10. Guardas que o próprio motor calcula ficam isentas de "precisa ser vista recusando", sempre com motivo escrito. As demais são cobertas transição por transição.
11. O orçamento é calculado pelo motor a partir do tamanho do plano, e só você pode mudá-lo (na aprovação ou numa emenda).
12. ★ **O corte de orçamento chega aos 80%.** Com 5 despachos, o 4º ainda é feito e terminado; o 5º nunca sai, e você recebe uma entrega parcial com o que sobrou devolvido ao backlog.
13. ★ **Sem progresso, ele encerra em vez de escalar.** Depois de rodadas que não avançam o aceite, o mandato replaneja uma vez e, se continuar parado, encerra com entrega parcial. Ele não fica pedindo sua ajuda por contagem de tentativas.
14. Quando um subagente morre no meio do trabalho, o script olha o disco: se não há mudança, a task volta para a fila; se há, ela vai direto para verificação.
15. ★ **Portão humano continua só seu.** Aprovar, emendar, resolver, parar e abortar exigem `--by <humano>`, e o guard bloqueia o modelo de rodar esses comandos. A frase-senha virá da outra campanha sem mudar este oráculo.
16. Os testes têm um relógio falso (`CS_NOW`), único jeito mecânico de provar que 8 horas de pausa não consomem o orçamento de tempo.
17. Uma task que corrige uma regressão (tipo FIX) cita o teste que quebrou, e o motor preenche sozinho a referência que a árvore exige.
18. Ficou fora deste oráculo: promoção de lições no fim, diário, modelo do verificador maior ou igual ao do autor, revisão "cega", custo medido pelo roteador e o modo semiautônomo para plataformas sem hook.
