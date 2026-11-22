"""Signal 2.0 - Account Risk Cockpit (Databricks App)

Three data paths, each used for what it is actually good at:

  Lakebase Postgres  -> rep worklist + alert state + write-back   (p50 ~1.2ms)
  SQL Warehouse      -> portfolio aggregates, briefings, trends   (seconds)
  Genie Agent        -> natural-language Q&A, execution_mode=FLASH

Writes go only to cockpit_app.{rep_actions,action_audit}. The app's service
principal holds SELECT+INSERT and deliberately lacks UPDATE/DELETE, so rep
decisions and audit rows are append-only at the database level.
"""
import json
import re
import os
import threading
import time
from contextlib import contextmanager
from typing import Any

import psycopg
import requests
from databricks.sdk import WorkspaceClient
from databricks.sdk.service.sql import StatementParameterListItem
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="Signal 2.0 - Account Risk Cockpit")


@app.middleware("http")
async def request_timing(request: Request, call_next):
    """Server-side time per API call: shown in the browser's network tab (Server-Timing) and in the app logs."""
    start = time.perf_counter()
    response = await call_next(request)
    ms = (time.perf_counter() - start) * 1000
    response.headers["Server-Timing"] = f"app;dur={ms:.1f}"
    if request.url.path.startswith("/api/"):
        print(f"[timing] {request.method} {request.url.path} {response.status_code} {ms:.1f}ms", flush=True)
    return response


w = WorkspaceClient()

WAREHOUSE_ID = os.environ["DATABRICKS_WAREHOUSE_ID"]
GENIE_SPACE  = os.environ["GENIE_SPACE_ID"]
DASHBOARD_ID = os.environ.get("DASHBOARD_ID", "")
def _normalize_host(raw: str) -> str:
    """Databricks Apps sets DATABRICKS_HOST WITHOUT a scheme (adb-xxx.azuredatabricks.net)."""
    h = (raw or "").strip().rstrip("/")
    return h if h.startswith(("http://", "https://")) else f"https://{h}"


HOST         = _normalize_host(os.environ.get("DATABRICKS_HOST") or w.config.host or "")
SCHEMA       = "main.ccg_workshop_cdm"

# ──────────────────────────────── Lakebase ────────────────────────────────
# The `postgres` app-resource key does NOT auto-inject PG* env vars (the
# legacy `database` key did), so take them from app.yaml and fall back to
# whatever the platform happens to provide.
LAKEBASE_ENDPOINT = os.environ.get("LAKEBASE_ENDPOINT") or (
    f"projects/{os.environ['LAKEBASE_PROJECT']}/branches/"
    f"{os.environ.get('LAKEBASE_BRANCH', 'production')}/endpoints/"
    f"{os.environ.get('LAKEBASE_ENDPOINT_ID', 'primary')}"
)

# Log what the platform actually injected - saves guessing on the next build.
print("[lakebase] resolved endpoint:", LAKEBASE_ENDPOINT)
print("[env] platform-provided keys:", sorted(
    k for k in os.environ
    if k.startswith(("PG", "LAKEBASE", "DATABRICKS"))
))

PG_HOST = os.environ.get("PGHOST") or w.postgres.get_endpoint(
    name=LAKEBASE_ENDPOINT
).status.hosts.host
PG_PORT = int(os.environ.get("PGPORT", "5432"))
PG_DB = os.environ.get("PGDATABASE", "databricks_postgres")
PG_USER = os.environ.get("PGUSER") or os.environ["DATABRICKS_CLIENT_ID"]
PG_SSL = os.environ.get("PGSSLMODE", "require")

_token = {"value": w.postgres.generate_database_credential(endpoint=LAKEBASE_ENDPOINT).token}


def _refresh_token_loop():
    while True:
        time.sleep(1800)  # 30 min, comfortably inside the ~1h expiry
        try:
            _token["value"] = w.postgres.generate_database_credential(
                endpoint=LAKEBASE_ENDPOINT
            ).token
        except Exception as exc:  # keep serving on the old token if refresh blips
            print(f"[lakebase] token refresh failed: {exc}")


threading.Thread(target=_refresh_token_loop, daemon=True).start()


def _connect(**kwargs):
    return psycopg.connect(
        host=PG_HOST, port=PG_PORT, dbname=PG_DB, user=PG_USER,
        password=_token["value"], sslmode=PG_SSL, **kwargs,
    )


@contextmanager
def pg():
    """Short-lived connection. Lakebase wakes from scale-to-zero in ~100ms."""
    conn = _connect()
    try:
        yield conn
    finally:
        conn.close()


