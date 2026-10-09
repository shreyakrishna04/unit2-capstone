# unit2-capstone

## Architecture Diagram
User Query (CLI)
      │
      ▼
┌─────────────────┐
│  Manager Agent  │  ── classifies query ──► qualitative / quantitative / both
└─────────────────┘
      │                          │
      ▼                          ▼
┌──────────────────┐    ┌───────────────────┐
│ Qualitative Agent│    │ Quantitative Agent │
│                  │    │                   │
│ • Vector DB      │    │ • SQLite DB        │
│   (ChromaDB)     │    │ • NL → SQL         │
│ • Semantic search│    │ • Query execution  │
│ • Claude for     │    │ • Claude for       │
│   generation     │    │   interpretation   │
└──────────────────┘    └───────────────────┘
      │                          │
      └──────────┬───────────────┘
                 ▼
      ┌─────────────────────┐
      │  Validation Layer   │  ── checks grounding, flags issues
      └─────────────────────┘
                 │
                 ▼
      ┌─────────────────────┐
      │  Tokenomics Logger  │  ── logs token usage and cost per query
      └─────────────────────┘
                 │
                 ▼
        Response to User

## Setup and Usage Instructions

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Add your API key to a .env file (never commit this file)
echo "GEMINI_API_KEY=your_key_here" > .env

# 3. Seed the database (if not already present)
python setup_db.py

# Start the interactive assistant
python main.py

Type a question at the prompt. The manager classifies each query and routes it:
qualitative (document search), quantitative (SQL + database), or both (multi-agent). Model: gemini-3.5-flash-lite. 

Example: Show me monthly revenue trends


## Trust-but-Verify

### Query 1 — Qualitative (document search)
**Query submitted:** "What is our company's security policy?"

**Route chosen:** `qualitative` — the classifier correctly identified this as a
policy/documentation question and routed it to the document-search agent only.

**What the model returned:** A detailed summary of Spoonful's Information Security
Policy covering seven areas — Access Control (least-privilege, quarterly reviews,
access revoked within 4 hours of departure), Authentication (mandatory MFA, 14-char
passwords), Data Classification (four tiers; customer data Restricted, AES-256 at
rest / TLS 1.2+ in transit), Incident Response (report within 1 hour, 72-hour breach
notification), Acceptable Use, Third-Party Risk (annual assessments, SOC 2 Type II),
and Policy Review (annual CISO review). Every claim carried a `[Source 1]` citation.

**What the validation layer flagged:** Nothing — no validation warning was printed.
The qualitative validator looks for source citations in the response; because every
bullet cited `[Source 1]`, `is_grounded` evaluated True and `flag` was False.

**What I accepted / changed, and why:** Accepted as-is. The answer was fully grounded with inline citations on every point, the route was correct, and the content matched the source document. Cost for the call was $0.001807 (2,399 input / 435 output tokens),which the tokenomics logger recorded. No changes needed.

### Query 2 — Qualitative (document search)
**Query submitted:** "Explain the code review process"

**Route chosen:** `qualitative` — correctly routed to the document-search agent as a
process/documentation question.

**What the model returned:** A structured summary of Spoonful's code review process:
Pull Request Requirements (PRs against main, ticket link, passing tests, <400 lines),
Reviewer Assignment (≥1 approval; 2 approvals incl. a senior for security-sensitive
areas; CODEOWNERS for protected dirs), What Reviewers Check (correctness, test
coverage, security; style left to linters), Service-Level Expectations (first feedback
within 1 business day), Merging/Deployment (CI/CD; expedited hotfix path with 24-hour
retrospective), and Continuous Improvement (quarterly retrospective metrics). Every
claim cited `[Source 1]`.

**What the validation layer flagged:** Nothing. Every statement carried a `[Source 1]`
citation, so the grounding check passed and no warning was printed.

**What I accepted / changed, and why:** Accepted as-is. Fully grounded, correctly
routed, consistent with the source document. Call cost $0.002017 (2,407 input /
518 output tokens), logged by the tokenomics layer.

### Query 3 — Quantitative (SQL + data) — a result I did NOT initially trust
**Query submitted:** "Show me monthly revenue trends"

**Route chosen:** `quantitative` — correctly routed to the SQL/data agent.

**What the model returned (first attempt):** No data. The agent generated SQL using
`DATE_TRUNC('month', date)`, and execution failed with:
`Query execution failed: no such function: DATE_TRUNC`.

**What the validation layer flagged:** `⚠️ VALIDATION WARNING: SQL validation
status: ERROR`. The quantitative validator detected the failed execution and raised
a warning instead of presenting a broken result as valid.

