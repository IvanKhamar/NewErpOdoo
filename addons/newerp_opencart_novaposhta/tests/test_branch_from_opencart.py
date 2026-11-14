from unittest.mock import patch

from odoo.addons.newerp_opencart.tests.fake_source import FakeOpenCartSource, order, product
from odoo.tests import TransactionCase, tagged

BELT = (103, "Пояс шкіряний", 1, 450.0, None)


@tagged("post_install", "-at_install")
class TestBranchFromOpenCart(TransactionCase):
    """Orders from OpenCart get their Nova Poshta branch from the text OpenCart keeps."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        Branch = cls.env["newerp.np.warehouse"]
        cls.kyiv_1 = Branch.create(
            {"ref": "wh-kyiv-1", "name": "Відділення №1: вул. Хрещатик, 1", "number": 1, "city_ref": "city-kyiv",
             "city_name": "Київ"}
        )  # fmt: skip
        cls.kyiv_7 = Branch.create(
            {"ref": "wh-kyiv-7", "name": "Відділення №7 (до 30 кг): вул. Саксаганського, 7", "number": 7,
             "city_ref": "city-kyiv", "city_name": "Київ"}
        )  # fmt: skip
        cls.lviv_1 = Branch.create(
            {"ref": "wh-lviv-1", "name": "Відділення №1", "number": 1, "city_ref": "city-lviv", "city_name": "Львів"}
        )
        cls.env["newerp.np.city"].create({"ref": "city-kyiv", "name": "Київ"})

    def setUp(self):
        super().setUp()
        self.source = FakeOpenCartSource(products=[product(103, "Пояс шкіряний", "P-03", 450.0)])
        patcher = patch.object(type(self.env["newerp.opencart.sync"]), "_opencart_source", return_value=self.source)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.env["newerp.opencart.sync"].import_catalog()

    def _import(self, **customer):
        row = order(2001, 24, [BELT], **customer)
        self.source.order_rows = [row]
        self.env["newerp.opencart.sync"].import_orders()
        return self.env["sale.order"].search([("opencart_id", "=", 2001)])

    def _with_branch_text(self, text, **customer):
        row = order(2001, 24, [BELT], **customer)
        row["shipping_address_2"] = text
        self.source.order_rows = [row]
        self.env["newerp.opencart.sync"].import_orders()
        return self.env["sale.order"].search([("opencart_id", "=", 2001)])

    def test_the_branch_is_found_by_its_name_in_the_city(self):
        sale = self._with_branch_text("Відділення №1: вул. Хрещатик, 1")
        self.assertEqual(sale.carrier_id, self.env.ref("newerp_base.carrier_np_branch"))
        self.assertEqual(sale.np_warehouse_id, self.kyiv_1)  # not Lviv's №1

    def test_else_by_its_number_in_the_city(self):
        self.assertEqual(self._with_branch_text("Відділення № 7").np_warehouse_id, self.kyiv_7)

    def test_unsure_leaves_it_for_the_manager(self):
        self.assertFalse(self._with_branch_text("біля метро").np_warehouse_id)

    def test_the_courier_gets_the_city(self):
        sale = self._import(shipping_method="Нова Пошта: кур'єр")
        self.assertEqual(sale.carrier_id, self.env.ref("newerp_novaposhta.carrier_np_door"))
        self.assertEqual(sale.np_city_id.name, "Київ")
        self.assertFalse(sale.np_warehouse_id)
