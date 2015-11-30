.. image:: https://img.shields.io/badge/licence-AGPL--3-blue.svg
   :target: http://www.gnu.org/licenses/agpl-3.0-standalone.html
   :alt: License: AGPL-3

===================
Portugal - Partners
===================

This modules extends partners, banks and company information in order to meet
the legal and functional requirements of the Portuguese localisation. The list
of added features includes:

 * Add *Alias Name* field to company-type partners. It can be a trade name,
   a shorter name or whatever alternative company name.
 * Add *No. of print copies* field to customers. This allows a granular
   control over the number of copies that will be printed on invoice/refund
   print jobs.
 * Add *Self Billing* field to partners. Companies are legally obligated
   to inform about the existence of `self billing agreements <https://www.gov.uk/guidance/vat-self-billing-arrangements>`_
   with customers or suppliers.
 * Add *Share Capital* and *Accountant TIN* fields to company.
 * Prevents user from changing a customer name or TIN when there are posted
   invoices.
 * Add *Long Name*, *VAT No.*, *Website* and *Country* fields to banks.
 * Add a list of the most frequently used portuguese banks, including address,
   BIC numbers and websites for improved user experience.
 * Add bank account number validation when the bank is Portuguese.

Usage
=====

When creating or editing bank accounts:

* It's a good idea to start by defining its country. Portuguese bank account
  numbers will be validated in either the standard (aka NIB) or IBAN types.

.. image:: https://odoo-community.org/website/image/ir.attachment/5784_f2813bd/datas
   :alt: Try me on Runbot
   :target: https://runbot.odoo-community.org/runbot/{repo_id}/{branch}

.. repo_id is available in https://github.com/OCA/maintainer-tools/blob/master/tools/repos_with_ids.txt
.. branch is "8.0" for example

Known issues / Roadmap
======================

* No effort is made to correct or validate previously existing related data.

Bug Tracker
===========

Bugs are tracked on `GitHub Issues
<https://github.com/OCA/{project_repo}/issues>`_. In case of trouble, please
check there if your issue has already been reported. If you spotted it first,
help us smashing it by providing a detailed and welcomed `feedback
<https://github.com/OCA/
{project_repo}/issues/new?body=module:%20
{module_name}%0Aversion:%20
{branch}%0A%0A**Steps%20to%20reproduce**%0A-%20...%0A%0A**Current%20behavior**%0A%0A**Expected%20behavior**>`_.

Credits
=======

Images
------

* Odoo Community Association: `Icon <https://github.com/OCA/maintainer-tools/blob/master/template/module/static/description/icon.svg>`_.

Contributors
------------

* Pedro Castro Silva (`Sossia <http://www.sossia.pt>`_)
* Daniel Reis <dreis.pt@hotmail.com>
* The `Spanish localisation team <https://github.com/OCA/l10n-spain>`_.

Maintainer
----------

.. image:: https://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: https://odoo-community.org

This module is maintained by the OCA.

OCA, or the Odoo Community Association, is a nonprofit organization whose
mission is to support the collaborative development of Odoo features and
promote its widespread use.

To contribute to this module, please visit https://odoo-community.org.
