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
| 1 | Standard apps set up as data in `newerp_base`: warehouse, product attributes size and colour (variants), order tags, delivery methods (Nova Poshta, pickup), payment terms, user groups like ours (manager, storekeeper, admin). Plus the table below: each item of the other versions → Odoo standard or our addon | done (2026-11-14) |
| 2 | `newerp_opencart`: connector to the OpenCart database (the `dd_*` tables in the Docker MySQL of NewErpPython, fake data). Import categories, products with size variants, customers and orders (`sale.order`), on a schedule; stock back to the storefront (`dd_product_option_value.quantity`). Needs `pymysql`, so a small Dockerfile on top of the official image | in progress: 2a (settings, categories, products with size variants, runs) done 2026-11-14; 2b orders and 2c stock next |
| 3 | `newerp_novaposhta`: a `delivery.carrier` provider: delivery cost, waybill creation, tracking on a schedule, cities and branches directory (NewErpPython phase 6, item 23) | |
| 4 | `newerp_bank_ua`: PrivatBank and monobank statements as bank statement lines, with the automatic matching of NewErpPython item 28 (exactly one confident order) | |
| 5 | `newerp_checkbox`: Checkbox fiscal receipts and cashier shifts on payments (NewErpPython phase 8) | |
| 6 | `newerp_smsclub`: SMSClub as the SMS provider; the SMS with the waybill (NewErpPython phase 10) | |
| 7 | `newerp_production`: the sewing workflow on Manufacturing: consumables in BOMs, cut and sew operations, the sewing plan from orders (NewErpPython phase 5, items 26–27) | |
| 8 | Migration of all addons to Odoo 20 | |

## Standard Odoo or our addon

Every phase and item of NewErpPython's `docs/plan.md`, with what covers it here. "Standard" means an Odoo Community
app or setting, set up in phase 1 or used as it is; "not planned" says why.

### NewErpPython phases 1–19

| # | Module | Here |
|---|---|---|
| 1 | Users, roles, login | Standard users; the roles Менеджер, Комірник, Адміністратор (phase 1). Odoo limits failed logins itself |
| 2 | Orders: list, card, statuses, new order, composition, customer risk | Standard Sales; the statuses map onto Odoo's states (table below); orders from the shop come through phase 2. The customer risk check (earlier cancellations) is a candidate for phase 2 |
| 3 | Managers' bonuses | Not planned: commissions are an Enterprise app; a small addon later if wanted |
| 4 | Stock: consumables, warehouses, purchase orders, reorder, stocktaking | Standard Inventory and Purchase: products, warehouses, reordering rules, inventory adjustments |
| 5 | Production: models, BOMs, sewn stock, sewing plan | Standard Manufacturing (BOMs, manufacturing orders); the sewing workflow and plan in phase 7 |
| 6 | Delivery: Nova Poshta waybills and reminders | Phase 3 (`newerp_novaposhta`) |
| 7 | Nova Post International | Not planned yet: the same pattern as phase 3, later if wanted |
| 8 | Cashbox: Checkbox | Phase 5 (`newerp_checkbox`) |
| 9 | Payments: PrivatBank statement, LiqPay | PrivatBank in phase 4; LiqPay as a payment provider is not planned (the shop takes the money, not the ERP) |
| 10 | SMS: SMSClub | Phase 6 (`newerp_smsclub`) |
| 11 | Partners: reseller XML feeds | Not planned: a storefront feature |
| 12 | Catalog: sort, products, storefront stock, cross-sell | Standard products and variants; storefront stock in phase 2; the sort and cross-sell belong to the storefront |
| 13 | Pre-orders | Standard: an order with no stock waits for its delivery (backorder) or its manufacturing order |
| 14 | Marketing: birthdays, coupons, bulk SMS, contacts export, gift vouchers | Standard Discount & Loyalty (coupons, gift cards), export and SMS marketing; birthdays not planned |
| 15 | Returns, customers | Standard: return pickings, credit notes, Contacts |
| 16 | Reports, revenue feed | Standard Sales, Inventory and Invoicing reports |
| 17 | Locations with Excel import and export | Standard import and export of any list |
| 18 | Competitor prices | Not planned: outside the ERP's core |
| 19 | Kafka events | Not needed: Odoo has its own bus and scheduled actions |

### NewErpPython items 20–84

| Items | Here |
|---|---|
| 20, 21, 22a–d | Docker: phase 0. Demo data: the fake OpenCart data through phase 2. The web interface is Odoo's own |
| 23 | Courier delivery to an address: phase 3 |
| 24 | Sale prices: standard pricelists |
| 25 | Coupon admin: standard Discount & Loyalty |
| 26 | Low-stock alerts: standard reordering rules (the SMS through phase 6) |
| 27 | Consumables for the sewing plan: phase 7 |
| 28 | Automatic bank payment matching: phase 4 |
| 29, 72, 73 | Checks against the real database and production settings: not needed here (fake data, settings in Odoo) |
| 30, 57 | UTM report, tracking codes: standard UTM sources, mediums and campaigns |
| 31 | Storefront reports: through phase 2 if wanted |
| 32 | Customers sharing one IP: not planned (a storefront fraud check) |
| 33, 34 | Login throttle, login CSRF: standard Odoo |
| 35–42 | Order tools: standard (edit, invoice, print, cancel, delivery dates); the waybill check before shipping in phase 3 |
| 43–49, 52, 75, 76 | Product form, import, labels, categories, attributes, options, pictures: standard products, variants and import |
| 50, 51, 70, 83 | Content, reviews, banners, SEO, review photos: website features, not planned (the shop stays on OpenCart) |
| 53, 54 | Customer card and groups: standard Contacts and pricelists |
| 55, 56 | monobank, PrivatBank business cards: phase 4 |
| 58 | Gift vouchers by e-mail: standard gift cards |
| 59–62, 77 | Klaviyo, TikTok, Instagram, remarketing: storefront marketing, not planned |
| 63–69, 71, 84 | Settings, user groups, API users, logs, backups, uploads, status lists, standard reports, printing: standard Odoo |
| 74, 78–82 | Work on the other versions: not applicable |

### OpenCart order statuses in Odoo

| Old status | In Odoo |
|---|---|
| 1) Уточнюємо | Quotation (draft) |
| 2) Прийнято, В обробці | Confirmed sales order |
| 3) Виготовляється | Its manufacturing order in progress (phase 7) |
| 4) Чекає на відправку | Delivery ready |
| 5) Відправлено, Виконано (B2B) | Delivery done |
| Відмінено | Cancelled |
| Терміново, Перевірити оплату | Sales tags |

## Notes

- Standard Odoo rights, kept on purpose: a salesperson's confirmed order creates its manufacturing orders (sale_mrp),
  warehouse users read and update sales orders, and purchase users create vendor bills. The roles split the apps, not
  those links between them.
- `stock.warehouse0` is noupdate too; `newerp_base` renames it with a `<function>` call in a noupdate block, which
  runs once on install.
- `base.main_company` belongs to `base` and is "noupdate", so our XML can't change it; `newerp_base` uses a
  `post_init_hook`. `account` loads a chart of accounts only after every module is loaded, so the hook hands it the
  Ukrainian chart instead of the generic one (in US dollars).
