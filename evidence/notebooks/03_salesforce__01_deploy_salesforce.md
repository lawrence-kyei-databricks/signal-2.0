# Run evidence: Salesforce: deploy the source package and verify every component

Source notebook: `03_salesforce/01_deploy_salesforce`. Outputs exported 2026-11-22 22:58 UTC from the executed notebook (no images; tables and logs as text).

## Config and Salesforce session

```text
Salesforce: https://[REDACTED] | package: <repo>/03_salesforce/package
```

## Deploy the package

```text
files: ['cspTrustedSites/Databricks_Workspace_Embed.cspTrustedSite', 'flexipages/Account_Record_Page.flexipage', 'objects/Account.object', 'package.xml', 'pages/Signal2_Risk_Dashboard.page', 'pages/Signal2_Risk_Dashboard.page-meta.xml', 'permissionsets/Signal2_Risk_Fields.permissionset']
placeholders filled: {'Signal2_Risk_Dashboard.page': 4, 'Databricks_Workspace_Embed.cspTrustedSite': 1}
deploy 0Afbm00000pHTOPCA4: Succeeded
```

## Grant the integration user access to the risk fields

```text
Signal2_Risk_Fields assigned to integration user <redacted-email> (already assigned)
```

## Verify every component

```text
risk fields writable       OK
  VF page                    OK
  CSP trusted site active    OK
  Lightning page             OK
  page embeds this workspace OK

Test: https://<redacted-salesforce-domain>/lightning/r/Account/001bm000030G3dyAAC/view
```
