"""File-system I/O helpers for moving messages between pipeline stages."""

from __future__ import annotations

import re
import shutil
from pathlib import Path

from common.message import PipelineMessage

# Only allow safe filename stems: alphanumerics, hyphens, underscores, dots.
# This blocks path-traversal payloads like "../../etc/passwd".
_SAFE_STEM_RE = re.compile(r"^[A-Za-z0-9_\-\.]+$")


def safe_stem(value: str) -> str:
    """Return *value* if it is a safe filename stem, else raise ValueError.

    Raises
    ------
    ValueError
        If *value* contains path-separators or other unsafe characters.
    """
    if not _SAFE_STEM_RE.match(value):
        raise ValueError(
            f"Unsafe filename stem {value!r}: only alphanumerics, hyphens, "
            "underscores, and dots are allowed."
        )
    return value


def list_messages(directory: Path) -> list[Path]:
    """Return all ``.json`` files in *directory*, sorted by name."""
    return sorted(directory.glob("*.json"))


def move_message(src: Path, dest_dir: Path) -> Path:
    """Move a message file from *src* to *dest_dir*.

    Returns the new path.
    """
    dest = dest_dir / src.name
    shutil.move(str(src), str(dest))
    return dest


def load_message(path: Path) -> PipelineMessage:
    """Load and return a :class:`~common.message.PipelineMessage` from *path*."""
    return PipelineMessage.load(path)


def save_message(message: PipelineMessage, directory: Path, filename: str | None = None) -> Path:
    """Serialise *message* into *directory*.

    If *filename* is not given the transaction_id is used as the stem.

    Raises
    ------
    ValueError
        If the resolved filename stem contains unsafe characters (path traversal guard).
    """
    stem = filename or message.data.get("transaction_id", message.message_id)
    safe_stem(stem)  # raises ValueError on path-traversal attempt
    path = directory / f"{stem}.json"
    message.save(path)
    return path


def clear_directory(directory: Path) -> None:
    """Remove all ``.json`` files inside *directory* (non-recursive)."""
    for f in directory.glob("*.json"):
        f.unlink()
