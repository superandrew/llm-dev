import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from pathlib import Path
from unittest.mock import patch

from llmdev import server
from llmdev.cli import main


class TestCLI(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.tmp = Path(self.tmp_dir.name)
        models_toml = self.tmp / "models.toml"
        models_toml.write_text("""
[defaults]
host = "127.0.0.1"

[models.m1]
backend = "ollama"
model = "m1-model"
ctx = 4096
port = 11434
""")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_list(self):
        with patch("llmdev.cli.ROOT", self.tmp):
            f_out = io.StringIO()
            f_err = io.StringIO()
            with redirect_stdout(f_out), redirect_stderr(f_err):
                ret = main(["list"])
            self.assertEqual(ret, 0)
            self.assertEqual(f_out.getvalue().strip(), "m1 ollama m1-model 4096 11434")
            self.assertEqual(f_err.getvalue(), "")

    def test_serve_started(self):
        with patch("llmdev.cli.ROOT", self.tmp), \
             patch("llmdev.cli.server.start") as mock_start:
            mock_start.return_value = 7
            f_out = io.StringIO()
            f_err = io.StringIO()
            with redirect_stdout(f_out), redirect_stderr(f_err):
                ret = main(["serve", "m1"])
            self.assertEqual(ret, 0)
            self.assertEqual(f_out.getvalue().strip(), "started pid 7")
            self.assertEqual(f_err.getvalue(), "")

    def test_serve_already_serving(self):
        with patch("llmdev.cli.ROOT", self.tmp), \
             patch("llmdev.cli.server.start") as mock_start:
            mock_start.return_value = None
            f_out = io.StringIO()
            f_err = io.StringIO()
            with redirect_stdout(f_out), redirect_stderr(f_err):
                ret = main(["serve", "m1"])
            self.assertEqual(ret, 0)
            self.assertEqual(f_out.getvalue().strip(), "already serving at http://127.0.0.1:11434/v1")
            self.assertEqual(f_err.getvalue(), "")

    def test_bench_unhealthy(self):
        with patch("llmdev.cli.ROOT", self.tmp), \
             patch("llmdev.cli.server.health") as mock_health:
            mock_health.return_value = False
            f_out = io.StringIO()
            f_err = io.StringIO()
            with redirect_stdout(f_out), redirect_stderr(f_err):
                ret = main(["bench", "m1"])
            self.assertEqual(ret, 1)
            self.assertEqual(f_err.getvalue().strip(), "m1 is not healthy")
            self.assertEqual(f_out.getvalue(), "")

    def test_bench_repeat(self):
        with patch("llmdev.cli.ROOT", self.tmp), \
             patch("llmdev.cli.server.health") as mock_health, \
             patch("llmdev.cli.bench.run") as mock_run:
            mock_health.return_value = True
            mock_run.return_value = {"tokens": 10}
            f_out = io.StringIO()
            f_err = io.StringIO()
            with redirect_stdout(f_out), redirect_stderr(f_err):
                ret = main(["bench", "m1", "--repeat", "3"])
            self.assertEqual(ret, 0)
            self.assertEqual(mock_run.call_count, 3)
            bench_path = self.tmp / "runs" / "bench.jsonl"
            self.assertTrue(bench_path.exists())
            lines = bench_path.read_text().strip().split("\n")
            self.assertEqual(len(lines), 3)
            for line in lines:
                data = json.loads(line)
                self.assertIn("timestamp", data)

    def test_run_passed(self):
        with patch("llmdev.cli.ROOT", self.tmp), \
             patch("llmdev.cli.server.health") as mock_health, \
             patch("llmdev.cli.cards.parse") as mock_parse, \
             patch("llmdev.cli.runner.run_card") as mock_run_card:
            mock_health.return_value = True
            mock_parse.return_value = type("Card", (), {
                "path": "card.md",
                "edit": ("file.py",),
                "read": (),
                "checks": (),
                "commit": "",
                "edit_format": "",
            })()
            mock_run_card.return_value = {"passed": True}
            f_out = io.StringIO()
            f_err = io.StringIO()
            with redirect_stdout(f_out), redirect_stderr(f_err):
                ret = main(["run", "card.md", "--model", "m1"])
            self.assertEqual(ret, 0)
            self.assertEqual(f_err.getvalue(), "")

    def test_run_failed(self):
        with patch("llmdev.cli.ROOT", self.tmp), \
             patch("llmdev.cli.server.health") as mock_health, \
             patch("llmdev.cli.cards.parse") as mock_parse, \
             patch("llmdev.cli.runner.run_card") as mock_run_card:
            mock_health.return_value = True
            mock_parse.return_value = type("Card", (), {
                "path": "card.md",
                "edit": ("file.py",),
                "read": (),
                "checks": (),
                "commit": "",
                "edit_format": "",
            })()
            mock_run_card.return_value = {"passed": False}
            f_out = io.StringIO()
            f_err = io.StringIO()
            with redirect_stdout(f_out), redirect_stderr(f_err):
                ret = main(["run", "card.md", "--model", "m1"])
            self.assertEqual(ret, 1)
            self.assertEqual(f_err.getvalue(), "")

    def test_run_unhealthy(self):
        with patch("llmdev.cli.ROOT", self.tmp), \
             patch("llmdev.cli.server.health") as mock_health:
            mock_health.return_value = False
            f_out = io.StringIO()
            f_err = io.StringIO()
            with redirect_stdout(f_out), redirect_stderr(f_err):
                ret = main(["run", "card.md", "--model", "m1"])
            self.assertEqual(ret, 1)
            self.assertEqual(f_err.getvalue().strip(), "m1 is not healthy")
            self.assertEqual(f_out.getvalue(), "")

    def test_serve_unknown_model(self):
        with patch("llmdev.cli.ROOT", self.tmp):
            f_out = io.StringIO()
            f_err = io.StringIO()
            with redirect_stdout(f_out), redirect_stderr(f_err):
                ret = main(["serve", "unknown"])
            self.assertEqual(ret, 1)
            self.assertIn("unknown model", f_err.getvalue())

    def test_serve_server_error(self):
        with patch("llmdev.cli.ROOT", self.tmp), \
             patch("llmdev.cli.server.start") as mock_start:
            mock_start.side_effect = server.ServerError("server error")
            f_out = io.StringIO()
            f_err = io.StringIO()
            with redirect_stdout(f_out), redirect_stderr(f_err):
                ret = main(["serve", "m1"])
            self.assertEqual(ret, 1)
            self.assertIn("server error", f_err.getvalue())
            self.assertEqual(f_out.getvalue(), "")
