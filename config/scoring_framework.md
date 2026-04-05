# Job Scoring Framework
> Scoring rubric used by the AI node to evaluate LinkedIn job postings against candidate priorities.
> Total possible score: 100 points.

---

## Scoring Categories

### 1. Compensation (0–30 pts)
The single biggest filter. The band is set in `.env` as `COMP_FLOOR`, `COMP_TARGET`, and `COMP_TOP`.

| Condition | Points |
|---|---|
| At or above `COMP_TOP` (total comp: base + equity + bonus) | 30 |
| `COMP_TARGET` up to `COMP_TOP` | 25 |
| `COMP_FLOOR` up to `COMP_TARGET` | 15 |
| Under `COMP_FLOOR` | 0 |
| Salary not listed | 0 |

> Not listed gets zero credit — if the salary isn't posted, don't assume it's competitive.

---

### 2. Role Alignment — AI Focus (0–30 pts)
The candidate moved intentionally into a full-time AI role. This category protects that move.
Use the candidate profile (candidate_profile.md) as the reference definition of a fully-aligned role.

| Condition | Points |
|---|---|
| Full AI Transformation role with technical building (MCP, agents, LLMs, production tooling) | 30 |
| AI Program / Strategy role with strong technical component | 22 |
| AI Enablement / Adoption role — some building, mostly coordination | 15 |
| AI-adjacent TPM / Director role — AI in title, but mostly project coordination | 8 |
| Traditional TPM/PM with "AI" mentioned as a minor duty | 3 |
| No meaningful AI component | 0 |

> Key signal: Does the role expect the person to BUILD as well as lead? If it's purely coordination with no hands-on AI/technical work, score it lower.

---

### 3. Company Prestige (0–25 pts)
Targeting FAANG and leading AI companies. Avoiding staffing firms and consulting agencies.

| Condition | Points |
|---|---|
| FAANG: Google, Apple, Meta, Amazon, Netflix, Microsoft | 25 |
| Top AI companies: OpenAI, Anthropic, xAI, Mistral, Cohere, Perplexity, Inflection, etc. | 25 |
| Top-tier tech / unicorns: Stripe, Databricks, Snowflake, Uber, Airbnb, Salesforce, etc. | 18 |
| Known enterprise tech company (Fortune 500 tech) | 12 |
| Unknown startup or small company | 5 |
| Staffing agency, consulting firm, or contract role | 0 |

---

### 4. Location (0–13 pts)
Only four acceptable locations. Anything else is not being considered at this time.

| Condition | Points |
|---|---|
| SF Bay Area (San Francisco, Palo Alto, Mountain View, San Jose, etc.) | 13 |
| NYC (New York City, Manhattan, Brooklyn, etc.) | 13 |
| Miami / South Florida | 13 |
| Remote (location not required) | 13 |
| Not specified — could be remote | 5 |
| Any other location | 0 |

---

### 5. Work Arrangement (0–2 pts)
Nice-to-have signal. Many strong jobs don't specify — don't penalize heavily.

| Condition | Points |
|---|---|
| Fully remote | 2 |
| Hybrid | 1 |
| On-site / Not specified | 0 |

---

## Score Thresholds

| Score | Rating | Action |
|---|---|---|
| 80–100 | 🔥 Top Priority | Apply immediately |
| 60–79 | ✅ Strong Fit | Worth applying |
| 40–59 | 🤔 Possible | Review manually before deciding |
| Below 40 | ❌ Skip | Filter out — do not send to Google Sheets |

---

## Scoring Notes for the AI Node

- Score each category independently, then sum for the total.
- If you cannot determine a value clearly from the job post, use the lower end of the range — do not assume.
- For **compensation**: Total comp includes base + equity + bonus. If only base is listed, treat it as base only.
- For **role alignment**: Use `candidate_profile.md` as the benchmark definition of full alignment.
- For **company prestige**: If the company name is unfamiliar, score it as Unknown Startup (5 pts).
- For **location**: If a job says "US Remote" or "Remote - USA", score it as Remote (13 pts) and Remote for work arrangement (2 pts).
- Always return a reason string explaining the score for each category.
