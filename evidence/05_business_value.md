# Evidence: business value calculation

Model v6 (champion). Out-of-time test: cutoffs Jan-Feb 2026, 399 account snapshots, 107 accounts that went on to decline,
**$254.0M of revenue lost** in the following 6 months (lost = 6-month run rate minus actual, for decliners). Same rep effort:
reps work the top 10% or 20% of accounts under each ranking. Options were chosen on a separate validation month (Nov 2025)
before this test was run.

| Review top | Ranked by | Decliners caught % | Lost revenue caught % |
|---|---|---|---|
| 10% | today's rule (score) | 14.0 | 13.2 |
| 10% | today's rule x revenue | 17.8 | 23.8 |
| 10% | model probability | 15.9 | 18.6 |
| 10% | **model expected $ loss (live)** | **19.6** | **30.0** |
| 20% | today's rule (score) | 27.1 | 28.4 |
| 20% | today's rule x revenue | 33.6 | 42.3 |
| 20% | model probability | 30.8 | 35.1 |
| 20% | **model expected $ loss (live)** | **32.7** | **46.1** |

**Measured lift (same base):** at a 20% review rate, ranking by the model's expected dollar loss catches 46.1% of lost revenue
vs 28.4% for today's rule: +17.7 points, about **$45.0M** more of the $254.0M in front of reps over the two test months.

**Honest decomposition:** most of the gain is from ranking by dollars. Today's rule weighted by revenue reaches 42.3%,
so the model's own edge over a dollar-weighted rule is +3.8 points. The product change (rank by dollars at risk) and the
model (which also reads delivery, backorder, activity and case signals) are both needed to reach 46.1%.

## Current portfolio (scored 2026-11-22, v6)

200 accounts, **annual revenue $1,750.4M** (Salesforce AnnualRevenue now equals trailing 12-month order revenue, so every
surface uses one base). Expected revenue at risk (annual revenue x probability of decline): **$561.4M**. High + Medium
accounts (top 40% by expected dollar loss: 20 High, 60 Medium) carry $359.3M of it.

## Projection (labelled; not measured)

Applying the measured +17.7-point lift to today's $561.4M gives about **$99.4M** more at-risk revenue surfaced to reps.
*Assuming* reps save 25% of what they work, about **$24.8M** retained per year. The save rate is the assumption a pilot
with a control group must measure; each 5 points of save rate is about $5.0M.

## History of this number

- v5 (smooth synthetic history) showed 59.8% vs 36.1% at 20% (today's method) on a $137.7M base, with Salesforce revenue
  ($177.0M) on a different base from orders ($1,750.4M). The earlier file's rule rows (33.8% / 34.7%) could not be reproduced.
- v6 trains on history with the real order cadence; ranking by probability alone fell to 35.1%. Ranking by expected dollar
  loss restored most of the lift on realistic data.
