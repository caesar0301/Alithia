"""
Storage backend factory for automatic selection and fallback.
"""

import os
from typing import Any, Dict, Optional

from noesium.core.utils import get_logger

from .base import StorageBackend
from .sqlite import SQLiteStorage
from .supabase import SupabaseStorage

logger = get_logger(__name__)


def _try_postgres(config: Dict[str, Any]) -> Optional[StorageBackend]:
    """Attempt to create a PostgreSQL backend from config or environment."""
    from .postgres import PostgresStorage

    storage_config = config.get("storage", {})
    pg_config = storage_config.get("postgres", {}) or config.get("postgres", {})
    dsn = storage_config.get("postgres_dsn") or pg_config.get("dsn") or os.environ.get("ALITHIA_POSTGRES_DSN")
    if not dsn:
        host = pg_config.get("host") or os.environ.get("PGHOST")
        port = pg_config.get("port") or os.environ.get("PGPORT", "5432")
        user = pg_config.get("user") or os.environ.get("PGUSER")
        password = pg_config.get("password") or os.environ.get("PGPASSWORD")
        db = pg_config.get("database") or os.environ.get("PGDATABASE")
        if host and user and db:
            pw_part = f":{password}" if password else ""
            dsn = f"postgresql://{user}{pw_part}@{host}:{port}/{db}"
    if not dsn:
        return None

    try:
        logger.info("Attempting to initialize PostgreSQL storage backend...")
        backend = PostgresStorage(dsn)
        backend.connect()
        if backend.test_connection():
            logger.info("Successfully connected to PostgreSQL")
            return backend
        else:
            logger.warning("PostgreSQL connection test failed")
    except Exception as e:
        logger.warning(f"Failed to initialize PostgreSQL storage: {e}")
    return None


def _try_supabase(config: Dict[str, Any]) -> Optional[StorageBackend]:
    """Attempt to create a Supabase backend from config."""
    storage_config = config.get("storage", {})
    supabase_config = storage_config.get("supabase", {}) or config.get("supabase", {})
    url = supabase_config.get("url")
    key = supabase_config.get("service_role_key") or supabase_config.get("anon_key")

    if not url or not key:
        logger.warning("Supabase credentials not provided in config")
        return None

    try:
        logger.info("Attempting to initialize Supabase storage backend...")
        backend = SupabaseStorage(url, key)
        backend.connect()
        if backend.test_connection():
            logger.info("Successfully connected to Supabase")
            return backend
        else:
            logger.warning("Supabase connection test failed")
    except Exception as e:
        logger.warning(f"Failed to initialize Supabase storage: {e}")
    return None


def _init_sqlite(sqlite_path: str) -> StorageBackend:
    """Initialize SQLite backend, raising on failure."""
    logger.info(f"Initializing SQLite storage backend at {sqlite_path}...")
    backend = SQLiteStorage(sqlite_path)
    backend.connect()
    if backend.test_connection():
        logger.info("Successfully connected to SQLite")
        return backend
    raise RuntimeError("SQLite connection test failed")


def get_storage_backend(config: Dict[str, Any]) -> StorageBackend:
    """
    Get the storage backend specified by ``storage.backend``.

    Only the configured backend is attempted.  If it fails and
    ``fallback_to_sqlite`` is ``True`` (default), SQLite is used instead.

    Args:
        config: Configuration dictionary containing:
            - storage.backend: "postgres", "supabase", or "sqlite"
            - storage.fallback_to_sqlite: bool (default: True)
            - storage.sqlite_path: path for SQLite DB
            - storage.postgres_dsn: PostgreSQL DSN (alternative)
            - storage.postgres.dsn / postgres.host / postgres.user / ...: PostgreSQL config
            - storage.supabase.url: Supabase project URL
            - storage.supabase.anon_key or storage.supabase.service_role_key: API key

    Returns:
        Connected storage backend instance

    Raises:
        RuntimeError: If no storage backend can be initialized
    """
    storage_config = config.get("storage", {})
    backend_type = storage_config.get("backend", "sqlite")
    fallback_to_sqlite = storage_config.get("fallback_to_sqlite", True)
    sqlite_path = storage_config.get("sqlite_path", "data/alithia.db")

    if backend_type == "sqlite":
        try:
            return _init_sqlite(sqlite_path)
        except Exception as e:
            raise RuntimeError(f"SQLite initialization failed: {e}") from e

    if backend_type == "postgres":
        backend = _try_postgres(config)
        if backend:
            return backend
        if not fallback_to_sqlite:
            raise RuntimeError("PostgreSQL not available and fallback is disabled")
        logger.warning("PostgreSQL not available, falling back to SQLite...")
        try:
            return _init_sqlite(sqlite_path)
        except Exception as e:
            raise RuntimeError(f"SQLite fallback failed: {e}") from e

    if backend_type == "supabase":
        backend = _try_supabase(config)
        if backend:
            return backend
        if not fallback_to_sqlite:
            raise RuntimeError("Supabase not available and fallback is disabled")
        logger.warning("Supabase not available, falling back to SQLite...")
        try:
            return _init_sqlite(sqlite_path)
        except Exception as e:
            raise RuntimeError(f"SQLite fallback failed: {e}") from e

    raise RuntimeError(f"Unknown storage backend: {backend_type!r}. Use 'postgres', 'supabase', or 'sqlite'.")


def create_storage_with_fallback(
    supabase_url: Optional[str] = None,
    supabase_key: Optional[str] = None,
    sqlite_path: str = "data/alithia.db",
    prefer_supabase: bool = True,
) -> StorageBackend:
    """
    Create storage backend with automatic fallback (convenience function).

    Args:
        supabase_url: Supabase project URL (optional)
        supabase_key: Supabase API key (optional)
        sqlite_path: Path to SQLite database file
        prefer_supabase: Try Supabase first if credentials provided

    Returns:
        Connected storage backend instance
    """
    # Try Supabase if credentials provided and preferred
    if prefer_supabase and supabase_url and supabase_key:
        try:
            logger.info("Attempting to connect to Supabase...")
            backend = SupabaseStorage(supabase_url, supabase_key)
            backend.connect()
            if backend.test_connection():
                logger.info("Connected to Supabase successfully")
                return backend
        except Exception as e:
            logger.warning(f"Supabase connection failed: {e}, falling back to SQLite")

    # Fallback to SQLite
    logger.info(f"Using SQLite storage at {sqlite_path}")
    backend = SQLiteStorage(sqlite_path)
    backend.connect()
    return backend
