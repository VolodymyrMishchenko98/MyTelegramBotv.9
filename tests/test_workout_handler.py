import asyncio
import unittest

from handlers import workouts


class _User:
    id = 123


class _Message:
    from_user = _User()

    def __init__(self):
        self.answers = []

    async def answer(self, text, **kwargs):
        self.answers.append((text, kwargs))


class WorkoutHandlerTests(unittest.TestCase):
    def setUp(self):
        self.states = []
        workouts.configure(
            lambda user_id: "en",
            lambda user_id, state: self.states.append((user_id, state)),
            lambda lang, uk, en: uk if lang == "uk" else en,
        )

    def test_workout_command_sets_manual_state_and_preserves_prompt(self):
        message = _Message()

        asyncio.run(workouts.workout(message))

        self.assertEqual(self.states, [(123, "workout")])
        self.assertEqual(
            message.answers,
            [("Enter workout.\nYou can separate by commas:\nRunning 30 min, Push ups 4x20", {})],
        )

    def test_note_keyboard_preserves_skip_callback(self):
        keyboard = workouts._workout_note_keyboard("en")

        button = keyboard.inline_keyboard[0][0]
        self.assertEqual(button.text, "Skip")
        self.assertEqual(button.callback_data, "workout_note_skip")

    def test_router_contains_one_workout_command_handler(self):
        handlers = workouts.router.message.handlers

        self.assertEqual(len(handlers), 1)


if __name__ == "__main__":
    unittest.main()
