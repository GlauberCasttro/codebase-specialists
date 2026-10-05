# Notes for coding agents (written by the shop team)

- Talk to Marina (catalog owner) before changing `priceCents` semantics; finance reconciles on it.
- We deploy the api on Fridays only after 14h BRT freeze review. Never bump `express` to 5.x
  without the api owner: middleware error handling changed.
- Prefer small PRs: one workspace per PR unless the change is a contract in `@shop/shared`.
