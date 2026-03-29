"""Fraud Detector Agent.

Scores each validated transaction on a 0–10 fraud-risk scale using a
deterministic rule set.  Appends ``fraud_risk_score``, ``fraud_risk_level``,
and ``fraud_flags`` to the message data.
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from common.audit import AuditLogger
from common.io_utils import list_messages, load_message, save_message
from common.masking import mask_account
from common.message import PipelineMessage
from common.paths import AUDIT_LOG, OUTPUT_DIR, PROCESSING_DIR, RESULTS_DIR

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

AGENT_NAME = "fraud_detector"

# Risk level thresholds
RISK_LOW_MAX = 2
RISK_MEDIUM_MAX = 6

# Scoring rules
THRESHOLD_HIGH_VALUE = Decimal("10000")
SCORE_HIGH_VALUE = 3

THRESHOLD_VERY_HIGH_VALUE = Decimal("50000")
SCORE_VERY_HIGH_VALUE = 4  # cumulative with SCORE_HIGH_VALUE

UNUSUAL_HOUR_START = 2   # 02:00 UTC inclusive
UNUSUAL_HOUR_END = 5     # 05:59 UTC inclusive
SCORE_UNUSUAL_HOUR = 2

US_COUNTRY = "US"
SCORE_CROSS_BORDER = 1

WIRE_TRANSFER_TYPE = "wire_transfer"
SCORE_WIRE_TRANSFER = 1


# ---------------------------------------------------------------------------
# Core scoring logic
# ---------------------------------------------------------------------------


def score_transaction(transaction: dict[str, Any]) -> dict[str, Any]:
    """Compute a fraud risk score for a validated *transaction*.

    Parameters
    ----------
    transaction:
        A transaction dict that has already passed validation (amount is a
        positive Decimal-compatible string, currency is valid).

    Returns
    -------
    dict
        Updated copy of *transaction* with three new keys:
        - ``fraud_risk_score``: int in 0–10
        - ``fraud_risk_level``: ``"LOW"``, ``"MEDIUM"``, or ``"HIGH"``
        - ``fraud_flags``: list of rule names that fired
    """
    score = 0
    flags: list[str] = []

    amount = Decimal(str(transaction.get("amount", "0")))
    metadata = transaction.get("metadata", {})
    country = str(metadata.get("country", "US")).upper()
    txn_type = str(transaction.get("transaction_type", "")).lower()
    timestamp_str = str(transaction.get("timestamp", ""))

    # Rule 1 & 2: high-value amounts
    if amount > THRESHOLD_VERY_HIGH_VALUE:
        # Add both thresholds cumulatively
        score += SCORE_HIGH_VALUE + SCORE_VERY_HIGH_VALUE
        flags.append("AMOUNT_VERY_HIGH")
    elif amount > THRESHOLD_HIGH_VALUE:
        score += SCORE_HIGH_VALUE
        flags.append("AMOUNT_HIGH")

    # Rule 3: unusual hour (02:00–05:59 UTC)
    hour = _parse_hour_utc(timestamp_str)
    if hour is not None and UNUSUAL_HOUR_START <= hour <= UNUSUAL_HOUR_END:
        score += SCORE_UNUSUAL_HOUR
        flags.append("UNUSUAL_HOUR")

    # Rule 4: cross-border (non-US country)
    if country != US_COUNTRY:
        score += SCORE_CROSS_BORDER
        flags.append("CROSS_BORDER")

    # Rule 5: wire transfer
    if txn_type == WIRE_TRANSFER_TYPE:
        score += SCORE_WIRE_TRANSFER
        flags.append("WIRE_TRANSFER")

    # Cap at 10
    score = min(score, 10)

    level = _risk_level(score)

    return {
        **transaction,
        "fraud_risk_score": score,
        "fraud_risk_level": level,
        "fraud_flags": flags,
    }


def _parse_hour_utc(timestamp: str) -> int | None:
    """Extract the UTC hour from an ISO 8601 timestamp string.

    Returns *None* if the string cannot be parsed.
    """
    for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S+00:00", "%Y-%m-%dT%H:%M:%S"):
        try:
            dt = datetime.strptime(timestamp, fmt).replace(tzinfo=timezone.utc)
            return dt.hour
        except ValueError:
            continue
    return None


def _risk_level(score: int) -> str:
    if score <= RISK_LOW_MAX:
        return "LOW"
    if score <= RISK_MEDIUM_MAX:
        return "MEDIUM"
    return "HIGH"


# ---------------------------------------------------------------------------
# Agent process_message — file-based pipeline interface
# ---------------------------------------------------------------------------


def process_message(message: PipelineMessage, audit: AuditLogger) -> PipelineMessage:
    """Score the fraud risk of the transaction in *message*."""
    txn = message.data
    scored = score_transaction(txn)
    txn_id = scored.get("transaction_id", "UNKNOWN")

    audit.log(
        transaction_id=txn_id,
        outcome=f"fraud_scored:{scored['fraud_risk_level']}",
        details={
            "source_account": mask_account(txn.get("source_account", "")),
            "score": scored["fraud_risk_score"],
            "flags": scored["fraud_flags"],
        },
    )

    return PipelineMessage(
        source_agent=AGENT_NAME,
        target_agent="reporting_agent",
        message_type="transaction",
        data=scored,
    )


# ---------------------------------------------------------------------------
# Agent runner
# ---------------------------------------------------------------------------


def run(
    input_dir: Path = OUTPUT_DIR,
    processing_dir: Path = PROCESSING_DIR,
    output_dir: Path = RESULTS_DIR,
    audit_log: Path = AUDIT_LOG,
) -> list[dict[str, Any]]:
    """Process all validated messages waiting in *input_dir*."""
    audit = AuditLogger(AGENT_NAME, audit_log)
    results: list[dict[str, Any]] = []

    for msg_path in list_messages(input_dir):
        proc_path = processing_dir / msg_path.name
        msg_path.replace(proc_path)

        msg = load_message(proc_path)
        out_msg = process_message(msg, audit)

        save_message(out_msg, output_dir, out_msg.data["transaction_id"])
        results.append(out_msg.data)

    return results


if __name__ == "__main__":
    run()
