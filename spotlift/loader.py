"""Data loaders and parsers for GA4 and Amazon CSV exports.

The real exports from GA4 or Amazon APIs can have many column formats. These
helpers provide a small, permissive normalization to a DataFrame with a
parsed date column and preserved metric columns. They are intentionally lightweight.
"""

from typing import Optional
import pandas as pd


def load_csv(path: str, parse_dates: Optional[list] = None, **kwargs) -> pd.DataFrame:
    """Load a CSV into a DataFrame, with optional date parsing.

    Args:
        path: Path to CSV file.
        parse_dates: List of columns to parse as dates.
        **kwargs: Passed to pandas.read_csv
    """
    if parse_dates is None:
        df = pd.read_csv(path, **kwargs)
    else:
        df = pd.read_csv(path, parse_dates=parse_dates, **kwargs)
    return df


def _find_date_column(df: pd.DataFrame) -> Optional[str]:
    candidates = ["date", "day", "event_date", "timestamp"]
    for c in candidates:
        if c in df.columns:
            return c
    # fallback: any column with datetime dtype
    for c in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[c]):
            return c
    return None


def load_ga4_csv(path: str) -> pd.DataFrame:
    """Load and lightly normalize a GA4 CSV export.

    Returns a DataFrame with a `date` column (if detected) and the original metrics.
    """
    df = load_csv(path)
    date_col = _find_date_column(df)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
        if date_col != "date":
            df = df.rename(columns={date_col: "date"})
    return df


def load_amazon_csv(path: str) -> pd.DataFrame:
    """Load and lightly normalize an Amazon response CSV.

    Amazon exports differ by product (Advertising, Retail) — this helper parses
    the CSV and attempts to find a date-like column.
    """
    df = load_csv(path)
    date_col = _find_date_column(df)
    if date_col:
        df[date_col] = pd.to_datetime(df[date_col])
        if date_col != "date":
            df = df.rename(columns={date_col: "date"})
    return df
