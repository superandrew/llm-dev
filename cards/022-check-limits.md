+++
id = "022"
title = "Time limits on checks and hidden tests"
edit = ["llmdev/runner.py", "llmdev/evals.py", "tests/test_runner.py", "tests/test_evals.py"]
read = ["AGENTS.md", ".aider.model.settings.yml"]
checks = ["python3 -m unittest tests.test_runner tests.test_evals -v", "python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/runner.py llmdev/evals.py", "git --no-pager diff --check HEAD"]
commit = "fix: time limits on checks and hidden tests"
edit_format = "diff"
+++

# 022 - Time limits on checks and hidden tests

A model wrote code with an endless loop: the card checks and the hidden tests ran for half an
hour, because nothing limits them. Checks run through a shell, so killing the shell on a timeout
leaves its children running: they also get a CPU time limit (`ulimit -t`), which the kernel
applies to every child.

## llmdev/runner.py

1. Below the imports add two constants and one function:

        CHECK_CPU_S = 120
        CHECK_TIMEOUT_S = 300


        def limited(cmd: str) -> str:
            """Prefix a shell command with a CPU time limit that its children inherit."""
            return f"ulimit -t {CHECK_CPU_S}; {cmd}"

2. In `aider_command`, the value after `--test-cmd` becomes
   `limited(" && ".join(card.checks))`.
3. In `run_checks`:
   - call `run(limited(check), shell=True, cwd=cwd, capture_output=True, text=True,
     timeout=CHECK_TIMEOUT_S)`;
   - when it raises `subprocess.TimeoutExpired`, the result for that check is
     `returncode` `None` and `output` `f"timeout after {CHECK_TIMEOUT_S} s"`;
   - the `"cmd"` of each result stays the original `check`, without the prefix.

## llmdev/evals.py

The hidden test run gets `timeout=runner.CHECK_TIMEOUT_S`. When it raises
`subprocess.TimeoutExpired`, the score is computed from an empty output (`hidden_score("")`,
which is `(0, 0)`). The command list itself does not change.

## Tests

In `tests/test_runner.py`:

- `test_limited`: `limited("true")` equals `"ulimit -t 120; true"`.
- `test_run_checks_passes_limits`: a fake `run` that records its first argument and its
  `timeout` keyword; after `run_checks(("echo hi",), "/tmp", run=fake_run)` the recorded command
  is `"ulimit -t 120; echo hi"`, the recorded timeout is `300`, and `results[0]["cmd"]` is
  `"echo hi"`.
- `test_run_checks_timeout`: a fake `run` that raises
  `subprocess.TimeoutExpired("x", 300)`; the result has `returncode` `None` and `output`
  `"timeout after 300 s"`.
- In the existing aider command test that checks `--test-cmd`, also check that the value after
  `--test-cmd` starts with `"ulimit -t 120; "`.

In `tests/test_evals.py`, one new test copied from the existing `run_eval` test, whose fake
`run` raises `subprocess.TimeoutExpired(cmd, 300)` for the hidden test command: the row has
`hidden_passed` 0 and `hidden_total` 0.
