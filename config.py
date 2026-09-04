import os
from typing import List

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")
DB_PATH = os.getenv("DB_PATH", "tournament.db")
DATABASE_URL = os.getenv("DATABASE_URL", "")
ALLOWED_JUDGES = [
    int(item.strip())
    for item in os.getenv("ALLOWED_JUDGES", "").split(",")
    if item.strip()
]


def get_allowed_judges() -> List[int]:
    return ALLOWED_JUDGES.copy()


def is_allowed_judge(user_id: int) -> bool:
    return bool(ALLOWED_JUDGES) and user_id in ALLOWED_JUDGES


def use_external_db() -> bool:
    return bool(DATABASE_URL)
