# Write Specification

Generate a complete technical specification for the banking pipeline project following the required template.

## Steps

1. Read `specification-TEMPLATE-hint.md` (if present) and `agents.md` for project context.

2. Read `sample-transactions.json` to understand the input data structure and identify which transactions will be valid vs. rejected.

3. Create or overwrite `specification.md` with exactly these five sections:

### Section 1 — High-Level Objective
One sentence describing the complete purpose of the pipeline.

### Section 2 — Mid-Level Objectives
4–5 concrete, testable bullet points. Each must be independently verifiable. Examples:
- Transactions with missing required fields are rejected with reason code MISSING_REQUIRED_FIELDS
- Amounts are parsed as decimal.Decimal and must be positive
- Fraud risk scoring uses 5 rules with a 0–10 scale
- All agent operations write ISO 8601 timestamped audit entries
- Test coverage gate blocks push if below 80%

### Section 3 — Implementation Notes
Must include:
- Monetary values: `decimal.Decimal` only, never `float`
- Currency: ISO 4217 whitelist (USD, EUR, GBP, JPY, CHF, CAD, AUD, NZD, SEK, NOK, DKK)
- Audit logging format: timestamp, agent name, transaction_id, outcome
- PII: mask account numbers as `ACC-****` in all logs

### Section 4 — Context
- Beginning state: describe `sample-transactions.json` and its 8 transactions
- Ending state: `shared/results/` with 8 result files, `pipeline_summary.json`, coverage ≥ 90%

### Section 5 — Low-Level Tasks
One entry per runtime agent using this exact format:
```
Task: [Agent Name]
Prompt: "[Exact prompt to give an AI coding assistant]"
File to CREATE: agents/<name>.py
Function to CREATE: <function_signature>
Details: [Specific checks, transformations, rules the agent implements]
```

Include entries for: Transaction Validator, Fraud Detector, Reporting Agent, and Orchestrator.

4. Print a confirmation: "specification.md written successfully."
