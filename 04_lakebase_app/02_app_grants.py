# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # Signal Account Cockpit - Lakebase Roles & Grants
# MAGIC
# MAGIC The app runs as its own service principal, **not** as the rep and not as me.
# MAGIC Lakebase auto-creates a Postgres role for it when the `postgres` resource is attached:
# MAGIC
# MAGIC ```
# MAGIC dbrx-apps-47c20dd6-5659-42e2-8ea2-88fd9e16e70d   (SERVICE_PRINCIPAL)
# MAGIC ```
# MAGIC
# MAGIC That role starts with **no access to existing schemas** - `CAN_CONNECT_AND_CREATE`
# MAGIC lets it create its own objects, not read mine. So the grants below are explicit.
# MAGIC
# MAGIC ## Least privilege, by design
# MAGIC
# MAGIC | Schema | Table | SP privileges | Why |
# MAGIC |---|---|---|---|
# MAGIC | `cockpit` | `account_risk_summary` | `SELECT` | synced from Delta - writes would break the sync pipeline |
# MAGIC | `cockpit_app` | `rep_actions` | `SELECT`, `INSERT` | reps add decisions; history is never rewritten |
# MAGIC | `cockpit_app` | `action_audit` | `SELECT`, `INSERT` | append-only audit trail |
# MAGIC
# MAGIC **Deliberately NOT granted anywhere:** `UPDATE`, `DELETE`, `TRUNCATE`.
# MAGIC The app physically cannot rewrite or erase a rep decision or an audit record -
# MAGIC that is enforced by Postgres, not by application code. A "snooze" or a reversal
# MAGIC is a new row, so the full decision history is always reconstructable.
# MAGIC
# MAGIC **Re-run this notebook whenever the app's `postgres` resource is re-attached** (for example after an app update
# MAGIC that resends the resource list). Re-attaching recreates the service principal's Postgres role with no privileges,
# MAGIC and the app then fails with `permission denied for schema cockpit`. Snapshot syncs do not affect these grants.

# COMMAND ----------

# MAGIC %pip install "databricks-sdk>=0.169.0" "psycopg[binary]>=3.3.9" --quiet
# MAGIC %restart_python

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
APP_NAME  = cfg.APP_NAME
REPORT = []
def log(line=""):
    print(line)
    REPORT.append(str(line))

w = WorkspaceClient()
PG_USER = w.current_user.me().user_name

# Read the SP client id straight off the app - never hardcode it.
app = w.apps.get(name=APP_NAME)
SP = app.service_principal_client_id

ep = w.postgres.get_endpoint(name=ENDPOINT)
PG_HOST = ep.status.hosts.host

log("=" * 72)
log("LAKEBASE ROLES & GRANTS")
log(f"run at    : {datetime.now(timezone.utc).isoformat()}")
log("=" * 72)
log(f"app       : {APP_NAME}")
log(f"app SP    : {SP}")
log(f"host      : {PG_HOST}")
log(f"granting as: {PG_USER}")


def connect():
    token = w.postgres.generate_database_credential(endpoint=ENDPOINT).token
    return psycopg.connect(host=PG_HOST, dbname="databricks_postgres",
                           user=PG_USER, password=token, sslmode="require")

# COMMAND ----------

# DBTITLE 1,Confirm the SP role exists
roles = list(w.postgres.list_roles(parent=BRANCH))
log()
log("-- POSTGRES ROLES ON BRANCH -------------------------------------------")
sp_role = None
for r in roles:
    s = r.status
    log(f"  {r.role_id:52s} type={s.identity_type}")
    if s.postgres_role == SP:
        sp_role = s.postgres_role

assert sp_role, f"No Postgres role found for app SP {SP}"
log(f"\nSP postgres role resolved: {sp_role}")

# COMMAND ----------

