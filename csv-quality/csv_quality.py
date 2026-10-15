"""Synthetic engineering-CSV quality demo. Standard library only; no network."""
import argparse
from collections import Counter
import csv
from datetime import date
from decimal import Decimal, InvalidOperation
import html
import json
from pathlib import Path
import re
import sys

REQUIRED = ("record_id", "observed_on", "sensor_id", "reading", "unit")
OPTIONAL = ("notes",)
CATEGORIES = (
    "missing_required_columns", "blank_required_cells", "duplicate_record_id",
    "invalid_typed_values", "unexpected_columns",
)
DECIMAL_PATTERN = re.compile(r"[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)(?:[eE][+-]?[0-9]+)?")


def same_file(left, right):
    try:
        return left.samefile(right)
    except OSError:
        return left.resolve() == right.resolve()


def validate_input_list(paths):
    if not 1 <= len(paths) <= 10:
        raise ValueError("Provide between one and ten CSV input files.")
    for index, path in enumerate(paths):
        if any(same_file(path, earlier) for earlier in paths[:index]):
            raise ValueError("Do not list the same input file more than once.")


def typed_value_ok(column, value):
    if column == "observed_on":
        try:
            return date.fromisoformat(value).isoformat() == value
        except ValueError:
            return False
    if not DECIMAL_PATTERN.fullmatch(value):
        return False
    try:
        return Decimal(value).is_finite()
    except InvalidOperation:
        return False


def inspect_inputs(paths):
    """Inspect synthetic fixtures without writing to source files or coercing cells."""
    paths = [Path(path) for path in paths]
    validate_input_list(paths)
    findings, input_errors, files, records = [], [], [], []
    seen_ids = {}

    def finding(category, location, message, **details):
        findings.append(dict(category=category, **location, message=message, **details))

    for file_index, path in enumerate(paths, 1):
        location = dict(file_index=file_index, file=path.name)
        stats = dict(**location, records_seen=0, records_checked=0)
        files.append(stats)
        try:
            with path.open("r", encoding="utf-8-sig", newline="") as stream:
                reader = csv.reader(stream, strict=True)
                header = next(reader, None)
                if header is None or not header or any(not cell.strip() for cell in header):
                    input_errors.append(dict(**location, message="Missing header or blank header name."))
                    continue
                if len(set(header)) != len(header):
                    input_errors.append(dict(**location, message="Duplicate header names are ambiguous; file skipped."))
                    continue
                stats["columns"] = header
                missing = [column for column in REQUIRED if column not in header]
                unexpected = [column for column in header if column not in REQUIRED + OPTIONAL]
                if missing:
                    finding("missing_required_columns", location, "Required columns are absent.", columns=missing)
                if unexpected:
                    finding("unexpected_columns", location, "Columns outside the documented schema.", columns=unexpected)
                for record_number, cells in enumerate(reader, 1):
                    stats["records_seen"] += 1
                    row_location = dict(**location, record_number=record_number, line_end=reader.line_num)
                    if len(cells) != len(header):
                        input_errors.append(dict(**row_location,
                            message=f"Expected {len(header)} cells, received {len(cells)}; record skipped."))
                        continue
                    values = dict(zip(header, cells))
                    stats["records_checked"] += 1
                    records.append(dict(**row_location, values=values))
                    for column in REQUIRED:
                        if column not in values:
                            continue  # Report missing headers once, without inventing cells.
                        value = values[column]
                        if not value.strip():
                            finding("blank_required_cells", row_location, "Required cell is empty or whitespace-only.",
                                    column=column, value=value)
                        elif column in ("observed_on", "reading") and not typed_value_ok(column, value):
                            expected = "exact YYYY-MM-DD calendar date" if column == "observed_on" else "finite decimal literal"
                            finding("invalid_typed_values", row_location, f"Expected {expected}; raw text retained.",
                                    column=column, value=value)
                    record_id = values.get("record_id", "")
                    if record_id.strip():
                        if record_id in seen_ids:
                            finding("duplicate_record_id", row_location, "record_id was already seen in this batch.",
                                    column="record_id", value=record_id, first_occurrence=seen_ids[record_id])
                        else:
                            seen_ids[record_id] = row_location
        except (OSError, UnicodeError, csv.Error) as exc:
            message = exc.strerror if isinstance(exc, OSError) else str(exc)
            input_errors.append(dict(**location, error_type=type(exc).__name__, message=message))
    counts = Counter(item["category"] for item in findings)
    status = "input_error" if input_errors else "quality_findings" if findings else "pass"
    return dict(
        report_type="synthetic_engineering_csv_quality_demo", schema_version="1.0",
        data_classification="SYNTHETIC FIXTURES ONLY - NO CUSTOMER DATA",
        limitations="Method demonstration only; no client delivery, business demand, financial or physical validation established.",
        status=status, file_count=len(files), records_checked=len(records),
        finding_count=len(findings), rule_counts={category: counts[category] for category in CATEGORIES},
        input_errors=input_errors, files=files, findings=findings, records=records,
    )


