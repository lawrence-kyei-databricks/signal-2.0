# Run evidence: Lakebase: operational schema, synced tables, app queries, latency

Source notebook: `04_lakebase_app/01_lakebase_setup`. Outputs exported 2026-11-22 21:53 UTC from the executed notebook (no images; tables and logs as text).

## Config + report buffer

```text
========================================================================
SIGNAL ACCOUNT COCKPIT - LAKEBASE OPERATIONAL LAYER
run at         : 2026-11-22T21:35:35.600725+00:00
========================================================================
sdk version    : 0.169.0
project        : signal-account-cockpit
endpoint host  : <lakebase-host>
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

## Create the Delta -> Lakebase synced tables if missing

```text
synced table signal_cockpit_pg.cockpit.account_risk_summary: SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE | source main.ccg_workshop_cdm.account_risk_summary | mode SNAPSHOT
synced table signal_cockpit_pg.cockpit.account_briefing_v2: SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE | source main.ccg_workshop_cdm.account_briefing_v2 | mode SNAPSHOT
synced table signal_cockpit_pg.cockpit.account_deep_insights: SYNCED_TABLE_ONLINE_NO_PENDING_UPDATE | source main.ccg_workshop_cdm.account_deep_insights | mode SNAPSHOT
```

## Verify the synced table landed from Delta

```text
-- SYNCED TABLE (Delta -> Lakebase) ------------------------------------
postgres tables:
  cockpit.account_briefing_v2
  cockpit.account_deep_insights
  cockpit.account_risk_summary
  cockpit_app.action_audit
  cockpit_app.rep_actions

cockpit.account_risk_summary: 200 rows synced from Delta

risk distribution, served from Postgres:
  category    accounts  avg_score   revenue_at_stake
  High              20       40.8        319,496,524
  Medium            60       34.6        682,810,264
  Low              120       26.7        748,137,361
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
-- REP WORKLIST (the app's main query, ranked by expected revenue at risk) --
account                          $ at risk (6 mo)  score category  state      driver                    
---------------------------------------------------------------------------------------------------------
Whitehead Institute                     4,059,630   46.1 High      new        Revenue vs 12-mo run rate 
Albuquerque Research Center             3,966,520   45.6 High      new        Revenue vs 12-mo run rate 
Massachusetts General Hospital          3,775,349   47.5 High      accepted   Revenue vs 12-mo run rate 
UPenn Perelman Medicine                 3,653,175   38.2 High      new        Support cases (6 mo): 0;  
AstraZeneca Biologics                   3,615,327   48.3 High      new        Revenue vs 12-mo run rate 
Boise Genomics Lab                      3,380,436   47.1 High      new        Revenue vs 12-mo run rate 
Buffalo Diagnostics Lab                 3,351,836   37.5 High      new        Revenue vs 12-mo run rate 
Penn Medicine Lancaster General         3,332,030   47.7 High      new        Rep activity trend (last  
Northwestern Feinberg                   3,311,535   34.0 High      new        High-priority cases (6 mo 
SAIC Life Sciences                      3,299,861   40.1 High      new        Backorder rate (6 mo): 46
```

## Latency - why Lakebase and not the warehouse

```text
-- LATENCY (single-account lookup, open connection, 20 runs) ----------
  database time only; per-screen times through the app are in evidence/07_latency.md
  p50 : 1.2 ms
  p95 : 2.2 ms
  min : 1.1 ms
  max : 2.3 ms
  this read happens on every app page load and every rep click
```
