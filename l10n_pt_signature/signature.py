#! -*- encoding: utf-8 -*-
##############################################################################
#
#    This file is a part of l10n_pt_digital_signature
#    Copyright (C) 2010 Paulino Ascenção <paulino1@sapo.pt>
#    Modificações (C) Jorge A. Ferreira sysop.x0@gmail.com 9/2013
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
##############################################################################

import datetime
import os

from openerp import models, _, exceptions


key = """-----BEGIN RSA PRIVATE KEY-----
MIICWwIBAAKBgQCoPIVQxVZfH0hX6iVIoCLGtSWQilks11kfpArOYfHL++JKGHha
KojFHFmJDjzxyLe+e946x1Y1WaN2HLjSIhnKFDfi5XVWaI93NDBG6dF8lqDIgir7
EkDv1cLtxCnTBDkKTTjn4+NH6bjpT1Gi+UMV7WpOn9+SxMZbvlK9btlMzwIDAQAB
AoGAZFx2S1DtzaEjzw5nX4PoOxIlbqyZth5hlHaP276iOEXzILCoW2G0ZaIb558O
zE4pDwFl+TqhOwJWeUd5GiItr1/Dzwi1BMi3BU2H9ohOLAU8L3ZQCZOEF9txIPIP
5KJ1kIbo1CtQlsjapupmHILsayIa49QN8TQZRoIlq7Hc1kECQQDX3uBQ88svknqr
t4IHTU0Ql05wseBfM52CXJcTGDV78/q+nM/bW+sc4gaTN76fV3cwMOBCL86EZ6lB
ZCzRUobLAkEAx4LElJWSJvF5mJJOSTXX6lnNjUJqj8K0cZ5pvQ8pbynanrwvXpB2
qxhDI/II9fdDE7kaqddVmnQ1vVYxwE5NjQJAE5XbED0uQCCwFIhPuc3fohO4QC1D
SB/suHkiE89setSF+WlMyoAqcrJnGlBCcT6ER9EHZ7niqMym5JHsJwmvxQJAEBX3
C5PTqNgnWanSLgztT7PV4uHL/bNRISgIlnm2eYQCYHIDz7gOGVVndGp7VnmNKvXt
tGvsNvvPqWhdsoedsQJAZvIC7FFVsYcVfM5CPRR7mzAA6TcmjoWec2A8Av7CxoG6
3srl/IG8pLj4OheIXZPP5ZyDR5JsiCIwh92cW4jdDQ==
-----END RSA PRIVATE KEY-----"""

priv_key = 'keys/privatekey.pem'

try:
    a = open(priv_key)
    a.close()
except IOError:
    os.mkdir('keys')
    k = open(priv_key, 'w')
    k.write(key)
    k.close()
hash_control = 1


class account_invoice(models.Model):
    _inherit = 'account.invoice'

    def get_hash(self, inv_id):
        """
        Gets the previous invoice of the same type and journal, and
        returns it's signature to be included in next invoice's string to sign
        """
        res = {}
        #invoice_obj=self.pool.get('account.invoice')
        invoice = self.browse(inv_id)
        self.env.cr.execute(
            """
            SELECT hash FROM account_invoice inv
             WHERE internal_number = (
                SELECT MAX( internal_number) FROM account_invoice
                WHERE journal_id = %d
                  AND internal_number < %s
                  AND period_id in (
                        SELECT id FROM account_period
                        WHERE fiscalyear_id = %d)
                  AND state in ('open', 'paid', 'cancel') )
            """,
            (invoice.journal_id.id,
             invoice.internal_number,
             invoice.period_id.fiscalyear_id.id))
        res = self._cr.fetchone()
        if res is None:
            return ''
        else:
            return res[0]

    _defaults = {
        'hash_control': lambda *a: hash_control
        }

    def action_signature(self):
        """Write hash and system_entry_date """
        # duvida: usar esta accao ou adicionar action_sign a incluir num
        # workflow redesenhado, que substitua o original ????
        for invoice in self:
            # continues when it is not necessary to sign the invoices
            if (invoice.type in ('out_refund', 'out_invoice') and
                    invoice.journal_id.self_billing) or \
                    (invoice.type in ('in_refund', 'in_invoice') and
                     not invoice.journal_id.self_billing):
                continue
            inv_date = str(invoice.date_invoice)
            now = invoice.system_entry_date or datetime.datetime.now()
            try:
                invoiceNo = str(
                    invoice.journal_id.saft_inv_type + ' ' + invoice.number)
            except TypeError:
                raise exceptions.ValidationError(
                    _("Please set the doc type at Journal's SAFT parameters!"))
                return False
            gross_total = self.grosstotal(invoice.id)
            prev_hash = self.get_hash(invoice.id)

            message = inv_date + ';' + str(now)[:19].replace(' ', 'T') + ';' \
                + invoiceNo + ';' + gross_total + ';' + prev_hash

            signature = os.popen(
                'echo -n "' + message + '" | openssl dgst -sha1 -sign ' +
                priv_key + ' | openssl enc -base64 -A', "r").read()
            self._cr.execute(
                "UPDATE account_invoice SET hash = '%s' \
                WHERE id = %d" % (signature, invoice.id))

            if not invoice.system_entry_date:
                self._cr.execute(
                    "UPDATE account_invoice SET system_entry_date = '%s' \
                    WHERE id = %d" % (now, invoice.id))
        return True

    def action_cancel(self, *args):
        account_move_obj = self.pool.get('account.move')
        invoices = self.browse(self.ids)
        # Sysop - unkown i - quick fix. Todo: find what it means
        i = 1
        for invoice in invoices:
            if invoice.move_id.id:
                # invoices that are signed can not be deleted
                if (invoice.type in ('out_refund', 'out_invoice') and
                        not invoice.journal_id.self_billing) or \
                        (invoice.type in ('in_refund', 'in_invoice') and
                         invoice.journal_id.self_billing):
                    raise exceptions.ValidationError(
                        _('You cannot cancel confirmed Invoices '
                          'subject to digital signature!'))
                    return False

                account_move_obj.button_cancel([invoice.move_id.id])
                # delete the move this invoice was pointing to
                # Note that the corresponding move_lines and move_reconciles
                # will be automatically deleted too
                account_move_obj.unlink([i['move_id'][0]])
            if invoice.payment_ids:
                account_move_line_obj = self.pool.get('account.move.line')
                pay_ids = account_move_line_obj.browse(i['payment_ids'])
                for move_line in pay_ids:
                    if move_line.reconcile_partial_id and \
                            move_line.reconcile_partial_id.line_partial_ids:
                        raise exceptions.ValidationError(
                            _('You cannot cancel the Invoice which is '
                              'Partially Paid! You need to unreconcile '
                              'concerned payment entries!'))

        self.write(self.ids, {'state': 'cancel', 'move_id': False})
        self._log_event(self.ids, -1.0, 'Cancel Invoice')
        return True