def render_html(report):
    def esc(value):
        return html.escape(str(value), quote=True)

    def raw(value):
        return esc(json.dumps(value, ensure_ascii=False, indent=2))

    count_rows = "".join(f"<tr><td>{esc(category)}</td><td>{count}</td></tr>"
                         for category, count in report["rule_counts"].items())
    finding_rows = "".join(
        f"<tr><td>{esc(item['category'])}</td><td>{esc(item['file'])} / file {item['file_index']}"
        f" / record {item.get('record_number', 'header')}</td><td><pre>{raw(item)}</pre></td></tr>"
        for item in report["findings"])
    record_rows = "".join(
        f"<tr><td>{esc(item['file'])} / file {item['file_index']} / record {item['record_number']}"
        f" / ending line {item['line_end']}</td><td><pre>{raw(item['values'])}</pre></td></tr>"
        for item in report["records"])
    errors = "".join(f"<li><pre>{raw(item)}</pre></li>" for item in report["input_errors"])
    return f"""<!doctype html>
<html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Synthetic CSV quality report</title>
<style>body{{font:16px/1.55 system-ui,sans-serif;color:#193333;background:#f5f7f5;margin:0}}
main{{max-width:1100px;margin:auto;padding:32px 20px 60px}}h1{{line-height:1.2}}h2{{margin-top:32px}}
.banner{{background:#fff0ba;border:1px solid #b88d20;padding:16px}}.card{{background:white;padding:18px;border:1px solid #d2dfd8;margin:20px 0}}
table{{border-collapse:collapse;width:100%;background:white}}td,th{{text-align:left;vertical-align:top;padding:12px;border:1px solid #d2dfd8}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;font:13px/1.5 ui-monospace,monospace;margin:0}}.scroll{{overflow-x:auto}}small{{color:#47635c}}</style>
<main><div class="banner"><b>SYNTHETIC DATA · METHOD DEMO</b><br>{esc(report['data_classification'])}</div>
<h1>Engineering CSV quality report</h1><p>{esc(report['limitations'])}</p>
<div class="card"><b>Status: {esc(report['status'])}</b><br>{report['file_count']} input files · {report['records_checked']} records checked · {report['finding_count']} quality findings · {len(report['input_errors'])} input errors</div>
<p>Five documented rules. No automatic correction, unit conversion, imputation or numeric coercion. All cell values below remain strings. A pass covers these checks only.</p>
<h2>Rule counts</h2><div class="scroll"><table><tr><th>Category</th><th>Findings</th></tr>{count_rows}</table></div>
<h2>Input errors</h2>{'<ul>' + errors + '</ul>' if errors else '<p>None.</p>'}
<h2>Findings</h2>{'<div class="scroll"><table><tr><th>Category</th><th>Location</th><th>Evidence</th></tr>' + finding_rows + '</table></div>' if finding_rows else '<p>No findings under the documented rules.</p>'}
<h2>Raw parsed records</h2><p>Record numbers count CSV records after the header; ending lines count physical lines, including quoted newlines. Header defects are reported once per file. File numbers disambiguate repeated basenames.</p>
<div class="scroll"><table><tr><th>Location</th><th>Unmodified cell strings</th></tr>{record_rows}</table></div>
<p><small>Standalone report; no external scripts, fonts, analytics or network requests.</small></p></main></html>"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--synthetic", required=True, action="store_true",
                        help="Confirm all inputs are synthetic fixtures for this method demo.")
    parser.add_argument("--json", dest="json_path", type=Path, default=Path("results.json"))
    parser.add_argument("--html", dest="html_path", type=Path, default=Path("sample-report.html"))
    args = parser.parse_args(argv)
    try:
        validate_input_list(args.inputs)
        outputs = (args.json_path, args.html_path)
        if same_file(*outputs) or any(same_file(output, source) for output in outputs for source in args.inputs):
            raise ValueError("Outputs must differ from each other and every source input; source files are read-only.")
    except ValueError as exc:
        parser.error(str(exc))
    report = inspect_inputs(args.inputs)
    try:
        for output in outputs:
            output.parent.mkdir(parents=True, exist_ok=True)
        args.json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        args.html_path.write_text(render_html(report), encoding="utf-8")
    except OSError as exc:
        print(f"Output error: {exc}", file=sys.stderr)
        return 2
    print(f"SYNTHETIC demo: {report['status']}; {report['records_checked']} records; {report['finding_count']} findings; {len(report['input_errors'])} input errors.")
    return 2 if report["input_errors"] else 1 if report["findings"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
