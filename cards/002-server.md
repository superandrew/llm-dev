+++
id = "002"
title = "Serve, stop, status"
edit = ["llmdev/server.py", "tests/test_server.py"]
read = ["llmdev/registry.py"]
checks = ["python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/server.py", "git diff --check"]
commit = "feat: start, stop and health-check model servers"
+++

# 002 - Serve, stop, status

## llmdev/server.py

    class ServerError(Exception): ...

    def build_command(m) -> tuple[list[str], dict[str, str]]
    def base_url(m) -> str                       # f"http://{m.host}:{m.port}/v1"
    def health(m, fetch=_fetch) -> bool
    def start(m, state_dir, spawn=subprocess.Popen, fetch=_fetch) -> int | None
    def stop(m, state_dir, kill=os.kill) -> bool
    def status(m, state_dir, fetch=_fetch, alive=_alive) -> dict

`build_command` (env always merged with `dict(m.env)`):
- ollama: `["ollama", "serve"]`, env `OLLAMA_HOST=<host>:<port>`,
  `OLLAMA_CONTEXT_LENGTH=<ctx>`.
- llama: `["llama-server", "-m", model, "-c", str(ctx), "--host", host,
  "--port", str(port), "--jinja", *args]`.
- mlx: `["mlx_lm.server", "--model", model, "--host", host, "--port",
  str(port), *args]`.
- ollama ignores `args`.

`_fetch(url, timeout=2)` returns the HTTP status code (urllib). `health` is
True when `fetch(base_url(m) + "/models")` returns 200; any exception -> False.

`_alive(pid)` uses `os.kill(pid, 0)`; ProcessLookupError -> False,
PermissionError -> True.

Files in `state_dir` (create it): `<name>.pid`, `<name>.log`.

`start`:
1. If `health(m)` is already True, return None (served by something else, for
   example the Ollama app). Do not spawn.
2. If the pid file exists and that pid is alive -> ServerError("<name> already
   running, pid N"). A stale pid file is removed.
3. Spawn `build_command` with stdout and stderr appended to the log file,
   `start_new_session=True`, env = `os.environ` updated with the command env.
   Write the pid and return it. Do not wait for readiness.

`stop`: no pid file -> False. Otherwise `kill(pid, signal.SIGTERM)`
(ProcessLookupError ignored), remove the pid file, return True.

`status` returns `{"name", "backend", "url", "healthy", "pid"}`; pid is None
when there is no pid file or the process is not alive.

## tests/test_server.py

Build Models directly from `llmdev.registry.Model`. Cover: each backend's
command; env merge; llama args appended; start when healthy spawns nothing;
start writes the pid file using a fake spawn returning an object with `pid`;
stale pid file replaced; live pid raises ServerError; stop with and without
pid file using a fake kill; status with fakes. No real processes or sockets.
