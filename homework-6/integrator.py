"""Pipeline Orchestrator — integrator.py

Runs the full three-stage banking pipeline end-to-end:

  1. Transaction Validator  (shared/input/ → shared/output/)
  2. Fraud Detector         (shared/output/ → shared/results/  via processing/)
  3. Reporting Agent        (shared/results/ — aggregates, writes summary)

Usage::

    python integrator.py

All results land in ``shared/results/`` including ``pipeline_summary.json``.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure project root is on sys.path when run as a script
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from common.audit import AuditLogger
from common.io_utils import save_message
from common.message import PipelineMessage
from common.paths import (
    AUDIT_LOG,
    INPUT_DIR,
    OUTPUT_DIR,
    PIPELINE_SUMMARY,
    PROCESSING_DIR,
    RESULTS_DIR,
    SAMPLE_TRANSACTIONS,
    SHARED_DIR,
)

import agents.transaction_validator as validator_agent
import agents.fraud_detector as fraud_agent
import agents.reporting_agent as reporting_agent

_ORCHESTRATOR_LOG = AuditLogger("orchestrator", also_stderr=True)


# ---------------------------------------------------------------------------
# Directory management
# ---------------------------------------------------------------------------


def _prepare_directories() -> None:
    """Create and clear all shared pipeline directories."""
    for d in (INPUT_DIR, PROCESSING_DIR, OUTPUT_DIR, RESULTS_DIR):
        d.mkdir(parents=True, exist_ok=True)
        # Remove stale message files from a previous run
        for f in d.glob("*.json"):
            f.unlink()
    # Ensure logs directory exists
    AUDIT_LOG.parent.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# Stage helpers
# ---------------------------------------------------------------------------


def _load_sample_transactions() -> list[dict[str, Any]]:
    """Load raw transactions from sample-transactions.json."""
    raw = json.loads(SAMPLE_TRANSACTIONS.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("sample-transactions.json must contain a JSON array.")
    return raw


def _seed_input(transactions: list[dict[str, Any]]) -> None:
    """Write each raw transaction as an initial PipelineMessage into shared/input/."""
    for txn in transactions:
        msg = PipelineMessage(
            source_agent="orchestrator",
            target_agent="transaction_validator",
            message_type="transaction",
            data=txn,
        )
        save_message(msg, INPUT_DIR, txn.get("transaction_id", msg.message_id))

    _ORCHESTRATOR_LOG.log(
        "PIPELINE", "seeded", {"count": len(transactions)}
    )


def _run_validator() -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Run the Transaction Validator stage.

    Returns
    -------
    tuple
        (validated_results, rejected_results) — both from the validator output.
    """
    results = validator_agent.run(
        input_dir=INPUT_DIR,
        processing_dir=PROCESSING_DIR,
        output_dir=OUTPUT_DIR,
        results_dir=RESULTS_DIR,
        audit_log=AUDIT_LOG,
    )
    validated = [r for r in results if r.get("status") == "validated"]
    rejected = [r for r in results if r.get("status") == "rejected"]
    _ORCHESTRATOR_LOG.log(
        "PIPELINE",
        "validation_complete",
        {"validated": len(validated), "rejected": len(rejected)},
    )
    return validated, rejected


def _run_fraud_detector() -> list[dict[str, Any]]:
    """Run the Fraud Detector on messages in shared/output/."""
    results = fraud_agent.run(
        input_dir=OUTPUT_DIR,
        processing_dir=PROCESSING_DIR,
        output_dir=RESULTS_DIR,
        audit_log=AUDIT_LOG,
    )
    _ORCHESTRATOR_LOG.log("PIPELINE", "fraud_detection_complete", {"count": len(results)})
    return results


def _run_reporting() -> dict[str, Any]:
    """Run the Reporting Agent to produce per-transaction files and a summary.

    RESULTS_DIR at this point contains:
    - Rejected PipelineMessages written by the validator
    - Fraud-scored PipelineMessages written by the fraud detector

    The reporting agent reads all of them, converts to canonical result records,
    and writes the final JSON files plus the summary.
    """
    summary = reporting_agent.run(
        input_dir=RESULTS_DIR,
        processing_dir=PROCESSING_DIR,
        results_dir=RESULTS_DIR,
        summary_path=PIPELINE_SUMMARY,
        audit_log=AUDIT_LOG,
        all_results=None,
    )
    return summary


# ---------------------------------------------------------------------------
# Public API / main
# ---------------------------------------------------------------------------


def run_pipeline() -> dict[str, Any]:
    """Execute the full pipeline and return the summary dict."""
    print("\n" + "=" * 60)
    print("  AI-Powered Banking Pipeline — Orchestrator")
    print("=" * 60)

    print("\n[1/5] Preparing directories …")
    _prepare_directories()

    print("[2/5] Loading sample transactions …")
    transactions = _load_sample_transactions()
    print(f"      Loaded {len(transactions)} transactions.")

    print("[3/5] Seeding shared/input/ …")
    _seed_input(transactions)

    print("[4/5] Running Transaction Validator …")
    validated, rejected = _run_validator()
    print(f"      Validated: {len(validated)}  Rejected: {len(rejected)}")

    print("[4b/5] Running Fraud Detector …")
    fraud_results = _run_fraud_detector()
    print(f"       Scored:   {len(fraud_results)}")

    print("[5/5] Running Reporting Agent …")
    summary = _run_reporting()

    _print_summary(summary)
    return summary


def _print_summary(summary: dict[str, Any]) -> None:
    print("\n" + "=" * 60)
    print("  Pipeline Summary")
    print("=" * 60)
    print(f"  Total transactions : {summary['total_transactions']}")
    print(f"  Validated          : {summary['validated_count']}")
    print(f"  Rejected           : {summary['rejected_count']}")
    print(f"  Fraud LOW          : {summary['fraud_low_count']}")
    print(f"  Fraud MEDIUM       : {summary['fraud_medium_count']}")
    print(f"  Fraud HIGH         : {summary['fraud_high_count']}")
    print(f"  Processed at       : {summary['processed_at']}")

    print(f"\n  Results written to : {RESULTS_DIR}")
    print(f"  Summary file       : {PIPELINE_SUMMARY}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run_pipeline()
