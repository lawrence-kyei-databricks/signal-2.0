"""Shared definitions for the CCG forward-looking account risk model.

One source of truth for features, label, rule baseline, and per-account drivers, imported by
notebook 04 (training on syn_account_monthly_history) and notebook 05 (scoring real data).
All features are point-in-time: they only use months <= the cutoff month.
"""
import numpy as np
import pandas as pd

FEATURES = [
    "log_rev_6m", "rev_momentum_3m", "rev_6m_vs_12m", "backorder_rate_6m", "slip_rate_6m",
    "avg_slip_days_6m", "activities_6m", "activity_trend_3m", "days_since_last_activity",
    "cases_6m", "high_priority_cases_6m",
]

# Kept in the model as a size control (it improves out-of-time AUC) but never shown to reps as a risk driver,
# because "the account is large" is not something a rep can act on.
CONTROL_FEATURES = {"log_rev_6m"}

HORIZON_MONTHS = 6       # predict revenue over the next 6 months
DECLINE_THRESHOLD = 0.6  # label = 1 if next-6m revenue < 60% of the trailing 12-month run rate (per 6 months)

# Plain-English driver labels for briefings: (label, value formatter)
DRIVER_LABELS = {
    "log_rev_6m": ("Revenue level (6 mo)", lambda r: f"${np.expm1(r['log_rev_6m']):,.0f}"),
    "rev_momentum_3m": ("Revenue momentum (last 3 mo vs prior 3)", lambda r: f"{r['rev_momentum_3m']:+.0%}"),
    "rev_6m_vs_12m": ("Revenue vs 12-mo run rate", lambda r: f"{r['rev_6m_vs_12m']:.2f}x"),
    "backorder_rate_6m": ("Backorder rate (6 mo)", lambda r: f"{r['backorder_rate_6m']:.0%}"),
    "slip_rate_6m": ("Order lines with pushed delivery dates (6 mo)", lambda r: f"{r['slip_rate_6m']:.0%}"),
    "avg_slip_days_6m": ("Avg delivery slip", lambda r: f"{r['avg_slip_days_6m']:.1f} days"),
    "activities_6m": ("Rep activities (6 mo)", lambda r: f"{r['activities_6m']:.0f}"),
    "activity_trend_3m": ("Rep activity trend (last 3 mo vs prior 3)", lambda r: f"{r['activity_trend_3m']:+.0f}"),
    "days_since_last_activity": ("Days since last rep activity", lambda r: f"{r['days_since_last_activity']:.0f}"),
    "cases_6m": ("Support cases (6 mo)", lambda r: f"{r['cases_6m']:.0f}"),
    "high_priority_cases_6m": ("High-priority cases (6 mo)", lambda r: f"{r['high_priority_cases_6m']:.0f}"),
}

