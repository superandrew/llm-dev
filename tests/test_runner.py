import json
import os
import tempfile
import unittest
from datetime import datetime

from llmdev.cards import Card, CardError, parse
from llmdev.runner import (
    BASE_FLAGS,
    aider_command,
    aider_model,
    agent_command,
    agent_message,
    default_message,
    run_card,
    run_checks,
)


class TestCardParsing(unittest.TestCase):
    def test_parse_valid_card(self):
        toml_content = """+++
id = "001"
title = "Test Card"
edit = ["file1.py", "file2.py"]
read = ["readme.md"]
checks = ["python3 -m unittest"]
commit = "feat: test"
+++

Markdown content here"""

        with tempfile.TemporaryDirectory() as tmpdir:
            card_path = os.path.join(tmpdir, "test.md")
            with open(card_path, "w") as f:
                f.write(toml_content)

            card = parse(card_path)

            self.assertEqual(card.id, "001")
            self.assertEqual(card.title, "Test Card")
            self.assertEqual(card.edit, ("file1.py", "file2.py"))
            self.assertEqual(card.read, ("readme.md",))
            self.assertEqual(card.checks, ("python3 -m unittest",))
            self.assertEqual(card.commit, "feat: test")
            self.assertEqual(card.edit_format, "")
            self.assertEqual(card.path, card_path)

    def test_parse_missing_keys(self):
        toml_content = """+++
id = "001"
title = "Test Card"
+++

Markdown content"""

        with tempfile.TemporaryDirectory() as tmpdir:
            card_path = os.path.join(tmpdir, "test.md")
            with open(card_path, "w") as f:
                f.write(toml_content)

            with self.assertRaises(CardError) as cm:
                parse(card_path)

            self.assertIn("missing required key", str(cm.exception))

    def test_parse_missing_plus_plus_plus(self):
        toml_content = """id = "001"
title = "Test Card"
edit = ["file1.py"]
checks = ["echo test"]
commit = "feat: test"

Markdown content"""

        with tempfile.TemporaryDirectory() as tmpdir:
            card_path = os.path.join(tmpdir, "test.md")
            with open(card_path, "w") as f:
                f.write(toml_content)

            with self.assertRaises(CardError) as cm:
                parse(card_path)

            self.assertIn("missing opening +++", str(cm.exception))

    def test_parse_missing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            card_path = os.path.join(tmpdir, "nonexistent.md")

            with self.assertRaises(CardError) as cm:
                parse(card_path)

            self.assertIn("cannot read card", str(cm.exception))
            self.assertIn(card_path, str(cm.exception))


class TestAiderModel(unittest.TestCase):
    def test_ollama_model(self):
        from llmdev.registry import Model
        m = Model(
            name="test",
            backend="ollama",
            model="qwen3-coder-next",
            ctx=4096,
            port=11434,
        )
        model_str, env = aider_model(m, "http://127.0.0.1:11434/v1")
        self.assertEqual(model_str, "ollama_chat/qwen3-coder-next")
        self.assertEqual(env, {"OLLAMA_API_BASE": "http://127.0.0.1:11434"})

    def test_llama_model(self):
        from llmdev.registry import Model
        m = Model(
            name="test",
            backend="llama",
            model="~/models/llama-7b",
            ctx=4096,
            port=8080,
        )
        model_str, env = aider_model(m, "http://127.0.0.1:8080/v1")
        self.assertEqual(model_str, "openai/~/models/llama-7b")
        self.assertEqual(env, {
            "OPENAI_API_BASE": "http://127.0.0.1:8080/v1",
            "OPENAI_API_KEY": "local",
        })

    def test_mlx_model(self):
        from llmdev.registry import Model
        m = Model(
            name="test",
            backend="mlx",
            model="mlx-community/Llama-3-8B",
            ctx=4096,
            port=8080,
        )
        model_str, env = aider_model(m, "http://127.0.0.1:8080/v1")
        self.assertEqual(model_str, "openai/mlx-community/Llama-3-8B")
        self.assertEqual(env, {
            "OPENAI_API_BASE": "http://127.0.0.1:8080/v1",
            "OPENAI_API_KEY": "local",
        })


