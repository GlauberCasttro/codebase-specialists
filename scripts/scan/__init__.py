"""scan — camadas L0–L10 (ARCHITECTURE.md §5) → <alvo>/.swarm/facts/*.json."""

LAYERS = (
    ("L0", "inventory"),
    ("L1", "graph"),
    ("L2", "architecture"),
    ("L3", "conventions"),
    ("L4", "rules"),
    ("L5", "history"),
    ("L6", "rationale"),
    ("L7", "operations"),
    ("L8", "stack"),            # também grava stack_graph.json5
    ("L9", "domain"),           # grava glossary.json5 + business_rules.json5
    ("L10", "project_docs"),
)
LAYER_NAME = dict(LAYERS)
