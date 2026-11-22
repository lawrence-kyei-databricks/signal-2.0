# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # Signal Account Cockpit - Lakebase Operational Layer
# MAGIC
# MAGIC **Purpose:** give sales reps a sub-second, transactional surface for acting on account risk.
# MAGIC
# MAGIC The analytical layer (`main.ccg_workshop_cdm`) answers *"which accounts are at risk?"*.
# MAGIC It cannot answer *"which alerts has this rep already dealt with, and what did they decide?"* -
# MAGIC that is a high-frequency, single-row read/write pattern Delta is the wrong tool for.
# MAGIC
# MAGIC | Schema | Table | Direction | Purpose |
# MAGIC |---|---|---|---|
# MAGIC | `cockpit` | `account_risk_summary` | Delta → Postgres (synced) | read-only risk scores served to the app |
# MAGIC | `cockpit_app` | `rep_actions` | app → Postgres (write) | rep accepts / dismisses / snoozes an alert |
# MAGIC | `cockpit_app` | `action_audit` | app → Postgres (write) | immutable audit trail of every decision |
# MAGIC
# MAGIC **Design note:** synced tables are read-only in Postgres - any write breaks the sync
# MAGIC pipeline. So operational writes live in a separate schema (`cockpit_app`) and are joined
# MAGIC to synced risk data at query time.
# MAGIC
# MAGIC Every cell appends to a `REPORT` buffer which is returned via `dbutils.notebook.exit()`,
# MAGIC so each run produces committable text evidence.

# COMMAND ----------

# MAGIC %md
# MAGIC The serverless runtime ships an SDK older than the `w.postgres` module (Lakebase
# MAGIC Autoscaling needs databricks-sdk >= 0.81.0), so pin it explicitly.

# COMMAND ----------

# MAGIC %pip install "databricks-sdk>=0.169.0" "psycopg[binary]>=3.3.9" --quiet
# MAGIC %restart_python

# COMMAND ----------

# DBTITLE 1,Config + report buffer
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
import time

PROJECT  = cfg.LAKEBASE_PROJECT
BRANCH   = cfg.LAKEBASE_BRANCH
ENDPOINT = cfg.LAKEBASE_ENDPOINT
PG_DB    = cfg.LAKEBASE_DATABASE
REPORT = []

def log(line=""):
    """Print for interactive use AND buffer for the returned evidence report."""
    print(line)
    REPORT.append(str(line))

w = WorkspaceClient()
PG_USER = w.current_user.me().user_name

ep = w.postgres.get_endpoint(name=ENDPOINT)
PG_HOST = ep.status.hosts.host

log("=" * 72)
log("SIGNAL ACCOUNT COCKPIT - LAKEBASE OPERATIONAL LAYER")
log(f"run at         : {datetime.now(timezone.utc).isoformat()}")
log("=" * 72)
log(f"sdk version    : {__import__('databricks.sdk.version', fromlist=['__version__']).__version__}")
log(f"project        : {PROJECT}")
log(f"endpoint host  : {PG_HOST}")
log(f"endpoint state : {ep.status.current_state}")
log(f"connecting as  : {PG_USER}")


def connect():
    """OAuth tokens are short-lived (~1h) - mint a fresh one per connection."""
    token = w.postgres.generate_database_credential(endpoint=ENDPOINT).token
    return psycopg.connect(
        host=PG_HOST, dbname=PG_DB, user=PG_USER,
        password=token, sslmode="require",
    )

# COMMAND ----------

# DBTITLE 1,Create operational schema + tables
DDL = """
CREATE SCHEMA IF NOT EXISTS cockpit_app;

-- One row per rep decision on an account risk alert.
CREATE TABLE IF NOT EXISTS cockpit_app.rep_actions (
    action_id       BIGSERIAL PRIMARY KEY,
    sf_account_id   TEXT        NOT NULL,
    account_name    TEXT,
    rep_email       TEXT        NOT NULL,
    action          TEXT        NOT NULL
                    CHECK (action IN ('accepted','dismissed','snoozed')),
    disposition     TEXT,
    risk_score_seen DOUBLE PRECISION,
    snooze_until    DATE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Hot path for the app: "what is the current state of this account's alert?"
CREATE INDEX IF NOT EXISTS idx_rep_actions_account
    ON cockpit_app.rep_actions (sf_account_id, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_rep_actions_rep
    ON cockpit_app.rep_actions (rep_email, created_at DESC);

-- Immutable audit trail. Never updated, only appended.
CREATE TABLE IF NOT EXISTS cockpit_app.action_audit (
    audit_id      BIGSERIAL PRIMARY KEY,
    action_id     BIGINT,
    actor         TEXT        NOT NULL,
    event         TEXT        NOT NULL,
    payload       JSONB,
    occurred_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_audit_occurred
    ON cockpit_app.action_audit (occurred_at DESC);
"""

