# EasyPay API
API_URL_TEST = "https://api.test.easypay.pt"
API_URL_PROD = "https://api.prod.easypay.pt"

# Map EasyPay API codes to Odoo payment method codes
# Only include codes that need translation; others use the payment.method code directly
EASYPAY_TO_ODOO = {
    "cc": "card",
    "mb": "multibanco",
    "mbw": "mbway",
}

# Reverse mapping for Odoo code -> EasyPay API code lookups
ODOO_TO_EASYPAY = {v: k for k, v in EASYPAY_TO_ODOO.items()}

# Payment types
PAYMENT_TYPE_SALE = "sale"

# Payment method codes owned by this module — the sync action may toggle their
# `active` flag. Shared core methods (card, multibanco, mbway) must never be
# deactivated, as other providers use them too.
# "dd" (SEPA Direct Debit) is reserved for a future implementation: its method
# record exists but is inactive.
OWNED_PAYMENT_METHOD_CODES = {"dd", "vi", "ap", "gp", "sw", "easypay"}
