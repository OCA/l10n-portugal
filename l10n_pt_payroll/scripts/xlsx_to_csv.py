#!/usr/bin/env python3
# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
"""Convert the official Portuguese IRS withholding workbooks into the
CSV format bundled under ``data/irs/`` and consumed by the import
wizard.

The Autoridade Tributária publishes one Excel file per region and year
on the Portal das Finanças doclib::

    https://info.portaldasfinancas.gov.pt/pt/apoio_contribuinte/tabela_ret_doclib/Pages/default.aspx

Typical names::

    Tabelas_RF_Continente_2026.xlsx
    Tabelas_RF_2026_RAM.xlsx          (Madeira)
    Tabelas_RF_RA_Acores_2026.xlsx

Workbook layout (verified against the 2026 files):

- One worksheet per income category: ``Categoria A`` holds the work
  tables I-VII, ``Categoria H`` the pension tables VIII-XI.
- Each table starts with a ``Tabela <roman> - ...`` marker row,
  followed by a header row (``Remuneração mensal``,
  ``Taxa marginal máxima``, ``Parcela a abater``, optional
  ``Parcela adicional a abater por dependente`` or ``... por Deficiente
  das Forças Armadas``, ``Taxa efetiva ...``) and the bracket rows.
- Bracket rows carry ``Até``/``Superior a`` in column B and the upper
  bound in C; the lower bound is the previous row's upper bound.
- Marginal rates and effective rates are fractions (0.125 = 12.5%);
  the converter emits them as percentages.
- ``Parcela a abater`` may be a number in column F or a formula
  spread over F:K using ``x`` as the multiplication sign.
- The Despacho period constants (IAS, disabled-dependent, disabled
  spouse and pension-dependent amounts) are NOT in the workbook; pass
  them with ``--set-json``.

Usage::

    # Discover the workbook layout (run this first on a new file):
    python3 scripts/xlsx_to_csv.py inspect Tabelas_RF_Continente_2026.xlsx

    # Convert to the module CSV format:
    python3 scripts/xlsx_to_csv.py convert Tabelas_RF_Continente_2026.xlsx \
        --region continente --year 2026 --ias 537.13 \
        --set-json set_values.json -o data/irs/2026_continente.csv

Requires ``openpyxl`` (``pip install openpyxl``).
"""

# Standalone developer CLI, not Odoo code: stdout is the interface.
# pylint: disable=print-used
import argparse
import csv
import json
import re
import sys

try:
    import openpyxl
except ImportError:  # pragma: no cover - environment issue
    sys.exit("openpyxl is required: pip install openpyxl")

CSV_FIELDS = [
    "date_start",
    "date_end",
    "region",
    "table_code",
    "lower_bound",
    "upper_bound",
    "marginal_rate",
    "parcela_abater",
    "dependent_parcela",
    "forces_disabled_parcela",
    "effective_rate_limit",
    "ias",
    "disabled_dep_parcela_single",
    "disabled_dep_parcela_joint",
    "spouse_disabled_parcela",
    "pension_dep_parcela_single",
    "pension_dep_parcela_joint",
    "pension_dep_parcela_single_income",
]
SET_FIELDS = CSV_FIELDS[11:]

REGIONS = ("continente", "acores", "madeira")
# Official table variants I..XI in Despacho order.
TABLE_CODES = ("I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X", "XI")

# Roman numeral after the word "tabela" marks each table variant;
# longest numerals first so "viii" wins over "v"/"i".
_TABLE_CODE_RE = re.compile(r"\btabela\s+(viii|ix|xi|vii|iv|vi|iii|ii|v|x|i)\b")
_ROMAN_TO_CODE = {
    "i": "I",
    "ii": "II",
    "iii": "III",
    "iv": "IV",
    "v": "V",
    "vi": "VI",
    "vii": "VII",
    "viii": "VIII",
    "ix": "IX",
    "x": "X",
    "xi": "XI",
}


def _cell_text(value):
    """Return the stripped text of a cell, or "" for empty cells."""
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def _norm_number(text):
    """Normalize a Portuguese/international number to a plain float.

    Returns None when the text is not numeric.
    """
    text = _cell_text(text)
    if not text:
        return None
    cleaned = text.replace("%", "").replace("\u00a0", "").replace(" ", "")
    if "," in cleaned and "." in cleaned:
        cleaned = cleaned.replace(".", "").replace(",", ".")
    elif "," in cleaned:
        cleaned = cleaned.replace(",", ".")
    try:
        return float(cleaned)
    except ValueError:
        return None


