---
name: new-front
description: Abre uma frente de desenvolvimento da codebase-specialists = campanha no motor embutido (ac.py init com escopo em campanhas/<frente>), oráculo separado, script de aprovação, cópia de trabalho e registro no WORKFLOW. Use quando o founder pedir uma mudança no produto, quando um achado de uso real virar trabalho, ou ao pegar o próximo item do BACKLOG.
---

# new-front `<frente>` (ex.: iter17)

AC = `python3 .claude/tools/ac/ac.py` — escreva SEMPRE o caminho literal (o hook de aprovação nega variável +
palavra de aprovação). W = `campanhas/<frente>` (relativo à raiz do projeto).

1. Pré-condição: `bash .claude/tools/carimbo.sh`. Se já há frente ativa, a nova só abre se for disjunta; declare
   as duas como paralelas no WORKFLOW depois do passo 3.
2. Abrir a campanha (um `--scope` por glob, relativo à raiz; critério de parada verificável):
   `python3 .claude/tools/ac/ac.py --work campanhas/<frente> init --target . --scope 'scripts/x/*.py' --scope '...' --problem '<problema>' --stop '<oráculo verde + suítes em 3.13 e 3.9 + nada removido>'`
   (o `.auto-correcao/` da campanha é gitignored: ledger e estado ficam só nesta máquina).
3. Colisão com outra frente: `python3 .claude/tools/ac/ac.py --work campanhas/<frente> overlap --other campanhas/<outra>`;
   colidiu ⇒ serialize.
4. Oráculo por um agente SEPARADO (não o corretor), em `campanhas/<frente>/oraculo/` (ESPEC.md + testes que falham
   antes; caminhos por variável de ambiente; nada privado — é versionado e público).
   Congelar: `python3 .claude/tools/ac/ac.py --work campanhas/<frente> oracle freeze --file <arq1> --file <arq2> ...`
   (um `--file` por arquivo, TODOS).
5. Aprovação humana: `bash .claude/tools/script-aprovacao.sh <frente> --criterio '<texto>' --oraculo '<texto>'`
   gera `local/aprovar-<frente>.sh`. O FOUNDER roda no terminal dele, com a senha. Você não roda, não pede a senha,
   não simula.
6. Cópia de trabalho do corretor: `bash .claude/tools/copia.sh <frente>` (imprime o caminho em `local/work/`). O
   corretor só escreve lá e só no escopo declarado; máx. 5 agentes simultâneos.
7. Registre no `.claude/state/WORKFLOW.md` (frente, o quê, etapa do `ac.py status`, escopo, próximo passo), tire o
   item do BACKLOG (ou marque "em frente <frente>") e acrescente a linha da campanha em `campanhas/README.md`.
