"""One test method per case, so that the score counts cases and not subtests."""
import unittest

from durations import DurationError, format_duration, parse_duration

PARSE_VALID = [
    ("0s", 0), ("45s", 45), ("2m", 120), ("1h", 3600), ("1d", 86400), ("1w", 604800),
    ("1w2d3h4m5s", 788645), ("1d2h", 93600), ("10m", 600), ("100s", 100), ("0h1m", 60),
]
PARSE_INVALID = [
    "2h1d", "1m1h", "1s1w",                      # order
    "1h2h", "1s1s",                              # repeated unit
    "1.5h", "-1h", "+1h", "01h", "00s", "1h05m",  # numbers
    "", "h", "1", "1h30", "1 h", "1h 30m", " 1h", "1h\n", "1x", "1H", "٣s",  # shape
    None, 5, 1.5, b"1h", ["1h"],                 # type
]
FORMAT_VALID = [
    (0, "0s"), (1, "1s"), (60, "1m"), (3600, "1h"), (3661, "1h1m1s"), (86400, "1d"),
    (90000, "1d1h"), (604800, "1w"), (788645, "1w2d3h4m5s"), (1209601, "2w1s"),
]
FORMAT_INVALID = [-1, 1.0, "1", None, True, False]
ROUND_TRIP = [0, 59, 61, 3599, 3661, 86399, 86400, 604799, 604800, 10**9]


class TestHidden(unittest.TestCase):
    def test_result_is_int(self):
        self.assertIs(type(parse_duration("1m")), int)

    def test_error_is_value_error(self):
        self.assertTrue(issubclass(DurationError, ValueError))


def _add(name, test):
    setattr(TestHidden, f"test_{name}", test)


def _parse_valid(text, expected):
    return lambda self: self.assertEqual(parse_duration(text), expected)


def _format_valid(seconds, expected):
    return lambda self: self.assertEqual(format_duration(seconds), expected)


def _raises(function, value):
    def test(self):
        with self.assertRaises(DurationError):
            function(value)
    return test


def _round_trip(n):
    return lambda self: self.assertEqual(parse_duration(format_duration(n)), n)


for i, (text, expected) in enumerate(PARSE_VALID):
    _add(f"parse_valid_{i}", _parse_valid(text, expected))
for i, value in enumerate(PARSE_INVALID):
    _add(f"parse_invalid_{i}", _raises(parse_duration, value))
for i, (seconds, expected) in enumerate(FORMAT_VALID):
    _add(f"format_valid_{i}", _format_valid(seconds, expected))
for i, value in enumerate(FORMAT_INVALID):
    _add(f"format_invalid_{i}", _raises(format_duration, value))
for i, n in enumerate(ROUND_TRIP):
    _add(f"round_trip_{i}", _round_trip(n))
