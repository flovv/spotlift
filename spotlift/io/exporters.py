"""Export helpers for results."""
from typing import Optional
import pandas as pd


def export_csv(df: pd.DataFrame, path: str) -> None:
    df.to_csv(path, index=False)


def export_json(df: pd.DataFrame, path: str) -> None:
    df.to_json(path, orient="records", date_format="iso")
