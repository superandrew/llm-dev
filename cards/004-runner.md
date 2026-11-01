+++
id = "004"
title = "Card runner"
edit = ["llmdev/cards.py", "llmdev/runner.py", "tests/test_runner.py"]
read = ["llmdev/registry.py", "llmdev/server.py", "bootstrap.py", "cards/001-registry.md"]
checks = ["python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/cards.py llmdev/runner.py", "git diff --check"]
commit = "feat: run a card with Aider and record the outcome"
+++

# 004 - Card runner

Turn `bootstrap.py` into tested code that also re-runs the checks itself and
records every run. Cards look like `cards/001-registry.md`: TOML front matter
between a first line `+++` and the next `+++` line, then Markdown.

## llmdev/cards.py

    class CardError(Exception): ...

    @dataclass(frozen=True)
    class Card:
        path: str; id: str; title: str; edit: tuple; read: tuple
        checks: tuple; commit: str; edit_format: str = ""

    def parse(path) -> Card

Required keys: id, title, edit, checks, commit. Optional: read (default ()),
edit_format. Missing `+++` lines or missing keys -> CardError naming the path.

## llmdev/runner.py

    BASE_FLAGS = [the fixed flags of bootstrap.py, from "--no-auto-commits"
                  through "--timeout", "900"]

    def aider_model(m, base_url) -> tuple[str, dict]
    def default_message(card) -> str
    def aider_command(card, m, base_url, history_path, message=None) -> tuple[list[str], dict]
    def run_checks(checks, cwd, run=subprocess.run) -> list[dict]
    def run_card(card, m, base_url, repo, runs_dir, run=subprocess.run, now=datetime.now, extra="") -> dict

- `aider_model`: ollama -> (`"ollama_chat/" + m.model`,
  `{"OLLAMA_API_BASE": base_url without the trailing "/v1"}`); llama and mlx ->
  (`"openai/" + m.model`, `{"OPENAI_API_BASE": base_url, "OPENAI_API_KEY": "local"}`).
- `default_message`: the same text bootstrap.py builds.
- `aider_command`: `["aider", "--model", <aider model>, *BASE_FLAGS,
  "--chat-history-file", history_path, "--read", "AGENTS.md", "--read",
  card.path, ("--read", r for each card.read), "--test-cmd", " && ".join(checks),
  "--auto-test", "--message", message or default_message(card), *card.edit]`;
  add `"--edit-format", card.edit_format` after the model when set. Returns
  the command and the env from `aider_model`.
- `run_checks`: each check run with `shell=True, cwd=cwd,
  capture_output=True, text=True`; returns `{"cmd", "returncode", "output"}`
  with output = last 4000 chars of stdout + stderr.
- `run_card`:
  1. run dir = `runs_dir/<now():%Y%m%d-%H%M%S>-<card.id>/`, created.
  2. run Aider (`cwd=repo`, `env=os.environ | env`), history file
     `aider.md` in the run dir; message = default + " " + extra when extra.
  3. `run_checks(card.checks, repo)` - never trust Aider's own result.
  4. `git add -N -- <edit files>` then `git diff -- <edit files>` in repo;
     write the diff to `diff.patch`.
  5. write `meta.json`: card id, title, model name, backend, started, ended
     (ISO), aider returncode, checks, `passed` (all returncodes 0).
  6. return the meta dict.

## tests/test_runner.py

Cover: parse valid card, missing keys, missing `+++`; command for ollama and
llama models; edit_format; extra message; run_card with a fake `run` that
records calls and returns objects with returncode/stdout/stderr, a fixed
`now`, in a temp dir: files written, passed true and false.
