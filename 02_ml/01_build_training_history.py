# Databricks notebook source
# /// script
# [tool.databricks.environment]
# environment_version = "6"
# ///
# DBTITLE 1,Overview
# MAGIC %md
# MAGIC # CCG Synthetic Account History (SYNTHETIC DATA)
# MAGIC
# MAGIC Builds `main.ccg_workshop_cdm.syn_account_monthly_history`: 24 months (Sep 2024 - Aug 2026) x 200 accounts at account-month grain. It is used **only to train** the forward-looking account risk model in `02_train_risk_model`. Scoring always uses real data.
# MAGIC
# MAGIC **Why it exists:** in the demo `cur_*` order data, backorders, delivery slips, and rep inactivity have no link to later revenue, so no model could learn those drivers. This table adds a realistic cause-and-effect pattern. The existing `cur_*` tables are not modified.
# MAGIC
# MAGIC **How it is generated (seeded, reproducible)**
# MAGIC - **Anchored to reality for the whole history:** every month sits around the account's **real** backorder rate, slip rate, activity cadence, case load, and revenue level, taken from the same live features the model scores. Levels wander slowly month to month, so training features match the scoring distribution (checked with PSI in `02_train_risk_model`).
# MAGIC - **Episodes:** supply disruptions (backorders, slips, cases rise) and relationship lapses (rep activity drops) can start in any month. Their average effect is netted off the real levels.
# MAGIC - **Lagged effect:** pain above the account's own normal in months m-3..m-1 lowers revenue in month m, and the impact fades over several months.
# MAGIC - **Noise:** seasonality, per-account drift, and order-level randomness, so the signal is learnable but not trivial.
# MAGIC - **Order cadence:** each account orders at its **real** rate (about 1 order a month on average), so revenue is as lumpy as the real data. An earlier version used a smooth 4 orders a month, which made decline easier to predict than reality (out-of-time AUC 0.818 vs 0.625 now). Raw order counts are not used as model inputs.
# MAGIC
# MAGIC Re-running with the same seed gives identical output. Replace this table with real CDM history when it is available; set `HISTORY_SOURCE = "cdm"` in `02_train_risk_model`.

# COMMAND ----------

# DBTITLE 1,Configuration and Real Anchors
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
import numpy as np
import pandas as pd

TARGET_TABLE = cfg.SYN_HISTORY_TABLE
MONTHS = pd.date_range("2024-09-01", "2026-08-01", freq="MS")   # 24 months, ends at the real snapshot month
N_M = len(MONTHS)

# Generator settings. Calibrated so training features match the live scoring features (see the drift check in
# 02_train_risk_model). Order cadence comes from each account's REAL order count, not a fixed smooth rate.
SEED = 42
OPS_EPISODE_RATE = 1.5     # expected supply disruption episodes per account over 24 months
ENG_EPISODE_RATE = 1.2     # expected relationship lapse episodes per account
EFFECT = 1.3               # strength of the pain -> revenue effect
NOISE_SD = 0.12
WANDER_SD = 0.25           # slow month-to-month wander of each account's backorder and activity levels
CASE_EPISODE_RATE = 0.3    # extra support cases per month per unit of supply disruption
REV_TREND = 0.10           # book-level revenue growth per year (real book grew over the window)
EPISODE_BO_ALLOWANCE = 0.06   # average backorder rate added by episodes; netted off the real level
LAPSE_ACTIVITY_SHARE = 0.84   # average share of months without a lapse; activity base is grossed up by it