**Why I did not trust it, and how I resolved it:** The SQL was syntactically plausible,
but `DATE_TRUNC` is PostgreSQL syntax — our database is SQLite, which has no such
function. I rejected the output, confirmed the dialect mismatch from the error, and
fixed the root cause: I added a SQLite-dialect instruction to the quantitative agent's
`SCHEMA_CONTEXT` prompt (use `strftime('%Y-%m', date)` for month grouping; do not use
`DATE_TRUNC`). I then re-ran the identical query.

**Verified result after fix:** SQL now uses
`SELECT strftime('%Y-%m', date) AS month, SUM(revenue) AS total_revenue FROM sales
GROUP BY strftime('%Y-%m', date) ORDER BY month;` — execution PASSED with no warning.
Returned 2024 monthly revenue: a peak in July ($17,940), a secondary peak in October
($8,970), a moderate $1,500–$3,500 baseline across most months, and lows in November
($190) and September ($833).

**Outcome:** The validation layer caught a confidently-wrong "no data" result before
it could be trusted, and the prompt fix produced a correct, verified answer.


### Query 4 — Complex / multi-agent (both routes)
**Query submitted:** "How does our employee satisfaction compare to industry
standards and what policies might impact this?"

**Route chosen:** `both` — correctly identified as needing document search (industry
standards, policies) AND data analysis (our satisfaction numbers). Dispatched to the
qualitative and quantitative agents.

**What the model returned:**
- *Qualitative half:* Spoonful targets an overall satisfaction score of ≥4.0, above
  the 3.6–3.9 benchmark cited for comparable B2B software firms; summarized the
  Employee Engagement and Satisfaction Policy, tenure/retention supports, and
  wellbeing/flexibility measures. Every claim cited `[Source 1]`.
- *Quantitative half:* Per-department averages from the `employees` table —
  Engineering 4.57 (8.6 yr tenure), Marketing 4.10, Operations 3.53, Support 3.20,
  Sales 2.87 (1.3 yr tenure) — plus four "potential policies impacting these scores."

**What the validation layer flagged:** No warning on either agent. The qualitative
answer was fully cited (grounding check passed); the SQL executed successfully
(`SELECT department, AVG(satisfaction_score), AVG(tenure_years) FROM employees GROUP
BY department;`), so the quantitative validator passed it.

