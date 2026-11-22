# Run evidence: ML: synthetic training history

Source notebook: `02_ml/01_build_training_history`. Outputs exported 2026-11-22 15:09 UTC from the executed notebook (no images; tables and logs as text).

## Configuration and Real Anchors

```text
Real snapshot date: 2026-08-14 | real account-months: 1971 | accounts anchored: 200
```

## Causal History Generator

```text
Generated 4800 account-months for 200 accounts (2024-09-01 to 2026-08-01)
```

## Validate Anchoring and Cause-and-Effect

| real_mean | syn_mean | per_account_corr |
|---|---|---|
| 14.424 | 14.672 | 0.147 |
| 0.155 | 0.169 | 0.828 |
| 2.707 | 2.631 | 0.548 |

(3 rows)

```text
Avg next-6m revenue change when the last 3 months had:
  high backorders (top quartile): -12.9% | others: +16.5%
  no rep activity:                -3.9% | some activity: +12.3%
```

## Write Synthetic History Table

```text
Wrote main.ccg_workshop_cdm.syn_account_monthly_history: 4800 rows, 200 accounts, 24 months, total revenue 2,412,587,647
```
