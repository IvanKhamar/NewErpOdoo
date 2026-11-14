from unittest.mock import patch

from odoo.tests import TransactionCase, tagged

from .fake_source import FakeOpenCartSource, order, product

DRESS = (101, "Сукня лляна")
BELT = (103, "Пояс шкіряний")


@tagged("post_install", "-at_install")
class TestOrderImport(TransactionCase):
    """Customers and orders from the shop, with the status table of docs/plan.md."""

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

    def _order(self, opencart_id):
        return self.env["sale.order"].search([("opencart_id", "=", opencart_id)])

    def test_an_order_with_two_sizes_and_a_product_without_sizes(self):
        self.source.order_rows = [
            order(1001, 18, [(*DRESS, 1, 1500.0, 501), (*DRESS, 2, 1500.0, 502), (*BELT, 1, 450.0, None)])
        ]
        run = self.sync.import_orders()
        self.assertEqual((run.state, run.created, run.updated), ("done", 1, 0))

        sale = self._order(1001)
        self.assertEqual(sale.state, "sale")  # 2) Прийнято: confirmed
        self.assertEqual(
            sorted((line.product_id.default_code, line.product_uom_qty) for line in sale.order_line),
            [("P-03", 1), ("SL-01-M", 2), ("SL-01-S", 1)],
        )
        self.assertEqual(sale.amount_total, 4950)  # the shop's prices, no tax on top
        self.assertEqual((sale.partner_id.name, sale.partner_id.city), ("Олена Петренко", "Київ"))
        self.assertEqual(sale.source_id.name, "Instagram")
        self.assertEqual(sale.carrier_id, self.env.ref("newerp_base.carrier_np_branch"))
        self.assertEqual(sale.payment_term_id, self.env.ref("newerp_base.payment_term_cod"))
        self.assertEqual(sale.origin, "OpenCart #1001")

    def test_a_guest_is_found_again_by_phone_however_it_was_typed(self):
        known = self.env["res.partner"].create({"name": "Олена П.", "phone": "+38 (067) 111-22-33"})
        self.source.order_rows = [order(1002, 24, [(*BELT, 1, 450.0, None)], telephone="0671112233")]
        self.sync.import_orders()
        self.assertEqual(self._order(1002).partner_id, known)

    def test_two_guests_get_two_customers(self):
        """A guest has customer_id 0; two of them must not collide on the OpenCart link."""
        self.source.order_rows = [
            order(1010, 24, [(*BELT, 1, 450.0, None)], telephone="0670000010", firstname="Ірина"),
            order(1011, 24, [(*BELT, 1, 450.0, None)], telephone="0670000011", firstname="Тарас"),
        ]
        self.sync.import_orders()
        self.assertEqual(len(self._order(1010).partner_id | self._order(1011).partner_id), 2)

    def test_statuses_map_onto_odoo_states_and_tags(self):
        self.source.order_rows = [
            order(1003, 24, [(*BELT, 1, 450.0, None)]),  # 1) Уточнюємо
            order(1004, 19, [(*BELT, 1, 450.0, None)]),  # Відмінено
            order(1005, 23, [(*BELT, 1, 450.0, None)]),  # Терміново
            order(1006, 1, [(*BELT, 1, 450.0, None)]),  # Перевірити оплату
        ]
        self.sync.import_orders()
        self.assertEqual(self._order(1003).state, "draft")
        self.assertEqual(self._order(1004).state, "cancel")
        self.assertEqual((self._order(1005).state, self._order(1005).tag_ids.name), ("sale", "Терміново"))
        self.assertEqual((self._order(1006).state, self._order(1006).tag_ids.name), ("draft", "Перевірити оплату"))

    def test_importing_again_follows_a_quotation_and_leaves_a_confirmed_order(self):
        self.source.order_rows = [
            order(1007, 24, [(*BELT, 1, 450.0, None)]),
            order(1008, 18, [(*BELT, 1, 450.0, None)]),
        ]
        self.sync.import_orders()
        self.assertEqual(self.source.asked_since, ["2000-01-01 00:00:00"])

        changed = "2026-11-02 12:00:00"
        self.source.order_rows = [
            order(1007, 18, [(*BELT, 3, 450.0, None)], changed=changed),  # accepted, and 3 belts now
            order(1008, 18, [(*BELT, 9, 450.0, None)], changed=changed),  # already confirmed in Odoo
        ]
        run = self.sync.import_orders()
        self.assertEqual(self.source.asked_since[-1], "2026-11-01 10:00:00")  # starts at the last change seen
        self.assertEqual((run.created, run.updated), (0, 1))
        self.assertEqual((self._order(1007).state, self._order(1007).order_line.product_uom_qty), ("sale", 3))
        self.assertEqual(self._order(1008).order_line.product_uom_qty, 1)

    def test_an_order_with_an_unknown_product_is_skipped_and_named(self):
        self.source.order_rows = [order(1009, 18, [(999, "Шарф", 1, 300.0, None)])]
        run = self.sync.import_orders()
        self.assertFalse(self._order(1009))
        self.assertIn("#1009", run.message)
        self.assertIn("«Шарф» (999)", run.message)
