import json
import os
import shutil
import subprocess
import urllib.request

GB = 1000 ** 3
DISK_MARGIN = 10 * GB
GPU_OVERHEAD = 1.15


class FitError(Exception): ...


def _fetch_json(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))


def remote_size(m, fetch_json=_fetch_json) -> int:
    """Bytes to download for model m, from the Hugging Face file list."""
    if m.backend not in ("mlx", "llama"):
        raise FitError(f"size check not supported for backend {m.backend}")
    if not m.source:
        raise FitError(f"model {m.name} has no source defined")
    files = fetch_json(f"https://huggingface.co/api/models/{m.source}/tree/main")
    files = [f for f in files if f.get("type") == "file"]
    if m.backend == "llama":
        name = os.path.basename(m.model)
        files = [f for f in files if f.get("path") == name]
        if not files:
            raise FitError(f"{name} not found in {m.source}")
    return sum(int(f.get("size", 0)) for f in files)


def gpu_limit(run=subprocess.run) -> int:
    """Bytes of memory the GPU may use."""
    def sysctl(key):
        out = run(["sysctl", "-n", key], capture_output=True, text=True, timeout=5)
        return int(out.stdout.strip())
    wired_mb = sysctl("iogpu.wired_limit_mb")
    if wired_mb > 0:
        return wired_mb * 1024 * 1024
    return int(sysctl("hw.memsize") * 0.75)


def verdict(size, free_disk, gpu) -> dict:
    return {
        "size": size,
        "free_disk": free_disk,
        "gpu_limit": gpu,
        "disk_ok": size + DISK_MARGIN <= free_disk,
        "gpu_ok": size * GPU_OVERHEAD <= gpu,
    }


def check(m, fetch_json=_fetch_json, run=subprocess.run, disk_usage=shutil.disk_usage) -> dict:
    size = remote_size(m, fetch_json)
    folder = os.path.dirname(os.path.abspath(os.path.expanduser(m.model)))
    while not os.path.exists(folder) and folder != os.path.dirname(folder):
        folder = os.path.dirname(folder)
    return verdict(size, disk_usage(folder).free, gpu_limit(run))


def format_verdict(v) -> str:
    def gb(x):
        return f"{x / GB:.1f} GB"
    disk = "ok" if v["disk_ok"] else "NO"
    gpu = "ok" if v["gpu_ok"] else "NO"
    return (f"size {gb(v['size'])}  disk free {gb(v['free_disk'])} {disk}"
            f"  GPU limit {gb(v['gpu_limit'])} {gpu}")