def pg_rows(sql: str, params: tuple | dict = ()) -> list[dict]:
    with pg() as conn:
        with conn.cursor() as cur:
            cur.execute(sql, params)
            cols = [c.name for c in cur.description]
            return [dict(zip(cols, r)) for r in cur.fetchall()]


# ──────────────────────────────── Warehouse ───────────────────────────────
def wh_rows(sql: str, params: dict | None = None) -> list[dict]:
    """Run SQL on the warehouse. Values are always bound as :named parameters, never formatted into SQL."""
    r = w.statement_execution.execute_statement(
        warehouse_id=WAREHOUSE_ID, statement=sql, wait_timeout="50s",
        parameters=[StatementParameterListItem(name=k, value=str(v)) for k, v in (params or {}).items()],
    )
    if not r.result or not r.result.data_array:
        return []
    cols = [c.name for c in r.manifest.schema.columns]
    return [dict(zip(cols, row)) for row in r.result.data_array]


def current_rep(request: Request) -> str:
    """The signed-in user, forwarded by Databricks Apps. Falls back to the app identity for local runs."""
    return (request.headers.get("x-forwarded-email")
            or request.headers.get("x-forwarded-preferred-username")
            or os.environ.get("DATABRICKS_CLIENT_ID", "app-service-principal"))


def user_auth_headers(request: Request) -> dict:
    """On-behalf-of-user auth (app user-authorization scopes `genie` + `sql`): Genie runs with the rep's own
    permissions. Without a forwarded user token (local runs), fall back to the app service principal."""
    token = request.headers.get("x-forwarded-access-token")
    return {"Authorization": f"Bearer {token}"} if token else w.config.authenticate()



READ_ONLY_SQL = re.compile(r"^\s*(WITH|SELECT)\b", re.I)


def genie_result(sql: str, request: Request, max_rows: int = 200) -> dict | None:
    """Re-run Genie's final read-only query as the signed-in rep (user scope `sql`) so the UI can show
    the real result table and a chart, instead of Genie's text placeholder."""
    if not sql or not READ_ONLY_SQL.match(sql) or ";" in sql.strip().rstrip(";"):
        return None
    r = requests.post(f"{HOST}/api/2.0/sql/statements", timeout=60,
                      headers={**user_auth_headers(request), "Content-Type": "application/json"},
                      json={"warehouse_id": WAREHOUSE_ID, "statement": sql.strip().rstrip(";"),
                            "wait_timeout": "30s", "row_limit": max_rows, "disposition": "INLINE", "format": "JSON_ARRAY"})
    if r.status_code >= 400:
        return {"error": f"result query returned {r.status_code}"}
    j = r.json()
    if j.get("status", {}).get("state") != "SUCCEEDED":
        return {"error": j.get("status", {}).get("state", "unknown")}
    cols = [{"name": c["name"], "type": c.get("type_name", "STRING")} for c in j["manifest"]["schema"]["columns"]]
    return {"columns": cols, "rows": (j.get("result") or {}).get("data_array") or [],
            "truncated": bool(j["manifest"].get("truncated"))}

# ═══════════════════════════════ API ══════════════════════════════════════

@app.get("/api/health")
def health(request: Request):
    """Proves all three data paths are reachable, with timings."""
    out: dict[str, Any] = {"signed_in_as": current_rep(request),
                           "user_authorization": bool(request.headers.get("x-forwarded-access-token"))}
    t = time.perf_counter()
    out["lakebase"] = {"rows": pg_rows("SELECT COUNT(*) AS n FROM cockpit.account_risk_summary")[0]["n"],
                       "ms": round((time.perf_counter() - t) * 1000, 1)}
    t = time.perf_counter()
    out["warehouse"] = {"rows": wh_rows(f"SELECT COUNT(*) AS n FROM {SCHEMA}.customer_360")[0]["n"],
                        "ms": round((time.perf_counter() - t) * 1000, 1)}
    out["genie_space"] = GENIE_SPACE
    out["write_privileges"] = pg_rows(
        """SELECT privilege_type FROM information_schema.table_privileges
           WHERE grantee = %s AND table_name = 'rep_actions' ORDER BY 1""",
        (PG_USER,),
    )
    return out


