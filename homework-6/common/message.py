"""Standard pipeline message schema.

All inter-agent communication uses the :class:`PipelineMessage` dataclass which
serialises to the canonical JSON envelope defined in the assignment.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class PipelineMessage:
    """A single message passed between pipeline agents.

    Attributes
    ----------
    message_id:
        Unique UUID-4 string generated at creation time.
    timestamp:
        ISO 8601 UTC string set at creation time.
    source_agent:
        Name of the agent that produced this message.
    target_agent:
        Name of the agent that should consume this message.
    message_type:
        Logical type of the payload (e.g. ``"transaction"``).
    data:
        Arbitrary key/value payload; monetary amounts must be strings
        representing :class:`decimal.Decimal` values.
    """

    source_agent: str
    target_agent: str
    message_type: str
    data: dict[str, Any]
    message_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )

    # ------------------------------------------------------------------
    # Serialisation helpers
    # ------------------------------------------------------------------

    def to_dict(self) -> dict[str, Any]:
        """Return the message as a plain dictionary."""
        return asdict(self)

    def to_json(self, indent: int = 2) -> str:
        """Serialise the message to a JSON string."""
        return json.dumps(self.to_dict(), indent=indent)

    def save(self, path: Path) -> None:
        """Write the message as a JSON file at *path*."""
        path.write_text(self.to_json(), encoding="utf-8")

    # ------------------------------------------------------------------
    # Deserialisation helpers
    # ------------------------------------------------------------------

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "PipelineMessage":
        """Reconstruct a :class:`PipelineMessage` from a dictionary."""
        return cls(
            message_id=d["message_id"],
            timestamp=d["timestamp"],
            source_agent=d["source_agent"],
            target_agent=d["target_agent"],
            message_type=d["message_type"],
            data=d["data"],
        )

    @classmethod
    def load(cls, path: Path) -> "PipelineMessage":
        """Load a :class:`PipelineMessage` from a JSON file."""
        raw = json.loads(path.read_text(encoding="utf-8"))
        return cls.from_dict(raw)
