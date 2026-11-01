import os
import signal
import tempfile
import unittest
from unittest.mock import MagicMock, patch

from llmdev.registry import Model
from llmdev.server import (
    ServerError,
    _alive,
    _fetch,
    base_url,
    build_command,
    health,
    start,
    status,
    stop,
)


class TestBuildCommand(unittest.TestCase):
    def test_ollama_command(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )
        cmd, env = build_command(m)
        self.assertEqual(cmd, ["ollama", "serve"])
        self.assertEqual(env["OLLAMA_HOST"], "127.0.0.1:11434")
        self.assertEqual(env["OLLAMA_CONTEXT_LENGTH"], "2048")

    def test_llama_command(self):
        m = Model(
            name="test",
            backend="llama",
            model="/path/to/model",
            ctx=2048,
            port=8080,
            host="127.0.0.1",
            args=("--arg1", "value1"),
        )
        cmd, env = build_command(m)
        self.assertEqual(
            cmd,
            [
                "llama-server",
                "-m", "/path/to/model",
                "-c", "2048",
                "--host", "127.0.0.1",
                "--port", "8080",
                "--jinja",
                "--arg1", "value1",
            ],
        )
        self.assertEqual(env, {})

    def test_mlx_command(self):
        m = Model(
            name="test",
            backend="mlx",
            model="test-model",
            ctx=2048,
            port=8080,
            host="127.0.0.1",
            args=("--arg1", "value1"),
        )
        cmd, env = build_command(m)
        self.assertEqual(
            cmd,
            [
                "mlx_lm.server",
                "--model", "test-model",
                "--host", "127.0.0.1",
                "--port", "8080",
                "--arg1", "value1",
            ],
        )
        self.assertEqual(env, {})

    def test_env_merge(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
            env=(("CUSTOM_VAR", "custom_value"),),
        )
        cmd, env = build_command(m)
        self.assertEqual(env["CUSTOM_VAR"], "custom_value")
        self.assertEqual(env["OLLAMA_HOST"], "127.0.0.1:11434")


class TestBaseUrl(unittest.TestCase):
    def test_base_url(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )
        self.assertEqual(base_url(m), "http://127.0.0.1:11434/v1")


class TestHealth(unittest.TestCase):
    def test_health_true(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )
        mock_fetch = MagicMock(return_value=200)
        self.assertTrue(health(m, fetch=mock_fetch))

    def test_health_false(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )
        mock_fetch = MagicMock(return_value=404)
        self.assertFalse(health(m, fetch=mock_fetch))

    def test_health_exception(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )
        mock_fetch = MagicMock(side_effect=Exception("network error"))
        self.assertFalse(health(m, fetch=mock_fetch))


class TestAlive(unittest.TestCase):
    def test_alive_true(self):
        with patch("os.kill") as mock_kill:
            mock_kill.return_value = None
            self.assertTrue(_alive(99999))

    def test_alive_process_not_found(self):
        with patch("os.kill") as mock_kill:
            mock_kill.side_effect = ProcessLookupError()
            self.assertFalse(_alive(99999))

    def test_alive_permission_error(self):
        with patch("os.kill") as mock_kill:
            mock_kill.side_effect = PermissionError()
            self.assertTrue(_alive(99999))


