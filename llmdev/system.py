import re
import subprocess

GB = 1024 ** 3


def parse_gpu(text) -> dict:
    if not text:
        return {}
    result = {}
    match = re.search(r'"Device Utilization %"=(\d+)', text)
    if match:
        result["gpu_percent"] = int(match.group(1))
    match = re.search(r'"In use system memory"=(\d+)', text)
    if match:
        result["gpu_memory_bytes"] = int(match.group(1))
    return result


def parse_vm_stat(text) -> dict:
    if not text:
        return {}
    page_size_match = re.search(r'\(page size of (\d+) bytes\)', text)
    if not page_size_match:
        return {}
    page_size = int(page_size_match.group(1))

    wired_match = re.search(r'Pages wired down:\s*(\d+)\.', text)
    if not wired_match:
        return {}
    wired_bytes = int(wired_match.group(1)) * page_size

    free_match = re.search(r'Pages free:\s*(\d+)\.', text)
    inactive_match = re.search(r'Pages inactive:\s*(\d+)\.', text)
    speculative_match = re.search(r'Pages speculative:\s*(\d+)\.', text)

    if not free_match or not inactive_match or not speculative_match:
        return {}

    free_bytes = int(free_match.group(1)) * page_size
    inactive_bytes = int(inactive_match.group(1)) * page_size
    speculative_bytes = int(speculative_match.group(1)) * page_size
    available_bytes = free_bytes + inactive_bytes + speculative_bytes

    return {
        "wired_bytes": wired_bytes,
        "available_bytes": available_bytes,
    }


def parse_swap(text) -> dict:
    if not text:
        return {}
    match = re.search(r'total = ([\d.]+)M.*used = ([\d.]+)M', text, re.DOTALL)
    if not match:
        return {}
    total = float(match.group(1))
    used = float(match.group(2))
    return {
        "swap_total_bytes": round(total * 1048576),
        "swap_used_bytes": round(used * 1048576),
    }


def sample(run=subprocess.run) -> dict:
    result = {}
    commands = [
        (["ioreg", "-r", "-d1", "-c", "IOAccelerator"], parse_gpu),
        (["vm_stat"], parse_vm_stat),
        (["sysctl", "-n", "vm.swapusage"], parse_swap),
    ]
    for cmd, parser in commands:
        try:
            proc = run(cmd, capture_output=True, text=True, timeout=2)
            if proc.returncode == 0:
                result.update(parser(proc.stdout))
        except (OSError, subprocess.SubprocessError):
            continue
    return result


def status_line(m) -> str:
    parts = []
    if "gpu_percent" in m:
        parts.append(f"GPU {m['gpu_percent']}%")
    if "gpu_memory_bytes" in m:
        parts.append(f"GPU mem {gb(m['gpu_memory_bytes'])} GB")
    if "wired_bytes" in m:
        parts.append(f"wired {gb(m['wired_bytes'])} GB")
    if "available_bytes" in m:
        parts.append(f"avail {gb(m['available_bytes'])} GB")
    if "swap_total_bytes" in m and "swap_used_bytes" in m:
        parts.append(f"swap {gb(m['swap_used_bytes'])}/{gb(m['swap_total_bytes'])} GB")
    return "  ".join(parts)


def gb(x):
    return f"{x / GB:.1f}"
