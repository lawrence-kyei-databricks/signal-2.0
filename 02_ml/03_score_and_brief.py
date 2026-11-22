# Databricks notebook source
# DBTITLE 1,Overview
# MAGIC %md
# MAGIC # CCG Account Risk - Scoring and AI Briefing
# MAGIC
# MAGIC The production refresh for Signal 2.0. Run after `02_train_risk_model`; scheduled by the refresh job in `06_orchestration`.
# MAGIC
# MAGIC 1. **Score** every real account with `account_risk_model@champion`: probability that revenue over the next 6 months falls below 60% of its run rate. Features come from real `cur_*` and `sf_*` data as of the data snapshot date, using the same `ccg_risk_features.py` code as training.
# MAGIC 2. **Explain**: top 2 drivers per account from the model itself (coefficient x standardized value).
# MAGIC 3. **Insights**: revenue trend, delivery reliability, peer benchmarks, and expected revenue at risk (annual revenue x probability), all anchored to the snapshot date.
# MAGIC 4. **Briefing**: `ai_decide` picks action type, urgency, and exec attention; `ai_query` writes 3 recommendations grounded in the model's drivers.
# MAGIC 5. **Salesforce**: JSON briefing to `Account.Description` (VF popup) plus `Risk_Score__c`, `Risk_Category__c`, `Last_Risk_Assessment__c` for reports.
# MAGIC 6. **Lakebase**: refresh the synced table so the Signal Cockpit app serves the new scores, then verify it matches Delta.
# MAGIC
# MAGIC **Outputs:** `account_risk_predictions` (append, history of every scoring run), `account_risk_summary`, `account_deep_insights`, `account_briefing`, `account_briefing_v2` (column names unchanged for the dashboard, Genie, and VF page).

# COMMAND ----------

# DBTITLE 1,Configuration
import os, sys, json
import mlflow
import numpy as np
import pandas as pd
import requests
from mlflow import MlflowClient
from pyspark.sql import functions as F

# Repo bootstrap: make signal_config (repo root) and sibling modules importable wherever the repo is checked out
import os, sys, importlib
NB_DIR = "/Workspace" + os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()).replace("/Workspace", "", 1)
REPO_ROOT = os.path.dirname(NB_DIR)
for _p in (NB_DIR, REPO_ROOT):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)
importlib.invalidate_caches()
import signal_config as cfg
importlib.reload(cfg)
import ccg_risk_features as rf
importlib.reload(rf)

mlflow.set_registry_uri("databricks-uc")
SCHEMA = cfg.SCHEMA
MODEL_NAME = cfg.MODEL_NAME

snap = spark.sql(f"""SELECT MAX(date_ordr_accepted) AS snapshot_date, LAST_DAY(MAX(date_ordr_accepted)) AS as_of
                     FROM {SCHEMA}.cur_sales_order_header""").first()
SNAPSHOT_DATE, AS_OF = snap.snapshot_date, snap.as_of      # windows are anchored to the data, not today's date
CUTOFF_MONTH = pd.Timestamp(AS_OF).replace(day=1)

champion = MlflowClient().get_model_version_by_alias(MODEL_NAME, "champion")
MODEL_VERSION = champion.version
assert champion.tags.get("output") == "probability", "Champion is not the forward-looking probability model"
print(f"Data snapshot {SNAPSHOT_DATE} | scoring as of {AS_OF} | {MODEL_NAME} v{MODEL_VERSION} (champion)")

# COMMAND ----------

# DBTITLE 1,Score Accounts with Champion Model
model = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}@champion")

real_monthly = spark.sql(rf.REAL_MONTHLY_SCORING_SQL).toPandas()
X = rf.compute_features(real_monthly, CUTOFF_MONTH, AS_OF)
prob = model.predict_proba(X[rf.FEATURES])[:, 1]
drivers, _ = rf.top_drivers(model, X)

scored = X.assign(risk_probability=prob, risk_category=rf.risk_category(prob), top_risk_driver=drivers)
mapping = spark.table(f"{SCHEMA}.sf_cdm_key_mapping").select("sf_account_id", "customer_shipto_key").toPandas()
scored = scored.merge(mapping, on="customer_shipto_key", how="inner")
assert len(scored) == scored.sf_account_id.nunique() == 200, "Expected one scored row per account"

