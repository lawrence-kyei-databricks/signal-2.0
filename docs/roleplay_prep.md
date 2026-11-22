# Roleplay Preparation - Signal 2.0

Two personas in the room: **business stakeholder** (VP Commercial, funds the decision) and **technical stakeholder** (data and platform architect, lives with the build).

## Opening (tell) - 60 seconds

"Your reps find out an account is slipping when the revenue report says so. By then it is too late. Today I'll show you how Signal 2.0 shows reps 60% of the revenue about to walk out the door, up from 35%, with the same effort, inside Salesforce where they already work. I'll show the rep's view, the manager's view, and how it stays governed. Then I'll land what it is worth: about $10.7M more at-risk revenue in front of reps, and roughly $2.7M a year retained at a conservative save rate."

## Demo flow (show) - keep to 8-10 minutes

| Step | Show | Land it (one line) |
|---|---|---|
| 1 | Salesforce account page (UPitt): briefing popup, score 61.7, drivers, recommendations | "The rep knows what is wrong and what to do before the first call." |
| 2 | Signal Account Cockpit: ranked worklist, accept an alert | "Every decision is recorded under the rep, so you can measure adoption." |
| 3 | Genie in the app: "Which 5 accounts have the highest risk score, and what is their top risk driver?" with table and chart | "Managers get answers in seconds, from the same governed numbers." |
| 4 | Dashboard: expected revenue at risk by region | "One number for revenue at risk, everywhere." |
| 5 | Lineage and the refresh job (brief, for the architect) | "One job, about 4 minutes, and every layer is connected and checked." |

## Close (tell) - 60 seconds

"Same effort, 25 more points of at-risk revenue in front of reps. On this book that is about $10.7M, and about $2.7M a year retained if reps save a quarter of what they work. I'm asking for a 6-week, one-region pilot with a control group so we measure the real save rate."

## Business stakeholder objections

| Objection | Answer (executive altitude) |
|---|---|
| "How do I know the $2.7M is real?" | "The detection lift is measured on held-out months: 59.8% vs 34.7% of lost revenue. The save rate is the assumption, which is why the pilot has a control group. Every 5 points of save rate is about $0.5M." |
| "What does it cost?" | "It runs on data you already have, on one scheduled job and a small app database. The pilot cost is a few weeks of a data engineer and 10 reps' time; we size production cost from the pilot's actual usage." |
| "Reps won't use another tool." | "They don't have to. The briefing is on the Salesforce account page. The app is for reps who want a worklist, and we can see adoption by rep." |
| "Time to value?" | "Prototype runs end to end today. A one-region pilot is 6 weeks, and the first two connect real order history." |
| "What if the AI says something wrong?" | "Every number in a recommendation is checked against the account's data. If it doesn't match after one retry, the recommendation is withheld, not sent." |

## Technical stakeholder objections

| Objection | Answer (with detail) |
|---|---|
| "The model trained on synthetic data." | "Yes, deliberately: the demo ERP data has no link between pain and later revenue. The history is anchored to real account levels, and one switch (`HISTORY_SOURCE = "cdm"`) retrains on real CDM history once about 23 months exist. Promotion gates (out-of-time AUC >= 0.70 and >= 0.05 above the rule) stop a weaker model reaching reps." |
| "Why logistic regression?" | "It validated best out-of-time and gives exact per-account drivers (coefficient x standardized value), which is what reps need. Gradient boosting is a drop-in candidate under the same gates." |
| "Data quality and freshness?" | "Lakeflow Connect ingests Salesforce incrementally; the declarative pipeline builds the gold table; the job ends by checking Lakebase matches Delta, and the app checks all consumers agree on the High count." |
| "Security?" | "Credentials in a secret scope; Unity Catalog classification and lineage; the app's database role can only read scores and append decisions, verified; Genie runs on the user's own token with scoped permissions." |
| "Why Lakebase and not query Delta?" | "Rep clicks need millisecond reads and a decision + audit write in one transaction: 1.3 ms p50 measured. Analytics stays on the metric view." |
| "Integration with Salesforce?" | "Batch reverse ETL writes JSON to the account and reportable risk fields, deployed from a source package. No callouts from Salesforce, so no network allow-lists." |
| "How does it scale?" | "Scoring is a batch over accounts, so it is linear in the book. Serverless compute, and Lakebase autoscaling for the app." |

## Altitude switches to practise

- Technical question from the business stakeholder: answer in one sentence of outcome, then offer detail.
- Business question from the architect: give the number, then the mechanism.
- Always end an answer by tying back to retained revenue or rep adoption.
