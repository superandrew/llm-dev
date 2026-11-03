+++
id = "017"
title = "Colourful TUI with system line"
edit = ["llmdev/tui.py", "tests/test_tui.py"]
read = ["AGENTS.md", "models.toml", "bin/llm", "llmdev/system.py"]
checks = ["python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/tui.py", "git --no-pager diff --check HEAD"]
commit = "feat: colourful TUI with GPU, memory and swap"
edit_format = "diff"
+++

# 017 - Colourful TUI with system line

The TUI gets colours and, under the model rows, the status line of `llmdev.system`, coloured
by how much memory is left. Every drawn line gets a style name; `_loop` maps names to colours.

## llmdev/tui.py

1. Import: `from llmdev import lab, registry, server, system`.
2. `State` gets two last fields: `system: str = ""` and `system_level: str = "ok"`.
3. Add, above `render_lines`, exactly:

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

4. Rename the body of `render_lines` into a new function `render_styled(state, width) -> list`
   that returns `(text, style)` pairs, built the same way as today's lines, with these styles:
   the title `"title"`; the header `"header"`; a model row `"selected"` when it is the selected
   one, else `"healthy"` when its row is healthy, else `"row"`; the empty line after the rows
   `"row"`; then, only when `state.system` is not empty, the line `state.system` with style
   `"system_" + state.system_level`; the job line `"job"`; the message line `"message"`; the
   footer `"footer"`. Each text is cut to `width` and stripped on the right, as today.
   `render_lines(state, width)` becomes `return [text for text, _ in render_styled(state, width)]`.
5. Add above `_loop`, exactly:

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

6. In `_loop`: at the top `attrs = init_styles()`. Replace the drawing loop with:

        for i, (line, style) in enumerate(render_styled(state, width - 1)[:height]):
            if style == "selected":
                line = line.ljust(width - 1)
            stdscr.addstr(i, 0, line, attrs.get(style, 0))

7. In `run_tui`, inside `refresh`, as the last lines of the function:

        m = system.sample()
        state.system = system.status_line(m)
        state.system_level = system_level(m)

Nothing else changes.

## tests/test_tui.py

Add to the existing class:

- A `State` with rows model1 (healthy), model2 (healthy), model3 (not healthy), `selected=0`,
  `system="GPU 5%"`, `system_level="warn"`, `message="boom"`: the styles of
  `render_styled(state, 80)` equal
  `["title", "header", "selected", "healthy", "row", "row", "system_warn", "message", "footer"]`
  and the text at index 6 is `"GPU 5%"`.
- The same state with `system=""`: the styles have no `system_warn` and the list has 8 items.
- The same state with `job=object()`, `job_label="serve model1"`: the style at the job line is `"job"`.
- `system_level({})` is `"ok"`; `system_level({"available_bytes": 4 * 1024 ** 3})` is `"alert"`;
  `system_level({"available_bytes": 12 * 1024 ** 3})` is `"warn"`;
  `system_level({"available_bytes": 32 * 1024 ** 3})` is `"ok"`.

The existing tests do not change.