# Real account-month grain from the demo CDM + Salesforce tables (point-in-time up to the snapshot date)
REAL_MONTHLY_SQL = """
WITH snap AS (SELECT MAX(date_ordr_accepted) AS snapshot_date FROM main.ccg_workshop_cdm.cur_sales_order_header),
lines AS (
  SELECT h.customer_shipto_key k, DATE_TRUNC('MONTH', h.date_ordr_accepted) m, h.sales_order_header_key o,
         l.qty_ordered * l.unit_price v,
         CASE WHEN l.date_ordr_line_prmsd > l.date_ordr_line_prmsd_orig THEN 1 ELSE 0 END slipped,
         CASE WHEN l.date_ordr_line_prmsd > l.date_ordr_line_prmsd_orig THEN DATEDIFF(l.date_ordr_line_prmsd, l.date_ordr_line_prmsd_orig) ELSE 0 END slip_days
  FROM main.ccg_workshop_cdm.cur_sales_order_header h
  JOIN main.ccg_workshop_cdm.cur_sales_order_line l USING (sales_order_header_key), snap
  WHERE h.date_ordr_accepted <= snap.snapshot_date),
o AS (SELECT k, m, SUM(v) revenue, COUNT(DISTINCT o) orders, COUNT(*) order_lines, SUM(slipped) lines_slipped, SUM(slip_days) slip_days FROM lines GROUP BY ALL),
s AS (
  SELECT h.customer_shipto_key k, DATE_TRUNC('MONTH', h.date_ordr_accepted) m, SUM(s.total_qty) qty_total, SUM(s.backorder_qty) qty_backordered
  FROM main.ccg_workshop_cdm.cur_shipment_line s JOIN main.ccg_workshop_cdm.cur_sales_order_header h USING (sales_order_header_key), snap
  WHERE h.date_ordr_accepted <= snap.snapshot_date GROUP BY ALL),
t AS (
  SELECT mp.customer_shipto_key k, DATE_TRUNC('MONTH', t.ActivityDate) m, COUNT(*) activities, MAX(t.ActivityDate) last_activity_date
  FROM main.ccg_workshop_cdm.sf_task t JOIN main.ccg_workshop_cdm.sf_cdm_key_mapping mp ON t.AccountId = mp.sf_account_id, snap
  WHERE t.IsDeleted = false AND t.ActivityDate <= snap.snapshot_date GROUP BY ALL),
-- Cases carry no reliable timestamps (all loaded on one date), so open cases count as current at the snapshot month
c AS (
  SELECT mp.customer_shipto_key k, DATE_TRUNC('MONTH', snap.snapshot_date) m,
         SUM(CASE WHEN NOT cs.IsClosed THEN 1 ELSE 0 END) cases_opened,
         SUM(CASE WHEN cs.IsEscalated THEN 1 ELSE 0 END) escalations,
         SUM(CASE WHEN cs.Priority IN ('High','Critical') AND NOT cs.IsClosed THEN 1 ELSE 0 END) high_priority_cases
  FROM main.ccg_workshop_cdm.sf_case cs JOIN main.ccg_workshop_cdm.sf_cdm_key_mapping mp ON cs.AccountId = mp.sf_account_id, snap
  WHERE cs.IsDeleted = false GROUP BY ALL),
keys AS (SELECT k, m FROM o UNION SELECT k, m FROM s UNION SELECT k, m FROM t UNION SELECT k, m FROM c)
SELECT keys.k AS customer_shipto_key, keys.m AS month_start,
  COALESCE(o.revenue,0) revenue, COALESCE(o.orders,0) orders, COALESCE(o.order_lines,0) order_lines,
  COALESCE(o.lines_slipped,0) lines_slipped, COALESCE(o.slip_days,0) slip_days,
  COALESCE(s.qty_total,0) qty_total, COALESCE(s.qty_backordered,0) qty_backordered,
  COALESCE(t.activities,0) activities, t.last_activity_date,
  COALESCE(c.cases_opened,0) cases_opened, COALESCE(c.escalations,0) escalations, COALESCE(c.high_priority_cases,0) high_priority_cases
FROM keys LEFT JOIN o USING (k, m) LEFT JOIN s USING (k, m) LEFT JOIN t USING (k, m) LEFT JOIN c USING (k, m)
"""

