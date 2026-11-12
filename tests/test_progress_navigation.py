import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import bot_legacy
from handlers import stats


def _callback(user_id=25):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(
            answer=AsyncMock(),
            edit_text=AsyncMock(),
        ),
        answer=AsyncMock(),
    )


def _callback_data(markup):
    return {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    }


class ProgressNavigationTests(unittest.IsolatedAsyncioTestCase):
    def test_stats_dashboard_exposes_all_progress_sections(self):
        for lang in ("uk", "en"):
            with self.subTest(language=lang):
                actions = _callback_data(stats._dashboard_keyboard(lang))
                self.assertTrue({
                    "stats_charts",
                    "stats_level",
                    "stats_records",
                    "stats_history",
                    "stats_weight",
                    "stats_weekly_goal",
                    "welcome_menu",
                }.issubset(actions))

    def test_empty_stats_screen_keeps_progress_navigation(self):
        actions = _callback_data(stats._empty_stats_keyboard("en"))
        self.assertTrue({
            "welcome_workout",
            "stats_charts",
            "stats_level",
            "stats_records",
            "stats_history",
            "stats_weight",
            "stats_weekly_goal",
            "welcome_menu",
        }.issubset(actions))

    async def test_stats_level_callback_uses_existing_level_renderer(self):
        callback = _callback(user_id=41)
        with patch.object(bot_legacy, "send_level", new_callable=AsyncMock) as send_level:
            await stats.stats_level(callback)

        callback.answer.assert_awaited_once_with()
        send_level.assert_awaited_once_with(callback.message, 41, edit=True)

    def test_weight_menu_exposes_add_recent_and_chart_actions(self):
        expected = {"weight_add", "weight_recent", "chart_weight", "stats_home", "welcome_menu"}
        for lang in ("uk", "en"):
            with self.subTest(language=lang):
                self.assertTrue(expected.issubset(_callback_data(bot_legacy.weight_keyboard(lang))))

    async def test_weight_command_opens_action_menu_without_skipping_input_choice(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=47),
            answer=AsyncMock(),
        )
        with patch.object(bot_legacy, "get_user_language", return_value="uk"), \
             patch.object(bot_legacy, "set_user_state") as set_state:
            await bot_legacy.weight(message)

        self.assertEqual(
            _callback_data(message.answer.await_args.kwargs["reply_markup"]),
            {"weight_add", "weight_recent", "chart_weight", "stats_home", "welcome_menu"},
        )
        set_state.assert_not_called()

    async def test_weight_add_callback_preserves_existing_input_state(self):
        callback = _callback(user_id=42)
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "set_user_state") as set_state:
            await bot_legacy.weight_add(callback)

        callback.answer.assert_awaited_once_with()
        set_state.assert_called_once_with(42, "weight")
        self.assertIn("Enter weight", callback.message.edit_text.await_args.args[0])

    async def test_weight_recent_callback_uses_existing_recent_entries_handler(self):
        callback = _callback(user_id=43)
        with patch.object(bot_legacy, "send_weight_stats", new_callable=AsyncMock) as send_recent:
            await bot_legacy.weight_recent(callback)

        callback.answer.assert_awaited_once_with()
        send_recent.assert_awaited_once_with(callback.message, 43, edit=True)

    def test_weekly_goal_menu_offers_edit_without_profile_goal_alias(self):
        for lang in ("uk", "en"):
            with self.subTest(language=lang):
                actions = _callback_data(bot_legacy.weekly_goal_keyboard(lang))
                self.assertEqual(actions, {"weekly_goal_set", "stats_home", "welcome_menu"})
                self.assertNotIn("suggest", actions)

    async def test_weekly_goal_callback_uses_existing_goal_input_state(self):
        callback = _callback(user_id=44)
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "set_user_state") as set_state:
            await bot_legacy.weekly_goal_set(callback)

        callback.answer.assert_awaited_once_with()
        set_state.assert_called_once_with(44, "weekly_goal")
        self.assertIn("weekly goal", callback.message.edit_text.await_args.args[0])

    async def test_set_goal_command_uses_the_same_existing_input_flow(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=45),
            answer=AsyncMock(),
        )
        with patch.object(bot_legacy, "get_user_language", return_value="uk"), \
             patch.object(bot_legacy, "set_user_state") as set_state:
            await bot_legacy.set_goal(message)

        set_state.assert_called_once_with(45, "weekly_goal")
        self.assertIn("мету на тиждень", message.answer.await_args.args[0])

    async def test_goal_progress_screen_offers_change_goal_action(self):
        cursor = Mock()
        cursor.fetchone.side_effect = [(3,), (2,)]
        database = Mock()
        database.cursor.return_value = cursor
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=46),
            answer=AsyncMock(),
        )
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "get_db", return_value=database):
            await bot_legacy.goal(message)

        self.assertIn("Goal: 3", message.answer.await_args.args[0])
        self.assertIn("Progress: 66%", message.answer.await_args.args[0])
        self.assertEqual(
            _callback_data(message.answer.await_args.kwargs["reply_markup"]),
            {"weekly_goal_set", "stats_home", "welcome_menu"},
        )
        self.assertIn("SELECT weekly_goal", cursor.execute.call_args_list[0].args[0])

    async def test_unset_weekly_goal_screen_offers_setup_button(self):
        cursor = Mock()
        cursor.fetchone.return_value = None
        database = Mock()
        database.cursor.return_value = cursor
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=48),
            answer=AsyncMock(),
        )
        with patch.object(bot_legacy, "get_user_language", return_value="uk"), \
             patch.object(bot_legacy, "get_db", return_value=database):
            await bot_legacy.goal(message)

        self.assertEqual(
            _callback_data(message.answer.await_args.kwargs["reply_markup"]),
            {"weekly_goal_set", "stats_home", "welcome_menu"},
        )


if __name__ == "__main__":
    unittest.main()
