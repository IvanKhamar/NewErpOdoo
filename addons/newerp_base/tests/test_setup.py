from odoo.exceptions import AccessError
from odoo.tests import TransactionCase, new_test_user, tagged


@tagged("post_install", "-at_install")
class TestSetup(TransactionCase):
    """Phase 1: the standard apps set up for the shop: variants, sources, tags, terms, delivery, warehouse, roles."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.customer = cls.env["res.partner"].create({"name": "Олена Тестова", "city": "Київ"})

    def test_sizes_and_colours_make_the_variants(self):
        size = self.env.ref("newerp_base.attribute_size")
        colour = self.env.ref("newerp_base.attribute_colour")
        self.assertEqual(size.value_ids.mapped("name"), ["S", "M", "L", "XL"])
        dress = self.env["product.template"].create(
            {
                "name": "Сукня лляна",
                "attribute_line_ids": [
                    (0, 0, {"attribute_id": size.id, "value_ids": [(6, 0, size.value_ids.ids)]}),
                    (0, 0, {"attribute_id": colour.id, "value_ids": [(6, 0, colour.value_ids[:2].ids)]}),
                ],
            }
        )
        self.assertEqual(dress.product_variant_count, 8)  # 4 sizes x 2 colours

    def test_sources_tags_and_payment_terms_are_ready_for_orders(self):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "source_id": self.env.ref("newerp_base.source_instagram").id,
                "tag_ids": [(4, self.env.ref("newerp_base.tag_urgent").id)],
                "payment_term_id": self.env.ref("newerp_base.payment_term_cod").id,
            }
        )
        self.assertEqual(order.source_id.name, "Instagram")
        self.assertEqual(order.tag_ids.name, "Терміново")
        self.assertEqual(order.payment_term_id.line_ids.value_amount, 100)

    def test_a_delivery_method_rates_an_order(self):
        carriers = self.env["delivery.carrier"].search([("product_id.name", "like", "Доставка:")])
        self.assertEqual(len(carriers), 3)  # Nova Poshta branch and locker, Ukrposhta; pickup is named apart
        product = self.env["product.product"].create({"name": "Сорочка", "list_price": 900, "is_storable": True})
        order = self.env["sale.order"].create(
            {"partner_id": self.customer.id, "order_line": [(0, 0, {"product_id": product.id})]}
        )
        rate = self.env.ref("newerp_base.carrier_np_branch").rate_shipment(order)
        self.assertTrue(rate["success"])
        self.assertEqual(rate["price"], 0)

    def test_the_main_warehouse_is_in_kyiv(self):
        warehouse = self.env.ref("stock.warehouse0")
        self.assertEqual((warehouse.name, warehouse.code), ("Склад Київ", "KYIV"))

    def test_the_roles_open_only_their_apps(self):
        manager = new_test_user(self.env, login="newerp-manager", groups="newerp_base.group_manager")
        storekeeper = new_test_user(self.env, login="newerp-storekeeper", groups="newerp_base.group_storekeeper")
        admin = new_test_user(self.env, login="newerp-admin", groups="newerp_base.group_admin")

        # Standard Odoo, kept on purpose: a salesperson's confirmed order creates its manufacturing orders (sale_mrp),
        # and warehouse users read and update sales orders. The roles split the apps, not those links.
        self.env["sale.order"].with_user(manager).check_access("create")
        self.env["account.move"].with_user(manager).check_access("create")
        self.assertFalse(manager.has_group("mrp.group_mrp_user") or manager.has_group("stock.group_stock_user"))
        with self.assertRaises(AccessError):
            self.env["mrp.production"].with_user(manager).check_access("unlink")
        with self.assertRaises(AccessError):
            self.env["purchase.order"].with_user(manager).check_access("create")

        self.env["mrp.production"].with_user(storekeeper).check_access("create")
        self.env["purchase.order"].with_user(storekeeper).check_access("create")
        self.assertFalse(storekeeper.has_group("sales_team.group_sale_salesman"))
        with self.assertRaises(AccessError):
            self.env["sale.order"].with_user(storekeeper).check_access("create")
        # A purchase user may create vendor bills (account.move), but not work with customer invoices and payments.
        self.assertFalse(storekeeper.has_group("account.group_account_invoice"))

        self.assertTrue(admin.has_group("base.group_system"))
        self.assertTrue(admin.has_group("newerp_base.group_manager"))
        self.assertTrue(admin.has_group("newerp_base.group_storekeeper"))
