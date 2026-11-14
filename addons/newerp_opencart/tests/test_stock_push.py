from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from .fake_source import FakeOpenCartSource, product


@tagged("post_install", "-at_install")
class TestStockPush(TransactionCase):
    """The ERP's free stock goes to the storefront, per size row and per product, like the Python version's push."""

    def setUp(self):
        super().setUp()
        self.source = FakeOpenCartSource(
            products=[
                product(101, "Сукня лляна", "SL-01", 1500.0, sizes=[(501, "S"), (502, "M")]),
                product(103, "Пояс шкіряний", "P-03", 450.0),
            ]
        )
        patcher = patch.object(type(self.env["newerp.opencart.sync"]), "_opencart_source", return_value=self.source)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.sync = self.env["newerp.opencart.sync"]
        self.sync.import_catalog()
        self.stock = self.env.ref("stock.warehouse0").lot_stock_id

    def _variant(self, opencart_id):
        return self.env["product.product"].search([("opencart_id", "=", opencart_id)])

    def _receive(self, variant, quantity):
        self.env["stock.quant"]._update_available_quantity(variant, self.stock, quantity)

    def test_free_stock_goes_per_size_and_per_product(self):
        self._receive(self._variant(501), 3)
        belt = self.env["product.template"].search([("opencart_id", "=", 103)]).product_variant_id
        self._receive(belt, 2.7)  # rounded down: the storefront counts whole pieces

        run = self.sync.push_stock()
        self.assertEqual(run.state, "done")
        self.assertEqual(self.source.size_stock, {501: 3, 502: 0})
        self.assertEqual(self.source.product_stock, {101: 3, 103: 2})

    def test_what_orders_reserved_is_not_offered_again(self):
        variant = self._variant(502)
        self._receive(variant, 3)
        customer = self.env["res.partner"].create({"name": "Олена"})
        order = self.env["sale.order"].create(
            {"partner_id": customer.id, "order_line": [(0, 0, {"product_id": variant.id, "product_uom_qty": 1})]}
        )
        order.action_confirm()
        order.picking_ids.action_assign()

        self.sync.push_stock()
        self.assertEqual(self.source.size_stock[502], 2)

    def test_only_changed_quantities_are_written(self):
        self.source.size_stock = {501: 0, 502: 0}
        self.source.product_stock = {101: 0, 103: 0}
        run = self.sync.push_stock()
        self.assertEqual(run.updated, 0)
        self.assertEqual(self.source.written, [])

        self._receive(self._variant(501), 1)
        run = self.sync.push_stock()
        self.assertEqual(self.source.written, [({501: 1}, {101: 1})])
        self.assertEqual(run.updated, 2)

    def test_a_push_can_be_limited_to_some_products(self):
        dress = self.env["product.template"].search([("opencart_id", "=", 101)])
        self.sync.push_stock(templates=dress)
        self.assertEqual(set(self.source.product_stock), {101})
