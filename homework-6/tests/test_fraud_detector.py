"""Unit tests for the Fraud Detector agent."""

from __future__ import annotations

from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.fraud_detector import (
    AGENT_NAME,
    _parse_hour_utc,
    _risk_level,
    process_message,
    run,
    score_transaction,
)
from common.audit import AuditLogger
from common.message import PipelineMessage


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def validated_txn() -> dict:
    return {
        "transaction_id": "TXN001",
        "timestamp": "2026-03-16T09:00:00Z",
        "source_account": "ACC-1001",
        "destination_account": "ACC-2001",
        "amount": "1500.00",
        "currency": "USD",
        "transaction_type": "transfer",
        "status": "validated",
        "metadata": {"channel": "online", "country": "US"},
    }


@pytest.fixture
def audit(tmp_path) -> AuditLogger:
    return AuditLogger("test_fraud", tmp_path / "audit.log", also_stderr=False)


# ---------------------------------------------------------------------------
# _parse_hour_utc
# ---------------------------------------------------------------------------

class TestParseHourUtc:
    def test_standard_z_suffix(self):
        assert _parse_hour_utc("2026-03-16T09:00:00Z") == 9

    def test_midnight(self):
        assert _parse_hour_utc("2026-03-16T00:00:00Z") == 0

    def test_unusual_hour(self):
        assert _parse_hour_utc("2026-03-16T02:47:00Z") == 2

    def test_invalid_returns_none(self):
        assert _parse_hour_utc("not-a-timestamp") is None

    def test_empty_string_returns_none(self):
        assert _parse_hour_utc("") is None


# ---------------------------------------------------------------------------
# _risk_level
# ---------------------------------------------------------------------------

class TestRiskLevel:
    def test_score_0_is_low(self):
        assert _risk_level(0) == "LOW"

    def test_score_2_is_low(self):
        assert _risk_level(2) == "LOW"

    def test_score_3_is_medium(self):
        assert _risk_level(3) == "MEDIUM"

    def test_score_6_is_medium(self):
        assert _risk_level(6) == "MEDIUM"

    def test_score_7_is_high(self):
        assert _risk_level(7) == "HIGH"

    def test_score_10_is_high(self):
        assert _risk_level(10) == "HIGH"


# ---------------------------------------------------------------------------
# score_transaction
# ---------------------------------------------------------------------------

