# Run evidence: Unity Catalog: classification, lineage, grants, model registry

Source notebook: `01_data/03_govern_unity_catalog`. Outputs exported 2026-11-22 21:40 UTC from the executed notebook (no images; tables and logs as text).

## Config

```text
Governing 14 tables in main.ccg_workshop_cdm
```

## Classify and document every stage

| table_name | journey_stage | classification | origin | owner_domain |
|---|---|---|---|---|
| cur_sales_order_header | 1-ingest | internal | synthetic | commercial_sales |
| cur_sales_order_line | 1-ingest | internal | synthetic | commercial_sales |
| cur_shipment_line | 1-ingest | internal | synthetic | commercial_sales |
| sf_account | 1-ingest | internal | synthetic | commercial_sales |
| sf_case | 1-ingest | internal | synthetic | commercial_sales |
| sf_contact | 1-ingest | internal | synthetic | commercial_sales |
| sf_opportunity | 1-ingest | internal | synthetic | commercial_sales |
| sf_task | 1-ingest | internal | synthetic | commercial_sales |
| customer_360 | 2-curate | internal | synthetic | commercial_sales |
| account_briefing_v2 | 3-intelligence | internal | synthetic | commercial_sales |
| account_deep_insights | 3-intelligence | internal | synthetic | commercial_sales |
| account_risk_predictions | 3-intelligence | internal | synthetic | commercial_sales |
| account_risk_summary | 3-intelligence | internal | synthetic | commercial_sales |
| syn_account_monthly_history | 3-intelligence | internal | synthetic | commercial_sales |

(14 rows)

| table_name | column_name | data_classification |
|---|---|---|
| account_deep_insights | annual_revenue | confidential |
| account_deep_insights | revenue_at_risk | confidential |
| account_risk_summary | annual_revenue | confidential |
| account_risk_summary | open_pipeline_value | confidential |
| customer_360 | annual_revenue | confidential |
| customer_360 | open_pipeline_value | confidential |

(6 rows)

## Prove the journey is connected - Unity Catalog lineage

| source | target | written_by | last_seen |
|---|---|---|---|
| main.ccg_workshop_cdm.account_deep_insights | main.ccg_workshop_cdm.account_briefing_v2 | NOTEBOOK | 2026-11-22T13:02:29.269Z |
| main.ccg_workshop_cdm.account_risk_summary | main.ccg_workshop_cdm.account_deep_insights | NOTEBOOK | 2026-11-22T20:15:23.632Z |
| main.ccg_workshop_cdm.account_risk_summary | main.ccg_workshop_cdm.account_deep_insights | JOB | 2026-11-22T20:30:20.788Z |
| main.ccg_workshop_cdm.cur_sales_order_header | main.ccg_workshop_cdm.account_deep_insights | JOB | 2026-11-22T20:30:20.788Z |
| main.ccg_workshop_cdm.cur_sales_order_header | main.ccg_workshop_cdm.account_deep_insights | NOTEBOOK | 2026-11-22T20:15:23.632Z |
| main.ccg_workshop_cdm.cur_sales_order_line | main.ccg_workshop_cdm.account_deep_insights | JOB | 2026-11-22T20:30:20.788Z |
| main.ccg_workshop_cdm.cur_sales_order_line | main.ccg_workshop_cdm.account_deep_insights | NOTEBOOK | 2026-11-22T20:15:23.632Z |
| main.ccg_workshop_cdm.sf_account | main.ccg_workshop_cdm.account_deep_insights | JOB | 2026-11-22T20:30:20.788Z |
| main.ccg_workshop_cdm.sf_account | main.ccg_workshop_cdm.account_deep_insights | NOTEBOOK | 2026-11-22T20:15:23.632Z |
| main.ccg_workshop_cdm.sf_cdm_key_mapping | main.ccg_workshop_cdm.account_deep_insights | JOB | 2026-11-22T20:30:20.788Z |
| main.ccg_workshop_cdm.sf_cdm_key_mapping | main.ccg_workshop_cdm.account_deep_insights | NOTEBOOK | 2026-11-22T20:15:23.632Z |
| main.ccg_workshop_cdm.customer_360 | main.ccg_workshop_cdm.account_risk_summary | NOTEBOOK | 2026-11-22T20:15:10.308Z |
| main.ccg_workshop_cdm.customer_360 | main.ccg_workshop_cdm.account_risk_summary | JOB | 2026-11-22T20:30:11.213Z |
| main.ccg_workshop_cdm.cur_customer_sales_org | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.cur_customer_shipto | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.cur_product | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.cur_sales_order_header | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.cur_sales_order_line | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.cur_shipment_line | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.sf_account | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.sf_case | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.sf_cdm_key_mapping | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.sf_contact | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.sf_opportunity | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.sf_task | main.ccg_workshop_cdm.customer_360 | PIPELINE | 2026-11-22T20:28:40.944Z |
| main.ccg_workshop_cdm.account_risk_summary | main.ccg_workshop_cdm.mv_customer_360 | PIPELINE | 2026-11-22T20:40:38.977Z |
| main.ccg_workshop_cdm.account_risk_summary | main.ccg_workshop_cdm.mv_customer_360 | QUERY | 2026-11-22T20:41:55.342Z |
| main.ccg_workshop_cdm.account_risk_summary | main.ccg_workshop_cdm.mv_customer_360 | NOTEBOOK | 2026-11-22T20:41:23.914Z |
| main.ccg_workshop_cdm.account_risk_summary | main.ccg_workshop_cdm.mv_customer_360 | DASHBOARD_V3 | 2026-11-22T13:19:29.691Z |
| main.ccg_workshop_cdm.customer_360 | main.ccg_workshop_cdm.mv_customer_360 | QUERY | 2026-11-22T20:41:55.342Z |

