+++
id = "020"
title = "Run a card with a tool-calling agent"
edit = ["llmdev/runner.py", "tests/test_runner.py"]
read = ["AGENTS.md", "llmdev/cards.py", "llmdev/registry.py"]
checks = ["python3 -m unittest tests.test_runner -v", "python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/runner.py", "git --no-pager diff --check HEAD"]
commit = "feat: run a card with Qwen Code or OpenCode instead of Aider"
edit_format = "diff"
+++

# 020 - Run a card with a tool-calling agent

`run_card` always drives Aider. Add two more harnesses: Qwen Code (`qwen`) and OpenCode
(`opencode`). They call tools themselves (read, edit, shell), so they get the checks in the
prompt and run them on their own.

## llmdev/runner.py

1. After `LLM_ERROR_PREFIXES = ...` add:

        HARNESSES = ("aider", "qwen", "opencode")

2. After `default_message` add exactly these two functions:

        def agent_message(card: Card) -> str:
            """Build the prompt for a tool-calling agent."""
            return (f"Implement card {card.id} as written in {card.path}. Follow AGENTS.md. "
                    "Read the files the card lists under read. Edit only: "
                    + ", ".join(card.edit) + ". Create no other file. When you are done, run "
                    "these checks and fix the code until they all pass: "
                    + " && ".join(card.checks) + ". Do not commit. No line may end with spaces.")


        def agent_command(harness: str, m: Model, base_url: str, message: str) -> tuple[list[str], dict]:
            """Build the command and environment of a tool-calling agent."""
            if harness == "qwen":
                cmd = ["qwen", "--auth-type", "openai", "--openai-base-url", base_url,
                       "--openai-api-key", "local", "--model", m.model,
                       "--approval-mode", "yolo", message]
                return cmd, {}
            if harness == "opencode":
                config = {
                    "provider": {
                        "local": {
                            "npm": "@ai-sdk/openai-compatible",
                            "name": "local",
                            "options": {"baseURL": base_url, "apiKey": "local"},
                            "models": {m.model: {"name": m.name}},
                        }
                    },
                    "autoupdate": False,
                    "share": "disabled",
                }
                cmd = ["opencode", "run", "--standalone", "--model", f"local/{m.model}",
                       "--auto", message]
                return cmd, {"OPENCODE_CONFIG_CONTENT": json.dumps(config)}
            raise ValueError(f"unknown harness: {harness}")

3. `run_card` gets a new last parameter `harness: str = "aider"`.
4. In `run_card`, replace everything from the line `history_path = os.path.join(run_dir, "aider.md")`
   down to the end of the `except subprocess.TimeoutExpired:` block (the block that builds the
   fake `result` with `'stderr': 'Timeout expired'`) with exactly:

        timed_out = False
        if harness == "aider":
            history_path = os.path.join(run_dir, "aider.md")
            message = default_message(card)
            if extra:
                message += " " + extra
            cmd, env = aider_command(card, m, base_url, history_path, message)
        else:
            history_path = os.path.join(run_dir, "agent.log")
            message = agent_message(card)
            if extra:
                message += " " + extra
            cmd, env = agent_command(harness, m, base_url, message)

        full_env = os.environ.copy()
        full_env.update(env)

        before = changed_paths(repo, run)

        try:
            if harness == "aider":
                result = run(cmd, cwd=repo, env=full_env, timeout=timeout_s)
            else:
                with open(history_path, "w") as log:
                    result = run(cmd, cwd=repo, env=full_env, timeout=timeout_s,
                                 stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT)
        except subprocess.TimeoutExpired:
            timed_out = True
            result = type('obj', (object,), {
                'returncode': None,
                'stdout': '',
                'stderr': 'Timeout expired',
            })()

5. In the `meta` dict, right after `"backend": m.backend,` add `"harness": harness,`.

Nothing else changes: the Aider path must build exactly the same command as before.

## tests/test_runner.py

Add a class `TestAgentHarness` (same imports and helpers style as the existing tests):

- `agent_message` of the card `Card(path="cards/001.md", id="001", title="Test", edit=("a.py", "b.py"), read=(), checks=("c1", "c2"), commit="feat: test")`
  contains `"cards/001.md"`, `"Edit only: a.py, b.py."` and `"c1 && c2"`.
- `agent_command("qwen", m, "http://127.0.0.1:8081/v1", "hello")` with
  `m = Model(name="test", backend="mlx", model="~/models/mlx/x", ctx=4096, port=8081)`:
  `cmd[0] == "qwen"`, `cmd[-1] == "hello"`, the item after `"--openai-base-url"` is
  `"http://127.0.0.1:8081/v1"`, the item after `"--model"` is `"~/models/mlx/x"`, and env is `{}`.
- `agent_command("opencode", m, "http://127.0.0.1:8081/v1", "hello")`: `cmd[:2] == ["opencode", "run"]`,
  the item after `"--model"` is `"local/~/models/mlx/x"`, `cmd[-1] == "hello"`, and
  `json.loads(env["OPENCODE_CONFIG_CONTENT"])["provider"]["local"]["options"]["baseURL"] == "http://127.0.0.1:8081/v1"`.
- `agent_command("cursor", m, "u", "hello")` raises `ValueError`.
- `run_card(..., harness="qwen")`, built like `test_run_card_success` (same card, same fake `run`
  and `fake_now`, but `m` is the mlx model above and the base URL `"http://127.0.0.1:8081/v1"`):
  `meta["harness"] == "qwen"`, `meta["passed"]` is true, exactly one call has `cmd[0] == "qwen"`,
  that call's kwargs have `stdin` equal to `subprocess.DEVNULL` and `stderr` equal to
  `subprocess.STDOUT`, no call has `cmd[0] == "aider"`, and the file `agent.log` exists in
  `os.path.join(runs_dir, "20240101-120000-001")`.
- In `test_run_card_success` add one line: `self.assertEqual(meta["harness"], "aider")`.
