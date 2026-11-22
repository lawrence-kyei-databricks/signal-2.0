# Run evidence: Genie agent (natural language over the governed metric view)

Asked through the Genie Conversation API against the Signal 2.0 Genie agent (source: `main.ccg_workshop_cdm.mv_customer_360`).

## Q: How many accounts are High risk, and what is their expected revenue at risk?

Status: COMPLETED

SQL Genie generated:

```sql
SELECT MEASURE(`At Risk Accounts`) AS `high_risk_accounts`, MEASURE(`Revenue At Risk`) AS `expected_revenue_at_risk`
FROM `main`.`ccg_workshop_cdm`.`mv_customer_360`
WHERE `Risk Category` = 'High'
GROUP BY ALL
```

Result:

| high_risk_accounts | expected_revenue_at_risk |
|---|---|
| 20 | 128845825.90 |

Answer:

> There are **20** high-risk accounts, and the expected revenue at risk for **Risk Category = High** is **$128,845,825.90**. In this result, all reported revenue at risk is tied to those **20** high-risk accounts.

**Stale-data incident caught while capturing this (2026-11-22):** the first time this was asked after the Salesforce revenue
realignment, Genie answered $11,138,514.53. The metric view's materializations run in RELAXED mode on a 6-hour schedule,
so matching queries read the last refresh without a freshness check. Fix: `03_score_and_brief` now runs
`REFRESH MATERIALIZED VIEW` after every rescore and fails the job unless the metric view's account count, revenue,
revenue at risk, and High count equal the scored tables. After the fix Genie returned the figure above.

## Q: Which 5 accounts have the highest risk score, and what is their top risk driver?

Status: COMPLETED

SQL Genie generated (uses the model's `Top Risk Driver` dimension):

```sql
SELECT
  `Account Name`,
  `Top Risk Driver`,
  MEASURE(`Avg Risk Score`) AS `risk_score`
FROM `main`.`ccg_workshop_cdm`.`mv_customer_360`
WHERE `Account Name` IS NOT NULL
  AND `Top Risk Driver` IS NOT NULL
GROUP BY ALL
ORDER BY `risk_score` DESC, `Account Name` ASC
LIMIT 5
```

Result (model v6):

| Account Name | Top Risk Driver | risk_score |
|---|---|---|
| SGS Life Sciences | Revenue vs 12-mo run rate: 0.72x; Order lines with pushed delivery dates (6 mo): 73% | 52.6 |
| Tulsa Genomics Lab | Rep activity trend (last 3 mo vs prior 3): -4; Revenue vs 12-mo run rate: 0.70x | 49.6 |
| AstraZeneca Biologics | Revenue vs 12-mo run rate: 0.20x; Revenue momentum (last 3 mo vs prior 3): -100% | 48.3 |
| Penn Medicine Lancaster General | Rep activity trend (last 3 mo vs prior 3): -6; Revenue vs 12-mo run rate: 0.70x | 47.7 |
| Massachusetts General Hospital | Revenue vs 12-mo run rate: 0.33x; Order lines with pushed delivery dates (6 mo): 80% | 47.5 |

Answer (Genie's wording; its dashes shown as hyphens):

> The **5 accounts with the highest risk scores** in the results are:
> - **SGS Life Sciences** - risk score **52.6**; top risk driver: **Revenue vs 12-mo run rate: 0.72x; Order lines with pushed delivery dates (6 mo): 73%**
> - **Tulsa Genomics Lab** - risk score **49.6**; top risk driver: **Rep activity trend (last 3 mo vs prior 3): -4; Revenue vs 12-mo run rate: 0.70x**
> - **AstraZeneca Biologics** - risk score **48.3**; top risk driver: **Revenue vs 12-mo run rate: 0.20x; Revenue momentum (last 3 mo vs prior 3): -100%**
> - **Penn Medicine Lancaster General** - risk score **47.7**; top risk driver: **Rep activity trend (last 3 mo vs prior 3): -6; Revenue vs 12-mo run rate: 0.70x**
> - **Massachusetts General Hospital** - risk score **47.5**; top risk driver: **Revenue vs 12-mo run rate: 0.33x; Order lines with pushed delivery dates (6 mo): 80%**
> Across these 5 accounts, the most common risk pattern is **revenue running below the 12-month baseline**, often combined with either **pushed delivery dates** or **declining rep activity**.

Check against `account_risk_summary` (the same drivers written to Salesforce): positions 1-4 match exactly. Position 5 is a
tie at 47.5 between Massachusetts General Hospital and Moderna Therapeutics; Genie breaks the tie by name.

This question ranks by probability. The rep worklist ranks by expected dollar loss, so its order differs by design
(Whitehead Institute, Albuquerque Research Center, Massachusetts General Hospital lead it).

Cross-check against the scored tables: High accounts = 20, expected revenue at risk for High accounts = 128,845,826.
