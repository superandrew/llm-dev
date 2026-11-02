import json
import os
import subprocess
import sys
import tempfile
import unittest
from io import StringIO
from unittest.mock import patch

from llmdev import pull, registry


class TestPull(unittest.TestCase):
    def test_source_loaded(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[models.test]
backend = "mlx"
model = "~/models/mlx/test"
ctx = 65536
port = 8080
source = "org/repo"
""")
            f.flush()
            try:
                reg = registry.load(f.name)
                self.assertEqual(reg["test"].source, "org/repo")
            finally:
                os.unlink(f.name)

    def test_source_default_empty(self):
        with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
            f.write("""
[models.test]
backend = "ollama"
model = "test"
ctx = 65536
port = 11434
""")
            f.flush()
            try:
                reg = registry.load(f.name)
                self.assertEqual(reg["test"].source, "")
            finally:
                os.unlink(f.name)

    def test_pull_command_ollama(self):
        m = registry.Model(
            name="test", backend="ollama", model="llama3", ctx=4096, port=11434
        )
        cmd = pull.pull_command(m)
        self.assertEqual(cmd, ["ollama", "pull", "llama3"])

    def test_pull_command_mlx(self):
        m = registry.Model(
            name="test",
            backend="mlx",
            model="~/models/mlx/repo",
            ctx=4096,
            port=8080,
            source="org/repo",
        )
        cmd = pull.pull_command(m, hf="/usr/bin/hf")
        self.assertEqual(cmd, ["/usr/bin/hf", "download", "org/repo", "--local-dir", "~/models/mlx/repo"])

    def test_pull_command_llama(self):
        m = registry.Model(
            name="test",
            backend="llama",
            model="~/models/gguf/model.gguf",
            ctx=4096,
            port=8080,
            source="org/repo",
        )
        cmd = pull.pull_command(m, hf="/usr/bin/hf")
        self.assertEqual(cmd, ["/usr/bin/hf", "download", "org/repo", "model.gguf", "--local-dir", "~/models/gguf"])

    def test_pull_command_empty_source(self):
        m = registry.Model(
            name="test", backend="mlx", model="~/models/mlx/test", ctx=4096, port=8080, source=""
        )
        with self.assertRaises(pull.PullError) as ctx:
            pull.pull_command(m)
        self.assertIn("test has no source", str(ctx.exception))

    def test_hf_command_from_which(self):
        def fake_which(cmd):
            if cmd == "hf":
                return "/usr/bin/hf"
            if cmd == "mlx_lm.server":
                return None
            return None

        hf = pull.hf_command(which=fake_which)
        self.assertEqual(hf, "/usr/bin/hf")

    def test_hf_command_from_shebang(self):
        def fake_which(cmd):
            if cmd == "hf":
                return None
            if cmd == "mlx_lm.server":
                return "/some/path/mlx_lm.server"
            return None

        def fake_read_first_line(path):
            return "#!/some/dir/python"

        hf = pull.hf_command(which=fake_which, read_first_line=fake_read_first_line)
        self.assertEqual(hf, "/some/dir/hf")

    def test_hf_command_error(self):
        def fake_which(cmd):
            return None

        with self.assertRaises(pull.PullError) as ctx:
            pull.hf_command(which=fake_which)
        self.assertIn("Please install mlx-lm", str(ctx.exception))

    def test_pull_ollama_returncode(self):
        m = registry.Model(
            name="test", backend="ollama", model="llama3", ctx=4096, port=11434
        )

        def fake_run(cmd):
            class Result:
                returncode = 0
            return Result()

        result = pull.pull(m, run=fake_run)
        self.assertEqual(result, 0)

    def test_pull_mlx_returncode(self):
        m = registry.Model(
            name="test",
            backend="mlx",
            model="~/models/mlx/repo",
            ctx=4096,
            port=8080,
            source="org/repo",
        )

        def fake_run(cmd):
            class Result:
                returncode = 1
            return Result()

        def fake_which(cmd):
            return None

        def fake_read_first_line(path):
            return "#!/usr/bin/python3"

        with patch("llmdev.pull.hf_command", side_effect=lambda *args, **kwargs: "/usr/bin/hf"):
            result = pull.pull(m, run=fake_run, which=fake_which, read_first_line=fake_read_first_line)
            self.assertEqual(result, 1)

    def test_add_block(self):
        block = pull.add_block("test", "mlx", "~/models/mlx/repo", 65536, 8080)
        expected = "\n[models.test]\nbackend = \"mlx\"\nmodel = \"~/models/mlx/repo\"\nctx = 65536\nport = 8080\n"
        self.assertEqual(block, expected)

    def test_add_block_with_source(self):
        block = pull.add_block("test", "mlx", "~/models/mlx/repo", 65536, 8080, source="org/repo")
        expected = "\n[models.test]\nbackend = \"mlx\"\nmodel = \"~/models/mlx/repo\"\nctx = 65536\nport = 8080\nsource = \"org/repo\"\n"
        self.assertEqual(block, expected)

    def test_add_block_with_args(self):
        block = pull.add_block("test", "mlx", "~/models/mlx/repo", 65536, 8080, args=("--max-tokens", "16000"))
        expected = "\n[models.test]\nbackend = \"mlx\"\nmodel = \"~/models/mlx/repo\"\nctx = 65536\nport = 8080\nargs = [\"--max-tokens\", \"16000\"]\n"
        self.assertEqual(block, expected)

    def test_next_port_ollama(self):
        reg = {}
        port = pull.next_port(reg, "ollama")
        self.assertEqual(port, 11434)

    def test_next_port_mlx(self):
        reg = {
            "m1": registry.Model(name="m1", backend="mlx", model="m1", ctx=4096, port=8080),
            "m2": registry.Model(name="m2", backend="mlx", model="m2", ctx=4096, port=8082),
        }
        port = pull.next_port(reg, "mlx")
        self.assertEqual(port, 8083)

    def test_next_port_mlx_empty(self):
        reg = {
            "m1": registry.Model(name="m1", backend="ollama", model="m1", ctx=4096, port=11434),
        }
        port = pull.next_port(reg, "mlx")
        self.assertEqual(port, 8080)

    def test_next_port_mlx_one_model(self):
        reg = {
            "m1": registry.Model(name="m1", backend="mlx", model="m1", ctx=4096, port=8080),
        }
        port = pull.next_port(reg, "mlx")
        self.assertEqual(port, 8081)

    def test_add_model_ollama(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_path = os.path.join(tmpdir, "models.toml")
            with open(toml_path, "w") as f:
                f.write("""
[models.existing]
backend = "ollama"
model = "existing"
ctx = 4096
port = 11434
""")

            reg = registry.load(toml_path)
            block = pull.add_model(toml_path, reg, "test", "ollama", source="llama3")

            reg2 = registry.load(toml_path)
            self.assertEqual(reg2["test"].model, "llama3")
            self.assertEqual(reg2["test"].source, "")

    def test_add_model_mlx(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_path = os.path.join(tmpdir, "models.toml")
            with open(toml_path, "w") as f:
                f.write("""
[models.existing]
backend = "ollama"
model = "existing"
ctx = 4096
port = 11434
""")

            reg = registry.load(toml_path)
            block = pull.add_model(toml_path, reg, "test", "mlx", source="org/repo")

            reg2 = registry.load(toml_path)
            self.assertEqual(reg2["test"].model, os.path.expanduser("~/models/mlx/repo"))
            self.assertEqual(reg2["test"].source, "org/repo")
            self.assertEqual(reg2["test"].args, ("--max-tokens", "16000"))

    def test_add_model_llama(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_path = os.path.join(tmpdir, "models.toml")
            with open(toml_path, "w") as f:
                f.write("""
[models.existing]
backend = "ollama"
model = "existing"
ctx = 4096
port = 11434
""")

            reg = registry.load(toml_path)
            block = pull.add_model(toml_path, reg, "test", "llama", source="org/repo", file="model.gguf")

            reg2 = registry.load(toml_path)
            self.assertEqual(reg2["test"].model, os.path.expanduser("~/models/gguf/model.gguf"))
            self.assertEqual(reg2["test"].args, ("-ngl", "99"))

    def test_add_model_llama_no_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_path = os.path.join(tmpdir, "models.toml")
            with open(toml_path, "w") as f:
                f.write("""
[models.existing]
backend = "ollama"
model = "existing"
ctx = 4096
port = 11434
""")

            reg = registry.load(toml_path)
            with self.assertRaises(pull.PullError) as ctx:
                pull.add_model(toml_path, reg, "test", "llama", source="org/repo")
            self.assertIn("requires --file", str(ctx.exception))

    def test_add_model_duplicate(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_path = os.path.join(tmpdir, "models.toml")
            with open(toml_path, "w") as f:
                f.write("""
[models.test]
backend = "ollama"
model = "llama3"
ctx = 4096
port = 11434
""")

            reg = registry.load(toml_path)
            with self.assertRaises(pull.PullError) as ctx:
                pull.add_model(toml_path, reg, "test", "ollama", source="llama3")
            self.assertIn("already exists", str(ctx.exception))

    def test_add_model_invalid_name(self):
        with self.assertRaises(pull.PullError) as ctx:
            pull.add_model("unused.toml", {}, "gemma4:e4b", "ollama", source="gemma4:e4b")
        self.assertIn("invalid model name", str(ctx.exception))

    def test_cli_pull_success(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_path = os.path.join(tmpdir, "models.toml")
            with open(toml_path, "w") as f:
                f.write("""
[models.test]
backend = "ollama"
model = "llama3"
ctx = 4096
port = 11434
""")

            from llmdev import cli
            with patch("llmdev.cli.ROOT", Path(tmpdir)):
                with patch("llmdev.cli.pull.pull") as mock_pull:
                    mock_pull.return_value = 0
                    ret = cli.main(["pull", "test"])
                    self.assertEqual(ret, 0)
                    mock_pull.assert_called_once()

    def test_cli_pull_error(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_path = os.path.join(tmpdir, "models.toml")
            with open(toml_path, "w") as f:
                f.write("""
[models.test]
backend = "mlx"
model = "~/models/mlx/test"
ctx = 4096
port = 8080
""")

            from llmdev import cli, pull
            with patch("llmdev.cli.ROOT", Path(tmpdir)):
                with patch("llmdev.cli.pull.pull") as mock_pull:
                    mock_pull.side_effect = pull.PullError("no source")
                    ret = cli.main(["pull", "test"])
                    self.assertEqual(ret, 1)

    def test_cli_add(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            toml_path = os.path.join(tmpdir, "models.toml")
            with open(toml_path, "w") as f:
                f.write("""
[models.existing]
backend = "ollama"
model = "existing"
ctx = 4096
port = 11434
""")

            from llmdev import cli
            with patch("llmdev.cli.ROOT", Path(tmpdir)):
                with patch("llmdev.cli.pull.add_model") as mock_add:
                    mock_add.return_value = "\n[models.test]\nbackend = \"mlx\"\nmodel = \"~/models/mlx/repo\"\nctx = 65536\nport = 8080\n"
                    ret = cli.main(["add", "test", "--backend", "mlx", "--source", "org/repo"])
                    self.assertEqual(ret, 0)
                    mock_add.assert_called_once()


class Path:
    def __init__(self, path):
        self._path = path

    def __truediv__(self, other):
        return Path(os.path.join(self._path, other))

    def __str__(self):
        return self._path
