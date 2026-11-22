# Run evidence: orchestrated refresh job

Job `Signal 2.0 - Account Risk Refresh` (definition: `06_orchestration/signal_refresh_job.json`), run 59050353608765:
result **SUCCESS**, started 2026-11-22 16:03 UTC, ended 2026-11-22 16:07 UTC.

| task | result | started | ended |
|---|---|---|---|
| refresh_customer_360 | SUCCESS | 2026-11-22 16:03 UTC | 2026-11-22 16:04 UTC |
| score_and_brief | SUCCESS | 2026-11-22 16:04 UTC | 2026-11-22 16:07 UTC |

What the run produced (queried after it finished):

| check | value |
|---|---|
| accounts scored in the latest run | 200 |
| model version used | v5 (`account_risk_model@champion`) |
| scored_at | 2026-11-22 16:05 UTC |
| Delta account_risk_summary score sum | 4518.1 |
| Lakebase cockpit.account_risk_summary score sum | 4518.1 |
