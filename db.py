import sqlite3
from datetime import datetime
from typing import Optional, Sequence

import psycopg2
import psycopg2.extras

from config import DATABASE_URL, DB_PATH


def _is_postgres(db_path: Optional[str] = None) -> bool:
    return bool(DATABASE_URL and not db_path)


def _adapt_sql(connection, sql: str) -> str:
    if isinstance(connection, sqlite3.Connection):
        return sql.replace("%s", "?")
    return sql


def execute(connection, sql: str, params: Optional[Sequence] = None):
    params = params or ()
    sql = _adapt_sql(connection, sql)
    if isinstance(connection, sqlite3.Connection):
        cursor = connection.cursor()
        cursor.execute(sql, params)
        return cursor

    cursor = connection.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
    cursor.execute(sql, params)
    return cursor


def fetchone(connection, sql: str, params: Optional[Sequence] = None):
    return execute(connection, sql, params).fetchone()


def fetchall(connection, sql: str, params: Optional[Sequence] = None):
    return execute(connection, sql, params).fetchall()


def init_db(db_path: Optional[str] = None) -> None:
    connection = get_connection(db_path)
    if _is_postgres(db_path):
        players_pk = "SERIAL PRIMARY KEY"
        matches_pk = "SERIAL PRIMARY KEY"
    else:
        players_pk = "INTEGER PRIMARY KEY AUTOINCREMENT"
        matches_pk = "INTEGER PRIMARY KEY AUTOINCREMENT"

    execute(
        connection,
        f"""
        CREATE TABLE IF NOT EXISTS players (
            id {players_pk},
            name TEXT UNIQUE NOT NULL,
            wins INTEGER DEFAULT 0,
            losses INTEGER DEFAULT 0,
            sets_won INTEGER DEFAULT 0,
            sets_lost INTEGER DEFAULT 0,
            games_won INTEGER DEFAULT 0,
            games_lost INTEGER DEFAULT 0,
            created_at TEXT NOT NULL
        )
        """,
    )
    execute(
        connection,
        f"""
        CREATE TABLE IF NOT EXISTS matches (
            id {matches_pk},
            winner_id INTEGER NOT NULL,
            loser_id INTEGER NOT NULL,
            score TEXT NOT NULL,
            reported_by TEXT NOT NULL,
            reported_at TEXT NOT NULL,
            FOREIGN KEY (winner_id) REFERENCES players(id),
            FOREIGN KEY (loser_id) REFERENCES players(id)
        )
        """,
    )
    connection.commit()
    connection.close()


def get_connection(db_path: Optional[str] = None):
    if DATABASE_URL and not db_path:
        return psycopg2.connect(DATABASE_URL)

    target_path = db_path or DB_PATH
    connection = sqlite3.connect(target_path)
    connection.row_factory = sqlite3.Row
    return connection


def utc_now() -> str:
    return datetime.utcnow().isoformat()


def get_player_by_name(connection, name: str) -> Optional[sqlite3.Row]:
    return fetchone(
        connection,
        "SELECT id FROM players WHERE lower(name) = lower(%s)",
        (name,),
    )
