"""One test method per case, so that the score counts cases and not subtests."""
import time
import unittest
from datetime import date, datetime, timedelta, timezone

from cron import CronError, matches, next_run

D = datetime
NEXT = [
    ("*/15 * * * *", D(2026, 1, 1, 10, 7), D(2026, 1, 1, 10, 15)),
    ("*/15 * * * *", D(2026, 1, 1, 10, 15), D(2026, 1, 1, 10, 30)),
    ("*/15 * * * *", D(2026, 1, 1, 10, 14, 59, 999999), D(2026, 1, 1, 10, 15)),
    ("* * * * *", D(2026, 1, 1, 10, 15, 30), D(2026, 1, 1, 10, 16)),
    ("0 * * * *", D(2026, 12, 31, 23, 30), D(2027, 1, 1, 0, 0)),
    ("5/20 * * * *", D(2026, 1, 1, 10, 46), D(2026, 1, 1, 11, 5)),
    ("1-10/3 * * * *", D(2026, 1, 1, 10, 5), D(2026, 1, 1, 10, 7)),
    ("0,30 8-9 * * *", D(2026, 1, 1, 9, 30), D(2026, 1, 2, 8, 0)),
    ("0 9 * * mon-fri", D(2026, 1, 2, 10, 0), D(2026, 1, 5, 9, 0)),
    ("0 9 * * 7", D(2026, 1, 1, 0, 0), D(2026, 1, 4, 9, 0)),
    ("0 9 * * SUN", D(2026, 1, 1, 0, 0), D(2026, 1, 4, 9, 0)),
    ("0 0 1 * *", D(2026, 1, 31, 12, 0), D(2026, 2, 1, 0, 0)),
    ("0 0 31 * *", D(2026, 4, 1, 0, 0), D(2026, 5, 31, 0, 0)),
    ("0 0 29 2 *", D(2026, 3, 1, 0, 0), D(2028, 2, 29, 0, 0)),
    ("0 0 29 2 *", D(2097, 3, 1, 0, 0), D(2104, 2, 29, 0, 0)),
    ("0 0 13 * fri", D(2026, 1, 1, 0, 0), D(2026, 1, 2, 0, 0)),
    ("0 0 13 * fri", D(2026, 1, 10, 0, 0), D(2026, 1, 13, 0, 0)),
    ("0 0 */2 * mon", D(2026, 1, 1, 0, 0), D(2026, 1, 5, 0, 0)),
    ("0 0 1 * */2", D(2026, 1, 1, 0, 0), D(2026, 2, 1, 0, 0)),
    ("0 0 * jan,jul *", D(2026, 2, 1, 0, 0), D(2026, 7, 1, 0, 0)),
    ("0 12 * JAN-mar Sat", D(2026, 3, 29, 0, 0), D(2027, 1, 2, 12, 0)),
    ("59 23 31 12 *", D(2026, 12, 31, 23, 59), D(2027, 12, 31, 23, 59)),
    ("@hourly", D(2026, 1, 1, 10, 0), D(2026, 1, 1, 11, 0)),
    ("@daily", D(2026, 1, 1, 10, 0), D(2026, 1, 2, 0, 0)),
    ("@midnight", D(2026, 1, 1, 10, 0), D(2026, 1, 2, 0, 0)),
    ("@weekly", D(2026, 1, 1, 10, 0), D(2026, 1, 4, 0, 0)),
    ("@monthly", D(2026, 1, 1, 0, 0), D(2026, 2, 1, 0, 0)),
    ("@YEARLY", D(2026, 1, 1, 0, 0), D(2027, 1, 1, 0, 0)),
    ("@annually", D(2026, 6, 1, 0, 0), D(2027, 1, 1, 0, 0)),
    ("  0\t0  * *\t*  ", D(2026, 1, 1, 10, 0), D(2026, 1, 2, 0, 0)),
]
NEVER = ["0 0 31 4 *", "0 0 30 2 *", "0 0 31 2,4,6,9,11 *"]
INVALID = [
    "* * * *", "* * * * * *", "", "   ",
    "60 * * * *", "* 24 * * *", "* * 0 * *", "* * 32 * *", "* * * 13 *", "* * * 0 *",
    "* * * * 8", "5-1 * * * *", "*/0 * * * *", "1,,2 * * * *", ",1 * * * *",
    "* * * foo *", "* * * * mo", "jan * * * *", "1.5 * * * *", "-1 * * * *", "1- * * * *",
    "1-5/ * * * *", "*/x * * * *", "? * * * *", "@reboot", "@every 5m",
    None, 5, b"* * * * *",
]
MATCHES = [
    ("0 9 * * mon-fri", D(2026, 11, 3, 9, 0, 30), True),
    ("0 9 * * mon-fri", D(2026, 11, 7, 9, 0), False),
    ("0 9 * * mon-fri", D(2026, 11, 3, 9, 1), False),
    ("* * * * *", D(2030, 5, 17, 13, 42, 11), True),
    ("0 0 13 * fri", D(2026, 2, 13, 0, 0), True),
    ("0 0 13 * fri", D(2026, 8, 14, 0, 0), True),
    ("0 0 13 * fri", D(2026, 8, 13, 0, 0), True),
    ("0 0 13 * fri", D(2026, 8, 12, 0, 0), False),
    ("0 0 */2 * mon", D(2026, 1, 7, 0, 0), False),
    ("0 0 */2 * mon", D(2026, 1, 12, 0, 0), True),
    ("0 0 * * 0", D(2026, 1, 4, 0, 0), True),
    ("0 0 * * 7", D(2026, 1, 4, 0, 0), True),
    ("0 0 * * 1-5", D(2026, 1, 4, 0, 0), False),
    ("30 */6 * * *", D(2026, 1, 4, 18, 30), True),
    ("30 */6 * * *", D(2026, 1, 4, 19, 30), False),
    ("0 0 * DEC *", D(2026, 12, 25, 0, 0), True),
]