def account_anchors(real_m, snapshot):
    """Per-account calibration targets from REAL data (last 6 months + lifetime revenue level)."""
    rm = real_m.copy(); rm["month_start"] = pd.to_datetime(rm.month_start)
    recent = rm[rm.month_start > pd.Timestamp(snapshot) - pd.DateOffset(months=6)]
    life = rm.groupby("customer_shipto_key").agg(rev_total=("revenue","sum"), n_months=("month_start","nunique"),
                                                 orders=("orders","sum"), lines=("order_lines","sum"), qty=("qty_total","sum"))
    r = recent.groupby("customer_shipto_key").agg(lines6=("order_lines","sum"), slipped6=("lines_slipped","sum"),
        qty6=("qty_total","sum"), bo6=("qty_backordered","sum"), acts6=("activities","sum"),
        cases=("cases_opened","sum"), esc=("escalations","sum"), hp=("high_priority_cases","sum"))
    a = life.join(r, how="left").fillna(0)
    span = (pd.Timestamp(snapshot) - pd.Timestamp("2025-01-01")).days / 30.4
    a["base_rev"] = np.maximum(a.rev_total / span, 20000)
    a["aov"] = np.maximum(a.rev_total / a.orders.replace(0, np.nan), 50000).fillna(200000)
    a["lines_per_order"] = (a.lines / a.orders.replace(0, np.nan)).fillna(4).clip(1, 12)
    a["qty_per_line"] = (a.qty / a.lines.replace(0, np.nan)).fillna(50).clip(5, 500)
    a["bo_end"] = (a.bo6 / a.qty6.replace(0, np.nan)).fillna(0.13).clip(0, 0.9)
    a["slip_end"] = (a.slipped6 / a.lines6.replace(0, np.nan)).fillna(0.9).clip(0.05, 1.0)
    a["act_end"] = (a.acts6 / 6).clip(0.05, 3)
    return a.reset_index()

real_m = spark.sql(REAL_MONTHLY_SQL).toPandas()
snapshot = spark.sql("SELECT MAX(date_ordr_accepted) d FROM main.ccg_workshop_cdm.cur_sales_order_header").first().d
anchors = account_anchors(real_m, snapshot)

# Anchor operational levels to the LIVE scoring features (same code path as 03_score_and_brief), so the model
# trains on the distribution it will score. Episodes add pain on top, so their average effect is netted off.
import ccg_risk_features as rf
importlib.reload(rf)
as_of = spark.sql("SELECT LAST_DAY(MAX(date_ordr_accepted)) a FROM main.ccg_workshop_cdm.cur_sales_order_header").first().a
live = rf.compute_features(spark.sql(rf.REAL_MONTHLY_SCORING_SQL).toPandas(), pd.Timestamp(as_of).replace(day=1), as_of)
anchors = anchors.set_index("customer_shipto_key").join(
    live.set_index("customer_shipto_key")[["backorder_rate_6m", "activities_6m", "cases_6m", "high_priority_cases_6m"]], how="left")
anchors["bo_end"] = (anchors.backorder_rate_6m.fillna(anchors.bo_end) - EPISODE_BO_ALLOWANCE).clip(0, 0.9)
anchors["act_end"] = (anchors.activities_6m.fillna(anchors.act_end * 6) / 6 / LAPSE_ACTIVITY_SHARE).clip(0.02, 3)
anchors["cases"] = anchors.cases_6m.fillna(anchors.cases)
anchors["hp"] = anchors.high_priority_cases_6m.fillna(anchors.hp)
anchors = anchors.reset_index()
print(f"Real snapshot date: {snapshot} | real account-months: {len(real_m)} | accounts anchored: {len(anchors)} "
      f"| live features as of {as_of}: {len(live)} accounts")

# COMMAND ----------

