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
* Customers: the shop's customer by its id; a guest by e-mail or phone (the last 9 digits, however the number was
  typed), so the same person is not doubled.
* Orders changed since the last import (by ``date_modified``) become sales orders: lines by the chosen size row,
  the shop's prices without tax on top, the source, the delivery method, the payment term (cash on delivery or
  prepaid). Statuses: Уточнюємо and Перевірити оплату stay quotations, Відмінено cancels, Прийнято and later confirm;
  Терміново and Перевірити оплату add their tags. A quotation follows later changes in the shop; a confirmed or
  cancelled order belongs to the ERP and is left alone. An order with a product Odoo does not know is skipped and
  named in the run.
* A scheduled action imports the catalog and the orders every 15 minutes; it is off until the connection is set up.
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