class TestStart(unittest.TestCase):
    def test_start_already_healthy(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )
        mock_fetch = MagicMock(return_value=200)
        mock_spawn = MagicMock()
        mock_alive = MagicMock(return_value=False)

        result = start(m, tempfile.gettempdir(), spawn=mock_spawn, fetch=mock_fetch, alive=mock_alive)
        self.assertIsNone(result)
        mock_spawn.assert_not_called()

    def test_start_with_pid_file_and_alive_process(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = os.path.join(tmpdir, "test.pid")
            with open(pid_file, "w") as f:
                f.write("12345")

            mock_fetch = MagicMock(return_value=404)  # Not healthy
            mock_spawn = MagicMock()
            mock_alive = MagicMock(return_value=True)

            with self.assertRaises(ServerError) as cm:
                start(m, tmpdir, spawn=mock_spawn, fetch=mock_fetch, alive=mock_alive)
            self.assertIn("already running", str(cm.exception))
            self.assertIn("12345", str(cm.exception))

    def test_start_with_stale_pid_file(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = os.path.join(tmpdir, "test.pid")
            with open(pid_file, "w") as f:
                f.write("12345")

            mock_fetch = MagicMock(return_value=404)  # Not healthy
            mock_spawn = MagicMock()
            mock_proc = MagicMock()
            mock_proc.pid = 54321
            mock_spawn.return_value = mock_proc
            mock_alive = MagicMock(return_value=False)

            result = start(m, tmpdir, spawn=mock_spawn, fetch=mock_fetch, alive=mock_alive)
            self.assertEqual(result, 54321)
            self.assertTrue(os.path.exists(pid_file))
            with open(pid_file) as f:
                self.assertEqual(f.read().strip(), "54321")

    def test_start_new_process(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_fetch = MagicMock(return_value=404)  # Not healthy
            mock_spawn = MagicMock()
            mock_proc = MagicMock()
            mock_proc.pid = 54321
            mock_spawn.return_value = mock_proc
            mock_alive = MagicMock(return_value=False)

            result = start(m, tmpdir, spawn=mock_spawn, fetch=mock_fetch, alive=mock_alive)
            self.assertEqual(result, 54321)

            # Verify spawn was called with correct arguments
            mock_spawn.assert_called_once()
            call_kwargs = mock_spawn.call_args[1]
            self.assertEqual(call_kwargs["start_new_session"], True)
            self.assertIn("env", call_kwargs)

            # Verify pid file
            pid_file = os.path.join(tmpdir, "test.pid")
            self.assertTrue(os.path.exists(pid_file))

    def test_start_llama_with_args(self):
        m = Model(
            name="test",
            backend="llama",
            model="/path/to/model",
            ctx=2048,
            port=8080,
            host="127.0.0.1",
            args=("--arg1", "value1"),
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_fetch = MagicMock(return_value=404)
            mock_spawn = MagicMock()
            mock_proc = MagicMock()
            mock_proc.pid = 54321
            mock_spawn.return_value = mock_proc
            mock_alive = MagicMock(return_value=False)

            start(m, tmpdir, spawn=mock_spawn, fetch=mock_fetch, alive=mock_alive)

            # Get the command from the call
            call_args = mock_spawn.call_args
            cmd = call_args[0][0]
            self.assertIn("--arg1", cmd)
            self.assertIn("value1", cmd)


class TestStop(unittest.TestCase):
    def test_stop_no_pid_file(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            result = stop(m, tmpdir)
            self.assertFalse(result)

    def test_stop_with_pid_file(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = os.path.join(tmpdir, "test.pid")
            with open(pid_file, "w") as f:
                f.write("12345")

            mock_kill = MagicMock()
            result = stop(m, tmpdir, kill=mock_kill)

            self.assertTrue(result)
            mock_kill.assert_called_once_with(12345, signal.SIGTERM)
            self.assertFalse(os.path.exists(pid_file))

    def test_stop_process_not_found(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = os.path.join(tmpdir, "test.pid")
            with open(pid_file, "w") as f:
                f.write("12345")

            mock_kill = MagicMock(side_effect=ProcessLookupError())
            result = stop(m, tmpdir, kill=mock_kill)

            self.assertTrue(result)
            self.assertFalse(os.path.exists(pid_file))


class TestStatus(unittest.TestCase):
    def test_status_no_pid(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            mock_fetch = MagicMock(return_value=404)
            result = status(m, tmpdir, fetch=mock_fetch)

            self.assertEqual(result["name"], "test")
            self.assertEqual(result["backend"], "ollama")
            self.assertEqual(result["url"], "http://127.0.0.1:11434/v1")
            self.assertEqual(result["healthy"], False)
            self.assertIsNone(result["pid"])

    def test_status_with_pid(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = os.path.join(tmpdir, "test.pid")
            with open(pid_file, "w") as f:
                f.write("12345")

            mock_alive = MagicMock(return_value=True)
            mock_fetch = MagicMock(return_value=200)

            result = status(m, tmpdir, fetch=mock_fetch, alive=mock_alive)

            self.assertEqual(result["pid"], 12345)
            self.assertEqual(result["healthy"], True)

    def test_status_stale_pid(self):
        m = Model(
            name="test",
            backend="ollama",
            model="test-model",
            ctx=2048,
            port=11434,
            host="127.0.0.1",
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            pid_file = os.path.join(tmpdir, "test.pid")
            with open(pid_file, "w") as f:
                f.write("12345")

            mock_alive = MagicMock(return_value=False)
            mock_fetch = MagicMock(return_value=200)

            result = status(m, tmpdir, fetch=mock_fetch, alive=mock_alive)

            self.assertIsNone(result["pid"])
            self.assertEqual(result["healthy"], True)