# DBTITLE 1,Causal History Generator
def generate_history(anchors, seed=SEED, k_ops=3.0, k_eng=1.4, effect=EFFECT, noise_sd=NOISE_SD):
    """Baselines sit on each account's REAL levels for the whole history; episodes can start in any month."""
    rng = np.random.default_rng(seed)
    rows = []
    m_idx = np.arange(N_M)
    for _, a in anchors.iterrows():
        def wander(sd):
            # Slow multiplicative wander (AR(1) on the log scale), centred so the last 6 months sit on the real level
            x, e = np.zeros(N_M), rng.normal(0, sd, N_M)
            for m in range(N_M):
                x[m] = 0.8 * (x[m-1] if m else 0) + e[m]
            return np.exp(x - x[-6:].mean())
        bo_mu = np.clip(a.bo_end * wander(WANDER_SD), 0, 0.9)
        slip_mu = np.clip(a.slip_end + rng.normal(0, 0.02, N_M), 0, 1)
        act_mu = np.clip(a.act_end * wander(WANDER_SD), 0.02, 3)
        case_mu = a.cases / 6.0
        hp_share = (a.hp / a.cases) if a.cases > 0 else 0.35
        ops_ep, eng_ep = np.zeros(N_M), np.zeros(N_M)
        for _ in range(rng.poisson(OPS_EPISODE_RATE)):          # supply disruption episodes, any month
            s, L, mag = rng.integers(0, N_M), rng.integers(2, 5), rng.uniform(0.15, 0.40)
            ops_ep[s:s+L] += mag
        for _ in range(rng.poisson(ENG_EPISODE_RATE)):          # relationship lapse episodes, any month
            s, L = rng.integers(0, N_M), rng.integers(2, 6)
            eng_ep[s:s+L] = np.maximum(eng_ep[s:s+L], rng.uniform(0.6, 0.95))
        bo = np.clip(bo_mu + ops_ep + rng.normal(0, 0.02, N_M), 0, 0.95)
        slip = np.clip(slip_mu + 0.3 * ops_ep, 0, 1)
        acts = rng.poisson(np.maximum(act_mu * (1 - eng_ep), 0.01))
        cases = rng.poisson(case_mu + CASE_EPISODE_RATE * ops_ep)
        esc = rng.binomial(cases, np.clip(0.1 + 0.6 * ops_ep, 0, 0.9))
        hp = rng.binomial(cases, np.clip(hp_share, 0, 1))
        # Pain is measured against the account's own normal: only above-normal ops pain or engagement lapses hurt revenue
        pain_dev = k_ops * np.maximum(0, bo - bo_mu) + k_eng * eng_ep + 0.15 * esc
        pain_lag = np.array([pain_dev[max(0, m-3):m].mean() if m > 0 else 0 for m in range(N_M)])
        hit = np.zeros(N_M)
        for m in range(N_M):                                    # impact persists for months after the episode ends
            hit[m] = (0.75 * hit[m-1] if m else 0) + 0.25 * pain_lag[m]
        drift = rng.normal(0, 0.06)
        season = 0.05 * np.sin(2 * np.pi * (MONTHS.month.values - 3) / 12)
        rev_target = a.base_rev * np.exp(-effect * hit + drift * (m_idx - 23) / 12 + season + rng.normal(0, noise_sd, N_M))
        orders_pm = max(a.orders / a.n_months, 0.3)             # the account's REAL order cadence
        aov_s = a.base_rev / orders_pm
        orders = rng.poisson(np.maximum(rev_target / aov_s, 0.02))
        revenue = np.where(orders > 0, orders * aov_s * rng.uniform(0.6, 1.4, N_M), 0.0)
        lines = orders * 2 + rng.poisson(orders)
        slipped = rng.binomial(lines, slip)
        slip_days = np.array([rng.gamma(2, 7.5 / 2, s).sum() if s else 0 for s in slipped]).round()   # real mean ~7.5 days
        qty = np.round(lines * a.qty_per_line * rng.uniform(0.8, 1.2, N_M)).astype(int)
        qty_bo = rng.binomial(qty, bo)
        for m in range(N_M):
            last_act = MONTHS[m] + pd.Timedelta(days=int(rng.integers(0, 28))) if acts[m] > 0 else pd.NaT
            rows.append((int(a.customer_shipto_key), MONTHS[m], float(round(revenue[m], 2)), int(orders[m]), int(lines[m]),
                         int(slipped[m]), int(slip_days[m]), int(qty[m]), int(qty_bo[m]), int(acts[m]), last_act,
                         int(cases[m]), int(esc[m]), int(hp[m])))
    cols = ["customer_shipto_key","month_start","revenue","orders","order_lines","lines_slipped","slip_days",
            "qty_total","qty_backordered","activities","last_activity_date","cases_opened","escalations","high_priority_cases"]
    df = pd.DataFrame(rows, columns=cols)
    # Book-level growth: the real book grew over the window, so revenue trends up toward the snapshot month
    ms = pd.to_datetime(df.month_start)
    df["revenue"] = (df.revenue * np.exp(REV_TREND * (ms.dt.year * 12 + ms.dt.month - (MONTHS[-1].year * 12 + MONTHS[-1].month)) / 12)).round(2)
    return df

