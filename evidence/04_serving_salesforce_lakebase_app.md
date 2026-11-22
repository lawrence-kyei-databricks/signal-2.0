# Run evidence: serving to the business (Salesforce, Lakebase, Databricks App)

## Salesforce reverse ETL

Accounts with `Risk_Score__c` populated: **200**. Two demo accounts read back from Salesforce:

| account | Risk_Score__c | Risk_Category__c | Last_Risk_Assessment__c | model_version | action_type | first recommendation |
|---|---|---|---|---|---|---|
| University of Pittsburgh | 61.7 | High | 2026-11-22T15:00:24.000+0000 | 5 | escalate_ops | 1. The sales rep should prioritize contacting the University of Pittsburgh within 24 hours to address the high backorder rate of 72% and its |
| Merck Life Sciences | 43.2 | Medium | 2026-11-22T15:00:24.000+0000 | 5 | escalate_ops | 1. The sales rep should prioritize addressing the high Backorder rate (6 mo) of 31% to mitigate potential revenue loss, within 24 hours. |

## Lakebase matches Delta after the sync

| side | rows | score_sum | high |
|---|---|---|---|
| Delta account_risk_summary | 200 | 4518.1 | 11 |
| Lakebase cockpit.account_risk_summary | 200 | 4518.1 | 11 |

## Every consumer agrees on the High-risk count (the app's band-consistency check)

| source | high_accounts |
|---|---|
| account_risk_summary (model) | 11 |
| mv_customer_360 (dashboard + Genie) | 11 |
| Lakebase (app) | 11 |

## Databricks App

App `signal-account-cockpit`: state RUNNING, active deployment SUCCEEDED,
resources ['postgres', 'warehouse', 'genie'], user-authorization scopes ['genie', 'sql'].
Rep-decision write path and latency: see `evidence/notebooks/04_lakebase_app__01_lakebase_setup.md`.
