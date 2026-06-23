"""
Databricks SQL Connector with connection pooling and TTL-based caching.

Provides a managed connection to Databricks SQL Warehouse, including:
- Connection pooling with periodic health checks
- Automatic reconnection on stale/broken connections
- TTL-based query result caching
- Typed query execution returning pandas DataFrames
"""

import logging
import threading
import time
from typing import Any

import pandas as pd

from config.settings import AppConfig, DatabricksConfig

logger = logging.getLogger(__name__)


class _CacheEntry:
    """A single cached result with a creation timestamp."""

    __slots__ = ("data", "created_at")

    def __init__(self, data: Any) -> None:
        self.data = data
        self.created_at = time.monotonic()

    def is_expired(self, ttl_seconds: float) -> bool:
        """Return True if this entry is older than *ttl_seconds*."""
        return (time.monotonic() - self.created_at) >= ttl_seconds


class DatabricksConnector:
    """Thread-safe Databricks SQL connector with pooling and caching.

    Usage::

        connector = DatabricksConnector()
        df = connector.execute_query("SELECT * FROM funds LIMIT 10")
    """

    _instance: "DatabricksConnector | None" = None
    _lock = threading.Lock()

    # ------------------------------------------------------------------
    # Singleton accessor
    # ------------------------------------------------------------------
    @classmethod
    def get_instance(cls) -> "DatabricksConnector":
        """Return the singleton connector (creates one if needed)."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------
    def __init__(self) -> None:
        if not DatabricksConfig.is_configured():
            raise ConnectionError(
                "Databricks is not configured. "
                "Set DATABRICKS_HOST, DATABRICKS_TOKEN, and DATABRICKS_HTTP_PATH "
                "in your .env file or environment variables. "
                "Alternatively, run the app with APP_MODE=demo to use synthetic data."
            )

        self._host: str = DatabricksConfig.HOST
        self._token: str = DatabricksConfig.TOKEN
        self._http_path: str = DatabricksConfig.HTTP_PATH
        self._catalog: str = DatabricksConfig.CATALOG
        self._schema: str = DatabricksConfig.SCHEMA

        self._cache: dict[str, _CacheEntry] = {}
        self._cache_ttl: float = float(AppConfig.CACHE_TTL)
        self._conn_lock = threading.Lock()
        self._connection: Any = None

        logger.info(
            "DatabricksConnector initialised (host=%s, catalog=%s, schema=%s)",
            self._host,
            self._catalog or "<default>",
            self._schema or "<default>",
        )

    # ------------------------------------------------------------------
    # Connection management
    # ------------------------------------------------------------------
    def _connect(self) -> Any:
        """Create a fresh Databricks SQL connection."""
        try:
            from databricks import sql as dbsql  # type: ignore[import-untyped]
        except ImportError as exc:
            raise ImportError(
                "The 'databricks-sql-connector' package is required. "
                "Install it with: pip install databricks-sql-connector"
            ) from exc

        extra_kwargs: dict[str, str] = {}
        if self._catalog:
            extra_kwargs["catalog"] = self._catalog
        if self._schema:
            extra_kwargs["schema"] = self._schema

        conn = dbsql.connect(
            server_hostname=self._host,
            http_path=self._http_path,
            access_token=self._token,
            **extra_kwargs,
        )
        logger.info("Databricks connection established.")
        return conn

    def _get_connection(self) -> Any:
        """Return a healthy connection, reconnecting if necessary."""
        with self._conn_lock:
            if self._connection is None or not self._is_healthy():
                self._close_connection_unsafe()
                self._connection = self._connect()
            return self._connection

    def _is_healthy(self) -> bool:
        """Run a lightweight health-check on the current connection."""
        if self._connection is None:
            return False
        try:
            cursor = self._connection.cursor()
            cursor.execute("SELECT 1")
            cursor.fetchone()
            cursor.close()
            return True
        except Exception:
            logger.warning("Databricks connection health-check failed; will reconnect.")
            return False

    def _close_connection_unsafe(self) -> None:
        """Close the connection without acquiring *_conn_lock*."""
        if self._connection is not None:
            try:
                self._connection.close()
            except Exception:
                logger.debug("Ignored error while closing stale connection.", exc_info=True)
            self._connection = None

    def close(self) -> None:
        """Explicitly close the connection and flush the cache."""
        with self._conn_lock:
            self._close_connection_unsafe()
        self.clear_cache()
        logger.info("DatabricksConnector closed and cache cleared.")

    # ------------------------------------------------------------------
    # Cache helpers
    # ------------------------------------------------------------------
    def _cache_get(self, key: str) -> Any | None:
        """Return cached data for *key*, or ``None`` if missing/expired."""
        entry = self._cache.get(key)
        if entry is None:
            return None
        if entry.is_expired(self._cache_ttl):
            del self._cache[key]
            return None
        return entry.data

    def _cache_set(self, key: str, data: Any) -> None:
        self._cache[key] = _CacheEntry(data)

    def clear_cache(self) -> None:
        """Remove all cached results."""
        self._cache.clear()

    # ------------------------------------------------------------------
    # Query execution
    # ------------------------------------------------------------------
    def execute_query(self, sql: str, *, use_cache: bool = True) -> pd.DataFrame:
        """Execute *sql* and return the result as a DataFrame.

        Parameters
        ----------
        sql:
            A valid Databricks SQL statement.
        use_cache:
            When ``True`` (default), results are cached for ``CACHE_TTL`` seconds.

        Returns
        -------
        pd.DataFrame
            Query result set.  Empty DataFrame on zero rows.
        """
        cache_key = sql.strip()

        if use_cache:
            cached = self._cache_get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for query: %s…", cache_key[:80])
                return cached.copy()

        logger.info("Executing query: %s…", cache_key[:120])
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute(sql)
            columns = [desc[0] for desc in cursor.description] if cursor.description else []
            rows = cursor.fetchall()
            cursor.close()

            df = pd.DataFrame(rows, columns=columns) if columns else pd.DataFrame()
            if use_cache:
                self._cache_set(cache_key, df)
            return df

        except Exception as exc:
            logger.error("Query failed: %s", exc, exc_info=True)
            # Invalidate connection so next call will reconnect
            with self._conn_lock:
                self._close_connection_unsafe()
            raise

    # ------------------------------------------------------------------
    # Schema introspection helpers
    # ------------------------------------------------------------------
    def get_tables(self) -> list[str]:
        """Return a list of table names in the configured catalog/schema."""
        sql = "SHOW TABLES"
        if self._schema:
            sql += f" IN {self._schema}"
        df = self.execute_query(sql)
        # Databricks SHOW TABLES returns a column named 'tableName'
        for candidate in ("tableName", "table_name", "TABLE_NAME"):
            if candidate in df.columns:
                return df[candidate].tolist()
        # Fallback: return values from the first column
        if not df.empty:
            return df.iloc[:, 0].tolist()
        return []

    def get_table_schema(self, table: str) -> list[dict[str, str]]:
        """Return column metadata for *table*.

        Each dict contains ``name`` and ``type`` keys.
        """
        sql = f"DESCRIBE TABLE {table}"
        df = self.execute_query(sql, use_cache=True)

        name_col: str | None = None
        type_col: str | None = None

        for col in df.columns:
            lower = col.lower()
            if lower in ("col_name", "column_name", "name"):
                name_col = col
            elif lower in ("data_type", "type", "column_type"):
                type_col = col

        if name_col is None and not df.empty:
            name_col = df.columns[0]
        if type_col is None and len(df.columns) >= 2:
            type_col = df.columns[1]

        results: list[dict[str, str]] = []
        if name_col and type_col:
            for _, row in df.iterrows():
                col_name = str(row[name_col]).strip()
                # Skip partition/comment separator rows
                if col_name.startswith("#") or col_name == "":
                    continue
                results.append({"name": col_name, "type": str(row[type_col]).strip()})
        return results

    def fetch_table(self, table: str, limit: int | None = None) -> pd.DataFrame:
        """Fetch all rows (or up to *limit*) from *table*.

        Parameters
        ----------
        table:
            Fully-qualified or simple table name.
        limit:
            Optional row cap.  ``None`` fetches the entire table.
        """
        sql = f"SELECT * FROM {table}"
        if limit is not None and limit > 0:
            sql += f" LIMIT {limit}"
        return self.execute_query(sql)

    # ------------------------------------------------------------------
    # Repr
    # ------------------------------------------------------------------
    def __repr__(self) -> str:
        return (
            f"<DatabricksConnector host={self._host!r} "
            f"catalog={self._catalog!r} schema={self._schema!r}>"
        )
