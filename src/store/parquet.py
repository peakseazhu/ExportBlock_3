from __future__ import annotations

import json
import os
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

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


def _iter_batches(df: pd.DataFrame, batch_rows: int):
    for start in range(0, len(df), batch_rows):
        yield df.iloc[start : start + batch_rows]


def _resolve_batch_rows(batch_rows: Optional[int]) -> int:
    if batch_rows is not None:
        return int(batch_rows)
    env_value = os.getenv("PARQUET_BATCH_ROWS")
    if env_value:
        return int(env_value)
    return 0


def _partition_dir(base: Path, partition_cols: List[str], key) -> Path:
    if not isinstance(key, tuple):
        key = (key,)
    part_dir = base
    for col, value in zip(partition_cols, key):
        part_dir = part_dir / f"{col}={value}"
    return part_dir


def _write_parquet_batched(
    df: pd.DataFrame,
    output_dir: Path,
    partition_cols: Optional[List[str]],
    compression: str,
    batch_rows: int,
) -> None:
    if df.empty:
        file_path = output_dir / "data.parquet"
        table = pa.Table.from_pandas(df)
        pq.write_table(table, file_path, compression=compression)
        return

    if partition_cols:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        ensure_dir(output_dir)
        writers = {}
        try:
            for batch in _iter_batches(df, batch_rows):
                batch = _normalize_flags(batch)
                grouped = batch.groupby(partition_cols)
                for key, group in grouped:
                    part_dir = _partition_dir(output_dir, partition_cols, key)
                    ensure_dir(part_dir)
                    table = pa.Table.from_pandas(group)
                    writer = writers.get(part_dir)
                    if writer is None:
                        file_path = part_dir / "data.parquet"
                        writer = pq.ParquetWriter(file_path, table.schema, compression=compression)
                        writers[part_dir] = writer
                    writer.write_table(table)
        finally:
            for writer in writers.values():
                writer.close()
        return

    file_path = output_dir / "data.parquet"
    writer = None
    try:
        for batch in _iter_batches(df, batch_rows):
            batch = _normalize_flags(batch)
            table = pa.Table.from_pandas(batch)
            if writer is None:
                writer = pq.ParquetWriter(file_path, table.schema, compression=compression)
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()


def write_parquet(
    df: pd.DataFrame,
    output_dir: Path,
    partition_cols: Optional[List[str]] = None,
    compression: str = "zstd",
    batch_rows: Optional[int] = None,
) -> None:
    ensure_dir(output_dir)
    if partition_cols and not set(partition_cols).issubset(df.columns):
        partition_cols = None
    batch_rows = _resolve_batch_rows(batch_rows)
    if batch_rows > 0:
        _write_parquet_batched(df, output_dir, partition_cols, compression, batch_rows)
        return

    try:
        normalized = _normalize_flags(df)
        table = pa.Table.from_pandas(normalized)
        if partition_cols:
            file_options = ds.ParquetFileFormat().make_write_options(compression=compression)
            ds.write_dataset(
                table,
                output_dir,
                format="parquet",
                partitioning=partition_cols,
                partitioning_flavor="hive",
                existing_data_behavior="overwrite_or_ignore",
                file_options=file_options,
            )
        else:
            file_path = output_dir / "data.parquet"
            pq.write_table(table, file_path, compression=compression)
    except (pa.ArrowMemoryError, MemoryError):
        _write_parquet_batched(df, output_dir, partition_cols, compression, 200_000)


def write_parquet_configured(
    df: pd.DataFrame,
    output_dir: Path,
    config: Dict[str, Any],
    partition_cols: Optional[List[str]] = None,
) -> None:
    parquet_cfg = (config.get("storage") or {}).get("parquet") or {}
    compression = parquet_cfg.get("compression", "zstd")
    batch_rows = parquet_cfg.get("batch_rows")
    write_parquet(
        df,
        output_dir,
        partition_cols=partition_cols,
        compression=compression,
        batch_rows=batch_rows,
    )


def read_parquet(path: Path) -> pd.DataFrame:
    if path.is_dir():
        dataset = ds.dataset(path, format="parquet", partitioning="hive")
        return dataset.to_table().to_pandas()
    return pd.read_parquet(path)
