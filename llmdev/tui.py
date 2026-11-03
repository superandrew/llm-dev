import curses
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path

from llmdev import lab, registry, server, system


@dataclass
class State:
    rows: list
    selected: int = 0
    message: str = ""
    job: object = None
    job_label: str = ""
    job_log: str = ""
    system: str = ""
    system_level: str = "ok"


def system_level(m) -> str:
    """ok, warn or alert from the memory still available."""
    available = m.get("available_bytes")
    if available is None:
        return "ok"
    if available < 8 * system.GB:
        return "alert"
    if available < 16 * system.GB:
        return "warn"
    return "ok"


def build_rows(registry_data, statuses, summaries) -> list:
    """Build rows for TUI from registry, statuses and summaries."""
    rows = []
    summary_map = {s.get("model"): s for s in summaries}

    for name, model in sorted(registry_data.items()):
        status = statuses.get(name, {})
        summary = summary_map.get(name)

        rows.append({
            "name": name,
            "backend": model.backend,
            "healthy": status.get("healthy", False),
            "pid": status.get("pid"),
            "prefill_tps": summary.get("prefill_tps") if summary else None,
            "decode_tps": summary.get("decode_tps") if summary else None,
        })

    return rows


def job_command(action, name, llm_path) -> list:
    """Build command for job."""
    return [sys.executable, llm_path, action, name]


def render_styled(state, width) -> list:
    """Render TUI lines as (text, style) pairs."""
    lines = []

    # Title
    lines.append(("LLM Dev - Lab TUI", "title"))

    # Header
    lines.append(("  name                      backend pid    prefill t/s  decode t/s", "header"))

    # Rows
    for i, row in enumerate(state.rows):
        name = row["name"]
        backend = row["backend"]
        healthy = row["healthy"]
        pid = row["pid"]
        prefill_tps = row["prefill_tps"]
        decode_tps = row["decode_tps"]

        # Format line
        pid_str = str(pid) if pid is not None else "-"
        prefill_str = str(prefill_tps) if prefill_tps is not None else "-"
        decode_str = str(decode_tps) if decode_tps is not None else "-"

        marker = ">" if i == state.selected else " "
        shown = name + "*" if healthy else name
        line = f"{marker} {shown:<25} {backend:<7} {pid_str:<6} {prefill_str:<12} {decode_str}"

        # Cut to width
        line = line[:width].rstrip()

        if i == state.selected:
            style = "selected"
        elif healthy:
            style = "healthy"
        else:
            style = "row"
        lines.append((line, style))

    # Empty line
    lines.append(("", "row"))

    # System line
    if state.system:
        lines.append((state.system, "system_" + state.system_level))

    # Job line or message
    if state.job is not None:
        lines.append((f"running: {state.job_label} - {state.job_log}", "job"))
    else:
        lines.append((state.message, "message"))

    # Footer
    lines.append(("up/down select  s serve/stop  p pull  b sweep  r refresh  q quit", "footer"))

    return [(text[:width].rstrip(), style) for text, style in lines]


def render_lines(state, width) -> list:
    """Render TUI lines."""
    return [text for text, _ in render_styled(state, width)]


def handle_key(state, key, start_job) -> bool:
    """Handle key press. Returns False only for 'q'."""
    if key == "up":
        if state.rows:
            state.selected = max(0, state.selected - 1)
    elif key == "down":
        if state.rows:
            state.selected = min(len(state.rows) - 1, state.selected + 1)
    elif key == "s":
        if state.job is not None:
            state.message = "job running"
            return True
        if not state.rows:
            return True
        row = state.rows[state.selected]
        if row["healthy"]:
            start_job("stop", row["name"])
        else:
            start_job("serve", row["name"])
    elif key == "p":
        if state.job is not None:
            state.message = "job running"
            return True
        if not state.rows:
            return True
        row = state.rows[state.selected]
        start_job("pull", row["name"])
    elif key == "b":
        if state.job is not None:
            state.message = "job running"
            return True
        if not state.rows:
            return True
        row = state.rows[state.selected]
        if row["healthy"]:
            start_job("sweep", row["name"])
        else:
            state.message = f"{row['name']} is not healthy"
    elif key == "r":
        state.message = ""
    elif key == "q":
        return False
    return True


