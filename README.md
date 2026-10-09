# unit2-capstone

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
