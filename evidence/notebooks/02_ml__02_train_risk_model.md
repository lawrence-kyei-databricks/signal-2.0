# Run evidence: ML: training, out-of-time validation, gated promotion

Source notebook: `02_ml/02_train_risk_model`. Outputs exported 2026-11-22 15:09 UTC from the executed notebook (no images; tables and logs as text).

## Configuration

```text
Features: ['log_rev_6m', 'rev_momentum_3m', 'rev_6m_vs_12m', 'backorder_rate_6m', 'slip_rate_6m', 'avg_slip_days_6m', 'activities_6m', 'activity_trend_3m', 'days_since_last_activity', 'cases_6m', 'high_priority_cases_6m']
Experiment: /Users/<redacted-email>/thermofisher/CCG/signal-2.0-assets/ccg_account_risk_model | id: 1945376116968627
```

## Build Point-in-Time Snapshots

```text
History: synthetic | cutoffs 2025-08-01..2026-02-01 | train <= 2025-11-01 | test >= 2026-01-01
Snapshots: 1400 rows over 7 cutoffs | train 800 | test 400
```

| cutoff_month | accounts | decline_rate |
|---|---|---|
| 2025-08-01T00:00:00.000Z | 200 | 0.365 |
| 2025-09-01T00:00:00.000Z | 200 | 0.335 |
| 2025-10-01T00:00:00.000Z | 200 | 0.335 |
| 2025-11-01T00:00:00.000Z | 200 | 0.295 |
| 2025-12-01T00:00:00.000Z | 200 | 0.23 |
| 2026-01-01T00:00:00.000Z | 200 | 0.19 |
| 2026-02-01T00:00:00.000Z | 200 | 0.15 |

(7 rows)

## Train, Validate Out-of-Time, Register

```text
🔗 View Logged Model at: https://adb-984752964297111.11.azuredatabricks.net/ml/experiments/1945376116968627/models/m-20ce8ba00d204415ab164c215e6bef02?o=984752964297111
Registered model 'main.ccg_workshop_cdm.account_risk_model' already exists. Creating a new version of this model...
```

```text
🔗 Created version '5' of model 'main.ccg_workshop_cdm.account_risk_model': https://adb-984752964297111.11.azuredatabricks.net/explore/data/models/main/ccg_workshop_cdm/account_risk_model/version/5?o=984752964297111
```

```text
Run 460930c56af84efba3a81f852e47bf40 -> main.ccg_workshop_cdm.account_risk_model v5
{'oot_auc': 0.818, 'oot_pr_auc': 0.475, 'oot_brier': 0.138, 'oot_rule_auc': 0.667, 'oot_gbc_auc': 0.781, 'oot_base_rate': 0.17, 'n_train': 800.0, 'n_test': 400.0, 'oot_lift_over_rule': 0.15}
```

| feature | coefficient (standardized) |
|---|---|
| log_rev_6m | 0.8871857718809553 |
| rev_6m_vs_12m | -0.5861604594143189 |
| backorder_rate_6m | 0.47180405075963916 |
| rev_momentum_3m | -0.20695743395426577 |
| days_since_last_activity | 0.2058981950047758 |
| activity_trend_3m | -0.13883011206420598 |
| cases_6m | 0.08201085290035064 |
| high_priority_cases_6m | 0.04788747521766574 |
| activities_6m | -0.042162333259202656 |
| avg_slip_days_6m | -0.02829890197188998 |
| slip_rate_6m | 0.017079899117118796 |

(11 rows)

## Gate and Promote

```text
Gate 1: OOT AUC 0.818 >= 0.7 -> PASS
Gate 2: lift over rule +0.150 (rule AUC 0.667) >= 0.05 -> PASS
Promoted v5 to champion
Aliases: {'champion': '5'}
```
