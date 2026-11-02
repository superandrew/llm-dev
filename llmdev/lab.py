from typing import Optional
import json


SWEEP_WORDS = (3000, 6000, 12000, 24000)


def slope_tps(points) -> Optional[float]:
    """Calculate prefill speed as slope of ttft over tokens."""
    if len(points) < 2:
        return None

    n = len(points)
    sum_x = sum(p[0] for p in points)
    sum_y = sum(p[1] for p in points)
    sum_xy = sum(x * y for x, y in points)
    sum_x2 = sum(x * x for x, y in points)

    denom = n * sum_x2 - sum_x * sum_x
    if denom == 0:
        return None

    b = (n * sum_xy - sum_x * sum_y) / denom
    if b <= 0:
        return None

    return round(1 / b, 1)


def sweep(m, seed, words=SWEEP_WORDS, max_tokens=128, run=None) -> list:
    """Run sweep benchmark on model m."""
    if run is None:
        from llmdev import bench
        run = bench.run

    # First run to load the model
    load_result = run(m, n_words=200, max_tokens=16, seed=seed)
    load_s = load_result.get("ttft_s")

    rows = []
    for n_words in words:
        result = run(m, n_words=n_words, max_tokens=max_tokens, seed=seed)
        result["seed"] = seed
        result["load_s"] = load_s
        rows.append(result)

    return rows


def summarize(rows) -> dict:
    """Summarize sweep results."""
    if not rows:
        return {}

    model = rows[0].get("model")
    backend = rows[0].get("backend")

    # Calculate prefill_tps from all rows
    points = [(r.get("prompt_tokens", 0), r.get("ttft_s", 0)) for r in rows]
    prefill_tps = slope_tps(points)

    # Calculate decode_tps from all rows
    decode_values = [r.get("decode_tps") for r in rows if r.get("decode_tps") is not None]
    if decode_values:
        n = len(decode_values)
        if n % 2 == 1:
            decode_tps = round(sorted(decode_values)[n // 2], 1)
        else:
            mid = n // 2
            decode_tps = round((sorted(decode_values)[mid - 1] + sorted(decode_values)[mid]) / 2, 1)
    else:
        decode_tps = None

    # Find load_s
    load_s = rows[0].get("load_s")

    # Find ttft_max_s (ttft_s of row with most prompt tokens)
    max_prompt_tokens = 0
    ttft_max_s = None
    for r in rows:
        prompt_tokens = r.get("prompt_tokens", 0)
        if prompt_tokens is not None and prompt_tokens > max_prompt_tokens:
            max_prompt_tokens = prompt_tokens
            ttft_max_s = r.get("ttft_s")

    return {
        "model": model,
        "backend": backend,
        "prefill_tps": prefill_tps,
        "decode_tps": decode_tps,
        "load_s": load_s,
        "ttft_max_s": ttft_max_s,
    }


def read_rows(path) -> list:
    """Read rows from JSONL file."""
    try:
        with open(path, "r") as f:
            return [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        return []


def latest_sweeps(rows) -> list:
    """Get latest sweep summary for each model."""
    # Filter rows with sweep key
    sweep_rows = [r for r in rows if "sweep" in r]

    # Group by model
    model_rows = {}
    for row in sweep_rows:
        model = row.get("model")
        if model not in model_rows:
            model_rows[model] = []
        model_rows[model].append(row)

    summaries = []
    for model, model_row_list in model_rows.items():
        # Find max sweep value
        max_sweep = max(r.get("sweep", 0) for r in model_row_list)
        # Get rows with max sweep
        latest_rows = [r for r in model_row_list if r.get("sweep") == max_sweep]
        # Summarize
        summary = summarize(latest_rows)
        summary["sweep"] = max_sweep
        summaries.append(summary)

    return sorted(summaries, key=lambda x: x.get("model", ""))


def format_table(summaries) -> str:
    """Format summaries as a table."""
    if not summaries:
        return "no sweeps yet"

    headers = ["model", "backend", "prefill t/s", "decode t/s", "load s", "ttft max s", "sweep"]
    rows = []

    for s in summaries:
        row = [
            s.get("model", ""),
            s.get("backend", ""),
            str(s.get("prefill_tps")) if s.get("prefill_tps") is not None else "-",
            str(s.get("decode_tps")) if s.get("decode_tps") is not None else "-",
            str(s.get("load_s")) if s.get("load_s") is not None else "-",
            str(s.get("ttft_max_s")) if s.get("ttft_max_s") is not None else "-",
            str(s.get("sweep", "")),
        ]
        rows.append(row)

    # Calculate column widths
    col_widths = [len(h) for h in headers]
    for row in rows:
        for i, val in enumerate(row):
            col_widths[i] = max(col_widths[i], len(val))

    # Format table
    lines = []
    header_line = " ".join(h.ljust(col_widths[i]) for i, h in enumerate(headers))
    lines.append(header_line.rstrip())

    for row in rows:
        line = " ".join(val.ljust(col_widths[i]) for i, val in enumerate(row))
        lines.append(line.rstrip())

    return "\n".join(lines)