@app.get("/api/governance/band-consistency")
def band_consistency():
    """Does every consumer agree on how many accounts are High risk?

    Single source: account_risk_summary.risk_category from account_risk_model@champion.
    The metric view (dashboard + Genie), Lakebase (this app's worklist) and Salesforce
    all derive from it, so their High counts must match.
    """
    wh = wh_rows(f"""
        SELECT 'account_risk_summary (model, source of truth)' AS source, COUNT_IF(risk_category = 'High') AS high_accounts
        FROM {SCHEMA}.account_risk_summary
        UNION ALL
        SELECT 'mv_customer_360 (dashboard + Genie)', MEASURE(`At Risk Accounts`)
        FROM {SCHEMA}.mv_customer_360
    """)
    lake = pg_rows("SELECT COUNT(*) FILTER (WHERE risk_category = 'High') AS high_accounts FROM cockpit.account_risk_summary")[0]
    rows = wh + [{"source": "Lakebase cockpit.account_risk_summary (this app)", "high_accounts": lake["high_accounts"]}]
    counts = {int(r["high_accounts"]) for r in rows}
    return {"sources": rows,
            "agreement": len(counts) == 1,
            "spread": (max(counts) - min(counts)) if counts else 0,
            "note": ("All consumers agree." if len(counts) == 1 else
                     "Consumers disagree - Lakebase is likely stale. Re-run 02_ml/03_score_and_brief, "
                     "which refreshes the synced table after scoring.")}


@app.get("/api/governance/sync-freshness")
def sync_freshness():
    """Is Lakebase still serving what Delta holds?

    The synced table runs in SNAPSHOT mode, so it does NOT follow the source.
    Every time the model is re-scored, Lakebase keeps serving the previous
    scores until the sync pipeline is re-run - and the app would silently show
    a stale worklist. Compare both sides and say so out loud.
    """
    delta = wh_rows(f"""
        SELECT COUNT(*) AS n, ROUND(SUM(ml_risk_score), 2) AS score_sum
        FROM {SCHEMA}.account_risk_summary
    """)[0]
    lake = pg_rows("""
        SELECT COUNT(*) AS n, ROUND(SUM(ml_risk_score)::numeric, 2) AS score_sum
        FROM cockpit.account_risk_summary
    """)[0]

    fresh = (int(delta["n"]) == int(lake["n"])
             and abs(float(delta["score_sum"]) - float(lake["score_sum"])) < 0.01)
    return {"delta": {"rows": int(delta["n"]), "score_sum": float(delta["score_sum"])},
            "lakebase": {"rows": int(lake["n"]), "score_sum": float(lake["score_sum"])},
            "in_sync": fresh,
            "sync_mode": "SNAPSHOT",
            "note": ("Lakebase matches Delta." if fresh else
                     "Lakebase is STALE - the source has been re-scored since the "
                     "last snapshot. Re-run the sync pipeline, or move the synced "
                     "table to TRIGGERED mode with CDF enabled on the source. "
                     "02_ml/03_score_and_brief refreshes it after every rescore.")}


@app.get("/api/kpis")
def kpis():
    """Portfolio view. Warehouse - this is an aggregate over the gold layer."""
    return wh_rows(f"""
        SELECT risk_category,
               COUNT(*)                        AS accounts,
               ROUND(AVG(ml_risk_score), 1)    AS avg_score,
               ROUND(SUM(annual_revenue), 0)   AS revenue_at_stake,
               ROUND(SUM(open_pipeline_value), 0) AS pipeline_at_stake
        FROM {SCHEMA}.account_risk_summary
        GROUP BY risk_category
        ORDER BY avg_score DESC
    """)


@app.get("/api/worklist")
def worklist(limit: int = 50, category: str | None = None, state: str | None = None):
    """Rep worklist from Lakebase, ranked by expected revenue at risk (probability x 6-month run rate).

    Synced risk data LEFT JOINed to live rep decisions so an alert the rep has already
    handled drops out of the queue immediately. Filters run in SQL before LIMIT.
    """
    limit = max(1, min(int(limit), 200))
    return pg_rows("""
        SELECT * FROM (
            SELECT s.sf_account_id, s.account_name, s.ml_risk_score, s.risk_category,
                   s.expected_revenue_at_risk,
                   s.top_risk_driver, s.days_since_last_activity, s.annual_revenue,
                   s.open_pipeline_value, s.open_case_count,
                   COALESCE(a.action, 'new') AS alert_state,
                   a.disposition, a.rep_email, a.created_at AS actioned_at
            FROM cockpit.account_risk_summary s
            LEFT JOIN LATERAL (
                SELECT action, disposition, rep_email, created_at
                FROM cockpit_app.rep_actions r
                WHERE r.sf_account_id = s.sf_account_id
                ORDER BY r.created_at DESC
                LIMIT 1
            ) a ON TRUE
        ) wl
        WHERE (%(category)s::text IS NULL OR wl.risk_category = %(category)s)
          AND (%(state)s::text IS NULL OR wl.alert_state = %(state)s)
        ORDER BY wl.expected_revenue_at_risk DESC NULLS LAST, wl.ml_risk_score DESC
        LIMIT %(limit)s
    """, {"category": category, "state": state, "limit": limit})


