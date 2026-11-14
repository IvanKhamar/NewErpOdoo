============================
NewErp: OpenCart connector
============================

Links Odoo to the shop that stays on OpenCart: reads its MySQL database (the ``dd_*`` tables of the Vidro shop) and
writes the stock back to the storefront.

What it does
============

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
* Stock to the storefront: each linked size gets its free quantity in the chosen warehouse (on hand minus what orders
  reserved), rounded down; a product gets the sum of its sizes, or its own free quantity when it has no sizes. Only
  quantities that differ from the storefront's are written.
* Scheduled actions: the catalog and the orders every 15 minutes, the stock every hour. Both are off until the
  connection is set up (Settings → Technical → Scheduled Actions).
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

Trying it with the fake shop
============================

NewErpPython's Docker MySQL holds a fake OpenCart database (``newerp_dev``, port 3307 on the host):

1. In the NewErpPython repository: ``docker compose up -d mysql``.
2. In Odoo, Settings → OpenCart: host ``host.docker.internal``, port ``3307``, database ``newerp_dev``, and the user
   and password from NewErpPython's ``.env``. "Перевірити з'єднання", then "Імпортувати товари" and
   "Імпортувати замовлення".
3. "Записати залишки у вітрину" writes Odoo's free stock into that database. It is a shared development database,
   so give the products stock in Odoo first, or the storefront quantities become 0.
