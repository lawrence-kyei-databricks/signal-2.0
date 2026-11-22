# Signal 2.0 - Account Risk Intelligence for Lab-Supply Sales

*Presentation deck (markdown export). Audience: VP Commercial (executive sponsor) and Director of Sales Operations (domain owner). All figures from the working prototype on synthetic data.*

---

## 1. The headline

**Same rep effort, 46% of the revenue about to walk out the door in front of reps, up from 28% today.**

- Measured on held-out months: about **$45.0M** more lost revenue reached reps over two months than under today's rule
- Today's book: $561.4M of expected revenue at risk across 200 accounts and $1,750.4M of annual revenue
- Projected: about **$99.4M more at-risk revenue** in front of reps; **about $24.8M a year retained** at an assumed 25% save rate
- Live in the rep's Salesforce page, a worklist app, and plain-English Q&A, refreshed by one job

---

## 2. The problem: account decline is visible too late

- Warning signs are split across systems: **backorders and late deliveries** (ERP) and **rep inactivity and support cases** (CRM)
- Today's prioritization is a static rule; working the top 20% of accounts it ranks puts only **28.4% of the revenue that is later lost** in front of reps
- Reps discover the loss in the revenue report, after it is too late to save

---

## 3. What changes for the rep

1. Opens a Salesforce account and sees a **morning briefing**: risk score, the two reasons (for example Massachusetts General Hospital: *revenue at 0.33x its run rate, 80% of order lines with pushed delivery dates*), a recommended action and urgency, and three recommendations with numbers verified against the account's data
2. Works a **worklist ranked by expected dollar loss** in the Signal Account Cockpit (opens an account in about 59 ms server side); accepts, snoozes, or dismisses, and the decision is recorded under their name
3. Asks Genie *"which of my accounts are high risk and why?"* and gets an answer, a table, and a chart

---

## 4. Proof: measured on held-out months

| Same rep effort (top 20% of accounts) | Today's rule | Rule x revenue | Signal 2.0 |
|---|---|---|---|
| Lost revenue in front of reps | 28.4% | 42.3% | **46.1%** |
| Declining accounts found | 27.1% | 33.6% | **32.7%** |
| Accuracy (AUC, out-of-time) | 0.543 | 0.543 | **0.625** |

Top 10% only: 30.0% of lost revenue vs 13.2% today.

**Where the lift comes from:** ranking by dollars at risk does most of the work; the model adds about 4 points on top of a dollar-weighted rule by reading delivery, backorder, activity and case signals. Both ship together.

---

## 5. Value model

| Line | Value | Basis |
|---|---|---|
| Additional share of lost revenue reps see | +17.7 points | 46.1% vs 28.4%, **measured** on held-out months |
| Same lift on the test months' $254.0M lost | about $45.0M | **measured**, two months |
| Expected revenue at risk today | $561.4M | annual revenue x model probability, 200 accounts |
| Additional at-risk revenue in front of reps | about $99.4M | $561.4M x 17.7%, **projected** |
| Revenue retained per year | about $24.8M | **assumption:** reps save 25% of what they work |

Scales with the book: the same logic applies per region or per business unit. The pilot's job is to measure the real save rate.

---

## 6. For the executive sponsor (VP Commercial)

- **Revenue retention:** about $24.8M a year per 200 accounts at a 25% save rate (projected); each additional 5 points of save rate adds about $5.0M
- **Forecast confidence:** expected revenue at risk is a single, governed number in Salesforce, the dashboard, and Genie
- **Time to value:** prototype built on the existing Salesforce and ERP data; a pilot needs real order history and one sales region

---

## 7. For the domain owner (Director of Sales Operations)

- **Focus:** the 80 High and Medium accounts (top 40% by expected dollar loss) carry $359.3M of the $561.4M at risk; the worklist starts with the biggest exposure
- **Explainable:** every score comes with its two main drivers, the same text in Salesforce, the app, and Genie
- **Adoption you can measure:** every accept, snooze, and dismiss is recorded with an audit trail, by rep
- **No new tool to learn:** the briefing is on the Salesforce account page reps already use

---

## 8. How it works (one slide)

Salesforce + ERP --> **Lakeflow** (ingest) --> **Unity Catalog** (govern) --> **risk model + AI briefings** --> **Lakebase** (app), **metric view + Genie** (Q&A), **Salesforce** (page) --> **Databricks App**

One scheduled job refreshes it all, then fails if any Lakebase table the app reads differs from Delta. Every consumer shows the same 20 High-risk accounts.

---

## 9. Trust: governance and security

- Credentials only in a secret scope; no secrets in code
- Every table classified; revenue columns tagged confidential; lineage from Salesforce to the app captured automatically
- The app can read scores and add decisions, and cannot change or delete history
- Genie answers with each user's own permissions
- AI recommendations are blocked if any number does not match the account's data

---

## 10. Pilot plan and the ask

| Week | Milestone |
|---|---|
| 1-2 | Connect real order history for one region; recalibrate on real decline labels and re-validate (the prototype's absolute accuracy comes from synthetic history) |
| 3-4 | Pilot with 10 reps; measure accepted alerts and save rate |
| 5-6 | Read out retained revenue vs a control group; decide on rollout |

**Ask:** sponsor a 6-week, one-region pilot with a control group, and name a Sales Ops owner for the success metric (retained revenue on worked accounts).
