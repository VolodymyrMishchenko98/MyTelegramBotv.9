import unittest
from datetime import date
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from handlers import stats


def _callback(user_id=7):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(edit_text=AsyncMock()),
        answer=AsyncMock(),
    )


class StatsHandlerTests(unittest.IsolatedAsyncioTestCase):
    def test_dashboard_keyboard_has_all_existing_sections(self):
        markup = stats._dashboard_keyboard("uk")
        callback_data = {
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
        }
        self.assertEqual(
            callback_data,
            {"stats_activity", "stats_charts", "stats_records", "stats_history"},
        )
        self.assertIn("Активність", markup.inline_keyboard[0][0].text)
        self.assertIn("🏅 Досягнення", markup.inline_keyboard[1][0].text)
        english = stats._dashboard_keyboard("en")
        self.assertIn("Activity", english.inline_keyboard[0][0].text)
        self.assertIn("🏅 Achievements", english.inline_keyboard[1][0].text)

    def test_empty_dashboard_displays_zeroes_and_level_progress(self):
        text = stats._dashboard_text({
            "activity": {
                "current_week_sessions": 0,
                "previous_week_sessions": 0,
                "current_streak": 0,
                "best_streak": 0,
                "days_28": 0,
            },
            "level": 1,
            "xp": 0,
            "last_achievement_key": None,
        }, "en")
        self.assertIn("This week so far: 0 workouts", text)
        self.assertIn("no change", text)
        self.assertIn("0/100 XP", text)

    def test_week_comparison_handles_increase_and_decrease(self):
        data = {
            "activity": {
                "current_week_sessions": 4,
                "previous_week_sessions": 2,
                "current_streak": 0,
                "best_streak": 0,
                "days_28": 0,
            },
            "level": 1,
            "xp": 0,
            "last_achievement_key": None,
        }
        self.assertIn("↑ +2", stats._dashboard_text(data, "en"))
        data["activity"]["current_week_sessions"] = 1
        self.assertIn("↓ by 1", stats._dashboard_text(data, "en"))

    async def test_empty_profile_gets_friendly_call_to_action(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=7),
            answer=AsyncMock(),
        )
        empty_data = {
            "activity": {
                "total_sessions": 0,
                "current_week_sessions": 0,
                "previous_week_sessions": 0,
                "current_streak": 0,
                "best_streak": 0,
                "days_28": 0,
            },
            "level": 1,
            "xp": 0,
            "last_achievement_key": None,
        }
        with patch.object(stats, "_language_for", return_value="uk"), patch.object(
            stats, "load_stats_data", return_value=empty_data
        ):
            await stats.send_stats(message)

        text = message.answer.await_args.args[0]
        self.assertIn("першого тренування", text)
        self.assertNotIn("Цього тижня: 0", text)
        markup = message.answer.await_args.kwargs["reply_markup"]
        self.assertEqual(markup.inline_keyboard[0][0].callback_data, "welcome_workout")
        self.assertIn("Записати тренування", markup.inline_keyboard[0][0].text)

    async def test_profile_with_workouts_keeps_dashboard_and_navigation(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=7),
            answer=AsyncMock(),
        )
        data = {
            "activity": {
                "total_sessions": 1,
                "current_week_sessions": 1,
                "previous_week_sessions": 0,
                "current_streak": 1,
                "best_streak": 1,
                "days_28": 1,
            },
            "level": 2,
            "xp": 100,
            "last_achievement_key": None,
        }
        with patch.object(stats, "_language_for", return_value="en"), patch.object(
            stats, "load_stats_data", return_value=data
        ):
            await stats.send_stats(message)

        text = message.answer.await_args.args[0]
        self.assertIn("This week so far: 1 workout", text)
        self.assertIn("Active days in 28 days: 1", text)
        self.assertIn("Streak: 1 day", text)
        markup = message.answer.await_args.kwargs["reply_markup"]
        self.assertEqual(
            {button.callback_data for row in markup.inline_keyboard for button in row},
            {"stats_activity", "stats_charts", "stats_records", "stats_history"},
        )

    async def test_activity_callback_renders_28_day_calendar(self):
        today = date.today()
        data = {
            "dates": [today.isoformat()],
            "activity": {"days_28": 1},
        }
        callback = _callback()
        with patch.object(stats, "_language_for", return_value="uk"), patch.object(
            stats, "load_stats_data", return_value=data
        ):
            await stats.stats_activity(callback)

        callback.answer.assert_awaited_once()
        text = callback.message.edit_text.await_args.args[0]
        self.assertIn("28 днів", text)
        self.assertIn("1/28", text)
        self.assertIn("Тиждень 4", text)
        week_rows = [line for line in text.splitlines() if line.startswith("Тиждень ")]
        self.assertEqual(sum(line.count("●") for line in week_rows), 1)

    async def test_charts_callback_reuses_existing_chart_callbacks(self):
        callback = _callback()
        with patch.object(stats, "_language_for", return_value="en"):
            await stats.stats_charts(callback)

        markup = callback.message.edit_text.await_args.kwargs["reply_markup"]
        callback_data = {
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
        }
        self.assertTrue({
            "chart_weight", "chart_workouts", "chart_streak", "chart_volume", "stats_home"
        }.issubset(callback_data))
        self.assertIn("Weight", markup.inline_keyboard[0][0].text)

    async def test_records_callback_uses_only_persisted_records(self):
        callback = _callback()
        with patch.object(stats, "_language_for", return_value="en"), patch.object(
            stats,
            "load_personal_records",
            return_value={"last_achievement_key": "first_workout", "max_weight": 82.5},
        ):
            await stats.stats_records(callback)

        text = callback.message.edit_text.await_args.args[0]
        self.assertIn("First Step", text)
        self.assertIn("82.5 kg", text)
        self.assertIn("Achievements", text)
        self.assertNotIn("Records", text)

    async def test_history_callback_delegates_to_existing_history_renderer(self):
        import bot_legacy

        callback = _callback(user_id=19)
        with patch.object(bot_legacy, "_history_list_message", new_callable=AsyncMock) as history:
            await stats.stats_history(callback)

        history.assert_awaited_once_with(callback, 0, 19)
        callback.answer.assert_awaited_once()


if __name__ == "__main__":
    unittest.main()
