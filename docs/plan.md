# Plan

Decided 2026-11-14. NewErp on Odoo is not a port of the other versions: standard Odoo covers most of their features,
and our addons add what it lacks. NewErpPython (`docs/plan.md` there) is the specification for every addon: its rules,
texts and tests. Each phase is one or more PRs; each starts with a short plan the user approves.

**Why Odoo 19, not 20:** Odoo 20.0 came out at the end of September 2026. Its OCA modules and tutorials are not ported
yet, and most client projects run 17–19. Moving to 20 is phase 8, and migrating addons to a new major version is a
skill of its own.

## Phases

| # | Phase | Status |
|---|---|---|
| 0 | Setup: Docker Compose (Odoo 19, PostgreSQL 17), `newerp_base` (standard apps, Ukraine, the Ukrainian chart of accounts, the hryvnia), test script, pre-commit (ruff, pylint-odoo), CI, Dependabot | done (2026-11-14) |
| 1 | Standard apps set up as data in `newerp_base`: warehouse, product attributes size and colour (variants), order tags, delivery methods (Nova Poshta, pickup), payment terms, user groups like ours (manager, storekeeper, admin). Plus the table below: each item of the other versions → Odoo standard or our addon | |
| 2 | `newerp_opencart`: connector to the OpenCart database (the `dd_*` tables in the Docker MySQL of NewErpPython, fake data). Import categories, products with size variants, customers and orders (`sale.order`), on a schedule; stock back to the storefront (`dd_product_option_value.quantity`). Needs `pymysql`, so a small Dockerfile on top of the official image | |
| 3 | `newerp_novaposhta`: a `delivery.carrier` provider: delivery cost, waybill creation, tracking on a schedule, cities and branches directory (NewErpPython phase 6, item 23) | |
| 4 | `newerp_bank_ua`: PrivatBank and monobank statements as bank statement lines, with the automatic matching of NewErpPython item 28 (exactly one confident order) | |
| 5 | `newerp_checkbox`: Checkbox fiscal receipts and cashier shifts on payments (NewErpPython phase 8) | |
| 6 | `newerp_smsclub`: SMSClub as the SMS provider; the SMS with the waybill (NewErpPython phase 10) | |
| 7 | `newerp_production`: the sewing workflow on Manufacturing: consumables in BOMs, cut and sew operations, the sewing plan from orders (NewErpPython phase 5, items 26–27) | |
| 8 | Migration of all addons to Odoo 20 | |

## Standard Odoo or our addon

Filled in during phase 1: every item of NewErpPython's plan gets a line here, with the Odoo app or setting that covers
it, or the addon that adds it.

## Notes

- `base.main_company` belongs to `base` and is "noupdate", so our XML can't change it; `newerp_base` uses a
  `post_init_hook`. `account` loads a chart of accounts only after every module is loaded, so the hook hands it the
  Ukrainian chart instead of the generic one (in US dollars).
