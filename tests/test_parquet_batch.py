from pathlib import Path

import pandas as pd

from src.store.parquet import read_parquet, write_parquet


def test_write_parquet_partitioned_batch(tmp_path: Path) -> None:
    df = pd.DataFrame(
        [
            {"ts_ms": i, "source": "a" if i % 2 == 0 else "b", "value": float(i)}
            for i in range(20)
        ]
    )
    output_dir = tmp_path / "partitioned"
    write_parquet(df, output_dir, partition_cols=["source"], batch_rows=3)

    reloaded = read_parquet(output_dir)
    assert len(reloaded) == len(df)
    assert set(reloaded["source"].unique()) == {"a", "b"}
