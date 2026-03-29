"""Audit logging for the banking pipeline.

All entries are written with ISO 8601 timestamps and never contain plaintext
account numbers or customer names.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _iso_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


class AuditLogger:
    """Structured audit logger that writes newline-delimited JSON records.

    Parameters
    ----------
    agent_name:
        Name of the owning agent; included in every log entry.
    log_path:
        File to append audit records to.  Parent directories must exist.
    also_stderr:
        When *True* a human-readable summary is also emitted to stderr.
    """

    def __init__(
        self,
        agent_name: str,
        log_path: Path | None = None,
        also_stderr: bool = True,
    ) -> None:
        self.agent_name = agent_name
        self.log_path = log_path
        self._stderr = also_stderr

        # Configure stdlib logger for human-readable output
        self._logger = logging.getLogger(f"pipeline.{agent_name}")
        if not self._logger.handlers:
            handler = logging.StreamHandler(sys.stderr)
            handler.setFormatter(
                logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
            )
            self._logger.addHandler(handler)
            self._logger.setLevel(logging.DEBUG)
            self._logger.propagate = False

    def log(
        self,
        transaction_id: str,
        outcome: str,
        details: dict[str, Any] | None = None,
        level: str = "INFO",
    ) -> None:
        """Write a structured audit entry.

        Parameters
        ----------
        transaction_id:
            Identifier of the transaction being processed.
        outcome:
            Short outcome string (e.g. ``"validated"``, ``"rejected"``).
        details:
            Optional extra context.  Must NOT contain plaintext account numbers.
        level:
            Log level string (``"INFO"``, ``"WARNING"``, ``"ERROR"``).
        """
        record: dict[str, Any] = {
            "timestamp": _iso_now(),
            "agent": self.agent_name,
            "transaction_id": transaction_id,
            "outcome": outcome,
        }
        if details:
            record["details"] = details

        # Write to file
        if self.log_path is not None:
            try:
                with self.log_path.open("a", encoding="utf-8") as fh:
                    fh.write(json.dumps(record) + "\n")
            except OSError as exc:
                # Non-fatal: don't crash the pipeline, but warn so the failure
                # isn't silently ignored during troubleshooting.
                print(f"[audit] WARNING: could not write to {self.log_path}: {exc}", file=sys.stderr)

        # Human-readable stderr
        if self._stderr:
            msg = f"txn={transaction_id} outcome={outcome}"
            if details:
                msg += f" details={json.dumps(details)}"
            getattr(self._logger, level.lower(), self._logger.info)(msg)
