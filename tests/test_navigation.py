import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bot_legacy
from handlers import stats
from handlers.keyboards import add_home_button


def _callback(user_id=25):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        message=SimpleNamespace(
            answer=AsyncMock(),
            edit_text=AsyncMock(),
        ),
        answer=AsyncMock(),
    )


class NavigationTests(unittest.IsolatedAsyncioTestCase):
    def test_home_button_preserves_existing_actions_and_localizes_label(self):
        original = stats._dashboard_keyboard("uk")
        original_callbacks = [
            button.callback_data
            for row in original.inline_keyboard
            for button in row
        ]

        for lang, label in (("uk", "Головне меню"), ("en", "Main menu")):
            with self.subTest(language=lang):
                result = add_home_button(original, lang)
                callbacks = [
                    button.callback_data
                    for row in result.inline_keyboard
                    for button in row
                ]
                self.assertEqual(callbacks, original_callbacks)
                self.assertIn(label, result.inline_keyboard[-1][0].text)

    async def test_welcome_menu_returns_to_home_and_clears_input_state(self):
        callback = _callback()
        bot_legacy._pending_workouts[25] = {"exercises": ["Run"]}
        bot_legacy._pending_history_edits[25] = {"kind": "note"}
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "clear_user_state") as clear_state:
            await bot_legacy.welcome_menu(callback)

        clear_state.assert_called_once_with(25)
        self.assertNotIn(25, bot_legacy._pending_workouts)
        self.assertNotIn(25, bot_legacy._pending_history_edits)
        callback.answer.assert_awaited_once_with()
        callback.message.answer.assert_not_awaited()
        args, kwargs = callback.message.edit_text.await_args
        self.assertIn("workout journal", args[0])
        self.assertEqual(kwargs["reply_markup"], bot_legacy.welcome_keyboard("en"))

    async def test_help_navigation_edits_current_message(self):
        callback = _callback()
        with patch.object(bot_legacy, "get_user_language", return_value="uk"):
            await bot_legacy.welcome_help(callback)

        callback.answer.assert_awaited_once_with()
        callback.message.answer.assert_not_awaited()
        text, kwargs = callback.message.edit_text.await_args.args[0], callback.message.edit_text.await_args.kwargs
        self.assertIn("Основні команди", text)
        self.assertIn("welcome_menu", {
            button.callback_data
            for row in kwargs["reply_markup"].inline_keyboard
            for button in row
        })

    async def test_stats_menu_entry_edits_message_and_has_home_navigation(self):
        callback = _callback()
        data = {
            "activity": {
                "total_sessions": 1,
                "current_week_sessions": 1,
                "previous_week_sessions": 1,
                "current_streak": 1,
                "best_streak": 1,
                "days_28": 1,
            },
            "level": 1,
            "xp": 0,
            "last_achievement_key": None,
        }
        with patch.object(stats, "_language_for", return_value="en"), \
             patch.object(stats, "load_stats_data", return_value=data):
            await bot_legacy.welcome_stats(callback)

        callback.message.answer.assert_not_awaited()
        text, kwargs = callback.message.edit_text.await_args.args[0], callback.message.edit_text.await_args.kwargs
        self.assertIn("This week so far", text)
        self.assertIn("welcome_menu", {
            button.callback_data
            for row in kwargs["reply_markup"].inline_keyboard
            for button in row
        })

    async def test_welcome_history_edits_current_message(self):
        callback = _callback()
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "_history_list_message", new_callable=AsyncMock) as render:
            await bot_legacy.welcome_history(callback)

        render.assert_awaited_once_with(callback, 0, 25)

    async def test_stats_subscreens_have_logical_back_and_home_actions(self):
        callbacks = _callback()
        with patch.object(stats, "_language_for", return_value="en"), \
             patch.object(
                 stats,
                 "load_stats_data",
                 return_value={"dates": [], "activity": {"days_28": 0}},
             ):
            await stats.stats_activity(callbacks)

        markup = callbacks.message.edit_text.await_args.kwargs["reply_markup"]
        actions = {
            button.callback_data
            for row in markup.inline_keyboard
            for button in row
        }
        self.assertEqual(actions, {"stats_home", "welcome_menu"})
        self.assertIn(stats.stats_home, [handler.callback for handler in stats.router.callback_query.handlers])

    async def test_stats_back_callback_returns_to_dashboard(self):
        callback = _callback()
        data = {
            "activity": {
                "total_sessions": 1,
                "current_week_sessions": 1,
                "previous_week_sessions": 0,
                "current_streak": 1,
                "best_streak": 1,
                "days_28": 1,
            },
            "level": 1,
            "xp": 0,
            "last_achievement_key": None,
        }
        with patch.object(stats, "_language_for", return_value="en"), \
             patch.object(stats, "load_stats_data", return_value=data):
            await stats.stats_home(callback)

        text, kwargs = callback.message.edit_text.await_args.args[0], callback.message.edit_text.await_args.kwargs
        self.assertIn("This week so far", text)
        self.assertIn("stats_activity", {
            button.callback_data
            for row in kwargs["reply_markup"].inline_keyboard
            for button in row
        })

    def test_primary_legacy_screens_have_a_localized_home_route(self):
        task = {"step": 1, "uk_unit": "хв", "en_unit": "min"}
        first_category = next(iter(bot_legacy.SHOP_ITEMS.values()))["category"]
        keyboards = (
            bot_legacy.profile_visibility_keyboard("uk", {}),
            bot_legacy.daily_task_keyboard("uk", task, False, "2026-11-11"),
            bot_legacy.shop_keyboard("uk"),
            bot_legacy.shop_category_keyboard("en", first_category),
            bot_legacy.reminders_on_keyboard("en"),
            bot_legacy.reminders_off_keyboard("uk"),
        )
        for markup in keyboards:
            with self.subTest(markup=markup):
                button = markup.inline_keyboard[-1][-1]
                self.assertEqual(button.callback_data, "welcome_menu")
                self.assertIn("menu" if "Main menu" in button.text else "меню", button.text.lower())
        self.assertIn(
            "shop_back_to_categories",
            {button.callback_data for row in keyboards[3].inline_keyboard for button in row},
        )
        self.assertEqual(keyboards[4].inline_keyboard[0][0].callback_data, "reminders_off")
        self.assertEqual(keyboards[5].inline_keyboard[0][0].callback_data, "reminders_on")


if __name__ == "__main__":
    unittest.main()
