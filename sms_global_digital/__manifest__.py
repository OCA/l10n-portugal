# Copyright 2022 Exo Software (https://exosoftware.pt).
# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "SMS Global Digital",
    "summary": "Send SMS messages using the Global Digital API",
    "version": "14.0.1.0.0",
    "category": "SMS",
    "website": "https://github.com/OCA/l10n-portugal",
    "author": "Exo Software,Odoo Community Association (OCA)",
    "maintainers": ["tiagosrangel"],
    "license": "AGPL-3",
    "application": False,
    "installable": True,
    "depends": ["base_phone", "sms", "iap_alternative_provider"],
    "data": ["views/iap_account_views.xml", "views/res_config_settings_views.xml"],
}
