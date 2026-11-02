import json
import os
import sys
import tempfile
import unittest
from contextlib import redirect_stdout, redirect_stderr
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from llmdev import bench, lab
import llmdev.cli as cli


class TestLab(unittest.TestCase):
    def test_slope_tps(self):
        # Test with points (1000, 1.0), (2000, 2.0), (3000, 3.0)
        points = [(1000, 1.0), (2000, 2.0), (3000, 3.0)]
        self.assertEqual(lab.slope_tps(points), 1000.0)

        # Test with one point
        self.assertIsNone(lab.slope_tps([(1000, 1.0)]))

        # Test with flat points (b <= 0)
        self.assertIsNone(lab.slope_tps([(1000, 1.0), (2000, 1.0)]))

    def test_sweep(self):
        # Fake run function
        call_count = [0]
        seed_values = []
        n_words_values = []

        def fake_run(m, n_words, max_tokens, seed):
            call_count[0] += 1
            seed_values.append(seed)
            n_words_values.append(n_words)
            return {
                "ttft_s": n_words / 1000,
                "decode_tps": 10.0,
                "prompt_tokens": n_words,
                "model": "test",
                "backend": "ollama",
                "n_words": n_words,
            }

        from llmdev import registry
        m = registry.Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=65536,
            port=11434,
        )

        seed = 42
        rows = lab.sweep(m, seed=seed, run=fake_run)

        # Check number of calls (1 for load + 4 for sweep words)
        self.assertEqual(call_count[0], 5)

        # Check seed values
        self.assertEqual(seed_values, [seed] * 5)

        # Check first call was 200 words
        self.assertEqual(n_words_values[0], 200)

        # Check load_s is from first call
        self.assertEqual(rows[0]["load_s"], 0.2)  # 200/1000

        # Check sweep rows
        self.assertEqual(len(rows), 4)
        self.assertEqual(rows[0]["n_words"], 3000)
        self.assertEqual(rows[0]["seed"], seed)

    def test_summarize_skips_rows_without_ttft(self):
        rows = [
            {"model": "m1", "backend": "ollama", "ttft_s": 1.0, "prompt_tokens": 1000},
            {"model": "m1", "backend": "ollama", "ttft_s": None, "prompt_tokens": 1500},
            {"model": "m1", "backend": "ollama", "ttft_s": 2.0, "prompt_tokens": 2000},
        ]
        self.assertEqual(lab.summarize(rows)["prefill_tps"], 1000.0)

    def test_summarize(self):
        # Test with even number of decode values
        rows = [
            {"model": "m1", "backend": "ollama", "decode_tps": 10.0, "ttft_s": 1.0, "prompt_tokens": 1000},
            {"model": "m1", "backend": "ollama", "decode_tps": 20.0, "ttft_s": 2.0, "prompt_tokens": 2000},
        ]
        summary = lab.summarize(rows)
        self.assertEqual(summary["decode_tps"], 15.0)

        # Test with odd number of decode values
        rows = [
            {"model": "m1", "backend": "ollama", "decode_tps": 10.0, "ttft_s": 1.0, "prompt_tokens": 1000},
            {"model": "m1", "backend": "ollama", "decode_tps": 20.0, "ttft_s": 2.0, "prompt_tokens": 2000},
            {"model": "m1", "backend": "ollama", "decode_tps": 30.0, "ttft_s": 3.0, "prompt_tokens": 3000},
        ]
        summary = lab.summarize(rows)
        self.assertEqual(summary["decode_tps"], 20.0)

        # Test with all None decode values
        rows = [
            {"model": "m1", "backend": "ollama", "decode_tps": None, "ttft_s": 1.0, "prompt_tokens": 1000},
        ]
        summary = lab.summarize(rows)
        self.assertIsNone(summary["decode_tps"])

    def test_read_rows(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, "test.jsonl")
            with open(path, "w") as f:
                f.write(json.dumps({"a": 1}) + "\n")
                f.write(json.dumps({"a": 2}) + "\n")

            rows = lab.read_rows(path)
            self.assertEqual(len(rows), 2)
            self.assertEqual(rows[0]["a"], 1)
            self.assertEqual(rows[1]["a"], 2)

            # Test missing file
            missing_path = os.path.join(tmpdir, "missing.jsonl")
            rows = lab.read_rows(missing_path)
            self.assertEqual(rows, [])

    def test_latest_sweeps(self):
        rows = [
            {"model": "m1", "backend": "ollama", "sweep": 1, "decode_tps": 10.0, "prompt_tokens": 1000},
            {"model": "m1", "backend": "ollama", "sweep": 2, "decode_tps": 20.0, "prompt_tokens": 2000},
            {"model": "m2", "backend": "llama", "sweep": 1, "decode_tps": 15.0, "prompt_tokens": 1500},
            {"model": "m2", "backend": "llama", "decode_tps": 25.0, "prompt_tokens": 2500},  # no sweep key
        ]

        summaries = lab.latest_sweeps(rows)
        self.assertEqual(len(summaries), 2)

        # m1 should have sweep=2
        m1_summary = next(s for s in summaries if s["model"] == "m1")
        self.assertEqual(m1_summary["sweep"], 2)
        self.assertEqual(m1_summary["decode_tps"], 20.0)

        # m2 should have sweep=1
        m2_summary = next(s for s in summaries if s["model"] == "m2")
        self.assertEqual(m2_summary["sweep"], 1)
        self.assertEqual(m2_summary["decode_tps"], 15.0)

    def test_format_table(self):
        # Test empty
        self.assertEqual(lab.format_table([]), "no sweeps yet")

        # Test with data
        summaries = [
            {"model": "m1", "backend": "ollama", "prefill_tps": 1000.0, "decode_tps": 20.0, "load_s": 1.5, "ttft_max_s": 2.0, "sweep": 1},
        ]
        table = lab.format_table(summaries)
        lines = table.split("\n")
        self.assertEqual(len(lines), 2)
        self.assertFalse(lines[0].endswith(" "))
        self.assertFalse(lines[1].endswith(" "))

    def test_bench_run_seed(self):
        # Test that bench.run passes seed to prompt
        from llmdev import registry
        m = registry.Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=65536,
            port=11434,
        )

        captured_prompt = []

        def fake_post(url, payload):
            captured_prompt.append(payload.get("messages", [{}])[0].get("content", ""))
            return iter([])

        bench.run(m, n_words=10, max_tokens=16, post=fake_post, seed=42)
        self.assertIn("Summarise", captured_prompt[0])

    def test_cli_sweep(self):
        row = {"model": "m1", "backend": "ollama", "decode_tps": 20.0, "prompt_tokens": 1000, "ttft_s": 1.0}
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "models.toml").write_text("[models.m1]\nbackend = \"ollama\"\nmodel = \"x\"\nctx = 4096\nport = 11434\n")
            with patch("llmdev.cli.ROOT", Path(tmpdir)), patch("llmdev.cli.server.health", return_value=True), patch("llmdev.cli.lab.sweep", return_value=[row]):
                with redirect_stdout(StringIO()):
                    ret = cli.main(["sweep", "m1"])
            self.assertEqual(ret, 0)
            lines = Path(tmpdir, "runs", "bench.jsonl").read_text().splitlines()
            self.assertEqual(len(lines), 1)
            self.assertIn("sweep", json.loads(lines[0]))

    def test_cli_sweep_unhealthy(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "models.toml").write_text("[models.m1]\nbackend = \"ollama\"\nmodel = \"x\"\nctx = 4096\nport = 11434\n")
            with patch("llmdev.cli.ROOT", Path(tmpdir)), patch("llmdev.cli.server.health", return_value=False), patch("llmdev.cli.lab.sweep") as mock_sweep:
                with redirect_stderr(StringIO()):
                    ret = cli.main(["sweep", "m1"])
            self.assertEqual(ret, 1)
            mock_sweep.assert_not_called()

    def test_cli_results(self):
        row = {"model": "m1", "backend": "ollama", "decode_tps": 20.0, "prompt_tokens": 1000, "ttft_s": 1.0, "load_s": 2.0, "sweep": "2026-01-01T00:00:00"}
        with tempfile.TemporaryDirectory() as tmpdir:
            Path(tmpdir, "models.toml").write_text("[models.m1]\nbackend = \"ollama\"\nmodel = \"x\"\nctx = 4096\nport = 11434\n")
            Path(tmpdir, "runs").mkdir()
            Path(tmpdir, "runs", "bench.jsonl").write_text(json.dumps(row) + "\n")
            out = StringIO()
            with patch("llmdev.cli.ROOT", Path(tmpdir)), redirect_stdout(out):
                ret = cli.main(["results"])
            self.assertEqual(ret, 0)
            self.assertIn("m1", out.getvalue())


if __name__ == "__main__":
    unittest.main()
