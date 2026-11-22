# Databricks notebook source
# MAGIC %md
# MAGIC # Signal Account Cockpit - Demo Reset / Cleanup Utility
# MAGIC
# MAGIC Operational utility for the Lakebase operational schema. Two jobs:
# MAGIC
# MAGIC 1. **Purge test artifacts** - rows written by endpoint smoke tests
# MAGIC    (`sf_account_id` values that do not exist in the synced risk table).
# MAGIC 2. **Reset demo state** - optionally clear all rep actions so the
# MAGIC    worklist shows every alert as `new` before a live walkthrough.
# MAGIC
# MAGIC Run this as the project owner. The **app's service principal cannot do
# MAGIC this** - it holds `SELECT`/`INSERT` only, with no `DELETE`. That is the
# MAGIC point: the running application can never erase a rep decision or an
# MAGIC audit record. Cleanup is a deliberate, separately-privileged act.
# MAGIC
# MAGIC Set `full_reset` to `true` only when you want a clean demo slate.

# COMMAND ----------

# MAGIC %pip install "databricks-sdk>=0.169.0" "psycopg[binary]>=3.3.9" --quiet
# MAGIC %restart_python

# COMMAND ----------

# DBTITLE 1,Parameters
dbutils.widgets.dropdown("full_reset", "false", ["false", "true"],
                         "Clear ALL rep actions (demo reset)")
FULL_RESET = dbutils.widgets.get("full_reset") == "true"
print(f"full_reset = {FULL_RESET}")

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
from databricks.sdk import WorkspaceClient
import psycopg
from datetime import datetime, timezone

PROJECT  = cfg.LAKEBASE_PROJECT
BRANCH   = cfg.LAKEBASE_BRANCH
ENDPOINT = cfg.LAKEBASE_ENDPOINT
REPORT = []
def log(line=""):
    print(line)
    REPORT.append(str(line))

w = WorkspaceClient()
PG_USER = w.current_user.me().user_name
PG_HOST = w.postgres.get_endpoint(name=ENDPOINT).status.hosts.host


def connect():
    token = w.postgres.generate_database_credential(endpoint=ENDPOINT).token
    return psycopg.connect(host=PG_HOST, dbname="databricks_postgres",
                           user=PG_USER, password=token, sslmode="require")


log("=" * 66)
log("LAKEBASE DEMO RESET / CLEANUP")
log(f"run at     : {datetime.now(timezone.utc).isoformat()}")
log(f"as         : {PG_USER}")
log(f"full_reset : {FULL_RESET}")
log("=" * 66)

# COMMAND ----------

# DBTITLE 1,Before state
with connect() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM cockpit_app.rep_actions")
        before_actions = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cockpit_app.action_audit")
        before_audit = cur.fetchone()[0]

        # Orphans: actions whose account is not in the synced risk table.
        cur.execute("""
            SELECT r.action_id, r.sf_account_id, r.account_name
            FROM cockpit_app.rep_actions r
            LEFT JOIN cockpit.account_risk_summary s
                   ON s.sf_account_id = r.sf_account_id
            WHERE s.sf_account_id IS NULL
            ORDER BY r.action_id
        """)
        orphans = cur.fetchall()

log()
log(f"rep_actions  : {before_actions}")
log(f"action_audit : {before_audit}")
log(f"orphan rows  : {len(orphans)} (account not present in synced risk table)")
for a_id, acct, name in orphans:
    log(f"   action_id={a_id} {acct} ({name})")

# COMMAND ----------

# DBTITLE 1,Purge test artifacts, and optionally reset all demo state
with connect() as conn:
    conn.autocommit = False
    with conn.cursor() as cur:
        if FULL_RESET:
            cur.execute("DELETE FROM cockpit_app.action_audit")
            audit_deleted = cur.rowcount
            cur.execute("DELETE FROM cockpit_app.rep_actions")
            actions_deleted = cur.rowcount
            scope = "ALL rep actions and audit rows"
        else:
            # Audit first - it references action_id.
            cur.execute("""
                DELETE FROM cockpit_app.action_audit
                WHERE action_id IN (
                    SELECT r.action_id
                    FROM cockpit_app.rep_actions r
                    LEFT JOIN cockpit.account_risk_summary s
                           ON s.sf_account_id = r.sf_account_id
                    WHERE s.sf_account_id IS NULL
                )
            """)
            audit_deleted = cur.rowcount
            cur.execute("""
                DELETE FROM cockpit_app.rep_actions
                WHERE sf_account_id NOT IN (
                    SELECT sf_account_id FROM cockpit.account_risk_summary
                )
            """)
            actions_deleted = cur.rowcount
            scope = "orphan/test rows only"
    conn.commit()

log()
log(f"-- DELETED ({scope}) --")
log(f"  action_audit : {audit_deleted}")
log(f"  rep_actions  : {actions_deleted}")

# COMMAND ----------

# DBTITLE 1,After state
with connect() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM cockpit_app.rep_actions")
        after_actions = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cockpit_app.action_audit")
        after_audit = cur.fetchone()[0]
        cur.execute("""
            SELECT COUNT(*)
            FROM cockpit_app.rep_actions r
            LEFT JOIN cockpit.account_risk_summary s
                   ON s.sf_account_id = r.sf_account_id
            WHERE s.sf_account_id IS NULL
        """)
        orphans_left = cur.fetchone()[0]

        cur.execute("""
            SELECT COALESCE(a.action, 'new') AS state, COUNT(*) AS n
            FROM cockpit.account_risk_summary s
            LEFT JOIN LATERAL (
                SELECT action FROM cockpit_app.rep_actions r
                WHERE r.sf_account_id = s.sf_account_id
                ORDER BY r.created_at DESC LIMIT 1
            ) a ON TRUE
            GROUP BY 1 ORDER BY n DESC
        """)
        states = cur.fetchall()

log()
log("-- AFTER --")
log(f"  rep_actions  : {before_actions} -> {after_actions}")
log(f"  action_audit : {before_audit} -> {after_audit}")
log(f"  orphans left : {orphans_left}")
log()
log("worklist alert states across the 200 synced accounts:")
for state, n in states:
    log(f"  {state:12s} {n:4d}")

assert orphans_left == 0, f"{orphans_left} orphan rows remain"

log()
log("=" * 66)
log("PASS - no test artifacts remain in the operational schema")
log("=" * 66)

dbutils.notebook.exit("\n".join(REPORT))
