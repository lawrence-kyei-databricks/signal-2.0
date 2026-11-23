# Run evidence: ML + Gen AI: scoring, AI briefings, Salesforce writeback, Lakebase and metric view refresh

Source notebook: `02_ml/03_score_and_brief`. Outputs exported 2026-11-23 00:31 UTC from the executed notebook (no images; tables and logs as text).

## Configuration

```text
{"ts": "2026-11-23 00:25:48.566", "level": "WARNING", "logger": "pyspark.sql.connect.logging", "msg": "Effective usage policy for this session is cct.Chpub3RlYm9va3MvMTk0NTM3NjExNjk2ODgyNBABIAEyJDAxYTIwNWNiLTNlOGEtN2IzZS05ZTM5LWVkYTc4MTFjNDFmMjokNDdhOTQ4OWEtNzIzZC0zMDQ0LWE3ZGItMDcwZWY1Y2U1NjgxQiQ5NTc3Y2NlMi1mM2RkLTRiNGYtYTY1Ny1iMTYwN2UzODAxZDlKDAj/j47YBhCAgcCqAlABWAFgAWiXw4PVivTfAYgBAA==.", "context": {}}
{"ts": "2026-11-23 00:25:48.566", "level": "WARNING", "logger": "pyspark.sql.connect.logging", "msg": "Effective usage policy for this session is cct.Chpub3RlYm9va3MvMTk0NTM3NjExNjk2ODgyNBABIAEyJDAxYTIwNWNiLTNlOGEtN2IzZS05ZTM5LWVkYTc4MTFjNDFmMjokNDdhOTQ4OWEtNzIzZC0zMDQ0LWE3ZGItMDcwZWY1Y2U1NjgxQiQ5NTc3Y2NlMi1mM2RkLTRiNGYtYTY1Ny1iMTYwN2UzODAxZDlKDAj/j47YBhCAgcCqAlABWAFgAWiXw4PVivTfAYgBAA==.", "context": {}}
{"ts": "2026-11-23 00:25:48.566", "level": "WARNING", "logger": "pyspark.sql.connect.logging", "msg": "Effective usage policy for this session is cct.Chpub3RlYm9va3MvMTk0NTM3NjExNjk2ODgyNBABIAEyJDAxYTIwNWNiLTNlOGEtN2IzZS05ZTM5LWVkYTc4MTFjNDFmMjokNDdhOTQ4OWEtNzIzZC0zMDQ0LWE3ZGItMDcwZWY1Y2U1NjgxQiQ5NTc3Y2NlMi1mM2RkLTRiNGYtYTY1Ny1iMTYwN2UzODAxZDlKDAj/j47YBhCAgcCqAlABWAFgAWiXw4PVivTfAYgBAA==.", "context": {}}
```

```text
Data snapshot 2026-08-14 | scoring as of 2026-08-31 | main.ccg_workshop_cdm.account_risk_model v6 (champion)
```

## Score Accounts with Champion Model

```text
Scored 200 accounts with v6: {'High': 20, 'Medium': 60, 'Low': 120}
```

