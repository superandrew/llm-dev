+++
id = "task"
title = "Durations"
edit = ["durations.py"]
read = ["tests/test_visible.py"]
checks = ["test -s durations.py", "python3 -m unittest discover -s tests -v", "python3 -m py_compile durations.py", "git add -N -- durations.py && git --no-pager diff --check HEAD"]
commit = "feat: durations"
edit_format = "whole"
+++

# Durations

Write `durations.py`, standard library only, with two functions and one exception.

    class DurationError(ValueError): ...

    def parse_duration(text) -> int
    def format_duration(seconds) -> str

## parse_duration

Converts text such as `"1h30m"` to whole seconds.

- Units: `w` = 7 days, `d` = 24 hours, `h`, `m`, `s`. Lowercase only.
- A duration is one or more `<integer><unit>` parts, without spaces, with units in strictly
  decreasing order: `"1d2h"` is valid, `"2h1d"` and `"1h2h"` are not.
- Decimal numbers, signs and leading zeros other than the single digit `0` are invalid:
  `"1.5h"`, `"-1h"`, `"+1h"` and `"01h"` are invalid, `"0s"` is valid and gives 0.
- Everything else raises `DurationError`, including the empty string, a unit without a
  number, a number without a unit, and any argument that is not a `str`.

## format_duration

The inverse of `parse_duration`, using the largest units first and leaving out zero parts:
3661 gives `"1h1m1s"`, 90000 gives `"1d1h"`, 604800 gives `"1w"`, 0 gives `"0s"`.

A negative value, or a value that is not an `int`, raises `DurationError`. `bool` is not
accepted as an `int`.

For every valid result, `parse_duration(format_duration(n)) == n`.