class TestHidden(unittest.TestCase):
    def test_error_is_value_error(self):
        self.assertTrue(issubclass(CronError, ValueError))

    def test_result_has_no_seconds(self):
        t = next_run("* * * * *", D(2026, 1, 1, 10, 0, 45, 123))
        self.assertEqual((t.second, t.microsecond, t.tzinfo), (0, 0, None))

    def test_after_date_raises(self):
        with self.assertRaises(CronError):
            next_run("* * * * *", date(2026, 1, 1))

    def test_after_aware_raises(self):
        with self.assertRaises(CronError):
            next_run("* * * * *", D(2026, 1, 1, tzinfo=timezone.utc))

    def test_after_str_raises(self):
        with self.assertRaises(CronError):
            next_run("* * * * *", "2026-01-01")


def _add(name, test):
    setattr(TestHidden, f"test_{name}", test)


def _next(expr, after, expected):
    return lambda self: self.assertEqual(next_run(expr, after), expected)


def _never(expr):
    def test(self):
        start = time.monotonic()
        with self.assertRaises(CronError):
            next_run(expr, D(2026, 1, 1))
        self.assertLess(time.monotonic() - start, 2.0)
    return test


def _invalid(function, expr):
    def test(self):
        with self.assertRaises(CronError):
            function(expr, D(2026, 1, 1))
    return test


def _matches(expr, when, expected):
    return lambda self: self.assertIs(matches(expr, when), expected)


for i, (expr, after, expected) in enumerate(NEXT):
    _add(f"next_{i}", _next(expr, after, expected))
for i, expr in enumerate(NEVER):
    _add(f"never_{i}", _never(expr))
for i, expr in enumerate(INVALID):
    _add(f"invalid_next_{i}", _invalid(next_run, expr))
for i, expr in enumerate(INVALID[:6]):
    _add(f"invalid_matches_{i}", _invalid(matches, expr))
for i, (expr, when, expected) in enumerate(MATCHES):
    _add(f"matches_{i}", _matches(expr, when, expected))
