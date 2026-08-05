import re
import sqlite3
from typing import List, Tuple

from db import execute, fetchone, get_connection, get_player_by_name, utc_now


def normalize_name(name: str) -> str:
    return " ".join(name.strip().split())


def ensure_player(connection, name: str) -> int:
    cleaned_name = normalize_name(name)
    if not cleaned_name:
        raise ValueError("Имя игрока не может быть пустым")

    existing = get_player_by_name(connection, cleaned_name)
    if existing:
        return existing["id"]

    execute(
        connection,
        "INSERT INTO players (name, created_at) VALUES (%s, %s)",
        (cleaned_name, utc_now()),
    )
    connection.commit()
    row = fetchone(
        connection,
        "SELECT id FROM players WHERE lower(name) = lower(%s)",
        (cleaned_name,),
    )
    return row["id"]


def parse_score(score_text: str) -> List[Tuple[int, int]]:
    score_text = score_text.strip()
    pairs = re.findall(r"(\d+)\s*[:\-]\s*(\d+)", score_text)
    if not pairs:
        raise ValueError("Нужен формат счета, например 6:3 или 6-3 7-5")

    parsed = [(int(first), int(second)) for first, second in pairs]
    if not all(first >= 0 and second >= 0 for first, second in parsed):
        raise ValueError("Счет должен содержать только положительные числа")
    if any(first == 0 and second == 0 for first, second in parsed):
        raise ValueError("Счет не может содержать нулевые значения")
    return parsed


def add_match_result(winner_name: str, loser_name: str, score_text: str, reported_by: str, db_path: str = "tournament.db") -> str:
    connection = get_connection(db_path)
    winner_id = ensure_player(connection, winner_name)
    loser_id = ensure_player(connection, loser_name)

    if winner_id == loser_id:
        raise ValueError("Победитель и проигравший не могут быть одним и тем же игроком")

    score_pairs = parse_score(score_text)
    sets_won = 0
    sets_lost = 0
    games_won = 0
    games_lost = 0

    for first, second in score_pairs:
        if first > second:
            sets_won += 1
        else:
            sets_lost += 1
        games_won += first
        games_lost += second

    connection.execute(
        """
        UPDATE players
        SET wins = wins + 1,
            sets_won = sets_won + ?,
            sets_lost = sets_lost + ?,
            games_won = games_won + ?,
            games_lost = games_lost + ?
        WHERE id = ?
        """,
        (sets_won, sets_lost, games_won, games_lost, winner_id),
    )
    connection.execute(
        """
        UPDATE players
        SET losses = losses + 1,
            sets_won = sets_won + ?,
            sets_lost = sets_lost + ?,
            games_won = games_won + ?,
            games_lost = games_lost + ?
        WHERE id = ?
        """,
        (sets_lost, sets_won, games_lost, games_won, loser_id),
    )
    connection.execute(
        """
        INSERT INTO matches (winner_id, loser_id, score, reported_by, reported_at)
        VALUES (?, ?, ?, ?, ?)
        """,
        (winner_id, loser_id, score_text, reported_by, utc_now()),
    )
    connection.commit()
    connection.close()

    return f"{winner_name} победил {loser_name} со счётом {score_text}"


def get_standings(db_path: str = "tournament.db") -> List[sqlite3.Row]:
    connection = get_connection(db_path)
    rows = connection.execute(
        """
        SELECT id, name, wins, losses, sets_won, sets_lost, games_won, games_lost
        FROM players
        ORDER BY wins DESC, losses ASC, (sets_won - sets_lost) DESC, (games_won - games_lost) DESC, name ASC
        """
    ).fetchall()
    connection.close()
    return rows


def get_player_stats(db_path: str = "tournament.db") -> List[sqlite3.Row]:
    connection = get_connection(db_path)
    rows = connection.execute(
        """
        SELECT name, wins, losses, sets_won, sets_lost, games_won, games_lost
        FROM players
        ORDER BY wins DESC, losses ASC, name ASC
        """
    ).fetchall()
    connection.close()
    return rows


def get_player_names(db_path: str = "tournament.db") -> List[str]:
    connection = get_connection(db_path)
    rows = connection.execute(
        "SELECT name FROM players ORDER BY name ASC"
    ).fetchall()
    connection.close()
    return [row["name"] for row in rows]


def format_table(db_path: str = "tournament.db") -> str:
    rows = get_standings(db_path)
    if not rows:
        return "Таблица пока пустая. Добавьте игроков командой /register_player"

    lines = ["Турнирная таблица:"]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"{index}. {row['name']} | В-П: {row['wins']}-{row['losses']} | Сеты: {row['sets_won']}-{row['sets_lost']} | Геймы: {row['games_won']}-{row['games_lost']}"
        )
    return "\n".join(lines)
