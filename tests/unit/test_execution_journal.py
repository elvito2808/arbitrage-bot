import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from arbitrage_bot.services.execution_journal import ExecutionJournal, DuplicateExecutionError


class ExecutionJournalTests(unittest.TestCase):
    def test_reserve_update_and_duplicate_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = ExecutionJournal(str(Path(tmp) / "journal.sqlite3"))
            journal.reserve("candidate-001", "test")
            journal.update("candidate-001", "PREFLIGHT_PASSED", "all checks passed")
            row = journal.get("candidate-001")
            self.assertEqual(row["status"], "PREFLIGHT_PASSED")
            self.assertEqual(row["details"], "all checks passed")
            with self.assertRaises(DuplicateExecutionError):
                journal.reserve("candidate-001")

    def test_unknown_key_cannot_be_updated(self):
        with tempfile.TemporaryDirectory() as tmp:
            journal = ExecutionJournal(str(Path(tmp) / "journal.sqlite3"))
            with self.assertRaises(KeyError):
                journal.update("missing", "FAILED")


if __name__ == "__main__":
    unittest.main()
