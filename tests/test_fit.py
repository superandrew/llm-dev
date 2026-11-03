import os
import tempfile
import types
import unittest

from llmdev import fit
from llmdev.registry import Model


class TestFit(unittest.TestCase):
    def test_remote_size_mlx(self):
        fake_files = [
            {"type": "file", "path": "a", "size": 10},
            {"type": "file", "path": "b", "size": 5},
            {"type": "directory", "path": "d"},
        ]

        def fake_fetch(url):
            self.assertEqual(url, "https://huggingface.co/api/models/org/repo/tree/main")
            return fake_files

        m = Model(name="m", backend="mlx", model="~/models/mlx/test", ctx=65536, port=8080, source="org/repo")
        self.assertEqual(fit.remote_size(m, fetch_json=fake_fetch), 15)

    def test_remote_size_llama(self):
        fake_files = [
            {"type": "file", "path": "x.gguf", "size": 7},
            {"type": "file", "path": "y.gguf", "size": 9},
        ]

        def fake_fetch(url):
            return fake_files

        m = Model(name="m", backend="llama", model="~/models/gguf/x.gguf", ctx=65536, port=8080, source="org/repo")
        self.assertEqual(fit.remote_size(m, fetch_json=fake_fetch), 7)

    def test_remote_size_llama_not_found(self):
        fake_files = [
            {"type": "file", "path": "y.gguf", "size": 9},
        ]

        def fake_fetch(url):
            return fake_files

        m = Model(name="m", backend="llama", model="~/models/gguf/x.gguf", ctx=65536, port=8080, source="org/repo")
        with self.assertRaises(fit.FitError):
            fit.remote_size(m, fetch_json=fake_fetch)

    def test_remote_size_ollama_raises(self):
        m = Model(name="m", backend="ollama", model="some-model", ctx=65536, port=8080)
        with self.assertRaises(fit.FitError):
            fit.remote_size(m)

    def test_remote_size_mlx_no_source(self):
        m = Model(name="m", backend="mlx", model="~/models/mlx/test", ctx=65536, port=8080, source="")
        with self.assertRaises(fit.FitError):
            fit.remote_size(m)

    def test_gpu_limit_wired_limit_zero(self):
        def fake_run(cmd, **kwargs):
            class Result:
                def __init__(self, stdout):
                    self.stdout = stdout

            if cmd[2] == "iogpu.wired_limit_mb":
                return Result("0\n")
            elif cmd[2] == "hw.memsize":
                return Result("103079215104\n")
            raise ValueError(cmd)

        self.assertEqual(fit.gpu_limit(run=fake_run), int(103079215104 * 0.75))

    def test_gpu_limit_wired_limit_nonzero(self):
        def fake_run(cmd, **kwargs):
            class Result:
                def __init__(self, stdout):
                    self.stdout = stdout

            if cmd[2] == "iogpu.wired_limit_mb":
                return Result("80000\n")
            raise ValueError(cmd)

        self.assertEqual(fit.gpu_limit(run=fake_run), 80000 * 1024 * 1024)

    def test_verdict_disk_ok_gpu_ok(self):
        v = fit.verdict(65 * fit.GB, 300 * fit.GB, 77 * fit.GB)
        self.assertTrue(v["disk_ok"])
        self.assertTrue(v["gpu_ok"])

    def test_verdict_gpu_not_ok(self):
        v = fit.verdict(82 * fit.GB, 300 * fit.GB, 77 * fit.GB)
        self.assertFalse(v["gpu_ok"])

    def test_verdict_disk_not_ok(self):
        v = fit.verdict(65 * fit.GB, 70 * fit.GB, 77 * fit.GB)
        self.assertFalse(v["disk_ok"])

    def test_format_verdict(self):
        v = fit.verdict(65 * fit.GB, 300 * fit.GB, 77 * fit.GB)
        self.assertEqual(fit.format_verdict(v), "size 65.0 GB  disk free 300.0 GB ok  GPU limit 77.0 GB ok")

    def test_check_mlx_temp_dir(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            subdir = os.path.join(tmpdir, "subdir")
            m = Model(name="m", backend="mlx", model=f"{subdir}/model", ctx=65536, port=8080, source="org/repo")

            fake_files = [{"type": "file", "path": "model", "size": 65 * (1000 ** 3)}]

            def fake_fetch(url):
                return fake_files

            fake_disk = types.SimpleNamespace(free=300 * fit.GB)

            seen = []
            fake_run = lambda cmd, **kw: types.SimpleNamespace(stdout="80000\n")
            result = fit.check(m, fetch_json=fake_fetch, run=fake_run,
                               disk_usage=lambda p: seen.append(p) or fake_disk)
            self.assertEqual(seen, [tmpdir])
            self.assertTrue(result["disk_ok"])
