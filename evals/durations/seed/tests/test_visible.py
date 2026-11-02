import unittest

from durations import DurationError, format_duration, parse_duration


class TestVisible(unittest.TestCase):
    def test_parse(self):
        self.assertEqual(parse_duration("1h30m"), 5400)

    def test_format(self):
        self.assertEqual(format_duration(3661), "1h1m1s")

    def test_invalid(self):
        with self.assertRaises(DurationError):
            parse_duration("")
