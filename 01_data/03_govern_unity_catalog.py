# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # Govern the Data Journey in Unity Catalog
# MAGIC
# MAGIC One governance layer covers every stage: the Lakeflow-ingested Salesforce tables, the gold Customer 360 table, the ML model, the AI briefings, the metric view behind Genie and the dashboard, and the Lakebase synced table behind the app.
# MAGIC
# MAGIC This notebook makes that governance visible and repeatable:
# MAGIC 1. **Classify**: tag every table by journey stage, data classification, and owning domain; tag revenue columns as confidential.
# MAGIC 2. **Document**: business comments on the tables reps and analysts use.
# MAGIC 3. **Prove the journey is connected**: lineage captured automatically by Unity Catalog, from ingestion to the app.
# MAGIC 4. **Show access**: grants on the schema and serving tables, the model registry and its promotion alias, and the secret scope (key names only).

# COMMAND ----------

# DBTITLE 1,Config
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
S = cfg.SCHEMA
STAGES = {   # table -> (journey stage, description)
    "sf_account": ("1-ingest", "Salesforce accounts ingested by Lakeflow Connect"),
    "sf_opportunity": ("1-ingest", "Salesforce opportunities ingested by Lakeflow Connect"),
    "sf_case": ("1-ingest", "Salesforce support cases ingested by Lakeflow Connect"),
    "sf_task": ("1-ingest", "Salesforce rep activities ingested by Lakeflow Connect"),
    "sf_contact": ("1-ingest", "Salesforce contacts ingested by Lakeflow Connect"),
    "cur_sales_order_header": ("1-ingest", "Synthetic ERP order headers"),
    "cur_sales_order_line": ("1-ingest", "Synthetic ERP order lines with promise dates"),
    "cur_shipment_line": ("1-ingest", "Synthetic shipments with backordered quantity"),
    "customer_360": ("2-curate", "Gold account view joining CRM and order health (Lakeflow Declarative Pipeline)"),
    "syn_account_monthly_history": ("3-intelligence", "SYNTHETIC training history for the risk model"),
    "account_risk_summary": ("3-intelligence", "Current model risk score, probability, category and drivers per account"),
    "account_risk_predictions": ("3-intelligence", "Append-only history of every scoring run"),
    "account_deep_insights": ("3-intelligence", "Revenue trend, delivery reliability, peer benchmarks, expected revenue at risk"),
    "account_briefing_v2": ("3-intelligence", "AI briefing: ai_decide action and urgency, number-checked ai_query recommendations"),
}
CONFIDENTIAL_COLUMNS = {"account_risk_summary": ["annual_revenue", "open_pipeline_value"],
                        "account_deep_insights": ["annual_revenue", "revenue_at_risk"],
                        "customer_360": ["annual_revenue", "open_pipeline_value"]}
print(f"Governing {len(STAGES)} tables in {S}")

# COMMAND ----------

# DBTITLE 1,Classify and document every stage
# data_classification is a governed tag in this workspace (allowed: public, internal, confidential, pii, restricted),
# so classification uses it; the synthetic origin of the data is recorded in a separate tag.
for t, (stage, desc) in STAGES.items():
    spark.sql(f"ALTER TABLE {S}.{t} SET TAGS ('journey_stage' = '{stage}', 'data_classification' = 'internal', 'data_origin' = 'synthetic', 'owner_domain' = 'commercial_sales')")
    if t != "customer_360":   # the pipeline owns its materialized view comment
        spark.sql(f"COMMENT ON TABLE {S}.{t} IS '{desc}'")
for t, cols in CONFIDENTIAL_COLUMNS.items():
    for c in cols:
        spark.sql(f"ALTER TABLE {S}.{t} ALTER COLUMN {c} SET TAGS ('data_classification' = 'confidential')")

