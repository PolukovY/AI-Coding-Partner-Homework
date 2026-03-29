"""Unit tests for the Reporting Agent."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.reporting_agent import (
    build_summary,
    produce_result,
    process_message,
    run,
    AGENT_NAME,
)
from common.audit import AuditLogger
from common.message import PipelineMessage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def scored_txn() -> dict:
    return {
        "transaction_id": "TXN001",
        "timestamp": "2026-03-16T09:00:00Z",
        "source_account": "ACC-1001",
        "destination_account": "ACC-2001",
        "amount": "1500.00",
        "currency": "USD",
        "transaction_type": "transfer",
        "status": "validated",
        "fraud_risk_score": 0,
        "fraud_risk_level": "LOW",
        "fraud_flags": [],
        "rejection_reason": None,
        "rejection_detail": None,
        "metadata": {"channel": "online", "country": "US"},
    }


@pytest.fixture
def rejected_txn() -> dict:
    return {
        "transaction_id": "TXN006",
        "amount": "200.00",
        "currency": "XYZ",
        "transaction_type": "transfer",
        "status": "rejected",
        "fraud_risk_score": None,
        "fraud_risk_level": None,
        "fraud_flags": [],
        "rejection_reason": "INVALID_CURRENCY",
        "rejection_detail": "Currency 'XYZ' not in whitelist",
    }


@pytest.fixture
def audit(tmp_path) -> AuditLogger:
    return AuditLogger("test_reporting", tmp_path / "audit.log", also_stderr=False)


# ---------------------------------------------------------------------------
# produce_result
# ---------------------------------------------------------------------------

class TestProduceResult:
    def test_required_keys_present(self, scored_txn):
        result = produce_result(scored_txn)
        for key in (
            "transaction_id", "status", "amount", "currency",
            "transaction_type", "fraud_risk_score", "fraud_risk_level",
            "fraud_flags", "rejection_reason", "rejection_detail", "processed_at",
        ):
            assert key in result, f"Missing key: {key}"

    def test_transaction_id_preserved(self, scored_txn):
        result = produce_result(scored_txn)
        assert result["transaction_id"] == "TXN001"

    def test_processed_at_is_iso8601(self, scored_txn):
        result = produce_result(scored_txn)
        ts = result["processed_at"]
        # Simple check: starts with year and ends with Z
        assert ts[:4].isdigit()
        assert ts.endswith("Z")

    def test_rejected_transaction_preserved(self, rejected_txn):
        result = produce_result(rejected_txn)
        assert result["status"] == "rejected"
        assert result["rejection_reason"] == "INVALID_CURRENCY"

    def test_unknown_id_defaults(self):
        result = produce_result({})
        assert result["transaction_id"] == "UNKNOWN"

    def test_fraud_flags_is_list(self, scored_txn):
        result = produce_result(scored_txn)
        assert isinstance(result["fraud_flags"], list)


# ---------------------------------------------------------------------------
# build_summary
# ---------------------------------------------------------------------------

class TestBuildSummary:
    def _make_results(self):
        return [
            {"status": "validated", "fraud_risk_level": "LOW"},
            {"status": "validated", "fraud_risk_level": "MEDIUM"},
            {"status": "validated", "fraud_risk_level": "HIGH"},
            {"status": "rejected", "fraud_risk_level": None},
            {"status": "rejected", "fraud_risk_level": None},
        ]

    def test_total_count(self):
        results = self._make_results()
        summary = build_summary(results)
        assert summary["total_transactions"] == 5

    def test_validated_count(self):
        results = self._make_results()
        summary = build_summary(results)
        assert summary["validated_count"] == 3

    def test_rejected_count(self):
        results = self._make_results()
        summary = build_summary(results)
        assert summary["rejected_count"] == 2

    def test_fraud_level_counts(self):
        results = self._make_results()
        summary = build_summary(results)
        assert summary["fraud_low_count"] == 1
        assert summary["fraud_medium_count"] == 1
        assert summary["fraud_high_count"] == 1

    def test_empty_results(self):
        summary = build_summary([])
        assert summary["total_transactions"] == 0
        assert summary["validated_count"] == 0
        assert summary["rejected_count"] == 0

    def test_processed_at_present(self):
        summary = build_summary([])
        assert "processed_at" in summary


# ---------------------------------------------------------------------------
# process_message
# ---------------------------------------------------------------------------

class TestProcessMessage:
    def test_returns_result_dict(self, scored_txn, audit):
        msg = PipelineMessage(
            source_agent="fraud_detector",
            target_agent="reporting_agent",
            message_type="transaction",
            data=scored_txn,
        )
        result = process_message(msg, audit)
        assert isinstance(result, dict)
        assert result["transaction_id"] == "TXN001"

    def test_audit_called(self, scored_txn, tmp_path):
        log_path = tmp_path / "audit.log"
        audit = AuditLogger("test_reporting", log_path, also_stderr=False)
        msg = PipelineMessage(
            source_agent="fraud_detector",
            target_agent="reporting_agent",
            message_type="transaction",
            data=scored_txn,
        )
        process_message(msg, audit)
        assert log_path.exists()
        entries = [json.loads(line) for line in log_path.read_text().splitlines()]
        assert any(e["transaction_id"] == "TXN001" for e in entries)


# ---------------------------------------------------------------------------
# run() — file-based integration
# ---------------------------------------------------------------------------

class TestRunFilesBased:
    def _make_scored_message(self, scored_txn) -> PipelineMessage:
        return PipelineMessage(
            source_agent="fraud_detector",
            target_agent="reporting_agent",
            message_type="transaction",
            data=scored_txn,
        )

    def test_run_writes_result_file(self, tmp_path, scored_txn):
        input_dir = tmp_path / "results_input"
        processing_dir = tmp_path / "processing"
        results_dir = tmp_path / "results"
        summary_path = tmp_path / "summary.json"
        for d in (input_dir, processing_dir, results_dir):
            d.mkdir()

        msg = self._make_scored_message(scored_txn)
        (input_dir / "TXN001.json").write_text(msg.to_json(), encoding="utf-8")

        summary = run(
            input_dir=input_dir,
            processing_dir=processing_dir,
            results_dir=results_dir,
            summary_path=summary_path,
            audit_log=tmp_path / "audit.log",
        )

        assert (results_dir / "TXN001.json").exists()
        assert summary_path.exists()
        assert summary["total_transactions"] == 1

    def test_run_with_pre_collected_results(self, tmp_path, scored_txn, rejected_txn):
        input_dir = tmp_path / "results_input"
        processing_dir = tmp_path / "processing"
        results_dir = tmp_path / "results"
        summary_path = tmp_path / "summary.json"
        for d in (input_dir, processing_dir, results_dir):
            d.mkdir()

        # No files in input_dir; pass rejected as pre-collected
        rejected_result = produce_result(rejected_txn)
        summary = run(
            input_dir=input_dir,
            processing_dir=processing_dir,
            results_dir=results_dir,
            summary_path=summary_path,
            audit_log=tmp_path / "audit.log",
            all_results=[rejected_result],
        )

        assert summary["total_transactions"] == 1
        assert summary["rejected_count"] == 1

    def test_run_empty(self, tmp_path):
        input_dir = tmp_path / "results_input"
        processing_dir = tmp_path / "processing"
        results_dir = tmp_path / "results"
        summary_path = tmp_path / "summary.json"
        for d in (input_dir, processing_dir, results_dir):
            d.mkdir()

        summary = run(
            input_dir=input_dir,
            processing_dir=processing_dir,
            results_dir=results_dir,
            summary_path=summary_path,
            audit_log=tmp_path / "audit.log",
        )
        assert summary["total_transactions"] == 0
