"""
Dynamic schema discovery and DataFrame profiling engine.

Works on any arbitrary pandas DataFrame – no fixed schema required.
Profiles every column to determine type, cardinality, nullness, range,
and sample values so that downstream components (ColumnMapper, charts,
AI prompts) can adapt automatically.
"""

import logging
from datetime import datetime
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

# Type constants used throughout the engine
DTYPE_NUMERIC = "numeric"
DTYPE_STRING = "string"
DTYPE_DATE = "date"
DTYPE_BOOLEAN = "boolean"

# Thresholds for heuristic classification
_CATEGORICAL_MAX_UNIQUE_RATIO = 0.05  # ≤5 % unique values ⇒ categorical
_CATEGORICAL_MAX_UNIQUE_ABS = 30      # or ≤30 distinct values


class SchemaEngine:
    """Analyse and profile the schema of any pandas DataFrame.

    The engine is stateless – every public method accepts a DataFrame
    and returns fresh results.  No Databricks dependency is required;
    a ``DatabricksConnector`` can optionally be stored for convenience
    so callers can say ``engine.fetch_and_profile("table")``.

    Parameters
    ----------
    connector:
        Optional :class:`DatabricksConnector` for live table access.
    """

    def __init__(self, connector: Any | None = None) -> None:
        self._connector = connector

    # ------------------------------------------------------------------
    # Core column-type detection
    # ------------------------------------------------------------------
    @staticmethod
    def detect_column_type(series: pd.Series) -> str:
        """Classify *series* into one of the four canonical types.

        Detection order:
        1. Boolean  – if the non-null values are all ``True``/``False``.
        2. Date     – if dtype is datetime64 or most values parse as dates.
        3. Numeric  – if dtype is numeric or most values coerce to float.
        4. String   – fallback.

        Returns
        -------
        str
            One of ``'numeric'``, ``'string'``, ``'date'``, ``'boolean'``.
        """
        if series.dropna().empty:
            return DTYPE_STRING

        non_null = series.dropna()

        # --- Boolean ---
        if pd.api.types.is_bool_dtype(series):
            return DTYPE_BOOLEAN
        unique_lower = {str(v).strip().lower() for v in non_null.unique()}
        if unique_lower <= {"true", "false", "1", "0", "yes", "no"}:
            return DTYPE_BOOLEAN

        # --- Date ---
        if pd.api.types.is_datetime64_any_dtype(series):
            return DTYPE_DATE
        if series.dtype == object:
            sample = non_null.head(20)
            parsed = 0
            for val in sample:
                try:
                    datetime.fromisoformat(str(val).replace("Z", "+00:00"))
                    parsed += 1
                except (ValueError, TypeError):
                    try:
                        pd.Timestamp(val)
                        parsed += 1
                    except Exception:
                        pass
            if parsed >= len(sample) * 0.8:
                return DTYPE_DATE

        # --- Numeric ---
        if pd.api.types.is_numeric_dtype(series):
            return DTYPE_NUMERIC
        if series.dtype == object:
            coerced = pd.to_numeric(non_null, errors="coerce")
            if coerced.notna().sum() >= len(non_null) * 0.8:
                return DTYPE_NUMERIC

        return DTYPE_STRING

    # ------------------------------------------------------------------
    # Categorical heuristic
    # ------------------------------------------------------------------
    @staticmethod
    def _is_categorical(series: pd.Series) -> bool:
        """Heuristic: is *series* best treated as a categorical variable?"""
        if series.dropna().empty:
            return False
        n_unique = series.nunique()
        n_rows = len(series)
        if n_unique <= _CATEGORICAL_MAX_UNIQUE_ABS:
            return True
        if n_rows > 0 and (n_unique / n_rows) <= _CATEGORICAL_MAX_UNIQUE_RATIO:
            return True
        return False

    # ------------------------------------------------------------------
    # Column-level profiling
    # ------------------------------------------------------------------
    def _profile_column(self, series: pd.Series) -> dict[str, Any]:
        """Build a profile dict for a single column."""
        col_type = self.detect_column_type(series)
        non_null = series.dropna()
        n_total = len(series)

        profile: dict[str, Any] = {
            "name": series.name,
            "dtype": str(series.dtype),
            "detected_type": col_type,
            "is_numeric": col_type == DTYPE_NUMERIC,
            "is_categorical": self._is_categorical(series),
            "is_date": col_type == DTYPE_DATE,
            "is_boolean": col_type == DTYPE_BOOLEAN,
            "unique_count": int(series.nunique()),
            "null_count": int(series.isna().sum()),
            "null_pct": round(series.isna().sum() / n_total * 100, 2) if n_total > 0 else 0.0,
            "sample_values": [_safe_native(v) for v in non_null.head(5).tolist()],
        }

        # Range / stats depending on type
        if col_type == DTYPE_NUMERIC:
            numeric_vals = pd.to_numeric(non_null, errors="coerce").dropna()
            if not numeric_vals.empty:
                profile["min_val"] = _safe_native(numeric_vals.min())
                profile["max_val"] = _safe_native(numeric_vals.max())
                profile["mean_val"] = round(float(numeric_vals.mean()), 4)
                profile["median_val"] = round(float(numeric_vals.median()), 4)
                profile["std_val"] = round(float(numeric_vals.std()), 4) if len(numeric_vals) > 1 else 0.0
            else:
                profile["min_val"] = None
                profile["max_val"] = None
                profile["mean_val"] = None
                profile["median_val"] = None
                profile["std_val"] = None

        elif col_type == DTYPE_DATE:
            try:
                dt_vals = pd.to_datetime(non_null, errors="coerce").dropna()
                if not dt_vals.empty:
                    profile["min_val"] = str(dt_vals.min())
                    profile["max_val"] = str(dt_vals.max())
                else:
                    profile["min_val"] = None
                    profile["max_val"] = None
            except Exception:
                profile["min_val"] = None
                profile["max_val"] = None
        else:
            if not non_null.empty:
                profile["min_val"] = str(non_null.min())
                profile["max_val"] = str(non_null.max())
            else:
                profile["min_val"] = None
                profile["max_val"] = None

        return profile

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def discover_schema(self, df: pd.DataFrame) -> dict[str, dict[str, Any]]:
        """Profile every column in *df*.

        Returns
        -------
        dict[str, dict]
            ``{column_name: profile_dict}`` where each *profile_dict*
            contains keys such as ``name``, ``dtype``, ``is_numeric``,
            ``is_categorical``, ``is_date``, ``unique_count``,
            ``null_pct``, ``min_val``, ``max_val``, ``sample_values``.
        """
        schema: dict[str, dict[str, Any]] = {}
        for col in df.columns:
            schema[col] = self._profile_column(df[col])
        logger.info(
            "Schema discovered: %d columns (%d numeric, %d categorical, %d date)",
            len(schema),
            sum(1 for p in schema.values() if p["is_numeric"]),
            sum(1 for p in schema.values() if p["is_categorical"]),
            sum(1 for p in schema.values() if p["is_date"]),
        )
        return schema

    def get_numeric_columns(self, df: pd.DataFrame) -> list[str]:
        """Return names of all numeric columns."""
        return [
            col for col in df.columns
            if self.detect_column_type(df[col]) == DTYPE_NUMERIC
        ]

    def get_categorical_columns(self, df: pd.DataFrame) -> list[str]:
        """Return names of columns detected as categorical."""
        return [
            col for col in df.columns
            if self._is_categorical(df[col])
        ]

    def get_date_columns(self, df: pd.DataFrame) -> list[str]:
        """Return names of all date/datetime columns."""
        return [
            col for col in df.columns
            if self.detect_column_type(df[col]) == DTYPE_DATE
        ]

    def profile_dataframe(self, df: pd.DataFrame) -> dict[str, Any]:
        """Return a comprehensive profile of the whole DataFrame.

        Includes per-column profiles plus aggregate statistics such as
        row count, column count, memory usage, and duplicate-row count.
        """
        column_profiles = self.discover_schema(df)
        memory_bytes = int(df.memory_usage(deep=True).sum())

        type_counts: dict[str, int] = {}
        for p in column_profiles.values():
            t = p["detected_type"]
            type_counts[t] = type_counts.get(t, 0) + 1

        profile: dict[str, Any] = {
            "row_count": len(df),
            "column_count": len(df.columns),
            "memory_bytes": memory_bytes,
            "memory_mb": round(memory_bytes / (1024 * 1024), 2),
            "duplicate_rows": int(df.duplicated().sum()),
            "total_nulls": int(df.isna().sum().sum()),
            "null_pct_overall": round(
                df.isna().sum().sum() / (len(df) * len(df.columns)) * 100, 2
            ) if len(df) > 0 and len(df.columns) > 0 else 0.0,
            "type_counts": type_counts,
            "columns": column_profiles,
        }
        return profile

    # ------------------------------------------------------------------
    # Convenience: fetch & profile directly from Databricks
    # ------------------------------------------------------------------
    def fetch_and_profile(
        self,
        table: str,
        limit: int | None = None,
    ) -> tuple[pd.DataFrame, dict[str, Any]]:
        """Fetch *table* via the connector and return ``(df, profile)``.

        Raises ``RuntimeError`` if no connector was provided at init.
        """
        if self._connector is None:
            raise RuntimeError(
                "No DatabricksConnector available. "
                "Pass one at construction time or call profile_dataframe(df) directly."
            )
        df = self._connector.fetch_table(table, limit=limit)
        profile = self.profile_dataframe(df)
        return df, profile


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------

def _safe_native(val: Any) -> Any:
    """Convert numpy scalars to Python-native types for JSON safety."""
    if isinstance(val, (np.integer,)):
        return int(val)
    if isinstance(val, (np.floating,)):
        return float(val)
    if isinstance(val, (np.bool_,)):
        return bool(val)
    if isinstance(val, (pd.Timestamp, np.datetime64)):
        return str(val)
    return val
