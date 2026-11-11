import asyncio
import sqlite3
import tempfile
import unittest
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import bot
import bot_legacy
from handlers import programs
from locales import TEXTS, t
from services import program_generator
from services import training_programs as program_db


def _preferences(**overrides):
    result = {
        "goal": "strength",
        "location": "home",
        "frequency": "2-3",
        "duration": "30",
        "level": "beginner",
        "equipment": ["none"],
        "other_equipment": "",
        "notes": "",
    }
    result.update(overrides)
    return result


class _Message:
    def __init__(self, user_id=101, text=None):
        self.text = text
        self.from_user = SimpleNamespace(id=user_id)
        self.chat = SimpleNamespace(id=user_id)
        self.answer = AsyncMock()
        self.edit_text = AsyncMock()


def _callback(data, user_id=101):
    return SimpleNamespace(
        data=data,
        from_user=SimpleNamespace(id=user_id),
        message=_Message(user_id),
        answer=AsyncMock(),
    )


class ProgramGeneratorTests(unittest.TestCase):
    def test_builds_moderate_weekly_plan_with_rest_days_and_progression(self):
        plan = program_generator.generate_program(_preferences())

        self.assertEqual(len(plan["sessions"]), 3)
        self.assertEqual(
            [session["day_key"] for session in plan["sessions"]],
            ["program_day_monday", "program_day_wednesday", "program_day_friday"],
        )
        self.assertEqual(plan["duration_minutes"], 30)
        self.assertEqual(len(plan["progression_keys"]), 4)
        self.assertEqual(plan["sessions"][0]["warmup_key"], "program_warmup_detail")
        self.assertEqual(plan["sessions"][0]["cooldown_key"], "program_cooldown_detail")
        self.assertTrue(all(session["rest_seconds"] > 0 for session in plan["sessions"]))

    def test_frequency_options_create_three_four_or_five_sessions(self):
        for frequency, count in (("2-3", 3), ("4", 4), ("5", 5)):
            with self.subTest(frequency=frequency):
                plan = program_generator.generate_program(
                    _preferences(frequency=frequency)
                )
                self.assertEqual(len(plan["sessions"]), count)
                if frequency == "5":
                    self.assertEqual(
                        [session["title_key"] for session in plan["sessions"]][1::2],
                        ["program_session_mobility", "program_session_mobility"],
                    )

    def test_duration_equipment_location_and_goal_affect_the_plan(self):
        home = program_generator.generate_program(
            _preferences(goal="endurance", location="home", duration="15-20")
        )
        gym = program_generator.generate_program(
            _preferences(
                goal="endurance",
                location="gym",
                duration="45",
                equipment=["machines"],
            )
        )

        self.assertEqual(home["duration_minutes"], 20)
        self.assertIn(
            "program_exercise_march",
            {exercise["key"] for exercise in home["sessions"][0]["exercises"]},
        )
        self.assertIn(
            "program_prescription_minutes",
            {exercise["prescription_key"] for exercise in home["sessions"][0]["exercises"]},
        )
        self.assertIn(
            "program_stationary_bike",
            {exercise["key"] for exercise in gym["sessions"][0]["exercises"]},
        )
        self.assertEqual(len(gym["sessions"][0]["exercises"]), 5)

    def test_minor_gets_technique_first_recommendation_and_lower_volume(self):
        plan = program_generator.generate_program(
            _preferences(level="advanced"),
            age=16,
        )

        self.assertTrue(plan["minor_guidance"])
        self.assertEqual(plan["safety_key"], "program_safety_minor")
        self.assertTrue(all(
            exercise["sets"] == 2
            for session in plan["sessions"]
            for exercise in session["exercises"]
        ))

    def test_extra_equipment_is_only_recognized_from_explicit_comma_separated_names(self):
        explicit = program_generator.generate_program(
            _preferences(
                equipment=["other"],
                other_equipment="гантелі",
            )
        )
        negated = program_generator.generate_program(
            _preferences(
                equipment=["other"],
                other_equipment="I have no dumbbells",
            )
        )

        self.assertIn(
            "program_dumbbell_squat",
            {exercise["key"] for exercise in explicit["sessions"][0]["exercises"]},
        )
        self.assertNotIn(
            "program_dumbbell_squat",
            {exercise["key"] for exercise in negated["sessions"][0]["exercises"]},
        )
        bands = program_generator.generate_program(
            _preferences(
                equipment=["other"],
                other_equipment="resistance bands",
            )
        )
        self.assertIn(
            "program_band_row",
            {exercise["key"] for exercise in bands["sessions"][0]["exercises"]},
        )

    def test_invalid_survey_answers_are_rejected(self):
        invalid_cases = (
            _preferences(goal="lose weight"),
            _preferences(location="unknown"),
            _preferences(equipment=[]),
            _preferences(equipment=["none", "dumbbells"]),
            _preferences(notes="x" * 501),
        )
        for answers in invalid_cases:
            with self.subTest(answers=answers):
                with self.assertRaises(ValueError):
                    program_generator.generate_program(answers)
        with self.assertRaises(ValueError):
            program_generator.generate_program(_preferences(goal=[]))

    def test_all_program_copy_is_localized_in_uk_and_en(self):
        for key, translations in TEXTS.items():
            if not key.startswith("program_"):
                continue
            with self.subTest(key=key):
                self.assertIn("uk", translations)
                self.assertIn("en", translations)
                self.assertNotEqual(t(key, "uk"), f"[{key}]")
                self.assertNotEqual(t(key, "en"), f"[{key}]")

    def test_generated_exercise_ids_always_have_localized_labels(self):
        for goal in program_generator.GOALS:
            for location in program_generator.LOCATIONS:
                for equipment in (["none"], ["dumbbells"], ["machines"],
                                  ["pullup_bar"], ["other"]):
                    with self.subTest(goal=goal, location=location, equipment=equipment):
                        plan = program_generator.generate_program(
                            _preferences(
                                goal=goal,
                                location=location,
                                equipment=equipment,
                                other_equipment="resistance bands"
                                if equipment == ["other"] else "",
                            )
                        )
                        for session in plan["sessions"]:
                            for exercise in session["exercises"]:
                                self.assertIn(exercise["key"], TEXTS)


class TrainingProgramPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "plans.sqlite3"

        @contextmanager
        def db_context():
            connection = sqlite3.connect(self.db_path)
            try:
                yield connection
                connection.commit()
            except Exception:
                connection.rollback()
                raise
            finally:
                connection.close()

        self.patcher = patch.object(program_db, "get_db_context", db_context)
        self.patcher.start()
        connection = sqlite3.connect(self.db_path)
        try:
            program_db.ensure_program_tables(connection.cursor())
            connection.commit()
        finally:
            connection.close()

    def tearDown(self):
        self.patcher.stop()
        self.temp_dir.cleanup()

    def test_save_load_replace_and_archive_are_user_scoped(self):
        preferences = _preferences()
        content = program_generator.generate_program(preferences)
        first_id = program_db.save_program(101, preferences, content)
        second_id = program_db.save_program(
            101,
            _preferences(goal="mobility"),
            program_generator.generate_program(_preferences(goal="mobility")),
        )

        active = program_db.get_active_program(101)
        archived = program_db.get_program(101, first_id)
        self.assertEqual(active["id"], second_id)
        self.assertEqual(active["status"], "active")
        self.assertEqual(archived["status"], "archived")
        self.assertIsNone(program_db.get_program(202, second_id))
        self.assertEqual(
            [item["id"] for item in program_db.list_archived_programs(101)],
            [first_id],
        )
        self.assertTrue(program_db.archive_program(101, second_id))
        self.assertIsNone(program_db.get_active_program(101))

    def test_schema_initialization_is_idempotent(self):
        connection = sqlite3.connect(self.db_path)
        try:
            program_db.ensure_program_tables(connection.cursor())
            program_db.ensure_program_tables(connection.cursor())
            connection.commit()
            self.assertEqual(
                connection.execute(
                    "SELECT COUNT(*) FROM sqlite_master "
                    "WHERE type='table' AND name='training_programs'"
                ).fetchone()[0],
                1,
            )
        finally:
            connection.close()

    def test_application_database_initialization_installs_program_schema(self):
        connection = sqlite3.connect(":memory:")

        class DatabaseProxy:
            def cursor(self):
                return connection.cursor()

            def commit(self):
                connection.commit()

            def close(self):
                connection.commit()

        with patch.object(bot_legacy, "get_db", return_value=DatabaseProxy()):
            bot_legacy.init_db()
        self.assertEqual(
            connection.execute(
                "SELECT COUNT(*) FROM sqlite_master "
                "WHERE type='table' AND name='training_programs'"
            ).fetchone()[0],
            1,
        )
        connection.close()


class ProgramHandlerTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.states = {}
        self.languages = {101: "uk", 202: "en"}
        programs.configure(
            self.languages.__getitem__,
            self.states.get,
            lambda user_id, state: self.states.__setitem__(user_id, state),
            lambda user_id: self.states.pop(user_id, None),
        )

    def tearDown(self):
        programs._drafts.clear()

    async def test_complete_survey_confirmation_and_save_flow(self):
        program = {
            "id": 7,
            "user_id": 101,
            "created_at": "2026-11-11T10:00:00+00:00",
            "preferences": _preferences(),
            "content": program_generator.generate_program(_preferences()),
            "status": "active",
            "archived_at": None,
        }
        with patch.object(programs.program_db, "get_user_age", return_value=None), \
             patch.object(programs.program_db, "save_program", return_value=7) as save, \
             patch.object(programs.program_db, "get_active_program", return_value=program):
            message = _Message()
            await programs.program_command(message)
            await programs.handle_program_callback(_callback("program:create"))
            self.assertEqual(self.states[101], programs.STATE_GOAL)
            for field, value, next_state in (
                ("goal", "strength", programs.STATE_LOCATION),
                ("location", "home", programs.STATE_FREQUENCY),
                ("frequency", "2-3", programs.STATE_DURATION),
                ("duration", "30", programs.STATE_LEVEL),
                ("level", "beginner", programs.STATE_EQUIPMENT),
            ):
                callback = _callback(f"program:choose:{field}:{value}")
                await programs.handle_program_callback(callback)
                self.assertEqual(self.states[101], next_state)
            await programs.handle_program_callback(
                _callback("program:equipment:none")
            )
            await programs.handle_program_callback(
                _callback("program:equipment:done")
            )
            await programs.handle_program_callback(_callback("program:skip_notes"))
            self.assertEqual(self.states[101], programs.STATE_CONFIRM)
            confirm = _callback("program:confirm")
            await programs.handle_program_callback(confirm)

        save.assert_called_once()
        self.assertEqual(save.call_args.args[0], 101)
        self.assertEqual(self.states, {})
        self.assertIn(
            "Тижнева програма #7",
            confirm.message.edit_text.await_args.args[0],
        )
        await programs.handle_program_callback(confirm)
        save.assert_called_once()

    async def test_back_cancel_other_equipment_and_free_text(self):
        message = _Message()
        await programs.handle_program_callback(_callback("program:create"))
        await programs.handle_program_callback(
            _callback("program:choose:goal:general")
        )
        await programs.handle_program_callback(_callback("program:back"))
        self.assertEqual(self.states[101], programs.STATE_GOAL)

        await programs.handle_program_callback(
            _callback("program:choose:goal:general")
        )
        await programs.handle_program_callback(
            _callback("program:choose:location:home")
        )
        await programs.handle_program_callback(
            _callback("program:choose:frequency:2-3")
        )
        await programs.handle_program_callback(
            _callback("program:choose:duration:30")
        )
        await programs.handle_program_callback(
            _callback("program:choose:level:beginner")
        )
        await programs.handle_program_callback(_callback("program:equipment:other"))
        await programs.handle_program_callback(_callback("program:equipment:done"))
        self.assertEqual(self.states[101], programs.STATE_EQUIPMENT_OTHER)

        equipment_message = _Message(text="resistance bands")
        await programs.receive_program_text(equipment_message)
        self.assertEqual(self.states[101], programs.STATE_NOTES)
        notes_message = _Message(text="Keep sessions low impact")
        with patch.object(programs.program_db, "get_active_program", return_value=None):
            await programs.receive_program_text(notes_message)
        self.assertEqual(self.states[101], programs.STATE_CONFIRM)

        with patch.object(programs.program_db, "get_active_program", return_value=None):
            await programs.handle_program_callback(_callback("program:cancel"))
        self.assertNotIn(101, self.states)

    async def test_bad_callbacks_are_rejected_and_main_menu_button_exists(self):
        invalid = _callback("program:choose:goal:unknown")
        await programs.handle_program_callback(invalid)
        self.assertTrue(invalid.answer.await_args.kwargs["show_alert"])

        keyboard = bot_legacy.welcome_keyboard("en")
        program_buttons = [
            button
            for row in keyboard.inline_keyboard
            for button in row
            if button.callback_data == "program:open"
        ]
        self.assertEqual(len(program_buttons), 1)
        self.assertEqual(program_buttons[0].text, "📝 Create a program")

    async def test_command_is_listed_in_help_and_telegram_commands(self):
        for lang in ("uk", "en"):
            self.assertIn("/program", t("help", lang))
            self.assertIn(
                "program",
                {command.command for command in bot_legacy.build_bot_commands(lang)},
            )

    async def test_program_state_is_not_consumed_by_the_legacy_catch_all(self):
        message = _Message()
        bot_legacy.set_user_state(message.from_user.id, programs.STATE_NOTES)
        try:
            self.assertFalse(bot_legacy._is_non_command_message(message))
            self.assertTrue(bot_legacy._is_training_program_state(message))
        finally:
            bot_legacy.clear_user_state(message.from_user.id)

    async def test_replacing_or_clearing_state_discards_unsaved_answers(self):
        programs._drafts[101] = {"notes": "private unsaved note"}
        bot_legacy.set_user_state(101, "workout")
        self.assertNotIn(101, programs._drafts)

        programs._drafts[101] = {"notes": "another unsaved note"}
        bot_legacy.clear_user_state(101)
        self.assertNotIn(101, programs._drafts)

    async def test_individual_day_view_has_full_session_details_and_back_link(self):
        stored = {
            "id": 13,
            "user_id": 202,
            "created_at": "2026-11-11T10:00:00+00:00",
            "preferences": _preferences(),
            "content": program_generator.generate_program(_preferences()),
            "status": "active",
            "archived_at": None,
        }
        callback = _callback("program:day:13:0", user_id=202)
        with patch.object(programs.program_db, "get_program", return_value=stored):
            await programs.handle_program_callback(callback)

        text = callback.message.edit_text.await_args.args[0]
        self.assertIn("Warm-up", text)
        self.assertIn("Exercises:", text)
        self.assertIn("Rest:", text)
        actions = {
            button.callback_data
            for row in callback.message.edit_text.await_args.kwargs[
                "reply_markup"
            ].inline_keyboard
            for button in row
        }
        self.assertIn("program:plan:13", actions)

    async def test_program_router_is_registered(self):
        self.assertIn(programs.router, bot.dp.sub_routers)

    async def test_empty_menu_is_localized_and_has_create_action(self):
        for user_id, lang, phrase in (
            (101, "uk", "немає активної програми"),
            (202, "en", "don't have an active plan"),
        ):
            with self.subTest(language=lang), \
                 patch.object(programs.program_db, "get_active_program", return_value=None):
                message = _Message(user_id)
                await programs.program_command(message)
                text, kwargs = message.answer.await_args.args[0], message.answer.await_args.kwargs
                self.assertIn(phrase, text)
                callbacks = {
                    button.callback_data
                    for row in kwargs["reply_markup"].inline_keyboard
                    for button in row
                }
                self.assertIn("program:create", callbacks)

    async def test_user_text_is_escaped_in_summary(self):
        preferences = _preferences(notes="<script>alert(1)</script>")
        content = program_generator.generate_program(preferences)
        program = {
            "id": 5,
            "preferences": preferences,
            "content": content,
        }
        rendered = programs._summary_text(program, "en")
        self.assertNotIn("<script>", rendered)
        self.assertIn("&lt;script&gt;", rendered)


if __name__ == "__main__":
    unittest.main()
