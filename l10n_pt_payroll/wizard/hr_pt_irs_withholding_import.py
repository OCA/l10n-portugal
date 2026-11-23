# Copyright (C) 2026 Daniel Reis
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

import base64
import csv
import io
import math
import os
from datetime import datetime

from odoo import api, fields, models
from odoo.exceptions import UserError
from odoo.tools import file_open
from odoo.tools.safe_eval import safe_eval

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
# Columns repeated on every row of a block that describe the whole
# table set (Despacho period constants), not a single bracket.
SET_CSV_FIELDS = [
    "ias",
    "disabled_dep_parcela_single",
    "disabled_dep_parcela_joint",
    "spouse_disabled_parcela",
    "pension_dep_parcela_single",
    "pension_dep_parcela_joint",
    "pension_dep_parcela_single_income",
]
REQUIRED_CSV_FIELDS = [field for field in CSV_FIELDS if field not in SET_CSV_FIELDS]


class HrPtIrsWithholdingImport(models.TransientModel):
    _name = "hr.pt.irs.withholding.import"
    _description = "Import IRS Withholding Tables"

    csv_file = fields.Binary(
        string="CSV File",
        help="CSV file with the official withholding table brackets, "
        "in the same format as the bundled files under data/irs/. "
        "Leave empty to load the bundled tables instead.",
    )
    filename = fields.Char()

    def action_import(self):
        self.ensure_one()
        if not self.csv_file:
            raise UserError(self.env._("Please select a CSV file to import."))
        csv_text = base64.b64decode(self.csv_file).decode("utf-8-sig")
        count = self._import_csv_data(csv_text)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("IRS tables imported"),
                "message": self.env._(
                    "%(count)s withholding table set(s) imported.", count=count
                ),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _import_csv_data(self, csv_text):
        """Import withholding brackets from a CSV in the bundled format.

        The whole file is validated before any write, so an invalid file
        aborts atomically. Returns the number of table sets imported.
        """
        rows = self._l10n_pt_parse_csv(csv_text)
        blocks = self._l10n_pt_validate_csv_rows(rows)
        for block in blocks.values():
            self._l10n_pt_upsert_block(block)
        return len(blocks)

    @staticmethod
    def _bundled_csv_paths():
        path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "irs")
        if not os.path.isdir(path):
            return []
        return sorted(
            os.path.join(path, name)
            for name in os.listdir(path)
            if name.endswith(".csv")
        )

    @classmethod
    def load_bundled(cls, env):
        """Import every bundled data/irs/*.csv file. Used by the
        post-init hook and by the 'Load bundled tables' action."""
        wizard = env["hr.pt.irs.withholding.import"]
        for path in cls._bundled_csv_paths():
            with file_open(path, "rb") as csv_file:
                wizard._import_csv_data(csv_file.read().decode("utf-8-sig"))
        return True

    @api.model
    def load_bundled_tables(self):
        """Load the bundled CSVs through the data loader; called from
        demo data, which runs before the post-init hook."""
        return self.load_bundled(self.env)

    def action_load_bundled(self):
        self.load_bundled(self.env)
        return {
            "type": "ir.actions.client",
            "tag": "display_notification",
            "params": {
                "title": self.env._("Bundled tables loaded"),
                "message": self.env._(
                    "The bundled IRS withholding tables were loaded."
                ),
                "type": "success",
                "sticky": False,
            },
        }

    @api.model
    def _l10n_pt_parse_csv(self, csv_text):
        try:
            reader = csv.DictReader(io.StringIO(csv_text))
            if reader.fieldnames is None:
                raise UserError(self.env._("The CSV file is empty."))
            missing = [f for f in REQUIRED_CSV_FIELDS if f not in reader.fieldnames]
            if missing:
                raise UserError(
                    self.env._(
                        "The CSV file is missing required columns: %s",
                        ", ".join(missing),
                    )
                )
            return list(reader)
        except csv.Error as e:
            raise UserError(self.env._("Could not parse the CSV file: %s", e)) from e

    @api.model
    def _l10n_pt_validate_csv_rows(self, rows):
        table_model = self.env["hr.pt.irs.withholding.table"]
        variants = {
            table.code: table
            for table in self.env["l10n.pt.irs.withholding.table"].search([])
        }
        regions = dict(table_model._fields["region"].selection)
        blocks = {}
        for lineno, row in enumerate(rows, start=2):
            date_start = self._l10n_pt_parse_date(
                row.get("date_start"), "date_start", lineno
            )
            date_end = self._l10n_pt_parse_date(
                row.get("date_end"), "date_end", lineno, required=False
            )
            if date_end and date_start > date_end:
                raise UserError(
                    self.env._(
                        "Line %(line)s: date_end is before date_start.",
                        line=lineno,
                    )
                )
            region = (row.get("region") or "").strip()
            if region not in regions:
                raise UserError(
                    self.env._(
                        "Line %(line)s: unknown region '%(region)s'.",
                        line=lineno,
                        region=region,
                    )
                )
            table_code = (row.get("table_code") or "").strip()
            variant = variants.get(table_code)
            if not variant:
                raise UserError(
                    self.env._(
                        "Line %(line)s: unknown table code '%(code)s'.",
                        line=lineno,
                        code=table_code,
                    )
                )
            lower = self._l10n_pt_parse_number(
                row.get("lower_bound"), "lower_bound", lineno
            )
            upper = self._l10n_pt_parse_number(
                row.get("upper_bound"), "upper_bound", lineno
            )
            rate = self._l10n_pt_parse_number(
                row.get("marginal_rate"), "marginal_rate", lineno
            )
            if lower is None or lower < 0:
                raise UserError(
                    self.env._(
                        "Line %(line)s: lower_bound must be a positive number.",
                        line=lineno,
                    )
                )
            if upper is not None and upper <= lower:
                raise UserError(
                    self.env._(
                        "Line %(line)s: upper_bound must be greater than lower_bound.",
                        line=lineno,
                    )
                )
            if rate is None or not 0 <= rate <= 100:
                raise UserError(
                    self.env._(
                        "Line %(line)s: marginal_rate must be between 0 and 100.",
                        line=lineno,
                    )
                )
            parcela = (row.get("parcela_abater") or "").strip() or "0"
            try:
                safe_eval(parcela, {"R": 1000.0})
            except Exception as e:
                raise UserError(
                    self.env._(
                        "Line %(line)s: parcela_abater is not a valid "
                        "expression: %(error)s",
                        line=lineno,
                        error=e,
                    )
                ) from e
            key = (str(date_start), str(date_end or ""), region, variant.id)
            set_values = {
                field: self._l10n_pt_parse_number(row.get(field), field, lineno)
                for field in SET_CSV_FIELDS
            }
            if key in blocks and blocks[key]["set_values"] != set_values:
                raise UserError(
                    self.env._(
                        "Line %(line)s: inconsistent table-set values "
                        "(IAS or Despacho constants) inside the same "
                        "table block.",
                        line=lineno,
                    )
                )
            blocks.setdefault(
                key,
                {
                    "date_start": date_start,
                    "date_end": date_end,
                    "region": region,
                    "variant": variant,
                    "set_values": set_values,
                    "lines": [],
                },
            )["lines"].append(
                {
                    "lower_bound": lower,
                    "upper_bound": upper or 0.0,
                    "marginal_rate": rate,
                    "parcela_abater": parcela,
                    "dependent_parcela": self._l10n_pt_parse_number(
                        row.get("dependent_parcela"), "dependent_parcela", lineno
                    )
                    or 0.0,
                    "forces_disabled_parcela": self._l10n_pt_parse_number(
                        row.get("forces_disabled_parcela"),
                        "forces_disabled_parcela",
                        lineno,
                    )
                    or 0.0,
                    "effective_rate_limit": self._l10n_pt_parse_number(
                        row.get("effective_rate_limit"),
                        "effective_rate_limit",
                        lineno,
                    )
                    or 0.0,
                }
            )
        for block in blocks.values():
            self._l10n_pt_check_brackets(block)
        return blocks

    @api.model
    def _l10n_pt_check_brackets(self, block):
        lines = sorted(block["lines"], key=lambda line: line["lower_bound"])
        block["lines"] = lines
        label = (
            f"{block['variant'].code} ({block['region']} from {block['date_start']})"
        )
        expected = 0.0
        for line in lines:
            if line["lower_bound"] != expected:
                raise UserError(
                    self.env._(
                        "Table %(label)s has a gap or overlap at bound "
                        "%(bound)s: brackets must be contiguous from 0.",
                        label=label,
                        bound=line["lower_bound"],
                    )
                )
            expected = line["upper_bound"] or math.inf
        if lines[-1]["upper_bound"]:
            raise UserError(
                self.env._(
                    "Table %(label)s: the last bracket must be open-ended.",
                    label=label,
                )
            )

    @api.model
    def _l10n_pt_upsert_block(self, block):
        table_model = self.env["hr.pt.irs.withholding.table"]
        table = table_model.search(
            [
                ("date_start", "=", block["date_start"]),
                ("date_end", "=", block["date_end"] or False),
                ("region", "=", block["region"]),
                ("table_id", "=", block["variant"].id),
            ],
            limit=1,
        )
        vals = {
            "date_start": block["date_start"],
            "date_end": block["date_end"] or False,
            "region": block["region"],
            "table_id": block["variant"].id,
        }
        vals.update(
            {field: block["set_values"].get(field) or 0.0 for field in SET_CSV_FIELDS}
        )
        line_vals = [(0, 0, dict(line)) for line in block["lines"]]
        if table:
            table.line_ids.unlink()
            table.write(vals)
            table.write({"line_ids": line_vals})
        else:
            table_model.create(dict(vals, line_ids=line_vals))

    @api.model
    def _l10n_pt_parse_number(self, value, field, lineno):
        text = "" if value is None else str(value).strip()
        if not text:
            if field in ("lower_bound", "marginal_rate"):
                raise UserError(
                    self.env._(
                        "Line %(line)s: %(field)s is required.",
                        line=lineno,
                        field=field,
                    )
                )
            return None
        number = self._l10n_pt_opt_number(text)
        if number is None:
            raise UserError(
                self.env._(
                    "Line %(line)s: %(field)s is not a valid number.",
                    line=lineno,
                    field=field,
                )
            )
        return number

    @api.model
    def _l10n_pt_opt_number(self, value):
        if value is None:
            return None
        text = str(value).strip()
        if not text:
            return None
        # Official tables use Portuguese formatting: "1 234,56" or
        # "44,95%". Normalize thousand separators and decimal commas.
        text = text.replace("%", "").replace("\u00a0", "").replace(" ", "")
        if "," in text and "." in text:
            text = text.replace(".", "").replace(",", ".")
        elif "," in text:
            text = text.replace(",", ".")
        try:
            return float(text)
        except ValueError:
            return None

    @api.model
    def _l10n_pt_parse_date(self, value, field, lineno, required=True):
        text = (value or "").strip()
        if not text:
            if required:
                raise UserError(
                    self.env._(
                        "Line %(line)s: %(field)s is required.",
                        line=lineno,
                        field=field,
                    )
                )
            return False
        for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%d-%m-%Y"):
            try:
                return datetime.strptime(text, fmt).date()
            except ValueError:
                continue
        raise UserError(
            self.env._(
                "Line %(line)s: %(field)s is not a valid date.",
                line=lineno,
                field=field,
            )
        )
