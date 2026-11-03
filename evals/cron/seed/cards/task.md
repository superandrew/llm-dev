+++
id = "task"
title = "Cron"
edit = ["cron.py"]
read = ["tests/test_visible.py"]
checks = ["test -s cron.py", "python3 -m unittest discover -s tests -v", "python3 -m py_compile cron.py", "git add -N -- cron.py && git --no-pager diff --check HEAD"]
commit = "feat: cron"
edit_format = "whole"
+++

# Cron

Write `cron.py`, standard library only, with two functions and one exception.

    class CronError(ValueError): ...

    def matches(expr, when) -> bool
    def next_run(expr, after) -> datetime.datetime

## Expressions

Five fields separated by one or more spaces or tabs, with optional whitespace around the
whole expression: minute, hour, day of month, month, day of week.

| Field | Values | Names |
|---|---|---|
| minute | 0-59 | |
| hour | 0-23 | |
| day of month | 1-31 | |
| month | 1-12 | `jan` ... `dec` |
| day of week | 0-7, both 0 and 7 are Sunday | `sun` ... `sat` |

Names are three letters, case-insensitive, and can be used wherever a number can, also in
ranges (`mon-fri`).

A field is a comma-separated list of items. An item is one of:

- `*`: every value of the field;
- `N`: one value;
- `A-B`: every value from A to B, with A <= B;
- any of the three followed by `/S` with S >= 1: every S-th value of the range, starting from
  its first value. `N/S` means from N to the end of the field: `5/20` in the minute field is
  5, 25, 45. `*/15` is 0, 15, 30, 45.

Instead of five fields the expression may be one of these macros, case-insensitive:
`@yearly` and `@annually` (`0 0 1 1 *`), `@monthly` (`0 0 1 * *`), `@weekly` (`0 0 * * 0`),
`@daily` and `@midnight` (`0 0 * * *`), `@hourly` (`0 * * * *`).

Day rule: when both day of month and day of week are restricted (neither field starts with
`*`), a day matches when either field matches. When one of them starts with `*`, only the
other one counts.

Everything else raises `CronError`: a wrong number of fields, an empty item, a value out of
range, A > B, a step of 0, an unknown name, any other character, and an `expr` that is not a
`str`.

## matches

`matches(expr, when)` is true when the minute, hour, day and month of `when` match.
Seconds and microseconds are ignored.

## next_run

`next_run(expr, after)` returns the first datetime strictly after `after`, with seconds and
microseconds set to 0, that matches `expr`.

- `after` must be a naive `datetime.datetime` (a `datetime.date` or an aware datetime raises
  `CronError`).
- When nothing matches within 8 years after `after` (for example `0 0 31 4 *`, as April has
  30 days), raise `CronError`.
- It must return within one second for any expression, including the ones that never match:
  do not step one minute at a time over years.
