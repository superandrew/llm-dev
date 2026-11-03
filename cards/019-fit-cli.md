+++
id = "019"
title = "Fit check in the CLI"
edit = ["llmdev/cli.py", "tests/test_fit.py"]
read = ["AGENTS.md", "models.toml", "bin/llm", "llmdev/fit.py", "llmdev/pull.py", "llmdev/registry.py"]
checks = ["python3 -m unittest tests.test_fit -v", "python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/cli.py", "git --no-pager diff --check HEAD"]
commit = "feat: llm fit, and pull checks the disk first"
edit_format = "diff"
+++

# 019 - Fit check in the CLI

## llmdev/cli.py

1. Add `fit` to the `from llmdev import ...` line.
2. New subcommand `fit NAME` (help "Check a model fits disk and GPU memory"). It runs
   `v = fit.check(m)` and prints `fit.format_verdict(v)`; returns 0 when `v["disk_ok"]` and
   `v["gpu_ok"]` are both true, else 1. On `fit.FitError` it prints the error to stderr and
   returns 1.
3. In `pull`, before `returncode = pull.pull(m)`, when `m.backend` is `"mlx"` or `"llama"`:

        try:
            v = fit.check(m)
        except (fit.FitError, OSError) as e:
            print(f"fit check skipped: {e}", file=sys.stderr)
        else:
            print(fit.format_verdict(v))
            if not v["disk_ok"]:
                print("not enough disk space", file=sys.stderr)
                return 1

Nothing else changes.

## tests/test_fit.py

Add a class `TestFitCli`. Each test writes a `models.toml` in a `tempfile.TemporaryDirectory`
with one model `test` (backend `mlx`, model `"~/models/mlx/test"`, ctx 4096, port 8080,
source `"org/repo"`), patches `llmdev.cli.ROOT` with `Path(tmpdir)` and patches
`llmdev.cli.fit.check` (never the network):

- `cli.main(["fit", "test"])` with `check` returning `fit.verdict(65 * fit.GB, 300 * fit.GB, 77 * fit.GB)` returns 0.
- The same with `fit.verdict(82 * fit.GB, 300 * fit.GB, 77 * fit.GB)` returns 1.
- `check` raising `fit.FitError("x")`: returns 1.
- `cli.main(["pull", "test"])` with `check` returning `fit.verdict(65 * fit.GB, 70 * fit.GB, 77 * fit.GB)`
  and `llmdev.cli.pull.pull` patched: returns 1 and `pull` was not called.
- The same with `fit.verdict(65 * fit.GB, 300 * fit.GB, 77 * fit.GB)` and `pull` returning 0:
  returns 0 and `pull` was called once.
