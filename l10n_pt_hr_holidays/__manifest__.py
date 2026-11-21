# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl).
{
    "name": "Portugal - Time Off",
    "version": "19.0.1.0.0",
    "license": "LGPL-3",
    "author": "Odoo Community Association (OCA)",
    "summary": "Portuguese leave types and annual vacation scheduling report",
    "website": "https://github.com/OCA/l10n-portugal",
    "category": "Human Resources/Time Off",
    "maintainers": ["dreispt"],
    "development_status": "Alpha",
    "depends": ["hr", "hr_holidays", "web"],
    "data": [
        "data/hr_leave_type_data.xml",
        "security/ir.model.access.csv",
        "report/vacation_schedule_report.xml",
        "wizard/vacation_schedule_wizard_views.xml",
    ],
    "installable": True,
    "auto_install": False,
}
