from __future__ import annotations

import shelve
from typing import Any

CACHE_PATH = "tmp/shelve"


def get(key: str) -> Any | None:
    with shelve.open(CACHE_PATH) as db:
        if key in db:
            return db[key]
        else:
            return None


def create(key: str, obj: Any) -> None:
    with shelve.open(CACHE_PATH) as db:
        db[key] = obj
