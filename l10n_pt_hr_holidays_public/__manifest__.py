# License AGPL-3.0 or later (https://www.gnu.org/licenses/agpl).

{
    "name": "Portugal - Public Holiday Generator",
    "version": "19.0.1.0.0",
    "summary": "Generate Portuguese public holidays in the OCA calendar",
    "license": "AGPL-3",
    "author": "Odoo Community Association (OCA)",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Human Resources/Time Off",
    "maintainers": ["dreispt"],
    "development_status": "Alpha",
    "depends": [
        "calendar_public_holiday",
        "hr_holidays",
        "hr_holidays_public",
    ],
    "data": [
        "security/ir.model.access.csv",
        "data/l10n_pt_public_holiday_rule_data.xml",
        "views/l10n_pt_public_holiday_rule_views.xml",
        "views/calendar_public_holiday_views.xml",
        "wizard/l10n_pt_generate_public_holidays_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