class TestDefaultMessage(unittest.TestCase):
    def test_default_message(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=(),
            commit="feat: test",
        )
        msg = default_message(card)
        self.assertIn("Implement card 001", msg)
        self.assertIn("file1.py", msg)


class TestAiderCommand(unittest.TestCase):
    def test_aider_command_ollama(self):
        from llmdev.registry import Model
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
        cmd, env = aider_command(card, m, "http://127.0.0.1:11434/v1", "history.md")

        self.assertEqual(cmd[:3], ["aider", "--model", "ollama_chat/qwen3-coder-next"])
        self.assertIn("--chat-history-file", cmd)
        self.assertIn("history.md", cmd)
        self.assertIn("--read", cmd)
        self.assertIn("--test-cmd", cmd)
        self.assertIn("--auto-test", cmd)
        self.assertIn("--message", cmd)

    def test_aider_command_llama(self):
        from llmdev.registry import Model
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=(),
            commit="feat: test",
        )
        m = Model(
            name="test",
            backend="llama",
            model="~/models/llama",
            ctx=4096,
            port=8080,
        )
        cmd, env = aider_command(card, m, "http://127.0.0.1:8080/v1", "history.md")

        self.assertEqual(cmd[:3], ["aider", "--model", "openai/~/models/llama"])

    def test_aider_command_with_edit_format(self):
        from llmdev.registry import Model
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=(),
            commit="feat: test",
            edit_format="diff",
        )
        m = Model(
            name="test",
            backend="ollama",
            model="qwen3-coder-next",
            ctx=4096,
            port=11434,
        )
        cmd, env = aider_command(card, m, "http://127.0.0.1:11434/v1", "history.md")

        self.assertEqual(cmd[3:5], ["--edit-format", "diff"])

    def test_aider_command_with_extra_message(self):
        from llmdev.registry import Model
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=(),
            commit="feat: test",
        )
        m = Model(
            name="test",
            backend="ollama",
            model="qwen3-coder-next",
            ctx=4096,
            port=11434,
        )
        cmd, env = aider_command(card, m, "http://127.0.0.1:11434/v1", "history.md", "extra message")

        self.assertIn("extra message", cmd)


class TestRunChecks(unittest.TestCase):
    def test_run_checks_success(self):
        def fake_run(cmd, **kwargs):
            result = type('obj', (object,), {
                'returncode': 0,
                'stdout': 'hello\n',
                'stderr': '',
            })()
            return result

        checks = ("echo hello",)
        results = run_checks(checks, "/tmp", run=fake_run)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["cmd"], "echo hello")
        self.assertEqual(results[0]["returncode"], 0)
        self.assertIn("hello", results[0]["output"])

    def test_run_checks_failure(self):
        def fake_run(cmd, **kwargs):
            result = type('obj', (object,), {
                'returncode': 1,
                'stdout': '',
                'stderr': 'error\n',
            })()
            return result

        checks = ("exit 1",)
        results = run_checks(checks, "/tmp", run=fake_run)

        self.assertEqual(results[0]["returncode"], 1)

    def test_run_checks_output_truncation(self):
        def fake_run(cmd, **kwargs):
            result = type('obj', (object,), {
                'returncode': 0,
                'stdout': 'a' * 5000,
                'stderr': 'b' * 5000,
            })()
            return result

        checks = ("test",)
        results = run_checks(checks, "/tmp", run=fake_run)

        self.assertEqual(len(results[0]["output"]), 4000)


