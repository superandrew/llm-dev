import sys
import unittest
from unittest.mock import MagicMock

from llmdev import tui


class TestTUI(unittest.TestCase):
    def test_build_rows(self):
        # Mock registry
        class MockModel:
            def __init__(self, name, backend):
                self.name = name
                self.backend = backend

        registry_data = {
            "model1": MockModel("model1", "ollama"),
            "model2": MockModel("model2", "mlx"),
        }

        # Mock statuses
        statuses = {
            "model1": {"healthy": True, "pid": 1234},
            "model2": {"healthy": False, "pid": None},
        }

        # Mock summaries
        summaries = [
            {"model": "model1", "prefill_tps": 100.5, "decode_tps": 50.2},
        ]

        rows = tui.build_rows(registry_data, statuses, summaries)

        # Check order (sorted by name)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0]["name"], "model1")
        self.assertEqual(rows[1]["name"], "model2")

        # Check values
        self.assertEqual(rows[0]["backend"], "ollama")
        self.assertTrue(rows[0]["healthy"])
        self.assertEqual(rows[0]["pid"], 1234)
        self.assertEqual(rows[0]["prefill_tps"], 100.5)
        self.assertEqual(rows[0]["decode_tps"], 50.2)

        self.assertEqual(rows[1]["backend"], "mlx")
        self.assertFalse(rows[1]["healthy"])
        self.assertIsNone(rows[1]["pid"])
        self.assertIsNone(rows[1]["prefill_tps"])
        self.assertIsNone(rows[1]["decode_tps"])

    def test_build_rows_no_summary(self):
        registry_data = {
            "model1": type("Model", (), {"name": "model1", "backend": "ollama"})(),
        }
        statuses = {"model1": {"healthy": False, "pid": None}}
        summaries = []

        rows = tui.build_rows(registry_data, statuses, summaries)
        self.assertEqual(len(rows), 1)
        self.assertIsNone(rows[0]["prefill_tps"])
        self.assertIsNone(rows[0]["decode_tps"])

    def test_job_command(self):
        cmd = tui.job_command("serve", "model1", "/path/to/llm")
        self.assertEqual(cmd, [sys.executable, "/path/to/llm", "serve", "model1"])

    def test_render_lines(self):
        state = tui.State(
            rows=[
                {"name": "model1", "backend": "ollama", "healthy": True, "pid": 1234, "prefill_tps": 100.5, "decode_tps": 50.2},
                {"name": "model2", "backend": "mlx", "healthy": False, "pid": None, "prefill_tps": None, "decode_tps": None},
            ],
            selected=0,
            message="",
            job=None,
            job_label="",
            job_log="",
        )

        lines = tui.render_lines(state, 80)

        # Check title
        self.assertEqual(lines[0], "LLM Dev - Lab TUI")

        # Check header
        self.assertEqual(lines[1], "  name                      backend pid    prefill t/s  decode t/s")

        # Check rows
        self.assertTrue(lines[2].startswith(">"))
        self.assertIn("*", lines[2])

        self.assertTrue(lines[3].startswith(" "))
        self.assertNotIn("*", lines[3])

        # Check empty line
        self.assertEqual(lines[4], "")

        # Check footer
        self.assertEqual(lines[6], "up/down select  s serve/stop  p pull  b sweep  r refresh  q quit")

    def test_render_lines_width_cut(self):
        state = tui.State(
            rows=[{"name": "model1", "backend": "ollama", "healthy": True, "pid": 1234, "prefill_tps": 100.5, "decode_tps": 50.2}],
            selected=0,
            message="",
            job=None,
            job_label="",
            job_log="",
        )

        lines = tui.render_lines(state, 40)

        # Check width
        for line in lines:
            self.assertLessEqual(len(line), 40)

    def test_render_lines_no_trailing_spaces(self):
        state = tui.State(rows=[], selected=0, message="", job=None, job_label="", job_log="")
        lines = tui.render_lines(state, 80)

        for line in lines:
            self.assertEqual(line, line.rstrip())

    def test_render_lines_job_line(self):
        state = tui.State(rows=[], selected=0, message="", job=MagicMock(), job_label="pull model1", job_log="Downloading...")
        lines = tui.render_lines(state, 80)
        self.assertIn("running: pull model1 - Downloading...", lines)

    def test_handle_key_up_down(self):
        state = tui.State(rows=[{"name": "m1"}, {"name": "m2"}], selected=0)

        # Up at start
        tui.handle_key(state, "up", lambda a, b: None)
        self.assertEqual(state.selected, 0)

        # Down
        tui.handle_key(state, "down", lambda a, b: None)
        self.assertEqual(state.selected, 1)

        # Down at end
        tui.handle_key(state, "down", lambda a, b: None)
        self.assertEqual(state.selected, 1)

    def test_handle_key_empty_rows(self):
        state = tui.State(rows=[], selected=0)
        tui.handle_key(state, "up", lambda a, b: None)
        self.assertEqual(state.selected, 0)

        tui.handle_key(state, "down", lambda a, b: None)
        self.assertEqual(state.selected, 0)

    def test_handle_key_s_serve(self):
        state = tui.State(rows=[{"name": "model1", "healthy": False}], selected=0, message="", job=None, job_label="", job_log="")
        recorded = []

        def start_job(action, name):
            recorded.append((action, name))

        tui.handle_key(state, "s", start_job)
        self.assertEqual(recorded, [("serve", "model1")])

    def test_handle_key_s_stop(self):
        state = tui.State(rows=[{"name": "model1", "healthy": True}], selected=0, message="", job=None, job_label="", job_log="")
        recorded = []

        def start_job(action, name):
            recorded.append((action, name))

        tui.handle_key(state, "s", start_job)
        self.assertEqual(recorded, [("stop", "model1")])

    def test_handle_key_p(self):
        state = tui.State(rows=[{"name": "model1", "healthy": False}], selected=0, message="", job=None, job_label="", job_log="")
        recorded = []

        def start_job(action, name):
            recorded.append((action, name))

        tui.handle_key(state, "p", start_job)
        self.assertEqual(recorded, [("pull", "model1")])

    def test_handle_key_b_healthy(self):
        state = tui.State(rows=[{"name": "model1", "healthy": True}], selected=0, message="", job=None, job_label="", job_log="")
        recorded = []

        def start_job(action, name):
            recorded.append((action, name))

        tui.handle_key(state, "b", start_job)
        self.assertEqual(recorded, [("sweep", "model1")])

    def test_handle_key_b_unhealthy(self):
        state = tui.State(rows=[{"name": "model1", "healthy": False}], selected=0, message="", job=None, job_label="", job_log="")
        tui.handle_key(state, "b", lambda a, b: None)
        self.assertEqual(state.message, "model1 is not healthy")

    def test_handle_key_job_running_blocks(self):
        state = tui.State(rows=[{"name": "model1", "healthy": False}], selected=0, message="", job=MagicMock(), job_label="", job_log="")
        tui.handle_key(state, "s", lambda a, b: None)
        self.assertEqual(state.message, "job running")

        tui.handle_key(state, "p", lambda a, b: None)
        self.assertEqual(state.message, "job running")

        tui.handle_key(state, "b", lambda a, b: None)
        self.assertEqual(state.message, "job running")

    def test_handle_key_r(self):
        state = tui.State(rows=[], message="some message", job=None, job_label="", job_log="")
        tui.handle_key(state, "r", lambda a, b: None)
        self.assertEqual(state.message, "")

    def test_handle_key_q(self):
        state = tui.State(rows=[])
        result = tui.handle_key(state, "q", lambda a, b: None)
        self.assertFalse(result)

    def test_poll_job_no_job(self):
        state = tui.State(rows=[])
        tui.poll_job(state, lambda: "")
        self.assertIsNone(state.job)

    def test_poll_job_running(self):
        mock_job = MagicMock()
        mock_job.poll.return_value = None

        state = tui.State(rows=[], job=mock_job, job_label="test", job_log="")
        tui.poll_job(state, lambda: "log line")
        self.assertEqual(state.job_log, "log line")
        self.assertEqual(state.job, mock_job)

    def test_poll_job_done(self):
        mock_job = MagicMock()
        mock_job.poll.return_value = True
        mock_job.returncode = 0

        state = tui.State(rows=[], job=mock_job, job_label="test", job_log="")
        tui.poll_job(state, lambda: "")
        self.assertIsNone(state.job)
        self.assertEqual(state.job_label, "")
        self.assertEqual(state.message, "test done")

    def test_poll_job_failed(self):
        mock_job = MagicMock()
        mock_job.poll.return_value = True
        mock_job.returncode = 1

        state = tui.State(rows=[], job=mock_job, job_label="test", job_log="")
        tui.poll_job(state, lambda: "")
        self.assertIsNone(state.job)
        self.assertEqual(state.job_label, "")
        self.assertEqual(state.message, "test failed (1)")

    def test_render_lines_healthy_marker(self):
        state = tui.State(rows=[{"name": "m1", "backend": "mlx", "healthy": True, "pid": 7, "prefill_tps": None, "decode_tps": None}], selected=0, message="", job=None, job_label="", job_log="")
        lines = tui.render_lines(state, 80)
        self.assertTrue(lines[2].startswith("> m1*"))
        self.assertIn("mlx", lines[2])

    def test_render_lines_unhealthy_marker_second_row(self):
        state = tui.State(rows=[
            {"name": "m1", "backend": "mlx", "healthy": True, "pid": 7, "prefill_tps": None, "decode_tps": None},
            {"name": "m2", "backend": "ollama", "healthy": False, "pid": None, "prefill_tps": None, "decode_tps": None},
        ], selected=1, message="", job=None, job_label="", job_log="")
        lines = tui.render_lines(state, 80)
        # Header is at index 1, first row at index 2, second row at index 3
        self.assertTrue(lines[2].startswith("  m1"))
        self.assertTrue(lines[3].startswith("> m2"))

    def test_cli_tui(self):
        from unittest.mock import patch
        from llmdev import cli
        with patch("llmdev.tui.run_tui", return_value=0) as run_tui:
            self.assertEqual(cli.main(["tui"]), 0)
        run_tui.assert_called_once_with(str(cli.ROOT))


if __name__ == "__main__":
    unittest.main()
