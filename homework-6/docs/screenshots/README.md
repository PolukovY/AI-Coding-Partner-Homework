# Screenshots — Required Captures

Place the following screenshots in this directory before submitting the pull request.
Each screenshot must be included both here and in the PR description.

---

## Required Screenshots

| Filename | What to Capture |
|---|---|
| `pipeline-run.png` | Full terminal output of `python integrator.py` showing all 5 stages, the pipeline summary table, and confirmation of 8 transactions processed |
| `test-coverage.png` | Terminal output of `pytest --cov=agents --cov=common --cov=integrator --cov-report=term-missing` showing per-module coverage percentages ≥ 80% (target ≥ 90%) |
| `skill-run-pipeline.png` | Claude Code session showing the `/run-pipeline` slash command being invoked and the AI executing the pipeline steps |
| `hook-trigger.png` | Terminal output showing the pre-push hook firing — either blocking a push (coverage < 80%) or allowing it (coverage ≥ 80%) |
| `mcp-interaction.png` | MCP tool call in Claude Code — showing either a `get_transaction_status` or `list_pipeline_results` tool response, and/or a context7 library lookup result |

---

## How to Capture Each Screenshot

### pipeline-run.png
```bash
cd homework-6
python integrator.py
# Screenshot the entire terminal window
```

### test-coverage.png
```bash
cd homework-6
pytest --cov=agents --cov=common --cov=integrator --cov-report=term-missing
# Screenshot from the start of the coverage table to the total line
```

### skill-run-pipeline.png
1. Open Claude Code in the `homework-6/` directory
2. Type `/run-pipeline` and press Enter
3. Screenshot the Claude Code window showing the AI's response and execution steps

### hook-trigger.png
Option A (show block):
1. Temporarily break a test so coverage drops below 80%
2. Run `git push` — the hook should print the block message
3. Screenshot the terminal
4. Restore the test

Option B (show pass):
1. Ensure `pytest` passes with coverage ≥ 80%
2. Run `bash .githooks/pre-push`
3. Screenshot the "Coverage OK" message

### mcp-interaction.png
1. Start `python mcp/server.py` in one terminal
2. In Claude Code, ask it to call `get_transaction_status("TXN001")` using the MCP tool
3. Screenshot showing the tool call and result JSON

---

*All screenshots should be in PNG format at ≥ 1280×720 resolution.*
