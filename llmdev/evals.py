import os
import re
import shutil
import subprocess
import tempfile
import dataclasses
import json
from datetime import datetime

from llmdev import cards, metrics, runner


def run_eval(name, m, base_url, root, runs_dir, run=subprocess.run, run_card=runner.run_card, timeout_s=1800, harness="aider"):
    """Run an eval and return a row dict."""
    evals_dir = os.path.join(root, "evals", name)
    if not os.path.isdir(evals_dir):
        raise cards.CardError(f"eval not found: {name}")

    with tempfile.TemporaryDirectory() as tmpdir:
        repo = os.path.join(tmpdir, "repo")
        seed_dir = os.path.join(evals_dir, "seed")
        shutil.copytree(seed_dir, repo)

        # Copy .aider.model.settings.yml if exists
        settings_src = os.path.join(root, ".aider.model.settings.yml")
        if os.path.isfile(settings_src):
            shutil.copy(settings_src, repo)

        # Initialize git repo
        run(["git", "init", "-q"], cwd=repo, capture_output=True, text=True)
        run(["git", "add", "-A"], cwd=repo, capture_output=True, text=True)
        run(["git", "-c", "user.name=eval", "-c", "user.email=eval@local", "commit", "-q", "-m", "seed"], cwd=repo, capture_output=True, text=True)

        # Parse card
        card_path = os.path.join(repo, "cards", "task.md")
        card = cards.parse(card_path)
        card = dataclasses.replace(card, path="cards/task.md", id=name)

        # Run card
        meta = run_card(card, m, base_url, repo, runs_dir, run=run, timeout_s=timeout_s, harness=harness)

        # Copy hidden tests
        hidden_src = os.path.join(evals_dir, "hidden")
        hidden_dst = os.path.join(repo, "hidden_tests")
        shutil.copytree(hidden_src, hidden_dst)

        # Run hidden tests
        try:
            result = run(
                ["python3", "-m", "unittest", "discover", "-s", "hidden_tests", "-t", "."],
                cwd=repo,
                capture_output=True,
                text=True,
                timeout=runner.CHECK_TIMEOUT_S,
            )
            hidden_output = result.stdout + result.stderr
        except subprocess.TimeoutExpired:
            hidden_output = ""
        hidden_passed, hidden_total = hidden_score(hidden_output)

        # Get stats from aider.md
        run_dir = meta.get("run_dir", "")
        aider_path = os.path.join(run_dir, "aider.md")
        stats = {"rounds": 0, "sent": 0, "received": 0, "applied": 0}
        if os.path.exists(aider_path):
            with open(aider_path, "r") as f:
                stats = metrics.aider_stats(f.read())

        # Calculate duration
        started_str = meta.get("started")
        ended_str = meta.get("ended")
        duration_s = None
        if started_str and ended_str:
            try:
                started = datetime.fromisoformat(started_str)
                ended = datetime.fromisoformat(ended_str)
                duration_s = int((ended - started).total_seconds())
            except Exception:
                duration_s = None

        # Build row
        row = {
            "eval": name,
            "model": m.name,
            "backend": m.backend,
            "harness": harness,
            "passed": meta.get("passed"),
            "hidden_passed": hidden_passed,
            "hidden_total": hidden_total,
            "duration_s": duration_s,
            "rounds": stats["rounds"],
            "sent": stats["sent"],
            "received": stats["received"],
            "timed_out": meta.get("timed_out"),
            "stray": len(meta.get("stray_files", [])),
            "empty": len(meta.get("empty_files", [])),
            "run": os.path.basename(run_dir) if run_dir else "",
        }

        return row


def read_evals(path):
    """Read eval records from JSONL file."""
    if not os.path.exists(path):
        return []

    records = []
    try:
        with open(path, "r") as f:
            for line in f:
                if line.strip():
                    records.append(json.loads(line))
    except Exception:
        pass

    return records


def format_evals(rows):
    """Format eval records as a table."""
    if not rows:
        return "no evals yet"

    headers = ["eval", "model", "backend", "passed", "hidden", "duration s", "rounds", "sent", "received", "stray", "empty", "timed out", "run"]
    formatted_rows = []

    for row in rows:
        def fmt(val):
            if val is None:
                return "-"
            return str(val)

        hidden_str = f"{row.get('hidden_passed', '-')}/{row.get('hidden_total', '-')}"
        if row.get('hidden_passed') is None or row.get('hidden_total') is None:
            hidden_str = "-"

        model = fmt(row.get("model"))
        if row.get("harness", "aider") != "aider":
            model += "+" + row["harness"]

        formatted_rows.append([
            fmt(row.get("eval")),
            model,
            fmt(row.get("backend")),
            fmt(row.get("passed")),
            hidden_str,
            fmt(row.get("duration_s")),
            fmt(row.get("rounds")),
            fmt(row.get("sent")),
            fmt(row.get("received")),
            fmt(row.get("stray")),
            fmt(row.get("empty")),
            fmt(row.get("timed_out")),
            fmt(row.get("run")),
        ])

    col_widths = [len(h) for h in headers]
    for row in formatted_rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    lines = []
    header_line = " ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    lines.append(header_line.rstrip())

    for row in formatted_rows:
        line = " ".join(val.ljust(col_widths[i]) for i, val in enumerate(row))
        lines.append(line.rstrip())

    return "\n".join(lines)


def hidden_score(output):
    total_match = re.search(r"^Ran (\d+) tests?", output, re.MULTILINE)
    if not total_match:
        return (0, 0)
    total = int(total_match.group(1))
    failed = 0
    failed_match = re.search(r"^FAILED \((.*)\)", output, re.MULTILINE)
    if failed_match:
        failed = sum(int(n) for n in re.findall(r"=(\d+)", failed_match.group(1)))
    return (max(total - failed, 0), total)
