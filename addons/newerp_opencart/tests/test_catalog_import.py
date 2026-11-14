from unittest.mock import patch

from odoo.addons.newerp_opencart.models.opencart_source import MySqlOpenCartSource, OpenCartConfig, OpenCartError
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from .fake_source import FakeOpenCartSource, category, product


@tagged("post_install", "-at_install")
class TestCatalogImport(TransactionCase):
    """Categories and products with sizes from the shop (rows like the devseed of NewErpPython)."""

    def setUp(self):
        super().setUp()
        self.source = FakeOpenCartSource(
            categories=[category(21, "Сорочки", parent_id=20), category(20, "Одяг")],
            products=[
                product(101, "Сукня лляна", "SL-01", 1500.0, [20], sizes=[(501, "S"), (502, "M"), (503, "L")]),
                product(102, "Сорочка оверсайз", "SO-02", 900.0, [21], sizes=[(504, "M")], status=0),
                product(103, "Пояс шкіряний", "P-03", 450.0),
            ],
        )
        patcher = patch.object(type(self.env["newerp.opencart.sync"]), "_opencart_source", return_value=self.source)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sync = self.env["newerp.opencart.sync"]

    def _template(self, opencart_id):
        return self.env["product.template"].search([("opencart_id", "=", opencart_id)])

    def test_categories_products_and_sizes_are_imported(self):
        run = self.sync.import_catalog()
        self.assertEqual((run.state, run.created, run.updated), ("done", 3, 0))

        shirts = self.env["product.category"].search([("opencart_id", "=", 21)])
        self.assertEqual((shirts.name, shirts.parent_id.name), ("Сорочки", "Одяг"))  # the parent came later in the list

        dress = self._template(101)
        self.assertEqual((dress.name, dress.list_price), ("Сукня лляна", 1500))
        # With several variants the internal reference is on each variant: the model and the size.
        self.assertEqual(sorted(dress.product_variant_ids.mapped("default_code")), ["SL-01-L", "SL-01-M", "SL-01-S"])
        self.assertTrue(dress.is_storable and dress.sale_ok)
        self.assertEqual(dress.categ_id.name, "Одяг")
        sizes = {v.product_template_attribute_value_ids.name: v.opencart_id for v in dress.product_variant_ids}
        self.assertEqual(sizes, {"S": 501, "M": 502, "L": 503})

        self.assertFalse(self._template(102).sale_ok)  # off in the shop
        belt = self._template(103)
        self.assertEqual((len(belt.product_variant_ids), belt.default_code), (1, "P-03"))  # no sizes, one product

    def test_importing_again_updates_and_adds_nothing_twice(self):
        self.sync.import_catalog()
        self.source.product_rows[0]["price"] = 1600.0
        self.source.product_rows[0]["sizes"].append({"id": 505, "name": "XXL"})  # a size Odoo does not know yet
        self.source.category_rows[1]["name"] = "Жіночий одяг"

        run = self.sync.import_catalog()
        self.assertEqual((run.created, run.updated), (0, 1))
        self.assertEqual(self.env["product.template"].search_count([("opencart_id", "in", [101, 102, 103])]), 3)
        dress = self._template(101)
        self.assertEqual(dress.list_price, 1600)
        self.assertEqual(dress.categ_id.name, "Жіночий одяг")
        xxl = dress.product_variant_ids.filtered(lambda v: v.opencart_id == 505)
        self.assertEqual(xxl.product_template_attribute_value_ids.name, "XXL")
        self.assertIn("XXL", self.env.ref("newerp_base.attribute_size").value_ids.mapped("name"))

    def test_a_failed_connection_is_written_down_and_told(self):
        self.source.fail = True
        with self.assertRaises(UserError):
            self.sync.import_catalog()
        run = self.sync.import_catalog(raise_errors=False)
        self.assertEqual(run.state, "failed")
        self.assertIn("2003", run.message)

    def test_the_table_prefix_cannot_carry_sql(self):
        config = OpenCartConfig(host="db", port=3306, database="shop", user="u", password="test-password")
        MySqlOpenCartSource(config)  # dd_ is fine
        for prefix in ("dd_; DROP TABLE x", "dd`", "../"):
            with self.assertRaises(OpenCartError):
                MySqlOpenCartSource(OpenCartConfig(**{**config.__dict__, "prefix": prefix}))

    def test_runs_are_for_the_admin_only(self):
        self.sync.import_catalog()
        manager = new_test_user(self.env, login="oc-manager", groups="newerp_base.group_manager")
        admin = new_test_user(self.env, login="oc-admin", groups="newerp_base.group_admin")
        with self.assertRaises(AccessError):
            self.env["newerp.opencart.run"].with_user(manager).search([])
        self.assertTrue(self.env["newerp.opencart.run"].with_user(admin).search([]))
