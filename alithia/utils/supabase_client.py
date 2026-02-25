"""
Supabase client utilities for Alithia.

This module provides connection management and helper functions for Supabase operations.
"""

import time
from typing import Any, Dict, List, Optional

from noesium.core.utils import get_logger
from supabase import Client, create_client

logger = get_logger(__name__)


class SupabaseClientManager:
    """Manages Supabase connections with retry logic and connection pooling."""

    def __init__(self, url: str, key: str, max_retries: int = 3, retry_delay: float = 1.0):
        """
        Initialize Supabase client manager.

        Args:
            url: Supabase project URL
            key: Supabase API key (anon_key or service_role_key)
            max_retries: Maximum number of retry attempts
            retry_delay: Delay between retries in seconds
        """
        self.url = url
        self.key = key
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._client: Optional[Client] = None

    @property
    def client(self) -> Client:
        """Get or create Supabase client."""
        if self._client is None:
            self._client = create_client(self.url, self.key)
        return self._client

    def _retry_operation(self, operation, operation_name: str):
        """
        Retry an operation with exponential backoff.

        Args:
            operation: Function to execute
            operation_name: Name for logging

        Returns:
            Result of the operation

        Raises:
            Exception: If all retries fail
        """
        last_error = None
        for attempt in range(self.max_retries):
            try:
                result = operation()
                return result
            except Exception as e:
                last_error = e
                if attempt < self.max_retries - 1:
                    wait_time = self.retry_delay * (2**attempt)
                    logger.warning(
                        f"{operation_name} failed (attempt {attempt + 1}/{self.max_retries}): {e}. "
                        f"Retrying in {wait_time}s..."
                    )
                    time.sleep(wait_time)
                else:
                    logger.error(f"{operation_name} failed after {self.max_retries} attempts: {e}")

        raise last_error

    def insert_record(self, table: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Insert a single record into a table.

        Args:
            table: Table name
            data: Record data as dictionary

        Returns:
            Inserted record with generated fields

        Raises:
            Exception: If insert fails after all retries
        """

        def _insert():
            response = self.client.table(table).insert(data).execute()
            if response.data:
                logger.debug(f"Inserted record into {table}: {data.get('id', 'unknown')}")
                return response.data[0] if response.data else data
            raise ValueError(f"Insert failed: no data returned")

        return self._retry_operation(_insert, f"Insert into {table}")

    def insert_records(self, table: str, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Insert multiple records into a table.

        Args:
            table: Table name
            data: List of record dictionaries

        Returns:
            List of inserted records

        Raises:
            Exception: If insert fails after all retries
        """

        def _insert():
            response = self.client.table(table).insert(data).execute()
            if response.data:
                logger.debug(f"Inserted {len(data)} records into {table}")
                return response.data
            raise ValueError(f"Batch insert failed: no data returned")

        return self._retry_operation(_insert, f"Batch insert into {table}")

    def update_record(self, table: str, record_id: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a record by ID.

        Args:
            table: Table name
            record_id: Record ID
            data: Updated fields

        Returns:
            Updated record

        Raises:
            Exception: If update fails after all retries
        """

        def _update():
            response = self.client.table(table).update(data).eq("id", record_id).execute()
            if response.data:
                logger.debug(f"Updated record in {table}: {record_id}")
                return response.data[0] if response.data else data
            raise ValueError(f"Update failed: no data returned")

        return self._retry_operation(_update, f"Update {table}/{record_id}")

    def upsert_record(
        self, table: str, data: Dict[str, Any], conflict_columns: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Insert or update a record based on conflict columns.

        Args:
            table: Table name
            data: Record data
            conflict_columns: Columns to check for conflicts (None = use table's unique constraints)

        Returns:
            Upserted record

        Raises:
            Exception: If upsert fails after all retries
        """

        def _upsert():
            query = self.client.table(table).upsert(data)
            if conflict_columns:
                query = query.on_conflict(",".join(conflict_columns))
            response = query.execute()
            if response.data:
                logger.debug(f"Upserted record into {table}")
                return response.data[0] if response.data else data
            raise ValueError(f"Upsert failed: no data returned")

        return self._retry_operation(_upsert, f"Upsert into {table}")

    def upsert_records(
        self, table: str, data: List[Dict[str, Any]], conflict_columns: Optional[List[str]] = None
    ) -> List[Dict[str, Any]]:
        """
        Insert or update multiple records based on conflict columns.

        Args:
            table: Table name
            data: List of record dictionaries
            conflict_columns: Columns to check for conflicts

        Returns:
            List of upserted records

        Raises:
            Exception: If upsert fails after all retries
        """

        def _upsert():
            query = self.client.table(table).upsert(data)
            if conflict_columns:
                query = query.on_conflict(",".join(conflict_columns))
            response = query.execute()
            if response.data:
                logger.debug(f"Upserted {len(data)} records into {table}")
                return response.data
            raise ValueError(f"Batch upsert failed: no data returned")

        return self._retry_operation(_upsert, f"Batch upsert into {table}")

    def query_records(
        self,
        table: str,
        filters: Optional[Dict[str, Any]] = None,
        order_by: Optional[str] = None,
        limit: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        """
        Query records from a table with filters.

        Args:
            table: Table name
            filters: Dictionary of column: value filters (equality only)
            order_by: Column name to order by (prefix with - for descending)
            limit: Maximum number of records to return

        Returns:
            List of matching records

        Raises:
            Exception: If query fails after all retries
        """

        def _query():
            query = self.client.table(table).select("*")

            if filters:
                for key, value in filters.items():
                    query = query.eq(key, value)

            if order_by:
                if order_by.startswith("-"):
                    query = query.order(order_by[1:], desc=True)
                else:
                    query = query.order(order_by)

            if limit:
                query = query.limit(limit)

            response = query.execute()
            logger.debug(f"Queried {table}: {len(response.data) if response.data else 0} results")
            return response.data if response.data else []

        return self._retry_operation(_query, f"Query {table}")

    def delete_record(self, table: str, record_id: str) -> bool:
        """
        Delete a record by ID.

        Args:
            table: Table name
            record_id: Record ID

        Returns:
            True if deleted successfully

        Raises:
            Exception: If delete fails after all retries
        """

        def _delete():
            self.client.table(table).delete().eq("id", record_id).execute()
            logger.debug(f"Deleted record from {table}: {record_id}")
            return True

        return self._retry_operation(_delete, f"Delete {table}/{record_id}")

    def execute_raw_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> Any:
        """
        Execute a raw SQL query (for advanced operations).

        Args:
            query: SQL query string
            params: Query parameters

        Returns:
            Query results

        Raises:
            Exception: If query fails after all retries
        """

        def _execute():
            response = self.client.rpc("execute_sql", {"query": query, "params": params or {}}).execute()
            logger.debug(f"Executed raw query")
            return response.data if response.data else []

        return self._retry_operation(_execute, "Raw query execution")

    def test_connection(self) -> bool:
        """
        Test if the connection to Supabase is working.

        Returns:
            True if connection is successful, False otherwise
        """
        try:
            # Try a simple query to check connection
            self.client.table("_health_check").select("*").limit(1).execute()
            return True
        except Exception as e:
            logger.warning(f"Supabase connection test failed: {e}")
            return False
