+++
id = "011"
title = "Development eval"
edit = ["llmdev/runner.py", "llmdev/evals.py", "llmdev/cli.py", "tests/test_evals.py"]
read = ["models.toml", "bin/llm", "AGENTS.md", "README.md", ".gitignore", ".aider.model.settings.yml", "llmdev/cards.py", "llmdev/metrics.py", "llmdev/lab.py"]
checks = ["test -s llmdev/evals.py && test -s tests/test_evals.py", "python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/runner.py llmdev/evals.py llmdev/cli.py", "git add -N -- llmdev/evals.py tests/test_evals.py && git --no-pager diff --check HEAD"]
commit = "feat: development eval with hidden tests"
edit_format = "diff"
+++

# 011 - Development eval

Speed does not say whether a model can develop. `llm eval` gives a model the same card in a
throwaway repo, then runs tests the model never saw. An eval lives in `evals/<name>/`:
`seed/` is copied as the repo (it holds `cards/task.md`), `hidden/` holds the hidden tests.

## llmdev/runner.py

In `run_card`, add the key `"run_dir": run_dir` to `meta`. Nothing else changes.

## llmdev/evals.py

    def hidden_score(output) -> tuple[int, int]
    def run_eval(name, m, base_url, root, runs_dir, run=subprocess.run, run_card=runner.run_card, timeout_s=1800) -> dict
    def read_evals(path) -> list[dict]
    def format_evals(rows) -> str

- `hidden_score`: from unittest output returns `(passed, total)`. Total is N in the line
  `Ran N tests` (or `Ran 1 test`). Failed is the sum of the numbers in the line
  `FAILED (failures=A, errors=B)`, where either part can be missing. No `Ran` line -> `(0, 0)`.
- `run_eval`, in order:
  1. `root/evals/<name>` missing -> raise `cards.CardError` naming the eval.
  2. In a `tempfile.TemporaryDirectory`, `repo` = the `repo` subdirectory: `shutil.copytree` of
     `seed` to `repo`; copy `root/.aider.model.settings.yml` to `repo` when it exists.
  3. With `run(cmd, cwd=repo, capture_output=True, text=True)` run, in order:
     `["git", "init", "-q"]`, `["git", "add", "-A"]`,
     `["git", "-c", "user.name=eval", "-c", "user.email=eval@local", "commit", "-q", "-m", "seed"]`.
  4. `card = cards.parse(os.path.join(repo, "cards", "task.md"))`, then
     `dataclasses.replace(card, path="cards/task.md", id=name)`.
  5. `meta = run_card(card, m, base_url, repo, runs_dir, run=run, timeout_s=timeout_s)`.
  6. `shutil.copytree` of `hidden` to `repo/hidden_tests`, then
     `run(["python3", "-m", "unittest", "discover", "-s", "hidden_tests", "-t", "."], cwd=repo,
     capture_output=True, text=True)`, and `hidden_score` of its stdout + stderr.
  7. Stats: `metrics.aider_stats` of the text of `meta["run_dir"]/aider.md`, zero stats when the
     file is missing.
  8. Returns the row: `eval`, `model` (`m.name`), `backend`, `passed` (`meta["passed"]`),
     `hidden_passed`, `hidden_total`, `duration_s` (`ended` minus `started`, whole seconds),
     `rounds`, `sent`, `received`, `timed_out`, `stray` (length of `stray_files`), `empty`
     (length of `empty_files`), `run` (last path part of `run_dir`).
- `read_evals`: one JSON object per line, a missing file -> `[]`.
- `format_evals`: a header and one line per row, columns eval, model, backend, passed, hidden
  (`3/10`), duration s, rounds, sent, received, stray, empty, timed out, run. Padded with spaces,
  None shown as `-`, no line ends with spaces. No rows -> `no evals yet`.

## llmdev/cli.py

Add two subcommands and `evals` to the `from llmdev import` line. Keep everything else identical.

- `eval NAME --model MODEL [--timeout 1800]`: fails with exit 1 and a message if `server.health` is
  False. Calls `evals.run_eval(args.name, m, server.base_url(m), str(ROOT), str(runs_dir),
  timeout_s=args.timeout)`, appends the row as one JSON line to `ROOT/runs/eval.jsonl`, prints
  `format_evals([row])`. Exit 0 when `passed` is true and `hidden_passed == hidden_total` and
  `hidden_total > 0`, otherwise 1.
- `evals`: prints `format_evals(read_evals(ROOT/runs/eval.jsonl))`.

## tests/test_evals.py

Never start a process, never run git: pass a fake `run` and a fake `run_card`. Use a temp dir with a
real `evals/demo/seed/cards/task.md` (a valid card), `seed/a.txt`, `hidden/test_x.py`. Cover:
- `hidden_score` on `Ran 10 tests in 0.1s\n\nOK` -> `(10, 10)`, `Ran 1 test in 0.1s\n\nOK` -> `(1, 1)`,
  `Ran 10 tests in 0.1s\n\nFAILED (failures=2, errors=1)` -> `(7, 10)`, `FAILED (errors=3)` with `Ran 5
  tests` -> `(2, 5)`, and no `Ran` line -> `(0, 0)`.
- `run_eval` missing eval raises `CardError`.
- `run_eval`: the fake `run_card` returns a meta with `run_dir` pointing to a temp dir with an
  `aider.md` having the line `> Tokens: 1k sent, 2k received.`. Assert the git commands come first and in
  order; the card given to `run_card` has `path == "cards/task.md"` and `id == "demo"`, and when it is
  called `a.txt` exists in its repo; the hidden tests are copied only after `run_card` (no `hidden_tests`
  directory when it is called); the row values, with hidden stdout `Ran 4 tests in 0.1s\n\nFAILED (failures=1)`
  giving `hidden_passed` 3 and `hidden_total` 4.
- `read_evals` missing file; `format_evals` empty, `3/4`, `-` for None, no trailing spaces.
- CLI, with `patch("llmdev.cli.ROOT", Path(tmp))` on a real Path and a temp `models.toml`,
  `patch("llmdev.cli.server.health")`, `patch("llmdev.cli.evals.run_eval")`, capturing stdout: refused
  when unhealthy; exit 0 and one line in `runs/eval.jsonl` on a full score; exit 1 when `hidden_passed` is
  below `hidden_total`; exit 1 when `hidden_total` is 0; `evals` prints the rows.
