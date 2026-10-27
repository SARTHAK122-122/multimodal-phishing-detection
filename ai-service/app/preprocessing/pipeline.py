"""Manual, reproducible dataset preprocessing.

The pipeline never modifies the uploaded file: it works on a copy and writes a
*separate* processed CSV. Every step records what it changed so the run can be
audited (dashboard STEP 5) and reproduced (identical parameters are echoed back
and stored in ``preprocessing_runs.parameters_json``).

Steps run in a fixed, documented order:

 1. normalize_labels        - explicit user mapping only, never guessed
 2. drop_invalid_rows       - rows with a missing/unmappable target label
 3. convert_types           - coerce declared numeric feature columns
 4. conflicting_duplicates  - identical features but different label -> drop
 5. handle_missing          - drop rows / median+mode impute / drop column
 6. remove_duplicates       - exact duplicate rows
 7. dedupe_on_column        - normalised-URL style deduplication (optional)
 8. drop/select columns     - explicit user selection only
 9. validate_feature_columns- report only, nothing is dropped silently
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

DEFAULT_OPTIONS: Dict[str, Any] = {
    "normalizeLabels": True,
    "dropInvalidRows": True,
    "convertTypes": True,
    "detectConflictingDuplicates": True,
    "removeDuplicates": True,
    "handleMissing": True,
    "missingStrategy": "median_mode",       # drop_rows | median_mode | drop_columns
    "missingMaxFraction": 0.5,              # columns missing more than this -> drop (drop_columns)
    "dedupeOnColumn": None,                 # e.g. "url"
    "dropColumns": [],                      # explicit removal list
    "selectColumns": [],                    # if non-empty, keep only these + target
    "validateFeatures": True,
    "labelMapping": {},                     # {"suspicious": "phishing", ...}
}

_URL_SCHEME_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*://")


def _log(step: str, description: str, affected: int = 0, details: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return {"step": step, "description": description, "rowsAffected": int(affected), "details": details or {}}


def normalize_url_for_dedupe(value: Any) -> str:
    """Cheap canonicalisation used only for duplicate detection (not a label)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip().lower()
    if not _URL_SCHEME_RE.match(text):
        text = "http://" + text
    text = text.rstrip("/")
    # strip default ports and fragment
    text = text.replace(":80", "").replace(":443", "")
    text = text.split("#", 1)[0]
    return text


