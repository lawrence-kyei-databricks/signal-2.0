# Databricks notebook source
# MAGIC %md
# MAGIC # Ingest Salesforce CRM with Lakeflow Connect
# MAGIC
# MAGIC **Stage 1 of the journey.** The CRM side of the account picture (accounts, contacts, opportunities, support cases, rep activities) lives in Salesforce. A managed Lakeflow Connect pipeline pulls those five objects into Unity Catalog incrementally, with no custom connector code. The order and shipment side comes from the synthetic ERP tables (`cur_*`).
# MAGIC
# MAGIC - **Pipeline definition:** `salesforce_ingestion/pipeline_spec.json` (connection `ccg-salesforce-dev`, OAuth managed by Unity Catalog)
# MAGIC - **Lands in:** `main.ccg_workshop_cdm.sf_account`, `sf_contact`, `sf_opportunity`, `sf_case`, `sf_task`
# MAGIC - **Next:** the Customer 360 Lakeflow Declarative Pipeline (`customer_360_pipeline/`) joins these with the ERP tables
# MAGIC
# MAGIC The CRM records were seeded once with `01_generate_crm_data` and `02_load_salesforce`. Those two notebooks are not re-run, because reloading would give every account a new Salesforce ID.

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
import json, time
from databricks.sdk import WorkspaceClient
w = WorkspaceClient()
PIPELINE_NAME = "CCG Salesforce Ingestion"
pid = next(p.pipeline_id for p in w.pipelines.list_pipelines(filter=f"name LIKE '{PIPELINE_NAME}'"))
spec = w.api_client.do("GET", f"/api/2.0/pipelines/{pid}")["spec"]
committed = json.load(open(os.path.join(NB_DIR, "salesforce_ingestion", "pipeline_spec.json")))
assert spec["ingestion_definition"] == committed["ingestion_definition"], "Deployed pipeline differs from the committed definition"
print(f"Pipeline '{PIPELINE_NAME}' ({pid}) matches the committed definition")
for o in spec["ingestion_definition"]["objects"]:
    t = o["table"]
    print(f"  Salesforce {t['source_table']:12s} -> {t['destination_catalog']}.{t['destination_schema']}.{t['destination_table']}")

# COMMAND ----------

# DBTITLE 1,Run an incremental ingestion update
before = {o["table"]["destination_table"]: spark.table(f"{cfg.SCHEMA}.{o['table']['destination_table']}").count()
          for o in spec["ingestion_definition"]["objects"]}
update_id = w.pipelines.start_update(pipeline_id=pid).update_id
started = time.time()
for _ in range(120):
    state = w.pipelines.get_update(pipeline_id=pid, update_id=update_id).update.state.value
    if state in ("COMPLETED", "FAILED", "CANCELED"):
        break
    time.sleep(10)
print(f"Lakeflow Connect update {update_id}: {state} in {time.time() - started:.0f}s")
assert state == "COMPLETED", f"Ingestion ended in state {state}"

# COMMAND ----------

# DBTITLE 1,What landed in Unity Catalog
rows = []
for o in spec["ingestion_definition"]["objects"]:
    t = o["table"]["destination_table"]
    df = spark.table(f"{cfg.SCHEMA}.{t}")
    rows.append((o["table"]["source_table"], t, before[t], df.count(), df.agg({"SystemModstamp": "max"}).first()[0]))
display(spark.createDataFrame(rows, "salesforce_object string, uc_table string, rows_before long, rows_after long, latest_salesforce_change timestamp"))

history = [(u.update_id, u.state.value, u.creation_time) for u in w.pipelines.list_updates(pipeline_id=pid, max_results=5).updates]
print("Recent ingestion updates:")
for uid, st, ct in history:
    print(f"  {uid}  {st:10s} {time.strftime('%Y-%m-%d %H:%M', time.gmtime(ct / 1000))} UTC")
