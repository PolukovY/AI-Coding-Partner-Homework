"""Unit tests for the Transaction Validator agent."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

import pytest

# Ensure project root is importable
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from agents.transaction_validator import (
    REASON_INVALID_AMOUNT,
    REASON_INVALID_CURRENCY,
    REASON_MISSING_FIELDS,
    REASON_NON_POSITIVE_AMOUNT,
    validate_transaction,
    run,
    _dry_run,
    _build_parser,
    main,
)
from common.audit import AuditLogger
from common.message import PipelineMessage
from agents.transaction_validator import process_message


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def valid_txn() -> dict:
    return {
        "transaction_id": "TXN001",
        "timestamp": "2026-03-16T09:00:00Z",
        "source_account": "ACC-1001",
        "destination_account": "ACC-2001",
        "amount": "1500.00",
        "currency": "USD",
        "transaction_type": "transfer",
        "description": "Monthly rent payment",
        "metadata": {"channel": "online", "country": "US"},
    }


@pytest.fixture
def audit(tmp_path) -> AuditLogger:
    return AuditLogger("test_validator", tmp_path / "audit.log", also_stderr=False)


# ---------------------------------------------------------------------------
# validate_transaction
# ---------------------------------------------------------------------------

class TestValidateTransaction:
    def test_valid_transaction_returns_validated(self, valid_txn):
        result = validate_transaction(valid_txn)
        assert result["status"] == "validated"
        assert result["rejection_reason"] is None
        assert result["transaction_id"] == "TXN001"

    def test_missing_field_returns_rejected(self, valid_txn):
        del valid_txn["currency"]
        result = validate_transaction(valid_txn)
        assert result["status"] == "rejected"
        assert result["rejection_reason"] == REASON_MISSING_FIELDS

    def test_multiple_missing_fields(self, valid_txn):
        del valid_txn["currency"]
        del valid_txn["amount"]
        result = validate_transaction(valid_txn)
        assert result["status"] == "rejected"
        assert "currency" in result["rejection_detail"]

    def test_non_numeric_amount_returns_rejected(self, valid_txn):
        valid_txn["amount"] = "not-a-number"
        result = validate_transaction(valid_txn)
        assert result["status"] == "rejected"
        assert result["rejection_reason"] == REASON_INVALID_AMOUNT

    def test_negative_amount_returns_rejected(self, valid_txn):
        valid_txn["amount"] = "-100.00"
        result = validate_transaction(valid_txn)
        assert result["status"] == "rejected"
        assert result["rejection_reason"] == REASON_NON_POSITIVE_AMOUNT

    def test_zero_amount_returns_rejected(self, valid_txn):
        valid_txn["amount"] = "0"
        result = validate_transaction(valid_txn)
        assert result["status"] == "rejected"
        assert result["rejection_reason"] == REASON_NON_POSITIVE_AMOUNT

    def test_invalid_currency_returns_rejected(self, valid_txn):
        valid_txn["currency"] = "XYZ"
        result = validate_transaction(valid_txn)
        assert result["status"] == "rejected"
        assert result["rejection_reason"] == REASON_INVALID_CURRENCY

    def test_valid_eur_currency(self, valid_txn):
        valid_txn["currency"] = "EUR"
        result = validate_transaction(valid_txn)
        assert result["status"] == "validated"

    def test_valid_gbp_currency(self, valid_txn):
        valid_txn["currency"] = "GBP"
        result = validate_transaction(valid_txn)
        assert result["status"] == "validated"

    def test_valid_jpy_currency(self, valid_txn):
        valid_txn["currency"] = "JPY"
        result = validate_transaction(valid_txn)
        assert result["status"] == "validated"

    def test_amount_is_preserved_as_string(self, valid_txn):
        """Ensure amount stays as string (Decimal-safe) in output data."""
        result = validate_transaction(valid_txn)
        assert isinstance(result["data"]["amount"], str)

    def test_currency_is_uppercased(self, valid_txn):
        valid_txn["currency"] = "usd"
        result = validate_transaction(valid_txn)
        assert result["status"] == "validated"
        assert result["data"]["currency"] == "USD"

    def test_missing_metadata(self, valid_txn):
        del valid_txn["metadata"]
        result = validate_transaction(valid_txn)
        assert result["status"] == "rejected"

    def test_unknown_transaction_id_default(self):
        result = validate_transaction({})
        assert result["transaction_id"] == "UNKNOWN"


# ---------------------------------------------------------------------------
# process_message
# ---------------------------------------------------------------------------

class TestProcessMessage:
    def test_valid_produces_fraud_detector_target(self, valid_txn, audit):
        msg = PipelineMessage(
            source_agent="orchestrator",
            target_agent="transaction_validator",
            message_type="transaction",
            data=valid_txn,
        )
        out = process_message(msg, audit)
        assert out.target_agent == "fraud_detector"
        assert out.data["status"] == "validated"

    def test_invalid_produces_results_target(self, valid_txn, audit):
        valid_txn["currency"] = "XYZ"
        msg = PipelineMessage(
            source_agent="orchestrator",
            target_agent="transaction_validator",
            message_type="transaction",
            data=valid_txn,
        )
        out = process_message(msg, audit)
        assert out.target_agent == "results"
        assert out.data["status"] == "rejected"

    def test_rejection_reason_in_output_data(self, valid_txn, audit):
        valid_txn["amount"] = "-5"
        msg = PipelineMessage(
            source_agent="orchestrator",
            target_agent="transaction_validator",
            message_type="transaction",
            data=valid_txn,
        )
        out = process_message(msg, audit)
        assert "rejection_reason" in out.data


# ---------------------------------------------------------------------------
# run() — file-based integration
# ---------------------------------------------------------------------------

class TestRunFilesBased:
    def test_run_processes_valid_transaction(self, tmp_path, valid_txn):
        input_dir = tmp_path / "input"
        processing_dir = tmp_path / "processing"
        output_dir = tmp_path / "output"
        results_dir = tmp_path / "results"
        for d in (input_dir, processing_dir, output_dir, results_dir):
            d.mkdir()

        msg = PipelineMessage(
            source_agent="orchestrator",
            target_agent="transaction_validator",
            message_type="transaction",
            data=valid_txn,
        )
        (input_dir / "TXN001.json").write_text(msg.to_json(), encoding="utf-8")

        results = run(
            input_dir=input_dir,
            processing_dir=processing_dir,
            output_dir=output_dir,
            results_dir=results_dir,
            audit_log=tmp_path / "audit.log",
        )

        assert len(results) == 1
        assert results[0]["status"] == "validated"
        assert (output_dir / "TXN001.json").exists()

    def test_run_processes_invalid_transaction(self, tmp_path, valid_txn):
        valid_txn["currency"] = "XYZ"
        input_dir = tmp_path / "input"
        processing_dir = tmp_path / "processing"
        output_dir = tmp_path / "output"
        results_dir = tmp_path / "results"
        for d in (input_dir, processing_dir, output_dir, results_dir):
            d.mkdir()

        msg = PipelineMessage(
            source_agent="orchestrator",
            target_agent="transaction_validator",
            message_type="transaction",
            data=valid_txn,
        )
        (input_dir / "TXN001.json").write_text(msg.to_json(), encoding="utf-8")

        results = run(
            input_dir=input_dir,
            processing_dir=processing_dir,
            output_dir=output_dir,
            results_dir=results_dir,
            audit_log=tmp_path / "audit.log",
        )

        assert results[0]["status"] == "rejected"
        assert (results_dir / "TXN001.json").exists()

    def test_run_with_empty_directory(self, tmp_path):
        input_dir = tmp_path / "input"
        input_dir.mkdir()
        processing_dir = tmp_path / "processing"
        processing_dir.mkdir()
        output_dir = tmp_path / "output"
        output_dir.mkdir()
        results_dir = tmp_path / "results"
        results_dir.mkdir()

        results = run(
            input_dir=input_dir,
            processing_dir=processing_dir,
            output_dir=output_dir,
            results_dir=results_dir,
            audit_log=tmp_path / "audit.log",
        )
        assert results == []


# ---------------------------------------------------------------------------
# dry-run
# ---------------------------------------------------------------------------

class TestDryRun:
    def test_dry_run_prints_report(self, tmp_path, capsys, valid_txn):
        src = tmp_path / "transactions.json"
        src.write_text(json.dumps([valid_txn]), encoding="utf-8")
        _dry_run(src)
        captured = capsys.readouterr()
        assert "TXN001" in captured.out
        assert "validated" in captured.out

    def test_dry_run_shows_invalid(self, tmp_path, capsys, valid_txn):
        valid_txn["currency"] = "XYZ"
        src = tmp_path / "transactions.json"
        src.write_text(json.dumps([valid_txn]), encoding="utf-8")
        _dry_run(src)
        captured = capsys.readouterr()
        assert "rejected" in captured.out
        assert "INVALID_CURRENCY" in captured.out

    def test_dry_run_missing_file_exits(self, tmp_path, capsys):
        with pytest.raises(SystemExit) as exc_info:
            _dry_run(tmp_path / "nonexistent.json")
        assert exc_info.value.code == 1
        assert "not found" in capsys.readouterr().err


# ---------------------------------------------------------------------------
# CLI — _build_parser and main
# ---------------------------------------------------------------------------

class TestCLI:
    def test_build_parser_dry_run_default_false(self):
        parser = _build_parser()
        args = parser.parse_args([])
        assert args.dry_run is False

    def test_build_parser_dry_run_flag(self):
        parser = _build_parser()
        args = parser.parse_args(["--dry-run"])
        assert args.dry_run is True

    def test_build_parser_custom_input(self, tmp_path):
        parser = _build_parser()
        args = parser.parse_args(["--input", str(tmp_path / "data.json")])
        assert "data.json" in args.input

    def test_main_dry_run(self, tmp_path, monkeypatch, capsys, valid_txn):
        src = tmp_path / "transactions.json"
        src.write_text(json.dumps([valid_txn]), encoding="utf-8")
        monkeypatch.setattr("sys.argv", ["validator", "--dry-run", "--input", str(src)])
        main()
        assert "TXN001" in capsys.readouterr().out
