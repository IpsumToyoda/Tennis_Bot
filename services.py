import re
import logging
from typing import List, Tuple, Dict, Any, Optional
from config import use_external_db

from db import execute, fetchall, fetchone, get_connection, get_player_by_name, utc_now


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
    parts = re.split(r"\s+", score_text)
    if not 1 <= len(parts) <= 3:
        raise ValueError("Укажите от 1 до 3 сетов, например 6:3 7:5")

    parsed = []
    for part in parts:
        match = re.fullmatch(r"(\d+)\s*[:\-]\s*(\d+)", part)
        if not match:
            raise ValueError("Формат счета: 6:3 7:5")
        first, second = (int(value) for value in match.groups())
        if not ((first == 6 and 0 <= second <= 4) or
                (first == 7 and second in (5, 6))):
            raise ValueError("Допустимы сеты 6:0-6:4, 7:5 или 7:6")
        parsed.append((first, second))

    required_sets = len(parsed) // 2 + 1
    if sum(first > second for first, second in parsed) != required_sets:
        raise ValueError("Победитель должен выиграть большинство сетов")
    return parsed


def add_match_result(winner_name: str, loser_name: str, score_text: str, reported_by: str, db_path: Optional[str] = None) -> str:
    connection = get_connection(db_path)
    try:
        status = fetchone(connection, "SELECT status FROM tournament_state WHERE id = 1")
        if not status or status["status"] != "active":
            raise ValueError("Сначала начните турнир командой /start_tournament")

        score_pairs = parse_score(score_text)
        winner_id = ensure_player(connection, winner_name)
        loser_id = ensure_player(connection, loser_name)
        if winner_id == loser_id:
            raise ValueError("Победитель и проигравший не могут быть одним и тем же игроком")

        sets_won = sum(first > second for first, second in score_pairs)
        sets_lost = len(score_pairs) - sets_won
        games_won = sum(first for first, _ in score_pairs)
        games_lost = sum(second for _, second in score_pairs)

        execute(connection, """
            UPDATE players SET wins = wins + 1, sets_won = sets_won + %s,
            sets_lost = sets_lost + %s, games_won = games_won + %s,
            games_lost = games_lost + %s WHERE id = %s
        """, (sets_won, sets_lost, games_won, games_lost, winner_id))
        execute(connection, """
            UPDATE players SET losses = losses + 1, sets_won = sets_won + %s,
            sets_lost = sets_lost + %s, games_won = games_won + %s,
            games_lost = games_lost + %s WHERE id = %s
        """, (sets_lost, sets_won, games_lost, games_won, loser_id))
        execute(connection, """
            INSERT INTO matches (winner_id, loser_id, score, reported_by, reported_at)
            VALUES (%s, %s, %s, %s, %s)
        """, (winner_id, loser_id, score_text, reported_by, utc_now()))
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()

    return f"{winner_name} победил {loser_name} со счётом {score_text}"


def start_tournament(db_path: Optional[str] = None) -> str:
    connection = get_connection(db_path)
    try:
        player_count = fetchone(connection, "SELECT COUNT(*) AS count FROM players")["count"]
        if player_count < 2:
            raise ValueError("Для старта турнира нужно минимум 2 игрока")
        if fetchone(connection, "SELECT status FROM tournament_state WHERE id = 1")["status"] == "active":
            return "Турнир уже активен"
        execute(connection, "UPDATE tournament_state SET status = %s, started_at = %s WHERE id = 1", ("active", utc_now()))
        connection.commit()
        return "Турнир начат. Можно вводить результаты матчей."
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def finish_tournament(db_path: Optional[str] = None) -> str:
    connection = get_connection(db_path)
    try:
        status = fetchone(connection, "SELECT status FROM tournament_state WHERE id = 1")
        if not status or status["status"] != "active":
            return "Турнир уже завершен"
        execute(connection, "UPDATE tournament_state SET status = %s WHERE id = 1", ("inactive",))
        connection.commit()
        return "Турнир завершен. Новые результаты больше не принимаются."
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def delete_all_players(db_path: Optional[str] = None) -> str:
    connection = get_connection(db_path)
    try:
        execute(connection, "DELETE FROM matches")
        execute(connection, "DELETE FROM players")
        execute(connection, "UPDATE tournament_state SET status = %s, started_at = NULL WHERE id = 1", ("inactive",))
        connection.commit()
        return "Все участники и результаты удалены. Турнир сброшен."
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def get_tournament_status(db_path: Optional[str] = None) -> str:
    connection = get_connection(db_path)
    row = fetchone(connection, "SELECT status FROM tournament_state WHERE id = 1")
    connection.close()
    if not row:
        return "inactive"
    return row["status"]


def get_standings(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    connection = get_connection(db_path)
    try:
        return fetchall(connection, """
            SELECT id, name, wins, losses, sets_won, sets_lost, games_won, games_lost
            FROM players
            ORDER BY wins DESC, losses ASC, (sets_won - sets_lost) DESC,
            (games_won - games_lost) DESC, name ASC
        """)
    finally:
        connection.close()


def get_player_stats(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    connection = get_connection(db_path)
    try:
        return fetchall(connection, """
            SELECT name, wins, losses, sets_won, sets_lost, games_won, games_lost
            FROM players
            ORDER BY wins DESC, losses ASC, name ASC
        """)
    finally:
        connection.close()


def get_player_names(db_path: Optional[str] = None) -> List[str]:
    logging.info(f"get_player_names: use_external_db={use_external_db()} db_path={db_path}")
    connection = get_connection(db_path)
    try:
        rows = fetchall(connection, "SELECT name FROM players ORDER BY name ASC")
    finally:
        connection.close()
    logging.info(f"get_player_names: found={len(rows)}")
    return [row["name"] for row in rows]


def format_table(db_path: Optional[str] = None) -> str:
    logging.info(f"format_table: use_external_db={use_external_db()} db_path={db_path}")
    rows = get_standings(db_path)
    logging.info(f"format_table: rows={len(rows)}")
    if not rows:
        return "Таблица пока пустая. Добавьте игроков командой /register_player"

    lines = ["Турнирная таблица:"]
    for index, row in enumerate(rows, start=1):
        lines.append(
            f"{index}. {row['name']} | В-П: {row['wins']}-{row['losses']} | Сеты: {row['sets_won']}-{row['sets_lost']} | Геймы: {row['games_won']}-{row['games_lost']}"
        )
    return "\n".join(lines)
