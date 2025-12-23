from __future__ import annotations

import json
import math
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


def _resolve_config_batch_rows(config: Dict[str, Any], default_rows: int) -> int:
    parquet_cfg = (config.get("storage") or {}).get("parquet") or {}
    batch_rows = parquet_cfg.get("batch_rows")
    if batch_rows is None:
        env_value = os.getenv("PARQUET_BATCH_ROWS")
        if env_value:
            return int(env_value)
        return default_rows
    batch_rows = int(batch_rows)
    return batch_rows if batch_rows > 0 else default_rows


def _resolve_config_compression(config: Dict[str, Any]) -> str:
    parquet_cfg = (config.get("storage") or {}).get("parquet") or {}
    return parquet_cfg.get("compression", "zstd")


def _resolve_partition_cols(config: Dict[str, Any]) -> List[str]:
    parquet_cfg = (config.get("storage") or {}).get("parquet") or {}
    cols = parquet_cfg.get("partition_cols")
    if not cols:
        return []
    return [str(col) for col in cols]


def _partition_value(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float) and math.isnan(value):
        return "unknown"
    return str(value)


def _partition_dir(base: Path, partition_cols: List[str], key) -> Path:
    if not isinstance(key, tuple):
        key = (key,)
    part_dir = base
    for col, value in zip(partition_cols, key):
        part_dir = part_dir / f"{col}={_partition_value(value)}"
    return part_dir


def _derive_date_series(df: pd.DataFrame) -> pd.Series:
    if "ts_ms" in df.columns:
        ts = pd.to_datetime(df["ts_ms"], unit="ms", utc=True, errors="coerce")
    elif "starttime" in df.columns:
        ts = pd.to_datetime(df["starttime"], utc=True, errors="coerce")
    else:
        return pd.Series(["unknown"] * len(df), index=df.index)
    return ts.dt.strftime("%Y-%m-%d").fillna("unknown")


def _ensure_partition_cols(
    df: pd.DataFrame, partition_cols: List[str]
) -> tuple[pd.DataFrame, List[str]]:
    added_cols: List[str] = []
    if "date" in partition_cols and "date" not in df.columns:
        df = df.copy()
        df["date"] = _derive_date_series(df)
        added_cols.append("date")
    return df, added_cols


def _write_parquet_batched(
    df: pd.DataFrame,
    output_dir: Path,
    partition_cols: Optional[List[str]],
    compression: str,
    batch_rows: int,
) -> None:
    if df.empty:
        file_path = output_dir / "data.parquet"
        table = pa.Table.from_pandas(df, preserve_index=False)
        pq.write_table(table, file_path, compression=compression)
        return

    if partition_cols:
        if output_dir.exists():
            shutil.rmtree(output_dir)
        ensure_dir(output_dir)
        writers = {}
        try:
            for batch in _iter_batches(df, batch_rows):
                batch = _normalize_flags(batch).reset_index(drop=True)
                grouped = batch.groupby(partition_cols)
                for key, group in grouped:
                    part_dir = _partition_dir(output_dir, partition_cols, key)
                    ensure_dir(part_dir)
                    table = pa.Table.from_pandas(group, preserve_index=False)
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
            batch = _normalize_flags(batch).reset_index(drop=True)
            table = pa.Table.from_pandas(batch, preserve_index=False)
            if writer is None:
                writer = pq.ParquetWriter(file_path, table.schema, compression=compression)
            writer.write_table(table)
    finally:
        if writer is not None:
            writer.close()


def _write_parquet_file_batched(
    df: pd.DataFrame,
    file_path: Path,
    compression: str,
    batch_rows: int,
) -> None:
    writer = None
    try:
        for batch in _iter_batches(df, batch_rows):
            batch = _normalize_flags(batch).reset_index(drop=True)
            table = pa.Table.from_pandas(batch, preserve_index=False)
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
    if output_dir.suffix == ".parquet":
        ensure_dir(output_dir.parent)
        batch_rows = _resolve_batch_rows(batch_rows)
        if batch_rows > 0:
            _write_parquet_file_batched(df, output_dir, compression, batch_rows)
            return
        normalized = _normalize_flags(df)
        table = pa.Table.from_pandas(normalized, preserve_index=False)
        pq.write_table(table, output_dir, compression=compression)
        return

    ensure_dir(output_dir)
    if partition_cols and not set(partition_cols).issubset(df.columns):
        partition_cols = None
    batch_rows = _resolve_batch_rows(batch_rows)
    if batch_rows > 0:
        _write_parquet_batched(df, output_dir, partition_cols, compression, batch_rows)
        return

    try:
        normalized = _normalize_flags(df)
        table = pa.Table.from_pandas(normalized, preserve_index=False)
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


def write_parquet_partitioned(
    df: pd.DataFrame,
    output_dir: Path,
    config: Dict[str, Any],
    partition_cols: Optional[List[str]] = None,
    part_counters: Optional[Dict[Path, int]] = None,
) -> Dict[Path, int]:
    if df.empty:
        return part_counters or {}

    if partition_cols is None:
        partition_cols = _resolve_partition_cols(config)
    if not partition_cols:
        write_parquet_configured(df, output_dir, config, partition_cols=None)
        return part_counters or {}

    compression = _resolve_config_compression(config)
    batch_rows = _resolve_config_batch_rows(config, default_rows=200_000)
    batch_rows = max(int(batch_rows), 1)
    part_counters = part_counters or {}

    df_with_parts, added_cols = _ensure_partition_cols(df, partition_cols)
    grouped = df_with_parts.groupby(partition_cols, sort=False, dropna=False)
    for key, group in grouped:
        part_dir = _partition_dir(output_dir, partition_cols, key)
        ensure_dir(part_dir)
        if added_cols:
            group = group.drop(columns=added_cols, errors="ignore")
        for batch in _iter_batches(group, batch_rows):
            batch = _normalize_flags(batch).reset_index(drop=True)
            table = pa.Table.from_pandas(batch, preserve_index=False)
            counter = part_counters.get(part_dir, 0)
            file_path = part_dir / f"part-{counter:05d}.parquet"
            part_counters[part_dir] = counter + 1
            pq.write_table(table, file_path, compression=compression)
    return part_counters


def read_parquet(path: Path) -> pd.DataFrame:
    if path.is_dir():
        dataset = ds.dataset(path, format="parquet", partitioning="hive")
        return dataset.to_table().to_pandas()
    return pd.read_parquet(path)


def read_parquet_filtered(
    path: Path,
    filters: Optional[ds.Expression] = None,
    columns: Optional[List[str]] = None,
    limit: Optional[int] = None,
) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    if path.is_dir():
        dataset = ds.dataset(path, format="parquet", partitioning="hive")
        if columns:
            available = [col for col in columns if col in dataset.schema.names]
            if not available:
                return pd.DataFrame()
            columns = available
        scanner = dataset.scanner(columns=columns, filter=filters)
        if limit is not None and limit > 0:
            batches = []
            remaining = int(limit)
            for batch in scanner.to_batches():
                if remaining <= 0:
                    break
                if batch.num_rows > remaining:
                    batch = batch.slice(0, remaining)
                batches.append(batch)
                remaining -= batch.num_rows
            if not batches:
                return pd.DataFrame(columns=columns or dataset.schema.names)
            table = pa.Table.from_batches(batches)
            return table.to_pandas()
        return scanner.to_table().to_pandas()
    return pd.read_parquet(path, columns=columns)
