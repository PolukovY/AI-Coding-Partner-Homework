# Pull Request — Homework 6: AI-Powered Multi-Agent Banking Pipeline

**Author:** Yevgen Levik
**Branch:** `homework-6-submission`
**Target:** `main`

---

## Summary

This PR implements the capstone project: a multi-agent banking transaction processing
pipeline driven by four meta-agents (specification, code generation, testing, and
documentation).

---

## Deliverables

### 1. Specification (Agent 1)

- [x] `specification.md` — complete 5-section technical specification
- [x] `agents.md` — describes all four meta-agents and three runtime agents
- [x] `.claude/commands/write-spec.md` — slash command that generates the spec

**Screenshot — specification produced:**

<!-- Insert screenshot here: docs/screenshots/spec-produced.png -->
> _Paste or drag the spec screenshot here_

---

### 2. Pipeline Run (Agent 2)

- [x] `integrator.py` — orchestrator
- [x] `agents/transaction_validator.py`
- [x] `agents/fraud_detector.py`
- [x] `agents/reporting_agent.py`
- [x] `common/` — shared utilities (audit, masking, message, io_utils, paths)
- [x] `sample-transactions.json` — 8 transactions (6 valid, 2 rejected)

All 8 transactions appear in `shared/results/` after running `python integrator.py`.

**Screenshot — pipeline run:**

<!-- Insert screenshot: docs/screenshots/pipeline-run.png -->
> _Paste or drag the pipeline terminal output screenshot here_

---

### 3. Tests and Coverage (Agent 3)

- [x] `tests/test_transaction_validator.py`
- [x] `tests/test_fraud_detector.py`
- [x] `tests/test_reporting_agent.py`
- [x] `tests/test_common.py`
- [x] `tests/test_integration_pipeline.py`
- [x] Coverage target: ≥ 90% (gate: 80%)

**Screenshot — test coverage:**

<!-- Insert screenshot: docs/screenshots/test-coverage.png -->
> _Paste or drag the pytest coverage report screenshot here_

---

### 4. Skills and Hook (Agent 3)

- [x] `.claude/commands/run-pipeline.md`
- [x] `.claude/commands/validate-transactions.md`
- [x] `.githooks/pre-push` — coverage gate hook
- [x] `scripts/check_coverage.py`
- [x] `scripts/install_hooks.sh`

**Screenshot — `/run-pipeline` skill executing:**

<!-- Insert screenshot: docs/screenshots/skill-run-pipeline.png -->
> _Paste or drag the slash command execution screenshot here_

**Screenshot — hook firing:**

<!-- Insert screenshot: docs/screenshots/hook-trigger.png -->
> _Paste or drag the hook trigger screenshot here_

---

### 5. MCP Integration (Agent 2 + 4)

- [x] `mcp.json` — context7 + pipeline-status servers
- [x] `mcp/server.py` — FastMCP server with 2 tools + 1 resource
- [x] `research-notes.md` — 3 context7 queries documented

MCP tools:
- `get_transaction_status(transaction_id)` — returns result from `shared/results/`
- `list_pipeline_results()` — returns all transaction summaries
- Resource: `pipeline://summary`

**Screenshot — MCP interaction:**

<!-- Insert screenshot: docs/screenshots/mcp-interaction.png -->
> _Paste or drag the MCP tool call screenshot here_

---

### 6. Documentation (Agent 4)

- [x] `README.md` — includes author name, ASCII diagram, tech stack table
- [x] `HOWTORUN.md` — numbered steps for all operations
- [x] `docs/screenshots/README.md` — screenshot capture guide
- [x] `docs/PR_DESCRIPTION_TEMPLATE.md` — this file

**Screenshot — README with author name:**

<!-- Insert screenshot here -->
> _Paste a screenshot of the README showing "Created by Yevgen Levik"_

---

## Screenshot Checklist

- [ ] Specification produced / `specification.md` visible
- [ ] Pipeline run terminal output (`python integrator.py`)
- [ ] Test coverage report (≥ 80%, target ≥ 90%)
- [ ] `/run-pipeline` slash command executing in Claude Code
- [ ] Coverage gate hook firing (pre-push block or allow)
- [ ] MCP tool call result (`get_transaction_status` or `list_pipeline_results`)
- [ ] README with author name ("Created by Yevgen Levik")

---

## How to Test

```bash
cd homework-6
pip install -r requirements.txt
python integrator.py
pytest
python agents/transaction_validator.py --dry-run
```
