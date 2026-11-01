import os
import signal
import subprocess
import urllib.request
from typing import Callable

from llmdev.registry import Model


class ServerError(Exception): ...


def build_command(m: Model) -> tuple[list[str], dict[str, str]]:
    """Build command and environment for a model backend."""
    env = dict(m.env)

    if m.backend == "ollama":
        cmd = ["ollama", "serve"]
        env["OLLAMA_HOST"] = f"{m.host}:{m.port}"
        env["OLLAMA_CONTEXT_LENGTH"] = str(m.ctx)
    elif m.backend == "llama":
        cmd = [
            "llama-server",
            "-m", m.model,
            "-c", str(m.ctx),
            "--host", m.host,
            "--port", str(m.port),
            "--jinja",
        ]
        cmd.extend(m.args)
    elif m.backend == "mlx":
        cmd = [
            "mlx_lm.server",
            "--model", m.model,
            "--host", m.host,
            "--port", str(m.port),
        ]
        cmd.extend(m.args)
    else:
        raise ServerError(f"unknown backend: {m.backend}")

    return cmd, env


def base_url(m: Model) -> str:
    """Return the base URL for a model."""
    return f"http://{m.host}:{m.port}/v1"


def _fetch(url: str, timeout: int = 2) -> int:
    """Fetch URL and return HTTP status code."""
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.getcode()
    except Exception:
        return 0


def health(m: Model, fetch: Callable = _fetch) -> bool:
    """Check if model server is healthy."""
    try:
        url = base_url(m) + "/models"
        return fetch(url) == 200
    except Exception:
        return False


def _alive(pid: int) -> bool:
    """Check if process is alive."""
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


def start(
    m: Model,
    state_dir: str,
    spawn: Callable = subprocess.Popen,
    fetch: Callable = _fetch,
    alive: Callable = _alive,
) -> int | None:
    """Start model server if not already running."""
    # Check if already healthy
    if health(m, fetch):
        return None

    pid_file = os.path.join(state_dir, f"{m.name}.pid")
    log_file = os.path.join(state_dir, f"{m.name}.log")

    # Check for existing pid file
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            try:
                pid = int(f.read().strip())
            except ValueError:
                pid = None

        if pid is not None and alive(pid):
            raise ServerError(f"{m.name} already running, pid {pid}")
        else:
            # Stale pid file, remove it
            if os.path.exists(pid_file):
                os.remove(pid_file)

    # Create state directory if needed
    os.makedirs(state_dir, exist_ok=True)

    # Build command
    cmd, env = build_command(m)

    # Merge environment
    full_env = os.environ.copy()
    full_env.update(env)

    # Open log file for appending
    with open(log_file, "ab") as log_f:
        # Spawn process
        proc = spawn(
            cmd,
            stdout=log_f,
            stderr=log_f,
            start_new_session=True,
            env=full_env,
        )

    # Write pid
    with open(pid_file, "w") as f:
        f.write(str(proc.pid))

    return proc.pid


def stop(m: Model, state_dir: str, kill: Callable = os.kill) -> bool:
    """Stop model server."""
    pid_file = os.path.join(state_dir, f"{m.name}.pid")

    if not os.path.exists(pid_file):
        return False

    with open(pid_file, "r") as f:
        try:
            pid = int(f.read().strip())
        except ValueError:
            os.remove(pid_file)
            return False

    try:
        kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass

    if os.path.exists(pid_file):
        os.remove(pid_file)

    return True


def status(
    m: Model,
    state_dir: str,
    fetch: Callable = _fetch,
    alive: Callable = _alive,
) -> dict:
    """Get server status."""
    pid_file = os.path.join(state_dir, f"{m.name}.pid")

    pid = None
    if os.path.exists(pid_file):
        with open(pid_file, "r") as f:
            try:
                pid = int(f.read().strip())
            except ValueError:
                pass

        if pid is not None and not alive(pid):
            pid = None

    return {
        "name": m.name,
        "backend": m.backend,
        "url": base_url(m),
        "healthy": health(m, fetch),
        "pid": pid,
    }
