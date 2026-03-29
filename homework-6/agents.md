# Agents — AI-Powered Multi-Agent Banking Pipeline

**Author:** Yevgen Levik
**Project:** Homework 6 — Capstone

---

## Overview

This document describes the four **meta-agents** (AI/automation workflows) that
design, build, test, and document the AI-powered banking pipeline.  Each meta-agent
has a distinct role and produces a concrete artefact.

---

## Meta-Agent Roles

### 1. Specification Agent (Task 1 / Agent 1)

**Role:** Produce the complete technical specification before any code is written.

**Input:** Assignment requirements, sample-transactions.json, specification template.
**Output:** `specification.md`, `agents.md`, `.claude/commands/write-spec.md`.

**How it operates:**
1. Reads the assignment brief and sample data to understand domain requirements.
2. Drafts a High-Level Objective (one sentence).
3. Expands into 4–5 Mid-Level Objectives that are concrete and testable.
4. Writes Implementation Notes covering decimal handling, ISO 4217 currency, audit
   logging, and PII masking rules.
5. Defines Context (beginning state → ending state).
6. Generates Low-Level Tasks with exact prompts, file paths, and function signatures
   for each runtime agent.

**Key constraint:** No production code is written until this agent completes.

---

### 2. Code Generation Agent (Task 2 / Agent 2)

**Role:** Implement the runtime pipeline from the specification.

**Input:** `specification.md`, `sample-transactions.json`.
**Output:** `agents/`, `common/`, `integrator.py`, `shared/` directory structure.

**How it operates:**
1. Uses **context7** (MCP) to look up canonical documentation for Python's
   `decimal` module and `pytest-cov` configuration patterns.
2. Implements `common/` utilities: `message.py`, `audit.py`, `masking.py`,
   `io_utils.py`, `paths.py`.
3. Implements the three runtime agents in order:
   - `agents/transaction_validator.py`
   - `agents/fraud_detector.py`
   - `agents/reporting_agent.py`
4. Implements `integrator.py` to orchestrate the full pipeline.
5. Documents all context7 queries in `research-notes.md`.

**Key constraint:** Uses `decimal.Decimal` everywhere for amounts; never `float`.

---

### 3. Unit Test / Quality Gate Agent (Task 3 / Agent 3)

**Role:** Write the test suite and enforce the coverage gate.

**Input:** All production code from Agent 2.
**Output:** `tests/`, `.githooks/pre-push`, `scripts/check_coverage.py`, `pytest.ini`.

**How it operates:**
1. Writes unit tests for every public function in `agents/` and `common/`.
2. Writes at least one end-to-end integration test in `test_integration_pipeline.py`.
3. Uses `tmp_path` (pytest fixture) to isolate all file I/O from real `shared/`.
4. Configures `pytest.ini` with `--cov-fail-under=80`.
5. Creates `.githooks/pre-push` and `scripts/check_coverage.py` so that any
   `git push` is blocked when coverage falls below 80%.
6. Creates `.claude/commands/run-pipeline.md` and
   `.claude/commands/validate-transactions.md` slash commands.

**Key constraint:** No test should read from or write to the real `shared/`
directory; all tests use isolated `tmp_path` fixtures.

---

### 4. Documentation Agent (Task 4 / Agent 4)

**Role:** Generate all human-facing documentation.

**Input:** The completed codebase, test results, pipeline output.
**Output:** `README.md`, `HOWTORUN.md`, `docs/`, `research-notes.md`.

**How it operates:**
1. Writes `README.md` including: author name ("Created by Yevgen Levik"), system
   description, per-agent responsibility bullets, ASCII pipeline diagram, tech stack
   table.
2. Writes `HOWTORUN.md` with numbered setup, run, test, hook, and MCP instructions.
3. Documents at least 2 context7 queries in `research-notes.md`.
4. Creates placeholder screenshots with a `docs/screenshots/README.md` describing
   what each screenshot should capture.
5. Creates `docs/PR_DESCRIPTION_TEMPLATE.md` for the pull request.

**Key constraint:** README must include the student's name.

---

## Runtime Agents (Pipeline Workers)

These agents are the *output* of the meta-agents above — the actual transaction
processing system.

### Transaction Validator (`agents/transaction_validator.py`)

Validates raw transaction records:
- Checks all 8 required fields are present.
- Parses `amount` as `decimal.Decimal`; rejects if non-positive.
- Validates `currency` against ISO 4217 whitelist.
- Produces `validated` or `rejected` result with structured reason codes.
- Supports `--dry-run` CLI mode.

### Fraud Detector (`agents/fraud_detector.py`)

Scores validated transactions for fraud risk:
- 5-rule scoring engine producing an integer score 0–10.
- Maps score to risk level: LOW (0–2), MEDIUM (3–6), HIGH (7–10).
- Adds `fraud_risk_score`, `fraud_risk_level`, `fraud_flags` to transaction data.

### Reporting Agent (`agents/reporting_agent.py`)

Produces final results:
- Writes one `<TXN_ID>.json` result file per transaction to `shared/results/`.
- Aggregates all results into `pipeline_summary.json`.
- Includes both validated (fraud-scored) and rejected transactions in summary.

### Orchestrator (`integrator.py`)

Coordinates the pipeline:
- Sets up and clears `shared/` directories.
- Seeds `shared/input/` from `sample-transactions.json`.
- Calls validator → fraud detector → reporting agent in sequence.
- Prints formatted progress and summary to stdout.

---

## File-Based Communication Protocol

```
shared/
├── input/       ← orchestrator seeds raw transaction messages here
├── processing/  ← agent moves message here while working (prevents double-processing)
├── output/      ← validator writes validated messages here for fraud detector
└── results/     ← all final outcomes land here (validated + rejected)
```

### Standard Message Envelope

```json
{
  "message_id": "uuid4-string",
  "timestamp": "2026-03-16T10:00:00Z",
  "source_agent": "transaction_validator",
  "target_agent": "fraud_detector",
  "message_type": "transaction",
  "data": {
    "transaction_id": "TXN001",
    "amount": "1500.00",
    "currency": "USD",
    "status": "validated"
  }
}
```
