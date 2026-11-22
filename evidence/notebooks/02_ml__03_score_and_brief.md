# Run evidence: ML + GenAI: scoring, AI briefings, Salesforce writeback, Lakebase sync

Source notebook: `02_ml/03_score_and_brief`. Outputs exported 2026-11-22 15:09 UTC from the executed notebook (no images; tables and logs as text).

## Configuration

```text
Data snapshot 2026-08-14 | scoring as of 2026-08-31 | main.ccg_workshop_cdm.account_risk_model v5 (champion)
```

## Score Accounts with Champion Model

```text
Scored 200 accounts with v5: {'High': 11, 'Medium': 68, 'Low': 121}
```

| sf_account_id | account_name | ml_risk_score | risk_category | days_since_last_activity | pct_qty_backordered | open_pipeline_value | annual_revenue | open_case_count | top_risk_driver | risk_probability | model_version | snapshot_date |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 001bm000030F3AWAA0 | Massachusetts General Hospital | 66.7 | High | 23 | 27.1 | 306033.38 | 688624.87 | 2 | Revenue vs 12-mo run rate: 0.33x; Revenue momentum (last 3 mo vs prior 3): -95% | 0.6668 | 5 | 2026-08-14 |
| 001bm000030G3dXAAS | SAIC Life Sciences | 65.8 | High | 198 | 45.8 | 346140.68000000005 | 2548806.16 | 1 | Backorder rate (6 mo): 46%; Days since last rep activity: 198 | 0.6581 | 5 | 2026-08-14 |
| 001bm000030G3eLAAS | AstraZeneca Biologics | 65.0 | High | 157 | 15.5 | 178536.05 | 1473730.88 | 1 | Revenue vs 12-mo run rate: 0.20x; Revenue momentum (last 3 mo vs prior 3): -100% | 0.6503 | 5 | 2026-08-14 |
| 001bm000030G3dBAAS | Berkeley Lights | 62.2 | High | 365 | 13.5 | 0.0 | 1628723.72 | 4 | Days since last rep activity: 365; Revenue momentum (last 3 mo vs prior 3): -40% | 0.6225 | 5 | 2026-08-14 |
| 001bm000030G3dyAAC | University of Pittsburgh | 61.7 | High | 94 | 72.4 | 49186.97 | 420000.0 | 2 | Backorder rate (6 mo): 72%; Revenue momentum (last 3 mo vs prior 3): -80% | 0.6166 | 5 | 2026-08-14 |
| 001bm000030G3fKAAS | Tucson BioAnalytical | 59.7 | High | 12 | 45.4 | 8985.51 | 93550.1 | 4 | Backorder rate (6 mo): 45%; Support cases (6 mo): 4 | 0.5969 | 5 | 2026-08-14 |
| 001bm000030G3fpAAC | Albuquerque Diagnostics Lab | 56.7 | High | 149 | 50.9 | 12087.65 | 116294.67 | 1 | Revenue vs 12-mo run rate: 0.27x; Backorder rate (6 mo): 51% | 0.5672 | 5 | 2026-08-14 |
| 001bm000030F3ACAA0 | SGS Life Sciences | 56.2 | High | 155 | 14.3 | 461013.27 | 2679823.75 | 0 | Revenue momentum (last 3 mo vs prior 3): -100%; Revenue vs 12-mo run rate: 0.72x | 0.5616 | 5 | 2026-08-14 |
| 001bm000030G3e7AAC | NewYork-Presbyterian Hospital | 55.7 | High | 111 | 33.0 | 118541.56 | 954464.39 | 1 | Revenue vs 12-mo run rate: 0.63x; Backorder rate (6 mo): 33% | 0.5566 | 5 | 2026-08-14 |
| 001bm000030G3dLAAS | Exact Sciences | 54.1 | High | 81 | 24.1 | 236075.43 | 1851446.03 | 1 | Revenue momentum (last 3 mo vs prior 3): -100%; Revenue vs 12-mo run rate: 0.76x | 0.5409 | 5 | 2026-08-14 |
| 001bm000030G3fJAAS | Austin Clinical Lab | 53.3 | High | 71 | 59.0 | 19550.519999999997 | 176492.36 | 1 | Backorder rate (6 mo): 59%; Avg delivery slip: 3.2 days | 0.5325 | 5 | 2026-08-14 |
| 001bm000030G3eRAAS | Moderna Therapeutics | 47.9 | Medium | 120 | 0.0 | 520462.09 | 4408075.39 | 2 | Revenue vs 12-mo run rate: 0.32x; Revenue momentum (last 3 mo vs prior 3): -100% | 0.4792 | 5 | 2026-08-14 |
| 001bm000030G3fWAAS | Tucson Life Sciences | 47.7 | Medium | 30 | 38.6 | 48599.89 | 374153.6 | 0 | Revenue momentum (last 3 mo vs prior 3): -100%; Backorder rate (6 mo): 39% | 0.4773 | 5 | 2026-08-14 |
| 001bm000030G3diAAC | Biogen Neurodegeneration | 47.4 | Medium | 45 | 2.8 | 194987.92 | 2205967.39 | 2 | Revenue vs 12-mo run rate: 0.61x; Revenue momentum (last 3 mo vs prior 3): -100% | 0.474 | 5 | 2026-08-14 |
| 001bm000030G3dEAAS | UPenn Perelman Medicine | 47.1 | Medium | 56 | 14.7 | 169135.66 | 654922.17 | 0 | Revenue momentum (last 3 mo vs prior 3): -46%; Revenue vs 12-mo run rate: 0.85x | 0.4709 | 5 | 2026-08-14 |

(15 rows)

## Deep Insights (anchored to snapshot)

```text
200 rows | accounts with 90-day revenue > 0: 164 | total expected revenue at risk: $42,729,768
```

## AI Briefing (ai_decide + ai_query, number-checked)

```text
Number check: 2 of 200 failed first pass | still failing after retry: 0
200 briefings | null action_type: 0 | null recommendations: 0
```

| action_type | count |
|---|---|
| re_engage | 123 |
| escalate_ops | 40 |
| expand_relationship | 24 |
| routine_checkin | 7 |
| protect_pipeline | 6 |

(5 rows)

## Write Briefings to Salesforce

```text
Salesforce: 200 updated, 0 failed 
University of Pittsburgh {'risk_score': 61.7, 'risk_category': 'High', 'model_version': '5', 'action_type': 'escalate_ops'} | fields: 61.7 High
Merck Life Sciences {'risk_score': 43.2, 'risk_category': 'Medium', 'model_version': '5', 'action_type': 'escalate_ops'} | fields: 43.2 Medium
```

## Refresh Lakebase and verify the app serves the new scores

```text
Lakebase sync 62630000-e72c-4b8e-8ef9-11d100dce040: COMPLETED | 200 rows, score sum 4518.1, 11 High - matches Delta
```
