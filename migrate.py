import os
import sys

from db import init_db


def main():
    """Run DB initialization using DATABASE_URL or local DB_PATH.

    Usage:
      python migrate.py
    """
    try:
        init_db()
        print("Database initialization completed.")
    except Exception as e:
        print("Migration failed:", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
