from odoo.tests import TransactionCase, tagged

from .common import WAREHOUSES, fake_novaposhta, pages, refused


@tagged("post_install", "-at_install")
class TestProvider(TransactionCase):
    """Nova Poshta as a delivery provider: the account, the branches and the rate (step 3a)."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.carrier = cls.env.ref("newerp_base.carrier_np_branch")
        cls.carrier.write(
            {
                "np_api_key": "test-np-key",
                "np_sender_city_ref": "city-kyiv",
                "np_sender_ref": "sender-ref",
                "np_contact_ref": "contact-ref",
                "np_sender_phone": "380670000000",
                "np_sender_warehouse_ref": "wh-kyiv-1",
            }
        )
        cls.customer = cls.env["res.partner"].create({"name": "Олена Петренко", "phone": "0671112233"})
        cls.dress = cls.env["product.product"].create({"name": "Сукня", "list_price": 1500, "weight": 0.4})

    def _order(self, quantity=2, branch=None):
        return self.env["sale.order"].create(
            {
                "partner_id": self.customer.id,
                "carrier_id": self.carrier.id,
                "np_warehouse_id": branch.id if branch else False,
                "order_line": [
                    (0, 0, {"product_id": self.dress.id, "product_uom_qty": quantity, "tax_ids": [(6, 0, [])]})
                ],
            }
        )

    def _branches(self):
        with fake_novaposhta({("Address", "getWarehouses"): pages(WAREHOUSES)}):
            self.carrier.action_np_update_warehouses()
        return self.env["newerp.np.warehouse"]

    def test_the_shops_nova_poshta_methods_became_this_provider(self):
        self.assertEqual(self.carrier.delivery_type, "novaposhta")
        locker = self.env.ref("newerp_base.carrier_np_locker")
        self.assertEqual((locker.delivery_type, locker.np_warehouse_kind), ("novaposhta", "locker"))

    def test_branches_are_imported_and_updated_by_ref(self):
        Branch = self._branches()
        kyiv = Branch.search([("ref", "=", "wh-kyiv-1")])
        self.assertEqual((kyiv.city_name, kyiv.number, kyiv.kind, kyiv.working), ("Київ", 1, "branch", True))
        self.assertEqual(Branch.search([("ref", "=", "wh-kyiv-2")]).kind, "locker")
        self.assertFalse(Branch.search([("ref", "=", "wh-lviv-12")]).working)
        self.assertEqual(kyiv.display_name, "Київ, Відділення №1: вул. Хрещатик, 1")

        # Nova Poshta renamed one and stopped listing the locker: renamed in place, the locker kept but closed.
        rows = [dict(WAREHOUSES[0], Description="Відділення №1: вул. Хрещатик, 3"), WAREHOUSES[2]]
        with fake_novaposhta({("Address", "getWarehouses"): pages(rows)}):
            self.carrier.action_np_update_warehouses()
        self.assertEqual(Branch.search_count([("ref", "like", "wh-")]), 3)
        self.assertEqual(kyiv.name, "Відділення №1: вул. Хрещатик, 3")
        self.assertFalse(Branch.search([("ref", "=", "wh-kyiv-2")]).working)

    def test_the_rate_comes_from_nova_poshta(self):
        branch = self._branches().search([("ref", "=", "wh-kyiv-1")])
        order = self._order(quantity=2, branch=branch)
        with fake_novaposhta({("InternetDocument", "getDocumentPrice"): [{"Cost": 85, "AssessedCost": 3000}]}) as np:
            rate = self.carrier.rate_shipment(order)
        self.assertTrue(rate["success"], rate)
        self.assertEqual(rate["price"], 85)
        [sent] = np.sent("InternetDocument", "getDocumentPrice")
        self.assertEqual((sent["CitySender"], sent["CityRecipient"]), ("city-kyiv", "city-kyiv"))
        self.assertEqual((sent["Weight"], sent["Cost"], sent["ServiceType"]), ("0.8", "3000", "WarehouseWarehouse"))

    def test_without_a_branch_or_with_an_error_the_rate_says_why(self):
        self.assertIn("відділення", self.carrier.rate_shipment(self._order())["error_message"])
        branch = self._branches().search([("ref", "=", "wh-kyiv-1")])
        with fake_novaposhta({("InternetDocument", "getDocumentPrice"): refused("API key expired")}):
            rate = self.carrier.rate_shipment(self._order(branch=branch))
        self.assertFalse(rate["success"])
        self.assertEqual(rate["error_message"], "Нова Пошта відмовила: API key expired")

    def test_without_a_key_the_carrier_is_a_fixed_price(self):
        self.carrier.np_api_key = False
        with fake_novaposhta({}) as np:
            rate = self.carrier.rate_shipment(self._order())
        self.assertEqual((rate["success"], rate["price"]), (True, 0))
        self.assertEqual(np.calls, [])

    def test_the_key_is_hidden_from_non_admins(self):
        manager = self.env["res.users"].create(
            {
                "name": "Марта",
                "login": "np-manager",
                "group_ids": [(6, 0, [self.env.ref("newerp_base.group_manager").id])],
            }
        )
        self.assertNotIn("np_api_key", self.env["delivery.carrier"].with_user(manager).fields_get())