display(spark.sql(f"""
  SELECT table_name, MAX(CASE WHEN tag_name = 'journey_stage' THEN tag_value END) AS journey_stage,
         MAX(CASE WHEN tag_name = 'data_classification' THEN tag_value END) AS classification,
         MAX(CASE WHEN tag_name = 'data_origin' THEN tag_value END) AS origin,
         MAX(CASE WHEN tag_name = 'owner_domain' THEN tag_value END) AS owner_domain
  FROM {S.split('.')[0]}.information_schema.table_tags
  WHERE schema_name = '{S.split('.')[1]}' AND table_name IN ({", ".join(f"'{t}'" for t in STAGES)})
  GROUP BY table_name ORDER BY journey_stage, table_name"""))
display(spark.sql(f"""
  SELECT table_name, column_name, tag_value AS data_classification FROM {S.split('.')[0]}.information_schema.column_tags
  WHERE schema_name = '{S.split('.')[1]}' AND tag_name = 'data_classification' ORDER BY table_name, column_name"""))

# COMMAND ----------

# DBTITLE 1,Prove the journey is connected - Unity Catalog lineage
lineage = spark.sql(f"""
  SELECT source_table_full_name AS source, target_table_full_name AS target,
         COALESCE(entity_type, 'QUERY') AS written_by, MAX(event_time) AS last_seen
  FROM system.access.table_lineage
  WHERE event_date >= current_date() - INTERVAL 30 DAYS
    AND source_table_full_name IS NOT NULL AND target_table_full_name IS NOT NULL
    AND source_table_full_name <> target_table_full_name
    AND target_table_full_name IN ('{S}.customer_360', '{S}.account_risk_summary', '{S}.account_deep_insights',
                                   '{S}.account_briefing_v2', '{S}.mv_customer_360',
                                   {", ".join(f"'{t}'" for t in cfg.SYNCED_TABLES.values())})
    AND source_table_full_name RLIKE '{S}\\.(sf_|cur_|customer_360|account_risk_summary|account_deep_insights|account_briefing_v2|sf_cdm_key_mapping)'
  GROUP BY ALL ORDER BY target, source""")
display(lineage)
edges = {(r.source.split(".")[-1], r.target.split(".")[-1]) for r in lineage.collect()}
chain = [("sf_account", "customer_360"), ("cur_sales_order_line", "customer_360"), ("customer_360", "account_risk_summary"),
         ("account_risk_summary", "account_deep_insights"), ("account_deep_insights", "account_briefing_v2"),
         ("account_risk_summary", "mv_customer_360"), ("account_risk_summary", "account_risk_summary")]
for a, b in chain[:-1]:
    print(f"  {a:24s} -> {b:24s} {'captured' if (a, b) in edges else 'MISSING'}")
targets = {r.target for r in lineage.collect()}
for src, synced in cfg.SYNCED_TABLES.items():   # every table the app reads from Lakebase
    print(f"  {src:24s} -> {'lakebase ' + synced.split('.')[-1]:24s} {'captured' if synced in targets else 'MISSING'}")

# COMMAND ----------

# DBTITLE 1,Access: grants, model registry, secret scope
display(spark.sql(f"SHOW GRANTS ON SCHEMA {S}"))
display(spark.sql(f"SHOW GRANTS ON TABLE {S}.account_risk_summary"))

import mlflow
mlflow.set_registry_uri("databricks-uc")
client = mlflow.MlflowClient()
champ = client.get_model_version_by_alias(cfg.MODEL_NAME, "champion")
versions = sorted(client.search_model_versions(f"name = '{cfg.MODEL_NAME}'"), key=lambda v: int(v.version))
print(f"\nModel {cfg.MODEL_NAME}: {len(versions)} versions, champion = v{champ.version}")
print(f"  champion tags: {champ.tags}")
print(f"  champion description: {champ.description}")

print(f"\nSecret scope '{cfg.SECRET_SCOPE}' keys (names only, values never printed): {[s.key for s in dbutils.secrets.list(cfg.SECRET_SCOPE)]}")