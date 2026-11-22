# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# MAGIC %md
# MAGIC # Deploy Salesforce Components (Signal 2.0)
# MAGIC
# MAGIC Deploys the source package in `./package` to the Salesforce org with the Metadata API, then verifies it.
# MAGIC Idempotent: safe to re-run. Credentials come from the `ccg-salesforce` secret scope.
# MAGIC
# MAGIC | Component | Purpose |
# MAGIC |---|---|
# MAGIC | `Signal2_Risk_Dashboard` (Visualforce) | Morning-briefing popup + embedded AI/BI dashboard and Genie agent; reads the JSON briefing in `Account.Description` |
# MAGIC | `Account_Record_Page` (Lightning page) | Places the Visualforce page on the Account record page (750px) |
# MAGIC | `Risk_Score__c`, `Risk_Category__c`, `Last_Risk_Assessment__c` | Reportable risk fields written by `02_ml/03_score_and_brief` |
# MAGIC | `Signal2_Risk_Fields` (permission set) | Field-level access to the risk fields; assigned to the integration user below |
# MAGIC | `Databricks_Workspace_Embed` (CSP trusted site) | Allows the workspace to be framed inside Salesforce |
# MAGIC
# MAGIC Prerequisite (one-time, in Databricks): add the Salesforce Visualforce domains to Settings > Security > Embed dashboards.

# COMMAND ----------

# DBTITLE 1,Config and Salesforce session
# Repo bootstrap: make signal_config (repo root) and sibling modules importable wherever the repo is checked out
import os, sys, importlib
NB_DIR = "/Workspace" + os.path.dirname(dbutils.notebook.entry_point.getDbutils().notebook().getContext().notebookPath().get()).replace("/Workspace", "", 1)
REPO_ROOT = os.path.dirname(NB_DIR)
for _p in (NB_DIR, REPO_ROOT):
    if _p in sys.path:
        sys.path.remove(_p)
    sys.path.insert(0, _p)
importlib.invalidate_caches()
import signal_config as cfg
importlib.reload(cfg)
import base64, io, time, zipfile
import xml.etree.ElementTree as ET
import requests

SF_URL, SF_TOKEN = cfg.salesforce_session(dbutils)
REST = f"{SF_URL}/services/data/v{cfg.SF_API_VERSION}"
HDRS = {"Authorization": f"Bearer {SF_TOKEN}", "Content-Type": "application/json"}
MD = "http://soap.sforce.com/2006/04/metadata"
PACKAGE_DIR = os.path.join(NB_DIR, "package")

def metadata(action, body):
    envelope = (f'<?xml version="1.0" encoding="UTF-8"?><soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:met="{MD}">'
                f'<soapenv:Header><met:SessionHeader><met:sessionId>{SF_TOKEN}</met:sessionId></met:SessionHeader></soapenv:Header>'
                f'<soapenv:Body>{body}</soapenv:Body></soapenv:Envelope>')
    r = requests.post(f"{SF_URL}/services/Soap/m/{cfg.SF_API_VERSION}", data=envelope, timeout=60,
                      headers={"Content-Type": "text/xml", "SOAPAction": action})
    r.raise_for_status()
    return ET.fromstring(r.text)

print(f"Salesforce: {SF_URL} | package: {PACKAGE_DIR}")

# COMMAND ----------

# DBTITLE 1,Deploy the package
buf = io.BytesIO()
with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
    for root, _, files in os.walk(PACKAGE_DIR):
        for name in files:
            full = os.path.join(root, name)
            zf.write(full, os.path.relpath(full, PACKAGE_DIR))
print("files:", sorted(zipfile.ZipFile(io.BytesIO(buf.getvalue())).namelist()))

deploy_id = metadata("deploy", f"<met:deploy><met:ZipFile>{base64.b64encode(buf.getvalue()).decode()}</met:ZipFile>"
                     "<met:DeployOptions><met:singlePackage>true</met:singlePackage><met:rollbackOnError>true</met:rollbackOnError>"
                     "<met:testLevel>NoTestRun</met:testLevel></met:DeployOptions></met:deploy>").find(f".//{{{MD}}}id").text
for _ in range(60):
    time.sleep(5)
    res = metadata("checkDeployStatus", f"<met:checkDeployStatus><met:asyncProcessId>{deploy_id}</met:asyncProcessId>"
                   "<met:includeDetails>true</met:includeDetails></met:checkDeployStatus>")
    if res.find(f".//{{{MD}}}done").text == "true":
        break
status = res.find(f".//{{{MD}}}status").text
failures = [(f.findtext(f"{{{MD}}}fullName"), f.findtext(f"{{{MD}}}problem")) for f in res.iter(f"{{{MD}}}componentFailures")]
print(f"deploy {deploy_id}: {status}")
assert status == "Succeeded", f"Deploy failed: {failures}"

# COMMAND ----------

# DBTITLE 1,Grant the integration user access to the risk fields
me = requests.get(f"{SF_URL}/services/oauth2/userinfo", headers=HDRS, timeout=30).json()
user_id = me["user_id"]
ps_id = requests.get(f"{REST}/query", headers=HDRS, params={"q": "SELECT Id FROM PermissionSet WHERE Name = 'Signal2_Risk_Fields'"}).json()["records"][0]["Id"]
existing = requests.get(f"{REST}/query", headers=HDRS, params={
    "q": f"SELECT Id FROM PermissionSetAssignment WHERE AssigneeId = '{user_id}' AND PermissionSetId = '{ps_id}'"}).json()["totalSize"]
if not existing:
    r = requests.post(f"{REST}/sobjects/PermissionSetAssignment", headers=HDRS, json={"AssigneeId": user_id, "PermissionSetId": ps_id})
    r.raise_for_status()
print(f"Signal2_Risk_Fields assigned to integration user {me.get('preferred_username')} ({'already assigned' if existing else 'assigned now'})")

# COMMAND ----------

# DBTITLE 1,Verify every component
fields = {f["name"]: f["updateable"] for f in requests.get(f"{REST}/sobjects/Account/describe", headers=HDRS).json()["fields"]}
checks = {
    "risk fields writable": all(fields.get(f) for f in ["Risk_Score__c", "Risk_Category__c", "Last_Risk_Assessment__c"]),
    "VF page": requests.get(f"{REST}/query", headers=HDRS, params={"q": "SELECT COUNT() FROM ApexPage WHERE Name = 'Signal2_Risk_Dashboard'"}).json()["totalSize"] == 1,
    "CSP trusted site active": requests.get(f"{REST}/tooling/query", headers=HDRS, params={
        "q": "SELECT IsActive FROM CspTrustedSite WHERE DeveloperName = 'Databricks_Workspace_Embed'"}).json()["records"][0]["IsActive"],
    "Lightning page": requests.get(f"{REST}/tooling/query", headers=HDRS, params={
        "q": "SELECT COUNT() FROM FlexiPage WHERE DeveloperName = 'Account_Record_Page'"}).json()["size"] == 1,
}
for k, v in checks.items():
    print(f"  {k:26s} {'OK' if v else 'MISSING'}")
assert all(checks.values()), f"Verification failed: {checks}"
print(f"\nTest: https://{cfg.SF_DOMAIN.replace('.my.salesforce.com', '.lightning.force.com')}/lightning/r/Account/001bm000030G3dyAAC/view")