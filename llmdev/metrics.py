import json
import os
import re
from datetime import datetime


def aider_stats(text: str) -> dict:
    """Extract aider stats from text."""
    rounds = 0
    sent = 0
    received = 0
    applied = 0

    if not text:
        return {"rounds": 0, "sent": 0, "received": 0, "applied": 0}

    lines = text.split("\n")
    for line in lines:
        # Match tokens line: "> Tokens: 20k sent, 2.8k received."
        match = re.match(r"> Tokens:\s+(\d+(?:\.\d+)?)([kK]?)\s+sent,\s+(\d+(?:\.\d+)?)([kK]?)\s+received\.", line)
        if match:
            rounds += 1
            s_val = float(match.group(1))
            if match.group(2).upper() == "K":
                s_val *= 1000
            r_val = float(match.group(3))
            if match.group(4).upper() == "K":
                r_val *= 1000
            sent += int(s_val)
            received += int(r_val)

        # Match applied line: "> Applied edit to a.py"
        if line.startswith("> Applied edit to"):
            applied += 1

    return {"rounds": rounds, "sent": sent, "received": received, "applied": applied}


def read_runs(runs_dir: str) -> list[dict]:
    """Read run records from runs directory."""
    if not os.path.exists(runs_dir):
        return []

    records = []
    entries = os.listdir(runs_dir)
    entries = [e for e in entries if os.path.isdir(os.path.join(runs_dir, e))]

    for entry in sorted(entries):
        meta_path = os.path.join(runs_dir, entry, "meta.json")
        if not os.path.exists(meta_path):
            continue

        with open(meta_path, "r") as f:
            meta = json.load(f)

        run_dir = os.path.join(runs_dir, entry)
        aider_path = os.path.join(run_dir, "aider.md")
        stats = {"rounds": 0, "sent": 0, "received": 0, "applied": 0}
        if os.path.exists(aider_path):
            with open(aider_path, "r") as f:
                stats = aider_stats(f.read())

        # Handle missing keys for older records
        timed_out = meta.get("timed_out")
        stray_files = meta.get("stray_files")
        empty_files = meta.get("empty_files")

        record = {
            "run": entry,
            "card": meta.get("card_id"),
            "model": meta.get("model_name"),
            "backend": meta.get("backend"),
            "duration_s": None,
            "passed": meta.get("passed"),
            "timed_out": timed_out,
            "stray": len(stray_files) if stray_files is not None else None,
            "empty": len(empty_files) if empty_files is not None else None,
            "rounds": stats["rounds"],
            "sent": stats["sent"],
            "received": stats["received"],
            "applied": stats["applied"],
        }

        started_str = meta.get("started")
        ended_str = meta.get("ended")
        if started_str and ended_str:
            try:
                started = datetime.fromisoformat(started_str)
                ended = datetime.fromisoformat(ended_str)
                record["duration_s"] = int((ended - started).total_seconds())
            except Exception:
                record["duration_s"] = None

        records.append(record)

    return records


def format_runs(rows: list[dict]) -> str:
    """Format run records as a table."""
    if not rows:
        return "no runs yet"

    headers = ["run", "card", "model", "passed", "duration s", "rounds", "sent", "received", "applied", "stray", "empty", "timed out"]
    formatted_rows = []

    for row in rows:
        def fmt(val):
            if val is None:
                return "-"
            return str(val)

        formatted_rows.append([
            fmt(row.get("run")),
            fmt(row.get("card")),
            fmt(row.get("model")),
            fmt(row.get("passed")),
            fmt(row.get("duration_s")),
            fmt(row.get("rounds")),
            fmt(row.get("sent")),
            fmt(row.get("received")),
            fmt(row.get("applied")),
            fmt(row.get("stray")),
            fmt(row.get("empty")),
            fmt(row.get("timed_out")),
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
