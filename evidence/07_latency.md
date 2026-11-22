# Evidence: latency per screen

Measured 2026-11-22 from a serverless notebook in the same workspace, 20 runs per path, one account
(Massachusetts General Hospital). Server-side times: they exclude the browser round trip and the Databricks Apps proxy,
which a notebook token cannot reach (the app returns 401 to it).

## Building blocks

| Path | p50 | p95 |
|---|---|---|
| Lakebase lookup, connection already open | 2.3 ms | 4.1 ms |
| Lakebase lookup, new connection each time (how the app connects) | 56.7 ms | 97.0 ms |
| SQL warehouse, same single-row lookup (Statement Execution API) | 375.1 ms | 403.9 ms |

The README used to quote 1.3 ms. That was the warm, open-connection case (first row above, measured earlier in
`notebooks/04_lakebase_app__01_lakebase_setup.md`). It is the database time, not what a rep waits for.

## What a rep waits for (server side)

| Screen | Before | After | Change |
|---|---|---|---|
| Worklist (`/api/worklist`, 50 rows) | 50.8 ms p50, 239.0 ms p95 | unchanged (already Lakebase only) | - |
| Account panel (`/api/account/{id}`) | 978.7 ms p50, 1,147.6 ms p95 | **59.0 ms p50, 79.1 ms p95** | about 16x faster |

**Why the account panel was slow:** it read risk from Lakebase, then made two warehouse calls in a row for the AI briefing
and deep insights. **Fix:** `account_briefing_v2` and `account_deep_insights` are now Lakebase synced tables, and the
panel reads all four sources over one Postgres connection. `03_score_and_brief` refreshes all three synced tables after
every rescore and fails the job if any Lakebase copy differs from Delta (row count plus a column-sum fingerprint).

**Bug fixed along the way:** the panel asked for `recommendation_1-3`, `urgency`, `revenue_trend_pct` and `peer_risk_delta`,
which no table had, so the AI recommendations and deep signals never rendered. The API now maps the real columns; all
200 briefings split into 3 recommendations.

**Not yet measured:** end-to-end time in a browser. Open the network tab on the deployed app for that number.
