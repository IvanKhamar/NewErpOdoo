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
* Roles: one privilege "NewErp" with Менеджер (sales, invoicing, contacts), Комірник (inventory, manufacturing,
  purchase) and Адміністратор (both, the app managers and settings).
* The shop's data: sizes S–XL and colours as variant attributes; order sources Сайт, Instagram, Телефон, Партнер;
  sales tags Терміново and Перевірити оплату; payment terms Передоплата and Накладений платіж; delivery methods
  Нова Пошта (відділення, поштомат), Укрпошта and Самовивіз (Київ); the main warehouse "Склад Київ" (KYIV).

OpenCart order statuses map onto Odoo's own states (quotation, confirmed, manufacturing, delivery ready and done,
cancelled); only "Терміново" and "Перевірити оплату" are tags. The table is in ``docs/plan.md``.

Tests
=====

``tools/run_tests.sh newerp_base`` from the repository root (see the README there).
