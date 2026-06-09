"""
Memory factory — the ONE file to edit when swapping backends.

To switch to Postgres: keep SQLiteMemoryBackend (it uses SQLAlchemy, just
change DATABASE_URL). To switch to Mem0 or Redis: implement MemoryBackend
and change the import/instantiation below.
"""
from sqlalchemy.orm import Session
from app.memory.base import MemoryBackend
from app.memory.sqlite_backend import SQLiteMemoryBackend


def get_memory_backend(db: Session) -> MemoryBackend:
    """Return the active memory backend, injected with a DB session."""
    return SQLiteMemoryBackend(db)
