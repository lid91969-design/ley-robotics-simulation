# Synthetic engineering CSV quality demo

This is a runnable method demonstration using invented measurements. It contains no customer data, client results, revenue evidence or validated business demand. It does not validate physical measurements. Python 3.10+ and the standard library are sufficient; no installation, model, server or network is needed.

## Run

From this directory:

```powershell
python -B csv_quality.py --synthetic fixtures/good.csv fixtures/faulty.csv --json results.json --html sample-report.html
```

The intentionally faulty batch exits **1**, while still writing both reports. Open `sample-report.html` directly in a browser. The saved sample is this two-file batch. To check the good fixture alone without replacing the saved sample:

```powershell
python -B csv_quality.py --synthetic fixtures/good.csv --json good-results.json --html good-report.html
```

Exit codes: **0** = no findings under the documented rules; **1** = quality findings; **2** = usage, output, unreadable-file or malformed-input error. An input error makes the audit incomplete even if other rows were checked. `--synthetic` is a required declaration that the inputs are synthetic fixtures; this demo is not a customer-data ingestion service.

## One supported format

UTF-8 CSV, optionally with an initial UTF-8 BOM; comma delimiter and standard double-quoted fields, including escaped quotes and embedded newlines. Read one to ten distinct input files in the supplied order. Source inputs are opened read-only. Repeated paths, symlink/hardlink aliases and outputs that overlap inputs are rejected.

Required, case-sensitive columns (any order):

| Column | Meaning and exact check |
|---|---|
| `record_id` | Nonblank text; unique within the entire batch. `0002` remains text and differs from `2`. |
| `observed_on` | A real calendar date written exactly `YYYY-MM-DD`; compact and week-date variants are rejected. |
| `sensor_id` | Nonblank text. No external sensor registry is checked. |
| `reading` | Finite decimal literal: optional sign, decimal digits/point and optional exponent, using ASCII digits. `23.50`, `.5`, `1.` and `1.02e2` are accepted; `NaN`, infinity, commas, underscores and surrounding spaces are rejected. Values remain raw strings, with no float conversion or rounding. |
| `unit` | Nonblank text; units are not interpreted or converted. |

Optional known column: `notes`, unrestricted text, including blank values. No other columns are expected. Cell text and headers are not trimmed or normalized; only the blank-cell check treats whitespace-only text as blank. For example, `0002` and ` 0002` are distinct nonblank IDs. No implicit date repair, locale interpretation, unit conversion or imputation occurs.

Duplicate or blank header names, an empty file, invalid UTF-8, errors raised by Python's strict CSV parser, and records with a different field count are **input errors**, not extra quality-rule categories. This uses Python's CSV dialect and is not a full RFC conformance validator. Ambiguous headers skip the file; wrong-width records are skipped and reported. Checks already completed are retained, with `status: input_error`. Missing required headers are quality findings; other available columns are still checked without inventing missing cells.

## Five quality-rule categories

1. `missing_required_columns`: one finding per file listing absent required headers.
2. `blank_required_cells`: one finding per blank available required cell.
3. `duplicate_record_id`: one finding for each occurrence after the first, across and within files; includes the first location. IDs are compared as exact raw text.
4. `invalid_typed_values`: one finding per nonblank invalid `observed_on` or `reading`. Blank values receive only the blank-cell finding.
5. `unexpected_columns`: one finding per file listing unexpected headers.

Record numbers count CSV records after the header; `line_end` is the physical ending line, including embedded newlines. Reports use input ordinal and basename, without absolute local paths. JSON retains all successfully parsed records as string-valued objects. HTML escapes all dynamic data and embeds its styles; it has no scripts, remote assets or analytics.

## Acceptance and observed sample

- Good fixture alone: 2 checked records, 0 findings, 0 input errors, status `pass`.
- Good + faulty in that order: 5 checked records, 9 findings, 0 input errors, status `quality_findings`.
- Counts: missing columns **1**, blank required cells **2**, duplicate IDs **1**, invalid typed values **4**, unexpected columns **1**.
- Duplicate `0002` references the good fixture's second record; it is not converted to number `2`.
- The script-like text in the good fixture must display as text in HTML and retain its original string in JSON.
- Running the CLI leaves source bytes unchanged. A pass establishes these checks only, not engineering correctness or business demand.

Focused verification:

```powershell
python -B -m unittest -v test_csv_quality
```

Scope: local synthetic fixtures only. No production integration, customer-specific accuracy, performance at large scale, database/API support or paid delivery is claimed.
