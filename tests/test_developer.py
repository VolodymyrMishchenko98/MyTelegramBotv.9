import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from aiogram.exceptions import TelegramAPIError
from aiogram.methods import SendMessage

import bot_legacy
from handlers import developer
from locales import TEXTS, t
from services import developer_feedback as feedback_db


class _Message:
    def __init__(
        self,
        user_id,
        text=None,
        *,
        first_name="Alex",
        username="alex_user",
        chat_id=None,
        bot=None,
    ):
        self.text = text
        self.from_user = SimpleNamespace(
            id=user_id,
            first_name=first_name,
            full_name=first_name,
            username=username,
        )
        self.chat = SimpleNamespace(id=chat_id if chat_id is not None else user_id)
        self.bot = bot or SimpleNamespace(send_message=AsyncMock())
        self.answer = AsyncMock()
        self.edit_text = AsyncMock()
        self.edit_reply_markup = AsyncMock()


def _callback(data, user_id, message):
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=message,
        answer=AsyncMock(),
    )


class DeveloperFeedbackTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = Path(self.tmp.name) / "feedback.sqlite3"
        self.states = {}
        self.languages = {}

        @contextmanager
        def db_context():
            connection = sqlite3.connect(self.db_path)
            connection.execute("PRAGMA foreign_keys=ON")
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        self.db_context_patcher = patch.object(feedback_db, "get_db_context", db_context)
        self.db_context_patcher.start()
        connection = sqlite3.connect(self.db_path)
        try:
            feedback_db.ensure_feedback_tables(connection.cursor())
            connection.commit()
        finally:
            connection.close()
        developer.configure(
            lambda uid: self.languages.get(uid, "uk"),
            lambda uid: self.states.get(uid),
            lambda uid, state: self.states.__setitem__(uid, state),
            lambda uid: self.states.pop(uid, None),
            bot_legacy.welcome_keyboard,
            9001,
        )
        self.languages.update({1001: "uk", 2002: "en", 9001: "uk"})

    def tearDown(self):
        developer._pending.clear()
        self.db_context_patcher.stop()
        self.tmp.cleanup()

    def _feedback_count(self):
        connection = sqlite3.connect(self.db_path)
        try:
            return connection.execute(
                "SELECT COUNT(*) FROM developer_feedback"
            ).fetchone()[0]
        finally:
            connection.close()

    def test_all_developer_feedback_strings_are_localized_in_uk_and_en(self):
        for key, translations in TEXTS.items():
            if not key.startswith("developer_"):
                continue
            with self.subTest(key=key):
                self.assertIn("uk", translations)
                self.assertIn("en", translations)
                self.assertNotEqual(t(key, "uk"), f"[{key}]")
                self.assertNotEqual(t(key, "en"), f"[{key}]")

    async def _submit_flow(self, user_id, mode, category, text, *, first_name, username):
        message = _Message(user_id, first_name=first_name, username=username)
        await developer.cmd_developer(message)
        mode_callback = _callback(
            f"devfb:mode:{mode}",
            user_id,
            SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        )
        await developer.handle_feedback_callback(mode_callback)
        category_callback = _callback(
            f"devfb:category:{category}",
            user_id,
            SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        )
        await developer.handle_feedback_callback(category_callback)
        message.text = text
        await developer.receive_feedback_message(message)
        return message

    async def test_developer_entry_and_mode_category_flow_are_localized(self):
        expected = {
            1001: ("Зв'язок із розробником", "🕵️ Анонімно", "🐛 Помилка"),
            2002: ("Contact the SportBot developer", "🕵️ Anonymous", "🐛 Bug"),
        }
        for user_id, (title, anonymous, bug) in expected.items():
            with self.subTest(user_id=user_id):
                message = _Message(user_id)
                await developer.cmd_developer(message)
                text = message.answer.await_args.args[0]
                self.assertIn(title, text)
                markup = message.answer.await_args.kwargs["reply_markup"]
                self.assertIn(
                    anonymous,
                    {button.text for row in markup.inline_keyboard for button in row},
                )

                mode = _callback(
                    "devfb:mode:a",
                    user_id,
                    SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
                )
                await developer.handle_feedback_callback(mode)
                category_labels = {
                    button.text
                    for row in mode.message.edit_text.await_args.kwargs["reply_markup"].inline_keyboard
                    for button in row
                }
                self.assertIn(bug, category_labels)
                category = _callback(
                    "devfb:category:bug",
                    user_id,
                    SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
                )
                await developer.handle_feedback_callback(category)
                self.assertEqual(self.states[user_id], developer.STATE_MESSAGE)
                self.assertIn(
                    t("developer_feedback_write_message", "en" if user_id == 2002 else "uk"),
                    category.message.edit_text.await_args.args[0],
                )

    async def test_anonymous_notification_and_callbacks_do_not_leak_identity(self):
        message = await self._submit_flow(
            1001,
            "a",
            "idea",
            "Please add a new workout view.",
            first_name="Secret Name",
            username="secret_handle",
        )
        notification = message.bot.send_message.await_args.kwargs
        self.assertIn("#1", notification["text"])
        self.assertIn("Please add a new workout view.", notification["text"])
        self.assertNotIn("Secret Name", notification["text"])
        self.assertNotIn("secret_handle", notification["text"])
        self.assertNotIn("1001", notification["text"])
        callbacks = {
            button.callback_data
            for row in notification["reply_markup"].inline_keyboard
            for button in row
        }
        self.assertEqual(callbacks, {"devfb:reply:1", "devfb:close:1"})
        self.assertNotIn("1001", " ".join(callbacks))
        self.assertIn(
            t("developer_feedback_saved", "uk").format(ticket_id=1),
            message.answer.await_args.args[0],
        )
        await developer.receive_feedback_message(message)
        self.assertEqual(self._feedback_count(), 1)

        ticket = feedback_db.get_feedback(1)
        self.assertEqual(ticket["sender_id"], 1001)
        self.assertTrue(ticket["anonymous"])
        self.assertEqual(ticket["notification_status"], "sent")

    async def test_identified_notification_contains_available_name_and_username(self):
        message = await self._submit_flow(
            2002,
            "i",
            "bug",
            "The chart did not load.",
            first_name="Visible Name",
            username="visible_handle",
        )
        text = message.bot.send_message.await_args.kwargs["text"]
        self.assertIn("Visible Name", text)
        self.assertIn("@visible_handle", text)
        self.assertNotIn("2002", text)
        self.assertIn(
            t("developer_feedback_mode_identified", "uk"),
            text,
        )

    async def test_anonymous_followup_keeps_sender_identity_private(self):
        message = await self._submit_flow(
            1001,
            "a",
            "question",
            "First question",
            first_name="Private Name",
            username="private_handle",
        )
        await developer.handle_feedback_callback(_callback(
            "devfb:user_reply:1",
            1001,
            _Message(1001),
        ))
        followup = _Message(
            1001,
            text="More details",
            first_name="Private Name",
            username="private_handle",
            bot=message.bot,
        )
        await developer.receive_feedback_message(followup)
        notification = followup.bot.send_message.await_args.kwargs
        self.assertIn("More details", notification["text"])
        self.assertNotIn("Private Name", notification["text"])
        self.assertNotIn("private_handle", notification["text"])
        self.assertNotIn("1001", notification["text"])

    async def test_cancel_validation_and_unsupported_message(self):
        user_id = 1001
        start = _Message(user_id)
        await developer.cmd_developer(start)
        mode = _callback(
            "devfb:mode:i", user_id,
            SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        )
        await developer.handle_feedback_callback(mode)
        category = _callback(
            "devfb:category:other", user_id,
            SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        )
        await developer.handle_feedback_callback(category)

        unsupported = _Message(user_id, text=None)
        unsupported.photo = [object()]
        await developer.receive_feedback_message(unsupported)
        self.assertIn(
            t("developer_feedback_text_only", "uk"),
            unsupported.answer.await_args.args[0],
        )
        self.assertEqual(self.states[user_id], developer.STATE_MESSAGE)

        empty = _Message(user_id, text="   ")
        await developer.receive_feedback_message(empty)
        self.assertIn(t("developer_feedback_empty", "uk"), empty.answer.await_args.args[0])
        too_long = _Message(user_id, text="x" * (developer.MAX_MESSAGE_LENGTH + 1))
        await developer.receive_feedback_message(too_long)
        self.assertIn(
            t("developer_feedback_too_long", "uk"),
            too_long.answer.await_args.args[0],
        )
        self.assertEqual(self._feedback_count(), 0)

        cancel = _callback(
            "devfb:cancel", user_id,
            SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        )
        await developer.handle_feedback_callback(cancel)
        self.assertNotIn(user_id, self.states)
        self.assertIn(
            t("developer_feedback_cancelled", "uk"),
            cancel.message.edit_text.await_args.args[0],
        )

    async def test_non_text_input_is_routed_to_feedback_not_legacy_import(self):
        user_id = 1001
        bot_legacy.set_user_state(user_id, developer.STATE_MESSAGE)
        photo = _Message(user_id, text=None)
        photo.photo = [object()]
        document = _Message(user_id, text=None)
        document.document = SimpleNamespace(file_name="payload.json")
        self.assertFalse(bot_legacy._is_non_command_message(photo))
        self.assertTrue(bot_legacy._is_developer_feedback_state(document))
        await developer.receive_feedback_message(document)
        self.assertIn(
            t("developer_feedback_text_only", "uk"),
            document.answer.await_args.args[0],
        )
        self.assertEqual(bot_legacy.get_user_state(user_id), developer.STATE_MESSAGE)
        bot_legacy.clear_user_state(user_id)

    async def test_rate_limit_allows_three_messages_per_ten_minutes(self):
        now = datetime.now(timezone.utc)
        for index in range(3):
            ticket_id = feedback_db.create_feedback(
                3003,
                False,
                "other",
                f"Request {index}",
                now=now + timedelta(minutes=index),
            )
            self.assertIsNotNone(ticket_id)
        blocked = feedback_db.create_feedback(
            3003,
            False,
            "other",
            "Request four",
            now=now + timedelta(minutes=4),
        )
        self.assertIsNone(blocked)
        reply_limited = feedback_db.add_user_message(1, 3003, "Another message")
        self.assertEqual(reply_limited, "rate_limited")

    async def test_developer_can_reply_and_history_is_saved(self):
        await self._submit_flow(
            1001,
            "a",
            "question",
            "How does the goal work?",
            first_name="Secret Name",
            username="secret_handle",
        )
        dev_notice = _Message(9001, chat_id=9001)
        callback = _callback("devfb:reply:1", 9001, dev_notice)
        await developer.handle_feedback_callback(callback)
        self.assertEqual(self.states[9001], developer.STATE_REPLY)

        reply = _Message(9001, text="Here is the answer.")
        await developer.receive_feedback_message(reply)
        reply_call = reply.bot.send_message.await_args
        self.assertEqual(reply_call.kwargs["chat_id"], 1001)
        self.assertIn("Here is the answer.", reply_call.kwargs["text"])
        self.assertNotIn("developer", reply_call.kwargs["text"].lower())
        reply_callbacks = {
            button.callback_data
            for row in reply_call.kwargs["reply_markup"].inline_keyboard
            for button in row
        }
        self.assertIn("devfb:user_reply:1", reply_callbacks)
        history = feedback_db.get_feedback_messages(1)
        self.assertEqual([entry["sender_type"] for entry in history], ["user", "developer"])
        self.assertEqual(history[1]["delivery_status"], "sent")
        self.assertIsNotNone(feedback_db.get_feedback(1)["replied_at"])

    async def test_user_can_continue_only_their_own_open_conversation(self):
        await self._submit_flow(
            1001,
            "i",
            "question",
            "Question one",
            first_name="A",
            username="a_user",
        )
        user_reply_callback = _callback(
            "devfb:user_reply:1",
            1001,
            _Message(1001),
        )
        await developer.handle_feedback_callback(user_reply_callback)
        followup = _Message(1001, text="Question two")
        await developer.receive_feedback_message(followup)
        self.assertIn(
            t("developer_feedback_followup_sent", "uk").format(ticket_id=1),
            followup.answer.await_args.args[0],
        )
        self.assertEqual(len(feedback_db.get_feedback_messages(1)), 2)

        another_user = _callback(
            "devfb:user_reply:1",
            2002,
            _Message(2002),
        )
        await developer.handle_feedback_callback(another_user)
        self.assertTrue(another_user.answer.await_args.kwargs["show_alert"])
        self.assertEqual(self.states.get(2002), None)

    async def test_admin_callbacks_require_the_configured_developer_chat(self):
        await self._submit_flow(
            1001,
            "a",
            "bug",
            "Broken",
            first_name="Private",
            username="private",
        )
        unauthorized = _callback(
            "devfb:close:1",
            2002,
            _Message(2002, chat_id=2002),
        )
        await developer.handle_feedback_callback(unauthorized)
        self.assertTrue(unauthorized.answer.await_args.kwargs["show_alert"])
        self.assertEqual(feedback_db.get_feedback(1)["status"], "open")

        wrong_user_same_chat = _callback(
            "devfb:close:1",
            2002,
            _Message(2002, chat_id=9001),
        )
        await developer.handle_feedback_callback(wrong_user_same_chat)
        self.assertTrue(wrong_user_same_chat.answer.await_args.kwargs["show_alert"])
        self.assertEqual(feedback_db.get_feedback(1)["status"], "open")

        authorized = _callback(
            "devfb:close:1",
            9001,
            _Message(9001, chat_id=9001),
        )
        await developer.handle_feedback_callback(authorized)
        self.assertEqual(feedback_db.get_feedback(1)["status"], "closed")
        self.assertEqual(
            authorized.message.edit_reply_markup.await_args.kwargs["reply_markup"]
            .inline_keyboard[0][0].callback_data,
            "devfb:reopen:1",
        )

    async def test_missing_chat_configuration_disables_feedback_without_crashing(self):
        developer.configure(
            lambda uid: "en",
            lambda uid: self.states.get(uid),
            lambda uid, state: self.states.__setitem__(uid, state),
            lambda uid: self.states.pop(uid, None),
            bot_legacy.welcome_keyboard,
            None,
        )
        message = _Message(2002)
        await developer.cmd_developer(message)
        self.assertIn(
            t("developer_contact_unavailable", "en"),
            message.answer.await_args.args[0],
        )
        callbacks = {
            button.callback_data
            for row in message.answer.await_args.kwargs["reply_markup"].inline_keyboard
            for button in row
            if button.callback_data
        }
        self.assertEqual(callbacks, {"welcome_menu"})
        self.assertEqual(self._feedback_count(), 0)

    async def test_failed_initial_notification_is_kept_and_logs_no_sender_identity(self):
        user_id = 1001
        message = _Message(
            user_id,
            text="A private anonymous report",
            first_name="Hidden Name",
            username="hidden_handle",
        )
        await developer.cmd_developer(_Message(user_id))
        await developer.handle_feedback_callback(_callback(
            "devfb:mode:a",
            user_id,
            SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        ))
        await developer.handle_feedback_callback(_callback(
            "devfb:category:bug",
            user_id,
            SimpleNamespace(edit_text=AsyncMock(), answer=AsyncMock()),
        ))
        message.bot.send_message.side_effect = TelegramAPIError(
            method=SendMessage(chat_id=9001, text="hidden"),
            message="unavailable",
        )
        with self.assertLogs("handlers.developer", level="WARNING") as captured:
            await developer.receive_feedback_message(message)
        ticket = feedback_db.get_feedback(1)
        self.assertEqual(ticket["notification_status"], "failed")
        self.assertEqual(ticket["message"], "A private anonymous report")
        self.assertIn(
            t("developer_feedback_delivery_failed", "uk").format(ticket_id=1),
            message.answer.await_args.args[0],
        )
        logged = "\n".join(captured.output)
        self.assertNotIn("1001", logged)
        self.assertNotIn("Hidden Name", logged)
        self.assertNotIn("hidden_handle", logged)

    async def test_reply_delivery_error_is_recorded_and_reported_to_developer(self):
        await self._submit_flow(
            1001,
            "a",
            "question",
            "A question",
            first_name="Hidden",
            username="hidden",
        )
        dev_notice = _Message(9001, chat_id=9001)
        await developer.handle_feedback_callback(_callback("devfb:reply:1", 9001, dev_notice))
        reply = _Message(9001, text="Response")
        reply.bot.send_message.side_effect = TelegramAPIError(
            method=SendMessage(chat_id=1001, text="Response"),
            message="blocked",
        )
        await developer.receive_feedback_message(reply)
        self.assertIn(
            t("developer_feedback_reply_failed", "uk").format(ticket_id=1),
            reply.answer.await_args.args[0],
        )
        history = feedback_db.get_feedback_messages(1)
        self.assertEqual(history[-1]["delivery_status"], "failed")
        self.assertEqual(feedback_db.get_feedback(1)["status"], "open")


if __name__ == "__main__":
    unittest.main()
