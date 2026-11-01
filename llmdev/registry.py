import os
import tomllib
from dataclasses import dataclass


BACKENDS = ("ollama", "llama", "mlx")


class RegistryError(Exception): ...


@dataclass(frozen=True)
class Model:
    name: str
    backend: str
    model: str
    ctx: int
    port: int
    host: str = "127.0.0.1"
    args: tuple = ()
    env: tuple = ()
    notes: str = ""


def load(path: str) -> dict[str, Model]:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    defaults = data.get("defaults", {})
    host = defaults.get("host", "127.0.0.1")

    models_data = data.get("models", {})
    if not models_data:
        raise RegistryError("no models defined")

    registry = {}
    for name, model_data in models_data.items():
        registry[name] = _parse_model(name, model_data, host)

    return registry


def _parse_model(name: str, data: dict, default_host: str) -> Model:
    required_keys = ["backend", "model", "ctx", "port"]
    allowed_keys = set(required_keys) | {"host", "args", "env", "notes"}

    unknown_keys = set(data.keys()) - allowed_keys
    if unknown_keys:
        raise RegistryError(f"models.{name}: unknown key(s): {', '.join(sorted(unknown_keys))}")

    # Validate required keys in fixed order
    for key in required_keys:
        if key not in data:
            raise RegistryError(f"models.{name}: missing required key '{key}'")

    backend = data["backend"]
    if backend not in BACKENDS:
        raise RegistryError(f"models.{name}: invalid backend '{backend}'")

    ctx = data["ctx"]
    if isinstance(ctx, bool) or not isinstance(ctx, int) or ctx <= 0:
        raise RegistryError(f"models.{name}: ctx must be a positive integer")

    port = data["port"]
    if isinstance(port, bool) or not isinstance(port, int) or not (1 <= port <= 65535):
        raise RegistryError(f"models.{name}: port must be an integer between 1 and 65535")

    host = data.get("host", default_host)

    # Handle args
    args_raw = data.get("args", [])
    if not isinstance(args_raw, list):
        raise RegistryError(f"models.{name}: args must be a list")
    args = tuple(args_raw)

    # Handle env
    env_raw = data.get("env", {})
    if not isinstance(env_raw, dict):
        raise RegistryError(f"models.{name}: env must be a table")
    env = tuple(sorted(env_raw.items()))

    model_path = data["model"]
    if backend in ("llama", "mlx") and model_path.startswith("~"):
        model_path = os.path.expanduser(model_path)

    notes = data.get("notes", "")

    return Model(
        name=name,
        backend=backend,
        model=model_path,
        ctx=ctx,
        port=port,
        host=host,
        args=args,
        env=env,
        notes=notes,
    )


def get(registry: dict[str, Model], name: str) -> Model:
    if name not in registry:
        available = ", ".join(sorted(registry.keys()))
        raise RegistryError(f"unknown model '{name}'. Available: {available}")
    return registry[name]
