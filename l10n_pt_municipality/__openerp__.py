# -*- coding: utf-8 -*-
# © 2016 Daniel Reis
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
{
    'name': 'Portuguese Municipalities',
    'summary': 'Support for PT municipalities through Eurostat LAUs',
    'version': '8.0.1.0.0',
    'category': 'Localisation/Portugal',
    'website': 'https://odoo-community.org/',
    'author': 'Daniel Reis, Odoo Community Association (OCA)',
    'license': 'AGPL-3',
    'installable': True,
    'depends': [
        'base_location_lau',  # from oca/partner-contact
        ],
    'data': [
        'data/res.partner.lau.csv',
        ],
}
