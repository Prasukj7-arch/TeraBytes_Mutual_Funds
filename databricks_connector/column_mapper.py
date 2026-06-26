"""
Semantic column mapper for heterogeneous mutual-fund data sources.

Maps arbitrary DataFrame column names to canonical names defined in
:pymod:`config.column_mappings`.  The matching pipeline applies four
strategies in priority order:

1. **Exact match** – case-insensitive comparison against known aliases.
2. **Fuzzy match** – token-sort-ratio via *thefuzz* (threshold 80).
3. **Keyword match** – substring check for registered keywords.
4. **Type-based inference** – picks the best unmatched canonical name
   whose expected type matches the actual column type.
"""

import logging
from typing import Any

import pandas as pd

from config.column_mappings import COLUMN_DEFINITIONS, COLUMN_GROUPS
from databricks_connector.schema_engine import SchemaEngine

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Fuzzy-matching backend: prefer thefuzz, fall back to difflib
# ---------------------------------------------------------------------------
_USE_THEFUZZ: bool
try:
    from thefuzz import fuzz as _fuzz  # type: ignore[import-untyped]
    _USE_THEFUZZ = True
except ImportError:
    _USE_THEFUZZ = False
    import difflib

_FUZZY_THRESHOLD = 80  # minimum score (0-100) to accept a fuzzy match


def _fuzzy_ratio(a: str, b: str) -> int:
    """Return a 0-100 similarity score between two strings."""
    if _USE_THEFUZZ:
        return int(_fuzz.token_sort_ratio(a, b))
    # difflib SequenceMatcher returns 0.0-1.0
    return int(difflib.SequenceMatcher(None, a.lower(), b.lower()).ratio() * 100)


