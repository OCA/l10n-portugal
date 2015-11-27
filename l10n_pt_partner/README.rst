Portugal - Partners
============================================================

This modules extends partners, suppliers, banks and company information in
order to meet the legal and functional requirements of the Portuguese
localization.

Features:
--------------

 * Adds the *Alias* field to company-type partners. It can be a trade name, a
   shorter name or whatever alternative company name.
 * Adds the *No. of copies* field to customers. This allows a granular control
   over the number of copies that will be printed on invoice/refund print jobs.
 * Adds the *Self Billing* field to partners. Companies are legally obligated
   to inform about the existence of `self billing agreements <https://www.gov.uk/guidance/vat-self-billing-arrangements>`_
   with customers or suppliers.
 * Prevents user from changing a customer name or TIN when there are posted
   invoices.
 * Converts VAT No. to upper case.
 * Add the *Long Name*, *VAT No.*, *Website* and *Country* fields to banks.
 * Adds a list of the most frequently used portuguese banks, including address,
   BIC numbers and websites for improved user experience.
 * Adds bank account number validation when a bank is Portuguese.



Standard bank account number (aka NIB) validation description:
-----------------------------------------------------------------------------

 * Account numbers must be 21 characters long (excluding spaces).
 * If the lenght is correct the Check Digits (CD) are validated.
 * If CD are correct, the account number will formatted as
   "1234 5678 12345678901 06"


IBAN type bank account validation description:
------------------------------------------------------------------------

 * Spaces are removed
 * The account number is divided into blocks, each containg 4 characters
 * The Control Numbers (CN) after PT are validated
 * The Check Digits (CD) are also validated

Credits
=======

Contributors
------------
* Pedro Castro Silva (`Sossia <http://www.sossia.pt>`_)
* Daniel Reis <dreis.pt@hotmail.com>
* The Spanish localisation `team <https://github.com/OCA/l10n-spain>`_.

Maintainer
----------

.. image:: http://odoo-community.org/logo.png
   :alt: Odoo Community Association
   :target: http://odoo-community.org

This module is maintained by the OCA.

OCA, or the Odoo Community Association, is a nonprofit organization whose mission is to support the collaborative development of Odoo features and promote its widespread use.

To contribute to this module, please visit http://odoo-community.org.