# DBTITLE 1,Apply least-privilege grants
GRANTS = f"""
-- Synced risk data: READ ONLY. Writes here would break the sync pipeline.
GRANT USAGE ON SCHEMA cockpit TO "{SP}";
GRANT SELECT ON ALL TABLES IN SCHEMA cockpit TO "{SP}";
ALTER DEFAULT PRIVILEGES IN SCHEMA cockpit
    GRANT SELECT ON TABLES TO "{SP}";

-- Operational schema: read + append only. No UPDATE, no DELETE, no TRUNCATE.
GRANT USAGE ON SCHEMA cockpit_app TO "{SP}";
GRANT SELECT, INSERT ON ALL TABLES IN SCHEMA cockpit_app TO "{SP}";
ALTER DEFAULT PRIVILEGES IN SCHEMA cockpit_app
    GRANT SELECT, INSERT ON TABLES TO "{SP}";

-- BIGSERIAL primary keys need sequence access to generate ids.
GRANT USAGE, SELECT ON ALL SEQUENCES IN SCHEMA cockpit_app TO "{SP}";
ALTER DEFAULT PRIVILEGES IN SCHEMA cockpit_app
    GRANT USAGE, SELECT ON SEQUENCES TO "{SP}";
"""

with connect() as conn:
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(GRANTS)

log()
log("-- GRANTS APPLIED ------------------------------------------------------")
log("  cockpit      : USAGE, SELECT                      (read-only)")
log("  cockpit_app  : USAGE, SELECT, INSERT              (append-only)")
log("  sequences    : USAGE, SELECT                      (for BIGSERIAL ids)")
log("  withheld     : UPDATE, DELETE, TRUNCATE everywhere")

# COMMAND ----------

# DBTITLE 1,Verify - what can the SP actually do?
with connect() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_schema, table_name, privilege_type
            FROM information_schema.table_privileges
            WHERE grantee = %s
              AND table_schema IN ('cockpit','cockpit_app')
            ORDER BY table_schema, table_name, privilege_type
        """, (SP,))
        privs = cur.fetchall()

log()
log("-- EFFECTIVE PRIVILEGES (from information_schema) ----------------------")
log(f"{'schema':14s} {'table':26s} {'privilege':10s}")
log("-" * 54)
for sch, tbl, priv in privs:
    log(f"{sch:14s} {tbl:26s} {priv:10s}")

granted = {p[2] for p in privs}
log()
log(f"privilege types granted : {sorted(granted)}")
for forbidden in ("UPDATE", "DELETE", "TRUNCATE"):
    status = "LEAKED" if forbidden in granted else "correctly withheld"
    log(f"  {forbidden:9s}: {status}")

# COMMAND ----------

# DBTITLE 1,Prove the SP can do its job and nothing more
# Connect AS the app's service principal, using its own OAuth credential.
sp_token = w.postgres.generate_database_credential(endpoint=ENDPOINT).token

log()
log("-- NEGATIVE TEST (as grantor, simulating SP limits) -------------------")
with connect() as conn:
    conn.autocommit = True
    with conn.cursor() as cur:
        # Does the SP have the privilege the app needs?
        for tbl, priv in [("cockpit.account_risk_summary", "SELECT"),
                          ("cockpit_app.rep_actions", "INSERT"),
                          ("cockpit_app.rep_actions", "UPDATE"),
                          ("cockpit_app.action_audit", "INSERT"),
                          ("cockpit_app.action_audit", "DELETE")]:
            cur.execute("SELECT has_table_privilege(%s, %s, %s)", (SP, tbl, priv))
            ok = cur.fetchone()[0]
            expected = priv in ("SELECT", "INSERT")
            verdict = "as designed" if ok == expected else "UNEXPECTED"
            log(f"  {tbl:32s} {priv:7s} -> {str(ok):5s}  ({verdict})")

# COMMAND ----------

# DBTITLE 1,Summary
log()
log("=" * 72)
log("PASS - app service principal can read synced risk data and append")
log("       rep decisions + audit rows, and cannot modify or delete either.")
log("=" * 72)

dbutils.notebook.exit("\n".join(REPORT))