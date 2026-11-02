+++
id = "010"
title = "Run metrics"
edit = ["llmdev/runner.py", "llmdev/metrics.py", "llmdev/cli.py", "tests/test_metrics.py"]
read = ["models.toml", "bin/llm", "AGENTS.md", "README.md", "llmdev/lab.py"]
checks = ["test -s llmdev/metrics.py && test -s tests/test_metrics.py", "python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/runner.py llmdev/metrics.py llmdev/cli.py", "git add -N -- llmdev/metrics.py tests/test_metrics.py && git --no-pager diff --check HEAD"]
commit = "feat: measure card runs"
edit_format = "whole"
+++

# 010 - Run metrics

Every card run leaves `runs/<stamp>-<id>/meta.json` and `aider.md`. `llm runs` turns them
into one table, to see what the tool really costs on real work.

## llmdev/runner.py

Change only `default_message`. When `card.edit_format == "whole"`, the sentence
`Output SEARCH/REPLACE blocks now.` is replaced by:

    Output each changed file once, as its path alone on one line followed by a fenced code block with the complete file, then stop. Write no other fenced code block: any text line before a fence becomes a file name.

All other cards get the same text as today.

## llmdev/metrics.py

    def aider_stats(text) -> dict
    def read_runs(runs_dir) -> list[dict]
    def format_runs(rows) -> str

- `aider_stats`: from the text of `aider.md` returns `{"rounds", "sent", "received",
  "applied"}`. Each line containing `Tokens: 20k sent, 2.8k received.` is one round; add up
  sent and received as integers, where `20k` is 20000, `2.8k` is 2800 and `950` is 950.
  `applied` counts the lines containing `Applied edit to`. No such lines -> all zero.
- `read_runs`: for each directory directly under `runs_dir` holding a `meta.json`, sorted by
  directory name, one dict: `run` (directory name), `card` (`card_id`), `model`
  (`model_name`), `backend`, `duration_s` (`ended` minus `started`, whole seconds), `passed`,
  `timed_out`, `stray` (length of `stray_files`), `empty` (length of `empty_files`), plus the
  `aider_stats` keys. Older records miss some keys: `timed_out`, `stray` and `empty` are None
  then. A missing `aider.md` gives zero stats. A missing `runs_dir` gives `[]`.
- `format_runs`: a header and one line per row, with columns run, card, model, passed, duration
  s, rounds, sent, received, applied, stray, empty, timed out. Padded with spaces, None shown as
  `-`, no line ends with spaces. No rows -> `no runs yet`.

## llmdev/cli.py

Add `runs [--card ID] [--model NAME]`: prints `format_runs` of `read_runs(str(ROOT / "runs"))`,
keeping only rows that match the given filters. Add `metrics` to the `from llmdev import` line.
Keep everything else identical.

## tests/test_metrics.py

Never start a process. Use a temp dir with real files. Cover: `default_message` for a whole card
(has `fenced code block`, no `SEARCH/REPLACE`) and for a normal card (has `SEARCH/REPLACE`);
`aider_stats` with lines `> Tokens: 20k sent, 2.8k received.` and `> Tokens: 950 sent, 12 received.`
gives rounds 2, sent 20950, received 2812, and `applied` from two `> Applied edit to a.py` lines;
empty text gives zeros; `read_runs` with a new record, an old record without the guard keys, a
directory without `meta.json` (skipped), a missing `aider.md`, a missing `runs_dir`; duration of
`2026-01-01T10:00:00` to `2026-01-01T10:01:30` is 90; `format_runs` empty, `-` for None, no trailing
spaces; CLI `runs` with `--card` filter, with `patch("llmdev.cli.ROOT", Path(tmp))` on a real Path and
a temp `models.toml`, capturing stdout.
