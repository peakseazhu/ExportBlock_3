# Module Deep Dive: io.vlf

Purpose / Reader / Takeaways:
- Purpose: define how VLF CDF files are read and normalized.
- Reader: developers adjusting VLF ingest or API slice logic.
- Takeaways: expected CDF variables and pad handling.

## Responsibilities
- Read VLF CDF variables and convert to arrays (`epoch_ns`, `freq_hz`, `ch1`, `ch2`).
- Extract station ID from filename.
- Compute gap report based on median time delta.
- [EVIDENCE] src/io/vlf.py:L12-L59

## Inputs
| Input | Description | Evidence |
| --- | --- | --- |
| CDF file | Expects variables `epoch_vlf`, `freq_vlf`, `ch1`, `ch2`. | - [EVIDENCE] src/io/vlf.py:L19-L25 |

## Outputs
| Output | Description | Evidence |
| --- | --- | --- |
| Payload dict | `station_id`, `epoch_ns`, `freq_hz`, `ch1`, `ch2`. | - [EVIDENCE] src/io/vlf.py:L39-L46 |
| Gap report | `gap_count`, `gap_indices`, `dt_median_s`. | - [EVIDENCE] src/io/vlf.py:L49-L59 |

## Key Functions
| Function | Role | Evidence |
| --- | --- | --- |
| `_station_from_name` | Extract station ID from filename (`vlf_<id>_`). | - [EVIDENCE] src/io/vlf.py:L12-L16 |
| `read_vlf_cdf` | Read CDF variables and sanitize pad values. | - [EVIDENCE] src/io/vlf.py:L19-L46 |
| `compute_gap_report` | Compute time-gap diagnostics. | - [EVIDENCE] src/io/vlf.py:L49-L59 |

## Error Handling / Edge Cases
- If PadValue exists, it is replaced with NaN in ch1/ch2.
  - [EVIDENCE] src/io/vlf.py:L29-L37
- `compute_gap_report` returns zero gaps when fewer than 2 time points exist.
  - [EVIDENCE] src/io/vlf.py:L49-L52

## Performance Notes
- Epoch conversion uses vectorized datetime conversion and numpy arrays.
  - [EVIDENCE] src/io/vlf.py:L26-L28

## Verification
- Unit test verifies pad value handling and station ID parsing.
  - [EVIDENCE] tests/test_vlf_reader.py:L11-L43