def run_preprocessing(df: pd.DataFrame, options: Dict[str, Any]) -> Dict[str, Any]:
    """Execute the configured pipeline. Returns stats + transformations."""
    opts = {**DEFAULT_OPTIONS, **{k: v for k, v in (options or {}).items() if v is not None}}
    target = options.get("targetColumn")
    if not target:
        raise ValueError("targetColumn is required")

    transformations: List[Dict[str, Any]] = []
    warnings: List[str] = []

    input_rows = int(len(df))
    missing_before = _missing_by_column(df)

    work = df.copy()
    work.columns = [str(c).strip() for c in work.columns]

    if target not in work.columns:
        raise ValueError(f"target column '{target}' not found; columns: {list(work.columns)}")

    # ---------------------------------------------------------------- 1. labels
    label_map: Dict[str, str] = {str(k): str(v) for k, v in (opts.get("labelMapping") or {}).items()}
    if opts["normalizeLabels"] and label_map:
        before_counts = work[target].astype(str).value_counts().to_dict()
        work[target] = work[target].map(lambda v: label_map.get(str(v), v) if pd.notna(v) else v)
        changed = int(sum(int(before_counts.get(k, 0)) for k in label_map))
        transformations.append(_log(
            "normalize_labels",
            f"Applied explicit label mapping {label_map} to column '{target}'.",
            changed,
            {"mapping": label_map},
        ))
        unmapped = sorted({str(v) for v in work[target].dropna().unique()
                           if str(v).strip().lower() not in {"phishing", "legitimate", "1", "0"}})
        if unmapped:
            warnings.append(f"Labels still not canonical after mapping: {unmapped[:10]}")

    # --------------------------------------------------------- 2. invalid rows
    invalid_rows_removed = 0
    if opts["dropInvalidRows"]:
        mask_missing_target = work[target].isna()
        # also drop rows whose target is an empty string
        if work[target].dtype == object:
            mask_missing_target = mask_missing_target | (work[target].astype(str).str.strip() == "")
        n = int(mask_missing_target.sum())
        if n:
            work = work[~mask_missing_target]
        invalid_rows_removed += n
        transformations.append(_log(
            "drop_invalid_rows",
            f"Removed rows where the target column '{target}' is missing/empty.",
            n,
        ))

    # --------------------------------------------------------- 3. types
    if opts["convertTypes"]:
        coerced: Dict[str, int] = {}
        for col in work.columns:
            if col == target:
                continue
            if work[col].dtype == object:
                converted = pd.to_numeric(work[col], errors="coerce")
                newly_na = int(converted.isna().sum() - work[col].isna().sum())
                # only treat as numeric if most values convert
                convertible_ratio = (len(work) - converted.isna().sum()) / max(len(work), 1)
                if convertible_ratio >= 0.9:
                    work[col] = converted
                    if newly_na > 0:
                        coerced[col] = newly_na
        if coerced:
            warnings.append(
                "Numeric conversion produced new missing values in: "
                + ", ".join(f"{k} (+{v})" for k, v in coerced.items())
            )
        transformations.append(_log(
            "convert_types",
            "Coerced numeric-looking feature columns to numeric dtype (unparseable cells -> NaN).",
            sum(coerced.values()),
            {"columns": list(coerced.keys())},
        ))

    # ------------------------------------------- 4. conflicting duplicates
    if opts["detectConflictingDuplicates"] and len(work):
        feature_cols = [c for c in work.columns if c != target]
        if feature_cols:
            keys = work[feature_cols].astype(str).agg("||".join, axis=1)
            labels = work[target].astype(str)
            combined = pd.DataFrame({"__key__": keys.to_numpy(), "__label__": labels.to_numpy()},
                                    index=work.index)
            label_counts = combined.groupby("__key__")["__label__"].nunique()
            bad_keys = set(label_counts[label_counts > 1].index)
            if bad_keys:
                conflict_index = combined[combined["__key__"].isin(bad_keys)].index
                n_conflict = int(len(conflict_index))
                work = work.drop(index=conflict_index)
                invalid_rows_removed += n_conflict
                transformations.append(_log(
                    "detect_conflicting_duplicates",
                    "Removed rows whose feature values are identical but whose labels disagree "
                    "(contradictory supervision would poison training).",
                    n_conflict,
                    {"conflictingFeatureGroups": len(bad_keys)},
                ))
            else:
                transformations.append(_log(
                    "detect_conflicting_duplicates",
                    "No contradictory duplicate records found.",
                    0,
                ))

    # ------------------------------------------------- 5. missing values
    missing_values_handled = 0
    if opts["handleMissing"]:
        strategy = opts["missingStrategy"]
        if strategy == "drop_rows":
            before = len(work)
            work = work.dropna()
            removed = int(before - len(work))
            missing_values_handled = removed  # reported as rows removed for missingness
            transformations.append(_log(
                "handle_missing",
                "Strategy=drop_rows: removed every row containing at least one missing value.",
                removed,
                {"strategy": strategy, "rowsRemoved": removed},
            ))
            if removed:
                warnings.append(f"drop_rows removed {removed} row(s); verify this does not bias the dataset.")
        elif strategy == "drop_columns":
            frac = work.isna().mean()
            to_drop = [c for c in work.columns if c != target and frac.get(c, 0) > float(opts["missingMaxFraction"])]
            if to_drop:
                work = work.drop(columns=to_drop)
            missing_values_handled = len(to_drop)
            transformations.append(_log(
                "handle_missing",
                f"Strategy=drop_columns: dropped columns with more than "
                f"{float(opts['missingMaxFraction']) * 100:.0f}% missing values.",
                len(to_drop),
                {"strategy": strategy, "columns": to_drop},
            ))
            if to_drop:
                warnings.append(
                    f"Columns dropped due to missingness: {to_drop}. Review before training - "
                    "dropping a feature is a modelling decision, not a default."
                )
        else:  # median_mode
            cells = 0
            imputed: Dict[str, str] = {}
            for col in work.columns:
                if col == target or work[col].isna().sum() == 0:
                    continue
                if pd.api.types.is_numeric_dtype(work[col]):
                    median = work[col].median()
                    if pd.notna(median):
                        cells += int(work[col].isna().sum())
                        work[col] = work[col].fillna(median)
                        imputed[col] = f"median={median}"
                else:
                    mode = work[col].mode(dropna=True)
                    if len(mode):
                        cells += int(work[col].isna().sum())
                        work[col] = work[col].fillna(mode.iloc[0])
                        imputed[col] = f"mode={mode.iloc[0]}"
            missing_values_handled = cells
            transformations.append(_log(
                "handle_missing",
                "Strategy=median_mode: numeric features filled with the column median, "
                "categorical features with the column mode (computed on THIS dataset only).",
                cells,
                {"strategy": strategy, "columns": imputed},
            ))

    # ------------------------------------------------- 6. duplicates
    duplicates_removed = 0
    if opts["removeDuplicates"] and len(work):
        before = len(work)
        work = work.drop_duplicates(keep="first").reset_index(drop=True)
        duplicates_removed += int(before - len(work))
        transformations.append(_log(
            "remove_duplicates",
            "Removed exact duplicate rows (kept the first occurrence).",
            int(before - len(work)),
        ))

    # ------------------------------------------- 7. dedupe on a column
    dedupe_col = opts.get("dedupeOnColumn")
    if dedupe_col:
        if dedupe_col not in work.columns:
            warnings.append(f"dedupeOnColumn '{dedupe_col}' does not exist - step skipped.")
        elif len(work):
            before = len(work)
            keys = work[dedupe_col].map(normalize_url_for_dedupe)
            work = work[~keys.duplicated(keep="first")].reset_index(drop=True)
            duplicates_removed += int(before - len(work))
            transformations.append(_log(
                "dedupe_on_column",
                f"Removed duplicates after canonicalising '{dedupe_col}' "
                "(lowercase, scheme added, trailing slash and fragment removed).",
                int(before - len(work)),
                {"column": dedupe_col},
            ))

    # ------------------------------------------- 8. column selection
    drop_cols = [c for c in (opts.get("dropColumns") or []) if c in work.columns]
    if drop_cols:
        missing_target_dropped = target in drop_cols
        drop_cols = [c for c in drop_cols if c != target]
        if missing_target_dropped:
            warnings.append("Refused to drop the target column - it would destroy the labels.")
        work = work.drop(columns=drop_cols)
        transformations.append(_log("drop_columns", f"Explicitly removed columns: {drop_cols}.", 0,
                                    {"columns": drop_cols}))

    select_cols = [c for c in (opts.get("selectColumns") or []) if c in work.columns]
    if select_cols:
        keep = select_cols + ([target] if target in work.columns else [])
        removed = [c for c in work.columns if c not in keep]
        work = work[keep]
        transformations.append(_log(
            "select_columns", f"Kept only selected feature columns: {select_cols}.", 0,
            {"removedColumns": removed},
        ))

    # ------------------------------------------- 9. feature validation (report)
    feature_report: Dict[str, Any] = {}
    if opts["validateFeatures"]:
        feature_report = validate_feature_columns(work, target)
        for item in feature_report["notes"]:
            warnings.append(item)

    missing_after = _missing_by_column(work)
    class_before = _class_distribution(df, target)
    class_after = _class_distribution(work, target)

    output_rows = int(len(work))
    if output_rows == 0:
        raise ValueError("Preprocessing produced 0 rows - check the selected operations and label mapping.")
    if input_rows and output_rows / input_rows < 0.2:
        warnings.append(
            f"Only {output_rows}/{input_rows} rows remain ({100 * output_rows / input_rows:.1f}%). "
            "Review the operations: heavy filtering can bias later evaluation."
        )

    return {
        "inputRows": input_rows,
        "outputRows": output_rows,
        "duplicatesRemoved": duplicates_removed,
        "invalidRowsRemoved": invalid_rows_removed,
        "missingValuesHandled": missing_values_handled,
        "transformations": transformations,
        "warnings": warnings,
        "missingBefore": missing_before,
        "missingAfter": missing_after,
        "classDistributionBefore": class_before,
        "classDistributionAfter": class_after,
        "featureReport": feature_report,
        "parameters": opts,
        "dataframe": work,
    }


