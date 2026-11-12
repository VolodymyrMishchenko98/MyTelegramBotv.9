import ast
import re
import unittest
from pathlib import Path
from unittest.mock import patch

import bot_legacy
from locales import t


ROOT = Path(__file__).resolve().parents[1]


def _active_command_files() -> list[Path]:
    runtime = ast.parse((ROOT / "bot.py").read_text(encoding="utf-8"))
    handler_modules = {}
    for node in runtime.body:
        if isinstance(node, ast.ImportFrom) and node.module == "handlers":
            for alias in node.names:
                handler_modules[alias.asname or alias.name] = alias.name

    active_routers = set()
    for node in ast.walk(runtime):
        if not isinstance(node, ast.For) or not isinstance(node.iter, ast.Tuple):
            continue
        if not isinstance(node.target, ast.Name) or node.target.id != "router":
            continue
        for item in node.iter.elts:
            if (
                isinstance(item, ast.Attribute)
                and item.attr == "router"
                and isinstance(item.value, ast.Name)
            ):
                active_routers.add(item.value.id)

    return [ROOT / "bot_legacy.py"] + [
        ROOT / "handlers" / f"{handler_modules[router]}.py"
        for router in sorted(active_routers)
    ]


def _registered_commands() -> list[str]:
    commands = []
    for path in _active_command_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute) or decorator.func.attr != "message":
                    continue
                for nested in ast.walk(decorator):
                    if not isinstance(nested, ast.Call):
                        continue
                    if not isinstance(nested.func, ast.Name) or nested.func.id != "Command":
                        continue
                    values = list(nested.args)
                    for keyword in nested.keywords:
                        if keyword.arg in ("command", "commands"):
                            values.append(keyword.value)
                    for value in values:
                        if isinstance(value, ast.Constant) and isinstance(value.value, str):
                            commands.append(value.value)
                        elif isinstance(value, (ast.List, ast.Tuple, ast.Set)):
                            commands.extend(
                                element.value
                                for element in value.elts
                                if isinstance(element, ast.Constant)
                                and isinstance(element.value, str)
                            )
    return commands


MAIN_COMMANDS = [
    "start",
    "help",
    "workout",
    "today",
    "stats",
    "history",
    "program",
]


def _literal_callback_registrations() -> list[str]:
    registrations = []
    for path in _active_command_files():
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            for decorator in node.decorator_list:
                if not isinstance(decorator, ast.Call):
                    continue
                if not isinstance(decorator.func, ast.Attribute) or decorator.func.attr != "callback_query":
                    continue
                for expression in ast.walk(decorator):
                    if not isinstance(expression, ast.Compare) or len(expression.comparators) != 1:
                        continue
                    if not isinstance(expression.left, ast.Attribute) or expression.left.attr != "data":
                        continue
                    value = expression.comparators[0]
                    if isinstance(value, ast.Constant) and isinstance(value.value, str):
                        registrations.append(value.value)
    return registrations


def _readme_commands(language_heading: str) -> list[str]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    command_section = readme.split("## 🎮 Команди / Commands\n", 1)[1].split("\n## ", 1)[0]
    language_section = command_section.split(f"### {language_heading}\n", 1)[1]
    if language_heading == "Українська":
        language_section = language_section.split("\n### English\n", 1)[0]
    language_section = language_section.split("\n### ", 1)[0]
    return re.findall(r"`/([a-z_]+)`", language_section)


class CommandDocumentationTests(unittest.TestCase):
    def test_literal_callback_registrations_are_not_duplicated(self):
        callbacks = _literal_callback_registrations()
        self.assertEqual(len(callbacks), len(set(callbacks)))

    def test_telegram_menus_contain_only_the_ordered_core_commands(self):
        registered = _registered_commands()
        self.assertEqual(len(registered), len(set(registered)), "active command registrations must be unique")
        self.assertTrue(set(MAIN_COMMANDS).issubset(registered))

        for lang, heading in (("uk", "Українська"), ("en", "English")):
            with self.subTest(language=lang):
                commands = bot_legacy.build_bot_commands(lang)
                self.assertEqual([command.command for command in commands], MAIN_COMMANDS)
                self.assertEqual(_readme_commands(heading), MAIN_COMMANDS)
                self.assertEqual(len({command.command for command in commands}), len(commands))
                self.assertTrue(all(0 < len(command.description) <= 256 for command in commands))
                self.assertEqual(
                    list(bot_legacy.BOT_COMMAND_DESCRIPTIONS[lang]),
                    MAIN_COMMANDS,
                )

    def test_language_callback_uses_the_same_command_guide(self):
        for lang in ("uk", "en"):
            with self.subTest(language=lang):
                self.assertEqual(bot_legacy.build_start_text(lang), t("help", lang))

    def test_help_is_sectioned_and_hides_admin_commands_from_regular_users(self):
        for lang in ("uk", "en"):
            with self.subTest(language=lang):
                help_text = bot_legacy.build_help_text(lang, 987654321)
                self.assertIn("stats" if lang == "en" else "Статистика", help_text)
                self.assertIn("Settings" if lang == "en" else "Налаштування", help_text)
                self.assertNotIn("/admin", help_text)
                self.assertNotIn("/backup", help_text)
                self.assertNotIn("/weight_stats", help_text)

        with patch("handlers.admin.is_admin", return_value=True):
            for lang in ("uk", "en"):
                with self.subTest(admin_language=lang):
                    admin_help = bot_legacy.build_help_text(lang, 1)
                    self.assertIn("/admin", admin_help)
                    self.assertIn("/backup", admin_help)

    def test_all_legacy_commands_remain_registered_but_not_in_telegram_menu(self):
        registered = set(_registered_commands())
        menu = {command.command for command in bot_legacy.build_bot_commands("en")}
        legacy_commands = {
            "level", "chart", "weight_stats", "edit_profile", "profile_visibility",
            "set_goal", "wallet", "use", "challenge", "daily", "suggest",
            "motivate", "tip", "shop", "reminders", "export", "import", "reset",
            "admin", "backup", "change_language", "developer", "goal", "profile",
            "weight",
        }
        self.assertTrue(legacy_commands.issubset(registered))
        self.assertTrue(legacy_commands.isdisjoint(menu))

    def test_readme_documents_legacy_command_groups_outside_the_menu_list(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for command in _registered_commands():
            if command not in MAIN_COMMANDS:
                self.assertIn(f"`/{command}`", readme)

    def test_help_navigation_callbacks_remain_unchanged(self):
        callbacks = {
            button.callback_data
            for row in bot_legacy.help_keyboard("uk").inline_keyboard
            for button in row
        }
        self.assertEqual(callbacks, {"welcome_workout", "welcome_menu"})


if __name__ == "__main__":
    unittest.main()