class TestStripTrailingSpaces(unittest.TestCase):
    def test_strip_trailing_spaces_multiple_lines(self):
        import re
        from llmdev.runner import strip_trailing_spaces

        with tempfile.TemporaryDirectory() as tmpdir:
            a_py = os.path.join(tmpdir, "a.py")
            with open(a_py, "w", encoding="utf-8", newline="") as f:
                f.write("x = 1   \n\n    \ny = 2\t\n")

            result = strip_trailing_spaces(tmpdir, ["a.py"])

            self.assertEqual(result, ["a.py"])
            with open(a_py, "r", encoding="utf-8", newline="") as f:
                content = f.read()
            self.assertEqual(content, "x = 1\n\n\ny = 2\n")

    def test_strip_trailing_spaces_no_change(self):
        from llmdev.runner import strip_trailing_spaces

        with tempfile.TemporaryDirectory() as tmpdir:
            b_py = os.path.join(tmpdir, "b.py")
            with open(b_py, "w", encoding="utf-8", newline="") as f:
                f.write("x = 1\n")

            result = strip_trailing_spaces(tmpdir, ["b.py"])

            self.assertEqual(result, [])
            with open(b_py, "r", encoding="utf-8", newline="") as f:
                content = f.read()
            self.assertEqual(content, "x = 1\n")

    def test_strip_trailing_spaces_no_final_newline(self):
        import re
        from llmdev.runner import strip_trailing_spaces

        with tempfile.TemporaryDirectory() as tmpdir:
            c_py = os.path.join(tmpdir, "c.py")
            with open(c_py, "w", encoding="utf-8", newline="") as f:
                f.write("x = 1  ")

            result = strip_trailing_spaces(tmpdir, ["c.py"])

            self.assertEqual(result, ["c.py"])
            with open(c_py, "r", encoding="utf-8", newline="") as f:
                content = f.read()
            self.assertEqual(content, "x = 1")

    def test_strip_trailing_spaces_binary(self):
        from llmdev.runner import strip_trailing_spaces

        with tempfile.TemporaryDirectory() as tmpdir:
            d_py = os.path.join(tmpdir, "d.py")
            with open(d_py, "wb") as f:
                f.write(b"x = 1 \r\ny\r\n")

            result = strip_trailing_spaces(tmpdir, ["d.py"])

            self.assertEqual(result, ["d.py"])
            with open(d_py, "rb") as f:
                content = f.read()
            self.assertEqual(content, b"x = 1\r\ny\r\n")

    def test_strip_trailing_spaces_missing_file(self):
        from llmdev.runner import strip_trailing_spaces

        with tempfile.TemporaryDirectory() as tmpdir:
            result = strip_trailing_spaces(tmpdir, ["nonexistent.py"])

            self.assertEqual(result, [])

    def test_strip_trailing_spaces_binary_decode_error(self):
        from llmdev.runner import strip_trailing_spaces

        with tempfile.TemporaryDirectory() as tmpdir:
            e_bin = os.path.join(tmpdir, "e.bin")
            with open(e_bin, "wb") as f:
                f.write(b"\xff\xfe  \n")

            result = strip_trailing_spaces(tmpdir, ["e.bin"])

            self.assertEqual(result, [])

    def test_strip_trailing_spaces_multiple_files(self):
        from llmdev.runner import strip_trailing_spaces

        with tempfile.TemporaryDirectory() as tmpdir:
            z_py = os.path.join(tmpdir, "z.py")
            a_py = os.path.join(tmpdir, "a.py")
            with open(z_py, "w", encoding="utf-8", newline="") as f:
                f.write("z = 1  \n")
            with open(a_py, "w", encoding="utf-8", newline="") as f:
                f.write("a = 1  \n")

            result = strip_trailing_spaces(tmpdir, ["z.py", "a.py"])

            self.assertEqual(result, ["a.py", "z.py"])


