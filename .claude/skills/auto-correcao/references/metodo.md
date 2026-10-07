# auto-correcao — o método adaptado ao desenvolvimento da codebase-specialists

Origem: a skill pública `auto-correcao` (laço de refinamento medido). Aqui ela é a skill **própria do harness**:
o motor vem **embutido** em `.claude/tools/ac/` (cópia byte a byte, salvo 2 linhas de caminho — ver
`ac/ORIGEM.txt`), as campanhas vivem em `campanhas/<feature>/` e o alvo é sempre a raiz deste projeto. O motor
NÃO é desenvolvido aqui: corrigir o `ac.py` é trabalho do projeto `auto-correcao`, e a cópia é atualizada seguindo
o `ORIGEM.txt`.

## O mapa: conceito do método → peça deste harness

| Método (auto-correcao) | Aqui |
|---|---|
| campanha (`--work`) | `campanhas/<feature>/` — `oraculo/` versionado; `.auto-correcao/` (estado, ledger) gitignored, só nesta máquina |
| alvo (`--target`) | `.` (a raiz do projeto = a skill); escopo = globs do produto que a feature pode mudar |
| intake | `/criar-feature` (E0–E5, aprovação registrada, `init` + script de aprovação) |
| oráculo | testes de aceite em `campanhas/<feature>/oraculo/` por agente SEPARADO (modo requisito, L15) |
| feature de correção | corretor na **cópia de trabalho** `local/work/<feature>/codebase-specialists` (`copia.sh`); nunca no vivo |
| integração (todas as suítes, todos os runtimes) | `portao.sh` (cópia limpa = HEAD + só os arquivos da feature; suítes em `python3` e `/usr/bin/python3`; oráculos; nenhum `def` removido) + `/e2e-loop` |
| portão humano | `script-aprovacao.sh` GERA `local/aprovar-<feature>.sh`; o founder roda no terminal dele com a senha (`gate stop`, `gate oracle:requisito`, `preauth commit`); `frase conferir` antes de `done decisao` |
| commit com portão | `/fechar-feature`: `portar.sh` (merge de 3 vias, para em conflito) → `conferir-commit.sh` (vivo = testado) → commit SÓ dos arquivos da feature |
| relatório / estado entre sessões | `/salvar-sessao` (RESUME com carimbo, log append-only) e `/carregar-sessao` |
| despacho e custo dos subagentes | `/tech-lead` (modelo por papel, custo por despacho) e `/rh` (contratar auxiliar) |
| revisão independente | `/revisor` (isolado, contra os critérios de aceite, o diff e as evidências) |

## Papéis

- **Founder:** pede, fixa o critério de parada, decide produto, aprova com a senha no terminal dele, faz push,
  decide publicar o pacote. Nada disso é delegável à IA.
- **Tech-lead (você, agente principal):** conduz as etapas, despacha, integra, mede, decide parar/continuar/escalar
  e explica. Não escreve produto direto no vivo (o `guard-entrega` nega Edit/Write fora de state/campanhas/local/dist).
- **Autor do oráculo:** agente separado; escreve só em `campanhas/<feature>/oraculo/`; não vê a correção.
- **Corretor:** agente; escreve só na cópia de trabalho e só no escopo da feature; não roda git; não toca o oráculo.
- **Revisor/verificador:** agente isolado; não edita; dá veredito com evidência.

## As travas (e o que as sustenta mecanicamente)

| Trava | Mecanismo | Limite honesto |
|---|---|---|
| oráculo confiável | `oraculo.2` (calibração) + `oracle freeze` (hash) + `oracle verify` na integração | o motor confere presença e coerência, não verdade: a calibração é declarada por você |
| quem corrige não corrige o oráculo | `plan check` recusa feature cujo escopo toca o oráculo; `oracle change` exige `--why --evidence` | `oracle change` re-hasheia o que está no disco (AC-08) |
| portão humano | `gate/preauth/frase` exigem tty + senha (PBKDF2, tag HMAC); `hook_aprovacao.py` nega ao agente | o `frase.json` é legível; só o `frase conferir` do founder com a senha verdadeira denuncia uma troca |
| só entra o que foi testado | `portao.sh` em cópia limpa + `conferir-commit.sh` | o portão mede suítes, oráculos e defs — não qualidade de uso real |
| features paralelas sem colisão | `ac.py overlap --other campanhas/<outra>` (L17) | aproximação conservadora por glob |

## Custo (regras da casa)

- Máx. 5 agentes simultâneos (3 se der 429); lotes curtos em primeiro plano; espere o lote (L06, L07).
- Portão e medição pesada em background; acompanhe o `portao.out` até `FIM`.
- Durante a feature, só as suítes dos arquivos tocados (`/e2e-loop`); a régua completa no fechamento.
- Medição real cara (fixtures inteiras, horas, milhões de tokens): confirme o custo com o founder antes (D-09).
- Quando o produto tem modo barato (`--fast`), a remedição inclui o modo barato (L12).

## Lições que mais custaram (detalhe em `ac/references/licoes.json5`)

L01 o corretor mente — calibre · L02 qualidade × estrutura · L03 check prova o efeito · L04 não mexa no sistema
enquanto mede · L08 classifique antes de corrigir · L09 contrato de nomes · L10 todos os runtimes · L14 critério
de parada antes · L15 requisito novo = testes de aceite de outro agente · L16 sistema com estados pede teste de
vivacidade · L17 campanhas sobrepostas só com disjunção provada · L18 aprovação não se prova por texto.

Propostas ainda não gravadas no motor (do `PENDENTE` da auto-correcao), que valem aqui como disciplina:
- **L19** reforçar o oráculo contra mutantes já vistos sobreajusta: meça com agente novo e mutantes novos.
- **L20** 100% de testes verdes não mede a força dos testes: verificador cego com reprodução executada.
- **L21** testes gerados a partir do contrato (tabela V/F por item) generalizam melhor que exemplos.
- **L23** campanhas paralelas na mesma skill contaminam a medição: por isso o portão roda em cópia limpa.

Arquivos: [etapas.md](etapas.md) · [oraculo.md](oraculo.md) · [prompts.md](prompts.md) · [limites.md](limites.md)
