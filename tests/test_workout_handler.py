import asyncio
import unittest
from unittest.mock import AsyncMock, patch

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

    def test_welcome_callback_delegates_to_active_workout_handler(self):
        from bot_legacy import welcome_workout

        message = _Message()
        callback = type("Callback", (), {
            "message": message,
            "answer": AsyncMock(),
        })()
        with patch("handlers.workouts.workout", new=AsyncMock()) as active_workout:
            asyncio.run(welcome_workout(callback))

        callback.answer.assert_awaited_once_with()
        active_workout.assert_awaited_once_with(message)


if __name__ == "__main__":
    unittest.main()
