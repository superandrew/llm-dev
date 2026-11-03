+++
id = "012"
title = "Strip trailing spaces"
edit = ["llmdev/runner.py", "tests/test_runner.py"]
read = ["models.toml", "bin/llm", "AGENTS.md", "llmdev/cards.py", "llmdev/registry.py"]
checks = ["python3 -m unittest discover -s tests -v", "python3 -m py_compile llmdev/runner.py", "git --no-pager diff --check HEAD"]
commit = "feat: strip trailing spaces before the checks"
edit_format = "diff"
+++

# 012 - Strip trailing spaces

Models often leave spaces at the end of lines, mostly on blank lines inside functions.
`git diff --check` then fails a card whose code is right. The runner removes them from the
card's `edit` files after Aider and before the checks, and records which files it touched.

## llmdev/runner.py

Add `import re` to the imports if missing, and this function above `run_card`, exactly:

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

In `run_card`, right after the line `stray = sorted(after - before - set(card.edit))`, add:

    stripped = strip_trailing_spaces(repo, card.edit)

and add the key `"stripped_files": stripped` to `meta`. Nothing else changes.

## tests/test_runner.py

Add a class `TestStripTrailingSpaces` with these tests, each in a `tempfile.TemporaryDirectory`:

- A file `a.py` with content `"x = 1   \n\n    \ny = 2\t\n"`: the function returns `["a.py"]`
  and the file now holds `"x = 1\n\n\ny = 2\n"`.
- A file `b.py` with content `"x = 1\n"`: returns `[]` and the content is unchanged.
- A file `c.py` with content `"x = 1  "` (no final newline): returns `["c.py"]`, content `"x = 1"`.
- A file `d.py` written in binary mode with `b"x = 1 \r\ny\r\n"`: returns `["d.py"]`, and read
  in binary mode it holds `b"x = 1\r\ny\r\n"`.
- A path that does not exist: returns `[]`.
- A file `e.bin` written in binary mode with `b"\xff\xfe  \n"`: returns `[]`.
- Two changed files passed as `["z.py", "a.py"]`: returns `["a.py", "z.py"]`.

In the existing `run_card` tests nothing changes, except that the meta they check may now
contain `stripped_files`.
