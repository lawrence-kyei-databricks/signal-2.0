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
| 11 | 7621239.732491 |

Answer:

> There are **11** High risk accounts, and the expected revenue at risk for **High risk accounts** is **7,621,239.732491**. In this result, all reported revenue at risk is tied to the **11** accounts filtered as **High** risk.

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
ORDER BY `risk_score` DESC
LIMIT 5
```

Result:

| Account Name | Top Risk Driver | risk_score |
|---|---|---|
| Massachusetts General Hospital | Revenue vs 12-mo run rate: 0.33x; Revenue momentum (last 3 mo vs prior 3): -95% | 66.7 |
| SAIC Life Sciences | Backorder rate (6 mo): 46%; Days since last rep activity: 198 | 65.8 |
| AstraZeneca Biologics | Revenue vs 12-mo run rate: 0.20x; Revenue momentum (last 3 mo vs prior 3): -100% | 65.0 |
| Berkeley Lights | Days since last rep activity: 365; Revenue momentum (last 3 mo vs prior 3): -40% | 62.2 |
| University of Pittsburgh | Backorder rate (6 mo): 72%; Revenue momentum (last 3 mo vs prior 3): -80% | 61.7 |

Answer:

> The **5 accounts with the highest risk scores** are:
> - **Massachusetts General Hospital** — **66.7**; top risk driver: Revenue vs 12-month run rate at **0.33x** and revenue momentum down **95%**
> - **SAIC Life Sciences** — **65.8**; top risk driver: **46%** backorder rate over 6 months and **198** days since last rep activity
> - **AstraZeneca Biologics** — **65.0**; top risk driver: Revenue vs 12-month run rate at **0.20x** and revenue momentum down **100%**
> - **Berkeley Lights** — **62.2**; top risk driver: **365** days since last rep activity and revenue momentum down **40%**
> - **University of Pittsburgh** — **61.7**; top risk driver: **72%** backorder rate over 6 months and revenue momentum down **80%**
> Across these five accounts, the main risk themes are sharp revenue declines, elevated backorder rates, and long gaps in sales activity.

Check: the top 5 accounts and their drivers match `account_risk_summary` (the same drivers written to Salesforce): True.

Cross-check against the scored table: High accounts = 11, expected revenue at risk for High accounts = 7,621,239.00.