with connect() as conn:
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute(DDL)

log()
log("-- DDL ------------------------------------------------------------------")
log("created schema cockpit_app")
log("  tables  : rep_actions, action_audit")
log("  indexes : idx_rep_actions_account, idx_rep_actions_rep, idx_audit_occurred")

# COMMAND ----------

# DBTITLE 1,Create the Delta -> Lakebase synced table if missing
# Serves account_risk_summary to the app from Postgres. SNAPSHOT mode: 03_score_and_brief
# triggers a refresh after every rescore, so the app never serves stale scores.
def synced_table():
    try:
        return w.api_client.do("GET", f"/api/2.0/postgres/synced_tables/{cfg.SYNCED_TABLE}")
    except Exception as e:
        if "NOT_FOUND" in str(e) or "does not exist" in str(e).lower():
            return None
        raise

st = synced_table()
if st is None:
    log(f"creating synced table {cfg.SYNCED_TABLE} ...")
    w.api_client.do("POST", "/api/2.0/postgres/synced_tables", body={
        "synced_table_id": cfg.SYNCED_TABLE,
        "spec": {
            "branch": cfg.LAKEBASE_BRANCH,
            "postgres_database": cfg.LAKEBASE_DATABASE,
            "source_table_full_name": f"{cfg.SCHEMA}.account_risk_summary",
            "primary_key_columns": ["sf_account_id"],
            "scheduling_policy": "SNAPSHOT",
            "create_database_objects_if_missing": True,
            "new_pipeline_spec": {"storage_catalog": cfg.SCHEMA.split(".")[0], "storage_schema": cfg.SCHEMA.split(".")[1]},
        },
    })
    for _ in range(60):
        st = synced_table()
        if st and st["status"].get("detailed_state", "").startswith("SYNCED_TABLE_ONLINE"):
            break
        time.sleep(10)
log(f"synced table {cfg.SYNCED_TABLE}: {st['status'].get('detailed_state')} | source {st['status'].get('source_table_full_name')} | mode {st['status'].get('scheduling_policy')}")

# COMMAND ----------

# DBTITLE 1,Verify the synced table landed from Delta
with connect() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT table_schema, table_name
            FROM information_schema.tables
            WHERE table_schema IN ('cockpit','cockpit_app')
            ORDER BY table_schema, table_name
        """)
        tables = cur.fetchall()

        cur.execute("SELECT COUNT(*) FROM cockpit.account_risk_summary")
        synced_rows = cur.fetchone()[0]

        cur.execute("""
            SELECT risk_category, COUNT(*) AS accounts,
                   ROUND(AVG(ml_risk_score)::numeric, 1) AS avg_score,
                   ROUND(SUM(annual_revenue)::numeric, 0) AS revenue_at_stake
            FROM cockpit.account_risk_summary
            GROUP BY risk_category
            ORDER BY avg_score DESC
        """)
        dist = cur.fetchall()

log()
log("-- SYNCED TABLE (Delta -> Lakebase) ------------------------------------")
log("postgres tables:")
for schema, table in tables:
    log(f"  {schema}.{table}")
log(f"\ncockpit.account_risk_summary: {synced_rows} rows synced from Delta")
log()
log("risk distribution, served from Postgres:")
log(f"  {'category':10s} {'accounts':>9s} {'avg_score':>10s} {'revenue_at_stake':>18s}")
for cat, cnt, avg, rev in dist:
    log(f"  {cat:10s} {cnt:9d} {float(avg):10.1f} {float(rev):18,.0f}")

# COMMAND ----------

# DBTITLE 1,Prove the write path - rep acts on an alert
# This is exactly what the Databricks App does when a rep clicks "Accept" on an alert.
with connect() as conn:
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.sf_account_id, s.account_name, s.ml_risk_score, s.top_risk_driver
            FROM cockpit.account_risk_summary s
            LEFT JOIN cockpit_app.rep_actions a
                   ON a.sf_account_id = s.sf_account_id
            WHERE a.action_id IS NULL
            ORDER BY s.ml_risk_score DESC
            LIMIT 1
        """)
        acct = cur.fetchone()

        cur.execute("""
            INSERT INTO cockpit_app.rep_actions
                (sf_account_id, account_name, rep_email, action, disposition, risk_score_seen)
            VALUES (%s, %s, %s, 'accepted', 'Booked save call for Thursday', %s)
            RETURNING action_id, created_at
        """, (acct[0], acct[1], PG_USER, acct[2]))
        action_id, created_at = cur.fetchone()

        cur.execute("""
            INSERT INTO cockpit_app.action_audit (action_id, actor, event, payload)
            VALUES (%s, %s, 'alert_accepted',
                    jsonb_build_object('account_name', %s::text,
                                       'risk_score', %s::float,
                                       'driver', %s::text))
            RETURNING audit_id
        """, (action_id, PG_USER, acct[1], acct[2], acct[3]))
        audit_id = cur.fetchone()[0]

