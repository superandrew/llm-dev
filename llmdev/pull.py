import json
import os
import shutil
import subprocess

from llmdev.registry import Model


class PullError(Exception): ...


def _read_first_line(path: str) -> str:
    """Read first line of a text file, without the newline."""
    with open(path, "r") as f:
        return f.readline().rstrip("\n")


def hf_command(which=shutil.which, read_first_line=_read_first_line) -> str:
    """Return path to hf executable."""
    hf_path = which("hf")
    if hf_path:
        return hf_path

    mlx_server_path = which("mlx_lm.server")
    if mlx_server_path:
        first_line = read_first_line(mlx_server_path)
        if first_line.startswith("#!"):
            python_dir = os.path.dirname(first_line[2:])
            hf_path = os.path.join(python_dir, "hf")
            return hf_path

    raise PullError("Please install mlx-lm to use hf commands")


def pull_command(m: Model, hf: str = "hf") -> list[str]:
    """Build pull command for a model."""
    if m.backend == "ollama":
        return ["ollama", "pull", m.model]
    elif m.backend in ("mlx", "llama"):
        if not m.source:
            raise PullError(f"model {m.name} has no source defined")
        if m.backend == "mlx":
            return [hf, "download", m.source, "--local-dir", m.model]
        else:
            # llama: m.model is full path to GGUF file
            dirname = os.path.dirname(m.model)
            basename = os.path.basename(m.model)
            return [hf, "download", m.source, basename, "--local-dir", dirname]
    else:
        raise PullError(f"unknown backend: {m.backend}")


def pull(m: Model, run=subprocess.run, which=shutil.which, read_first_line=_read_first_line) -> int:
    """Pull/download a model. Returns returncode."""
    if m.backend in ("mlx", "llama"):
        hf = hf_command(which, read_first_line)
    else:
        hf = "hf"
    cmd = pull_command(m, hf)
    result = run(cmd)
    return result.returncode


def add_block(name: str, backend: str, model: str, ctx: int, port: int, source: str = "", args: tuple = ()) -> str:
    """Generate a model block for models.toml."""
    lines = [f"[models.{name}]"]
    lines.append(f'backend = "{backend}"')
    lines.append(f"model = {json.dumps(model)}")
    lines.append(f"ctx = {ctx}")
    lines.append(f"port = {port}")
    if source:
        lines.append(f"source = {json.dumps(source)}")
    if args:
        args_json = json.dumps(list(args))
        lines.append(f"args = {args_json}")
    return "\n" + "\n".join(lines) + "\n"


def next_port(registry: dict[str, Model], backend: str) -> int:
    """Determine next available port for a backend."""
    if backend == "ollama":
        return 11434

    max_port = 8080
    has_non_ollama = False
    for m in registry.values():
        if m.backend != "ollama":
            has_non_ollama = True
            if m.port > max_port:
                max_port = m.port
    if has_non_ollama:
        return max_port + 1
    else:
        return 8080


def add_model(path: str, registry: dict[str, Model], name: str, backend: str, source: str = "", file: str = "", ctx: int = 65536) -> str:
    """Add a model to registry file."""
    if name in registry:
        raise PullError(f"model '{name}' already exists")
    if not all(c.isalnum() or c in "-_" for c in name):
        raise PullError(f"invalid model name '{name}': use letters, digits, - and _")

    if backend == "ollama":
        model = source
        args = ()
        block = add_block(name, backend, model, ctx, port=next_port(registry, backend), source="", args=args)
    elif backend == "mlx":
        # Extract last part of source as model name
        last_part = source.split("/")[-1]
        model = f"~/models/mlx/{last_part}"
        args = ("--max-tokens", "16000")
        block = add_block(name, backend, model, ctx, port=next_port(registry, backend), source=source, args=args)
    elif backend == "llama":
        if not file:
            raise PullError("llama backend requires --file")
        model = f"~/models/gguf/{file}"
        args = ("-ngl", "99")
        block = add_block(name, backend, model, ctx, port=next_port(registry, backend), source=source, args=args)
    else:
        raise PullError(f"unknown backend: {backend}")

    with open(path, "a") as f:
        f.write(block)

    return block