@app.get("/api/account/{account_id}")
def account_detail(account_id: str):
    """Single account. Everything from Lakebase in ONE connection: risk, AI briefing and deep insights are
    synced tables (refreshed and parity-checked by 03_score_and_brief); history is the live rep-decision table.
    No call here touches the SQL warehouse."""
    with pg() as conn:
        with conn.cursor() as cur:
            def rows(sql):
                cur.execute(sql, (account_id,))
                cols = [c.name for c in cur.description]
                return [dict(zip(cols, r)) for r in cur.fetchall()]
            risk = rows("SELECT * FROM cockpit.account_risk_summary WHERE sf_account_id = %s")
            if not risk:
                raise HTTPException(404, f"account {account_id} not found")
            briefing = rows("""SELECT action_type, urgency_score, recommendations, numbers_verified
                               FROM cockpit.account_briefing_v2 WHERE sf_account_id = %s""")
            insights = rows("""SELECT rev_trend_pct, risk_vs_industry
                               FROM cockpit.account_deep_insights WHERE sf_account_id = %s""")
            history = rows("""SELECT action, disposition, rep_email, risk_score_seen, created_at
                              FROM cockpit_app.rep_actions WHERE sf_account_id = %s ORDER BY created_at DESC""")

    # Shape for the UI: split the numbered recommendations and use the field names the page renders
    if briefing:
        b = briefing[0]
        recs = [s.strip() for s in re.split(r"(?m)^\s*\d\.\s+", b.get("recommendations") or "") if s.strip()]
        briefing = [{"action_type": b["action_type"], "urgency": b["urgency_score"],
                     **{f"recommendation_{i + 1}": r for i, r in enumerate(recs[:3])}}]
    if insights:
        i = insights[0]
        insights = [{"revenue_trend_pct": i["rev_trend_pct"], "peer_risk_delta": i["risk_vs_industry"]}]

    return {"risk": risk[0],
            "briefing": briefing[0] if briefing else None,
            "insights": insights[0] if insights else None,
            "history": history}


class ActionIn(BaseModel):
    sf_account_id: str
    account_name: str | None = None
    action: str                      # accepted | dismissed | snoozed
    disposition: str | None = None
    risk_score_seen: float | None = None
    snooze_until: str | None = None


