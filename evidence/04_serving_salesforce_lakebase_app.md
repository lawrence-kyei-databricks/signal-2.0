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

## A real rep decision made in the app

A signed-in user opened Massachusetts General Hospital in the app and clicked **Accept**.
The request came from the browser, not a notebook. App log:

```text
[22/Nov/2026:17:31:04 +0000] "POST /api/action HTTP/1.1" 200
```

The decision and its audit row were written in one transaction (`cockpit_app` schema in Lakebase):

| Table | id | Account | Action | Risk score seen | Actor | Event | Written at (UTC) |
| --- | --- | --- | --- | --- | --- | --- | --- |
| rep_actions | 5 | Massachusetts General Hospital (`001bm000030F3AWAA0`) | accepted | 66.7 | signed-in rep | - | 2026-11-22 17:31:04 |
| action_audit | 5 | - | - | - | signed-in rep | alert_accepted | 2026-11-22 17:31:04 |

The recorded actor is the signed-in user's identity, not the app's service principal.
Counts after the click: `rep_actions` = 4, `action_audit` = 4. Every decision has exactly one audit row.
The earlier 3 decisions came from notebook test runs (note "Booked save call for Thursday").
This is the only one made through the app UI. The rep left the optional note blank.
