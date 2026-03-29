"""FastMCP server — pipeline-status.

Exposes the banking pipeline results directory to MCP clients:

Tools
-----
get_transaction_status(transaction_id)
    Returns the current status of a specific transaction from shared/results/.

list_pipeline_results()
    Returns a summary of all processed transactions.

Resources
---------
pipeline://summary
    Returns the latest pipeline_summary.json content as text.

Run with::

    python mcp/server.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Ensure project root is importable
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from common.io_utils import safe_stem
from common.paths import PIPELINE_SUMMARY, RESULTS_DIR

try:
    from fastmcp import FastMCP
except ImportError as exc:
    raise ImportError(
        "FastMCP is not installed. Install it with: pip install fastmcp"
    ) from exc

# ---------------------------------------------------------------------------
# Server setup
# ---------------------------------------------------------------------------

mcp = FastMCP("pipeline-status")


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------


@mcp.tool()
def get_transaction_status(transaction_id: str) -> str:
    """Return the processing status of a single transaction.

    Parameters
    ----------
    transaction_id:
        The transaction identifier, e.g. ``TXN001``.

    Returns
    -------
    str
        JSON string with the transaction result, or an error message.
    """
    try:
        safe_stem(transaction_id)
    except ValueError:
        return json.dumps({"error": "Invalid transaction_id: must be alphanumeric/hyphens/underscores only."})
    path = RESULTS_DIR / f"{transaction_id}.json"
    if not path.exists():
        return json.dumps({"error": f"Transaction not found in shared/results/"})
    data = json.loads(path.read_text(encoding="utf-8"))
    return json.dumps(data, indent=2)


@mcp.tool()
def list_pipeline_results() -> str:
    """Return a summary of all transactions that have been processed.

    Returns
    -------
    str
        JSON string with a list of result records (transaction_id, status,
        fraud_risk_level, amount, currency).
    """
    result_files = sorted(RESULTS_DIR.glob("TXN*.json"))
    records = []
    for p in result_files:
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
            records.append(
                {
                    "transaction_id": data.get("transaction_id"),
                    "status": data.get("status"),
                    "fraud_risk_level": data.get("fraud_risk_level"),
                    "amount": data.get("amount"),
                    "currency": data.get("currency"),
                    "rejection_reason": data.get("rejection_reason"),
                }
            )
        except (json.JSONDecodeError, OSError):
            continue

    return json.dumps({"transactions": records, "count": len(records)}, indent=2)


# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------


@mcp.resource("pipeline://summary")
def pipeline_summary() -> str:
    """Return the latest pipeline run summary as a JSON text string.

    Returns the content of ``shared/results/pipeline_summary.json``, or an
    informative message if no pipeline run has been executed yet.
    """
    if not PIPELINE_SUMMARY.exists():
        return (
            "No pipeline summary found. "
            "Run the pipeline first with: python integrator.py"
        )
    return PIPELINE_SUMMARY.read_text(encoding="utf-8")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    mcp.run()
