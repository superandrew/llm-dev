import json
import os
import re
import subprocess
from datetime import datetime

from llmdev.cards import Card
from llmdev.registry import Model


BASE_FLAGS = [
    "--no-auto-commits",
    "--no-gitignore",
    "--no-suggest-shell-commands",
    "--no-detect-urls",
    "--no-check-update",
    "--analytics-disable",
    "--no-show-model-warnings",
    "--map-tokens", "0",
    "--no-pretty",
    "--yes-always",
    "--timeout", "900",
]


def strip_trailing_spaces(repo: str, paths) -> list:
    """Remove spaces and tabs at the end of lines; return the paths that changed."""
    changed = []
    for path in paths:
        full = os.path.join(repo, path)
        if not os.path.isfile(full):
            continue
        try:
            with open(full, encoding="utf-8", newline="") as f:
                text = f.read()
        except UnicodeDecodeError:
            continue
        tidy = re.sub(r"[ \t]+(?=\r?\n|\Z)", "", text)
        if tidy != text:
            with open(full, "w", encoding="utf-8", newline="") as f:
                f.write(tidy)
            changed.append(path)
    return sorted(changed)


def aider_model(m: Model, base_url: str) -> tuple[str, dict]:
    """Return aider model string and environment variables."""
    if m.backend == "ollama":
        model_str = f"ollama_chat/{m.model}"
        env = {"OLLAMA_API_BASE": base_url.removesuffix("/v1")}
    elif m.backend in ("llama", "mlx"):
        model_str = f"openai/{m.model}"
        env = {
            "OPENAI_API_BASE": base_url,
            "OPENAI_API_KEY": "local",
        }
    else:
        raise ValueError(f"unknown backend: {m.backend}")

    return model_str, env


def default_message(card: Card) -> str:
    """Build the default message for Aider."""
    if card.edit_format == "whole":
        msg = (f"Implement card {card.id} as written. Follow AGENTS.md. Edit only: "
               + ", ".join(card.edit) + ". Output each changed file once, as its path alone on one line followed by a fenced code block with the complete file, then stop. Write no other fenced code block: any text line before a fence becomes a file name. No line may end with spaces. ")
    else:
        msg = (f"Implement card {card.id} as written. Follow AGENTS.md. Edit only: "
               + ", ".join(card.edit) + ". Output SEARCH/REPLACE blocks now. "
               "No line may end with spaces. ")
    return msg


def aider_command(
    card: Card,
    m: Model,
    base_url: str,
    history_path: str,
    message: str | None = None,
) -> tuple[list[str], dict]:
    """Build the aider command and environment."""
    model_str, env = aider_model(m, base_url)

    cmd = [
        "aider",
        "--model", model_str,
    ]

    if card.edit_format:
        cmd.extend(["--edit-format", card.edit_format])

    cmd.extend(BASE_FLAGS)
    cmd.extend([
        "--chat-history-file", history_path,
        "--read", "AGENTS.md",
        "--read", card.path,
    ])

    for r in card.read:
        cmd.extend(["--read", r])

    cmd.extend(["--test-cmd", " && ".join(card.checks)])
    cmd.extend(["--auto-test"])

    if message is None:
        message = default_message(card)

    cmd.extend(["--message", message])
    cmd.extend(card.edit)

    return cmd, env


def run_checks(checks: tuple, cwd: str, run=subprocess.run) -> list[dict]:
    """Run checks and return results."""
    results = []
    for check in checks:
        result = run(
            check,
            shell=True,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
        output = result.stdout + result.stderr
        if len(output) > 4000:
            output = output[-4000:]
        results.append({
            "cmd": check,
            "returncode": result.returncode,
            "output": output,
        })
    return results


def changed_paths(repo: str, run=subprocess.run) -> set:
    """Return set of changed file paths."""
    result = run(
        ["git", "status", "--porcelain", "-z", "--untracked-files=all"],
        cwd=repo,
        capture_output=True,
        text=True,
    )
    stdout = result.stdout
    items = stdout.split("\0")
    items = [item for item in items if item]
    paths = set()
    for item in items:
        if len(item) > 3 and item[2] == " ":
            paths.add(item[3:])
    return paths


def empty_files(card: Card, repo: str) -> list:
    """Return list of edit files that are missing or empty."""
    empty = []
    for path in card.edit:
        full_path = os.path.join(repo, path)
        if not os.path.exists(full_path) or os.path.getsize(full_path) == 0:
            empty.append(path)
    return empty


def run_card(
    card: Card,
    m: Model,
    base_url: str,
    repo: str,
    runs_dir: str,
    run=subprocess.run,
    now=datetime.now,
    extra: str = "",
    timeout_s: int = 2400,
) -> dict:
    """Run a card and return metadata."""
    started = now()
    timestamp = started.strftime("%Y%m%d-%H%M%S")
    run_dir = os.path.join(runs_dir, f"{timestamp}-{card.id}")
    os.makedirs(run_dir, exist_ok=True)

    history_path = os.path.join(run_dir, "aider.md")

    message = default_message(card)
    if extra:
        message += " " + extra

    cmd, env = aider_command(card, m, base_url, history_path, message)

    full_env = os.environ.copy()
    full_env.update(env)

    before = changed_paths(repo, run)

    timed_out = False
    try:
        result = run(
            cmd,
            cwd=repo,
            env=full_env,
            timeout=timeout_s,
        )
    except subprocess.TimeoutExpired:
        timed_out = True
        result = type('obj', (object,), {
            'returncode': None,
            'stdout': '',
            'stderr': 'Timeout expired',
        })()

    after = changed_paths(repo, run)
    stray = sorted(after - before - set(card.edit))

    stripped = strip_trailing_spaces(repo, card.edit)

    checks_result = run_checks(card.checks, repo, run)
    passed = all(r["returncode"] == 0 for r in checks_result)

    # Get git diff for edit files
    add_result = run(
        ["git", "add", "-N", "--"] + list(card.edit),
        cwd=repo,
        capture_output=True,
        text=True,
    )
    diff_result = run(
        ["git", "diff", "--"] + list(card.edit),
        cwd=repo,
        capture_output=True,
        text=True,
    )
    diff_content = diff_result.stdout

    # Write diff.patch
    diff_path = os.path.join(run_dir, "diff.patch")
    with open(diff_path, "w") as f:
        f.write(diff_content)

    ended = now()

    # Write meta.json
    empty = empty_files(card, repo)
    meta = {
        "card_id": card.id,
        "title": card.title,
        "model_name": m.name,
        "backend": m.backend,
        "started": started.isoformat(),
        "ended": ended.isoformat(),
        "aider_returncode": result.returncode,
        "checks": checks_result,
        "passed": passed and not timed_out and len(empty) == 0 and len(stray) == 0,
        "timed_out": timed_out,
        "empty_files": empty,
        "stray_files": stray,
        "stripped_files": stripped,
        "run_dir": run_dir,
    }

    meta_path = os.path.join(run_dir, "meta.json")
    with open(meta_path, "w") as f:
        json.dump(meta, f, indent=2)

    return meta
