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

# Payment types
PAYMENT_TYPE_SALE = "sale"