hist = generate_history(anchors)
print(f"Generated {len(hist)} account-months for {hist.customer_shipto_key.nunique()} accounts ({hist.month_start.min().date()} to {hist.month_start.max().date()})")

# COMMAND ----------

# DBTITLE 1,Causal History Generator
def generate_history(anchors, seed=SEED, k_ops=3.0, k_eng=1.4, effect=EFFECT, noise_sd=NOISE_SD):
    rng = np.random.default_rng(seed)
    rows = []
    m_idx = np.arange(N_M)
    w = np.clip((m_idx - 12) / 6, 0, 1)                      # free history first, fully on real levels in the last 6 months
    for _, a in anchors.iterrows():
        bo_start = np.clip(rng.beta(2, 10), 0, 0.6)
        slip_start = np.clip(a.slip_end + rng.normal(0, 0.05), 0, 1)
        act_start = np.clip(rng.gamma(3, 0.4), 0.1, 3)
        bo_mu = (1 - w) * bo_start + w * a.bo_end
        slip_mu = (1 - w) * slip_start + w * a.slip_end
        act_mu = (1 - w) * act_start + w * a.act_end
        ops_ep, eng_ep = np.zeros(N_M), np.zeros(N_M)
        for _ in range(rng.poisson(OPS_EPISODE_RATE)):          # supply disruption episodes, before the anchored window
            s, L, mag = rng.integers(0, 17), rng.integers(2, 5), rng.uniform(0.15, 0.40)
            ops_ep[s:s+L] += mag
        for _ in range(rng.poisson(ENG_EPISODE_RATE)):          # relationship lapse episodes
            s, L = rng.integers(0, 17), rng.integers(2, 6)
            eng_ep[s:s+L] = np.maximum(eng_ep[s:s+L], rng.uniform(0.6, 0.95))
        bo = np.clip(bo_mu + ops_ep + rng.normal(0, 0.02, N_M), 0, 0.95)
        slip = np.clip(slip_mu + 0.3 * ops_ep + rng.normal(0, 0.02, N_M), 0, 1)
        act_rate = np.maximum(act_mu * (1 - eng_ep), 0.02)
        acts = rng.poisson(act_rate)
        cases = rng.poisson(0.10 + 2.0 * ops_ep)
        esc = rng.binomial(cases, np.clip(0.1 + 0.6 * ops_ep, 0, 0.9))
        hp = rng.binomial(cases, 0.35)
        # Pain is measured against the account's own normal: only above-normal ops pain or engagement lapses hurt revenue
        pain_dev = k_ops * np.maximum(0, bo - bo_mu) + k_eng * eng_ep + 0.15 * esc
        pain_lag = np.array([pain_dev[max(0, m-3):m].mean() if m > 0 else 0 for m in range(N_M)])
        hit = np.zeros(N_M)
        for m in range(N_M):                                    # impact persists for months after the episode ends
            hit[m] = (0.75 * hit[m-1] if m else 0) + 0.25 * pain_lag[m]
        drift = rng.normal(0, 0.06)
        season = 0.05 * np.sin(2 * np.pi * (MONTHS.month.values - 3) / 12)
        rev_target = a.base_rev * np.exp(-effect * hit + drift * (m_idx - 23) / 12 + season + rng.normal(0, noise_sd, N_M))
        aov_s = a.base_rev / ORDERS_PER_MONTH
        exp_orders = np.maximum(rev_target / aov_s, 0.05)
        orders = rng.poisson(exp_orders)
        revenue = np.where(orders > 0, orders * aov_s * (rev_target / (exp_orders * aov_s)) * rng.uniform(0.8, 1.2, N_M), 0.0)
        lines = orders * 2 + rng.poisson(orders)
        slipped = rng.binomial(lines, slip)
        slip_days = np.array([rng.gamma(2, 3.5, s).sum() if s else 0 for s in slipped]).round()
        qty = np.round(lines * a.qty_per_line * rng.uniform(0.8, 1.2, N_M)).astype(int)
        qty_bo = rng.binomial(qty, bo)
        for m in range(N_M):
            last_act = MONTHS[m] + pd.Timedelta(days=int(rng.integers(0, 28))) if acts[m] > 0 else pd.NaT
            rows.append((int(a.customer_shipto_key), MONTHS[m], float(round(revenue[m], 2)), int(orders[m]), int(lines[m]),
                         int(slipped[m]), int(slip_days[m]), int(qty[m]), int(qty_bo[m]), int(acts[m]), last_act,
                         int(cases[m]), int(esc[m]), int(hp[m])))
    cols = ["customer_shipto_key","month_start","revenue","orders","order_lines","lines_slipped","slip_days",
            "qty_total","qty_backordered","activities","last_activity_date","cases_opened","escalations","high_priority_cases"]
    return pd.DataFrame(rows, columns=cols)

