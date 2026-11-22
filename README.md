# Signal 2.0 - Stop Losing Lab-Supply Accounts You Could Have Saved

**Industry:** Life sciences tools and lab-supply distribution (Healthcare and Life Sciences)
**Buyer:** VP Commercial / Sales Operations | **Users:** field sales reps and sales managers
**Status:** working prototype, all data synthetic, every stage executed (see [evidence/](evidence/))

## The business problem

A lab-supply distributor serves hospitals, biopharma, CROs, and academic labs. When an account starts to slip, the warning signs live in different systems: **backorders and late deliveries** in the ERP, **rep inactivity and support cases** in Salesforce. Reps see the revenue drop only after it happens. Today's prioritization is a static rule (backorders + inactivity + cases), and it misses most of the accounts that are about to decline.

## The outcome

Signal 2.0 predicts which accounts will lose revenue in the next 6 months, explains why, recommends what the rep should do, and puts it where reps already work: on the Salesforce account page, in a rep worklist app, and in plain-English Q&A.

| KPI (buyer's language) | Today (rule) | With Signal 2.0 | Source |
|---|---|---|---|
| Declining accounts a rep sees when reviewing the top 20% of the book | 33.8% | **51.5%** | [evidence/05_business_value.md](evidence/05_business_value.md) |
| Lost revenue those accounts represent | 34.7% | **59.8%** | same |
| Prediction accuracy (out-of-time AUC) | 0.667 | **0.818** | [training run](evidence/notebooks/02_ml__02_train_risk_model.md) |
| Time from new data to updated scores in Salesforce, app, and Genie | manual | **about 4 minutes**, one job | [job run](evidence/02_refresh_job_run.md) |
| Rep worklist lookup | n/a | **1.3 ms p50** | [Lakebase run](evidence/notebooks/04_lakebase_app__01_lakebase_setup.md) |

**Current book (200 accounts, $177.0M annual revenue):** $42.7M of expected revenue at risk (annual revenue x the model's probability of decline). $30.2M of it sits in the 79 High and Medium accounts reps are asked to act on.

**Value estimate.** With the same rep effort, the model puts about 25 more points of the at-risk revenue in front of reps (59.8% vs 34.7%). Applied to today's $42.7M, that is **about $10.7M more at-risk revenue reps can act on**. *Assuming* reps save 25% of the at-risk revenue they work, that is **about $2.7M retained per year** for a 200-account book. The save rate is an assumption to validate in a pilot; the detection lift is measured.

## What the rep and the manager see

1. **Salesforce account page:** a morning briefing popup with the risk score, the model's two main drivers (for example *"Backorder rate (6 mo): 72%; Revenue momentum: -80%"*), a recommended action and urgency, and three recommendations whose numbers are checked against the account's real data. Risk fields are reportable in Salesforce list views.
2. **Signal Account Cockpit (Databricks App):** a worklist of at-risk accounts. Reps accept, snooze, or dismiss; every decision is recorded under the signed-in rep with an append-only audit row.
3. **Genie agent:** managers ask *"Which 5 accounts have the highest risk score, and what is their top risk driver?"* and get the answer, the SQL, and a chart. Genie runs with the user's own permissions.

## The integrated data journey

```mermaid
flowchart LR
    subgraph S["1. Ingest - Lakeflow"]
        SF["Salesforce CRM<br/>accounts, opportunities,<br/>cases, activities"]
        ERP["ERP orders, shipments,<br/>backorders (synthetic)"]
        LFC["Lakeflow Connect<br/>managed ingestion"]
        SDP["Lakeflow Declarative Pipeline<br/>customer_360 gold"]
        SF --> LFC
        LFC --> SDP
        ERP --> SDP
    end
    subgraph G["2. Govern - Unity Catalog"]
        UC["Tags, classification, lineage,<br/>model registry, grants,<br/>secret scope"]
    end
    subgraph I["3. Intelligence - ML + GenAI"]
        ML["Risk model<br/>account_risk_model@champion"]
        AI["ai_decide + ai_query<br/>number-checked briefings"]
        ML --> AI
    end
    subgraph V["4. Serve"]
        LB["Lakebase<br/>synced risk + rep decisions"]
        MV["Metric view<br/>mv_customer_360"]
        GN["Genie agent"]
        APP["Databricks App<br/>Signal Account Cockpit"]
        SFO["Salesforce page<br/>briefing + risk fields"]
        DB["AI/BI dashboard"]
    end
    SDP --> ML
    AI --> SFO
    ML --> LB --> APP
    ML --> MV --> GN --> APP
    MV --> DB
    UC -. governs .-> SDP
    UC -. governs .-> ML
    UC -. governs .-> MV
    UC -. governs .-> LB
```

One job (`06_orchestration`) runs it end to end: refresh Customer 360, score with the champion model, write insights and AI briefings, push to Salesforce, refresh Lakebase, and check that Lakebase matches Delta. Unity Catalog lineage confirms every link, from the ingested Salesforce tables to the Lakebase table the app reads ([governance evidence](evidence/notebooks/01_data__03_govern_unity_catalog.md)).

| Stage | Databricks capability | Where | Evidence |
|---|---|---|---|
| Ingest | Lakeflow Connect (Salesforce, 5 objects) + Lakeflow Declarative Pipeline | `01_data/lakeflow_connect/`, `01_data/customer_360_pipeline/` | [01_lakeflow_ingestion.md](evidence/01_lakeflow_ingestion.md) |
| Govern | Unity Catalog governed tags, column classification, lineage, model registry, secret scope | `01_data/03_govern_unity_catalog` | [governance](evidence/notebooks/01_data__03_govern_unity_catalog.md) |
| ML | Point-in-time training, out-of-time validation, gated promotion, batch scoring | `02_ml/` | [training](evidence/notebooks/02_ml__02_train_risk_model.md), [scoring](evidence/notebooks/02_ml__03_score_and_brief.md) |
| Gen AI | `ai_decide` (action, urgency) + `ai_query` (recommendations) with number verification | `02_ml/03_score_and_brief` | [scoring](evidence/notebooks/02_ml__03_score_and_brief.md) |
| Operational serving | Lakebase synced table + transactional rep decisions | `04_lakebase_app/` | [Lakebase](evidence/notebooks/04_lakebase_app__01_lakebase_setup.md), [grants](evidence/notebooks/04_lakebase_app__02_app_grants.md) |
| Natural language | Genie agent on a governed metric view | `05_analytics/` | [03_genie_agent.md](evidence/03_genie_agent.md) |
| Business app | Databricks App + Salesforce page | `04_lakebase_app/app/`, `03_salesforce/` | [04_serving_salesforce_lakebase_app.md](evidence/04_serving_salesforce_lakebase_app.md) |

## Decisions and trade-offs

| Decision | Why | Trade-off |
|---|---|---|
| Logistic regression, not gradient boosting | It scored best out-of-time and gives per-account drivers directly (coefficient x standardized value), so reps see *why* | Less capacity for complex interactions; revisit with real history |
| Train on a synthetic history anchored to real account levels | The demo ERP data has no link between operational pain and later revenue, so no model could learn it | Cause and effect comes from the generator. `HISTORY_SOURCE = "cdm"` switches to real history (needs about 23 months) |
| Out-of-time validation with promotion gates (AUC >= 0.70 and >= 0.05 above the rule) | Random splits overstate accuracy on time-series accounts; gates stop a weaker model reaching reps | Fewer training rows per model |
| Batch scoring, not a real-time endpoint | Risk changes when data refreshes, not per click. Salesforce reads scores from its own records, so there are no callouts or network allow-lists | Scores are as fresh as the last job run (about 4 minutes end to end) |
| Lakebase for the app, not querying Delta directly | Rep clicks need millisecond reads and transactional writes (decision + audit in one transaction) | A second store to keep in sync; the job refreshes it and verifies parity |
| One metric view for Genie and the dashboard | One definition of risk, revenue at risk, and drivers; Genie and dashboards cannot disagree | Changes go through the metric view, not ad hoc SQL |
| `ai_decide` for structured choices, `ai_query` with a number check | Structured outputs are reliable; free-text numbers can be wrong, so every number is checked against the account's data and failures are withheld | Extra LLM call on retry (2 of 200 retried, 0 withheld in the last run) |
| App user authorization (scopes `genie`, `sql`) | Genie answers and audit rows use the real rep's identity and permissions | Each user must have access to the Genie agent and warehouse |

## Security and governance

- **No secrets in code:** Salesforce credentials come from the `ccg-salesforce` secret scope; `scripts/check_secrets.py` runs before every commit.
- **Least privilege in Lakebase:** the app service principal can read risk scores and append decisions and audit rows; UPDATE, DELETE, and TRUNCATE are withheld and verified.
- **Classification:** every table carries governed `data_classification`, journey stage, and `data_origin = synthetic` tags; revenue columns are `confidential`.
- **Model governance:** Unity Catalog model registry with a `champion` alias, set only when both promotion gates pass.

## How AI was used as a teammate

Built with **Genie Code** (Databricks' AI agent) in one workspace, with me making the product, modeling, and architecture decisions. Patterns that made the build trustworthy:

- **Evidence-first loop:** every change was run, read back, and checked by a second method (for example, Genie's answer cross-checked against the scored table; Lakebase checked against Delta after every sync).
- **AI checking AI:** the briefing step uses an LLM to write recommendations and code to verify every number before anything reaches Salesforce.
- **Regression tests on real failures:** the app's Genie renderer was tested in Node against an actual broken answer before deploying.
- **Mistakes caught and documented:** for example, an app update that dropped resources and reset database grants was diagnosed, fixed, and turned into a troubleshooting rule.

## Repository layout

| Path | What it is |
|---|---|
| [`evidence/`](evidence/) | Execution evidence as text: notebook outputs, pipeline and job runs, Genie Q&A, serving checks, value calculation |
| [`docs/`](docs/) | Business deck and roleplay preparation |
| `01_data/` | Lakeflow Connect definition, CRM data generation and Salesforce load, Customer 360 pipeline, Unity Catalog governance |
| `02_ml/` | Training history, model training, scoring and AI briefing, shared feature module |
| `03_salesforce/` | Salesforce source package and deploy notebook |
| `04_lakebase_app/` | Lakebase setup, grants, demo reset, Databricks App |
| `05_analytics/` | Metric view, Genie agent, and dashboard definitions |
| `06_orchestration/` | Refresh job definition |
| `signal_config.py` | Single source of configuration (names, IDs, secret scope) |

## Run it

1. Create the `ccg-salesforce` secret scope with `consumer-key` and `consumer-secret`.
2. `01_data`: generate and load CRM data, run Lakeflow Connect, the Customer 360 pipeline, and the governance notebook.
3. `03_salesforce/01_deploy_salesforce`.
4. `02_ml/01_build_training_history`, then `02_ml/02_train_risk_model`.
5. `04_lakebase_app/01_lakebase_setup` and `02_app_grants`; deploy the app from `04_lakebase_app/app`.
6. Create the job from `06_orchestration/signal_refresh_job.json`; each run refreshes everything above.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| App error `permission denied for schema cockpit` | The app's `postgres` resource was re-attached, recreating its database role without privileges | Re-run `04_lakebase_app/02_app_grants` |
| Genie in the app returns 403 | Forwarded user token lacks a scope, or the user has not consented | App scopes must include `genie` and `sql`; reopen the app to consent |
| App update drops resources | `PATCH /api/2.0/apps/{name}` without `resources` removes them | Use `POST /api/2.0/apps/{name}/update` with an `update_mask` |
| App shows old scores | Lakebase not refreshed | Run the refresh job |

All data in this repository is synthetic. No customer data is included.
