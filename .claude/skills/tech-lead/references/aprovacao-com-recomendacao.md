# Aprovação com recomendação — todo gate humano que o tech-lead apresenta

Vale para cada etapa E1–E5 da `criar-frente`, para a decisão de desenho que pare uma task e para o aceite final. A
pergunta continua obrigatória, mas deve dar para respondê-la com **uma palavra**:

    Perguntas que mudam o desenho:
    1. {pergunta}
       → recomendo: {opção} — {motivo em 1 linha, com fonte: "medido em {arquivo:linha}" | "hipótese"}
         alternativa: {outra opção} — {quando ela seria melhor}
    2. …

    ok = aceito todas as recomendações · ou responda só os itens que quer mudar ("2: manter")
    · "adiar {n} para E2" · ajustar {o quê} · pausar

| Regra | Porquê |
|---|---|
| A recomendação **não** é a decisão: o gate só passa com a resposta do founder | aprovação literal, nunca fabricada |
| O registro guarda a palavra literal **e a lista resolvida**: `Aprovação: "ok" — aceitou 1 (…), 2 (…)` | "ok" sozinho não diz o que foi aprovado |
| Resposta parcial ⇒ itens citados usam a resposta, os demais a recomendação; registre item a item | não se perde de quem veio cada valor |
| O motivo diz se é **medido** (arquivo:linha, contagem, saída de script) ou **hipótese** | recomendação sem fonte é opinião disfarçada |
| Sem base para recomendar (preferência de produto pura) ⇒ `sem recomendação: é preferência sua` | inventar recomendação é assumir |
| A escolha entra nos CAs como **decisão travada** e vai para `DECISIONS.md` | impede o executor de decidir de novo |
| Aprovação de CAMPANHA (gate stop, oracle:requisito, preauth commit) não é resposta no chat: é o founder rodando `local/aprovar-<frente>.sh` com a senha | o motor confere a senha; a IA nunca roda o script nem pede a senha |
