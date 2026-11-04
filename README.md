# llm-dev

Deterministic tooling to serve, benchmark and drive local LLMs on a Mac
(Ollama, llama.cpp `llama-server`, MLX `mlx_lm.server`). The code is written by a local model
(Aider + gpt-oss-120b) from the cards in `cards/`, reviewed by a supervisor (Claude or Codex, see
`SUPERVISOR.md`), committed by Andrew.
Python >= 3.11, standard library only.

## Quick start

    bin/llm list
    bin/llm serve gpt-oss-120b-gguf
    bin/llm run cards/<card>.md --model gpt-oss-120b-gguf
    bin/llm stop gpt-oss-120b-gguf

## Commands

| Command | What it does |
|---|---|
| `list` | models in `models.toml` |
| `serve NAME` | start a model server |
| `stop NAME` | stop a model server |
| `status [NAME]` | check a model server status |
| `bench NAME` | one prefill and decode measure |
| `add NAME --backend B --source S` | register a model |
| `pull NAME` | download it |
| `sweep NAME` | prefill, decode and load over growing prompts |
| `results` | latest sweep per model |
| `run CARD --model NAME [--harness H]` | Aider (or `qwen`, `opencode`) works on a card, then the checks run |
| `runs` | table of card runs |
| `eval NAME --model M [--harness H]` | a card in a throwaway repo, scored by hidden tests |
| `evals` | table of evals |
| `tui` | terminal lab |

## Models

- Working model: `gpt-oss-120b-gguf` (gpt-oss-120b, MXFP4 as released, 63 GB, `llama-server`).
- Fast fallback for small cards: `qwen-coder-next-mlx6` (Qwen3-Coder-Next 80B, MLX 6-bit, 60 GB);
  `qwen-coder-next-mlx` is the same in 4-bit (42 GB, about 10% faster decode).
- Model comparison, November 2026, Aider, 3 x `durations` and 3 x `cron`, each run started with
  the Mac at nominal thermal pressure:

  | Model | durations | cron |
  |---|---|---|
  | `gpt-oss-120b-gguf` | 3/3, 65-66/66 hidden, ~30 s | 3/3, 75-86/89, ~85 s, one round |
  | `qwen-coder-next-mlx6` | 3/3, 65/66, ~16 s | 1/3, 77-78/89, up to 437 s |
  | `qwen36-mlx6-nothink` (Qwen3.6 35B A3B) | 3/3, 60-64/66, ~40 s | 2/3, 69-72/89, one endless loop |
  | Nanbeige4.3 33B (dense, removed) | 0/2, 11 tokens/s | 0/3 |

  On card 011 gpt-oss wrote code that passes the real 11 tests in 2 replays of 3 (Qwen 6-bit:
  1 of 2), but every replay failed its own tests: local models write wrong tests (a real
  `models.toml` loaded, a clock not faked) more often than wrong code.
- gpt-oss-120b on `mlx_lm.server` fails: the harmony tags (`<|channel|>final<|message|>`) end up
  in the reply and Aider takes them for a file name. Qwen3.6 with thinking on returns an empty
  reply: the reasoning fills the 8192-token cap and Aider ignores the `reasoning` field.
- Reserve: `qwen38-mlx` (Qwen3.8 27B, MLX 4-bit, 15 GB), thinking off with
  `--chat-template-args '{"enable_thinking":false}'`.
- Engine comparison, November 2026, same Qwen3-Coder-Next, `durations` eval x5 and card 011 x2:
  MLX 6-bit passed 5/5 in 12-16 s at the first round and card 011 with 11/11 and 10/11 hidden
  tests in 6-9 min. llama.cpp `llama-server` reads prompts 50% faster and loads in 0.5 s, but
  Qwen needed 2 rounds more often, so it finished later (50-90 s); speculative decoding
  (`--spec-type ngram-mod`) and big batches (`-b 4096 -ub 2048`) gave no gain. Ollama timed out
  twice on card 011.
- Agents (`--harness opencode` or `qwen`) need `llama-server` (Ollama untested): `mlx_lm.server` fails to
  parse Qwen3-Coder tool calls. On `durations` they passed 5/5 with 64-66/66 hidden tests but took
  109 s (OpenCode) and 163 s (Qwen Code) median, against 14 s for Aider on MLX.
- `mlx_lm.server` answers with at most 512 tokens unless the model has `--max-tokens` in `args`;
  long runaway replies crash it (`metal::malloc Resource limit`), so the MLX models cap at 8192.

## How a run is judged

- `run` saves `aider.md` (`agent.log` for an agent), `diff.patch` and `meta.json` in `runs/<time>-<card>/`.
- `passed` is true only when every check returns 0, Aider did not time out, no `edit` file is
  empty (`empty_files`) and no file outside `edit` changed (`stray_files`). Before the checks the
  runner removes trailing spaces from the `edit` files and lists them in `stripped_files`.
- `llm_errors` lists the model or server errors found in the Aider history: a run with errors
  is a broken server, not a weak model.
- Checks run with a CPU limit of 120 s per process (`ulimit -t`) and a wall limit of 300 s, hidden
  tests with the same wall limit: code with an endless loop fails instead of hanging the run.

## Writing cards for Aider

- `edit_format = "whole"` only for small new files; `diff` for existing files.
- List under `read` every repo file the reply may mention: Aider discards a reply that names a
  file outside the chat.
- When the model ignores an instruction twice, put the exact code in the card.

## Cards

| Card | What |
|---|---|
| 001 | model registry |
| 002 | serve / stop / status |
| 003 | bench |
| 004 | card runner |
| 005 | `bin/llm` CLI |
| 006 | `add` and `pull` |
| 007 | `sweep` and `results` |
| 008 | `tui` |
| 009 | run guards |
| 010 | `runs` |
| 011 | `eval` with hidden tests |
| 012 | strip trailing spaces |
| 013 | model errors |
| 014 | sweep on reasoning models |
| 015 | this README |
| 016 | GPU, memory and swap |
| 017 | colourful TUI |
| 018 | fit check |
| 019 | `fit` and `pull` check the disk |
| 020 | agent harnesses |
| 021 | `--harness` on `run` and `eval` |
| 022 | time limits on checks and hidden tests |
