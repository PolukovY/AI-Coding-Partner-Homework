# Research Notes — context7 Queries

**Author:** Yevgen Levik
**Project:** Homework 6 — AI-Powered Multi-Agent Banking Pipeline

These notes document the context7 queries made during development of this project.
context7 was used to retrieve up-to-date documentation and canonical code patterns
for the Python libraries used in this pipeline.

---

## Query 1: Python `decimal` Module — Monetary Arithmetic

- **Search query:** `Python decimal module monetary arithmetic ROUND_HALF_UP`
- **context7 library ID:** `/python/decimal`
- **Resolved docs URL:** `https://docs.python.org/3/library/decimal.html`

### Key Insights Applied

context7 confirmed that the correct pattern for parsing externally-sourced monetary
strings is `Decimal(str(raw_value))` — converting via `str()` first prevents the
floating-point precision loss that would occur with `Decimal(float(raw_value))`.

```python
# Correct — avoids float precision loss
from decimal import Decimal
amount = Decimal(str("1500.00"))   # Decimal('1500.00')

# WRONG — introduces float rounding errors
amount = Decimal(1500.0)           # Decimal('1500')
amount = Decimal(float("1500.00")) # May introduce precision errors
```

The docs also showed that `Decimal("0")` is the correct comparator for positivity
checks rather than `0` (int), since `Decimal.__gt__(int)` is supported but
explicit Decimal comparison is clearer:

```python
if amount <= Decimal("0"):
    raise ValueError("Amount must be positive")
```

**Applied in:** `agents/transaction_validator.py` — `validate_transaction()` function
uses `Decimal(str(transaction["amount"]))` and compares with `Decimal("0")`.

---

## Query 2: `pytest-cov` — Coverage Configuration and Failure Thresholds

- **Search query:** `pytest-cov coverage configuration fail-under threshold pytest.ini`
- **context7 library ID:** `/pytest-dev/pytest-cov`
- **Resolved docs URL:** `https://pytest-cov.readthedocs.io/en/latest/config.html`

### Key Insights Applied

context7 showed the canonical way to configure pytest-cov in `pytest.ini` using
the `addopts` key so coverage runs automatically without extra CLI flags:

```ini
[pytest]
testpaths = tests
addopts =
    --cov=agents
    --cov=common
    --cov=integrator
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-fail-under=80
```

The `--cov-fail-under=N` flag makes pytest exit with code 2 if coverage is below
the threshold, enabling the pre-push hook to gate on the exit code:

```bash
python -m pytest ...
if [ $? -ne 0 ]; then
    echo "Coverage below threshold — push blocked"
    exit 1
fi
```

**Applied in:** `pytest.ini` uses `--cov-fail-under=80`; `scripts/check_coverage.py`
and `.githooks/pre-push` use the pytest exit code as the coverage gate.

---

## Query 3: FastMCP — Tool and Resource Patterns

- **Search query:** `FastMCP tool resource decorator Python MCP server`
- **context7 library ID:** `/jlowin/fastmcp`
- **Resolved docs URL:** `https://gofastmcp.com/getting-started/welcome`

### Key Insights Applied

context7 showed the minimal FastMCP server pattern using `@mcp.tool()` and
`@mcp.resource()` decorators:

```python
from mcp.server.fastmcp import FastMCP

mcp = FastMCP("my-server")

@mcp.tool()
def get_status(transaction_id: str) -> str:
    """Return the status of a transaction."""
    ...

@mcp.resource("pipeline://summary")
def pipeline_summary() -> str:
    """Return the pipeline summary."""
    ...

if __name__ == "__main__":
    mcp.run()
```

The key insight was that tools return plain Python types (str, dict, list) which
FastMCP automatically serialises; resources use URI scheme strings as identifiers
and are exposed as readable text/data endpoints.

**Applied in:** `mcp/server.py` — `get_transaction_status()` and
`list_pipeline_results()` tools, and `pipeline://summary` resource.
