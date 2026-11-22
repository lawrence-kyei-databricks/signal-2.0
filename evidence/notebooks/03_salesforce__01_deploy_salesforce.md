# Run evidence: Salesforce package deploy

Source notebook: `03_salesforce/01_deploy_salesforce`. Outputs exported 2026-11-22 15:09 UTC from the executed notebook (no images; tables and logs as text).

## Config and Salesforce session

```text
Salesforce: https://<redacted-salesforce-domain> | package: /Workspace/Users/<redacted-email>/thermofisher/CCG/signal-2.0/03_salesforce/package
```

## Deploy the package

```text
files: ['cspTrustedSites/Databricks_Workspace_Embed.cspTrustedSite', 'flexipages/Account_Record_Page.flexipage', 'objects/Account.object', 'package.xml', 'pages/Signal2_Risk_Dashboard.page', 'pages/Signal2_Risk_Dashboard.page-meta.xml', 'permissionsets/Signal2_Risk_Fields.permissionset']
deploy 0Afbm00000pFQssCAG: Succeeded
```

## Grant the integration user access to the risk fields

```text
Signal2_Risk_Fields assigned to integration user <redacted-email> (assigned now)
```

## Verify every component

```text
  risk fields writable       OK
  VF page                    OK
  CSP trusted site active    OK
  Lightning page             OK

Test: https://<redacted-salesforce-domain>/lightning/r/Account/001bm000030G3dyAAC/view
```
