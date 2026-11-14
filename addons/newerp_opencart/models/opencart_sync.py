import logging

from odoo import api, models
from odoo.exceptions import UserError

from .opencart_source import MySqlOpenCartSource, OpenCartConfig, OpenCartError

_logger = logging.getLogger(__name__)

PARAM = "newerp_opencart."


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
