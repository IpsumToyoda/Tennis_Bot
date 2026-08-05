import sys
from pathlib import Path

import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from handlers import build_main_menu_keyboard


class InlineKeyboardTests(unittest.TestCase):
    def test_main_menu_keyboard_contains_expected_actions(self) -> None:
        keyboard = build_main_menu_keyboard()
        labels = [button.text for row in keyboard.inline_keyboard for button in row]

        self.assertIn("Регистрация", labels)
        self.assertIn("Игроки", labels)
        self.assertIn("Таблица", labels)
        self.assertIn("Статистика", labels)


if __name__ == "__main__":
    unittest.main()
