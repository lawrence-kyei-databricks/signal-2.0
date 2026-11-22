# Signal 2.0 - CCG Account Risk Intelligence in Salesforce

A forward-looking account risk model for Thermo Fisher CCG, delivered where reps work: a Salesforce briefing popup, an AI/BI dashboard, a Genie agent, and a Databricks App backed by Lakebase.

## What a rep sees

1. **Salesforce Account page**: a morning-briefing popup with the risk score, the model's top drivers, an `ai_decide` action type and urgency, and three number-checked recommendations. Behind it, the embedded AI/BI dashboard and Genie agent.
2. **Signal Account Cockpit (Databricks App)**: a worklist served from Lakebase in milliseconds, where reps accept, dismiss, or snooze alerts. Every decision is recorded under the rep's own identity with an append-only audit row.

## Architecture

```
Salesforce CRM --Lakeflow Connect--> sf_* tables --+
CDM orders / shipments (cur_*) --------------------+--> customer_360 (SDP)          01_data
                                                   |
syn_account_monthly_history (synthetic, training) -+--> account_risk_model (UC)     02_ml
                                                   |      @champion, gated
                                                   v
                            03_score_and_brief: score -> drivers -> insights -> ai_decide + ai_query
                                                   |
              +------------------------------------+-----------------------------+
              v                                    v                             v
   Salesforce (Description JSON +      mv_customer_360 -> dashboard +    Lakebase synced table -> App
   Risk_Score__c / Risk_Category__c)   Genie agent (05_analytics)        (04_lakebase_app)
```

The refresh job in `06_orchestration` runs the pipeline and then `03_score_and_brief`, which ends by refreshing Lakebase and checking it matches Delta.

## Repository layout

| Path | What it is |
|---|---|
| `signal_config.py` | Single source of configuration (schema, IDs, Lakebase names, secret scope) plus the Salesforce login helper. Every notebook imports it. |
| `01_data/01_generate_crm_data` | Synthetic CRM accounts, contacts, opportunities, cases, tasks |
| `01_data/02_load_salesforce` | Loads the CRM data into the Salesforce dev org |
| `01_data/customer_360_pipeline/` | Lakeflow Spark Declarative Pipeline: `customer_360` gold materialized view |
| `02_ml/01_build_training_history` | Seeded synthetic account-month history with cause and effect, used only for training |
| `02_ml/02_train_risk_model` | Point-in-time training, out-of-time validation, gated promotion to `champion` |
| `02_ml/03_score_and_brief` | Production refresh: score, explain, insights, AI briefing, Salesforce writeback, Lakebase sync |
| `02_ml/ccg_risk_features.py` | Shared features, label, rule baseline, and driver logic (training and scoring use the same code) |
| `03_salesforce/01_deploy_salesforce` | Deploys and verifies the Salesforce package |
| `03_salesforce/package/` | Salesforce source: VF page, Lightning page, risk fields, permission set, CSP trusted site |
| `04_lakebase_app/01_lakebase_setup` | Lakebase operational schema, synced table (created if missing), write-path proof, latency |
| `04_lakebase_app/02_app_grants` | Least-privilege grants for the app service principal (SELECT + INSERT only) |
| `04_lakebase_app/03_demo_reset` | Owner-only cleanup of test rows and optional demo reset |
| `04_lakebase_app/app/` | Signal Account Cockpit (FastAPI + static UI) |
| `05_analytics/` | Versioned definitions: metric view YAML, Genie agent config, dashboard JSON |
| `06_orchestration/signal_refresh_job.json` | Refresh job definition |
| `benchmarks/` | `ai_decide` vs `ai_classify` benchmark |
| `scripts/check_secrets.py` | Secret scanner, run before every commit |

Objects that cannot live in a Git folder are kept in `signal-2.0-assets/` next to this repo: the MLflow experiment, the Genie agent, and the dashboard.

## ML model

- **Model:** `main.ccg_workshop_cdm.account_risk_model`, `StandardScaler` + `LogisticRegression` on 11 point-in-time features.
- **Predicts:** the probability that an account's revenue over the next 6 months falls below 60% of its trailing 12-month run rate. `ml_risk_score` = 100 x probability; High >= 50, Medium >= 25, Low < 25.
- **Validation:** out-of-time. Train on Aug-Nov 2025 cutoffs, test on Jan-Feb 2026. Current champion: AUC 0.818 vs 0.667 for the rule formula.
- **Promotion gates:** out-of-time AUC >= 0.70 and at least 0.05 above the rule; otherwise the new version stays `challenger`.
- **Drivers:** the top two per account from the model itself (coefficient x standardized value). Revenue level is a size control and never shown as a driver.
- **Scoring:** batch, anchored to the data snapshot date. Every run is appended to `account_risk_predictions`.
- **Training data caveat:** the demo CDM orders carry no link between operational signals and later revenue, so the model trains on a synthetic history anchored to real account levels. Set `HISTORY_SOURCE = "cdm"` in `02_train_risk_model` when real history is available; it needs about 23 months.

## AI briefing

`ai_decide` returns action type, urgency, and executive-attention probability in one call. `ai_query` writes three recommendations from one labeled fact per line, with rules against inventing, recalculating, or combining numbers and against numeric targets. Every number in a recommendation is checked against that account's facts; failures are regenerated once and withheld if they still fail (`account_briefing_v2.numbers_verified`).

## Security and access

- **Secrets:** all Salesforce credentials are read at runtime from the `ccg-salesforce` secret scope (`consumer-key`, `consumer-secret`). Nothing secret is stored in this repo.
- **App user authorization:** the app has the `genie` user-authorization scope, so Genie questions run with the signed-in rep's own permissions, and rep decisions record the signed-in user.
- **Lakebase least privilege:** the app service principal can SELECT the synced risk table and INSERT decisions and audit rows; it has no UPDATE, DELETE, or TRUNCATE.
- **Salesforce field access:** the `Signal2_Risk_Fields` permission set grants the risk fields; the deploy notebook assigns it to the integration user.
- **Before every commit:** `python scripts/check_secrets.py` must report no secrets.

## Setup (one time)

1. Create the secret scope and add the Salesforce External Client App credentials:
   ```
   databricks secrets create-scope ccg-salesforce
   databricks secrets put-secret ccg-salesforce consumer-key
   databricks secrets put-secret ccg-salesforce consumer-secret
   ```
2. Workspace admin: Settings > Security > Embed dashboards, approve the Salesforce Visualforce domains.
3. Run `01_data` (data and Salesforce load), then `03_salesforce/01_deploy_salesforce`.
4. Run `02_ml/01_build_training_history` and `02_ml/02_train_risk_model`.
5. Run `04_lakebase_app/01_lakebase_setup` and `02_app_grants`, then deploy the app from `04_lakebase_app/app`.
6. Create the refresh job from `06_orchestration/signal_refresh_job.json` (the deployed job is `Signal 2.0 - Account Risk Refresh`).

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| App error `permission denied for schema cockpit` | The app's `postgres` resource was re-attached, which recreates its Postgres role with no privileges | Re-run `04_lakebase_app/02_app_grants` |
| App worklist shows old scores | Lakebase synced table not refreshed after rescoring | Run the refresh job, or the last cell of `02_ml/03_score_and_brief` |
| App update drops resources | `PATCH /api/2.0/apps/{name}` without the `resources` list removes them | Always send the full `resources` list with any app update, then re-run `02_app_grants` |

Internal Databricks demo. Not for external distribution.
