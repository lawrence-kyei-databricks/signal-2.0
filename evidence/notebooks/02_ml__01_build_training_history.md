# Run evidence: ML: synthetic training history anchored to real account levels

Source notebook: `02_ml/01_build_training_history`. Outputs exported 2026-11-22 22:58 UTC from the executed notebook (no images; tables and logs as text).

## Configuration and Real Anchors

```text
Using frozen anchors from main.ccg_workshop_cdm.syn_account_anchors: 200 accounts
Snapshot date: 2026-08-14 | account-months in ERP: 1971 | accounts anchored: 200
```

## Causal History Generator

```text
Generated 4800 account-months for 200 accounts (2024-09-01 to 2026-08-01)
```

## Validate Anchoring and Cause-and-Effect

| real_mean | syn_mean | per_account_corr |
|---|---|---|
| 14.424 | 14.113 | -0.024 |
| 0.155 | 0.154 | 0.694 |
| 2.707 | 3.056 | 0.636 |

(3 rows)

```text
Avg next-6m revenue change when the last 3 months had:
  high backorders (top quartile): +1.7% | others: +20.3%
  no rep activity:                +3.2% | some activity: +22.5%
```

## Write Synthetic History Table

```text
Wrote main.ccg_workshop_cdm.syn_account_monthly_history: 4800 rows, 200 accounts, 24 months, total revenue 2,412,970,896
```
