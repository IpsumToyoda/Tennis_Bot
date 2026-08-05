import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import init_db
from services import add_match_result, get_standings, parse_score


class ServicesTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.temp_dir.name, "test_tournament.db")
        init_db(self.db_path)

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def test_parse_score_parses_sets(self) -> None:
        parsed = parse_score("6:3 7:5")
        self.assertEqual(parsed, [(6, 3), (7, 5)])

    def test_parse_score_rejects_invalid_format(self) -> None:
        with self.assertRaises(ValueError):
            parse_score("bad score")

    def test_add_match_result_updates_standings(self) -> None:
        result = add_match_result("Alice", "Bob", "6:3 7:5", "Judge", self.db_path)

        self.assertIn("Alice победил Bob", result)

        rows = get_standings(self.db_path)
        self.assertEqual(len(rows), 2)

        alice = next(row for row in rows if row["name"] == "Alice")
        bob = next(row for row in rows if row["name"] == "Bob")

        self.assertEqual(alice["wins"], 1)
        self.assertEqual(alice["losses"], 0)
        self.assertEqual(alice["sets_won"], 2)
        self.assertEqual(alice["sets_lost"], 0)

        self.assertEqual(bob["wins"], 0)
        self.assertEqual(bob["losses"], 1)
        self.assertEqual(bob["sets_won"], 0)
        self.assertEqual(bob["sets_lost"], 2)


if __name__ == "__main__":
    unittest.main()
