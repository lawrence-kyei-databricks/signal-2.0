# Run evidence: Lakebase operational layer

Source notebook: `04_lakebase_app/01_lakebase_setup`. Outputs exported 2026-11-22 15:09 UTC from the executed notebook (no images; tables and logs as text).

## Config + report buffer

```text
========================================================================
SIGNAL ACCOUNT COCKPIT - LAKEBASE OPERATIONAL LAYER
run at         : 2026-11-22T15:01:56.947773+00:00
========================================================================
sdk version    : 0.169.0
project        : signal-account-cockpit
endpoint host  : ep-muddy-resonance-e1qdrf0h.database.eastus2.azuredatabricks.net
endpoint state : EndpointStatusState.ACTIVE
connecting as  : <redacted-email>
```

## Create operational schema + tables

```text

-- DDL ------------------------------------------------------------------
created schema cockpit_app
  tables  : rep_actions, action_audit
  indexes : idx_rep_actions_account, idx_rep_actions_rep, idx_audit_occurred
```

## Create the Delta -> Lakebase synced table if missing

```text
synced table signal_cockpit_pg.cockpit.account_risk_summary: SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE | source main.ccg_workshop_cdm.account_risk_summary | mode SNAPSHOT
```

## Verify the synced table landed from Delta

```text

-- SYNCED TABLE (Delta -> Lakebase) ------------------------------------
postgres tables:
  cockpit.account_risk_summary
  cockpit_app.action_audit
  cockpit_app.rep_actions

cockpit.account_risk_summary: 200 rows synced from Delta

risk distribution, served from Postgres:
  category    accounts  avg_score   revenue_at_stake
  High              11       59.7         12,631,957
  Medium            68       35.0         61,724,457
  Low              121       12.3        102,607,634
```

## Prove the write path - rep acts on an alert

```text

-- WRITE PATH (app -> Lakebase) ---------------------------------------
top un-actioned alert : Massachusetts General Hospital | score 66.7 | Revenue vs 12-mo run rate: 0.33x; Revenue momentum (last 3 mo vs prior 3): -95%
wrote rep_actions     : action_id=4 at 2026-11-22 15:02:16.415967+00:00
wrote action_audit    : audit_id=4 (same transaction)
```

## The query the app serves - synced risk JOINed to live rep state

```text

-- REP WORKLIST (the app's main query) --------------------------------
account                           score category  state      driver                    
----------------------------------------------------------------------------------------
Massachusetts General Hospital     66.7 High      accepted   Revenue vs 12-mo run rate 
SAIC Life Sciences                 65.8 High      new        Backorder rate (6 mo): 46 
AstraZeneca Biologics              65.0 High      new        Revenue vs 12-mo run rate 
Berkeley Lights                    62.2 High      new        Days since last rep activ 
University of Pittsburgh           61.7 High      new        Backorder rate (6 mo): 72 
Tucson BioAnalytical               59.7 High      new        Backorder rate (6 mo): 45 
Albuquerque Diagnostics Lab        56.7 High      new        Revenue vs 12-mo run rate 
SGS Life Sciences                  56.2 High      new        Revenue momentum (last 3  
NewYork-Presbyterian Hospital      55.7 High      new        Revenue vs 12-mo run rate 
Exact Sciences                     54.1 High      new        Revenue momentum (last 3
```

## Latency - why Lakebase and not the warehouse

```text

-- LATENCY (single-account lookup, 20 runs) ---------------------------
  p50 : 1.3 ms
  p95 : 2.3 ms
  min : 1.1 ms
  max : 2.5 ms
  this read happens on every app page load and every rep click
```