def poll_job(state, read_last_line):
    """Poll running job."""
    if state.job is None:
        return

    state.job_log = read_last_line()

    if state.job.poll() is not None:
        returncode = state.job.returncode
        if returncode == 0:
            state.message = f"{state.job_label} done"
        else:
            state.message = f"{state.job_label} failed ({returncode})"
        state.job = None
        state.job_label = ""


def run_tui(root):
    root_path = Path(root)
    state_dir = root_path / "state"
    log_path = state_dir / "tui-job.log"
    state = State(rows=[])

    def start_job(action, name):
        state_dir.mkdir(parents=True, exist_ok=True)
        cmd = job_command(action, name, str(root_path / "bin" / "llm"))
        with open(log_path, "wb") as log_f:
            state.job = subprocess.Popen(cmd, stdout=log_f, stderr=log_f, start_new_session=True)
        state.job_label = f"{action} {name}"
        state.job_log = ""
        state.message = ""

    def read_last_line():
        try:
            lines = log_path.read_text(errors="replace").replace("\r", "\n").splitlines()
        except OSError:
            return ""
        return lines[-1].strip() if lines else ""

    def refresh():
        try:
            models = registry.load(str(root_path / "models.toml"))
            statuses = {name: server.status(m, str(state_dir)) for name, m in models.items()}
            summaries = lab.latest_sweeps(lab.read_rows(str(root_path / "runs" / "bench.jsonl")))
        except Exception as e:
            state.message = str(e)
            return
        state.rows = build_rows(models, statuses, summaries)
        state.selected = min(state.selected, max(len(state.rows) - 1, 0))

    def refresh_system():
        m = system.sample()
        state.system = system.status_line(m)
        state.system_level = system_level(m)

    def wrapper_refresh():
        refresh()
        refresh_system()

    return curses.wrapper(_loop, state, wrapper_refresh, start_job, read_last_line)


STYLES = {
    "title": (curses.COLOR_CYAN, -1, curses.A_BOLD),
    "header": (curses.COLOR_WHITE, -1, curses.A_BOLD | curses.A_UNDERLINE),
    "selected": (curses.COLOR_BLACK, curses.COLOR_CYAN, curses.A_BOLD),
    "healthy": (curses.COLOR_GREEN, -1, curses.A_BOLD),
    "row": (-1, -1, 0),
    "system_ok": (curses.COLOR_GREEN, -1, 0),
    "system_warn": (curses.COLOR_YELLOW, -1, curses.A_BOLD),
    "system_alert": (curses.COLOR_RED, -1, curses.A_BOLD),
    "job": (curses.COLOR_MAGENTA, -1, curses.A_BOLD),
    "message": (curses.COLOR_RED, -1, 0),
    "footer": (curses.COLOR_BLUE, -1, curses.A_DIM),
}


def init_styles() -> dict:
    """Map style names to curses attributes; plain attributes without colours."""
    colours = curses.has_colors()
    if colours:
        try:
            curses.start_color()
            curses.use_default_colors()
        except curses.error:
            colours = False
    attrs = {}
    for i, (name, (fg, bg, extra)) in enumerate(STYLES.items(), start=1):
        if colours:
            curses.init_pair(i, fg, bg)
            attrs[name] = curses.color_pair(i) | extra
        else:
            attrs[name] = extra
    return attrs


def _loop(stdscr, state, refresh, start_job, read_last_line):
    attrs = init_styles()
    stdscr.timeout(1000)
    last_refresh = 0.0
    while True:
        had_job = state.job is not None
        poll_job(state, read_last_line)
        job_ended = had_job and state.job is None
        if job_ended or time.monotonic() - last_refresh >= 5:
            refresh()
            last_refresh = time.monotonic()

        height, width = stdscr.getmaxyx()
        stdscr.erase()
        for i, (line, style) in enumerate(render_styled(state, width - 1)[:height]):
            if style == "selected":
                line = line.ljust(width - 1)
            stdscr.addstr(i, 0, line, attrs.get(style, 0))
        stdscr.refresh()

        key = stdscr.getch()
        if key == curses.KEY_UP:
            key_name = "up"
        elif key == curses.KEY_DOWN:
            key_name = "down"
        elif 32 <= key <= 126:
            key_name = chr(key)
        else:
            continue
        if not handle_key(state, key_name, start_job):
            return 0
        if key_name == "r":
            last_refresh = 0.0
