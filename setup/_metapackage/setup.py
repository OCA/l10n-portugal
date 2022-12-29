import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo-addons-oca-l10n-portugal",
    description="Meta package for oca-l10n-portugal Odoo addons",
    version=version,
    install_requires=[
        'odoo-addon-l10n_pt_account_invoicexpress>=16.0dev,<16.1dev',
        'odoo-addon-l10n_pt_vat>=16.0dev,<16.1dev',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 16.0',
    ]
)
