# Supervisor guide

For the frontier model (Claude Code, Codex, ChatGPT) or the human who drives llm-dev.
`AGENTS.md` is for the local model that writes the code; this file is for whoever writes the
cards, launches the runs and reviews them.

## Who does what

| Step | Who | Why |
|---|---|---|
| Understand the problem, design, split it into cards | supervisor | quality matters most here and it costs few tokens |
| Write the code of a card | Qwen3-Coder-Next on MLX 6-bit, Aider | about 14 s for a small card, local, free |
| Open-ended card that needs test-fix loops | OpenCode on `llama-server` | slower (about 2 min) but fixes its own failures |
| Review the diff, commit | supervisor | reading a diff is cheap |

Do not put reasoning in the local model: a dense model that thinks runs at about 14 tokens/s on
this Mac, so one answer takes minutes. Reason once, in the card.

Write the code yourself when the card would have to dictate every line, or the logic is subtle:
the local model pays off on mechanical work (tests, CLI wiring, parsing, boilerplate).

## The loop

1. Draft the card outside the repo (a scratch folder): a file written into the repo during a run
   shows up as a stray file.
2. Copy it to `cards/NNN-name.md`, `git add` it, start the model and run it:

        bin/llm serve qwen-coder-next-mlx6
        bin/llm run cards/NNN-name.md --model qwen-coder-next-mlx6 --timeout 1800

   For an agent: `bin/llm serve qwen-coder-next-gguf` and add `--harness opencode` (or `qwen`).
3. Review. Never trust `passed` alone:
   - `git status --short`: the `edit` files changed, nothing else (no stray files, nothing
     outside the repo).
   - Read the diff. Run the whole suite yourself: `python3 -m unittest discover -s tests`.
   - For a TUI, drive it in a real pseudo-terminal.
4. Fix one or two lines by hand at most (usually a wrong expected value in a test). More than
   that: rewrite the card and run it again.
5. Commit with the card's `commit` message, only when the user allows it.
6. `bin/llm stop NAME` when done: the model holds 40-60 GB of GPU memory.

## Writing cards

- TOML front matter: `id`, `title`, `edit`, `read`, `checks`, `commit`, `edit_format`.
- `edit_format = "whole"` only for small new files. On existing files use `diff`: with `whole`
  the model rewrote `cli.py` and deleted commands.
- List under `read` every repo file the reply may mention (`models.toml`, `bin/llm`,
  `.aider.model.settings.yml`...). When a reply names a file outside the chat, Aider asks to
  add it, drops the reply's edits and the model then claims it is done: a green run with no diff.
- Cards with exact code and exact test inputs finish in about a minute and one round.
  Open-ended cards take about 10 minutes and often do not finish alone.
- When the model ignores an instruction twice, put the exact code in the card.
- Give expected test values as expressions (`65 * fit.GB`), not computed numbers.
- A `grep` check must match text the card itself dictates.
- A new test file needs a check that runs it (`python3 -m unittest tests.test_x -v`): an empty
  test module passes `discover`.
- With `whole`, any text line before a code fence becomes a file name.

## Models and engines

Measured in November 2026 (see the README for the numbers):

- `qwen-coder-next-mlx6`: working model with Aider.
- `qwen-coder-next-mlx`: same model in 4-bit, a little faster, a little less reliable.
- `qwen-coder-next-gguf` (`llama-server`): for agents. `mlx_lm.server` cannot parse Qwen3-Coder
  tool calls, so agents stop at their first step on MLX.
- Ollama: slowest on real cards.
- Before downloading a new model: `bin/llm fit NAME`.

## Known traps

- `mlx_lm.server` crashes on runaway replies of about 15k tokens: MLX entries cap at 8192.
- OpenCode uses `$PWD` as its working folder; the runner sets it to the run's repo.
- Qwen Code needs `node` on `PATH` (installed with `fnm`).
- Agents run shell commands without asking and without a sandbox: run them only on throwaway
  repos (evals, clones) or on a clean tree you can reset.
- `llm_errors` in `meta.json` lists model or server errors: a run with errors is a broken
  server, not a weak model.

## Codex

Codex reads `AGENTS.md` too: as supervisor it follows this file, not the rules in `AGENTS.md`.
`bin/llm run` talks to the model server on `127.0.0.1`, so Codex's sandbox must allow local
network access.
