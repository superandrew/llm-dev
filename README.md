# llm-dev

Deterministic tooling around local LLMs; the code is written by a local model
(Aider + Qwen) from the cards in `cards/`, reviewed by Claude, committed by Andrew.

| Card | What | Status |
|---|---|---|
| 001 | model registry (`models.toml`) | ready |
| 002 | serve / stop / status | ready (after 001) |
| 003 | bench: prefill vs decode | ready (after 002) |
| 004 | card runner with independent checks and run records | ready (after 002) |
| 005 | `bin/llm` CLI | ready (after 003, 004) |

Until 005 is done: `python3 bootstrap.py cards/<card>.md`.
After: `bin/llm run cards/<card>.md --model qwen-coder-next`.
