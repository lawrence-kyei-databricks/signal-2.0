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

SQL Genie generated:

```sql
WITH `ranked_accounts` AS (
  SELECT
    `Account Name`,
    MEASURE(`Avg Risk Score`) AS `risk_score`,
    `Risk Category`,
    `Is Stale`,
    `Has Escalations`,
    `Has Backorders`,
    MEASURE(`Avg Days Since Activity`) AS `avg_days_since_activity`,
    MEASURE(`Open Cases`) AS `open_cases`,
    MEASURE(`Escalated Cases`) AS `escalated_cases`,
    MEASURE(`Backorder Lines`) AS `backorder_lines`,
    RANK() OVER (ORDER BY MEASURE(`Avg Risk Score`) DESC) AS `risk_rank`
  FROM `main`.`ccg_workshop_cdm`.`mv_customer_360`
  WHERE `Account Name` IS NOT NULL
  GROUP BY ALL
)
SELECT
  `Account Name`,
  `risk_score`,
  `Risk Category`,
  CASE
    WHEN `Has Escalations` = true AND `Has Backorders` = true AND `Is Stale` = true THEN 'Escalations, Backorders, and Stale Activity'
    WHEN `Has Escalations` = true AND `Has Backorders` = true THEN 'Escalations and Backorders'
    WHEN `Has Escalations` = true AND `Is Stale` = true THEN 'Escalations and Stale Activity'
    WHEN `Has Backorders` = true AND `Is Stale` = true THEN 'Backorders and Stale Activity'
    WHEN `Has Escalations` = true THEN 'Escalations'
    WHEN `Has Backorders` = true THEN 'Backorders'
    WHEN `Is Stale` = true THEN 'Stale Activity'
    ELSE 'No explicit driver field available'
  END AS `top_risk_driver`,
  `avg_days_since_activity`,
  `open_cases`,
  `escalated_cases`,
  `backorder_lines`
FROM `ranked_accounts`
WHERE `risk_rank` <= 5
ORDER BY `risk_rank` ASC, `Account Name` ASC;
```

Result:

| Account Name | risk_score | Risk Category | top_risk_driver | avg_days_since_activity | open_cases | escalated_cases | backorder_lines |
|---|---|---|---|---|---|---|---|
| Massachusetts General Hospital | 66.7 | High | Backorders | 23.0 | 2 | 0 | 9 |
| SAIC Life Sciences | 65.8 | High | Backorders and Stale Activity | 198.0 | 1 | 0 | 5 |
| AstraZeneca Biologics | 65.0 | High | Backorders and Stale Activity | 157.0 | 1 | 0 | 7 |
| Berkeley Lights | 62.2 | High | Backorders and Stale Activity | 365.0 | 4 | 0 | 1 |
| University of Pittsburgh | 61.7 | High | Backorders and Stale Activity | 94.0 | 2 | 0 | 9 |

Answer:

> The **5 accounts with the highest risk scores** are listed below, along with the top risk driver identified in the results:
> 
> - **Massachusetts General Hospital** — risk score **66.7**; top risk driver: **Backorders**
> - **SAIC Life Sciences** — risk score **65.8**; top risk driver: **Backorders and Stale Activity**
> - **AstraZeneca Biologics** — risk score **65.0**; top risk driver: **Backorders and Stale Activity**
> - **Berkeley Lights** — risk score **62.2**; top risk driver: **Backorders and Stale Activity**
> - **University of Pittsburgh** — risk score **61.7**; top risk driver: **Backorders and Stale Activity**
> 
> Across all 5 accounts shown, **all are in the High risk category**, and **4 of the 5** include **stale activity plus backorders** as the top risk driver.

Cross-check against the scored table: High accounts = 11, expected revenue at risk for High accounts = 7,621,239.00.
