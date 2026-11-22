# Run evidence: ML: training, out-of-time validation, drift check, gated promotion

Source notebook: `02_ml/02_train_risk_model`. Outputs exported 2026-11-22 21:53 UTC from the executed notebook (no images; tables and logs as text).

## Configuration

```text
2026/11/22 19:17:00 INFO mlflow.tracking.fluent: Experiment with name '/Shared/signal-2.0-assets/ccg_account_risk_model' does not exist. Creating a new experiment.
```

```text
Features: ['log_rev_6m', 'rev_momentum_3m', 'rev_6m_vs_12m', 'backorder_rate_6m', 'slip_rate_6m', 'avg_slip_days_6m', 'activities_6m', 'activity_trend_3m', 'days_since_last_activity', 'cases_6m', 'high_priority_cases_6m']
Experiment: /Shared/signal-2.0-assets/ccg_account_risk_model | id: 1945376116972192
```

## Build Point-in-Time Snapshots

```text
History: synthetic | cutoffs 2025-08-01..2026-02-01 | train <= 2025-11-01 | test >= 2026-01-01
Snapshots: 1399 rows over 7 cutoffs | train 800 | test 399
```

| cutoff_month | accounts | decline_rate |
|---|---|---|
| 2025-08-01T00:00:00.000Z | 200 | 0.395 |
| 2025-09-01T00:00:00.000Z | 200 | 0.36 |
| 2025-10-01T00:00:00.000Z | 200 | 0.35 |
| 2025-11-01T00:00:00.000Z | 200 | 0.3 |
| 2025-12-01T00:00:00.000Z | 200 | 0.27 |
| 2026-01-01T00:00:00.000Z | 200 | 0.28 |
| 2026-02-01T00:00:00.000Z | 199 | 0.256 |

(7 rows)

## Train, Validate Out-of-Time, Register

```text
Drift vs 200 live accounts (as of 2026-08-31): score PSI 0.034 | features shift 5, watch 3
```

| feature | train_median | live_median | psi | ks_stat | band |
|---|---|---|---|---|---|
| log_rev_6m | 14.806 | 15.205 | 0.352 | 0.252 | shift |
| rev_momentum_3m | -0.014 | 0.016 | 0.297 | 0.171 | shift |
| rev_6m_vs_12m | 0.972 | 1.077 | 0.332 | 0.17 | shift |
| backorder_rate_6m | 0.133 | 0.126 | 0.318 | 0.091 | shift |
| slip_rate_6m | 1.0 | 0.938 | 0.204 | 0.219 | watch |
| avg_slip_days_6m | 7.355 | 7.441 | 0.055 | 0.071 | stable |
| activities_6m | 2.0 | 3.0 | 0.678 | 0.148 | shift |
| activity_trend_3m | 0.0 | 0.0 | 0.054 | 0.08 | stable |
| days_since_last_activity | 57.0 | 43.0 | 0.169 | 0.139 | watch |
| cases_6m | 0.0 | 1.0 | 0.101 | 0.081 | watch |
| high_priority_cases_6m | 0.0 | 0.0 | 0.082 | 0.072 | stable |

(11 rows)

```text
2026/11/22 19:17:54 WARNING mlflow.tracking.context.registry: Encountered unexpected error during resolving tags: getContext().extraContext() is not a CommandContext accessor, it is not available or is misspelled.
2026/11/22 19:17:56 WARNING mlflow.tracking.context.registry: Encountered unexpected error during resolving tags: getContext().extraContext() is not a CommandContext accessor, it is not available or is misspelled.
🔗 View Logged Model at: <workspace-url>
2026/11/22 19:18:05 WARNING mlflow.tracking.context.registry: Encountered unexpected error during resolving tags: getContext().extraContext() is not a CommandContext accessor, it is not available or is misspelled.
Registered model 'main.ccg_workshop_cdm.account_risk_model' already exists. Creating a new version of this model...
```

```text
🔗 Created version '6' of model 'main.ccg_workshop_cdm.account_risk_model': <workspace-url>
```

```text
Run cd6d3537415445289a199af4ead8eef9 -> main.ccg_workshop_cdm.account_risk_model v6
{'oot_auc': 0.625, 'oot_pr_auc': 0.39, 'oot_brier': 0.196, 'oot_rule_auc': 0.543, 'oot_gbc_auc': 0.706, 'oot_base_rate': 0.268, 'n_train': 800.0, 'n_test': 399.0, 'oot_lift_over_rule': 0.082, 'score_psi': 0.034, 'features_psi_shift': 5.0, 'features_psi_watch': 3.0, 'max_feature_psi': 0.678}
```

| feature | coefficient (standardized) |
|---|---|
| log_rev_6m | 0.5402881263453693 |
| rev_6m_vs_12m | -0.33359203053141656 |
| slip_rate_6m | -0.19108458938816042 |
| cases_6m | -0.16309755843672322 |
| activity_trend_3m | -0.12617134502129582 |
| high_priority_cases_6m | 0.10511110175782207 |
| backorder_rate_6m | 0.08887101982088196 |
| days_since_last_activity | 0.08825745144963652 |
| rev_momentum_3m | -0.07853045262306212 |
| activities_6m | 0.03943991692394765 |
| avg_slip_days_6m | 0.0026149895944872813 |

(11 rows)

## Gate and Promote

```text
Gate 1: OOT AUC 0.625 >= 0.6 -> PASS
Gate 2: lift over rule +0.082 (rule AUC 0.543) >= 0.05 -> PASS
Gate 3: score PSI train vs live 0.034 < 0.1 -> PASS
Promoted v6 to champion
Aliases: {'champion': '6'}
```
