from odoo import models, fields, api, _
from odoo.exceptions import UserError
from odoo.tools.float_utils import float_compare
from collections import defaultdict


class AccountMove(models.Model):
    _inherit = 'account.move'

    def _check_reversal_amounts_and_quantities(self, only_reconciled=True):
        """
        The purpose of these credit note checks is to confirm that neither the
        quantities nor the monetary amounts exceed their values on the source
        customer invoice, which is a requirement in some countries.
        """
        for move in self.filtered('reversed_entry_id'):
            original_move = move.reversed_entry_id
            if only_reconciled:
                reversals = original_move._get_reconciled_invoices().filtered(lambda move: move.move_type == 'out_refund')
            else:
                reversals = move

            # Unless all the invoices / credit notes are made in the same currency, we can't conveniently
            # check that the credit notes don't exceed the invoices (due to exchange rate differences),
            # so we skip this check.
            if len(set(original_move.mapped('currency_id') + reversals.mapped('currency_id'))) != 1:
                continue

            original_quantities = defaultdict(lambda: 0)
            reverse_quantities = defaultdict(lambda: 0)

            for line in original_move.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
                original_quantities[line.product_id] += line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id)
            for line in reversals.invoice_line_ids.filtered(lambda l: l.display_type == 'product'):
                reverse_quantities[line.product_id] += line.product_uom_id._compute_quantity(line.quantity, line.product_id.uom_id)

            exceeding_quantities = []
            for product, quantity in reverse_quantities.items():
                if product not in original_quantities:
                    exceeding_quantities.append(_("'%s' is not present on the original invoice.", product.name))
                elif (excess := quantity - original_quantities[product]) > 0:
                    exceeding_quantities.append(
                        _(
                            "'%(product_name)s' exceeds quantity on original invoice by %(excess)f %(uom_name)s",
                            product_name=product.name,
                            excess=excess,
                            uom_name=product.uom_id.name
                        )
                    )

            if exceeding_quantities:
                if len(reversals) > 1:
                    raise UserError(_(
                        "This credit note in conjunction with %(other_credit_notes)s has items of a quantity exceeding "
                        "that of the original customer invoice %(original_invoice)s. Please correct the quantity of "
                        "these lines before confirming:\n%(lines_to_correct)s",
                        other_credit_notes=', '.join(
                            rec.name or f"the credit note with ID {rec.id}"
                            for rec in (reversals - move)
                        ),
                        original_invoice=original_move.name,
                        lines_to_correct='\n'.join(exceeding_quantities),
                    ))
                raise UserError(_(
                    "This credit note has items of a quantity exceeding that of the original "
                    "customer invoice %(original_invoice)s. Please correct the quantity of these lines before "
                    "confirming:\n%(lines_to_correct)s",
                    original_invoice=original_move.name,
                    lines_to_correct='\n'.join(exceeding_quantities),
                ))

            credit_note_total = abs(sum(move.amount_total_in_currency_signed for move in reversals))
            excess = abs(credit_note_total) - abs(original_move.amount_total_in_currency_signed)

            if float_compare(excess, 0, precision_digits=2) > 0:
                if len(reversals) > 1:
                    raise UserError(_(
                        "This credit note in conjunction with %(other_credit_notes)s exceeds the amount on the "
                        "original customer invoice %(original_invoice)s. "
                        "Please adjust this credit note to a total value equal to or less than %(total_value)d before confirming.",
                        other_credit_notes=', '.join(
                            rec.name or f"the credit note with ID {rec.id}"
                            for rec in (reversals - move)
                        ),
                        original_invoice=original_move.name,
                        total_value=abs(move.amount_total_in_currency_signed) - excess,
                    ))
                raise UserError(_(
                    "This credit note exceeds the amount of the original customer invoice %(original_invoice)s. "
                    "Please adjust this credit note to a total value equal to or less than %(total_value)d before confirming.",
                    original_invoice=original_move.name,
                    total_value=abs(move.amount_total_in_currency_signed) - excess,
                ))