# Real account-month grain for SCORING. Every date is shifted forward so the snapshot date lands on a month end:
# the last bucket is a full month of data and windows line up with the monthly training grain.
REAL_MONTHLY_SCORING_SQL = """
WITH snap AS (
  SELECT MAX(date_ordr_accepted) AS snapshot_date,
         DATEDIFF(LAST_DAY(MAX(date_ordr_accepted)), MAX(date_ordr_accepted)) AS shift_days
  FROM main.ccg_workshop_cdm.cur_sales_order_header),
lines AS (
  SELECT h.customer_shipto_key k, DATE_TRUNC('MONTH', DATE_ADD(h.date_ordr_accepted, snap.shift_days)) m,
         h.sales_order_header_key o, l.qty_ordered * l.unit_price v,
         CASE WHEN l.date_ordr_line_prmsd > l.date_ordr_line_prmsd_orig THEN 1 ELSE 0 END slipped,
         CASE WHEN l.date_ordr_line_prmsd > l.date_ordr_line_prmsd_orig THEN DATEDIFF(l.date_ordr_line_prmsd, l.date_ordr_line_prmsd_orig) ELSE 0 END slip_days
  FROM main.ccg_workshop_cdm.cur_sales_order_header h
  JOIN main.ccg_workshop_cdm.cur_sales_order_line l USING (sales_order_header_key), snap
  WHERE h.date_ordr_accepted <= snap.snapshot_date),
o AS (SELECT k, m, SUM(v) revenue, COUNT(DISTINCT o) orders, COUNT(*) order_lines, SUM(slipped) lines_slipped, SUM(slip_days) slip_days FROM lines GROUP BY ALL),
s AS (
  SELECT h.customer_shipto_key k, DATE_TRUNC('MONTH', DATE_ADD(h.date_ordr_accepted, snap.shift_days)) m,
         SUM(s.total_qty) qty_total, SUM(s.backorder_qty) qty_backordered
  FROM main.ccg_workshop_cdm.cur_shipment_line s
  JOIN main.ccg_workshop_cdm.cur_sales_order_header h USING (sales_order_header_key), snap
  WHERE h.date_ordr_accepted <= snap.snapshot_date GROUP BY ALL),
t AS (
  SELECT mp.customer_shipto_key k, DATE_TRUNC('MONTH', DATE_ADD(t.ActivityDate, snap.shift_days)) m,
         COUNT(*) activities, MAX(DATE_ADD(t.ActivityDate, snap.shift_days)) last_activity_date
  FROM main.ccg_workshop_cdm.sf_task t
  JOIN main.ccg_workshop_cdm.sf_cdm_key_mapping mp ON t.AccountId = mp.sf_account_id, snap
  WHERE t.IsDeleted = false AND t.ActivityDate <= snap.snapshot_date GROUP BY ALL),
-- Cases have no reliable timestamps (all loaded on one date), so open cases count as current at the snapshot month
c AS (
  SELECT mp.customer_shipto_key k, DATE_TRUNC('MONTH', LAST_DAY(snap.snapshot_date)) m,
         SUM(CASE WHEN NOT cs.IsClosed THEN 1 ELSE 0 END) cases_opened,
         SUM(CASE WHEN cs.IsEscalated THEN 1 ELSE 0 END) escalations,
         SUM(CASE WHEN cs.Priority IN ('High','Critical') AND NOT cs.IsClosed THEN 1 ELSE 0 END) high_priority_cases
  FROM main.ccg_workshop_cdm.sf_case cs
  JOIN main.ccg_workshop_cdm.sf_cdm_key_mapping mp ON cs.AccountId = mp.sf_account_id, snap
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


def _prep(monthly):
    d = monthly.copy()
    d["month_start"] = pd.to_datetime(d["month_start"])
    d["last_activity_date"] = pd.to_datetime(d["last_activity_date"])
    return d


def compute_features(monthly, cutoff_month, as_of_date=None):
    """Point-in-time features per account from an account-month table, using only months <= cutoff_month."""
    d = _prep(monthly)
    c = pd.Timestamp(cutoff_month)
    as_of = pd.Timestamp(as_of_date) if as_of_date is not None else c + pd.offsets.MonthEnd(0)
    keys = pd.Index(sorted(d.customer_shipto_key.unique()), name="customer_shipto_key")
    d = d[d.month_start <= c]

    def win(lo, hi):
        return d[(d.month_start > c - pd.DateOffset(months=lo)) & (d.month_start <= c - pd.DateOffset(months=hi))]

    def total(frame, col):
        return frame.groupby("customer_shipto_key")[col].sum().reindex(keys).fillna(0)

    w6, w3, p3, w12 = win(6, 0), win(3, 0), win(6, 3), win(12, 0)
    rev6, r3, rp3, r12 = total(w6, "revenue"), total(w3, "revenue"), total(p3, "revenue"), total(w12, "revenue")
    lines, slipped, slip_days = total(w6, "order_lines"), total(w6, "lines_slipped"), total(w6, "slip_days")
    qty, bo = total(w6, "qty_total"), total(w6, "qty_backordered")
    a6, a3, ap3 = total(w6, "activities"), total(w3, "activities"), total(p3, "activities")
    last_act = d.groupby("customer_shipto_key").last_activity_date.max().reindex(keys)

    out = pd.DataFrame(index=keys)
    out["log_rev_6m"] = np.log1p(rev6)
    out["rev_momentum_3m"] = ((r3 - rp3) / (r3 + rp3).replace(0, np.nan)).fillna(0)
    out["rev_6m_vs_12m"] = (2 * rev6 / r12.replace(0, np.nan)).fillna(0).clip(0, 2)
    out["backorder_rate_6m"] = (bo / qty.replace(0, np.nan)).fillna(0)
    out["slip_rate_6m"] = (slipped / lines.replace(0, np.nan)).fillna(0)
    out["avg_slip_days_6m"] = (slip_days / slipped.replace(0, np.nan)).fillna(0)
    out["activities_6m"] = a6
    out["activity_trend_3m"] = a3 - ap3
    out["days_since_last_activity"] = (as_of - last_act).dt.days.fillna(365).clip(0, 365)
    out["cases_6m"] = total(w6, "cases_opened")
    out["high_priority_cases_6m"] = total(w6, "high_priority_cases")
    return out[FEATURES].astype(float).reset_index()


def compute_label(monthly, cutoff_month, horizon=HORIZON_MONTHS, drop=DECLINE_THRESHOLD):
    """1 if revenue in the next `horizon` months falls below `drop` x the trailing 12-month run rate."""
    d = _prep(monthly)
    c = pd.Timestamp(cutoff_month)
    trail = d[(d.month_start > c - pd.DateOffset(months=12)) & (d.month_start <= c)].groupby("customer_shipto_key").revenue.sum() * horizon / 12
    fut = d[(d.month_start > c) & (d.month_start <= c + pd.DateOffset(months=horizon))].groupby("customer_shipto_key").revenue.sum()
    lab = pd.DataFrame({"baseline_rev": trail, "future_rev": fut}).fillna(0)
    lab = lab[lab.baseline_rev > 0]
    lab["label"] = (lab.future_rev < drop * lab.baseline_rev).astype(int)
    return lab.reset_index()


def build_snapshots(monthly, cutoff_months):
    """Stack (features at cutoff, outcome after cutoff) for each cutoff month."""
    frames = []
    for c in cutoff_months:
        f = compute_features(monthly, c).merge(compute_label(monthly, c), on="customer_shipto_key")
        f["cutoff_month"] = pd.Timestamp(c)
        frames.append(f)
    return pd.concat(frames, ignore_index=True)


def rule_score(df):
    """Point-in-time version of the gold MV rule (risk_score_raw): staleness + backorders + high-priority cases."""
    return (np.minimum(40, df.days_since_last_activity * 0.2)
            + np.minimum(25, df.backorder_rate_6m * 100 * 1.5)
            + np.minimum(10, df.high_priority_cases_6m * 5))


# Bands are rank-based within each scoring run on EXPECTED REVENUE AT RISK (probability x the account's 6-month
# revenue run rate): the top 10% of the book is High, the next 30% Medium. Out-of-time, ranking by expected dollar
# loss put 46.1% of lost revenue in the top 20% vs 35.1% ranking by probability alone (today's rule: 28.4%).
# Rank-based bands also stay a workable size when a recalibrated model's probabilities compress.
HIGH_SHARE, MEDIUM_SHARE = 0.10, 0.30


def risk_category(score, high_share=HIGH_SHARE, medium_share=MEDIUM_SHARE):
    """Rank-based band for each value of `score` (pass expected revenue at risk)."""
    rank = pd.Series(np.asarray(score, float)).rank(ascending=False, method="first").values / len(score)
    return np.where(rank <= high_share, "High", np.where(rank <= high_share + medium_share, "Medium", "Low"))


def revenue_run_rate(monthly, cutoff_month, horizon=HORIZON_MONTHS):
    """Trailing 12-month order revenue scaled to `horizon` months: the same base the decline label uses."""
    d = _prep(monthly)
    c = pd.Timestamp(cutoff_month)
    keys = pd.Index(sorted(d.customer_shipto_key.unique()), name="customer_shipto_key")
    trail = d[(d.month_start > c - pd.DateOffset(months=12)) & (d.month_start <= c)].groupby("customer_shipto_key").revenue.sum()
    return (trail.reindex(keys).fillna(0) * horizon / 12).rename("revenue_run_rate_6m").reset_index()


def top_drivers(pipeline, X, k=2):
    """Per-account drivers for a StandardScaler + LogisticRegression pipeline.
    Contribution = coefficient x standardized value; positive pushes risk up."""
    scaler, clf = pipeline.named_steps["standardscaler"], pipeline.named_steps["logisticregression"]
    z = (X[FEATURES].values - scaler.mean_) / scaler.scale_
    contrib = z * clf.coef_[0]
    drivers = []
    for i in range(len(X)):
        row = X.iloc[i]
        order = [j for j in np.argsort(-contrib[i]) if FEATURES[j] not in CONTROL_FEATURES]
        picked = [FEATURES[j] for j in order[:k] if contrib[i, j] > 0]
        drivers.append("; ".join(f"{DRIVER_LABELS[f][0]}: {DRIVER_LABELS[f][1](row)}" for f in picked) or "No elevated risk drivers")
    return drivers, pd.DataFrame(contrib, columns=FEATURES, index=X.index)


# Drift between the training distribution and what the model scores today.
# PSI bands (industry convention): < 0.10 stable, 0.10-0.25 watch, >= 0.25 shift.
def psi(reference, current, bins=10):
    """Population stability index of `current` against `reference`, using reference quantile bins."""
    ref, cur = np.asarray(reference, float), np.asarray(current, float)
    edges = np.unique(np.quantile(ref, np.linspace(0, 1, bins + 1)))
    if len(edges) < 3:  # near-constant reference: split at the current median so there are two buckets
        edges = np.unique(np.concatenate([edges, np.quantile(cur, [0.5])]))
    edges[0], edges[-1] = -np.inf, np.inf
    r = np.clip(np.histogram(ref, edges)[0] / len(ref), 1e-4, None)
    c = np.clip(np.histogram(cur, edges)[0] / len(cur), 1e-4, None)
    return float(np.sum((c - r) * np.log(c / r)))


def psi_band(value):
    return "shift" if value >= 0.25 else ("watch" if value >= 0.10 else "stable")


def feature_drift(train_features, live_features):
    """Per-feature PSI and KS statistic, training snapshots vs the accounts being scored."""
    from scipy.stats import ks_2samp
    rows = []
    for f in FEATURES:
        p = psi(train_features[f], live_features[f])
        rows.append({"feature": f, "train_median": float(train_features[f].median()), "live_median": float(live_features[f].median()),
                     "psi": p, "ks_stat": float(ks_2samp(train_features[f], live_features[f]).statistic), "band": psi_band(p)})
    return pd.DataFrame(rows)