hist = generate_history(anchors)
print(f"Generated {len(hist)} account-months for {hist.customer_shipto_key.nunique()} accounts ({hist.month_start.min().date()} to {hist.month_start.max().date()})")

# COMMAND ----------

# DBTITLE 1,Validate Anchoring and Cause-and-Effect
# 1. Anchoring: last 6 synthetic months should sit on each account's REAL levels
def last6(df):
    d = df.copy(); d["month_start"] = pd.to_datetime(d.month_start)
    d = d[(d.month_start > pd.Timestamp("2026-07-01") - pd.DateOffset(months=6)) & (d.month_start <= "2026-07-01")]
    g = d.groupby("customer_shipto_key").agg(rev=("revenue","sum"), qty=("qty_total","sum"), bo=("qty_backordered","sum"), acts=("activities","sum"))
    return pd.DataFrame({"log_rev_6m": np.log1p(g.rev), "backorder_rate_6m": g.bo / g.qty.replace(0, np.nan), "activities_6m": g.acts})

cmp = last6(real_m).join(last6(hist), lsuffix="_real", rsuffix="_syn", how="inner")
anchor_report = pd.DataFrame({f: {"real_mean": cmp[f+"_real"].mean(), "syn_mean": cmp[f+"_syn"].mean(),
                                  "per_account_corr": cmp[[f+"_real", f+"_syn"]].corr().iloc[0, 1]}
                              for f in ["log_rev_6m", "backorder_rate_6m", "activities_6m"]}).T.round(3)
display(anchor_report)

