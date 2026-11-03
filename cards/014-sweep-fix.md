+++
id = "014"
title = "Sweep on reasoning models"
edit = ["llmdev/bench.py", "llmdev/cli.py", "tests/test_bench.py"]
read = ["models.toml", "bin/llm", "AGENTS.md", "llmdev/lab.py", "llmdev/server.py"]
checks = ["python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/bench.py llmdev/cli.py", "git --no-pager diff --check HEAD"]
commit = "fix: sweep measures reasoning models and reports timeouts"
edit_format = "diff"
+++

# 014 - Sweep on reasoning models

Reasoning models (qwen3.8, gemma4) stream their first tokens in `delta.reasoning_content` or
`delta.reasoning`, not in `delta.content`. The bench only looks at `content`, so with 128
tokens all spent on reasoning it finds no first token: `ttft_s` and `decode_tps` stay `None`.
Also a server that does not answer within the socket timeout ends `llm sweep` with a traceback.

## llmdev/bench.py

In `measure`, a delta counts as a generated token when any of `content`, `reasoning_content`
or `reasoning` is a non-empty string. Replace the two lines

    content = delta.get("content")
    if content:

with

    content = delta.get("content") or delta.get("reasoning_content") or delta.get("reasoning")
    if isinstance(content, str) and content:

Nothing else changes in `measure`.

## llmdev/cli.py

In the `sweep` command, wrap `rows = lab.sweep(m, seed=seed)` so that `TimeoutError` or
`OSError` (which covers `urllib.error.URLError`) prints to stderr
`sweep failed on <name>: <error>` and returns 1, without writing anything to `bench.jsonl`.

## tests/test_bench.py

Add to the existing tests for `measure`:

- Events, with `t0 = 0.0`: at time 1.0 `{"choices": [{"delta": {"reasoning_content": "a"}}]}`,
  at 2.0 `{"choices": [{"delta": {"reasoning_content": "b"}}]}`, at 3.0
  `{"choices": [{"delta": {"content": "c"}}]}`, at 3.0
  `{"usage": {"prompt_tokens": 100, "completion_tokens": 3}}`.
  `ttft_s` is `1.0` and `decode_tps` is `1.0` (2 tokens over 2 seconds).
- The same with the key `reasoning` instead of `reasoning_content`: `ttft_s` is `1.0`.
- A delta `{"reasoning_content": None, "content": None}` alone gives `ttft_s` `None`.
