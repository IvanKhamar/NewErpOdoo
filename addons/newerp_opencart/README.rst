============================
NewErp: OpenCart connector
============================

Links Odoo to the shop that stays on OpenCart: reads its MySQL database (the ``dd_*`` tables of the Vidro shop) and,
in later steps, writes the stock back to the storefront.

What it does now
================

* Categories with their parents become product categories.
* Products become product templates (name, model as the internal reference, price, "can be sold" from the status),
  in their first known category. Their "Розмір" rows become variants of the attribute Розмір from ``newerp_base``;
  a size Odoo does not know yet becomes a new value. Each variant keeps the id of its size row
  (``product_option_value_id``), the row the storefront counts stock on.
* Importing again updates the linked records and adds nothing twice. OpenCart stock is not taken over: stock belongs
  to the ERP.
* Every import is written to Sales → Configuration → OpenCart: запуски, with the error if it failed.

Setup
=====

Settings → OpenCart (administrators only): host, port, database, user, password, table prefix (``dd_``) and the
OpenCart language id. The values stay in the database; the password field is masked. Then "Перевірити з'єднання"
and "Імпортувати товари".

Tests
=====

The tests use a fake source with rows shaped like the shop's, so they need no MySQL:
``tools/run_tests.sh newerp_opencart``.
