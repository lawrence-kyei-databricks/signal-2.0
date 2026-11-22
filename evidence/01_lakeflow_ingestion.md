# Run evidence: Lakeflow ingestion and curation

## Lakeflow Connect - Salesforce (managed ingestion, definition in `01_data/lakeflow_connect/`)

Pipeline `CCG Salesforce Ingestion`, 5 objects: Account, Contact, Opportunity, Case, Task.

| update_id | state | started |
|---|---|---|
| 0a616d25-9b3b-45d3-b6b0-1615f555b1ea | COMPLETED | 2026-11-22 14:54 UTC |
| 6d6d9580-8a96-4407-a3f1-c5fde1fae3d4 | COMPLETED | 2026-10-01 01:17 UTC |
| d3e45d6c-632c-43e8-b07e-a1b09a27fa7a | COMPLETED | 2026-10-01 01:09 UTC |

Rows in the Unity Catalog destination tables after the latest run:

| table | rows |
|---|---|
| sf_account | 201 |
| sf_contact | 496 |
| sf_opportunity | 400 |
| sf_case | 300 |
| sf_task | 800 |

## Lakeflow Declarative Pipeline - Customer 360 gold (`01_data/customer_360_pipeline/`)

| update_id | state | started |
|---|---|---|
| 466146f8-8c5d-4fa9-bb33-280159740dfe | COMPLETED | 2026-11-22 14:05 UTC |
| dfde3925-04d6-49aa-a73f-fe825980fb15 | COMPLETED | 2026-10-05 18:47 UTC |
| 71e55ce2-5fd2-4ee0-9faa-f35b23189b24 | COMPLETED | 2026-10-01 03:56 UTC |

`customer_360` rows: 200
