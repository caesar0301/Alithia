"""
Storage backend for Alithia agents.

Provides persistent storage for caching, deduplication, and query history.
"""

from .base import StorageBackend
from .factory import get_storage_backend
from .postgres import PostgresStorage
from .sqlite import SQLiteStorage
from .supabase import SupabaseStorage

__all__ = [
    "StorageBackend",
    "PostgresStorage",
    "SQLiteStorage",
    "SupabaseStorage",
    "get_storage_backend",
]
