import os
import subprocess
import tempfile
import unittest
from datetime import datetime

from llmdev.cards import Card
from llmdev.registry import Model
from llmdev.runner import changed_paths, empty_files, run_card


class TestChangedPaths(unittest.TestCase):
    def test_changed_paths_with_files(self):
        def fake_run(cmd, **kwargs):
            result = type('obj', (object,), {
                'returncode': 0,
                'stdout': " M a.py\0?? But wait, a file\0",
                'stderr': '',
            })()
            return result

        paths = changed_paths("/tmp", run=fake_run)
        self.assertEqual(paths, {"a.py", "But wait, a file"})

    def test_changed_paths_empty(self):
        def fake_run(cmd, **kwargs):
            result = type('obj', (object,), {
                'returncode': 0,
                'stdout': "",
                'stderr': '',
            })()
            return result

        paths = changed_paths("/tmp", run=fake_run)
        self.assertEqual(paths, set())

    def test_changed_paths_single_file(self):
        def fake_run(cmd, **kwargs):
            result = type('obj', (object,), {
                'returncode': 0,
                'stdout': " M single.py\0",
                'stderr': '',
            })()
            return result

        paths = changed_paths("/tmp", run=fake_run)
        self.assertEqual(paths, {"single.py"})


class TestEmptyFiles(unittest.TestCase):
    def test_empty_files_missing(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("missing.py",),
            read=(),
            checks=(),
            commit="feat: test",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            empty = empty_files(card, tmpdir)
            self.assertEqual(empty, ["missing.py"])

    def test_empty_files_empty(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("empty.py",),
            read=(),
            checks=(),
            commit="feat: test",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            empty_path = os.path.join(tmpdir, "empty.py")
            with open(empty_path, "w") as f:
                f.write("")
            empty = empty_files(card, tmpdir)
            self.assertEqual(empty, ["empty.py"])

    def test_empty_files_content(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("content.py",),
            read=(),
            checks=(),
            commit="feat: test",
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            content_path = os.path.join(tmpdir, "content.py")
            with open(content_path, "w") as f:
                f.write("hello")
            empty = empty_files(card, tmpdir)
            self.assertEqual(empty, [])


class TestRunCardGuards(unittest.TestCase):
    def test_run_card_all_good(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=("echo test",),
            commit="feat: test",
        )

        m = Model(
            name="test",
            backend="ollama",
            model="qwen3-coder-next",
            ctx=4096,
            port=11434,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = tmpdir
            runs_dir = os.path.join(tmpdir, "runs")
            os.makedirs(runs_dir)
            with open(os.path.join(repo, "file1.py"), "w") as f:
                f.write("x")

            calls = []

            def fake_run(cmd, **kwargs):
                if isinstance(cmd, list) and cmd[0] == "git" and cmd[1] == "status":
                    if len(calls) == 0:
                        stdout = " M file1.py\0"
                    else:
                        stdout = ""
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': stdout,
                        'stderr': '',
                    })()
                elif isinstance(cmd, list) and cmd[:2] == ["git", "diff"]:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'DIFF',
                        'stderr': '',
                    })()
                else:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'success',
                        'stderr': '',
                    })()
                calls.append((cmd, kwargs))
                return result

            def fake_now():
                return datetime(2024, 1, 1, 12, 0, 0)

            meta = run_card(
                card, m, "http://127.0.0.1:11434/v1", repo, runs_dir,
                run=fake_run, now=fake_now
            )

            self.assertTrue(meta["passed"])
            self.assertFalse(meta["timed_out"])
            self.assertEqual(meta["empty_files"], [])
            self.assertEqual(meta["stray_files"], [])

    def test_run_card_stray_files(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=("echo test",),
            commit="feat: test",
        )

        m = Model(
            name="test",
            backend="ollama",
            model="qwen3-coder-next",
            ctx=4096,
            port=11434,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = tmpdir
            runs_dir = os.path.join(tmpdir, "runs")
            os.makedirs(runs_dir)
            with open(os.path.join(repo, "file1.py"), "w") as f:
                f.write("x")

            calls = []

            def fake_run(cmd, **kwargs):
                if isinstance(cmd, list) and cmd[0] == "git" and cmd[1] == "status":
                    if len(calls) == 0:
                        stdout = " M file1.py\0"
                    else:
                        stdout = " M file1.py\0?? stray.txt\0"
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': stdout,
                        'stderr': '',
                    })()
                elif isinstance(cmd, list) and cmd[:2] == ["git", "diff"]:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'DIFF',
                        'stderr': '',
                    })()
                else:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'success',
                        'stderr': '',
                    })()
                calls.append((cmd, kwargs))
                return result

            def fake_now():
                return datetime(2024, 1, 1, 12, 0, 0)

            meta = run_card(
                card, m, "http://127.0.0.1:11434/v1", repo, runs_dir,
                run=fake_run, now=fake_now
            )

            self.assertFalse(meta["passed"])
            self.assertFalse(meta["timed_out"])
            self.assertEqual(meta["empty_files"], [])
            self.assertEqual(meta["stray_files"], ["stray.txt"])

    def test_run_card_stray_file_in_edit(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=("echo test",),
            commit="feat: test",
        )

        m = Model(
            name="test",
            backend="ollama",
            model="qwen3-coder-next",
            ctx=4096,
            port=11434,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = tmpdir
            runs_dir = os.path.join(tmpdir, "runs")
            os.makedirs(runs_dir)
            with open(os.path.join(repo, "file1.py"), "w") as f:
                f.write("x")

            calls = []

            def fake_run(cmd, **kwargs):
                if isinstance(cmd, list) and cmd[0] == "git" and cmd[1] == "status":
                    if len(calls) == 0:
                        stdout = " M file1.py\0"
                    else:
                        stdout = " M file1.py\0?? file1.py\0"
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': stdout,
                        'stderr': '',
                    })()
                elif isinstance(cmd, list) and cmd[:2] == ["git", "diff"]:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'DIFF',
                        'stderr': '',
                    })()
                else:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'success',
                        'stderr': '',
                    })()
                calls.append((cmd, kwargs))
                return result

            def fake_now():
                return datetime(2024, 1, 1, 12, 0, 0)

            meta = run_card(
                card, m, "http://127.0.0.1:11434/v1", repo, runs_dir,
                run=fake_run, now=fake_now
            )

            self.assertTrue(meta["passed"])
            self.assertFalse(meta["timed_out"])
            self.assertEqual(meta["empty_files"], [])
            self.assertEqual(meta["stray_files"], [])

    def test_run_card_stray_file_before(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=("echo test",),
            commit="feat: test",
        )

        m = Model(
            name="test",
            backend="ollama",
            model="qwen3-coder-next",
            ctx=4096,
            port=11434,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = tmpdir
            runs_dir = os.path.join(tmpdir, "runs")
            os.makedirs(runs_dir)
            with open(os.path.join(repo, "file1.py"), "w") as f:
                f.write("x")
            with open(os.path.join(repo, "pre.txt"), "w") as f:
                f.write("pre")

            calls = []

            def fake_run(cmd, **kwargs):
                if isinstance(cmd, list) and cmd[0] == "git" and cmd[1] == "status":
                    if len(calls) == 0:
                        stdout = " M file1.py\0 M pre.txt\0"
                    else:
                        stdout = " M file1.py\0"
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': stdout,
                        'stderr': '',
                    })()
                elif isinstance(cmd, list) and cmd[:2] == ["git", "diff"]:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'DIFF',
                        'stderr': '',
                    })()
                else:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'success',
                        'stderr': '',
                    })()
                calls.append((cmd, kwargs))
                return result

            def fake_now():
                return datetime(2024, 1, 1, 12, 0, 0)

            meta = run_card(
                card, m, "http://127.0.0.1:11434/v1", repo, runs_dir,
                run=fake_run, now=fake_now
            )

            self.assertTrue(meta["passed"])
            self.assertFalse(meta["timed_out"])
            self.assertEqual(meta["empty_files"], [])
            self.assertEqual(meta["stray_files"], [])

    def test_run_card_empty_files(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=("echo test",),
            commit="feat: test",
        )

        m = Model(
            name="test",
            backend="ollama",
            model="qwen3-coder-next",
            ctx=4096,
            port=11434,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = tmpdir
            runs_dir = os.path.join(tmpdir, "runs")
            os.makedirs(runs_dir)
            with open(os.path.join(repo, "file1.py"), "w") as f:
                f.write("")

            calls = []

            def fake_run(cmd, **kwargs):
                if isinstance(cmd, list) and cmd[0] == "git" and cmd[1] == "status":
                    if len(calls) == 0:
                        stdout = " M file1.py\0"
                    else:
                        stdout = ""
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': stdout,
                        'stderr': '',
                    })()
                elif isinstance(cmd, list) and cmd[:2] == ["git", "diff"]:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'DIFF',
                        'stderr': '',
                    })()
                else:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'success',
                        'stderr': '',
                    })()
                calls.append((cmd, kwargs))
                return result

            def fake_now():
                return datetime(2024, 1, 1, 12, 0, 0)

            meta = run_card(
                card, m, "http://127.0.0.1:11434/v1", repo, runs_dir,
                run=fake_run, now=fake_now
            )

            self.assertFalse(meta["passed"])
            self.assertFalse(meta["timed_out"])
            self.assertEqual(meta["empty_files"], ["file1.py"])
            self.assertEqual(meta["stray_files"], [])

    def test_run_card_timeout(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=("echo test",),
            commit="feat: test",
        )

        m = Model(
            name="test",
            backend="ollama",
            model="qwen3-coder-next",
            ctx=4096,
            port=11434,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = tmpdir
            runs_dir = os.path.join(tmpdir, "runs")
            os.makedirs(runs_dir)
            with open(os.path.join(repo, "file1.py"), "w") as f:
                f.write("x")

            calls = []

            def fake_run(cmd, **kwargs):
                if isinstance(cmd, list) and cmd[0] == "git" and cmd[1] == "status":
                    if len(calls) == 0:
                        stdout = " M file1.py\0"
                    else:
                        stdout = ""
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': stdout,
                        'stderr': '',
                    })()
                elif isinstance(cmd, list) and cmd[:2] == ["git", "diff"]:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'DIFF',
                        'stderr': '',
                    })()
                elif isinstance(cmd, list) and cmd[0] == "aider":
                    calls.append((cmd, kwargs))
                    raise subprocess.TimeoutExpired(cmd, timeout=2400)
                else:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'success',
                        'stderr': '',
                    })()
                calls.append((cmd, kwargs))
                return result

            def fake_now():
                return datetime(2024, 1, 1, 12, 0, 0)

            meta = run_card(
                card, m, "http://127.0.0.1:11434/v1", repo, runs_dir,
                run=fake_run, now=fake_now
            )

            self.assertFalse(meta["passed"])
            self.assertTrue(meta["timed_out"])
            self.assertIsNone(meta["aider_returncode"])
            self.assertEqual(meta["empty_files"], [])
            self.assertEqual(meta["stray_files"], [])

            run_dir = os.path.join(runs_dir, "20240101-120000-001")
            self.assertTrue(os.path.exists(os.path.join(run_dir, "meta.json")))
            self.assertTrue(os.path.exists(os.path.join(run_dir, "diff.patch")))

            # Check timeout was passed
            aider_call = [c for c in calls if isinstance(c[0], list) and c[0][0] == "aider"][0]
            self.assertEqual(aider_call[1]["timeout"], 2400)

    def test_run_card_timeout_custom(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=("echo test",),
            commit="feat: test",
        )

        m = Model(
            name="test",
            backend="ollama",
            model="qwen3-coder-next",
            ctx=4096,
            port=11434,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = tmpdir
            runs_dir = os.path.join(tmpdir, "runs")
            os.makedirs(runs_dir)
            with open(os.path.join(repo, "file1.py"), "w") as f:
                f.write("x")

            calls = []

            def fake_run(cmd, **kwargs):
                if isinstance(cmd, list) and cmd[0] == "git" and cmd[1] == "status":
                    if len(calls) == 0:
                        stdout = " M file1.py\0"
                    else:
                        stdout = ""
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': stdout,
                        'stderr': '',
                    })()
                elif isinstance(cmd, list) and cmd[:2] == ["git", "diff"]:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'DIFF',
                        'stderr': '',
                    })()
                elif isinstance(cmd, list) and cmd[0] == "aider":
                    calls.append((cmd, kwargs))
                    raise subprocess.TimeoutExpired(cmd, timeout=5)
                else:
                    result = type('obj', (object,), {
                        'returncode': 0,
                        'stdout': 'success',
                        'stderr': '',
                    })()
                calls.append((cmd, kwargs))
                return result

            def fake_now():
                return datetime(2024, 1, 1, 12, 0, 0)

            meta = run_card(
                card, m, "http://127.0.0.1:11434/v1", repo, runs_dir,
                run=fake_run, now=fake_now, timeout_s=5
            )

            self.assertFalse(meta["passed"])
            self.assertTrue(meta["timed_out"])

            aider_call = [c for c in calls if isinstance(c[0], list) and c[0][0] == "aider"][0]
            self.assertEqual(aider_call[1]["timeout"], 5)

    def test_cli_run_timeout(self):
        from pathlib import Path
        from unittest.mock import patch
        from llmdev import cli
        with tempfile.TemporaryDirectory() as tmp:
            Path(tmp, "models.toml").write_text("[models.m1]\nbackend = \"ollama\"\nmodel = \"x\"\nctx = 4096\nport = 11434\n")
            with patch("llmdev.cli.ROOT", Path(tmp)), patch("llmdev.cli.server.health", return_value=True), patch("llmdev.cli.cards.parse"), patch("llmdev.cli.runner.run_card", return_value={"passed": True}) as run_card, patch("builtins.print"):
                self.assertEqual(cli.main(["run", "c.md", "--model", "m1", "--timeout", "5"]), 0)
        self.assertEqual(run_card.call_args.kwargs["timeout_s"], 5)


if __name__ == "__main__":
    unittest.main()
