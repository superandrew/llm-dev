+++
id = "003"
title = "Benchmark prefill and decode"
edit = ["llmdev/bench.py", "tests/test_bench.py"]
read = ["llmdev/registry.py", "llmdev/server.py"]
checks = ["python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/bench.py", "git --no-pager diff --check"]
commit = "feat: benchmark prefill and decode speed separately"
+++

# 003 - Benchmark prefill and decode

Measure time to first token (prefill) and generation speed (decode) through
the OpenAI-compatible endpoint that all three backends expose.

## llmdev/bench.py

    WORDS = (a fixed tuple of 50 plain English words, written in the file)

    def make_prompt(n_words, seed=0) -> str
    def parse_sse(lines) -> Iterator[dict]
    def measure(t0, timed_events) -> dict
    def run(m, n_words=2000, max_tokens=128, post=_post, clock=time.perf_counter) -> dict

- `make_prompt`: `n_words` words taken cyclically from WORDS starting at index
  `seed % len(WORDS)`, joined by spaces, then the line
  "\n\nSummarise the text above in one sentence." Same inputs, same output.
- `parse_sse`: accepts str or bytes lines; keeps lines starting with `data: `;
  skips `data: [DONE]` and blank payloads; yields `json.loads` of the rest.
- `timed_events` is a list of `(time, event)`. A content event has a non-empty
  `choices[0]["delta"]["content"]`. Usage is the `usage` dict of any event
  that has one (last wins).
- `measure` returns:
  - `ttft_s`: first content time minus t0 (None if no content);
  - `completion_tokens`: usage value, else the number of content events;
  - `prompt_tokens`: usage value or None;
  - `prefill_tps`: prompt_tokens / ttft_s when both exist, else None;
  - `decode_tps`: (completion_tokens - 1) / (last content time - first content
    time) when that span > 0 and completion_tokens > 1, else None.
  Round floats to 2 decimals.
- `_post(url, payload, timeout=600)` POSTs JSON with urllib and yields the
  response lines.
- `run` posts to `base_url(m) + "/chat/completions"` with
  `{"model": m.model, "messages": [{"role": "user", "content": prompt}],
  "stream": True, "stream_options": {"include_usage": True},
  "max_tokens": max_tokens, "temperature": 0}`. `t0 = clock()` right before
  the post; each parsed event is stamped with `clock()`. Returns `measure`'s
  dict plus `{"model": m.name, "backend": m.backend, "n_words": n_words}`.

## tests/test_bench.py

Cover: prompt determinism and seed offset; SSE parsing of str and bytes, DONE
and non-data lines; measure with usage, without usage, with no content; run
with a fake post yielding SSE lines and a fake clock (iterator of floats),
checking the payload and the numbers.
