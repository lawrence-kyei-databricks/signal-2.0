# Evidence: training vs live feature drift

The model trains on synthetic history (`syn_account_monthly_history`) and scores real accounts (`cur_*`, `sf_*`).
This checks that the two look alike. Training: 800 snapshots (cutoffs Aug-Nov 2025). Live: 200 real accounts as of 2026-08-31,
built by the same feature code (`ccg_risk_features.py`). PSI bands: < 0.10 stable, 0.10-0.25 watch, >= 0.25 shift.
`02_train_risk_model` logs every value below to MLflow on each run and blocks promotion if score PSI >= 0.10.

## Before and after recalibrating the generator

| | v5 (smooth history, 4 orders a month) | v6 (real levels, real order cadence) |
|---|---|---|
| Score PSI, training vs live | 0.218 | **0.034** |
| Features at PSI >= 0.25 | 8 of 11 | 5 of 11 |
| Live accounts in the top band (old fixed cut-offs) | 5.5% vs 12.8% in training | n/a (bands are now rank-based) |
| Out-of-time AUC | 0.818 | 0.625 |
| AUC of today's rule, same test | 0.667 | 0.543 |

The v5 AUC came largely from the generator: smooth 4-orders-a-month revenue made decline easy to predict.
Real accounts order about once a month and are active in about 10 of 20 months, so revenue is lumpy and decline is harder to call.

## v6 per-feature drift (MLflow run for model v6)

| Feature | Train median | Live median | PSI | Band |
|---|---|---|---|---|
| log_rev_6m | 14.806 | 15.205 | 0.352 | shift |
| rev_momentum_3m | -0.014 | 0.016 | 0.297 | shift |
| rev_6m_vs_12m | 0.972 | 1.077 | 0.332 | shift |
| backorder_rate_6m | 0.133 | 0.126 | 0.318 | shift |
| slip_rate_6m | 1.000 | 0.938 | 0.204 | watch |
| avg_slip_days_6m | 7.355 | 7.441 | 0.055 | stable |
| activities_6m | 2.0 | 3.0 | 0.678 | shift |
| activity_trend_3m | 0.0 | 0.0 | 0.054 | stable |
| days_since_last_activity | 57.0 | 43.0 | 0.169 | watch |
| cases_6m | 0.0 | 1.0 | 0.101 | watch |
| high_priority_cases_6m | 0.0 | 0.0 | 0.082 | stable |

## What this does and does not show

- **Shows:** the model's scores on today's accounts are distributed like its training scores (score PSI 0.034), so bands and rankings mean the same thing in training and in production.
- **Does not show:** that the cause-and-effect in the synthetic history is real. Five inputs still shift, and the generator authored the link between operational pain and revenue. Absolute accuracy (AUC 0.625) will not transfer as-is.
- **What transfers:** the model beat today's rule in every generator variant tested (lift +0.04 to +0.15 AUC). The pilot's first job is recalibration on real decline labels; `HISTORY_SOURCE = "cdm"` retrains on real history once about 23 months exist.
- **Tried and rejected:** a gradient-boosted model with order-cadence features (out-of-time AUC 0.715) failed the drift gate (score PSI 0.24), so v6 stays champion.
