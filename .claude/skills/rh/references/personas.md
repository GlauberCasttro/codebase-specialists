# Personas do rh — espelho legível de `.claude/tools/personas.json`

O JSON é a fonte (o `rh.py` e o `tech_lead.py modelo --papel rh:<persona>` leem dele); esta tabela só explica. Não é
lista fechada: persona nova entra no JSON com os mesmos campos.

| persona | quando contratar | modelo | permissão | missão (uma pergunta) | não faz |
|---|---|---|---|---|---|
| `diagnosticador` | a régua/portão falhou e a causa não é óbvia; antes do IMPASSE (uma vez por task) | sonnet | SOMENTE LEITURA | por que a verificação falha? causa, não correção | não corrige; não roda a suíte inteira se um teste focado basta |
| `cetico` | finding BLOQUEANTE veio SUSPEITA, ou o executor contestou um finding com evidência | opus | SOMENTE LEITURA | tente refutar o finding; assuma que está errado | não procura finding novo |
| `investigador-ambiente` | NOT_RUN de ambiente: `/usr/bin/python3` ausente, 429, git, permissão, sandbox | haiku | SOMENTE LEITURA | o que exatamente falta para a verificação rodar? medir, não consertar | não instala, não mexe em PATH/venv |
| `especialista-seguranca` | a task toca área sensível: motor `ac/`, guards, hooks, frase/senha, `scripts/harness/`, privacidade do pacote | opus | SOMENTE LEITURA | a entrega abre brecha (aprovação contornável, guard que deixa passar, segredo, vazamento)? | não corrige; não revisa fora da entrega |
| `explorador` | task larga, universo desconhecido, antes do executor | sonnet | SOMENTE LEITURA | onde vive o comportamento e o que o executor precisa tocar? | localiza, não julga |
| `oraculista` | frente aberta sem oráculo congelado | opus | ESCRITA em `campanhas/<frente>/oraculo/` | escrever ESPEC + testes que falham hoje a partir dos CAs | não vê a cópia do corretor; não congela (o tech-lead congela) |
| `executor` | só quando pedido explicitamente (o executor do loop usa `tech-lead/references/executor-prompt.md`) | sonnet | ESCRITA nos paths exatos da task | implementar a entrega na cópia de trabalho | não escreve estado, não roda git, não toca o oráculo |

Por que o modelo varia: o custo de um erro de diagnóstico (sonnet) é um ciclo; o de um cético ou especialista que
deixa passar um BLOQUEANTE (opus) é uma regressão publicada; medir o ambiente (haiku) é mecânico. A economia é
hipótese até o `custo.py resumo` da frente dizer o contrário.
