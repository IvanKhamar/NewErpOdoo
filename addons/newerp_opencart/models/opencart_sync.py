import logging

from odoo import api, models
from odoo.exceptions import UserError

from .opencart_source import MySqlOpenCartSource, OpenCartConfig, OpenCartError
from .res_partner import phone_key

_logger = logging.getLogger(__name__)

PARAM = "newerp_opencart."
ORDERS_SINCE = PARAM + "orders_since"  # date_modified of the last imported order: the next import starts there
FIRST_IMPORT_SINCE = "2000-01-01 00:00:00"

# order_status_id of the real shop (NewErpPython devseed) → what the order becomes in Odoo (table in docs/plan.md).
QUOTATION_STATUSES = {24: None, 1: "newerp_base.tag_check_payment"}  # Уточнюємо, Перевірити оплату
CONFIRMED_STATUSES = {18: None, 17: None, 25: None, 21: None, 22: None, 20: None, 23: "newerp_base.tag_urgent"}
CANCELLED_STATUS = 19  # Відмінено


class OpenCartSync(models.AbstractModel):
    """The import steps. An abstract model has no table: it is a service, like an application service class in .NET."""

    _name = "newerp.opencart.sync"
    _description = "OpenCart import and stock push"

    def _opencart_source(self):
        """The shop's database, from the settings. Tests replace this method with a fake source."""
        get = self.env["ir.config_parameter"].sudo().get_param
        return MySqlOpenCartSource(
            OpenCartConfig(
                host=get(PARAM + "host", ""),
                port=int(get(PARAM + "port", "3306") or 3306),
                database=get(PARAM + "database", ""),
                user=get(PARAM + "user", ""),
                password=get(PARAM + "password", ""),
                prefix=get(PARAM + "prefix", "dd_"),
                language_id=int(get(PARAM + "language_id", "3") or 3),
            )
        )

    @api.model
    def check_connection(self):
        self._opencart_source().check()

    @api.model
    def import_catalog(self, raise_errors=True):
        """Categories, then products with their sizes as variants. Returns the run."""
        return self._run("catalog", self._import_catalog, raise_errors)

    @api.model
    def import_orders(self, raise_errors=True):
        """Customers and orders changed since the last import. Returns the run."""
        return self._run("orders", self._import_orders, raise_errors)

    @api.model
    def _cron_import(self):
        """Scheduled action: the catalog, then the orders; quiet until the connection is set up."""
        if not self.env["ir.config_parameter"].sudo().get_param(PARAM + "host"):
            return
        self.import_catalog(raise_errors=False)
        self.import_orders(raise_errors=False)

    @api.model
    def push_stock(self, raise_errors=True, templates=None):
        """The free stock of the linked products to the storefront. Returns the run. `templates` limits the push
        (a check against a live shop); without it every linked product goes."""
        return self._run("stock", lambda source: self._push_stock(source, templates), raise_errors)

    @api.model
    def _cron_push_stock(self):
        if self.env["ir.config_parameter"].sudo().get_param(PARAM + "host"):
            self.push_stock(raise_errors=False)

    def _run(self, kind, step, raise_errors):
        Run = self.env["newerp.opencart.run"].sudo()
        try:
            created, updated, message = step(self._opencart_source())
        except OpenCartError as error:
            _logger.warning("OpenCart %s failed: %s", kind, error)
            run = Run.create({"kind": kind, "state": "failed", "message": str(error)})
            if raise_errors:
                raise UserError(str(error)) from error
            return run
        return Run.create({"kind": kind, "state": "done", "created": created, "updated": updated, "message": message})

    # ── Catalog ──

    def _import_catalog(self, source):
        categories, created_categories, updated_categories = self._import_categories(source.categories())
        created, updated = self._import_products(source.products(), categories)
        message = f"Категорій: нових {created_categories}, оновлених {updated_categories}."
        return created, updated, message

    def _import_categories(self, rows):
        Category = self.env["product.category"]
        linked = {c.opencart_id: c for c in Category.search([("opencart_id", "in", [r["category_id"] for r in rows])])}
        created = updated = 0
        for row in rows:
            category = linked.get(row["category_id"])
            name = row["name"] or f"OpenCart {row['category_id']}"
            if category is None:
                linked[row["category_id"]] = Category.create({"name": name, "opencart_id": row["category_id"]})
                created += 1
            elif category.name != name:
                category.name = name
                updated += 1
        # Parents after every category exists, so a child listed before its parent still finds it.
        for row in rows:
            parent = linked.get(row["parent_id"]) or Category
            category = linked[row["category_id"]]
            if category.parent_id != parent:
                category.parent_id = parent
        return linked, created, updated

    def _import_products(self, rows, categories):
        Template = self.env["product.template"]
        linked = {t.opencart_id: t for t in Template.search([("opencart_id", "in", [r["product_id"] for r in rows])])}
        size_attribute = self.env.ref("newerp_base.attribute_size")
        created = updated = 0
        for row in rows:
            category = next((categories[c] for c in row["category_ids"] if c in categories), None)
            values = {
                "name": row["name"] or row["model"] or f"OpenCart {row['product_id']}",
                "list_price": row["price"],
                "sale_ok": bool(row["status"]),
            }
            if not row["sizes"]:  # with sizes the reference goes on each variant (see _import_sizes)
                values["default_code"] = row["model"] or False
            if category:
                values["categ_id"] = category.id
            template = linked.get(row["product_id"])
            if template is None:
                template = Template.create(
                    {**values, "type": "consu", "is_storable": True, "opencart_id": row["product_id"]}
                )
                created += 1
            else:
                current = {**template.read(list(values))[0], "categ_id": template.categ_id.id}
                changed = {key: value for key, value in values.items() if current[key] != value}
                if changed:
                    template.write(changed)
                    updated += 1
            self._import_sizes(template, row["sizes"], size_attribute, row["model"])
        return created, updated

    def _import_sizes(self, template, sizes, size_attribute, model):
        """The size rows become variants of the attribute Розмір; an unknown size becomes a new value.

        With several variants the internal reference lives on each variant, not on the template, so each size gets
        "<model>-<size>", like a SKU."""
        if not sizes:
            return
        values = [self._size_value(size["name"], size_attribute) for size in sizes]
        line = template.attribute_line_ids.filtered(lambda line: line.attribute_id == size_attribute)
        wanted = self.env["product.attribute.value"].union(*values)
        if not line:
            template.write(
                {"attribute_line_ids": [(0, 0, {"attribute_id": size_attribute.id, "value_ids": wanted.ids})]}
            )
        elif set(line.value_ids.ids) != set(wanted.ids):
            line.value_ids = [(6, 0, wanted.ids)]
        for size, value in zip(sizes, values, strict=True):
            variant = template.product_variant_ids.filtered(
                lambda v, value=value: value in v.product_template_attribute_value_ids.product_attribute_value_id
            )
            if len(variant) != 1:
                continue
            code = f"{model}-{value.name}" if model else False
            if variant.opencart_id != size["id"] or variant.default_code != code:
                variant.write({"opencart_id": size["id"], "default_code": code})

    def _size_value(self, name, size_attribute):
        name = (name or "").strip() or "?"
        value = size_attribute.value_ids.filtered(lambda v: v.name == name)
        if not value:
            value = self.env["product.attribute.value"].create({"attribute_id": size_attribute.id, "name": name})
        return value

    # ── Customers and orders ──

    def _import_orders(self, source):
        """Orders changed since the last import become sales orders, with their customers.

        An order still a quotation in Odoo follows the shop (lines, status); a confirmed or cancelled one belongs to
        the ERP and a later change in the shop does not touch it. An order with a product Odoo does not know is
        skipped and named in the run: guessing a product would ship the wrong thing."""
        params = self.env["ir.config_parameter"].sudo()
        since = params.get_param(ORDERS_SINCE) or FIRST_IMPORT_SINCE
        created = updated = 0
        skipped, last_change = [], since
        for row in source.orders(since):
            last_change = max(last_change, row["date_modified"])
            lines, missing = self._order_lines(row["lines"])
            if missing:
                skipped.append(f"#{row['order_id']}: немає товару {', '.join(missing)}")
                continue
            order = self.env["sale.order"].search([("opencart_id", "=", row["order_id"])], limit=1)
            if not order:
                order = self.env["sale.order"].create(
                    {**self._order_values(row), "opencart_id": row["order_id"], "order_line": lines}
                )
                created += 1
            elif order.state == "draft":
                order.write({**self._order_values(row), "order_line": [(5, 0, 0), *lines]})
                updated += 1
            else:
                continue
            self._apply_status(order, row["order_status_id"])
        params.set_param(ORDERS_SINCE, last_change)
        message = "Пропущено (спершу імпортуйте товари): " + "; ".join(skipped) if skipped else ""
        return created, updated, message

    def _order_lines(self, rows):
        """Order lines by the chosen size row, else by the product when it has one variant. No taxes: the shop's
        prices already are the final ones."""
        Product = self.env["product.product"]
        lines, missing = [], []
        for row in rows:
            variant = (
                Product.search([("opencart_id", "=", row["size_row_id"])], limit=1) if row["size_row_id"] else Product
            )
            if not variant:
                template = self.env["product.template"].search([("opencart_id", "=", row["product_id"])], limit=1)
                variant = template.product_variant_id if len(template.product_variant_ids) == 1 else Product
            if not variant:
                missing.append(f"«{row['name']}» ({row['product_id']})")
                continue
            lines.append(
                (0, 0, {
                    "product_id": variant.id,
                    "product_uom_qty": row["quantity"],
                    "price_unit": row["price"],
                    "tax_ids": [(6, 0, [])],
                })
            )  # fmt: skip
        return lines, missing

    def _order_values(self, row):
        method = (row["shipping_method"] or "").lower()
        cod = row["payment_code"] == "cod" or "наклад" in (row["payment_method"] or "").lower()
        values = {
            "partner_id": self._customer(row).id,
            "date_order": row["date_added"],
            "origin": f"OpenCart #{row['order_id']}",
            "note": row["comment"] or False,
            "payment_term_id": self.env.ref(
                "newerp_base.payment_term_cod" if cod else "newerp_base.payment_term_prepaid"
            ).id,
            "carrier_id": self._carrier(method).id,
        }
        if row["source"]:
            source = self.env["utm.source"].search([("name", "=", row["source"])], limit=1)
            values["source_id"] = (source or self.env["utm.source"].create({"name": row["source"]})).id
        return values

    def _carrier(self, method):
        if "поштомат" in method:
            return self.env.ref("newerp_base.carrier_np_locker")
        if "нова пошта" in method or "novaposhta" in method:
            return self.env.ref("newerp_base.carrier_np_branch")
        if "укрпошта" in method:
            return self.env.ref("newerp_base.carrier_ukrposhta")
        if "самовивіз" in method or "pickup" in method:
            return self.env.ref("newerp_base.carrier_pickup")
        return self.env["delivery.carrier"]

    def _customer(self, row):
        """The shop's customer by its id; a guest by e-mail or phone, so the same person is not doubled."""
        Partner = self.env["res.partner"]
        partner = Partner
        if row["customer_id"]:
            partner = Partner.search([("opencart_id", "=", row["customer_id"])], limit=1)
        if not partner and row["email"]:
            partner = Partner.search([("email", "=ilike", row["email"].strip())], limit=1)
        if not partner and (key := phone_key(row["telephone"])):
            partner = Partner.search([("newerp_phone_key", "=", key)], limit=1)
        values = {
            "name": f"{row['firstname'] or ''} {row['lastname'] or ''}".strip() or row["telephone"] or row["email"],
            "phone": row["telephone"] or False,
            "email": (row["email"] or "").strip() or False,
            "city": row["shipping_city"] or False,
            "street": row["shipping_address_1"] or False,
            "street2": row["shipping_address_2"] or False,
        }
        if not partner:
            # A guest has customer_id 0: no link then (an Integer field would keep False as 0).
            link = {"opencart_id": row["customer_id"]} if row["customer_id"] else {}
            return Partner.create({**values, **link})
        if row["customer_id"] and not partner.opencart_id:
            partner.opencart_id = row["customer_id"]
        return partner

    def _apply_status(self, order, status_id):
        tags = {**QUOTATION_STATUSES, **CONFIRMED_STATUSES}
        if tags.get(status_id):
            order.tag_ids = [(4, self.env.ref(tags[status_id]).id)]
        if status_id == CANCELLED_STATUS:
            order.action_cancel()
        elif status_id in CONFIRMED_STATUSES:
            order.action_confirm()

    # ── Stock to the storefront ──

    def _push_stock(self, source, templates=None):
        """Each linked size gets its free quantity in the shop's warehouse (on hand minus what orders reserved),
        rounded down; a product gets the sum of its sizes, or its own free quantity when it has no sizes. Only
        quantities that differ from the storefront's are written."""
        warehouse = self._stock_warehouse()
        if templates is None:
            templates = self.env["product.template"].search([("opencart_id", ">", 0)])
        templates = templates.with_context(warehouse_id=warehouse.id)
        # free_qty is computed, not stored, and kept in the cache: stock moved in this transaction must be read anew.
        self.env["product.product"].invalidate_model(["free_qty"])
        sizes, products = {}, {}
        for template in templates:
            linked = template.product_variant_ids.filtered(lambda v: v.opencart_id > 0)
            for variant in linked:
                sizes[variant.opencart_id] = max(int(variant.free_qty), 0)
            if linked:
                products[template.opencart_id] = sum(sizes[v.opencart_id] for v in linked)
            elif len(template.product_variant_ids) == 1:
                products[template.opencart_id] = max(int(template.product_variant_id.free_qty), 0)
        current_sizes, current_products = source.stock(list(sizes), list(products))
        changed_sizes = {row: qty for row, qty in sizes.items() if current_sizes.get(row) != qty}
        changed_products = {pid: qty for pid, qty in products.items() if current_products.get(pid) != qty}
        if changed_sizes or changed_products:
            source.write_stock(changed_sizes, changed_products)
        message = f"Розмірів: {len(changed_sizes)}, товарів: {len(changed_products)} (з {len(products)} пов'язаних)."
        return 0, len(changed_sizes) + len(changed_products), message

    def _stock_warehouse(self):
        warehouse_id = self.env["ir.config_parameter"].sudo().get_param(PARAM + "warehouse_id")
        warehouse = self.env["stock.warehouse"].browse(int(warehouse_id)).exists() if warehouse_id else None
        return warehouse or self.env.ref("stock.warehouse0")
