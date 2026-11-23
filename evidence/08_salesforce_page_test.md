# Evidence: Salesforce briefing page, tested against every live account

Run 2026-11-23 00:30 UTC. The script of the **deployed** Visualforce page (`Signal2_Risk_Dashboard`, read back from the
Salesforce Tooling API) was executed in Node with `scripts/test_salesforce_page.js`, once per account, using each
account's real `Description` briefing JSON from the org (200 accounts).

## Bug found and fixed

The page split recommendations on any "digit + dot", so it also cut inside numbers such as `-6.9%`. A rep saw `-` and
`9%` as separate fragments, and the third recommendation was dropped. The app was unaffected (it anchors the split to
line starts). The page now uses the same rule as the app, and it builds recommendations and metric cards as text
nodes, never HTML, because the recommendations are LLM output.

| Page version | Accounts | Rendered exactly 3 recommendations, identical to the source text | Test exit |
|---|---|---|---|
| Old splitter | 200 | 26 (174 failures) | 1 |
| Deployed fix | 200 | **200** (0 failures) | 0 |

No page code uses `innerHTML` (the test's DOM shim throws if it does).

## Second revenue metric added to the banner

The banner showed only the 90-day revenue trend. It now also shows the model's 6-month vs 12-month run rate, because
the two answer different questions: an account that fell months ago and stayed down looks roughly flat over 90 days
but low against its run rate.

| Check | Result |
|---|---|
| Accounts whose briefing carries `rev_vs_run_rate` (written by `02_ml/03_score_and_brief`) | 200 of 200 |
| Value in Salesforce equals the scored table (`account_risk_predictions`, latest run) | 200 of 200 |
| Run-rate card rendered with the correct value | 200 of 200 |
| 90-day trend card rendered | 158 of 200; the other 42 had no revenue in the prior 90 days, so no trend exists (all 42 null at source) |

Example, Whitehead Institute: `Revenue, last 90d vs prior 90d: -6.9%` and `Revenue, last 6 mo vs 12-mo run rate: 0.54x`.
Massachusetts General Hospital: `-97.4%` and `0.33x`.
