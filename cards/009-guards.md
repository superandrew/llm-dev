+++
id = "009"
title = "Run guards"
edit = ["llmdev/runner.py", "llmdev/cli.py", "tests/test_guards.py"]
read = ["models.toml", "bin/llm", "AGENTS.md", "llmdev/cards.py", "llmdev/registry.py", "tests/test_runner.py"]
checks = ["test -s llmdev/runner.py && test -s tests/test_guards.py", "python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/runner.py llmdev/cli.py", "git add -N -- tests/test_guards.py && git --no-pager diff --check HEAD"]
commit = "feat: guard card runs against hangs, empty and stray files"
edit_format = "whole"
+++

# 009 - Run guards

`passed` must not be true when Aider hung, left a file of the card empty, or touched
files the card does not list. All of this happened in real runs.

## llmdev/runner.py

Add two functions and change `run_card`. Everything else stays identical.

    def changed_paths(repo, run=subprocess.run) -> set
    def empty_files(card, repo) -> list

- `changed_paths`: `run(["git", "status", "--porcelain", "-z", "--untracked-files=all"],
  cwd=repo, capture_output=True, text=True)`. Split stdout on `"\0"`, drop empty items,
  return the set of `item[3:]`.
- `empty_files`: the entries of `card.edit`, in order, that do not exist under `repo` or
  have size 0.

`run_card` gets a new last parameter `timeout_s=2400`:

1. Before Aider: `before = changed_paths(repo, run)`.
2. Run Aider with `timeout=timeout_s` added to the same call. On
   `subprocess.TimeoutExpired`: `timed_out = True` and the Aider returncode is None.
   Otherwise `timed_out = False`.
3. Right after Aider, before the checks:
   `stray = sorted(changed_paths(repo, run) - before - set(card.edit))`.
4. After the checks: `empty = empty_files(card, repo)`.
5. `meta` gets three new keys: `"timed_out"`, `"empty_files"`, `"stray_files"`.
6. `passed` is true only when every check returned 0, and not timed out, and both
   lists are empty.

The checks, `diff.patch` and `meta.json` are still produced after a timeout.

## llmdev/cli.py

`run` gets `--timeout` (int, seconds, default 2400), passed as `timeout_s` to
`runner.run_card`. Keep everything else identical.

## tests/test_guards.py

Never start a process: pass a fake `run`, as `tests/test_runner.py` does. Use a temp
dir as repo with real files for `empty_files`. Cover:

- `changed_paths` on stdout `" M a.py\0?? But wait, a file\0"` gives both paths; empty
  stdout gives an empty set.
- `empty_files`: missing file, empty file, file with content.
- `run_card` with a fake `run` where the status call returns a different stdout before and
  after Aider (count the Aider call in a list):
  - all good -> `passed` True and the three new keys are False, [], [].
  - new path not in the card -> `stray_files` lists it, `passed` False.
  - new path that is in `card.edit` -> not stray.
  - path already changed before Aider -> not stray.
  - edit file empty -> `empty_files` lists it, `passed` False.
  - Aider raises `subprocess.TimeoutExpired` -> `timed_out` True, Aider returncode None,
    `passed` False, `meta.json` and `diff.patch` written.
  - the Aider call receives `timeout=timeout_s`.
- CLI `run --timeout 5` passes `timeout_s=5`, with `patch("llmdev.cli.ROOT", Path(tmp))`
  (a real Path, temp `models.toml`), `patch("llmdev.cli.server.health", return_value=True)`,
  `patch("llmdev.cli.cards.parse")`, `patch("llmdev.cli.runner.run_card",
  return_value={"passed": True})`.
