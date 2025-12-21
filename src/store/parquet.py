from __future__ import annotations

import json
from pathlib import Path
from typing import List, Optional

import pandas as pd
import pyarrow as pa
import pyarrow.dataset as ds
import pyarrow.parquet as pq

from src.utils import ensure_dir


def _normalize_flags(df: pd.DataFrame) -> pd.DataFrame:
    if "quality_flags" in df.columns:
        df = df.copy()
        df["quality_flags"] = df["quality_flags"].apply(
            lambda x: json.dumps(x, ensure_ascii=False) if isinstance(x, dict) else x
        )
    return df


def write_parquet(
    df: pd.DataFrame,
    output_dir: Path,
    partition_cols: Optional[List[str]] = None,
    compression: str = "zstd",
) -> None:
    ensure_dir(output_dir)
    df = _normalize_flags(df)
    table = pa.Table.from_pandas(df)
    if partition_cols:
        ds.write_dataset(
            table,
            output_dir,
            format="parquet",
            partitioning=partition_cols,
            existing_data_behavior="overwrite_or_ignore",
            file_options=pa.parquet.ParquetWriterOptions(compression=compression),
        )
    else:
        file_path = output_dir / "data.parquet"
        pq.write_table(table, file_path, compression=compression)


def read_parquet(path: Path) -> pd.DataFrame:
    if path.is_dir():
        dataset = ds.dataset(path, format="parquet")
        return dataset.to_table().to_pandas()
    return pd.read_parquet(path)