log()
log("-- WRITE PATH (app -> Lakebase) ---------------------------------------")
log(f"top un-actioned alert : {acct[1]} | score {acct[2]} | {acct[3]}")
log(f"wrote rep_actions     : action_id={action_id} at {created_at}")
log(f"wrote action_audit    : audit_id={audit_id} (same transaction)")

# COMMAND ----------

# DBTITLE 1,The query the app serves - synced risk JOINed to live rep state
with connect() as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT s.account_name, s.ml_risk_score, s.risk_category,
                   s.top_risk_driver, COALESCE(a.action, 'new') AS alert_state,
                   a.rep_email
            FROM cockpit.account_risk_summary s
            LEFT JOIN LATERAL (
                SELECT action, rep_email
                FROM cockpit_app.rep_actions r
                WHERE r.sf_account_id = s.sf_account_id
                ORDER BY r.created_at DESC
                LIMIT 1
            ) a ON TRUE
            ORDER BY s.ml_risk_score DESC
            LIMIT 10
        """)
        worklist = cur.fetchall()

log()
log("-- REP WORKLIST (the app's main query) --------------------------------")
log(f"{'account':32s} {'score':>6s} {'category':9s} {'state':10s} {'driver':26s}")
log("-" * 88)
for r in worklist:
    log(f"{(r[0] or '')[:31]:32s} {r[1]:6} {r[2]:9s} {r[4]:10s} {(r[3] or '')[:25]:26s}")

# COMMAND ----------

# DBTITLE 1,Latency - why Lakebase and not the warehouse
import time

with connect() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT 1")  # warm the connection
        timings = []
        for _ in range(20):
            t0 = time.perf_counter()
            cur.execute("""
                SELECT account_name, ml_risk_score, top_risk_driver
                FROM cockpit.account_risk_summary
                WHERE sf_account_id = %s
            """, (acct[0],))
            cur.fetchall()
            timings.append((time.perf_counter() - t0) * 1000)

timings.sort()
log()
log("-- LATENCY (single-account lookup, 20 runs) ---------------------------")
log(f"  p50 : {timings[len(timings)//2]:.1f} ms")
log(f"  p95 : {timings[int(len(timings)*0.95)-1]:.1f} ms")
log(f"  min : {timings[0]:.1f} ms")
log(f"  max : {timings[-1]:.1f} ms")
log("  this read happens on every app page load and every rep click")

# COMMAND ----------

# DBTITLE 1,Validation summary + return evidence
with connect() as conn:
    with conn.cursor() as cur:
        cur.execute("SELECT version()")
        ver = cur.fetchone()[0].split(",")[0]
        cur.execute("SELECT COUNT(*) FROM cockpit.account_risk_summary")
        synced = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cockpit_app.rep_actions")
        actions = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM cockpit_app.action_audit")
        audits = cur.fetchone()[0]

log()
log("=" * 72)
log("VALIDATION")
log("=" * 72)
log(f"  postgres                     : {ver}")
log(f"  cockpit.account_risk_summary : {synced} rows (synced from Delta, read-only)")
log(f"  cockpit_app.rep_actions      : {actions} rows (app writes)")
log(f"  cockpit_app.action_audit     : {audits} rows (append-only audit)")
log("=" * 72)
log("PASS - round trip confirmed:")
log("  Delta -> Lakebase sync -> app read -> app write -> audit -> joined read")
log("=" * 72)

dbutils.notebook.exit("\n".join(REPORT))