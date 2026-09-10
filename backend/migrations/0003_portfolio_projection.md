# 0003 Portfolio projection

`scripts/migrate.py` creates only `portfolio_connectors` from the separate, explicit metadata in
`backend/kuanguard/portfolio.py`, then applies FORCE RLS and the verified transaction tenant policy.
The table is a minimal, TTL-bounded, rebuildable read-only summary cache. It holds no QIDAIGO orders,
names, private evidence, keys or raw source data. No source database schema changes occur.

Rollback disables the routes/connectors and clears their projection through the authorized disable
operation. The additive table may remain for compatibility; old application/worker versions ignore it.
Do not drop the live database or replay financial transactions.