@app.post("/api/action")
def record_action(body: ActionIn, request: Request):
    """The write path. Decision + audit row in ONE transaction.

    Either both land or neither does - there is no state where a rep decision
    exists without its audit record.
    """
    if body.action not in ("accepted", "dismissed", "snoozed"):
        raise HTTPException(400, "action must be accepted, dismissed or snoozed")

    rep = current_rep(request)                       # the signed-in rep, not the app identity
    with pg() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO cockpit_app.rep_actions
                    (sf_account_id, account_name, rep_email, action,
                     disposition, risk_score_seen, snooze_until)
                VALUES (%s,%s,%s,%s,%s,%s,%s)
                RETURNING action_id, created_at
            """, (body.sf_account_id, body.account_name, rep, body.action,
                  body.disposition, body.risk_score_seen, body.snooze_until))
            action_id, created_at = cur.fetchone()

            cur.execute("""
                INSERT INTO cockpit_app.action_audit (action_id, actor, event, payload)
                VALUES (%s,%s,%s,%s::jsonb)
                RETURNING audit_id
            """, (action_id, rep, f"alert_{body.action}",
                  json.dumps(body.model_dump())))
            audit_id = cur.fetchone()[0]
        conn.commit()

    return {"action_id": action_id, "audit_id": audit_id,
            "created_at": str(created_at), "committed": True}


@app.get("/api/audit")
def audit(limit: int = 50):
    return pg_rows("""
        SELECT a.audit_id, a.action_id, a.actor, a.event, a.payload, a.occurred_at
        FROM cockpit_app.action_audit a
        ORDER BY a.occurred_at DESC LIMIT %s
    """, (int(limit),))


# ──────────────────────────────── Genie ───────────────────────────────────
class AskIn(BaseModel):
    question: str
    conversation_id: str | None = None


@app.post("/api/genie/ask")
def genie_ask(body: AskIn, request: Request):
    """Genie agent-mode with execution_mode=FLASH.

    FLASH trades reasoning depth for speed - the right call for a rep asking a
    quick portfolio question inside a workflow. execution_mode is fixed when the
    conversation is created; sending a different value on a follow-up is a
    BAD_REQUEST, so we only set it on the first turn.
    """
    url = f"{HOST}/api/2.0/genie/agents/{GENIE_SPACE}/responses"
    payload: dict[str, Any] = {
        "input": [{"type": "message", "role": "user",
                   "content": [{"type": "input_text", "text": body.question}]}]
    }
    if body.conversation_id:
        payload["conversation_id"] = body.conversation_id
    else:
        payload["execution_mode"] = "FLASH"

    # w.config.authenticate() returns the ready auth headers for whatever
    # credential strategy the app is running under - do not build the bearer
    # token by hand.
    headers = {
        **user_auth_headers(request),
        "Content-Type": "application/json",
        "Accept": "text/event-stream",
    }

    started = time.perf_counter()
    deltas: list[str] = []            # streamed token-by-token
    final_texts: dict[str, str] = {}  # item_id -> text, so repeats collapse
    sql_queries: list[str] = []
    conversation_id = body.conversation_id
    # Every output item is emitted twice - once on response.output_item.added
    # and again on response.output_item.done - and a single answer can span
    # several message items (prose + a table). Dedupe on item id, keep order.

    try:
        resp_ctx = requests.post(url, headers=headers, json=payload,
                                 stream=True, timeout=180)
    except Exception as exc:
        raise HTTPException(502, f"genie request failed: {type(exc).__name__}: {exc}")

    with resp_ctx as resp:
        if resp.status_code >= 400:
            hint = ""
            if resp.status_code in (401, 403) and request.headers.get("x-forwarded-access-token"):
                hint = (" | Genie runs as the signed-in user. Check that the app has user-authorization scopes "
                        "genie and sql, that you re-opened the app to consent to them, and that you have "
                        "CAN RUN on the Genie agent and CAN USE on its warehouse.")
            raise HTTPException(resp.status_code,
                                f"genie returned {resp.status_code} for {current_rep(request)}: {resp.text[:400]}{hint}")
        # SSE carries no charset, so requests guesses latin-1 and mangles
        # em dashes into mojibake. Pin UTF-8.
        resp.encoding = "utf-8"
        for line in resp.iter_lines(decode_unicode=True):
            if not line or not line.startswith("data:"):
                continue
            try:
                evt = json.loads(line[5:].strip())
            except json.JSONDecodeError:
                continue
            if evt.get("type") == "response.created":
                conversation_id = evt["response"].get("conversation_id", conversation_id)
            item = evt.get("item") or {}
            if item.get("type") == "function_call" and item.get("name") == "execute_sql":
                try:
                    sql = json.loads(item.get("arguments", "{}")).get("sql", "")
                except json.JSONDecodeError:
                    sql = ""
                if sql and sql not in sql_queries:
                    sql_queries.append(sql)
            if evt.get("type") == "response.output_text.delta" and evt.get("delta"):
                deltas.append(evt["delta"])
            if item.get("type") == "message":
                item_id = item.get("id") or item.get("call_id") or str(len(final_texts))
                text = "\n\n".join(
                    c["text"]
                    for c in item.get("content", [])
                    if c.get("type") == "output_text" and c.get("text")
                )
                if text:
                    final_texts[item_id] = text

    # Completed message items repeat what already streamed as deltas, so prefer
    # them and fall back to the deltas only if no message item arrived.
    answer = ("\n\n".join(final_texts.values()) or "".join(deltas)).strip()

    try:
        result = genie_result(sql_queries[-1], request) if sql_queries else None
    except Exception as exc:                      # the answer text is still useful without the table
        result = {"error": f"{type(exc).__name__}"}

    return {"answer": answer or "(no text returned)",
            "sql": sql_queries,
            "result": result,
            "conversation_id": conversation_id,
            "execution_mode": "FLASH",
            "elapsed_ms": round((time.perf_counter() - started) * 1000)}


@app.get("/api/config")
def config():
    return {"dashboard_id": DASHBOARD_ID, "genie_space": GENIE_SPACE, "host": HOST}


# ──────────────────────────────── Static ──────────────────────────────────
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/")
def index():
    return FileResponse("static/index.html")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("DATABRICKS_APP_PORT", 8000)))
