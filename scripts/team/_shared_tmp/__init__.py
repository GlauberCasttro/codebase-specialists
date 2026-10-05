"""Helpers TEMPORÁRIOS compartilhados por scripts/team e scripts/probes.

Duplicam deliberadamente partes de cslib (construído em paralelo). O integrador deve trocar estes
imports por cslib.* e apagar este pacote. Toda leitura de fatos passa por factsio: é o ÚNICO ponto
que conhece o formato interno das camadas do scan (ver references/probes.md, "Contrato de consumo").
"""
