"""Single source of configuration for Signal 2.0.

Every notebook and the refresh job import this module, so IDs, names and
secret-scope keys live in one place. Credentials are never stored here:
they are read at runtime from the Databricks secret scope SECRET_SCOPE.
"""
import os
import requests

# Unity Catalog
SCHEMA = "main.ccg_workshop_cdm"
MODEL_NAME = f"{SCHEMA}.account_risk_model"
SYN_HISTORY_TABLE = f"{SCHEMA}.syn_account_monthly_history"
METRIC_VIEW = f"{SCHEMA}.mv_customer_360"

# Workspace objects that cannot live inside a Git folder (experiment, Genie agent, dashboard)
ASSETS_FOLDER = "/Shared/signal-2.0-assets"
EXPERIMENT_PATH = f"{ASSETS_FOLDER}/ccg_account_risk_model"
WAREHOUSE_ID = "148ccb90800933a1"
DASHBOARD_ID = "01f1a72dc5a713608e84a6d9c8eff268"
GENIE_SPACE_ID = "01f19c88f94816f3808eef719283e510"
CUSTOMER_360_PIPELINE_ID = "46e9e7c6-339e-4dff-864a-2a633144d724"

# Lakebase + Databricks App
LAKEBASE_PROJECT = "signal-account-cockpit"
LAKEBASE_BRANCH = f"projects/{LAKEBASE_PROJECT}/branches/production"
LAKEBASE_ENDPOINT = f"{LAKEBASE_BRANCH}/endpoints/primary"
LAKEBASE_DATABASE = "databricks_postgres"
LAKEBASE_CATALOG = "signal_cockpit_pg"
SYNCED_TABLE = f"{LAKEBASE_CATALOG}.cockpit.account_risk_summary"
# Every Delta table the app reads, synced to Lakebase so no app click waits on the SQL warehouse.
# Delta source table name -> Lakebase synced table. All are SNAPSHOT mode, keyed on sf_account_id.
SYNCED_TABLES = {
    "account_risk_summary": SYNCED_TABLE,
    "account_briefing_v2": f"{LAKEBASE_CATALOG}.cockpit.account_briefing_v2",
    "account_deep_insights": f"{LAKEBASE_CATALOG}.cockpit.account_deep_insights",
}
APP_NAME = "signal-account-cockpit"

# Salesforce (credentials come from the secret scope, never from code)
SECRET_SCOPE = "ccg-salesforce"
SF_DOMAIN = os.getenv("SF_DOMAIN", "")
SF_API_VERSION = "59.0"


def salesforce_session(dbutils):
    """OAuth client-credentials login. Returns (instance_url, access_token)."""
    sf_domain = SF_DOMAIN
    if not sf_domain:
        for key in ("sf-domain", "domain"):
            try:
                sf_domain = dbutils.secrets.get(scope=SECRET_SCOPE, key=key)
                break
            except Exception:
                continue
    if not sf_domain:
        raise ValueError("Set SF_DOMAIN or add sf-domain/domain to the Salesforce secret scope before running this notebook.")
    resp = requests.post(f"https://{sf_domain}/services/oauth2/token", data={
        "grant_type": "client_credentials",
        "client_id": dbutils.secrets.get(scope=SECRET_SCOPE, key="consumer-key"),
        "client_secret": dbutils.secrets.get(scope=SECRET_SCOPE, key="consumer-secret"),
    }, timeout=30)
    resp.raise_for_status()
    auth = resp.json()
    return auth["instance_url"], auth["access_token"]
