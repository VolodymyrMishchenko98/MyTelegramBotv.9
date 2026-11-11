import unittest
from collections import OrderedDict
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bot_legacy
from daily_tasks import DAILY_TASKS, DEFAULT_DAILY_TASK_ID
from handlers import keyboards
from locales import TEXTS, t


def _callbacks(markup):
    return {
        button.callback_data
        for row in markup.inline_keyboard
        for button in row
    }


def _message(text=None, *, message_id=500):
    return SimpleNamespace(
        chat=SimpleNamespace(id=400),
        message_id=message_id,
        text=text,
        answer=AsyncMock(),
        edit_text=AsyncMock(),
    )


def _callback(user_id=25, data="", text=None, *, message_id=500):
    return SimpleNamespace(
        from_user=SimpleNamespace(id=user_id),
        data=data,
        message=_message(text, message_id=message_id),
        answer=AsyncMock(),
    )


class _FakeCursor:
    def __init__(self, fetchone_values=()):
        self.fetchone_values = list(fetchone_values)
        self.executed = []

    def execute(self, query, params=()):
        self.executed.append((query, params))

    def fetchone(self):
        return self.fetchone_values.pop(0) if self.fetchone_values else None


class _FakeDb:
    def __init__(self, cursor):
        self._cursor = cursor
        self.committed = False
        self.closed = False

    def cursor(self):
        return self._cursor

    def commit(self):
        self.committed = True

    def close(self):
        self.closed = True