class TestScoreTransaction:
    def test_low_amount_us_transfer_scores_low(self, validated_txn):
        result = score_transaction(validated_txn)
        assert result["fraud_risk_score"] == 0
        assert result["fraud_risk_level"] == "LOW"
        assert result["fraud_flags"] == []

    def test_high_value_adds_amount_high_flag(self, validated_txn):
        validated_txn["amount"] = "15000.00"
        result = score_transaction(validated_txn)
        assert "AMOUNT_HIGH" in result["fraud_flags"]
        assert result["fraud_risk_score"] >= 3

    def test_very_high_value_adds_very_high_flag(self, validated_txn):
        validated_txn["amount"] = "75000.00"
        result = score_transaction(validated_txn)
        assert "AMOUNT_VERY_HIGH" in result["fraud_flags"]
        assert result["fraud_risk_score"] >= 7

    def test_unusual_hour_adds_flag(self, validated_txn):
        validated_txn["timestamp"] = "2026-03-16T02:47:00Z"
        validated_txn["amount"] = "500.00"
        result = score_transaction(validated_txn)
        assert "UNUSUAL_HOUR" in result["fraud_flags"]
        assert result["fraud_risk_score"] >= 2

    def test_cross_border_adds_flag(self, validated_txn):
        validated_txn["metadata"]["country"] = "DE"
        result = score_transaction(validated_txn)
        assert "CROSS_BORDER" in result["fraud_flags"]

    def test_wire_transfer_adds_flag(self, validated_txn):
        validated_txn["transaction_type"] = "wire_transfer"
        result = score_transaction(validated_txn)
        assert "WIRE_TRANSFER" in result["fraud_flags"]

    def test_score_capped_at_10(self, validated_txn):
        validated_txn["amount"] = "100000.00"
        validated_txn["timestamp"] = "2026-03-16T03:00:00Z"
        validated_txn["metadata"]["country"] = "NG"
        validated_txn["transaction_type"] = "wire_transfer"
        result = score_transaction(validated_txn)
        assert result["fraud_risk_score"] <= 10

    def test_output_contains_all_required_keys(self, validated_txn):
        result = score_transaction(validated_txn)
        assert "fraud_risk_score" in result
        assert "fraud_risk_level" in result
        assert "fraud_flags" in result

    def test_original_data_preserved(self, validated_txn):
        result = score_transaction(validated_txn)
        assert result["transaction_id"] == "TXN001"
        assert result["amount"] == "1500.00"

    def test_missing_metadata_defaults_to_us(self, validated_txn):
        del validated_txn["metadata"]
        result = score_transaction(validated_txn)
        # Without metadata, country defaults to US — no cross-border flag
        assert "CROSS_BORDER" not in result["fraud_flags"]

    def test_txn002_wire_high_value(self):
        """TXN002: wire_transfer $25k → AMOUNT_HIGH + WIRE_TRANSFER = score 4."""
        txn = {
            "transaction_id": "TXN002",
            "timestamp": "2026-03-16T09:15:00Z",
            "source_account": "ACC-1002",
            "destination_account": "ACC-3001",
            "amount": "25000.00",
            "currency": "USD",
            "transaction_type": "wire_transfer",
            "status": "validated",
            "metadata": {"channel": "branch", "country": "US"},
        }
        result = score_transaction(txn)
        assert result["fraud_risk_score"] == 4
        assert result["fraud_risk_level"] == "MEDIUM"

    def test_txn004_unusual_hour_cross_border(self):
        """TXN004: unusual hour + cross-border EUR → score 3."""
        txn = {
            "transaction_id": "TXN004",
            "timestamp": "2026-03-16T02:47:00Z",
            "source_account": "ACC-1004",
            "destination_account": "ACC-5500",
            "amount": "500.00",
            "currency": "EUR",
            "transaction_type": "transfer",
            "status": "validated",
            "metadata": {"channel": "api", "country": "DE"},
        }
        result = score_transaction(txn)
        assert "UNUSUAL_HOUR" in result["fraud_flags"]
        assert "CROSS_BORDER" in result["fraud_flags"]
        assert result["fraud_risk_score"] == 3

    def test_txn005_very_high_wire(self):
        """TXN005: $75k wire_transfer → AMOUNT_VERY_HIGH + WIRE_TRANSFER = 8."""
        txn = {
            "transaction_id": "TXN005",
            "timestamp": "2026-03-16T10:00:00Z",
            "source_account": "ACC-1005",
            "destination_account": "ACC-6600",
            "amount": "75000.00",
            "currency": "USD",
            "transaction_type": "wire_transfer",
            "status": "validated",
            "metadata": {"channel": "branch", "country": "US"},
        }
        result = score_transaction(txn)
        assert result["fraud_risk_score"] == 8
        assert result["fraud_risk_level"] == "HIGH"


# ---------------------------------------------------------------------------
# process_message
# ---------------------------------------------------------------------------

class TestProcessMessage:
    def test_process_message_returns_pipeline_message(self, validated_txn, audit):
        msg = PipelineMessage(
            source_agent="transaction_validator",
            target_agent="fraud_detector",
            message_type="transaction",
            data=validated_txn,
        )
        out = process_message(msg, audit)
        assert isinstance(out, PipelineMessage)
        assert out.source_agent == AGENT_NAME
        assert out.target_agent == "reporting_agent"

    def test_fraud_fields_added(self, validated_txn, audit):
        msg = PipelineMessage(
            source_agent="transaction_validator",
            target_agent="fraud_detector",
            message_type="transaction",
            data=validated_txn,
        )
        out = process_message(msg, audit)
        assert "fraud_risk_score" in out.data
        assert "fraud_risk_level" in out.data
        assert "fraud_flags" in out.data


# ---------------------------------------------------------------------------
# run() — file-based integration
# ---------------------------------------------------------------------------

class TestRunFilesBased:
    def test_run_processes_validated_transaction(self, tmp_path, validated_txn):
        input_dir = tmp_path / "output"
        processing_dir = tmp_path / "processing"
        output_dir = tmp_path / "results"
        for d in (input_dir, processing_dir, output_dir):
            d.mkdir()

        msg = PipelineMessage(
            source_agent="transaction_validator",
            target_agent="fraud_detector",
            message_type="transaction",
            data=validated_txn,
        )
        (input_dir / "TXN001.json").write_text(msg.to_json(), encoding="utf-8")

        results = run(
            input_dir=input_dir,
            processing_dir=processing_dir,
            output_dir=output_dir,
            audit_log=tmp_path / "audit.log",
        )

        assert len(results) == 1
        assert "fraud_risk_score" in results[0]
        assert (output_dir / "TXN001.json").exists()

    def test_run_empty_directory(self, tmp_path):
        for d in ("output", "processing", "results"):
            (tmp_path / d).mkdir()
        results = run(
            input_dir=tmp_path / "output",
            processing_dir=tmp_path / "processing",
            output_dir=tmp_path / "results",
            audit_log=tmp_path / "audit.log",
        )
        assert results == []
