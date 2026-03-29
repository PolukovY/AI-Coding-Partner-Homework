"""Transaction Validator Agent.

Validates raw transaction records against required fields, type constraints,
and ISO 4217 currency codes.  Produces ``validated`` or ``rejected`` messages.

Can also be run in *dry-run* mode (``--dry-run`` CLI flag) to report
validation results without writing to the shared directory.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Ensure project root is importable when running this file directly
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from common.audit import AuditLogger
from common.io_utils import list_messages, load_message, save_message
from common.masking import mask_account
from common.message import PipelineMessage
from common.paths import AUDIT_LOG, INPUT_DIR, PROCESSING_DIR, OUTPUT_DIR, RESULTS_DIR

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "transaction_validator"

# Minimum ISO 4217 whitelist required by the specification
VALID_CURRENCIES: frozenset[str] = frozenset(
    {"USD", "EUR", "GBP", "JPY", "CHF", "CAD", "AUD", "NZD", "SEK", "NOK", "DKK"}
)

REQUIRED_FIELDS: tuple[str, ...] = (
    "transaction_id",
    "timestamp",
    "source_account",
    "destination_account",
    "amount",
    "currency",
    "transaction_type",
    "metadata",
)

# Reason codes
REASON_MISSING_FIELDS = "MISSING_REQUIRED_FIELDS"
REASON_INVALID_AMOUNT = "INVALID_AMOUNT"
REASON_NON_POSITIVE_AMOUNT = "NON_POSITIVE_AMOUNT"
REASON_INVALID_CURRENCY = "INVALID_CURRENCY"


# ---------------------------------------------------------------------------
# Core validation logic
# ---------------------------------------------------------------------------


def validate_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    """Validate a single raw transaction record.

    Parameters
    ----------
    transaction:
        Raw dictionary loaded from ``sample-transactions.json``.

    Returns
    -------
    dict
        A result dict with keys:
        - ``transaction_id`` — copied from input (or ``"UNKNOWN"``).
        - ``status`` — ``"validated"`` or ``"rejected"``.
        - ``rejection_reason`` — reason code string if rejected, else ``None``.
        - ``rejection_detail`` — human-readable detail if rejected, else ``None``.
        - ``data`` — the original transaction data (for downstream agents).
    """
    txn_id: str = transaction.get("transaction_id", "UNKNOWN")

    # 1. Required fields
    missing = [f for f in REQUIRED_FIELDS if f not in transaction]
    if missing:
        return _rejected(txn_id, transaction, REASON_MISSING_FIELDS, f"Missing: {missing}")

    # 2. Amount must parse as Decimal
    try:
        amount = Decimal(str(transaction["amount"]))
    except InvalidOperation:
        return _rejected(
            txn_id, transaction, REASON_INVALID_AMOUNT,
            f"Cannot parse amount: {transaction['amount']!r}"
        )

    # 3. Amount must be positive
    if amount <= Decimal("0"):
        return _rejected(
            txn_id, transaction, REASON_NON_POSITIVE_AMOUNT,
            f"Amount must be positive, got {amount}"
        )

    # 4. Currency must be in ISO 4217 whitelist
    currency: str = str(transaction["currency"]).upper()
    if currency not in VALID_CURRENCIES:
        return _rejected(
            txn_id, transaction, REASON_INVALID_CURRENCY,
            f"Currency {currency!r} not in whitelist {sorted(VALID_CURRENCIES)}"
        )

    return {
        "transaction_id": txn_id,
        "status": "validated",
        "rejection_reason": None,
        "rejection_detail": None,
        "data": {**transaction, "amount": str(amount), "currency": currency},
    }


def _rejected(
    txn_id: str,
    transaction: dict[str, Any],
    reason: str,
    detail: str,
) -> dict[str, Any]:
    return {
        "transaction_id": txn_id,
        "status": "rejected",
        "rejection_reason": reason,
        "rejection_detail": detail,
        "data": transaction,
    }


# ---------------------------------------------------------------------------
# Agent process_message — file-based pipeline interface
# ---------------------------------------------------------------------------


def process_message(message: PipelineMessage, audit: AuditLogger) -> PipelineMessage:
    """Validate the transaction contained in *message* and return the result message."""
    txn = message.data
    result = validate_transaction(txn)
    txn_id = result["transaction_id"]

    outcome_data: dict[str, Any] = {
        **result["data"],
        "status": result["status"],
    }
    if result["rejection_reason"]:
        outcome_data["rejection_reason"] = result["rejection_reason"]
        outcome_data["rejection_detail"] = result["rejection_detail"]

    target = "fraud_detector" if result["status"] == "validated" else "results"

    audit.log(
        transaction_id=txn_id,
        outcome=result["status"],
        details={
            "source_account": mask_account(txn.get("source_account", "")),
            "reason": result.get("rejection_reason"),
        },
    )

    return PipelineMessage(
        source_agent=AGENT_NAME,
        target_agent=target,
        message_type="transaction",
        data=outcome_data,
    )


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


def run(
    input_dir: Path = INPUT_DIR,
    processing_dir: Path = PROCESSING_DIR,
    output_dir: Path = OUTPUT_DIR,
    results_dir: Path = RESULTS_DIR,
    audit_log: Path = AUDIT_LOG,
) -> list[dict[str, Any]]:
    """Process all messages in *input_dir*.

    Returns a list of result dicts (one per transaction).
    """
    audit = AuditLogger(AGENT_NAME, audit_log)
    results: list[dict[str, Any]] = []

    for msg_path in list_messages(input_dir):
        # Move to processing
        proc_path = processing_dir / msg_path.name
        msg_path.replace(proc_path)

        msg = load_message(proc_path)
        out_msg = process_message(msg, audit)

        # Rejected → results; validated → output (next agent)
        if out_msg.target_agent == "results":
            save_message(out_msg, results_dir, out_msg.data["transaction_id"])
        else:
            save_message(out_msg, output_dir, out_msg.data["transaction_id"])

        results.append(out_msg.data)

    return results


# ---------------------------------------------------------------------------
# CLI — dry-run support
# ---------------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description="Transaction Validator — validate transactions without full pipeline."
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate sample-transactions.json and report results without writing files.",
    )
    p.add_argument(
        "--input",
        default=str(_PROJECT_ROOT / "sample-transactions.json"),
        help="Path to the JSON file containing raw transactions.",
    )
    return p


def main() -> None:
    args = _build_parser().parse_args()

    if args.dry_run:
        _dry_run(Path(args.input))
    else:
        run()


def _dry_run(source: Path) -> None:
    """Validate all transactions in *source* and print a report to stdout."""
    if not source.exists():
        print(f"Error: file not found: {source}", file=sys.stderr)
        sys.exit(1)
    raw = json.loads(source.read_text(encoding="utf-8"))
    results = [validate_transaction(t) for t in raw]

    total = len(results)
    valid = sum(1 for r in results if r["status"] == "validated")
    invalid = total - valid

    print(f"\nDry-run validation report — {source.name}")
    print(f"{'='*60}")
    print(f"Total      : {total}")
    print(f"Valid      : {valid}")
    print(f"Invalid    : {invalid}")
    print(f"\n{'TXN ID':<10} {'STATUS':<12} {'REASON'}")
    print(f"{'-'*60}")
    for r in results:
        reason = r["rejection_reason"] or "-"
        print(f"{r['transaction_id']:<10} {r['status']:<12} {reason}")
    print()


if __name__ == "__main__":
    main()
