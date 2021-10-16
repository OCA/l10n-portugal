import setuptools

with open('VERSION.txt', 'r') as f:
    version = f.read().strip()

setuptools.setup(
    name="odoo12-addons-oca-l10n-portugal",
    description="Meta package for oca-l10n-portugal Odoo addons",
    version=version,
    install_requires=[
        'odoo12-addon-l10n_pt_vat',
    ],
    classifiers=[
        'Programming Language :: Python',
        'Framework :: Odoo',
        'Framework :: Odoo :: 12.0',
    ]
)
