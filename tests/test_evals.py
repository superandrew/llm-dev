import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from llmdev import cards, evals, metrics, runner


class TestHiddenScore(unittest.TestCase):
    def test_all_passed(self):
        output = "Ran 10 tests in 0.1s\n\nOK"
        passed, total = evals.hidden_score(output)
        self.assertEqual((passed, total), (10, 10))

    def test_single_test(self):
        output = "Ran 1 test in 0.1s\n\nOK"
        passed, total = evals.hidden_score(output)
        self.assertEqual((passed, total), (1, 1))

    def test_some_failed(self):
        output = "Ran 10 tests in 0.1s\n\nFAILED (failures=2, errors=1)"
        passed, total = evals.hidden_score(output)
        self.assertEqual((passed, total), (7, 10))

    def test_errors_only(self):
        output = "Ran 5 tests\n\nFAILED (errors=3)"
        passed, total = evals.hidden_score(output)
        self.assertEqual((passed, total), (2, 5))

    def test_no_ran_line(self):
        output = "FAILED (errors=1)"
        passed, total = evals.hidden_score(output)
        self.assertEqual((passed, total), (0, 0))


class TestRunEval(unittest.TestCase):
    def test_missing_eval_raises(self):
        with self.assertRaises(cards.CardError):
            evals.run_eval(
                name="nonexistent",
                m=type("Model", (), {"name": "test", "backend": "ollama"})(),
                base_url="http://localhost:11434",
                root="/tmp",
                runs_dir="/tmp/runs",
            )

    def test_run_eval_flow(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup eval directory
            evals_dir = os.path.join(tmpdir, "evals", "demo", "seed", "cards")
            os.makedirs(evals_dir)
            task_path = os.path.join(evals_dir, "task.md")
            with open(task_path, "w") as f:
                f.write("+++\nid = \"task\"\ntitle = \"Task\"\nedit = []\nchecks = [\"true\"]\ncommit = \"task\"\n+++\n")

            with open(os.path.join(os.path.join(tmpdir, "evals", "demo", "seed"), "a.txt"), "w") as f:
                f.write("content")

            hidden_dir = os.path.join(tmpdir, "evals", "demo", "hidden")
            os.makedirs(hidden_dir)
            with open(os.path.join(hidden_dir, "test_x.py"), "w") as f:
                f.write("import unittest\n\nclass TestX(unittest.TestCase):\n    def test_x(self):\n        self.assertTrue(True)\n")

            # Setup repo directory
            repo_dir = os.path.join(tmpdir, "repo")
            os.makedirs(repo_dir)

            # Setup runs directory
            runs_dir = os.path.join(tmpdir, "runs")
            os.makedirs(runs_dir)

            # Create meta.json with run_dir
            meta_dir = os.path.join(runs_dir, "20240101-000000-task")
            os.makedirs(meta_dir)
            with open(os.path.join(meta_dir, "meta.json"), "w") as f:
                json.dump({"run_dir": meta_dir, "passed": True, "timed_out": False, "empty_files": [], "stray_files": []}, f)

            # Create aider.md
            with open(os.path.join(meta_dir, "aider.md"), "w") as f:
                f.write("> Tokens: 1k sent, 2k received.\n")

            # Fake run function
            commands_run = []

            def fake_run(cmd, *args, **kwargs):
                commands_run.append(cmd)
                if cmd[0] == "git":
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                elif cmd[0] == "python3" and "unittest" in cmd:
                    return subprocess.CompletedProcess(cmd, 1, "Ran 4 tests in 0.1s\n\nFAILED (failures=1)", "")
                else:
                    return subprocess.CompletedProcess(cmd, 0, "", "")

            # Fake run_card function
            def fake_run_card(card, *args, **kwargs):
                return {"passed": True, "timed_out": False, "empty_files": [], "stray_files": [], "run_dir": meta_dir}

            row = evals.run_eval(
                name="demo",
                m=type("Model", (), {"name": "test", "backend": "ollama"})(),
                base_url="http://localhost:11434",
                root=tmpdir,
                runs_dir=runs_dir,
                run=fake_run,
                run_card=fake_run_card,
            )

            # Check git commands came first and in order
            self.assertEqual(commands_run[0], ["git", "init", "-q"])
            self.assertEqual(commands_run[1], ["git", "add", "-A"])
            self.assertEqual(commands_run[2], ["git", "-c", "user.name=eval", "-c", "user.email=eval@local", "commit", "-q", "-m", "seed"])

            # Check card path and id
            self.assertEqual(row["eval"], "demo")
            self.assertEqual(row["model"], "test")
            self.assertEqual(row["backend"], "ollama")
            self.assertEqual(row["harness"], "aider")
            self.assertEqual(row["passed"], True)
            self.assertEqual(row["hidden_passed"], 3)
            self.assertEqual(row["hidden_total"], 4)
            self.assertEqual(row["rounds"], 1)
            self.assertEqual(row["sent"], 1000)
            self.assertEqual(row["received"], 2000)

    def test_run_eval_with_harness(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            # Setup eval directory
            evals_dir = os.path.join(tmpdir, "evals", "demo", "seed", "cards")
            os.makedirs(evals_dir)
            task_path = os.path.join(evals_dir, "task.md")
            with open(task_path, "w") as f:
                f.write("+++\nid = \"task\"\ntitle = \"Task\"\nedit = []\nchecks = [\"true\"]\ncommit = \"task\"\n+++\n")

            with open(os.path.join(os.path.join(tmpdir, "evals", "demo", "seed"), "a.txt"), "w") as f:
                f.write("content")

            hidden_dir = os.path.join(tmpdir, "evals", "demo", "hidden")
            os.makedirs(hidden_dir)
            with open(os.path.join(hidden_dir, "test_x.py"), "w") as f:
                f.write("import unittest\n\nclass TestX(unittest.TestCase):\n    def test_x(self):\n        self.assertTrue(True)\n")

            # Setup repo directory
            repo_dir = os.path.join(tmpdir, "repo")
            os.makedirs(repo_dir)

            # Setup runs directory
            runs_dir = os.path.join(tmpdir, "runs")
            os.makedirs(runs_dir)

            # Create meta.json with run_dir
            meta_dir = os.path.join(runs_dir, "20240101-000000-task")
            os.makedirs(meta_dir)
            with open(os.path.join(meta_dir, "meta.json"), "w") as f:
                json.dump({"run_dir": meta_dir, "passed": True, "timed_out": False, "empty_files": [], "stray_files": []}, f)

            # Create aider.md
            with open(os.path.join(meta_dir, "aider.md"), "w") as f:
                f.write("> Tokens: 1k sent, 2k received.\n")

            # Fake run function
            commands_run = []

            def fake_run(cmd, *args, **kwargs):
                commands_run.append(cmd)
                if cmd[0] == "git":
                    return subprocess.CompletedProcess(cmd, 0, "", "")
                elif cmd[0] == "python3" and "unittest" in cmd:
                    return subprocess.CompletedProcess(cmd, 1, "Ran 4 tests in 0.1s\n\nFAILED (failures=1)", "")
                else:
                    return subprocess.CompletedProcess(cmd, 0, "", "")

            # Fake run_card function
            received_kwargs = {}

            def fake_run_card(card, *args, **kwargs):
                received_kwargs.update(kwargs)
                return {"passed": True, "timed_out": False, "empty_files": [], "stray_files": [], "run_dir": meta_dir}

            row = evals.run_eval(
                name="demo",
                m=type("Model", (), {"name": "test", "backend": "ollama"})(),
                base_url="http://localhost:11434",
                root=tmpdir,
                runs_dir=runs_dir,
                run=fake_run,
                run_card=fake_run_card,
                harness="qwen",
            )

            # Check harness was passed to run_card
            self.assertEqual(received_kwargs.get("harness"), "qwen")

            # Check row has harness
            self.assertEqual(row["harness"], "qwen")


class TestReadEvals(unittest.TestCase):
    def test_missing_file(self):
        rows = evals.read_evals("/tmp/nonexistent/eval.jsonl")
        self.assertEqual(rows, [])


class TestFormatEvals(unittest.TestCase):
    def test_empty(self):
        result = evals.format_evals([])
        self.assertEqual(result, "no evals yet")

    def test_with_rows(self):
        rows = [
            {
                "eval": "demo",
                "model": "test",
                "backend": "ollama",
                "passed": True,
                "hidden_passed": 3,
                "hidden_total": 4,
                "duration_s": 10,
                "rounds": 1,
                "sent": 1000,
                "received": 2000,
                "timed_out": False,
                "stray": 0,
                "empty": 0,
                "run": "20240101-000000-demo",
            }
        ]
        result = evals.format_evals(rows)
        self.assertIn("demo", result)
        self.assertIn("3/4", result)
        self.assertNotIn(" \n", result)  # No trailing spaces

    def test_none_values(self):
        rows = [
            {
                "eval": "demo",
                "model": None,
                "backend": None,
                "passed": None,
                "hidden_passed": None,
                "hidden_total": None,
                "duration_s": None,
                "rounds": None,
                "sent": None,
                "received": None,
                "timed_out": None,
                "stray": None,
                "empty": None,
                "run": None,
            }
        ]
        result = evals.format_evals(rows)
        self.assertIn("-", result)

    def test_format_evals_with_harness(self):
        rows = [
            {"eval": "e", "model": "m", "backend": "mlx", "harness": "qwen"}
        ]
        result = evals.format_evals(rows)
        self.assertIn("m+qwen", result)

    def test_format_evals_without_harness(self):
        rows = [
            {"eval": "e", "model": "m", "backend": "mlx"}
        ]
        result = evals.format_evals(rows)
        self.assertNotIn("+", result)
