import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from db import get_connection, init_db
from services import add_match_result, get_standings, get_tournament_status, parse_score, start_tournament


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
        from services import ensure_player

        connection = get_connection(self.db_path)
        ensure_player(connection, "Alice")
        ensure_player(connection, "Bob")
        connection.close()
        start_tournament(self.db_path)
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

    def test_start_tournament_marks_active_status(self) -> None:
        from services import ensure_player

        connection = get_connection(self.db_path)
        ensure_player(connection, "Alice")
        ensure_player(connection, "Bob")
        connection.close()

        result = start_tournament(self.db_path)

        self.assertIn("Турнир начат", result)
        self.assertEqual(get_tournament_status(self.db_path), "active")

    def test_result_requires_active_tournament(self) -> None:
        with self.assertRaises(ValueError):
            add_match_result("Alice", "Bob", "6:3", "Judge", self.db_path)

    def test_parse_score_rejects_invalid_sets(self) -> None:
        for score in ("1:6", "6:6", "6:3 garbage", "6:3 6:4 6:0"):
            with self.assertRaises(ValueError):
                parse_score(score)


if __name__ == "__main__":
    unittest.main()
