import json
import os
import sys
import tempfile
import unittest
from io import StringIO
from pathlib import Path

from llmdev import metrics, runner


class TestMetrics(unittest.TestCase):
    def test_aider_stats_empty(self):
        stats = metrics.aider_stats("")
        self.assertEqual(stats, {"rounds": 0, "sent": 0, "received": 0, "applied": 0})

    def test_aider_stats_tokens(self):
        text = "> Tokens: 20k sent, 2.8k received.\n> Tokens: 950 sent, 12 received."
        stats = metrics.aider_stats(text)
        self.assertEqual(stats["rounds"], 2)
        self.assertEqual(stats["sent"], 20950)
        self.assertEqual(stats["received"], 2812)

    def test_aider_stats_applied(self):
        text = "> Applied edit to a.py\n> Applied edit to b.py"
        stats = metrics.aider_stats(text)
        self.assertEqual(stats["applied"], 2)

    def test_aider_stats_ignores_quoted(self):
        text = '        text = "> Tokens: 20k sent, 2.8k received."\n        if "> Applied edit to" in line:'
        stats = metrics.aider_stats(text)
        self.assertEqual(stats["rounds"], 0)
        self.assertEqual(stats["applied"], 0)

    def test_read_runs_missing_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            rows = metrics.read_runs(os.path.join(tmpdir, "nonexistent"))
            self.assertEqual(rows, [])

    def test_read_runs_new_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = os.path.join(tmpdir, "20260101-100000-card1")
            os.makedirs(run_dir)
            meta = {
                "card_id": "card1",
                "model_name": "test-model",
                "backend": "ollama",
                "started": "2026-01-01T10:00:00",
                "ended": "2026-01-01T10:01:30",
                "passed": True,
                "timed_out": False,
                "empty_files": [],
                "stray_files": [],
            }
            with open(os.path.join(run_dir, "meta.json"), "w") as f:
                json.dump(meta, f)

            rows = metrics.read_runs(tmpdir)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["run"], "20260101-100000-card1")
            self.assertEqual(row["card"], "card1")
            self.assertEqual(row["model"], "test-model")
            self.assertEqual(row["backend"], "ollama")
            self.assertEqual(row["duration_s"], 90)
            self.assertEqual(row["passed"], True)
            self.assertEqual(row["timed_out"], False)
            self.assertEqual(row["stray"], 0)
            self.assertEqual(row["empty"], 0)
            self.assertEqual(row["rounds"], 0)
            self.assertEqual(row["sent"], 0)
            self.assertEqual(row["received"], 0)
            self.assertEqual(row["applied"], 0)

    def test_read_runs_old_record(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = os.path.join(tmpdir, "20260101-100000-card1")
            os.makedirs(run_dir)
            meta = {
                "card_id": "card1",
                "model_name": "test-model",
                "backend": "ollama",
                "started": "2026-01-01T10:00:00",
                "ended": "2026-01-01T10:01:30",
                "passed": True,
            }
            with open(os.path.join(run_dir, "meta.json"), "w") as f:
                json.dump(meta, f)

            rows = metrics.read_runs(tmpdir)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["timed_out"], None)
            self.assertEqual(row["stray"], None)
            self.assertEqual(row["empty"], None)

    def test_read_runs_no_meta(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = os.path.join(tmpdir, "20260101-100000-card1")
            os.makedirs(run_dir)
            rows = metrics.read_runs(tmpdir)
            self.assertEqual(rows, [])

    def test_read_runs_no_aider(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = os.path.join(tmpdir, "20260101-100000-card1")
            os.makedirs(run_dir)
            meta = {
                "card_id": "card1",
                "model_name": "test-model",
                "backend": "ollama",
                "started": "2026-01-01T10:00:00",
                "ended": "2026-01-01T10:01:30",
                "passed": True,
                "timed_out": False,
                "empty_files": [],
                "stray_files": [],
            }
            with open(os.path.join(run_dir, "meta.json"), "w") as f:
                json.dump(meta, f)

            rows = metrics.read_runs(tmpdir)
            self.assertEqual(len(rows), 1)
            row = rows[0]
            self.assertEqual(row["rounds"], 0)
            self.assertEqual(row["sent"], 0)
            self.assertEqual(row["received"], 0)
            self.assertEqual(row["applied"], 0)

    def test_format_runs_empty(self):
        result = metrics.format_runs([])
        self.assertEqual(result, "no runs yet")

    def test_format_runs_with_rows(self):
        rows = [
            {
                "run": "20260101-100000-card1",
                "card": "card1",
                "model": "test-model",
                "passed": True,
                "duration_s": 90,
                "rounds": 2,
                "sent": 20950,
                "received": 2812,
                "applied": 2,
                "stray": 0,
                "empty": 0,
                "timed_out": False,
            }
        ]
        result = metrics.format_runs(rows)
        lines = result.split("\n")
        self.assertEqual(len(lines), 2)
        self.assertIn("run", lines[0])
        self.assertIn("20260101-100000-card1", lines[1])

    def test_format_runs_none_values(self):
        rows = [
            {
                "run": "20260101-100000-card1",
                "card": "card1",
                "model": "test-model",
                "passed": None,
                "duration_s": None,
                "rounds": None,
                "sent": None,
                "received": None,
                "applied": None,
                "stray": None,
                "empty": None,
                "timed_out": None,
            }
        ]
        result = metrics.format_runs(rows)
        self.assertIn("-", result)

    def test_format_runs_no_trailing_spaces(self):
        rows = [
            {
                "run": "run1",
                "card": "card1",
                "model": "model1",
                "passed": True,
                "duration_s": 10,
                "rounds": 1,
                "sent": 100,
                "received": 100,
                "applied": 1,
                "stray": 0,
                "empty": 0,
                "timed_out": False,
            }
        ]
        result = metrics.format_runs(rows)
        for line in result.split("\n"):
            self.assertEqual(line, line.rstrip())

    def test_default_message_whole_format(self):
        from llmdev.cards import Card
        card = Card(id="001", title="Test", edit=["file.py"], read=[], checks=[], edit_format="whole", path="cards/001-test.md", commit="test commit")
        msg = runner.default_message(card)
        self.assertIn("fenced code block", msg)
        self.assertIn("No line may end with spaces", msg)
        self.assertNotIn("SEARCH/REPLACE", msg)

    def test_default_message_normal_format(self):
        from llmdev.cards import Card
        card = Card(id="001", title="Test", edit=["file.py"], read=[], checks=[], edit_format="", path="cards/001-test.md", commit="test commit")
        msg = runner.default_message(card)
        self.assertIn("SEARCH/REPLACE", msg)

    def test_read_runs_duration(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            run_dir = os.path.join(tmpdir, "20260101-100000-card1")
            os.makedirs(run_dir)
            meta = {
                "card_id": "card1",
                "model_name": "test-model",
                "backend": "ollama",
                "started": "2026-01-01T10:00:00",
                "ended": "2026-01-01T10:01:30",
                "passed": True,
                "timed_out": False,
                "empty_files": [],
                "stray_files": [],
            }
            with open(os.path.join(run_dir, "meta.json"), "w") as f:
                json.dump(meta, f)

            rows = metrics.read_runs(tmpdir)
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["duration_s"], 90)

    def test_cli_runs_filter(self):
        from unittest.mock import patch

        with tempfile.TemporaryDirectory() as tmpdir:
            # Create models.toml
            models_toml = Path(tmpdir) / "models.toml"
            models_toml.write_text('''
[models.test-model]
backend = "ollama"
model = "test"
ctx = 65536
port = 11434
''')

            # Create runs directory structure
            runs_dir = Path(tmpdir) / "runs"
            runs_dir.mkdir()

            run1_dir = runs_dir / "20260101-100000-001"
            run1_dir.mkdir()
            meta1 = {"card_id": "001", "model_name": "test-model", "backend": "ollama"}
            with open(run1_dir / "meta.json", "w") as f:
                json.dump(meta1, f)

            run2_dir = runs_dir / "20260101-110000-002"
            run2_dir.mkdir()
            meta2 = {"card_id": "002", "model_name": "test-model", "backend": "ollama"}
            with open(run2_dir / "meta.json", "w") as f:
                json.dump(meta2, f)

            # Patch ROOT and capture output
            from llmdev import cli

            with patch("llmdev.cli.ROOT", Path(tmpdir)):
                captured_output = StringIO()
                old_stdout = sys.stdout
                sys.stdout = captured_output
                try:
                    cli.main(["runs", "--card", "002"])
                finally:
                    sys.stdout = old_stdout

                output = captured_output.getvalue()
                self.assertIn("20260101-110000-002", output)
                self.assertNotIn("20260101-100000-001", output)


if __name__ == "__main__":
    unittest.main()
