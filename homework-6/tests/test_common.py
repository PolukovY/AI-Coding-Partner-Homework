"""Unit tests for common utilities: masking, message, io_utils, audit."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from common.masking import mask_account, mask_accounts_in_dict
from common.message import PipelineMessage
from common.io_utils import (
    clear_directory,
    list_messages,
    load_message,
    move_message,
    safe_stem,
    save_message,
)
from common.audit import AuditLogger
from common.paths import ensure_shared_dirs


# ---------------------------------------------------------------------------
# masking
# ---------------------------------------------------------------------------

class TestMasking:
    def test_mask_account_basic(self):
        assert mask_account("ACC-1001") == "ACC-****"

    def test_mask_account_different_number(self):
        assert mask_account("ACC-9999") == "ACC-****"

    def test_mask_account_empty_string(self):
        assert mask_account("") == ""

    def test_mask_accounts_in_dict(self):
        d = {
            "source_account": "ACC-1001",
            "destination_account": "ACC-2002",
            "amount": "100.00",
        }
        result = mask_accounts_in_dict(d)
        assert result["source_account"] == "ACC-****"
        assert result["destination_account"] == "ACC-****"
        assert result["amount"] == "100.00"

    def test_mask_accounts_in_dict_no_accounts(self):
        d = {"amount": "100.00", "currency": "USD"}
        result = mask_accounts_in_dict(d)
        assert result == d


# ---------------------------------------------------------------------------
# PipelineMessage
# ---------------------------------------------------------------------------

class TestPipelineMessage:
    def _make_msg(self) -> PipelineMessage:
        return PipelineMessage(
            source_agent="test_agent",
            target_agent="other_agent",
            message_type="transaction",
            data={"transaction_id": "T1", "amount": "100.00"},
        )

    def test_to_dict_has_required_keys(self):
        msg = self._make_msg()
        d = msg.to_dict()
        for key in ("message_id", "timestamp", "source_agent", "target_agent",
                    "message_type", "data"):
            assert key in d

    def test_message_id_is_uuid4_format(self):
        msg = self._make_msg()
        parts = msg.message_id.split("-")
        assert len(parts) == 5

    def test_timestamp_iso8601(self):
        msg = self._make_msg()
        assert "T" in msg.timestamp
        assert msg.timestamp.endswith("Z")

    def test_to_json_round_trip(self):
        msg = self._make_msg()
        raw = msg.to_json()
        d = json.loads(raw)
        assert d["source_agent"] == "test_agent"

    def test_from_dict(self):
        msg = self._make_msg()
        reconstructed = PipelineMessage.from_dict(msg.to_dict())
        assert reconstructed.message_id == msg.message_id
        assert reconstructed.source_agent == msg.source_agent

    def test_save_and_load(self, tmp_path):
        msg = self._make_msg()
        path = tmp_path / "msg.json"
        msg.save(path)
        loaded = PipelineMessage.load(path)
        assert loaded.message_id == msg.message_id
        assert loaded.data == msg.data


# ---------------------------------------------------------------------------
# io_utils
# ---------------------------------------------------------------------------

class TestIoUtils:
    def _make_msg(self, txn_id="TXN001"):
        return PipelineMessage(
            source_agent="a",
            target_agent="b",
            message_type="transaction",
            data={"transaction_id": txn_id},
        )

    def test_save_and_list_messages(self, tmp_path):
        d = tmp_path / "msgs"
        d.mkdir()
        save_message(self._make_msg("TXN001"), d)
        save_message(self._make_msg("TXN002"), d)
        files = list_messages(d)
        assert len(files) == 2

    def test_list_messages_empty_dir(self, tmp_path):
        d = tmp_path / "empty"
        d.mkdir()
        assert list_messages(d) == []

    def test_save_message_uses_transaction_id(self, tmp_path):
        d = tmp_path / "msgs"
        d.mkdir()
        path = save_message(self._make_msg("TXN003"), d)
        assert path.name == "TXN003.json"

    def test_load_message(self, tmp_path):
        d = tmp_path / "msgs"
        d.mkdir()
        path = save_message(self._make_msg("TXN001"), d)
        msg = load_message(path)
        assert msg.data["transaction_id"] == "TXN001"

    def test_move_message(self, tmp_path):
        src_dir = tmp_path / "src"
        dst_dir = tmp_path / "dst"
        src_dir.mkdir()
        dst_dir.mkdir()
        path = save_message(self._make_msg("TXN001"), src_dir)
        new_path = move_message(path, dst_dir)
        assert new_path.exists()
        assert not path.exists()

    def test_clear_directory(self, tmp_path):
        d = tmp_path / "msgs"
        d.mkdir()
        save_message(self._make_msg("TXN001"), d)
        save_message(self._make_msg("TXN002"), d)
        clear_directory(d)
        assert list_messages(d) == []


# ---------------------------------------------------------------------------
# AuditLogger
# ---------------------------------------------------------------------------

class TestAuditLogger:
    def test_writes_to_file(self, tmp_path):
        log_path = tmp_path / "audit.log"
        audit = AuditLogger("test_agent", log_path, also_stderr=False)
        audit.log("TXN001", "validated")
        assert log_path.exists()
        line = json.loads(log_path.read_text().strip())
        assert line["transaction_id"] == "TXN001"
        assert line["outcome"] == "validated"
        assert line["agent"] == "test_agent"

    def test_iso8601_timestamp(self, tmp_path):
        log_path = tmp_path / "audit.log"
        audit = AuditLogger("a", log_path, also_stderr=False)
        audit.log("T1", "ok")
        line = json.loads(log_path.read_text().strip())
        ts = line["timestamp"]
        assert "T" in ts and "Z" in ts

    def test_details_included(self, tmp_path):
        log_path = tmp_path / "audit.log"
        audit = AuditLogger("a", log_path, also_stderr=False)
        audit.log("T1", "ok", details={"score": 5})
        line = json.loads(log_path.read_text().strip())
        assert line["details"]["score"] == 5

    def test_multiple_entries(self, tmp_path):
        log_path = tmp_path / "audit.log"
        audit = AuditLogger("a", log_path, also_stderr=False)
        audit.log("T1", "validated")
        audit.log("T2", "rejected")
        lines = [json.loads(l) for l in log_path.read_text().splitlines()]
        assert len(lines) == 2

    def test_no_log_path_does_not_raise(self):
        audit = AuditLogger("a", log_path=None, also_stderr=False)
        audit.log("T1", "ok")  # Should not raise

    def test_account_not_logged_plaintext(self, tmp_path):
        """Ensure plaintext account numbers do not appear in audit log."""
        log_path = tmp_path / "audit.log"
        audit = AuditLogger("a", log_path, also_stderr=False)
        from common.masking import mask_account
        audit.log(
            "TXN001",
            "validated",
            details={"source_account": mask_account("ACC-1001")},
        )
        content = log_path.read_text()
        assert "ACC-1001" not in content
        assert "ACC-****" in content

    def test_oserror_on_write_emits_warning(self, tmp_path, capsys):
        """OSError on file write emits a stderr warning instead of crashing."""
        # Point log_path at a directory (not a file) so open() raises OSError
        bad_path = tmp_path / "not_a_file"
        bad_path.mkdir()
        audit = AuditLogger("a", bad_path, also_stderr=False)
        audit.log("T1", "ok")  # Should not raise
        captured = capsys.readouterr()
        assert "WARNING" in captured.err


# ---------------------------------------------------------------------------
# safe_stem
# ---------------------------------------------------------------------------

class TestSafeStem:
    def test_valid_txn_id(self):
        assert safe_stem("TXN001") == "TXN001"

    def test_valid_with_hyphens(self):
        assert safe_stem("TXN-001") == "TXN-001"

    def test_valid_with_underscores(self):
        assert safe_stem("txn_001") == "txn_001"

    def test_path_traversal_rejected(self):
        with pytest.raises(ValueError, match="Unsafe"):
            safe_stem("../../etc/passwd")

    def test_slash_rejected(self):
        with pytest.raises(ValueError):
            safe_stem("foo/bar")

    def test_empty_string_rejected(self):
        with pytest.raises(ValueError):
            safe_stem("")

    def test_save_message_rejects_traversal(self, tmp_path):
        """save_message() must reject a transaction_id that traverses the path."""
        msg = PipelineMessage(
            source_agent="a",
            target_agent="b",
            message_type="transaction",
            data={"transaction_id": "../../evil"},
        )
        with pytest.raises(ValueError):
            save_message(msg, tmp_path)


# ---------------------------------------------------------------------------
# ensure_shared_dirs
# ---------------------------------------------------------------------------

class TestEnsureSharedDirs:
    def test_creates_directories(self, tmp_path, monkeypatch):
        """ensure_shared_dirs() creates all pipeline subdirectories."""
        import common.paths as cp
        # Redirect all path constants to a tmp subtree
        monkeypatch.setattr(cp, "INPUT_DIR", tmp_path / "input")
        monkeypatch.setattr(cp, "PROCESSING_DIR", tmp_path / "processing")
        monkeypatch.setattr(cp, "OUTPUT_DIR", tmp_path / "output")
        monkeypatch.setattr(cp, "RESULTS_DIR", tmp_path / "results")
        monkeypatch.setattr(cp, "LOGS_DIR", tmp_path / "logs")
        ensure_shared_dirs()
        for sub in ("input", "processing", "output", "results", "logs"):
            assert (tmp_path / sub).is_dir()
