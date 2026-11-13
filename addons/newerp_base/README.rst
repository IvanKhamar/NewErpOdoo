============
NewErp: base
============

Shared settings of NewErp on Odoo 19, the base every other ``newerp_*`` addon depends on.

What it does
============

* Installs the standard apps NewErp builds on: Sales, Inventory, Manufacturing, Purchase, Contacts, Invoicing and
  the Ukrainian accounting localization (``l10n_ua``).
* On install, sets the main company to Ukraine and loads the Ukrainian chart of accounts (``ua_psbo``), which makes
  the hryvnia the company currency. An admin may change it later; a company that already keeps its books is left alone.

Tests
=====

``tools/run_tests.sh newerp_base`` from the repository root (see the README there).
