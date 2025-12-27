# Module Deep Dive: io.iaga2002

Purpose / Reader / Takeaways:
- Purpose: define how IAGA2002 geomag/AEF files are parsed.
- Reader: developers validating raw ingestion or adjusting parsing rules.
- Takeaways: header parsing, data columns, sentinel handling.

## Responsibilities
- Parse IAGA2002 header fields (station id, lat, lon, elev, reported).
- Read data rows and produce long-table records with `ts_ms` and `quality_flags`.
- Scan files to compute start/end time and sampling interval.
- [EVIDENCE] src/io/iaga2002.py:L10-L211

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| IAGA2002 text file | Lines with header + `DATE TIME` columns. | - [EVIDENCE] src/io/iaga2002.py:L28-L33 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| DataFrame | Columns include `ts_ms`, `station_id`, `channel`, `value`, lat/lon/elev, flags. | - [EVIDENCE] src/io/iaga2002.py:L83-L105 |
| Scan metadata | `start_ms`, `end_ms`, `interval_s`, `file_path`, etc. | - [EVIDENCE] src/io/iaga2002.py:L166-L211 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_parse_header` | Extract station/location metadata. | - [EVIDENCE] src/io/iaga2002.py:L10-L25 |
| `_find_data_start` | Locate header line with `DATE`/`TIME`. | - [EVIDENCE] src/io/iaga2002.py:L28-L33 |
| `_is_sentinel` | Identify missing/sentinel values (>=88888). | - [EVIDENCE] src/io/iaga2002.py:L35-L39 |
| `parse_iaga_file` | Parse file into long-table records. | - [EVIDENCE] src/io/iaga2002.py:L64-L105 |
| `scan_iaga_file` | Compute file bounds and interval. | - [EVIDENCE] src/io/iaga2002.py:L166-L211 |
| `read_iaga_window` | Windowed read for raw query. | - [EVIDENCE] src/io/iaga2002.py:L214-L259 |

## Error Handling / Edge Cases
- Missing header raises `ValueError`.
  - [EVIDENCE] src/io/iaga2002.py:L28-L33
  - [EVIDENCE] src/io/iaga2002.py:L130-L133
- Sentinel values are converted to `None` and flagged in `quality_flags`.
  - [EVIDENCE] src/io/iaga2002.py:L35-L39
  - [EVIDENCE] src/io/iaga2002.py:L88-L99

## Performance Notes
- Parsing reads entire file into memory via pandas `read_csv`.
  - [EVIDENCE] src/io/iaga2002.py:L72-L73

## Verification
- Unit test validates channel parsing and sentinel handling.
  - [EVIDENCE] tests/test_iaga_parser.py:L9-L21
