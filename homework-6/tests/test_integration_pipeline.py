"""Integration tests for the full banking pipeline.

These tests run the entire pipeline (validator → fraud detector → reporting)
against isolated tmp directories and the real sample-transactions.json.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from integrator import run_pipeline, _prepare_directories, _seed_input, _load_sample_transactions, _print_summary
from common.paths import (
    INPUT_DIR,
    OUTPUT_DIR,
    PROCESSING_DIR,
    RESULTS_DIR,
    PIPELINE_SUMMARY,
    SAMPLE_TRANSACTIONS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_DATA = [
    {
        "transaction_id": "ITXN001",
        "timestamp": "2026-03-16T09:00:00Z",
        "source_account": "ACC-1001",
        "destination_account": "ACC-2001",
        "amount": "1500.00",
        "currency": "USD",
        "transaction_type": "transfer",
        "description": "Test payment",
        "metadata": {"channel": "online", "country": "US"},
    },
    {
        "transaction_id": "ITXN002",
        "timestamp": "2026-03-16T09:15:00Z",
        "source_account": "ACC-1002",
        "destination_account": "ACC-3001",
        "amount": "25000.00",
        "currency": "USD",
        "transaction_type": "wire_transfer",
        "description": "High-value wire",
        "metadata": {"channel": "branch", "country": "US"},
    },
    {
        "transaction_id": "ITXN003",
        "timestamp": "2026-03-16T10:05:00Z",
        "source_account": "ACC-1006",
        "destination_account": "ACC-7700",
        "amount": "200.00",
        "currency": "XYZ",   # invalid — should be rejected
        "transaction_type": "transfer",
        "description": "Invalid currency",
        "metadata": {"channel": "online", "country": "US"},
    },
]


# ---------------------------------------------------------------------------
# Integration test: mini pipeline with isolated dirs
# ---------------------------------------------------------------------------

class TestFullPipelineIsolated:
    """Run a mini pipeline using tmp_path so real shared/ is untouched."""

    def _run_mini_pipeline(self, tmp_path, transactions):
        """Execute the three agent stages with isolated tmp directories."""
        input_dir = tmp_path / "input"
        processing_dir = tmp_path / "processing"
        output_dir = tmp_path / "output"
        results_dir = tmp_path / "results"
        audit_log = tmp_path / "audit.log"
        summary_path = tmp_path / "pipeline_summary.json"
        for d in (input_dir, processing_dir, output_dir, results_dir):
            d.mkdir()

        # Seed
        from common.io_utils import save_message
        from common.message import PipelineMessage
        for txn in transactions:
            msg = PipelineMessage(
                source_agent="orchestrator",
                target_agent="transaction_validator",
                message_type="transaction",
                data=txn,
            )
            save_message(msg, input_dir, txn["transaction_id"])

        # Stage 1: Validator
        import agents.transaction_validator as v
        v_results = v.run(
            input_dir=input_dir,
            processing_dir=processing_dir,
            output_dir=output_dir,
            results_dir=results_dir,
            audit_log=audit_log,
        )

        validated = [r for r in v_results if r.get("status") == "validated"]
        rejected = [r for r in v_results if r.get("status") == "rejected"]

        # Stage 2: Fraud detector — reads from output_dir
        import agents.fraud_detector as f
        f_results = f.run(
            input_dir=output_dir,
            processing_dir=processing_dir,
            output_dir=results_dir,
            audit_log=audit_log,
        )

        # Stage 3: Reporting — reads ALL messages from results_dir
        # (both fraud-scored PipelineMessages and rejected PipelineMessages
        #  written by the validator)
        import agents.reporting_agent as r

        summary = r.run(
            input_dir=results_dir,
            processing_dir=processing_dir,
            results_dir=results_dir,
            summary_path=summary_path,
            audit_log=audit_log,
            all_results=None,
        )
        return v_results, f_results, summary, results_dir, summary_path

    def test_all_transactions_end_in_results(self, tmp_path):
        _, _, summary, results_dir, _ = self._run_mini_pipeline(tmp_path, SAMPLE_DATA)
        result_files = list(results_dir.glob("ITXN*.json"))
        assert len(result_files) == len(SAMPLE_DATA)

    def test_invalid_currency_rejected(self, tmp_path):
        v_results, _, _, _, _ = self._run_mini_pipeline(tmp_path, SAMPLE_DATA)
        rejected = [r for r in v_results if r.get("status") == "rejected"]
        assert any(r["transaction_id"] == "ITXN003" for r in rejected)

    def test_high_value_wire_scored_medium_or_higher(self, tmp_path):
        _, f_results, _, _, _ = self._run_mini_pipeline(tmp_path, SAMPLE_DATA)
        txn002 = next((r for r in f_results if r["transaction_id"] == "ITXN002"), None)
        assert txn002 is not None
        assert txn002["fraud_risk_level"] in ("MEDIUM", "HIGH")

    def test_summary_totals_match_input(self, tmp_path):
        _, _, summary, _, _ = self._run_mini_pipeline(tmp_path, SAMPLE_DATA)
        assert summary["total_transactions"] == len(SAMPLE_DATA)
        assert summary["validated_count"] + summary["rejected_count"] == len(SAMPLE_DATA)

    def test_summary_json_written(self, tmp_path):
        _, _, _, _, summary_path = self._run_mini_pipeline(tmp_path, SAMPLE_DATA)
        assert summary_path.exists()
        data = json.loads(summary_path.read_text())
        assert "total_transactions" in data

    def test_audit_log_written(self, tmp_path):
        self._run_mini_pipeline(tmp_path, SAMPLE_DATA)
        audit_log = tmp_path / "audit.log"
        assert audit_log.exists()
        lines = [json.loads(l) for l in audit_log.read_text().splitlines() if l.strip()]
        assert len(lines) > 0


# ---------------------------------------------------------------------------
# Full pipeline against real sample-transactions.json
# ---------------------------------------------------------------------------

class TestFullPipelineWithSampleData:
    """Run the real integrator.run_pipeline() and verify the 8 sample transactions."""

    def test_run_pipeline_produces_8_results(self):
        """run_pipeline() using the actual shared/ dirs and real sample data."""
        summary = run_pipeline()
        result_files = list(RESULTS_DIR.glob("TXN*.json"))
        assert len(result_files) == 8

    def test_pipeline_summary_has_correct_totals(self):
        summary = run_pipeline()
        assert summary["total_transactions"] == 8
        assert summary["validated_count"] + summary["rejected_count"] == 8

    def test_txn006_and_txn007_are_rejected(self):
        run_pipeline()
        # TXN006 has invalid currency XYZ
        txn006_path = RESULTS_DIR / "TXN006.json"
        assert txn006_path.exists()
        data = json.loads(txn006_path.read_text())
        assert data["status"] == "rejected"

        # TXN007 has negative amount
        txn007_path = RESULTS_DIR / "TXN007.json"
        assert txn007_path.exists()
        data = json.loads(txn007_path.read_text())
        assert data["status"] == "rejected"

    def test_txn005_is_high_risk(self):
        run_pipeline()
        path = RESULTS_DIR / "TXN005.json"
        data = json.loads(path.read_text())
        assert data["fraud_risk_level"] == "HIGH"

    def test_pipeline_summary_json_exists(self):
        run_pipeline()
        assert PIPELINE_SUMMARY.exists()
        data = json.loads(PIPELINE_SUMMARY.read_text())
        assert data["total_transactions"] == 8


# ---------------------------------------------------------------------------
# _load_sample_transactions — error branch
# ---------------------------------------------------------------------------

class TestLoadSampleTransactions:
    def test_raises_on_non_list_json(self, tmp_path, monkeypatch):
        """_load_sample_transactions() must raise ValueError when JSON is not a list."""
        import common.paths as cp
        fake = tmp_path / "sample-transactions.json"
        fake.write_text(json.dumps({"not": "a list"}), encoding="utf-8")
        monkeypatch.setattr(cp, "SAMPLE_TRANSACTIONS", fake)
        # Reload the constant used inside integrator via monkeypatching the module attr
        import integrator as ig
        monkeypatch.setattr(ig, "SAMPLE_TRANSACTIONS", fake)
        # Re-import the function so it picks up the patched constant
        from integrator import _load_sample_transactions as load_fn
        with pytest.raises(ValueError, match="JSON array"):
            load_fn()


# ---------------------------------------------------------------------------
# _print_summary — output coverage
# ---------------------------------------------------------------------------

class TestPrintSummary:
    def test_prints_all_fields(self, capsys):
        summary = {
            "total_transactions": 8,
            "validated_count": 6,
            "rejected_count": 2,
            "fraud_low_count": 3,
            "fraud_medium_count": 2,
            "fraud_high_count": 1,
            "processed_at": "2026-03-29T12:00:00Z",
        }
        _print_summary(summary)
        out = capsys.readouterr().out
        assert "8" in out
        assert "6" in out
        assert "2026-03-29" in out