spark.createDataFrame(scored[["sf_account_id", "customer_shipto_key", "risk_probability", "risk_category", "top_risk_driver"] + rf.FEATURES]) \
    .withColumn("ml_risk_score", F.round(F.col("risk_probability") * 100, 1)) \
    .withColumn("model_version", F.lit(str(MODEL_VERSION))) \
    .withColumn("snapshot_date", F.lit(SNAPSHOT_DATE)) \
    .withColumn("scored_at", F.current_timestamp()) \
    .createOrReplaceTempView("scored_now")

# 1. Prediction history (append): one row per account per scoring run
spark.table("scored_now").write.mode("append").option("mergeSchema", "true").saveAsTable(f"{SCHEMA}.account_risk_predictions")

# 2. Current summary, same columns consumers already use (+ probability, version, snapshot)
spark.sql(f"""
CREATE OR REPLACE TABLE {SCHEMA}.account_risk_summary
COMMENT 'Current account risk from {MODEL_NAME} v{MODEL_VERSION}: ml_risk_score = 100 x P(next-6-month revenue < 60% of run rate). Refreshed by notebook 05.'
AS SELECT
  s.sf_account_id, c.account_name, s.ml_risk_score, s.risk_category,
  CAST(s.days_since_last_activity AS INT) AS days_since_last_activity,
  CAST(ROUND(s.backorder_rate_6m * 100, 1) AS DECIMAL(4,1)) AS pct_qty_backordered,
  c.open_pipeline_value, c.annual_revenue, c.open_case_count,
  s.top_risk_driver, ROUND(s.risk_probability, 4) AS risk_probability, s.model_version, s.snapshot_date
FROM scored_now s JOIN {SCHEMA}.customer_360 c ON s.sf_account_id = c.sf_account_id
""")

summary = spark.table(f"{SCHEMA}.account_risk_summary")
print(f"Scored {summary.count()} accounts with v{MODEL_VERSION}:", {r.risk_category: r["count"] for r in summary.groupBy("risk_category").count().collect()})
display(summary.orderBy(F.desc("ml_risk_score")).limit(15))

# COMMAND ----------

