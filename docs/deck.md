# Signal 2.0 - Account Risk Intelligence for Lab-Supply Sales

*Presentation deck (markdown export). Audience: VP Commercial (executive sponsor) and Director of Sales Operations (domain owner). All figures from the working prototype on synthetic data.*

---

## 1. The headline

**Reps can see 60% of the revenue about to walk out the door, up from 35% today, with the same effort.**

- $42.7M of expected revenue at risk in a 200-account, $177.0M book
- About **$10.7M more at-risk revenue** surfaced to reps; **about $2.7M a year retained** at an assumed 25% save rate
- Live in the rep's Salesforce page, a worklist app, and plain-English Q&A, refreshed in about 4 minutes

---

## 2. The problem: account decline is visible too late

- Warning signs are split across systems: **backorders and late deliveries** (ERP) and **rep inactivity and support cases** (CRM)
- Today's prioritization is a static rule; reviewing the top 20% of accounts it ranks finds only **33.8% of the accounts that go on to decline**
- Reps discover the loss in the revenue report, after it is too late to save

---

## 3. What changes for the rep

1. Opens a Salesforce account and sees a **morning briefing**: risk score, the two reasons (for example *backorder rate 72%, revenue momentum -80%*), a recommended action and urgency, and three recommendations with numbers verified against the account's data
2. Works a **ranked worklist** in the Signal Account Cockpit; accepts, snoozes, or dismisses, and the decision is recorded under their name
3. Asks Genie *"which of my accounts are high risk and why?"* and gets an answer, a table, and a chart

---

## 4. Proof: measured on held-out months

| Same rep effort (top 20% of accounts) | Today's rule | Signal 2.0 |
|---|---|---|
| Declining accounts found | 33.8% | **51.5%** |
| Lost revenue they represent | 34.7% | **59.8%** |
| Accuracy (AUC, out-of-time) | 0.667 | **0.818** |

Reviewing only the top 10%: 39.6% of lost revenue vs 25.3% today.

---

## 5. Value model

| Line | Value | Basis |
|---|---|---|
| Expected revenue at risk today | $42.7M | annual revenue x model probability, 200 accounts |
| Additional share reps see | +25.1 points | 59.8% vs 34.7%, measured |
| Additional at-risk revenue in front of reps | about $10.7M | $42.7M x 25.1% |
| Revenue retained per year | about $2.7M | **assumption:** reps save 25% of what they work |

Scales with the book: the same logic applies per region or per business unit. The pilot's job is to measure the real save rate.

---

## 6. For the executive sponsor (VP Commercial)

- **Revenue retention:** about $2.7M a year per 200 accounts at a 25% save rate; each additional 5 points of save rate adds about $0.5M
- **Forecast confidence:** expected revenue at risk is a single, governed number in Salesforce, the dashboard, and Genie
- **Time to value:** prototype built on the existing Salesforce and ERP data; a pilot needs real order history and one sales region

---

## 7. For the domain owner (Director of Sales Operations)

- **Focus:** 79 High and Medium accounts carry $30.2M of the $42.7M at risk; the worklist is ranked by it
- **Explainable:** every score comes with its two main drivers, the same text in Salesforce, the app, and Genie
- **Adoption you can measure:** every accept, snooze, and dismiss is recorded with an audit trail, by rep
- **No new tool to learn:** the briefing is on the Salesforce account page reps already use

---

## 8. How it works (one slide)

Salesforce + ERP --> **Lakeflow** (ingest) --> **Unity Catalog** (govern) --> **risk model + AI briefings** --> **Lakebase** (app), **metric view + Genie** (Q&A), **Salesforce** (page) --> **Databricks App**

One scheduled job refreshes it all and checks that every consumer shows the same High-risk count (11 accounts today).

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
| 1-2 | Connect real order history for one region; retrain on real data and re-validate |
| 3-4 | Pilot with 10 reps; measure accepted alerts and save rate |
| 5-6 | Read out retained revenue vs a control group; decide on rollout |

**Ask:** sponsor a 6-week, one-region pilot with a control group, and name a Sales Ops owner for the success metric (retained revenue on worked accounts).
