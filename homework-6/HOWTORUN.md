# How to Run — AI-Powered Multi-Agent Banking Pipeline

**Author:** Yevgen Polukov

---

## 1. Prerequisites

- Python 3.12 or newer
- pip
- git (for hook setup)
- Node.js + npx (for context7 MCP server only)

---

## 2. Setup

```bash
# Clone / navigate to the homework-6 directory
cd homework-6

# Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # macOS / Linux
# .venv\Scripts\activate       # Windows

# Install all dependencies
pip install -r requirements.txt
```

---

## 3. Run the Full Pipeline

```bash
python integrator.py
```

This will:
1. Clear `shared/input/`, `shared/processing/`, `shared/output/`, `shared/results/`
2. Load `sample-transactions.json` (8 transactions)
3. Run the Transaction Validator
4. Run the Fraud Detector
5. Run the Reporting Agent
6. Print a summary and write `shared/results/pipeline_summary.json`

Expected output:
```
==============================================================
  AI-Powered Banking Pipeline — Orchestrator
==============================================================

[1/5] Preparing directories …
[2/5] Loading sample transactions …
      Loaded 8 transactions.
[3/5] Seeding shared/input/ …
[4/5] Running Transaction Validator …
      Validated: 6  Rejected: 2
[4b/5] Running Fraud Detector …
       Scored:   6
[5/5] Running Reporting Agent …

==============================================================
  Pipeline Summary
==============================================================
  Total transactions : 8
  Validated          : 6
  Rejected           : 2
  Fraud LOW          : X
  Fraud MEDIUM       : X
  Fraud HIGH         : X
  Processed at       : 2026-03-24T...Z
==============================================================
```

---

## 4. Validator Dry-Run (No File Writes)

To validate `sample-transactions.json` without running the full pipeline:

```bash
python agents/transaction_validator.py --dry-run
```

Or with a custom file:

```bash
python agents/transaction_validator.py --dry-run --input /path/to/your/transactions.json
```

This prints a report to stdout showing total, valid, invalid counts and reason codes.

---

## 5. Run Tests with Coverage

```bash
# Full test suite with coverage report
pytest

# Or explicitly:
pytest --cov=agents --cov=common --cov=integrator --cov-report=term-missing

# Generate HTML coverage report
pytest --cov-report=html:htmlcov
open htmlcov/index.html
```

The `pytest.ini` in this directory configures `--cov-fail-under=80` so pytest
exits with a non-zero code if coverage drops below 80%.

---

## 6. Enable / Install the Pre-Push Coverage Hook

The pre-push hook blocks `git push` if test coverage is below 80%.

```bash
# One-command install
bash scripts/install_hooks.sh

# What it does:
#   git config core.hooksPath .githooks
#   chmod +x .githooks/pre-push
```

To uninstall:

```bash
git config --unset core.hooksPath
```

To test the hook manually:

```bash
bash .githooks/pre-push
```

---

## 7. Run the MCP Server

The custom FastMCP server exposes pipeline results as MCP tools and resources.

```bash
python mcp/server.py
```

The server will start and listen for MCP protocol connections (stdio transport).

Available tools:
- `get_transaction_status(transaction_id)` — e.g. `get_transaction_status("TXN001")`
- `list_pipeline_results()` — returns all processed transactions

Available resource:
- `pipeline://summary` — latest `pipeline_summary.json` content

To include both MCP servers in Claude Code, the `mcp.json` at the project root
configures context7 and pipeline-status:

```json
{
  "mcpServers": {
    "context7": {
      "command": "npx",
      "args": ["-y", "@upstash/context7-mcp@latest"]
    },
    "pipeline-status": {
      "command": "python",
      "args": ["mcp/server.py"]
    }
  }
}
```

---

## 8. Use the Claude Slash Commands

The following slash commands are available in Claude Code when working in this
project directory:

| Command | Description |
|---|---|
| `/write-spec` | Generate `specification.md` from the template |
| `/run-pipeline` | Run the full pipeline end-to-end and show summary |
| `/validate-transactions` | Dry-run validator on `sample-transactions.json` |

To invoke in Claude Code:

```
/run-pipeline
/validate-transactions
/write-spec
```

---

## 9. Inspect Results

After running the pipeline:

```bash
# List all result files
ls shared/results/

# View a specific transaction result
cat shared/results/TXN001.json

# View the pipeline summary
cat shared/results/pipeline_summary.json

# View the audit log
cat shared/results/audit.log
```

---

## 10. Project Structure

```
homework-6/
├── agents/                  # Runtime agent modules
│   ├── transaction_validator.py
│   ├── fraud_detector.py
│   └── reporting_agent.py
├── common/                  # Shared utilities
│   ├── audit.py
│   ├── io_utils.py
│   ├── masking.py
│   ├── message.py
│   └── paths.py
├── mcp/
│   └── server.py            # FastMCP pipeline-status server
├── tests/                   # pytest test suite
├── shared/                  # Pipeline communication directories
│   ├── input/
│   ├── processing/
│   ├── output/
│   └── results/
├── .claude/commands/        # Claude slash commands
├── .githooks/pre-push       # Coverage gate hook
├── scripts/
│   ├── check_coverage.py
│   └── install_hooks.sh
├── integrator.py            # Pipeline orchestrator
├── sample-transactions.json
├── pytest.ini
├── requirements.txt
├── mcp.json
├── specification.md
├── agents.md
├── research-notes.md
├── README.md
└── HOWTORUN.md
```
