"""Reporting Agent.

Accepts fraud-scored transactions, writes per-transaction result files to
``shared/results/``, and builds the pipeline summary JSON.
"""

from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from common.audit import AuditLogger
from common.io_utils import list_messages, load_message, save_message
from common.masking import mask_account
from common.message import PipelineMessage
from common.paths import (
    AUDIT_LOG,
    OUTPUT_DIR,
    PIPELINE_SUMMARY,
    PROCESSING_DIR,
    RESULTS_DIR,
)

AGENT_NAME = "reporting_agent"


# ---------------------------------------------------------------------------
# Core reporting logic
# ---------------------------------------------------------------------------


def produce_result(transaction: dict[str, Any]) -> dict[str, Any]:
    """Build the final result record for a fraud-scored transaction.

    This is the canonical shape stored in ``shared/results/<TXN_ID>.json``.
    """
    return {
        "transaction_id": transaction.get("transaction_id", "UNKNOWN"),
        "status": transaction.get("status", "processed"),
        "amount": transaction.get("amount"),
        "currency": transaction.get("currency"),
        "transaction_type": transaction.get("transaction_type"),
        "fraud_risk_score": transaction.get("fraud_risk_score"),
        "fraud_risk_level": transaction.get("fraud_risk_level"),
        "fraud_flags": transaction.get("fraud_flags", []),
        "rejection_reason": transaction.get("rejection_reason"),
        "rejection_detail": transaction.get("rejection_detail"),
        "processed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


def build_summary(results: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate *results* into a pipeline summary dict.

    Parameters
    ----------
    results:
        List of result records produced by :func:`produce_result`.

    Returns
    -------
    dict
        Summary with counts per status and fraud level.
    """
    validated = sum(1 for r in results if r.get("status") == "validated")
    rejected = sum(1 for r in results if r.get("status") == "rejected")

    fraud_low = sum(1 for r in results if r.get("fraud_risk_level") == "LOW")
    fraud_medium = sum(1 for r in results if r.get("fraud_risk_level") == "MEDIUM")
    fraud_high = sum(1 for r in results if r.get("fraud_risk_level") == "HIGH")

    return {
        "total_transactions": len(results),
        "validated_count": validated,
        "rejected_count": rejected,
        "fraud_low_count": fraud_low,
        "fraud_medium_count": fraud_medium,
        "fraud_high_count": fraud_high,
        "processed_at": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }


# ---------------------------------------------------------------------------
# Agent process_message — file-based pipeline interface
# ---------------------------------------------------------------------------


def process_message(message: PipelineMessage, audit: AuditLogger) -> dict[str, Any]:
    """Produce the final result record from a fraud-scored *message*."""
    txn = message.data
    result = produce_result(txn)
    txn_id = result["transaction_id"]

    audit.log(
        transaction_id=txn_id,
        outcome="reported",
        details={
            "source_account": mask_account(txn.get("source_account", "")),
            "fraud_risk_level": result.get("fraud_risk_level"),
        },
    )
    return result


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


def run(
    input_dir: Path = OUTPUT_DIR,
    processing_dir: Path = PROCESSING_DIR,
    results_dir: Path = RESULTS_DIR,
    summary_path: Path = PIPELINE_SUMMARY,
    audit_log: Path = AUDIT_LOG,
    all_results: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Process all fraud-scored messages in *input_dir*.

    Parameters
    ----------
    all_results:
        Optional list of previously-processed result records (e.g. rejected
        transactions from the validator stage) to include in the summary.

    Returns
    -------
    dict
        The pipeline summary.
    """
    audit = AuditLogger(AGENT_NAME, audit_log)
    collected: list[dict[str, Any]] = list(all_results or [])

    for msg_path in list_messages(input_dir):
        proc_path = processing_dir / msg_path.name
        msg_path.replace(proc_path)

        msg = load_message(proc_path)
        result = process_message(msg, audit)
        collected.append(result)

        # Write per-transaction result file
        txn_id = result["transaction_id"]
        out_path = results_dir / f"{txn_id}.json"
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    summary = build_summary(collected)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    audit.log(
        transaction_id="PIPELINE",
        outcome="summary_written",
        details={"summary": summary},
    )
    return summary


if __name__ == "__main__":
    run()
