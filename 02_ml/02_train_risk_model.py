# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# DBTITLE 1,Overview
# MAGIC %md
# MAGIC # CCG Account Risk Model - Training (forward-looking)
# MAGIC
# MAGIC Trains `main.ccg_workshop_cdm.account_risk_model` to predict a **future business outcome**: will an account's revenue over the **next 6 months** fall below 60% of its trailing 12-month run rate? Notebook `03_score_and_brief` scores real accounts with `@champion` and the probability becomes the risk score reps see in Salesforce.
# MAGIC
# MAGIC **Design**
# MAGIC - **Training data:** point-in-time snapshots from `syn_account_monthly_history` (`01_build_training_history`, synthetic, anchored to real account levels). Each snapshot uses only months up to its cutoff for features, and the following 6 months for the label.
# MAGIC - **Features:** 11 signals from `ccg_risk_features.py` (shared with scoring): revenue level and momentum, backorder rate, delivery slips, rep activity and recency, support cases.
# MAGIC - **Model:** `StandardScaler` + `LogisticRegression` - chosen because it validated best out-of-time and gives per-account drivers directly (coefficient x standardized value).
# MAGIC - **Validation:** out-of-time. Train on cutoffs Aug-Nov 2025, test on Jan-Feb 2026 (Dec skipped as a gap). Compared against the point-in-time rule formula behind `risk_score_raw`.
# MAGIC - **Promotion gates:** out-of-time AUC >= 0.70 **and** at least 0.05 above the rule. Only then does the new version become `champion`.
# MAGIC - **Serving:** batch only. Scores change when data refreshes; Salesforce reads them from its own records.
# MAGIC
# MAGIC **Caveat:** the cause-and-effect the model learns comes from the synthetic history. When real CDM history is available, set `HISTORY_SOURCE = "cdm"`; nothing else changes.

# COMMAND ----------

# DBTITLE 1,Configuration
import os, sys
import mlflow
import numpy as np
import pandas as pd
from mlflow import MlflowClient
from mlflow.models import infer_signature
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import average_precision_score, brier_score_loss, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

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
import ccg_risk_features as rf
importlib.reload(rf)

mlflow.set_registry_uri("databricks-uc")
client = MlflowClient()

# Training history - the ONE switch to move from synthetic to real data:
#   "synthetic" -> syn_account_monthly_history (01_build_training_history)
#   "cdm"       -> real CDM orders/shipments + Salesforce activity, built by the same SQL used for scoring
HISTORY_SOURCE = "synthetic"
HISTORY_TABLE = cfg.SYN_HISTORY_TABLE
MODEL_NAME = cfg.MODEL_NAME
EXPERIMENT_PATH = cfg.EXPERIMENT_PATH   # experiments cannot live inside a Git folder
RANDOM_STATE = 42

# Cutoffs are derived from the data: each needs 12 months before (features + baseline) and 6 after (label).
# The last TEST_CUTOFFS are the out-of-time test, GAP_CUTOFFS are skipped, everything earlier is training.
TEST_CUTOFFS, GAP_CUTOFFS, MIN_TRAIN_CUTOFFS = 2, 1, 3

MIN_OOT_AUC = 0.70
MIN_LIFT_OVER_RULE = 0.05

mlflow.set_experiment(EXPERIMENT_PATH)
print("Features:", rf.FEATURES)
print("Experiment:", EXPERIMENT_PATH, "| id:", mlflow.get_experiment_by_name(EXPERIMENT_PATH).experiment_id)

# COMMAND ----------

# DBTITLE 1,Build Point-in-Time Snapshots
if HISTORY_SOURCE == "synthetic":
    history = spark.table(HISTORY_TABLE).toPandas()
elif HISTORY_SOURCE == "cdm":
    history = spark.sql(rf.REAL_MONTHLY_SCORING_SQL).toPandas()
else:
    raise ValueError(f"Unknown HISTORY_SOURCE {HISTORY_SOURCE!r}")

months = pd.to_datetime(history.month_start)
CUTOFFS = pd.date_range(months.min() + pd.DateOffset(months=11), months.max() - pd.DateOffset(months=rf.HORIZON_MONTHS), freq="MS")
needed = MIN_TRAIN_CUTOFFS + GAP_CUTOFFS + TEST_CUTOFFS
if len(CUTOFFS) < needed:
    raise ValueError(f"{HISTORY_SOURCE} history spans {months.min().date()} to {months.max().date()}, which allows {len(CUTOFFS)} "
                     f"cutoff(s); out-of-time validation needs {needed} (about {needed + 17} months of history).")
TEST_CUTOFF_MIN = CUTOFFS[-TEST_CUTOFFS]
TRAIN_CUTOFF_MAX = CUTOFFS[-(TEST_CUTOFFS + GAP_CUTOFFS + 1)]
print(f"History: {HISTORY_SOURCE} | cutoffs {CUTOFFS[0].date()}..{CUTOFFS[-1].date()} | train <= {TRAIN_CUTOFF_MAX.date()} | test >= {TEST_CUTOFF_MIN.date()}")

snaps = rf.build_snapshots(history, CUTOFFS)

train = snaps[snaps.cutoff_month <= TRAIN_CUTOFF_MAX]
test = snaps[snaps.cutoff_month >= TEST_CUTOFF_MIN]
assert snaps[rf.FEATURES].notna().all().all(), "Features contain nulls"
assert not snaps.duplicated(["customer_shipto_key", "cutoff_month"]).any(), "Duplicate account-snapshot rows"

