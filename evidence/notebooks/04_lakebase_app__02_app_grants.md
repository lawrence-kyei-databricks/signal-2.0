# Run evidence: Lakebase: least-privilege grants for the app service principal

Source notebook: `04_lakebase_app/02_app_grants`. Outputs exported 2026-11-22 21:53 UTC from the executed notebook (no images; tables and logs as text).

## Config

```text
========================================================================
LAKEBASE ROLES & GRANTS
run at    : 2026-11-22T20:49:18.912377+00:00
========================================================================
app       : signal-account-cockpit
app SP    : 47c20dd6-5659-42e2-8ea2-88fd9e16e70d
host      : <lakebase-host>
granting as: <redacted-email>
```

## Confirm the SP role exists

```text
-- POSTGRES ROLES ON BRANCH -------------------------------------------
  <user-role>                                        type=RoleIdentityType.USER
  dbrx-apps-47c20dd6-5659-42e2-8ea2-88fd9e16e70d       type=RoleIdentityType.SERVICE_PRINCIPAL

SP postgres role resolved: 47c20dd6-5659-42e2-8ea2-88fd9e16e70d
```

## Apply least-privilege grants

```text
-- GRANTS APPLIED ------------------------------------------------------
  cockpit      : USAGE, SELECT                      (read-only)
  cockpit_app  : USAGE, SELECT, INSERT              (append-only)
  sequences    : USAGE, SELECT                      (for BIGSERIAL ids)
  withheld     : UPDATE, DELETE, TRUNCATE everywhere
```

## Verify - what can the SP actually do?

```text
-- EFFECTIVE PRIVILEGES (from information_schema) ----------------------
schema         table                      privilege 
------------------------------------------------------
cockpit        account_briefing_v2        SELECT    
cockpit        account_deep_insights      SELECT    
cockpit        account_risk_summary       SELECT    
cockpit_app    action_audit               INSERT    
cockpit_app    action_audit               SELECT    
cockpit_app    rep_actions                INSERT    
cockpit_app    rep_actions                SELECT    

privilege types granted : ['INSERT', 'SELECT']
  UPDATE   : correctly withheld
  DELETE   : correctly withheld
  TRUNCATE : correctly withheld
```

## Prove the SP can do its job and nothing more

```text
-- NEGATIVE TEST (as grantor, simulating SP limits) -------------------
  cockpit.account_risk_summary     SELECT  -> True   (as designed)
  cockpit_app.rep_actions          INSERT  -> True   (as designed)
  cockpit_app.rep_actions          UPDATE  -> False  (as designed)
  cockpit_app.action_audit         INSERT  -> True   (as designed)
  cockpit_app.action_audit         DELETE  -> False  (as designed)
```
