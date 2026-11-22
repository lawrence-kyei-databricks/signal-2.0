# Roleplay Preparation - Signal 2.0

Two personas in the room: **business stakeholder** (VP Commercial, funds the decision) and **technical stakeholder** (data and platform architect, lives with the build).

## Opening (tell) - 60 seconds

"Your reps find out an account is slipping when the revenue report says so. By then it is too late. Today I'll show you how Signal 2.0 puts 46% of the revenue about to walk out the door in front of reps, up from 28%, with the same effort, inside Salesforce where they already work. I'll show the rep's view, the manager's view, and how it stays governed. Then I'll land what it is worth, and I'll separate what we measured from what we assumed."

**Say this before anyone asks (rigour, not concession):** "The model trains on synthetic history, because the demo data has no link between operational pain and later revenue. The rule and the model are compared in the same authored world, so the lift over today's rule is a fair relative comparison; the absolute accuracy is not something I'd promise on your data. We recalibrated the history to your real order cadence and check every run that the scores on live accounts look like training. First pilot job: recalibrate on six months of real decline labels."

## Demo flow (show) - keep to 8-10 minutes

| Step | Show | Land it (one line) |
|---|---|---|
| 1 | Salesforce account page (Massachusetts General Hospital): briefing popup, High, score 47.5, drivers "revenue at 0.33x run rate, 80% of order lines with pushed delivery dates", recommendations | "The rep knows what is wrong and what to do before the first call." |
| 2 | Signal Account Cockpit: worklist ranked by expected dollar loss, open MGH (AI recommendations and deep signals), accept the alert | "The day starts with the biggest exposure, and every decision is recorded under the rep." |
| 3 | Genie in the app: "Which 5 accounts have the highest risk score, and what is their top risk driver?" with table and chart | "Managers get answers in seconds, from the same governed numbers." |
| 4 | Dashboard: expected revenue at risk by region | "One number for revenue at risk, everywhere." |
| 5 | Lineage, the refresh job, and the drift check in MLflow (brief, for the architect) | "One job, every layer connected, and it fails rather than serve stale or drifted scores." |

## Close (tell) - 60 seconds

"Same effort, 17.7 more points of the revenue you actually lost in front of reps; on the test months that was about $45 million. Projected onto today's book, about $99 million more at-risk revenue reaches reps, and about $25 million a year retained if they save a quarter of what they work. The save rate is the one number I'm assuming, so I'm asking for a 6-week, one-region pilot with a control group to measure it."

## Business stakeholder objections

| Objection | Answer (executive altitude) |
|---|---|
| "How do I know the $24.8M is real?" | "Two parts. Measured: on held-out months, 46.1% vs 28.4% of lost revenue reached reps, about $45M over two months. Assumed: the 25% save rate, which is why the pilot has a control group. Every 5 points of save rate is about $5M." |
| "You measured on lost revenue but projected on at-risk revenue. Same thing?" | "No, and I say so on the slide. The lift is measured as a share of revenue that was actually lost; the projection applies that share to today's expected revenue at risk. It assumes the model ranks today's book as well as it ranked the test months. That's why the $45M measured number leads." |
| "Isn't this just sorting by big accounts?" | "Partly, and on purpose: ranking by dollars at risk does most of the work. A revenue-weighted version of today's rule gets 42.3%; the model gets 46.1% because it also reads delivery slips, backorders, activity and cases. You need both." |
| "What does it cost?" | "It runs on data you already have, on one scheduled job and a small app database. The pilot cost is a few weeks of a data engineer and 10 reps' time; we size production cost from the pilot's actual usage." |
| "Reps won't use another tool." | "They don't have to. The briefing is on the Salesforce account page. The app is for reps who want a worklist, and we can see adoption by rep." |
| "Time to value?" | "Prototype runs end to end today. A one-region pilot is 6 weeks, and the first two connect real order history." |
| "What if the AI says something wrong?" | "Every number in a recommendation is checked against the account's data. If it doesn't match after one retry, the recommendation is withheld, not sent." |

## Technical stakeholder objections

| Objection | Answer (with detail) |
|---|---|
| "The model trained on synthetic data." | (Raise it first; see the opening.) "The history sits on each account's real levels and real order cadence for all 24 months. An earlier smoother history gave AUC 0.818; once revenue was as lumpy as yours it fell to 0.625, which is the honest number. One switch (`HISTORY_SOURCE = "cdm"`) retrains on real history once about 23 months exist." |
| "Train on synthetic, score on real: how do you know the distributions match?" | "We check every run. Score PSI between training and today's live accounts is 0.034, and promotion is blocked above 0.10. Five individual inputs still shift (revenue level, momentum, backorders, activity), logged per feature in MLflow. That's the monitoring story for production." |
| "Why logistic regression?" | "It gives exact per-account drivers, which is what reps need. A gradient-boosted model scored higher out-of-time (AUC 0.715) but failed our drift gate, so it didn't ship. Same gates apply when real history arrives." |
| "Data quality and freshness?" | "Lakeflow Connect ingests Salesforce incrementally; the declarative pipeline builds the gold table; the job ends by checking Lakebase matches Delta, and the app checks all consumers agree on the High count." |
| "Security?" | "Credentials in a secret scope; Unity Catalog classification and lineage; the app's database role can only read scores and append decisions, verified; Genie runs on the user's own token with scoped permissions." |
| "Why Lakebase and not query Delta?" | "Opening an account went from 979 ms to 59 ms server side once everything the panel reads was synced to Lakebase; the warehouse alone takes about 375 ms per lookup. Inside the database a lookup is 2-4 ms; the rest is the connection. Writes are a decision + audit row in one transaction. Analytics stays on the metric view." (If they open the network tab: those are server-side numbers; the browser adds the app proxy.) |
| "Integration with Salesforce?" | "Batch reverse ETL writes JSON to the account and reportable risk fields, deployed from a source package. No callouts from Salesforce, so no network allow-lists." |
| "How does it scale?" | "Scoring is a batch over accounts, so it is linear in the book. Serverless compute, and Lakebase autoscaling for the app." |

## Altitude switches to practise

- Technical question from the business stakeholder: answer in one sentence of outcome, then offer detail.
- Business question from the architect: give the number, then the mechanism.
- Always end an answer by tying back to retained revenue or rep adoption.