class EngagementNavigationTests(unittest.IsolatedAsyncioTestCase):
    def test_section_menus_are_bilingual_and_link_to_all_three_groups(self):
        for lang in ("uk", "en"):
            with self.subTest(language=lang):
                self.assertEqual(
                    _callbacks(keyboards.sections_keyboard(lang)),
                    {"economy_home", "activities_home", "inspiration_home", "welcome_menu"},
                )
                self.assertIn("welcome_sections", _callbacks(bot_legacy.welcome_keyboard(lang)))
                for key, entry in TEXTS.items():
                    if key.startswith(("sections_", "economy_", "activities_", "inspiration_")):
                        self.assertTrue(entry.get("uk"), key)
                        self.assertTrue(entry.get("en"), key)

    async def test_economy_home_and_empty_inventory_have_navigation(self):
        message = _message()
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "get_coin_balance", return_value=42):
            await bot_legacy.show_economy_home(message, 25)

        args = message.answer.await_args
        self.assertIn("42 coins", args.args[0])
        self.assertEqual(
            _callbacks(args.kwargs["reply_markup"]),
            {"economy_shop", "economy_inventory", "economy_use", "welcome_menu"},
        )

        message = _message()
        with patch.object(bot_legacy, "get_user_language", return_value="uk"), \
             patch.object(bot_legacy, "get_user_items", return_value={}):
            await bot_legacy.show_inventory(message, 25)

        args = message.answer.await_args
        self.assertEqual(args.args[0], t("economy_use_empty", "uk"))
        self.assertTrue({"economy_shop", "economy_inventory", "economy_home"}.issubset(
            _callbacks(args.kwargs["reply_markup"])
        ))

        message = _message()
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "get_user_items", return_value={"gym_towel": 1}):
            await bot_legacy.show_inventory(message, 25)

        self.assertIn(
            "use_item_gym_towel",
            _callbacks(message.answer.await_args.kwargs["reply_markup"]),
        )

    async def test_legacy_commands_still_open_their_existing_scenarios(self):
        message = SimpleNamespace(
            from_user=SimpleNamespace(id=952),
            answer=AsyncMock(),
        )
        command_screens = (
            (bot_legacy.shop, "show_shop"),
            (bot_legacy.wallet, "show_wallet"),
            (bot_legacy.use_item, "show_inventory"),
            (bot_legacy.daily, "show_daily_task"),
            (bot_legacy.challenge, "show_challenge"),
            (bot_legacy.suggest, "show_suggest"),
            (bot_legacy.motivate, "show_motivation"),
            (bot_legacy.tip, "show_tip"),
        )
        for command, screen_name in command_screens:
            with self.subTest(command=command.__name__), \
                 patch.object(bot_legacy, screen_name, new_callable=AsyncMock) as show:
                await command(message)
                show.assert_awaited_once_with(message, 952)

    async def test_new_section_callbacks_route_to_their_screen_renderers(self):
        routes = (
            (bot_legacy.welcome_sections, "show_sections_menu"),
            (bot_legacy.economy_home, "show_economy_home"),
            (bot_legacy.economy_shop, "show_shop"),
            (bot_legacy.economy_inventory, "show_wallet"),
            (bot_legacy.economy_use, "show_inventory"),
            (bot_legacy.activities_home, "show_activities_home"),
            (bot_legacy.activities_daily, "show_daily_task"),
            (bot_legacy.activities_challenge, "show_challenge"),
            (bot_legacy.inspiration_home, "show_inspiration_home"),
            (bot_legacy.inspiration_suggest, "show_suggest"),
            (bot_legacy.inspiration_motivate, "show_motivation"),
            (bot_legacy.inspiration_tip, "show_tip"),
        )
        for route, renderer_name in routes:
            callback = _callback(user_id=953)
            with self.subTest(route=route.__name__), \
                 patch.object(bot_legacy, renderer_name, new_callable=AsyncMock) as renderer:
                await route(callback)

            callback.answer.assert_awaited_once_with()
            renderer.assert_awaited_once_with(callback.message, 953, edit=True)

    def test_shop_purchase_buttons_keep_legacy_prefix_and_use_unique_tokens(self):
        item_id, item = next(iter(bot_legacy.SHOP_ITEMS.items()))
        first = bot_legacy.shop_category_keyboard("en", item["category"])
        second = bot_legacy.shop_category_keyboard("en", item["category"])
        first_data = next(
            data for data in _callbacks(first)
            if data.startswith(f"shop_buy_{item_id}:")
        )
        second_data = next(
            data for data in _callbacks(second)
            if data.startswith(f"shop_buy_{item_id}:")
        )

        self.assertTrue(first_data.startswith(f"shop_buy_{item_id}:"))
        self.assertTrue(second_data.startswith(f"shop_buy_{item_id}:"))
        self.assertNotEqual(first_data, second_data)
        self.assertIn("shop_back_to_categories", _callbacks(first))
        self.assertIn("economy_home", _callbacks(first))

    async def test_duplicate_shop_button_does_not_charge_twice_and_legacy_callback_still_works(self):
        item = {
            "cost": 10,
            "uk_name": "Тест",
            "en_name": "Test",
            "uk_desc": "Опис",
            "en_desc": "Description",
            "type": "collectible",
            "category": "Test",
        }
        callbacks = (
            _callback(user_id=77123, data="shop_buy_navigation_test_item"),
            _callback(
                user_id=77124,
                data="shop_buy_navigation_test_item:purchase-token",
                message_id=501,
            ),
        )
        with patch.object(bot_legacy, "SHOP_ITEMS", {"navigation_test_item": item}), \
             patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "ensure_user"), \
             patch.object(bot_legacy, "get_user_xp_level", return_value={"level": 1}), \
             patch.object(bot_legacy, "buy_shop_item", return_value=(True, 90, "success")) as buy, \
             patch.object(bot_legacy, "_shop_purchase_in_progress", set()), \
             patch.object(bot_legacy, "_shop_purchase_completed", OrderedDict()):
            for callback in callbacks:
                await bot_legacy.shop_buy(callback)
                await bot_legacy.shop_buy(callback)

        self.assertEqual(buy.call_count, 2)
        for callback in callbacks:
            self.assertEqual(callback.message.edit_text.await_count, 1)
            self.assertIn(
                t("economy_purchase_duplicate", "en"),
                callback.answer.await_args_list[-1].args,
            )

    async def test_daily_and_challenge_keep_separate_callbacks_and_reward_sources(self):
        task = DAILY_TASKS[DEFAULT_DAILY_TASK_ID]
        today = datetime.now().strftime("%Y-%m-%d")
        daily_callback = _callback(data=f"daily_add_{today}")
        daily_rewards = {
            "coins_awarded": task["reward"],
            "xp_awarded": bot_legacy.DAILY_TASK_XP_REWARD,
            "balance": 20,
            "achievements": [],
            "leveled_up": False,
        }
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "get_or_create_daily_task", return_value=(
                 today, DEFAULT_DAILY_TASK_ID, task, 0, False
             )), \
             patch.object(bot_legacy, "update_daily_progress", return_value=(
                 task, task["target"], True, False, 20
             )), \
             patch.object(bot_legacy, "settle_action_rewards", return_value=daily_rewards) as settle, \
             patch.object(bot_legacy, "reward_summary", return_value="daily rewards"):
            await bot_legacy.daily_progress(daily_callback)

        self.assertEqual(settle.call_args.args[4], "daily")
        self.assertEqual(
            _callbacks(bot_legacy.daily_task_keyboard("en", task, False, today)),
            {
                f"daily_add_{today}",
                "activities_challenge",
                "activities_home",
                "welcome_menu",
            },
        )
        self.assertIn("challenge_done", _callbacks(bot_legacy.challenge_keyboard("en")))

        cursor = _FakeCursor([None])
        db = _FakeDb(cursor)
        challenge_callback = _callback(
            data="challenge_done",
            text="Challenge of the day\n🔥 Test challenge",
        )
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "get_db", return_value=db), \
             patch.object(bot_legacy, "settle_action_rewards", return_value={
                 "xp_awarded": bot_legacy.CHALLENGE_XP_REWARD,
                 "coins_awarded": bot_legacy.CHALLENGE_COIN_REWARD,
                 "balance": 30,
                 "achievements": [],
             }) as settle, \
             patch.object(bot_legacy, "reward_summary", return_value="challenge rewards"):
            await bot_legacy.challenge_done(challenge_callback)

        self.assertIn("is_challenge=1", cursor.executed[0][0])
        self.assertIn("is_challenge", cursor.executed[1][0])
        self.assertEqual(settle.call_args.args[4], "challenge")
        self.assertTrue(db.committed)

    async def test_suggested_workout_confirmation_saves_and_settles_existing_rewards(self):
        cursor = _FakeCursor([None])
        db = _FakeDb(cursor)
        callback = _callback(
            data="suggest_done",
            text="Suggested workout\n• Run 20 min\n• Push ups 3x10",
        )
        with patch.object(bot_legacy, "get_user_language", return_value="en"), \
             patch.object(bot_legacy, "get_db", return_value=db), \
             patch.object(bot_legacy, "settle_action_rewards", return_value={
                 "xp_awarded": bot_legacy.SUGGESTED_WORKOUT_XP,
                 "coins_awarded": bot_legacy.SUGGESTED_WORKOUT_REWARD,
                 "balance": 30,
                 "achievements": [],
             }) as settle, \
             patch.object(bot_legacy, "reward_summary", return_value="rewards"):
            await bot_legacy.suggest_done(callback)

        workout_inserts = [
            (query, params)
            for query, params in cursor.executed
            if query.startswith("INSERT INTO workouts")
        ]
        self.assertEqual(len(workout_inserts), 2)
        self.assertEqual(settle.call_args.args[4], "suggest")
        self.assertTrue(db.committed)
        self.assertIn("inspiration_home", _callbacks(callback.message.edit_text.await_args.kwargs["reply_markup"]))

    async def test_inspiration_screens_keep_existing_action_callbacks(self):
        for screen, expected in (
            (bot_legacy.suggest_keyboard("en"), {"suggest_done", "suggest_retry", "inspiration_home"}),
            (bot_legacy.challenge_keyboard("en"), {"challenge_done", "challenge_next", "activities_home"}),
        ):
            self.assertTrue(expected.issubset(_callbacks(screen)))

        callback = _callback(data="inspiration_motivate")
        with patch.object(bot_legacy, "show_motivation", new_callable=AsyncMock) as show:
            await bot_legacy.inspiration_motivate(callback)

        show.assert_awaited_once_with(callback.message, 25, edit=True)


if __name__ == "__main__":
    unittest.main()