# DBTITLE 1,Deep Insights (anchored to snapshot)
spark.sql(f"""
CREATE OR REPLACE TABLE {SCHEMA}.account_deep_insights
COMMENT 'Revenue trend, delivery reliability, peer benchmarks and expected revenue at risk, anchored to the data snapshot date. Refreshed by notebook 05.'
AS
WITH snap AS (SELECT DATE'{SNAPSHOT_DATE}' AS d),
lines AS (
  SELECT h.customer_shipto_key, h.date_ordr_accepted dt, h.sales_order_header_key o, l.qty_ordered * l.unit_price v,
         l.date_ordr_line_prmsd pr, l.date_ordr_line_prmsd_orig pro
  FROM {SCHEMA}.cur_sales_order_header h JOIN {SCHEMA}.cur_sales_order_line l USING (sales_order_header_key), snap
  WHERE h.date_ordr_accepted <= snap.d),
trend AS (
  SELECT customer_shipto_key,
    SUM(CASE WHEN dt > DATE_SUB(snap.d, 90) THEN v ELSE 0 END) rev_last_90d,
    SUM(CASE WHEN dt > DATE_SUB(snap.d, 180) AND dt <= DATE_SUB(snap.d, 90) THEN v ELSE 0 END) rev_prior_90d,
    COUNT(DISTINCT CASE WHEN dt > DATE_SUB(snap.d, 90) THEN o END) orders_last_90d,
    COUNT(DISTINCT CASE WHEN dt > DATE_SUB(snap.d, 180) AND dt <= DATE_SUB(snap.d, 90) THEN o END) orders_prior_90d,
    CAST(ROUND(100.0 * AVG(CASE WHEN dt > DATE_SUB(snap.d, 180) AND pr IS NOT NULL AND pro IS NOT NULL
                                THEN CASE WHEN pr > pro THEN 1 ELSE 0 END END), 1) AS DECIMAL(26,1)) pct_delivery_pushed,
    ROUND(AVG(CASE WHEN dt > DATE_SUB(snap.d, 180) AND pr > pro THEN DATEDIFF(pr, pro) END), 1) avg_days_pushed
  FROM lines, snap GROUP BY customer_shipto_key),
base AS (
  SELECT r.*, m.customer_shipto_key, a.Industry AS industry
  FROM {SCHEMA}.account_risk_summary r
  JOIN {SCHEMA}.sf_cdm_key_mapping m ON r.sf_account_id = m.sf_account_id
  JOIN {SCHEMA}.sf_account a ON r.sf_account_id = a.Id),
peers AS (
  SELECT industry, ROUND(AVG(ml_risk_score), 1) industry_avg_risk, CAST(ROUND(AVG(pct_qty_backordered), 1) AS DECIMAL(5,1)) industry_avg_backorder,
         ROUND(AVG(days_since_last_activity), 0) industry_avg_inactivity, COUNT(*) industry_peer_count
  FROM base GROUP BY industry),
portfolio AS (SELECT ROUND(AVG(ml_risk_score), 1) portfolio_avg_risk FROM base)
SELECT
  b.sf_account_id, b.account_name, b.ml_risk_score, b.risk_category, b.risk_probability, b.model_version, b.industry,
  ROUND(t.rev_last_90d, 0) rev_last_90d, ROUND(t.rev_prior_90d, 0) rev_prior_90d,
  CASE WHEN t.rev_prior_90d > 0 THEN ROUND(100.0 * (t.rev_last_90d - t.rev_prior_90d) / t.rev_prior_90d, 1) END rev_trend_pct,
  t.orders_last_90d, t.orders_prior_90d, t.pct_delivery_pushed, t.avg_days_pushed,
  p.industry_avg_risk, p.industry_avg_backorder, p.industry_avg_inactivity, p.industry_peer_count,
  ROUND(b.ml_risk_score - p.industry_avg_risk, 1) risk_vs_industry,
  pf.portfolio_avg_risk, ROUND(b.ml_risk_score - pf.portfolio_avg_risk, 1) risk_vs_portfolio,
  ROUND(b.annual_revenue * b.risk_probability, 0) revenue_at_risk,
  b.annual_revenue, b.days_since_last_activity, b.pct_qty_backordered, b.open_pipeline_value, b.open_case_count,
  b.top_risk_driver, b.snapshot_date
FROM base b
LEFT JOIN trend t ON b.customer_shipto_key = t.customer_shipto_key
LEFT JOIN peers p ON b.industry = p.industry
CROSS JOIN portfolio pf
""")

ins = spark.table(f"{SCHEMA}.account_deep_insights")
print(f"{ins.count()} rows | accounts with 90-day revenue > 0: {ins.filter('rev_last_90d > 0').count()} | total expected revenue at risk: ${ins.agg(F.sum('revenue_at_risk')).first()[0]:,.0f}")

# COMMAND ----------

# DBTITLE 1,AI Briefing (ai_decide + ai_query, number-checked)
DECIDE_QUESTIONS = json.dumps({
    "action_type": {"type": "choice", "instructions": "What should the sales rep do next for this account?",
                    "criteria": {"re_engage": "Account going dark - rep activity lapsed or revenue fading",
                                 "escalate_ops": "Operational issues (backorders, delivery slips, cases) driving risk",
                                 "protect_pipeline": "Active pipeline or revenue at risk of loss",
                                 "expand_relationship": "Healthy account - pursue growth",
                                 "routine_checkin": "Stable - maintain regular cadence"}},
    "urgency": {"type": "score", "instructions": "How urgently does this account need attention?",
                "criteria": ["Routine", "Low", "Medium", "High", "Critical"]},
    "needs_exec_attention": {"type": "noul", "instructions": "Does this account warrant executive escalation?"},
})

import re

LLM = "databricks-meta-llama-3-3-70b-instruct"
RULES = ("You are a CCG commercial intelligence analyst at Thermo Fisher Scientific. "
         "Write exactly 3 numbered recommendations for the sales rep, one sentence each, most important model driver first. "
         "Rules: (1) Use only numbers from the FACTS list, written exactly as shown and attached to the same label - "
         "never move a number to a different fact. (2) Do not calculate, round, combine, or invent any number. "
         "(3) Do not set numeric targets or goals. (4) For timing, use only: within 24 hours, within 48 hours, this week, "
         "within 2 weeks, within 30 days. Format: 1. ... 2. ... 3. ...")