**What I accepted, what I did not trust, and why:** I accepted both the cited policy
summary and the raw per-department averages — those are grounded in the document and
the database respectively. However, I did NOT fully trust the quantitative agent's
"Potential Policies Impacting These Scores" section. That part (e.g. "high-pressure
commission structures," "ticket-handling quotas driving burnout") is the model
INFERRING causes that are not present in the SQL result — the query only returned
averages, not any causal driver. The agent even flagged part of this itself, noting
"the database does not contain external benchmark data." Resolution: I kept the
numeric averages and the cited policy facts, but treated the causal policy
explanations as hypotheses, not findings, and would not present them as data-backed
conclusions without further evidence. The validation layer passed this because the SQL
ran correctly — a reminder that passing validation confirms the SQL is valid, not that
every sentence of the model's prose is grounded.

### Query 5 — Quantitative (SQL + data)
**Query submitted:** "What is our customer churn rate?"

**Route chosen:** `quantitative` — correctly routed to the SQL/data agent.

**What the model returned:** "Your current customer churn rate is 33.33%" — i.e.
one-third of recorded customers have a non-null churn_date.

**SQL generated:**
    SELECT (CAST(SUM(CASE WHEN churn_date IS NOT NULL THEN 1 ELSE 0 END) AS REAL)
            / COUNT(*)) * 100 AS churn_rate
    FROM customers;

**What the validation layer flagged:** Nothing. The query is a valid SELECT, executed
successfully, so the quantitative validator passed it with no warning.

**What I accepted / changed, and why:** I accepted the SQL and the 33.33% figure — the
logic is correct for the definition it used (share of all-time customers with any churn
date). I noted one caveat for interpretation: this is a cumulative all-time churn ratio,
NOT a period-based rate (e.g. monthly/annual churn), because the query divides total
churned by total customers with no time window. The number is correct for what was
computed; I would clarify the definition before using it as a KPI.

### Query 6 — Quantitative (SQL + data)
**Query submitted:** "Compare Q4 performance across regions"

**Route chosen:** `quantitative` — correctly routed to the SQL/data agent.

**What the model returned:** A Q4 regional comparison — Central led with $8,970
(30 units), South second with $2,970 (30 units), North lowest at $190 (10 units) —
with the takeaway that Central outperformed South ~3x and North ~47x.

**SQL generated:**
    SELECT region, SUM(revenue) AS total_revenue, SUM(units_sold) AS total_units_sold,
           AVG(revenue) AS average_revenue
    FROM sales
    WHERE CAST(strftime('%m', date) AS INTEGER) IN (10, 11, 12)
    GROUP BY region ORDER BY total_revenue DESC;

**What the validation layer flagged:** Nothing. Valid SELECT, executed successfully,
quantitative validator passed with no warning. (Note: this query also confirmed the
SQLite dialect fix from Query 3 is working — it correctly used strftime, not DATE_TRUNC.)

**What I accepted / changed, and why:** I accepted the figures and ranking — the SQL
correctly sums revenue/units by region for the Oct–Dec window. One caveat I noted on
verification: the WHERE clause filters months 10–12 across ALL years in the table,
not a single fiscal year's Q4. If the data spans multiple years this would blend them.
For this synthetic single-year dataset it's correct, but I'd add a year filter before
using it on multi-year data.

### Query 7 — Qualitative (document search)
**Query submitted:** "How do we handle customer complaints?"

**Route chosen:** `qualitative` — correctly routed to the document-search agent.

**What the model returned:** The complaint-handling procedure — Intake (all channels
logged as cases, none handled informally), Severity Levels (Sev 1 critical: 1-hr ack /
4-hr target; Sev 2 major: 4-business-hr ack / 2-day target; Sev 3 minor: 1-day ack /
5-day target), Escalation (team lead; Sev 1 to Director of Customer Success + eng
on-call; enterprise copied to account manager), Closing the Loop (customer must
confirm resolution; root cause recorded; unconfirmed cases auto-reopened), and
Learning from Complaints (monthly review; Sev 1/2 spikes flagged as churn-risk signal).
Every claim cited `[Source 1]`.

**What the validation layer flagged:** Nothing. Every statement carried a `[Source 1]`
citation, so the grounding check passed and no warning was printed.

**What I accepted / changed, and why:** Accepted as-is. Fully grounded, correctly
routed, consistent with the source document. Call cost $0.001753 (2,368 input /
417 output tokens).

### Query 8 — Complex / multi-agent (both) — the result I trusted LEAST
**Query submitted:** "Analyse our sales performance and recommend policy changes
based on our customer success strategies"

**Route chosen:** `both` — correctly split to the qualitative and quantitative agents.

**What the model returned:**
- *Qualitative half:* Grounded, honest partial answer — it reported that regional
  sales are reviewed jointly with Customer Success and that churn/complaint data is
  shared with Sales [Source 1], then explicitly stated "the provided context does not
  outline specific policy changes for sales... I cannot find any other specific sales
  policy recommendations." It did not invent policy that wasn't in the docs.
- *Quantitative half:* All of total_revenue, total_units_sold and revenue_per_customer
  came back as NULL. The agent itself diagnosed the cause: the SQL used
  `LEFT JOIN sales s ON c.name = s.product` — joining customer NAME to product NAME,
  which never matches. It still produced satisfaction/churn figures (Technology best:
  4.33, zero churn; Healthcare worst: 2.57, 2 of 3 churned) and recommendations.

**What the validation layer flagged:** NOTHING. The SQL was a syntactically valid
SELECT and executed without error — it simply returned NULLs. The validator checks for
blocked keywords and execution errors, so a query that "succeeds" but is logically
wrong passes straight through with no warning.

**Why I did not trust it, and how I resolved it:** This is the clearest example of why
validation-passing is not the same as trustworthy. The revenue analysis was built on a
broken join (`c.name = s.product` is meaningless — there is no key relating customers to
sales in the schema). I did NOT accept any revenue/ROI claim. I DID accept the
satisfaction/churn-by-industry figures, which came from the valid `customers`-only
columns, and I accepted the qualitative half because it was cited and honestly admitted
its limits. Notably, the model self-flagged the NULLs rather than hiding them — but I
treated that as a prompt-for-verification, not a free pass. Resolution: I confirmed from
the schema that `sales` has no customer foreign key at all, so sales cannot currently be
attributed to a customer/industry; the "fix the join" recommendation is not achievable
without a schema change. I recorded the revenue analysis as INVALID and kept only the
satisfaction/churn insights.

### Conversation history

Follow-up questions work because the system remembers earlier turns. History is kept
in a module-level list in `manager.py` (`_HISTORY`), which survives across `run()`
calls without touching `main.py`, and only the last 5 turns are held onto so the
re-sent context doesn't balloon the token count. The answering agents see the whole
exchange — questions and answers — so something like "why?" still makes sense, while
the classifier only needs the earlier questions to figure out routing. One thing to
watch: when history feeds into SQL generation, the model can keep the subject of a
follow-up but quietly drop a filter from the original question (see Q9), so it's worth
sanity-checking chained results against what was first asked.


### Token optimization: trimming classifier context
The manager's classifier only needs prior **topics** to route a follow-up, not the
full prior **answers**. So the classifier receives previous questions only
(`_classifier_context()`), while the answering agents still get the full history
(questions + answers) via `_history_context()`. This keeps classifier input near its
~84-token baseline instead of growing with each answer (it had climbed to 150+ once
history was enabled), with zero impact on routing accuracy or answer quality — the
classifier's one-word decision is unchanged, and the agents that produce the actual
output lose nothing.