class TestLlmErrors(unittest.TestCase):
    def test_empty_response(self):
        from llmdev.runner import llm_errors
        text = "> Tokens: 11k sent, 0 received.  \n> Empty response received from LLM. Check your provider account?  \n"
        result = llm_errors(text)
        self.assertEqual(result, ["Empty response received from LLM. Check your provider account?"])

    def test_litellm_error(self):
        from llmdev.runner import llm_errors
        text = "> litellm.NotFoundError: NotFoundError: OpenAIException - Error code: 404 - {'error': 'generation thread died'}  \n"
        result = llm_errors(text)
        self.assertEqual(len(result), 1)
        self.assertTrue(result[0].startswith("litellm.NotFoundError"))

    def test_no_marker(self):
        from llmdev.runner import llm_errors
        text = "litellm.NotFoundError at the start of a line without the marker\n"
        result = llm_errors(text)
        self.assertEqual(result, [])

    def test_no_error(self):
        from llmdev.runner import llm_errors
        text = "#### Implement card 011\n> Applied edit to llmdev/evals.py\n"
        result = llm_errors(text)
        self.assertEqual(result, [])

    def test_empty_text(self):
        from llmdev.runner import llm_errors
        result = llm_errors("")
        self.assertEqual(result, [])


class TestAgentMessage(unittest.TestCase):
    def test_agent_message(self):
        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("a.py", "b.py"),
            read=(),
            checks=("c1", "c2"),
            commit="feat: test",
        )
        msg = agent_message(card)
        self.assertIn("cards/001.md", msg)
        self.assertIn("Edit only: a.py, b.py.", msg)
        self.assertIn("c1 && c2", msg)


class TestAgentCommand(unittest.TestCase):
    def test_agent_command_qwen(self):
        from llmdev.registry import Model
        m = Model(
            name="test",
            backend="mlx",
            model="~/models/mlx/x",
            ctx=4096,
            port=8081,
        )
        cmd, env = agent_command("qwen", m, "http://127.0.0.1:8081/v1", "hello")
        self.assertEqual(cmd[0], "qwen")
        self.assertEqual(cmd[-1], "hello")
        self.assertEqual(cmd[cmd.index("--openai-base-url") + 1], "http://127.0.0.1:8081/v1")
        self.assertEqual(cmd[cmd.index("--model") + 1], "~/models/mlx/x")
        self.assertEqual(env, {})

    def test_agent_command_opencode(self):
        from llmdev.registry import Model
        m = Model(
            name="test",
            backend="mlx",
            model="~/models/mlx/x",
            ctx=4096,
            port=8081,
        )
        cmd, env = agent_command("opencode", m, "http://127.0.0.1:8081/v1", "hello")
        self.assertEqual(cmd[:2], ["opencode", "run"])
        self.assertEqual(cmd[cmd.index("--model") + 1], "local/~/models/mlx/x")
        self.assertEqual(cmd[-1], "hello")
        config = json.loads(env["OPENCODE_CONFIG_CONTENT"])
        self.assertEqual(config["provider"]["local"]["options"]["baseURL"], "http://127.0.0.1:8081/v1")

    def test_agent_command_unknown(self):
        from llmdev.registry import Model
        m = Model(
            name="test",
            backend="mlx",
            model="~/models/mlx/x",
            ctx=4096,
            port=8081,
        )
        with self.assertRaises(ValueError) as cm:
            agent_command("cursor", m, "u", "hello")
        self.assertIn("unknown harness", str(cm.exception))


