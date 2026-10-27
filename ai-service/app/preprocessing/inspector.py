"""Dataset inspection: raw profiling used by STEP 2 of the dashboard workflow."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

import pandas as pd

# Label values we recognise without any user mapping.
CANONICAL_LABELS = {
    "phishing", "phish", "malicious", "bad", "1", "1.0", "true", "yes", "attack",
    "legitimate", "legit", "benign", "good", "0", "0.0", "false", "no", "safe",
}

MAX_HEAD_ROWS = 20
MAX_CELLS_PER_COLUMN_SAMPLE = 5


def _json_safe(value: Any) -> Any:
    """Convert pandas/numpy scalars into JSON-serialisable Python values."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if hasattr(value, "item"):
        try:
            return value.item()
        except Exception:  # pragma: no cover - defensive
            return str(value)
    if isinstance(value, float) and pd.isna(value):
        return None
    return value if isinstance(value, (str, int, float, bool)) else str(value)


def read_csv_profile(path) -> pd.DataFrame:
    """Read a delimited file, falling back to tab separated if needed."""
    try:
        df = pd.read_csv(path)
    except pd.errors.ParserError:
        df = pd.read_csv(path, sep="\t")
    # Normalise column names (they are used as keys by the whole platform)
    df.columns = [str(c).strip() for c in df.columns]
    return df


def profile_dataset(
    df: pd.DataFrame,
    target_column: Optional[str],
    filename: str = "",
    max_rows: int = 1_000_000,
) -> Dict[str, Any]:
    """Build the inspection payload shown in STEP 2 of the dashboard."""
    warnings: List[str] = []
    columns: List[Dict[str, Any]] = []

    for name in df.columns:
        series = df[name]
        missing = int(series.isna().sum())
        # Treat blank strings as missing too (common in exported CSVs)
        if series.dtype == object:
            missing = int(series.isna().sum() + (series.astype(str).str.strip() == "").sum())
        non_null = series.dropna()
        columns.append({
            "name": name,
            "dtype": str(series.dtype),
            "missing": missing,
            "missingPct": round(100.0 * missing / max(len(df), 1), 2),
            "unique": int(series.nunique(dropna=True)),
            "samples": [_json_safe(v) for v in non_null.head(MAX_CELLS_PER_COLUMN_SAMPLE).tolist()],
        })

    target_info: Dict[str, Any] = {
        "column": target_column,
        "present": bool(target_column) and target_column in df.columns,
        "distribution": {},
        "uniqueValues": [],
        "unrecognisedValues": [],
        "warnings": [],
    }

    if target_info["present"]:
        series = df[target_column]
        counts = series.value_counts(dropna=False)
        target_info["distribution"] = {
            ("<null>" if pd.isna(k) else str(k)): int(v) for k, v in counts.items()
        }
        unique_vals = [str(v) for v in series.dropna().unique().tolist()]
        target_info["uniqueValues"] = unique_vals[:50]
        unrecognised = [v for v in unique_vals if v.strip().lower() not in CANONICAL_LABELS]
        target_info["unrecognisedValues"] = unrecognised
        if unrecognised:
            msg = (
                f"Target column '{target_column}' contains values that are not in the "
                f"recognised label set: {unrecognised[:10]}. Provide an explicit label "
                f"mapping when running preprocessing - rows will NOT be relabelled silently."
            )
            target_info["warnings"].append(msg)
            warnings.append(msg)
        if series.isna().any():
            msg = f"Target column '{target_column}' has {int(series.isna().sum())} missing values."
            target_info["warnings"].append(msg)
            warnings.append(msg)
    elif target_column:
        msg = f"Target column '{target_column}' does not exist in this file."
        target_info["warnings"].append(msg)
        warnings.append(msg)
    else:
        warnings.append("No target column selected yet - select the label column before preprocessing.")

    dup_count = int(df.duplicated().sum())
    if dup_count:
        warnings.append(f"{dup_count} fully duplicated row(s) detected (exact matches across all columns).")

    if len(df) > max_rows:
        warnings.append(f"File has {len(df)} rows which exceeds the configured limit {max_rows}.")

    head_df = df.head(MAX_HEAD_ROWS)
    head: List[Dict[str, Any]] = [
        {str(col): _json_safe(val) for col, val in row.items()}
        for row in head_df.to_dict(orient="records")
    ]

    return {
        "filename": filename,
        "rows": int(len(df)),
        "columns": columns,
        "columnNames": [str(c) for c in df.columns],
        "duplicateRows": dup_count,
        "missingCells": int(sum(c["missing"] for c in columns)),
        "target": target_info,
        "head": head,
        "warnings": warnings,
    }
