"""Extract and profile the PhiUSIIL dataset (UCI #967) for the project.

Run from ai-service/:  .venv\\Scripts\\python.exe training\\inspect_dataset.py
Prints shape, label distribution, missing values and sample URLs.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
ZIP = ROOT / "datasets" / "sources" / "phiusiil_phishing_url_dataset.zip"
CSV = ROOT / "datasets" / "sources" / "PhiUSIIL_Phishing_URL_Dataset.csv"


def ensure_extracted() -> None:
    if CSV.exists():
        return
    with zipfile.ZipFile(ZIP) as zf:
        zf.extractall(CSV.parent)
    print(f"extracted -> {CSV}")


def main() -> None:
    ensure_extracted()
    df = pd.read_csv(CSV, encoding="utf-8-sig")
    print(f"shape: {df.shape}")
    print(f"columns ({len(df.columns)}): {list(df.columns)}")
    print("\nlabel distribution:")
    print(df["label"].value_counts(dropna=False).to_string())
    print(f"\nunique URLs: {df['URL'].nunique()} / {len(df)}")
    print(f"missing URL cells: {df['URL'].isna().sum()}")
    print(f"missing label cells: {df['label'].isna().sum()}")
    print("\nsample rows:")
    for _, row in df[["URL", "label"]].head(5).iterrows():
        print(f"  [{row['label']}] {row['URL'][:110]}")
    for _, row in df[["URL", "label"]].tail(3).iterrows():
        print(f"  [{row['label']}] {row['URL'][:110]}")


if __name__ == "__main__":
    main()
