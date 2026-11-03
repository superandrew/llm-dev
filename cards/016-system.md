+++
id = "016"
title = "System status"
edit = ["llmdev/system.py", "tests/test_system.py"]
read = ["AGENTS.md", "models.toml", "bin/llm"]
checks = ["test -s llmdev/system.py && test -s tests/test_system.py", "python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/system.py", "git add -N -- llmdev/system.py tests/test_system.py && git --no-pager diff --check HEAD"]
commit = "feat: read GPU, memory and swap without sudo"
edit_format = "whole"
+++

# 016 - System status

Read GPU, memory and swap from macOS commands that need no sudo, cheap enough to run every
few seconds, and format them as one status line. Missing measures are left out, never zero.

## llmdev/system.py

Imports: `re`, `subprocess`. Write exactly these functions.

    GB = 1024 ** 3

    def parse_gpu(text) -> dict

`"Device Utilization %"=N` -> key `gpu_percent` with the int N.
`"In use system memory"=N` -> key `gpu_memory_bytes` with the int N. The pattern must not match
`"In use system memory (driver)"=0`. Each missing key is left out.

    def parse_vm_stat(text) -> dict

The page size is the number in `(page size of N bytes)`; when missing return `{}`.
`wired_bytes` = the number of the line `Pages wired down:` times the page size.
`available_bytes` = the sum of the numbers of the lines `Pages free:`, `Pages inactive:` and
`Pages speculative:` times the page size; leave it out when any of the three is missing.
Numbers end with a dot, for example `960917.`.

    def parse_swap(text) -> dict

`text` looks like `total = 4096.00M  used = 2566.56M  free = 1529.44M  (encrypted)`.
Keys `swap_total_bytes` and `swap_used_bytes`, each `round(value * 1048576)`; each missing key is left out.

    def sample(run=subprocess.run) -> dict

Runs each command with `run(cmd, capture_output=True, text=True, timeout=2)` and merges:
`["ioreg", "-r", "-d1", "-c", "IOAccelerator"]` with `parse_gpu`, `["vm_stat"]` with
`parse_vm_stat`, `["sysctl", "-n", "vm.swapusage"]` with `parse_swap`. A command that raises
`OSError` or `subprocess.SubprocessError`, or has a non-zero `returncode`, adds nothing; the
others still run.

    def status_line(m) -> str

Parts in this order, each only when its keys are present, joined by two spaces, with
`gb(x) = f"{x / GB:.1f}"`:
`GPU {gpu_percent}%`, `GPU mem {gb(gpu_memory_bytes)} GB`, `wired {gb(wired_bytes)} GB`,
`avail {gb(available_bytes)} GB`, `swap {gb(swap_used_bytes)}/{gb(swap_total_bytes)} GB`
(the swap part needs both keys). An empty dict gives `""`.

## tests/test_system.py

Use `unittest` and `types.SimpleNamespace`. Module-level inputs:

    GPU = '"PerformanceStatistics" = {"In use system memory (driver)"=0,"Alloc system memory"=29249503232,"Device Utilization %"=99,"In use system memory"=25320931328}'
    VM = "Mach Virtual Memory Statistics: (page size of 16384 bytes)\nPages free:      960917.\nPages active:     1158457.\nPages inactive:     2195956.\nPages speculative:   90377.\nPages wired down:   1757015.\n"
    SWAP = "total = 4096.00M  used = 2566.56M  free = 1529.44M  (encrypted)\n"

Write expected values as the expressions shown, do not compute them:

- `parse_gpu(GPU)` equals `{"gpu_percent": 99, "gpu_memory_bytes": 25320931328}`; `parse_gpu("")` equals `{}`.
- `parse_vm_stat(VM)` equals `{"wired_bytes": 1757015 * 16384, "available_bytes": (960917 + 2195956 + 90377) * 16384}`.
- `parse_vm_stat("Pages free: 1.\n")` equals `{}`.
- `parse_swap(SWAP)` equals `{"swap_total_bytes": round(4096.00 * 1048576), "swap_used_bytes": round(2566.56 * 1048576)}`.
- `status_line` of the merge of the three parsed inputs equals
  `"GPU 99%  GPU mem 23.6 GB  wired 26.8 GB  avail 49.5 GB  swap 2.5/4.0 GB"`.
- `status_line({})` equals `""`; `status_line({"gpu_percent": 5})` equals `"GPU 5%"`.
- `sample` with a fake `run` that returns `SimpleNamespace(returncode=0, stdout=...)` with GPU,
  VM or SWAP by command: the result has 6 keys.
- `sample` with a fake `run` that raises `FileNotFoundError` for `ioreg` only: 4 keys.
- `sample` with a fake `run` that returns `returncode=1` for `vm_stat` only: 4 keys.
- `sample` with a fake `run` that raises `subprocess.TimeoutExpired("x", 2)` always: `{}`.
