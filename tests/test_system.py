import unittest
import subprocess
from types import SimpleNamespace

from llmdev.system import (
    GB,
    parse_gpu,
    parse_vm_stat,
    parse_swap,
    sample,
    status_line,
)


GPU = '"PerformanceStatistics" = {"In use system memory (driver)"=0,"Alloc system memory"=29249503232,"Device Utilization %"=99,"In use system memory"=25320931328}'
VM = "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free:      960917.\nPages active:     1158457.\nPages inactive:     2195956.\nPages speculative:   90377.\nPages wired down:   1757015.\n"
SWAP = "total = 4096.00M  used = 2566.56M  free = 1529.44M  (encrypted)\n"


class TestSystem(unittest.TestCase):
    def test_parse_gpu(self):
        self.assertEqual(
            parse_gpu(GPU),
            {"gpu_percent": 99, "gpu_memory_bytes": 25320931328},
        )
        self.assertEqual(parse_gpu(""), {})

    def test_parse_vm_stat(self):
        self.assertEqual(
            parse_vm_stat(VM),
            {"wired_bytes": 1757015 * 16384, "available_bytes": (960917 + 2195956 + 90377) * 16384},
        )
        self.assertEqual(parse_vm_stat("Pages free: 1.\n"), {})

    def test_parse_swap(self):
        self.assertEqual(
            parse_swap(SWAP),
            {"swap_total_bytes": round(4096.00 * 1048576), "swap_used_bytes": round(2566.56 * 1048576)},
        )

    def test_status_line(self):
        merged = {
            "gpu_percent": 99,
            "gpu_memory_bytes": 25320931328,
            "wired_bytes": 1757015 * 16384,
            "available_bytes": (960917 + 2195956 + 90377) * 16384,
            "swap_total_bytes": round(4096.00 * 1048576),
            "swap_used_bytes": round(2566.56 * 1048576),
        }
        self.assertEqual(
            status_line(merged),
            "GPU 99%  GPU mem 23.6 GB  wired 26.8 GB  avail 49.5 GB  swap 2.5/4.0 GB",
        )
        self.assertEqual(status_line({}), "")
        self.assertEqual(status_line({"gpu_percent": 5}), "GPU 5%")

    def test_sample(self):
        def fake_run(cmd, capture_output=True, text=True, timeout=2):
            if "ioreg" in cmd:
                return SimpleNamespace(returncode=0, stdout=GPU)
            if "vm_stat" in cmd:
                return SimpleNamespace(returncode=0, stdout=VM)
            if "sysctl" in cmd:
                return SimpleNamespace(returncode=0, stdout=SWAP)
            raise AssertionError(f"Unexpected cmd: {cmd}")

        result = sample(run=fake_run)
        self.assertEqual(len(result), 6)

    def test_sample_ioreg_error(self):
        def fake_run(cmd, capture_output=True, text=True, timeout=2):
            if "ioreg" in cmd:
                raise FileNotFoundError()
            if "vm_stat" in cmd:
                return SimpleNamespace(returncode=0, stdout=VM)
            if "sysctl" in cmd:
                return SimpleNamespace(returncode=0, stdout=SWAP)
            raise AssertionError(f"Unexpected cmd: {cmd}")

        result = sample(run=fake_run)
        self.assertEqual(len(result), 4)

    def test_sample_vm_stat_error(self):
        def fake_run(cmd, capture_output=True, text=True, timeout=2):
            if "ioreg" in cmd:
                return SimpleNamespace(returncode=0, stdout=GPU)
            if "vm_stat" in cmd:
                return SimpleNamespace(returncode=1, stdout="")
            if "sysctl" in cmd:
                return SimpleNamespace(returncode=0, stdout=SWAP)
            raise AssertionError(f"Unexpected cmd: {cmd}")

        result = sample(run=fake_run)
        self.assertEqual(len(result), 4)

    def test_sample_timeout(self):
        def fake_run(cmd, capture_output=True, text=True, timeout=2):
            raise subprocess.TimeoutExpired("x", 2)

        result = sample(run=fake_run)
        self.assertEqual(result, {})