def validate_feature_columns(df: pd.DataFrame, target: str) -> Dict[str, Any]:
    """Report-only checks: leakage candidates, constant and non-numeric columns."""
    notes: List[str] = []
    constant: List[str] = []
    non_numeric: List[str] = []
    leakage_suspects: List[str] = []
    identifier_like: List[str] = []

    leakage_names = {"label", "class", "result", "target", "label_num", "is_phishing", "phishing"}
    identifier_patterns = ("url", "id", "hash", "index", "uuid", "timestamp", "time", "date")

    for col in df.columns:
        if col == target:
            continue
        series = df[col]
        if series.nunique(dropna=True) <= 1:
            constant.append(col)
        if not pd.api.types.is_numeric_dtype(series) and series.dtype != bool:
            non_numeric.append(col)
        if col.strip().lower() in leakage_names and col != target:
            leakage_suspects.append(col)
        if col.strip().lower().startswith(identifier_patterns):
            identifier_like.append(col)

    if constant:
        notes.append(f"Constant feature column(s) carry no signal: {constant}.")
    if leakage_suspects:
        notes.append(
            f"Possible label-leaking column(s) found: {leakage_suspects}. They were NOT removed "
            "automatically - decide explicitly and record the decision."
        )
    if identifier_like:
        notes.append(
            f"Identifier-like column(s) {identifier_like} may encode the label indirectly or split "
            "poorly; consider excluding them before training (not done automatically)."
        )
    if non_numeric:
        notes.append(f"Non-numeric feature column(s) {non_numeric} need encoding before ML training.")

    return {
        "constantColumns": constant,
        "nonNumericColumns": non_numeric,
        "possibleLeakageColumns": leakage_suspects,
        "identifierLikeColumns": identifier_like,
        "notes": notes,
    }


def _class_distribution(df: pd.DataFrame, target: str) -> Dict[str, int]:
    if target not in df.columns:
        return {}
    counts = df[target].value_counts(dropna=False)
    return {"<null>" if pd.isna(k) else str(k): int(v) for k, v in counts.items()}


def _missing_by_column(df: pd.DataFrame) -> Dict[str, int]:
    result: Dict[str, int] = {}
    for col in df.columns:
        series = df[col]
        missing = int(series.isna().sum())
        if series.dtype == object:
            missing += int((series.astype(str).str.strip() == "").sum())
        result[str(col)] = missing
    return result


def dataframe_fingerprint(df: pd.DataFrame) -> str:
    """Stable hash of a dataframe, used to verify reproducibility claims."""
    payload = pd.util.hash_pandas_object(df, index=True).values.tobytes()
    return hashlib.sha256(payload).hexdigest()[:16]
