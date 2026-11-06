import unittest

from services.workout_input import parse_workout_exercises


class WorkoutInputTests(unittest.TestCase):
    def test_single_exercise(self):
        self.assertEqual(parse_workout_exercises("Running 30 min"), ["Running 30 min"])

    def test_multiple_exercises_are_split_by_commas(self):
        self.assertEqual(
            parse_workout_exercises("Running 30 min, Push ups 4x20"),
            ["Running 30 min", "Push ups 4x20"],
        )

    def test_spaces_around_names_are_removed(self):
        self.assertEqual(
            parse_workout_exercises("  Run  ,  Push ups  "),
            ["Run", "Push ups"],
        )

    def test_empty_input_returns_no_exercises(self):
        self.assertEqual(parse_workout_exercises(""), [])

    def test_extra_commas_are_ignored(self):
        self.assertEqual(
            parse_workout_exercises(",, Run ,, Push ups, ,"),
            ["Run", "Push ups"],
        )

    def test_whitespace_only_input_returns_no_exercises(self):
        self.assertEqual(parse_workout_exercises("   ,  \t,\n"), [])

    def test_boundary_text_is_not_reinterpreted(self):
        self.assertEqual(parse_workout_exercises("Bench,press, 10x3"), ["Bench", "press", "10x3"])


if __name__ == "__main__":
    unittest.main()