print(f"Snapshots: {len(snaps)} rows over {snaps.cutoff_month.nunique()} cutoffs | train {len(train)} | test {len(test)}")
display(snaps.groupby("cutoff_month").agg(accounts=("label", "size"), decline_rate=("label", "mean")).round(3).reset_index())

# COMMAND ----------

# DBTITLE 1,Train, Validate Out-of-Time, Register
def make_model():
    return make_pipeline(StandardScaler(), LogisticRegression(max_iter=3000, C=0.5))

# 1. Out-of-time validation: fit on older snapshots, score later ones the model never saw
oot_model = make_model().fit(train[rf.FEATURES], train.label)
p_test = oot_model.predict_proba(test[rf.FEATURES])[:, 1]
gbc = GradientBoostingClassifier(n_estimators=200, max_depth=3, learning_rate=0.05, subsample=0.8, random_state=RANDOM_STATE)
gbc.fit(train[rf.FEATURES], train.label)

metrics = {
    "oot_auc": roc_auc_score(test.label, p_test),
    "oot_pr_auc": average_precision_score(test.label, p_test),
    "oot_brier": brier_score_loss(test.label, p_test),
    "oot_rule_auc": roc_auc_score(test.label, rf.rule_score(test)),
    "oot_gbc_auc": roc_auc_score(test.label, gbc.predict_proba(test[rf.FEATURES])[:, 1]),
    "oot_base_rate": test.label.mean(),
    "n_train": len(train), "n_test": len(test),
}
metrics["oot_lift_over_rule"] = metrics["oot_auc"] - metrics["oot_rule_auc"]

# 2. Final model: same recipe refit on all snapshots
final_model = make_model().fit(snaps[rf.FEATURES], snaps.label)
coefs = pd.Series(final_model.named_steps["logisticregression"].coef_[0], index=rf.FEATURES).sort_values(key=abs, ascending=False)

with mlflow.start_run(run_name="account_decline_risk_logreg") as run:
    mlflow.log_params({"model_type": "LogisticRegression", "C": 0.5, "target": "revenue_decline_next_6m",
                       "horizon_months": rf.HORIZON_MONTHS, "decline_threshold": rf.DECLINE_THRESHOLD,
                       "history_source": HISTORY_SOURCE, "cutoffs": f"{CUTOFFS[0].date()}..{CUTOFFS[-1].date()}",
                       "n_features": len(rf.FEATURES)})
    mlflow.log_metrics(metrics)
    mlflow.log_metrics({f"coef_{k}": float(v) for k, v in coefs.items()})
    model_info = mlflow.sklearn.log_model(
        final_model,
        name="model",
        signature=infer_signature(snaps[rf.FEATURES], final_model.predict_proba(snaps[rf.FEATURES])),
        input_example=snaps[rf.FEATURES].head(3),
        pyfunc_predict_fn="predict_proba",
        registered_model_name=MODEL_NAME,
    )

new_version = model_info.registered_model_version
client.update_model_version(MODEL_NAME, new_version,
    description="Forward-looking: P(revenue over next 6 months < 60% of trailing 12-month run rate). "
                "LogisticRegression on 11 point-in-time features (ccg_risk_features.py). Use predict_proba[:, 1].")
for k, v in {"target": "revenue_decline_next_6m", "training_data": f"{HISTORY_SOURCE}_history", "output": "probability"}.items():
    client.set_model_version_tag(MODEL_NAME, new_version, k, v)

print(f"Run {run.info.run_id} -> {MODEL_NAME} v{new_version}")
print({k: round(float(v), 3) for k, v in metrics.items()})
display(coefs.rename("coefficient (standardized)").reset_index().rename(columns={"index": "feature"}))

# COMMAND ----------

# DBTITLE 1,Gate and Promote
# New version starts as challenger; it becomes champion only if it clears both gates
client.set_registered_model_alias(MODEL_NAME, "challenger", new_version)

# Reload from the registry to prove the logged artifact reproduces the in-memory model
reloaded = mlflow.sklearn.load_model(f"models:/{MODEL_NAME}/{new_version}")
assert np.allclose(reloaded.predict_proba(snaps[rf.FEATURES])[:, 1], final_model.predict_proba(snaps[rf.FEATURES])[:, 1])

gate_auc = metrics["oot_auc"] >= MIN_OOT_AUC
gate_lift = metrics["oot_lift_over_rule"] >= MIN_LIFT_OVER_RULE
print(f"Gate 1: OOT AUC {metrics['oot_auc']:.3f} >= {MIN_OOT_AUC} -> {'PASS' if gate_auc else 'FAIL'}")
print(f"Gate 2: lift over rule {metrics['oot_lift_over_rule']:+.3f} (rule AUC {metrics['oot_rule_auc']:.3f}) >= {MIN_LIFT_OVER_RULE} -> {'PASS' if gate_lift else 'FAIL'}")

if gate_auc and gate_lift:
    client.set_registered_model_alias(MODEL_NAME, "champion", new_version)
    client.delete_registered_model_alias(MODEL_NAME, "challenger")
    print(f"Promoted v{new_version} to champion")
else:
    print(f"v{new_version} stays challenger; champion unchanged")

print("Aliases:", client.get_registered_model(MODEL_NAME).aliases)