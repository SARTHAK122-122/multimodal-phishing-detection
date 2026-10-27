"""Standalone, reproducible preprocessing demonstration.

Runs exactly the same code path as the web workflow (app.preprocessing.pipeline)
but entirely from the command line, so the whole process can be inspected
without the dashboard.

Usage (from the repository root or ai-service/):

    python ai-service/preprocessing/run_preprocessing_demo.py \
        --input uploads/sample_urls_demo.csv \
        --target label \
        --label-map "suspicious=phishing" \
        --out uploads/processed/sample_urls_demo__cli.csv

It prints:
  * raw inspection (rows, dtypes, missing values, duplicates, label counts)
  * every transformation applied with the number of rows it affected
  * a before/after comparison table
  * warnings (label issues, leakage candidates, heavy filtering)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.preprocessing.inspector import profile_dataset, read_csv_profile  # noqa: E402
from app.preprocessing.pipeline import run_preprocessing  # noqa: E402


def parse_label_map(raw: str | None) -> dict[str, str]:
    if not raw:
        return {}
    mapping = {}
    for pair in raw.split(","):
        if "=" not in pair:
            raise SystemExit(f"Invalid --label-map entry '{pair}'. Use key=value,key=value")
        key, value = pair.split("=", 1)
        mapping[key.strip()] = value.strip()
    return mapping


def main() -> int:
    parser = argparse.ArgumentParser(description="Reproducible dataset preprocessing demo")
    parser.add_argument("--input", required=True, help="Path to the raw CSV (left untouched)")
    parser.add_argument("--target", required=True, help="Label column name")
    parser.add_argument("--label-map", default="", help='Explicit mapping, e.g. "suspicious=phishing,1=phishing"')
    parser.add_argument("--missing-strategy", default="median_mode",
                        choices=["drop_rows", "median_mode", "drop_columns"])
    parser.add_argument("--dedupe-column", default="url", help="Column to canonicalise before dedupe ('' to disable)")
    parser.add_argument("--out", default="", help="Output CSV path (default: <input>__processed.csv)")
    args = parser.parse_args()

    input_path = Path(args.input)
    if not input_path.exists():
        raise SystemExit(f"Input file not found: {input_path}")
    out_path = Path(args.out) if args.out else input_path.with_name(input_path.stem + "__processed.csv")

    # ---------------------------------------------------------------- inspect
    df = read_csv_profile(input_path)
    profile = profile_dataset(df, args.target, filename=input_path.name)

    print("=" * 78)
    print("RAW DATASET INSPECTION")
    print("=" * 78)
    print(f"file            : {input_path}")
    print(f"rows x columns  : {profile['rows']} x {len(profile['columns'])}")
    print(f"duplicate rows  : {profile['duplicateRows']}")
    print(f"missing cells   : {profile['missingCells']}")
    print(f"columns         : {', '.join(profile['columnNames'])}")
    print("\ncolumn profile:")
    for col in profile["columns"]:
        print(f"  - {col['name']:<24} dtype={col['dtype']:<10} missing={col['missing']:<4} "
              f"unique={col['unique']:<5} samples={col['samples'][:3]}")
    print("\ntarget label distribution:")
    for label, count in profile["target"]["distribution"].items():
        print(f"  - {label:<15} {count}")
    if profile["target"]["unrecognisedValues"]:
        print(f"  ! unrecognised label values: {profile['target']['unrecognisedValues']}")
    if profile["warnings"]:
        print("\ninspection warnings:")
        for warning in profile["warnings"]:
            print(f"  ! {warning}")

    # ----------------------------------------------------------- preprocessing
    options = {
        "targetColumn": args.target,
        "normalizeLabels": True,
        "dropInvalidRows": True,
        "convertTypes": True,
        "detectConflictingDuplicates": True,
        "removeDuplicates": True,
        "handleMissing": True,
        "missingStrategy": args.missing_strategy,
        "dedupeOnColumn": args.dedupe_column or None,
        "validateFeatures": True,
        "labelMapping": parse_label_map(args.label_map),
    }

    print("\n" + "=" * 78)
    print("PREPROCESSING")
    print("=" * 78)
    print("parameters:")
    print(json.dumps(options, indent=2))

    result = run_preprocessing(df, options)
    processed: pd.DataFrame = result.pop("dataframe")

    print("\ntransformations applied:")
    for step in result["transformations"]:
        print(f"  [{step['step']:<28}] affected={step['rowsAffected']:<5} {step['description']}")

    if result["warnings"]:
        print("\nwarnings:")
        for warning in result["warnings"]:
            print(f"  ! {warning}")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    processed.to_csv(out_path, index=False)

    print("\n" + "=" * 78)
    print("BEFORE / AFTER")
    print("=" * 78)
    print(f"rows                : {result['inputRows']} -> {result['outputRows']}")
    print(f"duplicates removed  : {result['duplicatesRemoved']}")
    print(f"invalid rows removed: {result['invalidRowsRemoved']}")
    print(f"missing values fixed: {result['missingValuesHandled']}")
    print(f"class distribution  : {result['classDistributionBefore']} -> {result['classDistributionAfter']}")
    print(f"missing by column   : before={result['missingBefore']}")
    print(f"                      after ={result['missingAfter']}")
    if result["featureReport"]:
        print("\nfeature report (report-only - nothing was dropped automatically):")
        print(json.dumps(result["featureReport"], indent=2))
    print(f"\nprocessed CSV written to: {out_path}")
    print("original file left untouched.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
