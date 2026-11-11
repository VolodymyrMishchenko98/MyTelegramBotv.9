import ast
import re
import unittest
from pathlib import Path

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


def _readme_commands(language_heading: str) -> set[str]:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    command_section = readme.split("## 🎮 Команди / Commands\n", 1)[1].split("\n## ", 1)[0]
    language_section = command_section.split(f"### {language_heading}\n", 1)[1]
    if language_heading == "Українська":
        language_section = language_section.split("\n### English\n", 1)[0]
    return set(re.findall(r"`/([a-z_]+)`", language_section))


class CommandDocumentationTests(unittest.TestCase):
    def test_help_readme_and_telegram_menus_match_active_registrations(self):
        registered = _registered_commands()
        self.assertEqual(len(registered), len(set(registered)), "active command registrations must be unique")
        expected = set(registered)

        for lang, heading in (("uk", "Українська"), ("en", "English")):
            with self.subTest(language=lang):
                help_commands = set(re.findall(r"(?<!<)/([a-z_]+)", t("help", lang)))
                menu_commands = {command.command for command in bot_legacy.build_bot_commands(lang)}
                self.assertEqual(help_commands, expected)
                self.assertEqual(_readme_commands(heading), expected)
                self.assertEqual(menu_commands, expected)

    def test_language_callback_uses_the_same_command_guide(self):
        for lang in ("uk", "en"):
            with self.subTest(language=lang):
                self.assertEqual(bot_legacy.build_start_text(lang), t("help", lang))

    def test_help_navigation_callbacks_remain_unchanged(self):
        callbacks = {
            button.callback_data
            for row in bot_legacy.help_keyboard("uk").inline_keyboard
            for button in row
        }
        self.assertEqual(callbacks, {"welcome_workout", "welcome_menu"})


if __name__ == "__main__":
    unittest.main()
