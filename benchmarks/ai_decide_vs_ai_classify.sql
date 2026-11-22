-- ai_decide vs ai_classify benchmark (5 demo accounts)
-- Result path note: ai_decide returns VARIANT at response:answers:<question>:<field>

WITH demo AS (
  SELECT account_name, ml_risk_score, risk_category,
    CONCAT('Account: ', account_name, ' | Risk Score: ', ml_risk_score, '/100 (', risk_category, ')',
      ' | Days Inactive: ', days_since_last_activity, ' | Backorder: ', pct_qty_backordered, '%',
      ' | Open Cases: ', open_case_count, ' | Pipeline: $', FORMAT_NUMBER(open_pipeline_value, 0),
      ' | Revenue: $', FORMAT_NUMBER(annual_revenue, 0), ' | Top Driver: ', top_risk_driver) AS content_str
  FROM main.ccg_workshop_cdm.account_briefing
  WHERE account_name IN ('University of Pittsburgh','Merck Life Sciences','Moderna Therapeutics',
                         'Rush University Medical Center','Austin Medical Center')
),
decided AS (
  SELECT *, ai_decide(content_str,
    '{"action_type":{"type":"choice","instructions":"What action should the rep take?","criteria":{"re_engage":"Going dark","escalate_ops":"Ops issues","protect_pipeline":"Pipeline at risk","expand_relationship":"Healthy, grow","routine_checkin":"Stable"}},
      "urgency":{"type":"score","instructions":"How urgently?","criteria":["Routine","Low","Medium","High","Critical"]},
      "needs_exec_attention":{"type":"noul","instructions":"Needs executive escalation?"}}') AS d
  FROM demo
)
SELECT account_name, ml_risk_score, risk_category,
  d:response:answers:action_type:choice::STRING                       AS decide_action,
  ROUND(d:response:answers:action_type:confidence::DOUBLE, 2)         AS decide_confidence,
  ROUND(d:response:answers:urgency:score::DOUBLE, 1)                  AS decide_urgency,
  ROUND(d:response:answers:needs_exec_attention:probability::DOUBLE, 2) AS decide_exec_prob,
  ai_classify(content_str, ARRAY('re_engage','escalate_ops','protect_pipeline','expand_relationship','routine_checkin')) AS classify_action
FROM decided
ORDER BY ml_risk_score DESC;
