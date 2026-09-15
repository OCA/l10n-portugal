# Copyright 2026 Open Source Integrators
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Account Payment EasyPay Direct Debit",
    "version": "18.0.1.0.0",
    "category": "Accounting/Payment",
    "summary": "SEPA Direct Debit collection via the EasyPay API using payment orders",
    "author": "Open Source Integrators, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-portugal",
    "license": "AGPL-3",
    "depends": ["account_banking_mandate", "payment_easypay_oca"],
    "data": [
        "data/account_payment_method_data.xml",
        "data/ir_cron_data.xml",
        "views/payment_transaction_views.xml",
        "views/account_payment_mode_views.xml",
        "views/account_banking_mandate_views.xml",
        "views/account_payment_views.xml",
    ],
    "installable": True,
}
