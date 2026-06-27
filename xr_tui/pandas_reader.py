"""Utilities for reading pandas-supported tabular files into xarray DataTrees."""

from pathlib import Path

import pandas as pd
import xarray as xr

TABULAR_EXTENSIONS = {
    ".csv": ("read_csv", {}),
    ".tsv": ("read_csv", {"sep": "\t"}),
    ".json": ("read_json", {}),
    ".parquet": ("read_parquet", {}),
    ".xlsx": ("read_excel", {"sheet_name": None}),
    ".xls": ("read_excel", {"sheet_name": None}),
    ".feather": ("read_feather", {}),
    ".orc": ("read_orc", {}),
}


def is_tabular(path) -> bool:
    """Return True if the path has a pandas-supported tabular extension."""
    return Path(str(path)).suffix.lower() in TABULAR_EXTENSIONS


def _df_to_dataset(df: pd.DataFrame) -> xr.Dataset:
    """Convert a DataFrame to an xarray Dataset."""
    return df.to_xarray()


def _excel_to_datatree(path, sheets: dict) -> xr.DataTree:
    """Build a DataTree from a dict of sheet_name → DataFrame (from read_excel)."""
    name = Path(str(path)).stem
    if len(sheets) == 1:
        df = next(iter(sheets.values()))
        return xr.DataTree(name=name, dataset=_df_to_dataset(df))
    children = {
        sheet: xr.DataTree(name=sheet, dataset=_df_to_dataset(df))
        for sheet, df in sheets.items()
    }
    return xr.DataTree(name=name, dataset=xr.Dataset(), children=children)


def pandas_to_datatree(path) -> xr.DataTree:
    """Load a tabular file via pandas and return an xr.DataTree."""
    suffix = Path(str(path)).suffix.lower()
    reader_name, kwargs = TABULAR_EXTENSIONS[suffix]
    reader = getattr(pd, reader_name)

    if suffix in (".xlsx", ".xls"):
        sheets = reader(path, **kwargs)
        return _excel_to_datatree(path, sheets)

    if suffix == ".json":
        try:
            df = reader(path, **kwargs)
        except ValueError:
            df = reader(path, orient="records")
    else:
        df = reader(path, **kwargs)

    return xr.DataTree(name=Path(str(path)).stem, dataset=_df_to_dataset(df))
