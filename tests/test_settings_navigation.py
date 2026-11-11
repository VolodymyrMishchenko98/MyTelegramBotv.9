import io
import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import bot_legacy
from handlers import keyboards
from locales import TEXTS, t


def _callback(user_id=25, data=None):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        data=data,
        message=SimpleNamespace(
            answer=AsyncMock(),
            answer_document=AsyncMock(),
            edit_text=AsyncMock(),
            edit_reply_markup=AsyncMock(),
        ),
        answer=AsyncMock(),
    )


def _callbacks(markup):
    return {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    }


class SettingsNavigationTests(unittest.IsolatedAsyncioTestCase):
    def test_welcome_menu_and_settings_menu_expose_all_sections(self):
        for lang in ("uk", "en"):
            with self.subTest(language=lang):
                welcome = _callbacks(bot_legacy.welcome_keyboard(lang))
                self.assertIn("settings_home", welcome)
                self.assertEqual(
                    _callbacks(keyboards.settings_keyboard(lang)),
                    {
                        "settings_profile",
                        "settings_language",
                        "settings_reminders",
                        "settings_data",
                        "welcome_menu",
                    },
                )

    async def test_settings_open_callback_renders_settings_screen(self):
        callback = _callback()
        with patch.object(bot_legacy, "clear_user_state"), \
             patch.object(bot_legacy, "get_user_language", return_value="en"):
            await bot_legacy.settings_home(callback)

        self.assertIn("settings", callback.message.edit_text.await_args.args[0].lower())
        self.assertEqual(
            _callbacks(callback.message.edit_text.await_args.kwargs["reply_markup"]),
            _callbacks(keyboards.settings_keyboard("en")),
        )

    async def test_settings_profile_routes_to_shared_profile_renderer(self):
        callback = _callback(user_id=31)
        with patch.object(bot_legacy, "show_profile", new_callable=AsyncMock) as show_profile:
            await bot_legacy.settings_profile(callback)

        callback.answer.assert_awaited_once_with()
        show_profile.assert_awaited_once_with(callback.message, 31, edit=True)

    async def test_profile_screen_offers_edit_and_visibility(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=32),
            message_id=3201,
            answer=AsyncMock(),
        )
        profile_data = {
            "height": 180, "gender": "male", "age": 30, "goal": "strength",
            "current_weight": 80, "show_height": 1, "show_gender": 1,
            "show_age": 1, "show_weight": 1, "show_goal": 1,
        }
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "get_user_data_safe", return_value=profile_data), \
             patch.object(bot_legacy, "profile_is_filled", return_value=True), \
             patch.object(bot_legacy, "clear_user_state"):
            await bot_legacy.profile(message)

        actions = _callbacks(message.answer.await_args.kwargs["reply_markup"])
        self.assertTrue({"profile_edit_open", "profile_visibility_open", "settings_home"}.issubset(actions))

    async def test_profile_edit_callback_starts_existing_profile_state(self):
        callback = _callback(user_id=33)
        with patch.object(bot_legacy, "get_user_language", return_value="uk"), \
             patch.object(bot_legacy, "set_user_state") as set_state:
            await bot_legacy.profile_edit_open(callback)

        set_state.assert_called_once_with(33, "profile")
        self.assertIn("профіль", callback.message.edit_text.await_args.args[0].lower())
        self.assertIn("profile_screen", _callbacks(callback.message.edit_text.await_args.kwargs["reply_markup"]))

    async def test_visibility_screen_has_profile_return_and_existing_toggle_callbacks(self):
        callback = _callback(user_id=34)
        visibility = {"height": True, "gender": True, "age": True, "weight": True, "goal": True}
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "ensure_user_exists"), \
             patch.object(bot_legacy, "get_profile_visibility", return_value=visibility):
            await bot_legacy.profile_visibility_open(callback)

        actions = _callbacks(callback.message.edit_text.await_args.kwargs["reply_markup"])
        self.assertIn("profile_toggle_height", actions)
        self.assertIn("profile_screen", actions)
        self.assertIn("welcome_menu", actions)

    async def test_language_screen_shows_current_language_and_selects_language(self):
        callback = _callback(user_id=35)
        with patch.object(bot_legacy, "set_user_language") as set_language, \
             patch.object(bot_legacy, "get_user_language", return_value="uk"):
            await bot_legacy.settings_language_en(callback)

        set_language.assert_called_once_with(35, "en")
        callback.answer.assert_awaited_once_with(t("settings_language_saved", "en"))
        args = callback.message.edit_text.await_args
        self.assertIn("Українська", args.args[0])
        self.assertEqual(
            _callbacks(args.kwargs["reply_markup"]),
            {"settings_language_uk", "settings_language_en", "settings_home", "welcome_menu"},
        )

    async def test_change_language_command_keeps_its_toggle_behavior(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=350),
            answer=AsyncMock(),
        )
        with patch.object(bot_legacy, "toggle_user_language", return_value="en") as toggle:
            await bot_legacy.change_language_command(message)

        toggle.assert_called_once_with(350)
        self.assertIn("Language changed to English", message.answer.await_args.args[0])
        self.assertIn(
            "settings_home",
            _callbacks(message.answer.await_args.kwargs["reply_markup"]),
        )

    async def test_reminder_screen_and_toggle_use_existing_persistence_helper(self):
        callback = _callback(user_id=36)
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "get_reminders_enabled", return_value=False):
            await bot_legacy.settings_reminders(callback)

        actions = _callbacks(callback.message.edit_text.await_args.kwargs["reply_markup"])
        self.assertIn("settings_reminders_enable", actions)
        self.assertIn("settings_home", actions)

        callback = _callback(user_id=36)
        with patch.object(bot_legacy, "set_reminders_enabled") as save_enabled, \
             patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "get_reminders_enabled", return_value=True):
            await bot_legacy.settings_reminders_enable(callback)

        save_enabled.assert_called_once_with(36, True)
        self.assertIn(
            "settings_reminders_disable",
            _callbacks(callback.message.edit_text.await_args.kwargs["reply_markup"]),
        )

        callback = _callback(user_id=36)
        with patch.object(bot_legacy, "set_reminders_enabled") as save_enabled, \
             patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "get_reminders_enabled", return_value=False):
            await bot_legacy.settings_reminders_disable(callback)

        save_enabled.assert_called_once_with(36, False)
        self.assertIn(
            "settings_reminders_enable",
            _callbacks(callback.message.edit_text.await_args.kwargs["reply_markup"]),
        )

    async def test_legacy_language_and_reminder_callbacks_remain_available(self):
        language_callback = _callback(user_id=360, data="set_lang_en")
        with patch.object(bot_legacy, "set_user_language") as set_language:
            await bot_legacy.set_language(language_callback)

        set_language.assert_called_once_with(360, "en")
        self.assertEqual(
            language_callback.message.edit_text.await_args.kwargs["reply_markup"],
            bot_legacy.welcome_keyboard("en"),
        )

        reminders_callback = _callback(user_id=361)
        with patch.object(bot_legacy, "get_user_language", return_value="uk"), \
             patch.object(bot_legacy, "set_reminders_enabled") as save_status:
            await bot_legacy.reminders_off(reminders_callback)

        save_status.assert_called_once_with(361, False)
        self.assertIn(
            "reminders_on",
            _callbacks(reminders_callback.message.edit_text.await_args.kwargs["reply_markup"]),
        )
    async def test_data_management_routes_to_existing_operations(self):
        callback = _callback(user_id=37)
        with patch.object(bot_legacy, "get_user_language", return_value="uk"):
            await bot_legacy.settings_data(callback)

        actions = _callbacks(callback.message.edit_text.await_args.kwargs["reply_markup"])
        self.assertEqual(
            actions,
            {"settings_data_export", "settings_data_import", "settings_data_reset", "settings_home", "welcome_menu"},
        )
        self.assertIn("не резервна копія", callback.message.edit_text.await_args.args[0])

    async def test_data_buttons_delegate_to_existing_export_import_and_reset_flows(self):
        callback = _callback(user_id=371)
        with patch.object(bot_legacy, "send_user_export", new_callable=AsyncMock) as send_export:
            await bot_legacy.settings_data_export(callback)
        send_export.assert_awaited_once_with(callback.message, 371)

        callback = _callback(user_id=372)
        with patch.object(bot_legacy, "show_import_prompt", new_callable=AsyncMock) as show_import:
            await bot_legacy.settings_data_import(callback)
        show_import.assert_awaited_once_with(callback.message, 372, edit=True)

        callback = _callback(user_id=373)
        with patch.object(bot_legacy, "get_user_language", return_value="uk"), \
             patch.object(bot_legacy, "show_reset_prompt", new_callable=AsyncMock) as show_reset, \
             patch.object(bot_legacy, "clear_user_all_data") as clear_data:
            await bot_legacy.settings_data_reset(callback)
        show_reset.assert_awaited_once_with(callback.message, "uk", edit=True)
        self.assertFalse(clear_data.called)

    async def test_reset_requires_yes_callback_and_cancel_keeps_confirmation_semantics(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=38),
            answer=AsyncMock(),
        )
        with patch.object(bot_legacy, "get_user_language", return_value="uk"), \
             patch.object(bot_legacy, "clear_user_all_data") as clear_data:
            await bot_legacy.reset_profile(message)

        self.assertFalse(clear_data.called)
        actions = _callbacks(message.answer.await_args.kwargs["reply_markup"])
        self.assertTrue({"reset_yes", "reset_no"}.issubset(actions))

        callback = _callback(user_id=38)
        with patch.object(bot_legacy, "get_user_language", return_value="uk"), \
             patch.object(bot_legacy, "clear_user_all_data", return_value=True) as clear_data:
            await bot_legacy.reset_yes(callback)

        clear_data.assert_called_once_with(38)

    async def test_import_requires_confirm_callback(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=39),
            document=SimpleNamespace(file_name="backup.json", file_id="file-id"),
            answer=AsyncMock(),
        )
        callback = _callback(user_id=39)
        with patch.object(bot_legacy.bot, "download", new_callable=AsyncMock, return_value=io.BytesIO(b'{"profile": {}}')), \
             patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "set_user_state") as save_state, \
             patch.object(bot_legacy, "import_user_data") as import_data:
            await bot_legacy.handle_import_file(message)

        self.assertFalse(import_data.called)
        self.assertTrue(save_state.called)
        self.assertEqual(
            _callbacks(message.answer.await_args.kwargs["reply_markup"]),
            {"import_confirm", "import_cancel", "welcome_menu"},
        )

        callback.message.text = "confirmation message"
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "get_user_state", return_value='import_data:{"profile": {}}'), \
             patch.object(bot_legacy, "import_user_data", return_value=(True, "ok")) as import_data, \
             patch.object(bot_legacy, "clear_user_state"):
            await bot_legacy.import_confirm(callback)

        import_data.assert_called_once_with(39, {"profile": {}})

    def test_new_interface_texts_have_ukrainian_and_english_values(self):
        keys = (
            "settings_title",
            "settings_description",
            "settings_language_current",
            "settings_reminders_enabled",
            "settings_reminders_disabled",
            "settings_data_description",
            "settings_import_confirmation",
            "settings_reset_prompt",
        )
        for key in keys:
            with self.subTest(key=key):
                self.assertIn("uk", TEXTS[key])
                self.assertIn("en", TEXTS[key])


if __name__ == "__main__":
    unittest.main()