| sf_account_id | account_name | ml_risk_score | risk_category | days_since_last_activity | pct_qty_backordered | open_pipeline_value | annual_revenue | open_case_count | top_risk_driver | risk_probability | model_version | snapshot_date | expected_revenue_at_risk |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 001bm000030G3deAAC | Whitehead Institute | 46.1 | High | 51 | 11.1 | 3584138.78 | 1.761603837E7 | 0 | Revenue vs 12-mo run rate: 0.54x; Support cases (6 mo): 0 | 0.4609 | 6 | 2026-08-14 | 4059630.26 |
| 001bm000030G3edAAC | Albuquerque Research Center | 45.6 | High | 9 | 2.5 | 966002.6 | 1.740178394E7 | 0 | Revenue vs 12-mo run rate: 0.47x; Support cases (6 mo): 0 | 0.4559 | 6 | 2026-08-14 | 3966519.75 |
| 001bm000030F3AWAA0 | Massachusetts General Hospital | 47.5 | High | 23 | 27.1 | 7062655.59 | 1.589212357E7 | 2 | Revenue vs 12-mo run rate: 0.33x; Order lines with pushed delivery dates (6 mo): 80% | 0.4751 | 6 | 2026-08-14 | 3775349.26 |
| 001bm000030G3dEAAS | UPenn Perelman Medicine | 38.2 | High | 56 | 14.7 | 4938687.859999999 | 1.912344309E7 | 0 | Support cases (6 mo): 0; Revenue vs 12-mo run rate: 0.85x | 0.3821 | 6 | 2026-08-14 | 3653174.8 |
| 001bm000030G3eLAAS | AstraZeneca Biologics | 48.3 | High | 157 | 15.5 | 1813064.9300000002 | 1.49659958E7 | 1 | Revenue vs 12-mo run rate: 0.20x; Revenue momentum (last 3 mo vs prior 3): -100% | 0.4831 | 6 | 2026-08-14 | 3615326.74 |
| 001bm000030G3fSAAS | Boise Genomics Lab | 47.1 | High | 9 | 3.7 | 1373996.62 | 1.435701689E7 | 1 | Revenue vs 12-mo run rate: 0.39x; Order lines with pushed delivery dates (6 mo): 75% | 0.4709 | 6 | 2026-08-14 | 3380435.65 |
| 001bm000030G3f7AAC | Buffalo Diagnostics Lab | 37.5 | High | 17 | 18.3 | 0.0 | 1.788767625E7 | 1 | Revenue vs 12-mo run rate: 0.76x; Rep activities (6 mo): 5 | 0.3748 | 6 | 2026-08-14 | 3351835.79 |
| 001bm000030F3APAA0 | Penn Medicine Lancaster General | 47.7 | High | 115 | 0.0 | 2604431.89 | 1.396616044E7 | 1 | Rep activity trend (last 3 mo vs prior 3): -6; Revenue vs 12-mo run rate: 0.70x | 0.4772 | 6 | 2026-08-14 | 3332030.38 |
| 001bm000030G3eUAAS | Northwestern Feinberg | 34.0 | High | 118 | 11.3 | 6516832.78 | 1.945168408E7 | 2 | High-priority cases (6 mo): 2; Rep activity trend (last 3 mo vs prior 3): -2 | 0.3405 | 6 | 2026-08-14 | 3311535.07 |
| 001bm000030G3dXAAS | SAIC Life Sciences | 40.1 | High | 198 | 45.8 | 2235216.04 | 1.645900858E7 | 1 | Backorder rate (6 mo): 46%; Days since last rep activity: 198 | 0.401 | 6 | 2026-08-14 | 3299861.15 |
| 001bm000030F3AGAA0 | Emory Vaccine Center | 37.4 | High | 62 | 20.2 | 4588181.26 | 1.757585209E7 | 0 | Support cases (6 mo): 0; Revenue vs 12-mo run rate: 0.93x | 0.3735 | 6 | 2026-08-14 | 3282484.56 |
| 001bm000030G3e4AAC | Walter Reed Army Institute | 43.4 | High | 51 | 3.9 | 3039344.63 | 1.507154018E7 | 0 | Revenue momentum (last 3 mo vs prior 3): -100%; Support cases (6 mo): 0 | 0.4339 | 6 | 2026-08-14 | 3269439.59 |
| 001bm000030G3dmAAC | Cold Spring Harbor Lab | 32.0 | High | 138 | 10.3 | 3480881.6500000004 | 1.917578665E7 | 1 | Rep activity trend (last 3 mo vs prior 3): -1; Days since last rep activity: 138 | 0.3197 | 6 | 2026-08-14 | 3065719.23 |
| 001bm000030G3fQAAS | Phoenix Clinical Lab | 40.1 | High | 30 | 0.0 | 0.0 | 1.484034623E7 | 0 | Revenue vs 12-mo run rate: 0.42x; Support cases (6 mo): 0 | 0.4012 | 6 | 2026-08-14 | 2977175.8 |
| 001bm000030F3AEAA0 | Guardant Health | 31.2 | High | 14 | 10.2 | 3634981.11 | 1.884540184E7 | 1 | Revenue momentum (last 3 mo vs prior 3): -88%; Avg delivery slip: 7.3 days | 0.3121 | 6 | 2026-08-14 | 2941164.01 |

(15 rows)

## Deep Insights (anchored to snapshot)

```text
200 rows | accounts with 90-day revenue > 0: 164 | total expected revenue at risk: $561,379,968
```

## AI Briefing (ai_decide + ai_query, number-checked)

```text
Number check: 3 of 200 failed first pass | still failing after retry: 0
200 briefings | null action_type: 0 | null recommendations: 0
```

| action_type | count |
|---|---|
| re_engage | 135 |
| escalate_ops | 40 |
| expand_relationship | 13 |
| protect_pipeline | 11 |
| routine_checkin | 1 |

(5 rows)

## Write Briefings to Salesforce

```text
Salesforce: 200 updated, 0 failed 
University of Pittsburgh {'risk_score': 40.6, 'risk_category': 'Low', 'model_version': '6', 'action_type': 're_engage'} | fields: 40.6 Low
Merck Life Sciences {'risk_score': 31.0, 'risk_category': 'Medium', 'model_version': '6', 'action_type': 'escalate_ops'} | fields: 31.0 Medium
```

## Refresh Lakebase and the metric view, verify every consumer matches

```text
Lakebase account_risk_summary   sync c26371cb-39ae-4284-a205-f2ebb1e158be: COMPLETED | 200 rows, fingerprint (6099.9, 20) - matches Delta
Lakebase account_briefing_v2    sync 8544b42f-516c-4c05-8838-d7cabc78f3df: COMPLETED | 200 rows, fingerprint (6099.9, 200) - matches Delta
Lakebase account_deep_insights  sync 6542aeed-a821-4814-9fd7-4f6ebf798264: COMPLETED | 200 rows, fingerprint (561379968.0, 43170.1) - matches Delta
Metric view main.ccg_workshop_cdm.mv_customer_360 refreshed | 200 accounts, revenue 1,750,444,149, at risk 561,379,966, 20 High - matches source
```