# 1. One clearly labeled fact per line, so the LLM cannot mix up similar figures (e.g. open cases vs high-priority cases)
spark.sql(f"""
CREATE OR REPLACE TEMP VIEW briefing_ctx AS
SELECT d.*,
  CONCAT_WS('\\n',
    CONCAT('- Account: ', account_name, ' (', COALESCE(industry, 'Unknown industry'), ')'),
    CONCAT('- Risk score: ', ml_risk_score, ' out of 100 (', risk_category, ')'),
    CONCAT('- Chance revenue falls below 60% of run rate in the next 6 months: ', CAST(ROUND(risk_probability * 100) AS INT), '%'),
    CONCAT('- Top model drivers: ', top_risk_driver),
    CONCAT('- Revenue change, last 90 days vs prior 90 days: ', COALESCE(CONCAT(rev_trend_pct, '%'), 'no revenue in prior 90 days')),
    CONCAT('- Backorder rate, last 6 months: ', pct_qty_backordered, '%'),
    CONCAT('- Deliveries with pushed promise dates, last 180 days: ', COALESCE(pct_delivery_pushed, 0), '%'),
    CONCAT('- Days since last rep activity: ', days_since_last_activity),
    CONCAT('- Open support cases: ', open_case_count),
    CONCAT('- Open pipeline: $', FORMAT_NUMBER(open_pipeline_value, 0)),
    CONCAT('- Expected revenue at risk: $', FORMAT_NUMBER(revenue_at_risk, 0)),
    CONCAT('- Risk score vs ', COALESCE(industry, 'peer'), ' average: ', risk_vs_industry, ' points (', industry_peer_count, ' peers)')
  ) AS facts
FROM {SCHEMA}.account_deep_insights d
""")

# 2. Decisions + first-pass recommendations
spark.sql(f"""
CREATE OR REPLACE TABLE {SCHEMA}.account_briefing_stage AS
WITH decided AS (SELECT *, ai_decide(facts, '{DECIDE_QUESTIONS.replace("'", "\\'")}') AS dec FROM briefing_ctx)
SELECT *,
  dec:response:answers:action_type:choice::STRING AS action_type,
  ROUND(dec:response:answers:action_type:confidence::DOUBLE, 2) AS action_confidence,
  ROUND(dec:response:answers:urgency:score::DOUBLE, 1) AS urgency_score,
  ROUND(dec:response:answers:needs_exec_attention:probability::DOUBLE, 2) AS exec_attention_prob,
  ai_query('{LLM}', CONCAT('{RULES}', '\\n\\nFACTS:\\n', facts),
           modelParameters => named_struct('temperature', CAST(0.0 AS DOUBLE), 'max_tokens', 220)) AS recommendations
FROM decided
""")

# 3. Number check: every number in a recommendation must come from that account's facts
NUM = re.compile(r"(?<![\w.])[-+]?\$?\d[\d,]*(?:\.\d+)?")
ALLOWED_TIMING = {"24", "48", "2", "30"}

def norm(tok):
    return tok.replace("$", "").replace(",", "").lstrip("+")

def bad_numbers(rec, facts):
    fact_vals = {norm(t) for t in NUM.findall(facts)}
    fact_vals |= {v.lstrip("-") for v in fact_vals}                       # "declined 88.7%" for a -88.7% fact
    text = re.sub(r"(?m)^\s*[123]\.\s", "", rec or "")                    # list markers
    text = re.sub(r"within (24|48) hours|within 2 weeks|within 30 days", "", text)
    return sorted({norm(t) for t in NUM.findall(text)} - fact_vals)

stage = spark.table(f"{SCHEMA}.account_briefing_stage").select("sf_account_id", "facts", "recommendations").toPandas()
stage["bad"] = [bad_numbers(r, f) for r, f in zip(stage.recommendations, stage.facts)]
first_pass_fail = int((stage.bad.str.len() > 0).sum())

