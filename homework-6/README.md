# AI-Powered Multi-Agent Banking Pipeline

**Created by Yevgen Polukov**
**Course:** AI as a Personalized Coding Partner — Homework 6 (Capstone)

---

## What This System Does

This project implements an AI-powered multi-agent banking transaction processing
pipeline written in Python 3.12.  Raw transaction records are loaded from a JSON
file and passed through a three-stage pipeline: validation, fraud detection, and
reporting.  Agents communicate exclusively through file-based JSON message passing
across a shared directory hierarchy (`shared/input/` → `shared/output/` →
`shared/results/`), making the pipeline fully observable and debuggable at every
stage.

The system was designed by four meta-agents (specification, code generation, testing,
and documentation) each with a distinct role, modelling how AI assistants can be
composed into a complete software delivery workflow.  All monetary values use
`decimal.Decimal` (never `float`), currency codes are validated against an ISO 4217
whitelist, and account numbers are masked in every audit log entry.

---

## Agent Responsibilities

- **Transaction Validator** — checks 8 required fields, validates that amounts are
  positive `decimal.Decimal` values, and enforces ISO 4217 currency codes; rejects
  invalid records with structured reason codes before they proceed.
- **Fraud Detector** — scores every validated transaction on a 0–10 risk scale using
  five deterministic rules (high value, very high value, unusual hour, cross-border,
  wire transfer) and labels each as LOW / MEDIUM / HIGH risk.
- **Reporting Agent** — writes one canonical result JSON file per transaction to
  `shared/results/` and aggregates all outcomes into `pipeline_summary.json`.
- **Orchestrator** (`integrator.py`) — seeds the pipeline, coordinates agent
  execution in order, and prints a formatted progress + summary report.

---

## ASCII Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                    integrator.py (Orchestrator)                  │
│                                                                   │
│  sample-transactions.json                                         │
│         │                                                         │
│         ▼                                                         │
│   shared/input/                                                   │
│   TXN001.json ... TXN008.json   (raw PipelineMessage files)      │
│         │                                                         │
│         ▼                                                         │
│  ┌─────────────────────────────┐                                 │
│  │   Transaction Validator      │  ← agents/transaction_validator │
│  │   • field check              │                                 │
│  │   • Decimal amount           │                                 │
│  │   • ISO 4217 currency        │                                 │
│  └──────────┬──────────────────┘                                 │
│             │                    ╔══════════════════╗            │
│    validated│                    ║  rejected msgs   ║            │
│             ▼                    ║  shared/results/ ║            │
│      shared/output/              ╚══════════════════╝            │
│         │                                                         │
│         ▼                                                         │
│  ┌─────────────────────────────┐                                 │
│  │   Fraud Detector             │  ← agents/fraud_detector        │
│  │   • 5-rule scoring           │                                 │
│  │   • 0–10 risk scale          │                                 │
│  │   • LOW / MEDIUM / HIGH      │                                 │
│  └──────────┬──────────────────┘                                 │
│             │                                                     │
│             ▼                                                     │
│      shared/results/ (fraud-scored msgs)                         │
│         │                                                         │
│         ▼                                                         │
│  ┌─────────────────────────────┐                                 │
│  │   Reporting Agent            │  ← agents/reporting_agent       │
│  │   • per-transaction JSON     │                                 │
│  │   • pipeline_summary.json    │                                 │
│  │   • audit.log                │                                 │
│  └──────────────────────────────┘                                 │
└─────────────────────────────────────────────────────────────────┘

MCP Server (mcp/server.py — FastMCP)
  Tool: get_transaction_status(transaction_id)
  Tool: list_pipeline_results()
  Resource: pipeline://summary
```

---

## Tech Stack

| Component | Technology |
|---|---|
| Language | Python 3.12 |
| Testing | pytest 8+ |
| Coverage | pytest-cov 5+ |
| MCP server | FastMCP 2+ |
| Monetary arithmetic | `decimal.Decimal` (stdlib) |
| Message format | JSON (stdlib `json`) |
| Unique IDs | `uuid.uuid4` (stdlib) |
| Timestamps | ISO 8601 via `datetime` (stdlib) |
| File I/O | `pathlib.Path` (stdlib) |
| Data structures | `dataclasses` (stdlib) |
| Coverage gate | `.githooks/pre-push` + `scripts/check_coverage.py` |
| Claude slash commands | `.claude/commands/` |
| MCP integration | `mcp.json` (context7 + pipeline-status) |

---

## Quick Start

```bash
cd homework-6
pip install -r requirements.txt
python integrator.py
```

See [HOWTORUN.md](HOWTORUN.md) for full setup, test, and MCP server instructions.
