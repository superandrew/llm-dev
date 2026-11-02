+++
id = "006"
title = "Add and download models"
edit = ["llmdev/registry.py", "llmdev/pull.py", "llmdev/cli.py", "tests/test_pull.py"]
read = ["models.toml", "llmdev/server.py"]
checks = ["python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/registry.py llmdev/pull.py llmdev/cli.py", "git add -N -- llmdev/pull.py tests/test_pull.py && git --no-pager diff --check"]
commit = "feat: add and download models"
edit_format = "whole"
+++

# 006 - Add and download models

Trying a new model must take two commands: `llm add`, then `llm pull`.

## llmdev/registry.py

Add `source: str = ""` as the last field of `Model` and accept an optional
`source` key in `_parse_model`. Nothing else changes.

## llmdev/pull.py

    class PullError(Exception): ...

    def hf_command(which=shutil.which, read_first_line=_read_first_line) -> str
    def pull_command(m, hf="hf") -> list[str]
    def pull(m, run=subprocess.run, which=shutil.which, read_first_line=_read_first_line) -> int
    def add_block(name, backend, model, ctx, port, source="", args=()) -> str
    def next_port(registry, backend) -> int
    def add_model(path, registry, name, backend, source, file="", ctx=65536) -> str

- `_read_first_line(path)`: first line of a text file, without the newline.
- `hf_command`: `which("hf")` when found. Otherwise find `which("mlx_lm.server")`,
  read its first line (`#!/some/dir/python`) and return `/some/dir/hf`. Neither
  found -> PullError saying to install mlx-lm.
- `pull_command`:
  - ollama: `["ollama", "pull", m.model]`
  - mlx: `[hf, "download", m.source, "--local-dir", m.model]`
  - llama: `[hf, "download", m.source, <basename of m.model>, "--local-dir", <dirname of m.model>]`
  - mlx or llama with an empty source -> PullError naming the model.
- `pull`: ollama does not need `hf`, so call `hf_command` only for mlx and llama.
  Runs the command with `run(cmd)` (no capture, the user sees the progress) and
  returns its returncode.
- `add_block`: returns this text, strings written with `json.dumps`, the `source`
  line only when source is set, the `args` line only when args is set:


      [models.NAME]
      backend = "mlx"
      model = "~/models/mlx/dir"
      ctx = 65536
      port = 8082
      source = "org/repo"
      args = ["--max-tokens", "16000"]

  The first line of the text is empty and the text ends with a newline.
- `next_port`: ollama -> 11434. Otherwise 1 + the highest port among the registry
  models whose backend is not ollama, or 8080 when there is none.
- `add_model`: name already in registry, or with characters other than letters,
  digits, `-` and `_` (it becomes a TOML key) -> PullError. Appends `add_block` to the
  file at `path` and returns the block. Per backend:
  - ollama: model = source, no `source` line, no args.
  - mlx: model = `~/models/mlx/<last path part of source>`,
    args = `("--max-tokens", "16000")`.
  - llama: file is required, otherwise PullError. model =
    `~/models/gguf/<file>`, args = `("-ngl", "99")`.

## llmdev/cli.py

Add two subcommands. Keep everything else identical.

- `add NAME --backend {ollama,llama,mlx} --source S [--file F] [--ctx 65536]` -
  `pull.add_model(str(ROOT / "models.toml"), ...)`, prints the block, exit 0.
- `pull NAME` - `pull.pull(m)`; exit 0 and print "pulled NAME" when the returncode
  is 0, otherwise exit with that returncode and a message on stderr.

Catch `pull.PullError` in `main` like the other errors.

## tests/test_pull.py

Never start a process. Cover: `source` loaded by `registry.load` and default "";
`pull_command` for the three backends and the empty source error; `hf_command`
from `which`, from the shebang, and the error; `pull` returning the fake's
returncode and ollama never calling `which`; exact text of `add_block`;
`next_port` with and without other models; `add_model` for the three backends
loaded back with `registry.load` from a temp file, duplicate name, llama without
file; CLI `add` and `pull` exit codes with `patch("llmdev.cli.ROOT", Path(tmp))`
and `patch("llmdev.cli.pull.pull")`.
