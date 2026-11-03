# llm-dev

Deterministic tooling to serve, benchmark and drive local LLMs on a Mac
(Ollama, llama.cpp `llama-server`, MLX `mlx_lm.server`). The code is written by a local model
(Aider + Qwen) from the cards in `cards/`, reviewed by Claude, committed by Andrew.
Python >= 3.11, standard library only.

## Quick start

    bin/llm list
    bin/llm serve qwen-coder-next-mlx6
    bin/llm run cards/<card>.md --model qwen-coder-next-mlx6
    bin/llm stop qwen-coder-next-mlx6

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

- Working model: `qwen-coder-next-mlx6` (Qwen3-Coder-Next 80B, MLX 6-bit, 60 GB).
- Faster fallback: `qwen-coder-next-mlx` (same model, MLX 4-bit, 42 GB, about 10% faster decode).
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
