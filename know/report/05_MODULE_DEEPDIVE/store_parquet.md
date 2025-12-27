# Module Deep Dive: store.parquet

Purpose / Reader / Takeaways:
- Purpose: document parquet I/O utilities and partitioning behavior.
- Reader: developers working on storage or performance tuning.
- Takeaways: batching, partitioning, and quality_flags serialization.

## Responsibilities
- Write parquet datasets with optional partitioning and batching.
- Serialize `quality_flags` dicts to JSON strings before write.
- Read full datasets or filtered subsets.
- [EVIDENCE] src/store/parquet.py:L18-L315

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| DataFrame | Long-table rows with optional `quality_flags`. | - [EVIDENCE] src/store/parquet.py:L18-L24 |
| `storage.parquet.*` | Compression, partition columns, batch rows. | - [EVIDENCE] src/store/parquet.py:L41-L63 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| Parquet dataset | Partitioned hive layout if partition cols set. | - [EVIDENCE] src/store/parquet.py:L174-L217 |
| Partition files | `part-00000.parquet` when using custom partitioned writer. | - [EVIDENCE] src/store/parquet.py:L239-L274 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_normalize_flags` | Convert `quality_flags` dicts to JSON strings. | - [EVIDENCE] src/store/parquet.py:L18-L24 |
| `write_parquet` | Main write routine (batched or dataset). | - [EVIDENCE] src/store/parquet.py:L174-L217 |
| `write_parquet_partitioned` | Custom partitioned writer with batching. | - [EVIDENCE] src/store/parquet.py:L239-L274 |
| `read_parquet_filtered` | Predicate pushdown + limit support. | - [EVIDENCE] src/store/parquet.py:L284-L314 |

## Error Handling / Edge Cases
- If DataFrame is empty, writes a single parquet file with empty schema.
  - [EVIDENCE] src/store/parquet.py:L111-L115
- When memory errors occur, writes in batches with default batch size.
  - [EVIDENCE] src/store/parquet.py:L217-L218

## Performance Notes
- Batch size is configurable via `storage.parquet.batch_rows` or env `PARQUET_BATCH_ROWS`.
  - [EVIDENCE] src/store/parquet.py:L32-L48
- `date` partition is derived from `ts_ms` or `starttime` when requested.
  - [EVIDENCE] src/store/parquet.py:L83-L101

## Verification
- Test validates partitioned batch write and read.
  - [EVIDENCE] tests/test_parquet_batch.py:L8-L20