(36 rows, first 30 shown)

```text
sf_account               -> customer_360             captured
  cur_sales_order_line     -> customer_360             captured
  customer_360             -> account_risk_summary     captured
  account_risk_summary     -> account_deep_insights    captured
  account_deep_insights    -> account_briefing_v2      captured
  account_risk_summary     -> mv_customer_360          captured
  account_risk_summary     -> lakebase account_risk_summary captured
  account_briefing_v2      -> lakebase account_briefing_v2 captured
  account_deep_insights    -> lakebase account_deep_insights captured
```

## Access: grants, model registry, secret scope

| Principal | ActionType | ObjectType | ObjectKey |
|---|---|---|---|
| ecca10ba-9ac5-464e-ba5b-4e0abc485513 | ALL PRIVILEGES | CATALOG | main |
| f91a2aa3-8bc7-4ec0-9e65-500f0e79587a | ALL PRIVILEGES | CATALOG | main |
| c3f1683b-c35f-47ae-ba72-e495e672ecac | ALL PRIVILEGES | CATALOG | main |
| collibra-edge-readers | EXECUTE | CATALOG | main |
| collibra-edge-readers | READ VOLUME | CATALOG | main |
| collibra-edge-readers | SELECT | CATALOG | main |
| collibra-edge-readers | USE SCHEMA | CATALOG | main |
| <redacted-email> | READ METADATA | METASTORE | field-eng-east |
| <redacted-email> | EXECUTE | CATALOG | main |
| <redacted-email> | SELECT | CATALOG | main |
| <redacted-email> | USE SCHEMA | CATALOG | main |
| account users | ALL PRIVILEGES | CATALOG | main |
| account users | EXTERNAL USE SCHEMA | CATALOG | main |
| account users | MANAGE | CATALOG | main |
| <redacted-email> | EXECUTE | SCHEMA | main.ccg_workshop_cdm |
| <redacted-email> | USE SCHEMA | SCHEMA | main.ccg_workshop_cdm |
| <redacted-email> | ALL PRIVILEGES | CATALOG | main |
| <redacted-email> | ALL PRIVILEGES | CATALOG | main |
| <redacted-email> | EXTERNAL USE SCHEMA | CATALOG | main |
| <redacted-email> | MANAGE | CATALOG | main |
| <redacted-email> | ALL PRIVILEGES | CATALOG | main |
| <redacted-email> | READ METADATA | METASTORE | field-eng-east |
| e11003f7-f6b6-41ce-8263-94cf9012fc57 | ALL PRIVILEGES | CATALOG | main |
| e11003f7-f6b6-41ce-8263-94cf9012fc57 | MANAGE | CATALOG | main |
| e11003f7-f6b6-41ce-8263-94cf9012fc57 | SELECT | CATALOG | main |
| e11003f7-f6b6-41ce-8263-94cf9012fc57 | USE SCHEMA | CATALOG | main |

(26 rows)

| Principal | ActionType | ObjectType | ObjectKey |
|---|---|---|---|
| ecca10ba-9ac5-464e-ba5b-4e0abc485513 | ALL PRIVILEGES | CATALOG | main |
| f91a2aa3-8bc7-4ec0-9e65-500f0e79587a | ALL PRIVILEGES | CATALOG | main |
| c3f1683b-c35f-47ae-ba72-e495e672ecac | ALL PRIVILEGES | CATALOG | main |
| collibra-edge-readers | SELECT | CATALOG | main |
| <redacted-email> | READ METADATA | METASTORE | field-eng-east |
| <redacted-email> | SELECT | CATALOG | main |
| account users | ALL PRIVILEGES | CATALOG | main |
| account users | MANAGE | CATALOG | main |
| <redacted-email> | ALL PRIVILEGES | CATALOG | main |
| <redacted-email> | ALL PRIVILEGES | CATALOG | main |
| <redacted-email> | MANAGE | CATALOG | main |
| <redacted-email> | ALL PRIVILEGES | CATALOG | main |
| <redacted-email> | READ METADATA | METASTORE | field-eng-east |
| e11003f7-f6b6-41ce-8263-94cf9012fc57 | ALL PRIVILEGES | CATALOG | main |
| e11003f7-f6b6-41ce-8263-94cf9012fc57 | MANAGE | CATALOG | main |
| e11003f7-f6b6-41ce-8263-94cf9012fc57 | SELECT | CATALOG | main |

(16 rows)

```text
Model main.ccg_workshop_cdm.account_risk_model: 6 versions, champion = v6
  champion tags: {'output': 'probability', 'target': 'revenue_decline_next_6m', 'training_data': 'synthetic_history'}
  champion description: Forward-looking: P(revenue over next 6 months < 60% of trailing 12-month run rate). LogisticRegression on 11 point-in-time features (ccg_risk_features.py). Use predict_proba[:, 1].

Secret scope 'ccg-salesforce' keys (names only, values never printed): ['consumer-key', 'consumer-secret', 'databricks-pat', 'sf-domain']
```
