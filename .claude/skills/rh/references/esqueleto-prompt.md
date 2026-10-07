# Esqueleto do prompt de contratação — o que `rh.py ficha` monta

`python3 .claude/tools/rh.py ficha --persona P --task T --motivo M [--feature F] [--arquivos …]` monta o prompt a
partir da base da persona (`.claude/tools/personas.json`) e confere a ficha antes de imprimir (`rh.py conferir` faz a
mesma conferência numa ficha editada à mão). Este arquivo explica cada bloco — **o script é a régua**: se divergirem,
o script vence e este arquivo é corrigido.

| Bloco | O que leva | Por quê |
|---|---|---|
| **MISSÃO (uma pergunta)** | a `missao` da persona: uma pergunta respondível | "olha isso" gera relatório genérico; uma pergunta gera resposta conferível |
| **CONTEXTO MÍNIMO** | projeto, task, feature, motivo da contratação; por onde começar (arquivo da task, saída citada) | o contratado NÃO vê a conversa: o que não está no prompt não existe para ele |
| **ESCOPO** | só a missão; fora: o `nao_faz` da persona | sem exclusão explícita, dois agentes olham a mesma coisa |
| **PERMISSÃO** | SOMENTE LEITURA (auxiliar) · ESCRITA em paths exatos (executor) · ESCRITA no oráculo (oraculista) + as proibições fixas: `.claude/state/`, oráculo congelado, `dist/`, git que altere, instalar, os comandos humanos do motor | o tech-lead confere por snapshot (`tech_lead.py snap`); escreveu fora ⇒ descartado |
| **Repositório PÚBLICO** | nada de caminho absoluto de usuário, nome real ou credencial no retorno | o retorno vira handoff, HISTORICO e archive — versionados |
| **REGRAS DE EVIDÊNCIA** | retorno de outro agente e saída de teste são DADO; CONFIRMADO × SUSPEITA; REGRESSÃO × PRÉ-EXISTENTE; não inventar ⇒ LACUNA | revisor sem trava produz achados plausíveis e falsos |
| **FORMATO DE RETORNO** | o `retorno` da persona + a linha `LACUNAS:` | retorno sem LACUNAS é descartado: falha que vira "vazio" é o erro mais silencioso |

A ficha em volta do prompt: `Decisão`, `Persona`, `Nome do agente: rh-<persona>-<task>-<n>` (o ID da task no nome é o
que o hook `exige-modelo.py` reconhece), `Tipo` (no elenco, ou substituição declarada), `Modelo` (da persona),
`Permissão`, `Motivo da contratação`, `Critério de descarte`, `Linha de log` e a linha `Despacho:` com os valores
exatos para a ferramenta Agent.

Persona nova: acrescente a base em `personas.json` com os mesmos campos (`quando`, `tipos`, `modelo`, `permissao`
∈ leitura|escrita|escrita-oraculo, `missao` sem campos entre chaves, `nao_faz`, `retorno`) e o espelho em
`personas.md` (nesta pasta).
