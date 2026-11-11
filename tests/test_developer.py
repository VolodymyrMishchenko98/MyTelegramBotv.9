import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bot_legacy
from locales import t


class DeveloperContactTests(unittest.IsolatedAsyncioTestCase):
    async def test_developer_card_and_contact_button_are_localized(self):
        expected = {
            "uk": ("Розробник SportBot", "Маєш пропозиції", "✉️ Написати розробнику"),
            "en": ("SportBot developer", "Have a suggestion", "✉️ Contact the developer"),
        }
        for lang, (title, body, button_label) in expected.items():
            with self.subTest(language=lang), \
                 patch.object(bot_legacy, "DEVELOPER_USERNAME", "sportbot_dev"), \
                 patch.object(bot_legacy, "get_user_language", return_value=lang):
                message = SimpleNamespace(
                    from_user=SimpleNamespace(id=42),
                    answer=AsyncMock(),
                )
                await bot_legacy.developer(message)

            text = message.answer.await_args.args[0]
            markup = message.answer.await_args.kwargs["reply_markup"]
            contact_button = markup.inline_keyboard[0][0]
            self.assertIn(title, text)
            self.assertIn(body, text)
            self.assertEqual(contact_button.text, button_label)
            self.assertEqual(contact_button.url, "https://t.me/sportbot_dev")
            self.assertEqual(markup.inline_keyboard[-1][0].callback_data, "welcome_menu")

    async def test_missing_username_shows_localized_notice_without_contact_url(self):
        for lang in ("uk", "en"):
            with self.subTest(language=lang), \
                 patch.object(bot_legacy, "DEVELOPER_USERNAME", ""), \
                 patch.object(bot_legacy, "get_user_language", return_value=lang):
                message = SimpleNamespace(
                    from_user=SimpleNamespace(id=42),
                    answer=AsyncMock(),
                )
                await bot_legacy.developer(message)

            text = message.answer.await_args.args[0]
            markup = message.answer.await_args.kwargs["reply_markup"]
            buttons = [
                button
                for row in markup.inline_keyboard
                for button in row
            ]
            self.assertIn(t("developer_contact_unavailable", lang), text)
            self.assertFalse(any(button.url for button in buttons))
            self.assertEqual(buttons[-1].callback_data, "welcome_menu")

    def test_welcome_menu_contact_button_is_optional_and_preserves_callbacks(self):
        with patch.object(bot_legacy, "DEVELOPER_USERNAME", "sportbot_dev"):
            markup = bot_legacy.welcome_keyboard("uk")

        buttons = [button for row in markup.inline_keyboard for button in row]
        self.assertIn("https://t.me/sportbot_dev", {button.url for button in buttons})
        self.assertEqual(
            {button.callback_data for button in buttons if button.callback_data},
            {
                "welcome_workout", "welcome_stats", "welcome_history",
                "welcome_help", "welcome_lang_en",
            },
        )

    def test_help_includes_developer_command_in_both_languages(self):
        for lang in ("uk", "en"):
            with self.subTest(language=lang):
                self.assertIn("/developer", t("help", lang))
                self.assertIn(
                    "розробником" if lang == "uk" else "developer",
                    t("help", lang).lower(),
                )


if __name__ == "__main__":
    unittest.main()
