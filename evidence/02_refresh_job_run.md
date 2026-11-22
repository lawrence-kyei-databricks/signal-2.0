# Run evidence: orchestrated refresh job

Job `Signal 2.0 - Account Risk Refresh` (definition: `06_orchestration/signal_refresh_job.json`), run 263450252359106:
result **SUCCESS**, started 2026-11-22 20:28 UTC, ended 2026-11-22 20:32 UTC (4.4 minutes wall clock).

| task | result | duration |
|---|---|---|
| refresh_customer_360 | SUCCESS | 54 s |
| score_and_brief | SUCCESS | 208 s |

What the run produced (queried after it finished):

| check | value |
|---|---|
| accounts scored in the latest run | 200 |
| model version used | v6 (`account_risk_model@champion`) |
| scored_at | 2026-11-22 20:30 UTC |
| Score sum, Delta vs Lakebase: account_risk_summary | 6099.9 vs 6099.9 (200 rows each) |
| Score sum, Delta vs Lakebase: account_briefing_v2 | 6099.9 vs 6099.9 (200 rows each) |
| Score sum, Delta vs Lakebase: account_deep_insights | 6099.9 vs 6099.9 (200 rows each) |
| High-risk accounts in Delta / Lakebase / metric view (Genie and dashboard) | 20 / 20 / 20 |