def _fmt_number(value):
    """Format a float without trailing zeros for CSV output."""
    if value is None:
        return ""
    rounded = round(value, 4)
    if rounded == int(rounded):
        return str(int(rounded))
    return f"{rounded:g}"


def _norm_expression(cells):
    """Join the parcela a abater cells (F:K) into a safe_eval string.

    "0.125" "x" "2.6" "x (" "1273.85" "- R )" becomes
    "0.125 * 2.6 * (1273.85 - R)".
    """
    text = " ".join(_cell_text(cell) for cell in cells if _cell_text(cell))
    text = re.sub(r"\bx\b", "*", text)
    return re.sub(r"\s+", " ", text).strip()


def cmd_inspect(args):
    """Dump the non-empty cells of every worksheet to learn the layout."""
    workbook = openpyxl.load_workbook(args.workbook, data_only=True)
    for sheet in workbook.worksheets:
        print(
            f"=== sheet: {sheet.title} "
            f"(dims {sheet.dimensions}, max_row={sheet.max_row}, "
            f"max_col={sheet.max_column}) ==="
        )
        for row in sheet.iter_rows():
            cells = [
                f"{cell.coordinate}={_cell_text(cell.value)!r}"
                for cell in row
                if _cell_text(cell.value)
            ]
            if cells:
                print("  " + " | ".join(cells))
        print()


def _find_table_sections(sheet):
    """Locate the marker row of each table variant on a worksheet.

    Returns {code: row_index} using 1-based row numbers.
    """
    sections = {}
    for idx, row in enumerate(sheet.iter_rows(), start=1):
        text = " ".join(
            _cell_text(cell.value).lower() for cell in row if _cell_text(cell.value)
        )
        match = _TABLE_CODE_RE.search(text)
        if match:
            sections.setdefault(_ROMAN_TO_CODE[match.group(1)], idx)
    return sections


def _column_index(header_cells, needle):
    """0-based column index of the header cell containing ``needle``."""
    for idx, cell in enumerate(header_cells):
        if needle in _cell_text(cell.value).lower():
            return idx
    return None


def _extract_table(sheet, marker_row):
    """Extract one table variant starting at its marker row.

    Returns a list of bracket dicts in official order.
    """
    rows = list(sheet.iter_rows(min_row=marker_row))
    header_idx = None
    for offset, row in enumerate(rows):
        if _column_index(row, "remunera") is not None:
            header_idx = offset
            header = row
            break
    if header_idx is None:
        return []
    col_upper = _column_index(header, "remunera")
    # The upper bound is the numeric cell right of the "Remuneração"
    # label column (column C when B holds Até/Superior a).
    col_rate = _column_index(header, "taxa marginal")
    col_parcela = _column_index(header, "parcela a abater")
    col_dep = _column_index(header, "por dependente")
    col_forces = _column_index(header, "forças armadas")
    col_effective = _column_index(header, "taxa efetiva")
    if col_rate is None or col_parcela is None:
        return []
    brackets = []
    lower = 0.0
    for row in rows[header_idx + 1 :]:
        label = _cell_text(row[1].value).lower() if len(row) > 1 else ""
        if label not in ("até", "superior a"):
            if brackets:
                break
            continue
        # "Superior a" marks the open-ended last bracket: its bound is
        # the lower bound, not an upper one.
        upper = (
            None if label == "superior a" else _norm_number(row[col_upper + 1].value)
        )
        if upper is None and label == "até":
            if brackets:
                break
            continue
        rate = _norm_number(row[col_rate].value)
        parcela_cells = [cell.value for cell in row[col_parcela : col_parcela + 6]]
        parcela_text = _norm_expression(parcela_cells)
        parcela_num = _norm_number(parcela_text)
        dependent = _norm_number(row[col_dep].value) if col_dep is not None else None
        forces = _norm_number(row[col_forces].value) if col_forces is not None else None
        effective = (
            _norm_number(row[col_effective].value)
            if col_effective is not None
            else None
        )
        brackets.append(
            {
                "lower_bound": lower,
                "upper_bound": upper,
                "marginal_rate": None if rate is None else rate * 100,
                "parcela_abater": (
                    _fmt_number(parcela_num)
                    if parcela_num is not None
                    else parcela_text
                ),
                "dependent_parcela": dependent,
                "forces_disabled_parcela": forces,
                "effective_rate_limit": (
                    None if effective is None else effective * 100
                ),
            }
        )
        if upper is not None:
            lower = upper
    return brackets


