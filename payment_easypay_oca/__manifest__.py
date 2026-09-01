# Copyright 2025 Open Source Integrators
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).

{
    "name": "Payment Provider: EasyPay",
    "version": "19.0.1.0.0",
    "category": "Accounting/Payment Providers",
    "summary": "Payment Provider for EasyPay with multiple payment methods",
    "author": "Open Source Integrators, Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-portugal",
    "license": "LGPL-3",
    "depends": ["payment", "phone_validation"],
    "data": [
        "security/ir.model.access.csv",
        "views/payment_easypay_templates.xml",
        "views/payment_provider_views.xml",
        "views/payment_transaction_views.xml",
        "views/checkout_template.xml",
        "views/mb_reference_template.xml",
        "data/payment_method_data.xml",
        "data/payment_provider_data.xml",
    ],
    "demo": ["demo/payment_provider_demo.xml"],
    "assets": {
        "web.assets_frontend": [
            "payment_easypay_oca/static/src/js/payment_form.esm.js",
            "payment_easypay_oca/static/src/scss/payment_easypay_oca.scss",
        ],
    },
    "installable": True,
}
