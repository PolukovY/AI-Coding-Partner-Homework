# Banking Pipeline — Technical Specification

**Author:** Yevgen Levik
**Version:** 1.0.0
**Date:** 2026-03-24

---

## 1. High-Level Objective

Build an AI-powered multi-agent Python pipeline that validates, scores for fraud risk, and reports on a stream of banking transactions using file-based JSON message passing through a shared directory protocol.

---

## 2. Mid-Level Objectives

- **M1 — Field Validation:** Every transaction must be checked for eight required fields; any record missing a field, containing a non-positive amount, or using a currency outside the ISO 4217 whitelist is rejected with a structured reason code before entering the fraud-scoring stage.
- **M2 — Fraud Scoring:** Validated transactions receive a deterministic integer risk score (0–10) and a level label (LOW / MEDIUM / HIGH) based on five rules: high value (>$10k, >$50k), unusual hour (02:00–05:59 UTC), cross-border indicator, and wire-transfer type.
- **M3 — Audit Logging:** Every agent operation is appended to `shared/results/audit.log` as a newline-delimited JSON record containing ISO 8601 timestamp, agent name, transaction_id, and outcome; account numbers are masked (e.g. `ACC-****`) and never logged in plaintext.
- **M4 — Results Persistence:** Each processed transaction produces a canonical JSON file in `shared/results/<TXN_ID>.json`; the pipeline also produces a `pipeline_summary.json` aggregating counts by status and fraud level.
- **M5 — Test Coverage Gate:** The unit test suite achieves ≥ 90% line coverage; a pre-push git hook (`.githooks/pre-push`) blocks pushes if coverage falls below 80%.

---

## 3. Implementation Notes

- **Monetary values:** Use `decimal.Decimal` exclusively; parse amounts with `Decimal(str(raw))`. Never use `float` for monetary arithmetic.
- **ISO 4217 currency handling:** Validate currency codes against a whitelist — minimum: `USD`, `EUR`, `GBP`, `JPY`, `CHF`, `CAD`, `AUD`, `NZD`, `SEK`, `NOK`, `DKK`. Reject unknown codes with `REASON_INVALID_CURRENCY`.
- **Audit logging:** Each log entry must include:
  - `timestamp` — ISO 8601 UTC (`%Y-%m-%dT%H:%M:%S.%fZ`)
  - `agent` — name of the emitting agent
  - `transaction_id` — or `"PIPELINE"` for orchestrator-level events
  - `outcome` — short description string
  - `details` — optional dict (must not contain plaintext account numbers)
- **PII protection:** Mask account numbers via `common.masking.mask_account()` before including them in any log record or audit trail. Never log `source_account` or `destination_account` in raw form.

---

## 4. Context

### Beginning State
A file `sample-transactions.json` at the project root contains 8 raw transaction records with varied statuses:
- 6 records that will pass validation (TXN001–TXN005, TXN008)
- 2 records that will be rejected:
  - TXN006 — invalid currency `XYZ`
  - TXN007 — negative amount `-100.00`

### Ending State
After running `python integrator.py`:
- `shared/results/TXN001.json` through `TXN008.json` — one result file per transaction
- `shared/results/pipeline_summary.json` — pipeline aggregate summary
- `shared/results/audit.log` — structured audit trail
- Test coverage ≥ 90% when running `pytest --cov`

---

## 5. Low-Level Tasks

---

### Task: Transaction Validator

```
Task: Transaction Validator
Prompt: "Implement a Python module agents/transaction_validator.py. The function
validate_transaction(transaction: dict) -> dict must check: (1) all 8 required
fields present; (2) amount parses as decimal.Decimal and is > 0; (3) currency is
in the ISO 4217 whitelist. Return a result dict with keys: transaction_id, status
('validated'|'rejected'), rejection_reason, rejection_detail, and data. A
process_message(message, audit) function wraps this for file-based pipeline use.
A run() function processes all .json files in shared/input/. Include a --dry-run
CLI mode that validates sample-transactions.json and prints a report."
File to CREATE: agents/transaction_validator.py
Function to CREATE: validate_transaction(transaction: dict) -> dict
Details:
  - Required fields: transaction_id, timestamp, source_account,
    destination_account, amount, currency, transaction_type, metadata
  - Reason codes: MISSING_REQUIRED_FIELDS, INVALID_AMOUNT,
    NON_POSITIVE_AMOUNT, INVALID_CURRENCY
  - Valid currencies: USD, EUR, GBP, JPY, CHF, CAD, AUD, NZD, SEK, NOK, DKK
  - Amount must be positive Decimal; use Decimal(str(raw)) for parsing
  - Rejected transactions go to shared/results/; validated go to shared/output/
  - Mask account numbers before logging
```

---

### Task: Fraud Detector

```
Task: Fraud Detector
Prompt: "Implement agents/fraud_detector.py. The function score_transaction(transaction:
dict) -> dict adds fraud_risk_score (int 0–10), fraud_risk_level ('LOW'|'MEDIUM'|'HIGH'),
and fraud_flags (list[str]) to the transaction dict. Rules: amount > 10000 => +3;
amount > 50000 => +4 additional (cumulative); unusual hour 02:00–05:59 UTC => +2;
non-US country => +1; wire_transfer type => +1. Score capped at 10. LOW=0–2,
MEDIUM=3–6, HIGH=7–10."
File to CREATE: agents/fraud_detector.py
Function to CREATE: score_transaction(transaction: dict) -> dict
Details:
  - Parse amount with Decimal
  - Parse timestamp UTC hour from ISO 8601 string
  - Flags: AMOUNT_HIGH, AMOUNT_VERY_HIGH, UNUSUAL_HOUR, CROSS_BORDER, WIRE_TRANSFER
  - process_message() wraps for file-based pipeline use
  - run() processes all .json files in shared/output/
  - Audit log includes masked account, score, and flags
```

---

### Task: Reporting Agent

```
Task: Reporting Agent
Prompt: "Implement agents/reporting_agent.py. The function produce_result(transaction:
dict) -> dict builds a canonical result record with keys: transaction_id, status,
amount, currency, transaction_type, fraud_risk_score, fraud_risk_level, fraud_flags,
rejection_reason, rejection_detail, processed_at (ISO 8601). The function
build_summary(results: list[dict]) -> dict aggregates counts: total_transactions,
validated_count, rejected_count, fraud_low_count, fraud_medium_count, fraud_high_count,
processed_at. run() writes per-transaction JSON files to shared/results/ and writes
pipeline_summary.json."
File to CREATE: agents/reporting_agent.py
Function to CREATE: produce_result(transaction: dict) -> dict
Details:
  - Write shared/results/<TXN_ID>.json for each processed transaction
  - Write shared/results/pipeline_summary.json with aggregated counts
  - Accept pre-collected rejected records via all_results parameter
  - Audit log each result write
```

---

### Task: Orchestrator

```
Task: Orchestrator
Prompt: "Implement integrator.py. The function run_pipeline() -> dict must:
(1) create/clear shared/ directories; (2) load sample-transactions.json;
(3) write each transaction as a PipelineMessage to shared/input/; (4) run
validator, fraud detector, and reporting agent in sequence; (5) ensure all 8
transactions appear in shared/results/; (6) print a formatted summary. Return
the summary dict."
File to CREATE: integrator.py
Function to CREATE: run_pipeline() -> dict
Details:
  - Use common.paths for all directory constants
  - Pass isolated directory arguments to each agent's run() for testability
  - Print stage progress to stdout
  - Write pipeline_summary.json via reporting agent
```
