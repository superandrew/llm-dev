import unittest
from datetime import datetime

from cron import CronError, matches, next_run


class TestVisible(unittest.TestCase):
    def test_next_run(self):
        self.assertEqual(next_run("*/15 * * * *", datetime(2026, 1, 1, 10, 7)), datetime(2026, 1, 1, 10, 15))

    def test_matches(self):
        self.assertTrue(matches("0 9 * * mon-fri", datetime(2026, 11, 3, 9, 0, 30)))

    def test_invalid(self):
        with self.assertRaises(CronError):
            next_run("60 * * * *", datetime(2026, 1, 1))
