+++
id = "007"
title = "Sweep benchmark and results"
edit = ["llmdev/bench.py", "llmdev/lab.py", "llmdev/cli.py", "tests/test_lab.py"]
read = ["models.toml", "bin/llm", "llmdev/registry.py", "llmdev/server.py"]
checks = ["test -s llmdev/lab.py && test -s tests/test_lab.py", "python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/bench.py llmdev/lab.py llmdev/cli.py", "git add -N -- llmdev/lab.py tests/test_lab.py && git --no-pager diff --check"]
commit = "feat: sweep benchmark and results table"
edit_format = "whole"
+++

# 007 - Sweep benchmark and results

`llm bench` mixes model load, prompt cache and prefill in one number. A sweep
measures the prefill speed as the slope of time over prompt size, on prompts the
server cannot have in its cache.

## llmdev/bench.py

Add `seed: int = 0` as the last parameter of `run` and use
`make_prompt(n_words, seed)`. Nothing else changes.

## llmdev/lab.py

    SWEEP_WORDS = (3000, 6000, 12000, 24000)

    def slope_tps(points) -> float | None
    def sweep(m, seed, words=SWEEP_WORDS, max_tokens=128, run=bench.run) -> list[dict]
    def summarize(rows) -> dict
    def read_rows(path) -> list[dict]
    def latest_sweeps(rows) -> list[dict]
    def format_table(summaries) -> str

- `slope_tps`: points are `(prompt_tokens, ttft_s)`. Least squares slope `b` of
  ttft over tokens; returns `round(1 / b, 1)`. Fewer than 2 points, or `b <= 0`
  -> None.
- `sweep`: first `run(m, n_words=200, max_tokens=16, seed=seed)` to load the model;
  its `ttft_s` is `load_s`. Then one `run` per entry of `words`, same seed, in
  order. Returns the rows of those runs, each with two more keys: `"seed"` and
  `"load_s"`. The first run is not returned.
- `summarize`: from the rows of one sweep returns `{"model", "backend", "prefill_tps"
  (slope_tps), "decode_tps" (median of the non-None values, rounded to 1 decimal,
  None when there are none), "load_s", "ttft_max_s" (ttft_s of the row with the most
  prompt tokens), "sweep"}`.
- `read_rows`: one JSON object per line; a missing file -> `[]`.
- `latest_sweeps`: keep only rows with a `"sweep"` key; for each `model` take the rows
  with its highest `sweep` value and `summarize` them. Sorted by model.
- `format_table`: a header line, then one line per summary, columns model, backend,
  prefill t/s, decode t/s, load s, ttft max s, sweep. None shown as `-`. Columns are
  padded with spaces, and no line ends with spaces. No summaries -> "no sweeps yet".

## llmdev/cli.py

Add two subcommands. Keep everything else identical.

- `sweep NAME` - fails with exit 1 and a message if `server.health` is False. The
  seed is `int(time.time()) % 50`, the sweep id is `datetime.now().isoformat()`.
  Calls `lab.sweep`, adds `"sweep"` to every row, appends the rows to
  `ROOT/runs/bench.jsonl` as `bench` does, prints `format_table` of the summary.
- `results` - prints `format_table(latest_sweeps(read_rows(ROOT/runs/bench.jsonl)))`.

## tests/test_lab.py

Never start a process, never open a socket. Cover: `slope_tps` on points
`(1000, 1.0), (2000, 2.0), (3000, 3.0)` -> 1000.0, one point -> None, flat points ->
None; `sweep` with a fake `run`: number of calls, same seed in all calls, first call
200 words, `load_s` from the first call; `summarize` with an even and an odd number
of decode values and all None; `read_rows` on a missing file; `latest_sweeps` picks the
latest sweep per model and skips rows without `sweep`; `format_table` empty and no line
ending with spaces; `bench.run` passes `seed` to the prompt (with a fake `post`);
CLI `sweep` refused when unhealthy, CLI `sweep` writes rows with `sweep`, CLI `results`.