# 4. Regenerate failures once, telling the model exactly which numbers were not in its facts
retry = stage[stage.bad.str.len() > 0].copy()
if len(retry):
    retry["feedback"] = retry.bad.apply(lambda b: "Your previous answer used numbers not in FACTS: " + ", ".join(b) + ". Remove them.")
    spark.createDataFrame(retry[["sf_account_id", "facts", "feedback"]]).createOrReplaceTempView("briefing_retry")
    fixed = spark.sql(f"""SELECT sf_account_id, ai_query('{LLM}', CONCAT('{RULES}', '\\n', feedback, '\\n\\nFACTS:\\n', facts),
                          modelParameters => named_struct('temperature', CAST(0.0 AS DOUBLE), 'max_tokens', 220)) AS recommendations
                          FROM briefing_retry""").toPandas()
    stage = stage.drop(columns="recommendations").merge(
        pd.concat([stage[~stage.sf_account_id.isin(fixed.sf_account_id)][["sf_account_id", "recommendations"]], fixed]), on="sf_account_id")
    stage["bad"] = [bad_numbers(r, f) for r, f in zip(stage.recommendations, stage.facts)]

stage["numbers_verified"] = stage.bad.str.len() == 0
spark.createDataFrame(stage[["sf_account_id", "recommendations", "numbers_verified"]]).createOrReplaceTempView("briefing_final_recs")
print(f"Number check: {first_pass_fail} of {len(stage)} failed first pass | still failing after retry: {int((~stage.numbers_verified).sum())}")
if (~stage.numbers_verified).any():
    display(stage[~stage.numbers_verified][["sf_account_id", "bad", "recommendations"]])

# 5. Final briefing table (same columns as before, plus facts and the verification flag)
spark.sql(f"""
CREATE OR REPLACE TABLE {SCHEMA}.account_briefing_v2
COMMENT 'AI briefing per account: ai_decide action/urgency/exec attention + ai_query recommendations grounded in the risk model drivers, number-checked against facts. Refreshed by notebook 05.'
AS SELECT
  s.sf_account_id, s.account_name, s.ml_risk_score, s.risk_category, s.top_risk_driver,
  s.days_since_last_activity, s.pct_qty_backordered, s.open_pipeline_value, s.open_case_count, s.annual_revenue,
  s.action_type, s.action_confidence, s.urgency_score, s.exec_attention_prob,
  CASE WHEN f.numbers_verified THEN f.recommendations
       ELSE 'Recommendations withheld: generated figures did not match account data. Review the facts below.' END AS recommendations,
  s.rev_trend_pct, s.revenue_at_risk, s.risk_vs_industry, s.industry, s.industry_peer_count,
  s.pct_delivery_pushed, s.avg_days_pushed, s.risk_probability, s.model_version, s.snapshot_date,
  s.facts, f.numbers_verified, current_timestamp() AS briefing_generated_at
FROM {SCHEMA}.account_briefing_stage s JOIN briefing_final_recs f USING (sf_account_id)
""")
spark.sql(f"DROP TABLE IF EXISTS {SCHEMA}.account_briefing_stage")

# Keep the original account_briefing (16 columns) in sync for existing consumers
spark.sql(f"""CREATE OR REPLACE TABLE {SCHEMA}.account_briefing AS
  SELECT sf_account_id, account_name, ml_risk_score, risk_category, top_risk_driver, days_since_last_activity,
         pct_qty_backordered, open_pipeline_value, open_case_count, annual_revenue, action_type, action_confidence,
         urgency_score, exec_attention_prob, recommendations, briefing_generated_at
  FROM {SCHEMA}.account_briefing_v2""")

b = spark.table(f"{SCHEMA}.account_briefing_v2")
print(f"{b.count()} briefings | null action_type: {b.filter('action_type IS NULL').count()} | null recommendations: {b.filter('recommendations IS NULL').count()}")
display(b.groupBy("action_type").count().orderBy(F.desc("count")))

# COMMAND ----------

# DBTITLE 1,Write Briefings to Salesforce
from datetime import datetime, timezone
sf_url, sf_token = cfg.salesforce_session(dbutils)          # credentials from the ccg-salesforce secret scope
assessed_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
sf_headers = {"Authorization": f"Bearer {sf_token}", "Content-Type": "application/json"}

def num(v, cast=float):
    return cast(v) if v is not None else None

