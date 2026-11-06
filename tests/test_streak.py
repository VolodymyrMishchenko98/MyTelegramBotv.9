import unittest
from datetime import datetime, timedelta

from utils.streak import calculate_best_streak, calculate_streak


class StreakCalculationTests(unittest.TestCase):
    def setUp(self):
        self.today = datetime.now().date()

    def date(self, offset):
        return (self.today + timedelta(days=offset)).strftime("%Y-%m-%d")

    def test_today_and_yesterday_are_active(self):
        self.assertEqual(calculate_streak(None, [self.date(0)]), 1)
        self.assertEqual(calculate_streak(None, [self.date(-1)]), 1)
        self.assertEqual(calculate_streak(None, [self.date(-1), self.date(0)]), 2)

    def test_duplicate_workouts_same_day_count_once(self):
        dates = [self.date(0), self.date(0), self.date(-1), self.date(-1)]
        self.assertEqual(calculate_streak(None, dates), 2)

    def test_sequence_and_gap(self):
        self.assertEqual(calculate_streak(None, [self.date(-2), self.date(-1), self.date(0)]), 3)
        self.assertEqual(calculate_streak(None, [self.date(-3), self.date(-1), self.date(0)]), 2)

    def test_old_last_workout_has_no_current_streak(self):
        self.assertEqual(calculate_streak(None, [self.date(-2)]), 0)
        self.assertEqual(calculate_streak(None, [self.date(-5), self.date(-4)]), 0)

    def test_empty_history(self):
        self.assertEqual(calculate_streak(None, []), 0)
        self.assertEqual(calculate_best_streak([]), 0)

    def test_best_streak_uses_unique_dates_across_history(self):
        dates = [
            self.date(-10), self.date(-9), self.date(-8),
            self.date(-5), self.date(-4), self.date(-3), self.date(-2), self.date(-2),
        ]
        self.assertEqual(calculate_best_streak(dates), 4)


if __name__ == "__main__":
    unittest.main()