class TestRunCard(unittest.TestCase):
    def test_run_card_success(self):
        from llmdev.registry import Model

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
                if isinstance(cmd, list) and cmd[:2] == ["git", "diff"]:
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
            self.assertEqual(meta["card_id"], "001")
            self.assertEqual(meta["model_name"], "test")
            self.assertEqual(meta["backend"], "ollama")
            self.assertEqual(meta["harness"], "aider")

            run_dir = os.path.join(runs_dir, "20240101-120000-001")
            self.assertTrue(os.path.exists(run_dir))
            self.assertTrue(os.path.exists(os.path.join(run_dir, "meta.json")))
            self.assertTrue(os.path.exists(os.path.join(run_dir, "diff.patch")))

            with open(os.path.join(run_dir, "meta.json"), "r") as f:
                import json
                saved_meta = json.load(f)
            self.assertEqual(saved_meta, meta)

            with open(os.path.join(run_dir, "diff.patch"), "r") as f:
                diff_content = f.read()
            self.assertEqual(diff_content, "DIFF")

            aider_call = [c for c in calls if isinstance(c[0], list) and c[0][0] == "aider"][0]
            self.assertEqual(aider_call[1]["cwd"], repo)
            self.assertIn("OLLAMA_API_BASE", aider_call[1]["env"])

            git_add_call = [c for c in calls if isinstance(c[0], list) and c[0][:2] == ["git", "add"]][0]
            git_diff_call = [c for c in calls if isinstance(c[0], list) and c[0][:2] == ["git", "diff"]][0]
            git_add_idx = calls.index(git_add_call)
            git_diff_idx = calls.index(git_diff_call)
            self.assertLess(git_add_idx, git_diff_idx)

    def test_run_card_failure(self):
        from llmdev.registry import Model

        card = Card(
            path="cards/001.md",
            id="001",
            title="Test",
            edit=("file1.py",),
            read=(),
            checks=("exit 1",),
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

            def fake_run(cmd, **kwargs):
                if isinstance(cmd, str) and cmd == "exit 1":
                    result = type('obj', (object,), {
                        'returncode': 1,
                        'stdout': 'failed',
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
                        'stdout': '',
                        'stderr': '',
                    })()
                return result

            def fake_now():
                return datetime(2024, 1, 1, 12, 0, 0)

            meta = run_card(
                card, m, "http://127.0.0.1:11434/v1", repo, runs_dir,
                run=fake_run, now=fake_now
            )

            self.assertFalse(meta["passed"])

    def test_run_card_with_extra(self):
        from llmdev.registry import Model

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
                run=fake_run, now=fake_now, extra="more"
            )

            aider_call = [c for c in calls if isinstance(c[0], list) and c[0][0] == "aider"][0]
            message_idx = aider_call[0].index("--message")
            message = aider_call[0][message_idx + 1]
            self.assertTrue(message.endswith(" more"))

    def test_run_card_qwen_harness(self):
        from llmdev.registry import Model

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
            backend="mlx",
            model="~/models/mlx/x",
            ctx=4096,
            port=8081,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo = tmpdir
            runs_dir = os.path.join(tmpdir, "runs")
            os.makedirs(runs_dir)
            with open(os.path.join(repo, "file1.py"), "w") as f:
                f.write("x")

            calls = []
            def fake_run(cmd, **kwargs):
                if isinstance(cmd, list) and cmd[:2] == ["git", "diff"]:
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
                card, m, "http://127.0.0.1:8081/v1", repo, runs_dir,
                run=fake_run, now=fake_now, harness="qwen"
            )

            self.assertTrue(meta["passed"])
            self.assertEqual(meta["harness"], "qwen")

            run_dir = os.path.join(runs_dir, "20240101-120000-001")
            self.assertTrue(os.path.exists(run_dir))
            self.assertTrue(os.path.exists(os.path.join(run_dir, "meta.json")))
            self.assertTrue(os.path.exists(os.path.join(run_dir, "diff.patch")))
            self.assertTrue(os.path.exists(os.path.join(run_dir, "agent.log")))

            agent_call = [c for c in calls if isinstance(c[0], list) and c[0][0] == "qwen"][0]
            self.assertEqual(agent_call[1]["cwd"], repo)
            self.assertEqual(agent_call[1]["env"]["PWD"], os.path.abspath(repo))
            self.assertEqual(agent_call[1].get("stdin"), __import__('subprocess').DEVNULL)
            self.assertEqual(agent_call[1].get("stderr"), __import__('subprocess').STDOUT)

            aider_calls = [c for c in calls if isinstance(c[0], list) and c[0][0] == "aider"]
            self.assertEqual(len(aider_calls), 0)


if __name__ == "__main__":
    unittest.main()