# 2. Cause-and-effect: months with above-normal backorders or low activity should precede revenue decline
h = hist.sort_values(["customer_shipto_key", "month_start"]).copy()
h["bo_rate"] = h.qty_backordered / h.qty_total.replace(0, np.nan)
grp = h.groupby("customer_shipto_key")
h["bo_3m"] = grp.bo_rate.transform(lambda s: s.rolling(3, min_periods=1).mean())
h["acts_3m"] = grp.activities.transform(lambda s: s.rolling(3, min_periods=1).sum())
h["rev_next_6m"] = grp.revenue.transform(lambda s: s[::-1].rolling(6, min_periods=6).sum()[::-1].shift(-1))
h["rev_prev_6m"] = grp.revenue.transform(lambda s: s.rolling(6, min_periods=6).sum())
h["rev_change"] = h.rev_next_6m / h.rev_prev_6m.replace(0, np.nan) - 1
v = h.dropna(subset=["rev_change", "bo_3m"])
print("Avg next-6m revenue change when the last 3 months had:")
print(f"  high backorders (top quartile): {v[v.bo_3m >= v.bo_3m.quantile(0.75)].rev_change.mean():+.1%} | others: {v[v.bo_3m < v.bo_3m.quantile(0.75)].rev_change.mean():+.1%}")
print(f"  no rep activity:                {v[v.acts_3m == 0].rev_change.mean():+.1%} | some activity: {v[v.acts_3m > 0].rev_change.mean():+.1%}")

assert len(hist) == 200 * N_M, "Expected 200 accounts x 24 months"
assert abs(anchor_report.loc["backorder_rate_6m", "syn_mean"] - anchor_report.loc["backorder_rate_6m", "real_mean"]) < 0.05, "Backorder anchoring drifted"

# COMMAND ----------

# DBTITLE 1,Write Synthetic History Table
out = hist.copy()
out["month_start"] = pd.to_datetime(out.month_start).dt.date
out["last_activity_date"] = pd.to_datetime(out.last_activity_date).dt.date
out = out.astype(object).where(pd.notna(out), None)

schema = """customer_shipto_key BIGINT, month_start DATE, revenue DOUBLE, orders BIGINT, order_lines BIGINT,
            lines_slipped BIGINT, slip_days BIGINT, qty_total BIGINT, qty_backordered BIGINT, activities BIGINT,
            last_activity_date DATE, cases_opened BIGINT, escalations BIGINT, high_priority_cases BIGINT"""
sdf = spark.createDataFrame(out.values.tolist(), schema=schema)
sdf.write.mode("overwrite").option("overwriteSchema", "true").saveAsTable(TARGET_TABLE)

spark.sql(f"""COMMENT ON TABLE {TARGET_TABLE} IS
  'SYNTHETIC account-month history (Sep 2024 - Aug 2026) for training the forward-looking account risk model only. Generated by notebook 01b (seed {SEED}). Anchored to real current account levels; adds lagged cause-and-effect from backorders, delivery slips, cases, and rep inactivity to revenue. Not real customer data. Scoring uses real cur_* and sf_* tables.'""")
for col, txt in {"revenue": "Synthetic monthly order revenue", "qty_backordered": "Synthetic backordered quantity",
                 "lines_slipped": "Synthetic order lines whose promise date was pushed", "activities": "Synthetic rep activities in the month",
                 "cases_opened": "Synthetic support cases opened in the month"}.items():
    spark.sql(f"ALTER TABLE {TARGET_TABLE} ALTER COLUMN {col} COMMENT '{txt}'")

check = spark.sql(f"SELECT COUNT(*) n, COUNT(DISTINCT customer_shipto_key) accts, COUNT(DISTINCT month_start) months, ROUND(SUM(revenue), 0) total_rev FROM {TARGET_TABLE}").first()
print(f"Wrote {TARGET_TABLE}: {check.n} rows, {check.accts} accounts, {check.months} months, total revenue {check.total_rev:,.0f}")
assert check.n == 4800 and check.accts == 200 and check.months == 24