class ColumnMapper:
    """Map arbitrary column names to canonical names using multi-strategy matching.

    Parameters
    ----------
    schema_engine:
        Optional :class:`SchemaEngine` used for type-based inference.
        One is created automatically if omitted.
    """

    def __init__(self, schema_engine: SchemaEngine | None = None) -> None:
        self._engine = schema_engine or SchemaEngine()
        self._definitions: dict[str, dict[str, Any]] = COLUMN_DEFINITIONS

    # ------------------------------------------------------------------
    # Internal matching helpers
    # ------------------------------------------------------------------

    def _exact_match(self, col_name: str) -> tuple[str | None, int]:
        """Try case-insensitive exact alias match.

        Returns ``(canonical_name, confidence)`` or ``(None, 0)``.
        """
        lower = col_name.strip().lower()
        for canonical, defn in self._definitions.items():
            aliases = [a.lower() for a in defn.get("aliases", [])]
            if lower in aliases:
                return canonical, 100
        return None, 0

    def _fuzzy_match(self, col_name: str) -> tuple[str | None, int]:
        """Try fuzzy token-sort-ratio match against all aliases.

        Returns ``(canonical_name, confidence)`` or ``(None, 0)``.
        """
        lower = col_name.strip().lower()
        best_canonical: str | None = None
        best_score = 0

        for canonical, defn in self._definitions.items():
            for alias in defn.get("aliases", []):
                score = _fuzzy_ratio(lower, alias.lower())
                if score > best_score:
                    best_score = score
                    best_canonical = canonical

        if best_score >= _FUZZY_THRESHOLD:
            return best_canonical, best_score
        return None, 0

    def _keyword_match(self, col_name: str) -> tuple[str | None, int]:
        """Check if any registered keyword is a substring of *col_name*.

        Returns ``(canonical_name, confidence)`` or ``(None, 0)``.
        """
        lower = col_name.strip().lower()
        best_canonical: str | None = None
        best_keyword_len = 0

        for canonical, defn in self._definitions.items():
            for keyword in defn.get("keywords", []):
                kw_lower = keyword.lower()
                if kw_lower in lower and len(kw_lower) > best_keyword_len:
                    best_keyword_len = len(kw_lower)
                    best_canonical = canonical

        if best_canonical is not None:
            # Confidence scales with keyword length relative to column name
            confidence = min(70, 40 + best_keyword_len * 5)
            return best_canonical, confidence
        return None, 0

    def _type_match(
        self,
        col_name: str,
        series: pd.Series,
        already_mapped: set[str],
    ) -> tuple[str | None, int]:
        """Attempt to match by detected column type for unmatched canonicals.

        Only considers canonical names that have *not* been mapped yet.
        """
        detected_type = self._engine.detect_column_type(series)
        candidates: list[str] = [
            canonical
            for canonical, defn in self._definitions.items()
            if canonical not in already_mapped
            and defn.get("type", "string") == detected_type
        ]
        if len(candidates) == 1:
            return candidates[0], 30
        return None, 0

    # ------------------------------------------------------------------
    # Public API: mapping
    # ------------------------------------------------------------------

    def map_columns(self, df: pd.DataFrame) -> dict[str, str]:
        """Determine the best mapping from *df* column names to canonical names.

        Returns a ``{original_column: canonical_name}`` dict.  Columns that
        cannot be mapped are excluded from the result.
        """
        mapping: dict[str, str] = {}
        confidences: dict[str, int] = {}
        mapped_canonicals: set[str] = set()

        # Pass 1: exact match (highest priority)
        for col in df.columns:
            canonical, score = self._exact_match(col)
            if canonical and canonical not in mapped_canonicals:
                mapping[col] = canonical
                confidences[col] = score
                mapped_canonicals.add(canonical)

        # Pass 2: fuzzy match on remaining columns
        for col in df.columns:
            if col in mapping:
                continue
            canonical, score = self._fuzzy_match(col)
            if canonical and canonical not in mapped_canonicals:
                mapping[col] = canonical
                confidences[col] = score
                mapped_canonicals.add(canonical)

        # Pass 3: keyword match
        for col in df.columns:
            if col in mapping:
                continue
            canonical, score = self._keyword_match(col)
            if canonical and canonical not in mapped_canonicals:
                mapping[col] = canonical
                confidences[col] = score
                mapped_canonicals.add(canonical)

        # Pass 4: type-based inference (weakest signal)
        for col in df.columns:
            if col in mapping:
                continue
            canonical, score = self._type_match(col, df[col], mapped_canonicals)
            if canonical and canonical not in mapped_canonicals:
                mapping[col] = canonical
                confidences[col] = score
                mapped_canonicals.add(canonical)

        logger.info(
            "Column mapping: %d/%d columns mapped (%d exact, %d fuzzy, %d keyword, %d type)",
            len(mapping),
            len(df.columns),
            sum(1 for s in confidences.values() if s == 100),
            sum(1 for s in confidences.values() if _FUZZY_THRESHOLD <= s < 100),
            sum(1 for s in confidences.values() if 30 < s < _FUZZY_THRESHOLD),
            sum(1 for s in confidences.values() if s == 30),
        )
        return mapping

    def apply_mapping(
        self,
        df: pd.DataFrame,
        mapping: dict[str, str],
    ) -> pd.DataFrame:
        """Return a copy of *df* with columns renamed per *mapping*.

        Columns not present in *mapping* are kept with their original names.
        """
        rename_map = {orig: canonical for orig, canonical in mapping.items() if orig in df.columns}
        return df.rename(columns=rename_map)

    # ------------------------------------------------------------------
    # Confidence & diagnostics
    # ------------------------------------------------------------------

    def get_mapping_confidence(self, mapping: dict[str, str]) -> dict[str, int]:
        """Return ``{original_column: confidence_score}`` for each mapped column.

        Scores:
        - 100  = exact alias match
        - 80-99 = fuzzy match
        - 40-70 = keyword match
        - 30    = type-only inference
        """
        confidences: dict[str, int] = {}
        for orig, canonical in mapping.items():
            # Re-evaluate the best strategy that produced this mapping
            _, exact_score = self._exact_match(orig)
            if exact_score > 0:
                confidences[orig] = exact_score
                continue

            _, fuzzy_score = self._fuzzy_match(orig)
            if fuzzy_score >= _FUZZY_THRESHOLD:
                confidences[orig] = fuzzy_score
                continue

            _, kw_score = self._keyword_match(orig)
            if kw_score > 0:
                confidences[orig] = kw_score
                continue

            confidences[orig] = 30  # type-based
        return confidences

    def get_unmapped_columns(
        self,
        df: pd.DataFrame,
        mapping: dict[str, str],
    ) -> list[str]:
        """Return column names from *df* that have no canonical mapping."""
        return [col for col in df.columns if col not in mapping]

    # ------------------------------------------------------------------
    # Metric / return discovery
    # ------------------------------------------------------------------

    def get_available_metrics(
        self,
        df: pd.DataFrame,
        mapping: dict[str, str],
    ) -> list[str]:
        """Return canonical metric names (risk group) that were successfully mapped."""
        risk_group = set(COLUMN_GROUPS.get("Risk Metrics", []))
        mapped_canonicals = set(mapping.values())
        return sorted(risk_group & mapped_canonicals)

    def get_available_returns(
        self,
        df: pd.DataFrame,
        mapping: dict[str, str],
    ) -> list[str]:
        """Return canonical return column names that were successfully mapped."""
        returns_group = set(COLUMN_GROUPS.get("Returns", []))
        mapped_canonicals = set(mapping.values())
        return sorted(returns_group & mapped_canonicals)