records = []
for r in spark.table(f"{SCHEMA}.account_briefing_v2").collect():
    payload = {
        "risk_score": num(r.ml_risk_score), "risk_probability": num(r.risk_probability), "risk_category": r.risk_category,
        "model_version": r.model_version, "snapshot_date": str(r.snapshot_date),
        "action_type": r.action_type, "action_confidence": num(r.action_confidence) or 0.0,
        "urgency_score": num(r.urgency_score) or 0.0, "exec_attention_prob": num(r.exec_attention_prob) or 0.0,
        "top_risk_driver": r.top_risk_driver, "recommendations": r.recommendations,
        "rev_trend_pct": num(r.rev_trend_pct), "revenue_at_risk": num(r.revenue_at_risk, int) or 0,
        "risk_vs_industry": num(r.risk_vs_industry) or 0.0, "industry": r.industry,
        "delivery_pushed_pct": num(r.pct_delivery_pushed) or 0.0,
    }
    records.append({"attributes": {"type": "Account"}, "Id": r.sf_account_id,
                    "Description": json.dumps(payload, ensure_ascii=False),       # read by the Signal 2.0 VF popup
                    "Risk_Score__c": num(r.ml_risk_score),                      # reportable fields (permission set Signal2_Risk_Fields)
                    "Risk_Category__c": r.risk_category,
                    "Last_Risk_Assessment__c": assessed_at})

resp = requests.patch(f"{sf_url}/services/data/v59.0/composite/sobjects", headers=sf_headers,
                      json={"records": records, "allOrNone": False})
resp.raise_for_status()
results = resp.json()
failed = [x for x in results if not x.get("success")]
print(f"Salesforce: {len(results) - len(failed)} updated, {len(failed)} failed", failed[:3] if failed else "")

# Read back two demo accounts to confirm what reps will see
q = requests.get(f"{sf_url}/services/data/v59.0/query", headers=sf_headers,
                 params={"q": "SELECT Id, Name, Description, Risk_Score__c, Risk_Category__c FROM Account WHERE Id IN ('001bm000030G3dyAAC','001bm000030G3dzAAC')"})
q.raise_for_status()
for rec in q.json()["records"]:
    d = json.loads(rec["Description"])
    print(rec["Name"], {k: d.get(k) for k in ["risk_score", "risk_category", "model_version", "action_type"]},
          "| fields:", rec["Risk_Score__c"], rec["Risk_Category__c"])
    assert rec["Risk_Score__c"] == d["risk_score"], "Risk_Score__c does not match the briefing"
# COMMAND ----------

# DBTITLE 1,Refresh Lakebase and verify the app serves the new scores
# The synced table runs in SNAPSHOT mode, so it does not follow the Delta source on its own.
# Trigger its pipeline after every rescore, then prove Lakebase matches Delta.
import time
from databricks.sdk import WorkspaceClient

w = WorkspaceClient()
synced = w.api_client.do("GET", f"/api/2.0/postgres/synced_tables/{cfg.SYNCED_TABLE}")
sync_pipeline = synced["status"]["pipeline_id"]
update_id = w.pipelines.start_update(pipeline_id=sync_pipeline).update_id
for _ in range(90):
    state = w.pipelines.get_update(pipeline_id=sync_pipeline, update_id=update_id).update.state.value
    if state in ("COMPLETED", "FAILED", "CANCELED"):
        break
    time.sleep(10)
assert state == "COMPLETED", f"Lakebase sync ended in state {state}"

parity = spark.sql(f"""
  SELECT 'delta' AS side, COUNT(*) n, ROUND(SUM(ml_risk_score), 2) score_sum, COUNT_IF(risk_category = 'High') high FROM {SCHEMA}.account_risk_summary
  UNION ALL
  SELECT 'lakebase', COUNT(*), ROUND(SUM(ml_risk_score), 2), COUNT_IF(risk_category = 'High') FROM {cfg.SYNCED_TABLE}""").collect()
d, l = parity
assert (d.n, d.score_sum, d.high) == (l.n, l.score_sum, l.high), f"Lakebase does not match Delta: {parity}"
print(f"Lakebase sync {update_id}: {state} | {l.n} rows, score sum {l.score_sum}, {l.high} High - matches Delta")