def _load_set_values(args):
    values = {}
    if args.set_json:
        with open(args.set_json, encoding="utf-8") as set_file:
            values = json.load(set_file)
    unknown = set(values) - set(SET_FIELDS)
    if unknown:
        sys.exit(f"unknown set-value keys: {sorted(unknown)}")
    if args.ias:
        values["ias"] = args.ias
    return values


def cmd_convert(args):
    """Convert the workbook into the module's normalized CSV format."""
    workbook = openpyxl.load_workbook(args.workbook, data_only=True)
    set_values = _load_set_values(args)
    out_rows = []
    found = set()
    for sheet in workbook.worksheets:
        if args.sheet and sheet.title != args.sheet:
            continue
        sections = _find_table_sections(sheet)
        for code, marker_row in sorted(sections.items(), key=lambda i: i[1]):
            brackets = _extract_table(sheet, marker_row)
            if not brackets:
                print(
                    f"warning: no brackets found for table {code} "
                    f"on sheet {sheet.title!r}",
                    file=sys.stderr,
                )
                continue
            found.add(code)
            for bracket in brackets:
                row = {
                    "date_start": f"{args.year}-01-01",
                    "date_end": f"{args.year}-12-31",
                    "region": args.region,
                    "table_code": code,
                    "lower_bound": _fmt_number(bracket["lower_bound"]),
                    "upper_bound": _fmt_number(bracket["upper_bound"]),
                    "marginal_rate": _fmt_number(bracket["marginal_rate"]),
                    "parcela_abater": bracket["parcela_abater"],
                    "dependent_parcela": _fmt_number(bracket["dependent_parcela"]),
                    "forces_disabled_parcela": _fmt_number(
                        bracket["forces_disabled_parcela"]
                    ),
                    "effective_rate_limit": _fmt_number(
                        bracket["effective_rate_limit"]
                    ),
                }
                for field in SET_FIELDS:
                    row[field] = set_values.get(field, "")
                out_rows.append(row)
    missing = set(TABLE_CODES) - found
    if missing:
        print(
            f"warning: table variants not found: {sorted(missing)}",
            file=sys.stderr,
        )
    output = (
        sys.stdout
        if args.output == "-"
        else open(args.output, "w", newline="", encoding="utf-8")
    )
    writer = csv.DictWriter(output, fieldnames=CSV_FIELDS)
    writer.writeheader()
    writer.writerows(out_rows)
    if output is not sys.stdout:
        output.close()
    print(
        f"# wrote {len(out_rows)} bracket rows "
        f"({len(found)} variants) for {args.region} {args.year}",
        file=sys.stderr,
    )


def main():
    parser = argparse.ArgumentParser(
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)

    inspect_parser = sub.add_parser(
        "inspect", help="dump worksheet cells to discover the layout"
    )
    inspect_parser.add_argument("workbook")
    inspect_parser.set_defaults(func=cmd_inspect)

    convert_parser = sub.add_parser(
        "convert", help="convert a workbook to the module CSV format"
    )
    convert_parser.add_argument("workbook")
    convert_parser.add_argument(
        "--region",
        required=True,
        choices=REGIONS,
        help="tax region the tables belong to",
    )
    convert_parser.add_argument(
        "--year",
        required=True,
        type=int,
        help="calendar year the tables cover",
    )
    convert_parser.add_argument(
        "--ias",
        help="IAS value for the year (e.g. 537.13 for 2026)",
    )
    convert_parser.add_argument(
        "--set-json",
        help="JSON file with the Despacho set-level constants "
        "(ias, disabled_dep_parcela_*, spouse_disabled_parcela, "
        "pension_dep_parcela_*) not present in the workbook",
    )
    convert_parser.add_argument(
        "--sheet",
        help="only convert the named worksheet",
    )
    convert_parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="output CSV path, or '-' for stdout (default)",
    )
    convert_parser.set_defaults(func=cmd_convert)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
