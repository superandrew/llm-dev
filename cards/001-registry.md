+++
id = "001"
title = "Model registry"
edit = ["llmdev/registry.py", "tests/test_registry.py"]
read = ["models.toml"]
checks = ["python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/registry.py", "git diff --check"]
commit = "feat: model registry loaded from models.toml"
+++

# 001 - Model registry

Load and validate `models.toml` (see the file for the format).

## llmdev/registry.py

    BACKENDS = ("ollama", "llama", "mlx")

    class RegistryError(Exception): ...

    @dataclass(frozen=True)
    class Model:
        name: str; backend: str; model: str; ctx: int; port: int
        host: str = "127.0.0.1"; args: tuple = (); env: tuple = (); notes: str = ""

    def load(path) -> dict[str, Model]
    def get(registry, name) -> Model

- `load` reads the file with `tomllib`. `[defaults]` may hold `host`.
  Each `[models.<name>]` table becomes a Model; `host` falls back to defaults.
- Required keys: backend, model, ctx, port. Allowed extra keys: host, args
  (list of str), env (table of str to str), notes. Any other key -> RegistryError.
- `env` is stored as a sorted tuple of (key, value) pairs (keeps Model hashable).
- backend not in BACKENDS, ctx not a positive int, port not in 1..65535,
  missing required key -> RegistryError. Every message starts with
  `models.<name>: ` and names the field.
- For backends llama and mlx, a `model` starting with `~` is expanded with
  `os.path.expanduser`. Ollama tags are never touched.
- No `[models]` table, or an empty one -> RegistryError("no models defined").
- `get` raises RegistryError for an unknown name, listing the available names
  sorted and comma separated.

## tests/test_registry.py

Write TOML strings to a `tempfile.TemporaryDirectory`. Cover: valid file with
two models; host default and override; args default `()`; env sorted tuple;
missing ctx; bad backend; port 70000; unknown key; tilde expanded for llama but
not for ollama; empty registry; `get` unknown name message lists names.
