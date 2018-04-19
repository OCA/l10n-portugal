import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo8-addons-oca-l10n-portugal",
    description="Meta package for oca-l10n-portugal Odoo addons",
    version=version,
    install_requires=[
        'odoo8-addon-l10n_pt_account_asset',
        'odoo8-addon-l10n_pt_municipality',
        'odoo8-addon-l10n_pt_vat',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
    ]
)
