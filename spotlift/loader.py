"""Data loaders for common CSV exports.

Currently includes lightweight CSV parsers for GA4 (Google Analytics 4)
and a simple Amazon response CSV format.

These functions return pandas.DataFrame objects ready for modeling.
"""
from typing import List

import pandas as pd


def load_ga4_csv(path: str, date_col: str = "date", metrics: List[str] = None) -> pd.DataFrame:
    """Load a GA4 CSV export into a DataFrame.

    The function tries to be forgiving about common GA4 CSV shapes: it
    coerces the date column to datetime and keeps only the requested metrics
    (or all numeric columns if metrics is None).
    """
    df = pd.read_csv(path)
    if date_col not in df.columns and "Date" in df.columns:
        date_col = "Date"

    df[date_col] = pd.to_datetime(df[date_col])

    if metrics:
        cols = [date_col] + metrics
        missing = [c for c in cols if c not in df.columns]
        if missing:
            raise ValueError(f"Missing expected columns in GA4 CSV: {missing}")
        return df[cols]

    # default: keep date and all numeric cols
    numerics = df.select_dtypes(include=["number"]).columns.tolist()
    cols = [date_col] + numerics
    return df[cols]


def load_amazon_csv(path: str, date_col: str = "date", value_col: str = "purchases") -> pd.DataFrame:
    """Load a simple Amazon responses CSV into a DataFrame.

    Expects at least a date column and a numeric column with the response metric
    (clicks, purchases, sales, etc.).
    """
    df = pd.read_csv(path)
    if date_col not in df.columns and "Date" in df.columns:
        date_col = "Date"
    df[date_col] = pd.to_datetime(df[date_col])

    if value_col not in df.columns:
        raise ValueError(f"Expected value column '{value_col}' not found in Amazon CSV")

    return df[[date_col, value_col]]
