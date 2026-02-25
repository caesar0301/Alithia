"""
Storage backend factory for automatic selection and fallback.
"""

from typing import Any, Dict, Optional

from noesium.core.utils import get_logger

from .base import StorageBackend
from .sqlite import SQLiteStorage
from .supabase import SupabaseStorage

logger = get_logger(__name__)


def get_storage_backend(config: Dict[str, Any]) -> StorageBackend:
    """
    Get appropriate storage backend based on configuration.

    Tries Supabase first (if configured), falls back to SQLite if:
    - Supabase is not configured
    - Supabase connection fails and fallback_to_sqlite is True
    - Supabase is explicitly disabled

    Args:
        config: Configuration dictionary containing:
            - storage.backend: "supabase" or "sqlite"
            - storage.fallback_to_sqlite: bool (default: True)
            - storage.sqlite_path: path for SQLite DB
            - storage.user_id: user identifier
            - supabase.url: Supabase project URL
            - supabase.anon_key or supabase.service_role_key: API key

    Returns:
        Connected storage backend instance

    Raises:
        RuntimeError: If no storage backend can be initialized
    """
    storage_config = config.get("storage", {})
    backend_type = storage_config.get("backend", "supabase")
    fallback_to_sqlite = storage_config.get("fallback_to_sqlite", True)
    sqlite_path = storage_config.get("sqlite_path", "data/alithia.db")

    # Try Supabase first if configured
    if backend_type == "supabase":
        supabase_config = config.get("supabase", {})
        url = supabase_config.get("url")
        # Prefer service_role_key for full access, fallback to anon_key
        key = supabase_config.get("service_role_key") or supabase_config.get("anon_key")

        if url and key:
            try:
                logger.info("Attempting to initialize Supabase storage backend...")
                backend = SupabaseStorage(url, key)
                backend.connect()

                if backend.test_connection():
                    logger.info("Successfully connected to Supabase")
                    return backend
                else:
                    logger.warning("Supabase connection test failed")
                    if not fallback_to_sqlite:
                        raise RuntimeError("Supabase connection failed and fallback is disabled")

            except Exception as e:
                logger.warning(f"Failed to initialize Supabase storage: {e}")
                if not fallback_to_sqlite:
                    raise RuntimeError(f"Supabase initialization failed: {e}")
        else:
            logger.warning("Supabase credentials not provided in config")
            if not fallback_to_sqlite:
                raise RuntimeError("Supabase not configured and fallback is disabled")

    # Fallback to SQLite (or use it as primary if specified)
    if backend_type == "sqlite" or fallback_to_sqlite:
        try:
            logger.info(f"Initializing SQLite storage backend at {sqlite_path}...")
            backend = SQLiteStorage(sqlite_path)
            backend.connect()

            if backend.test_connection():
                logger.info("Successfully connected to SQLite")
                return backend
            else:
                raise RuntimeError("SQLite connection test failed")

        except Exception as e:
            logger.error(f"Failed to initialize SQLite storage: {e}")
            raise RuntimeError(f"SQLite initialization failed: {e}")

    raise RuntimeError("No storage backend could be initialized")


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
