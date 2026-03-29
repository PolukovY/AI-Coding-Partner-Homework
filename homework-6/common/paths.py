"""Canonical path definitions for the pipeline's shared directory structure."""

from pathlib import Path

# Root of the homework-6 project
PROJECT_ROOT: Path = Path(__file__).parent.parent

# Shared communication directories used by all agents
SHARED_DIR: Path = PROJECT_ROOT / "shared"
INPUT_DIR: Path = SHARED_DIR / "input"
PROCESSING_DIR: Path = SHARED_DIR / "processing"
OUTPUT_DIR: Path = SHARED_DIR / "output"
RESULTS_DIR: Path = SHARED_DIR / "results"

# Logs
LOGS_DIR: Path = PROJECT_ROOT / "logs"
AUDIT_LOG: Path = RESULTS_DIR / "audit.log"

# Source data
SAMPLE_TRANSACTIONS: Path = PROJECT_ROOT / "sample-transactions.json"

# Final summary
PIPELINE_SUMMARY: Path = RESULTS_DIR / "pipeline_summary.json"


def ensure_shared_dirs() -> None:
    """Create all shared directories, clearing existing message files."""
    for d in (INPUT_DIR, PROCESSING_DIR, OUTPUT_DIR, RESULTS_DIR, LOGS_DIR):
        d.mkdir(parents=True, exist_ok=True)
