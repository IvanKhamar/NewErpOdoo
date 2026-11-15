from odoo import fields
from odoo.exceptions import AccessError, UserError
from odoo.tests import TransactionCase, new_test_user, tagged

from .common import fake_privatbank, statement


@tagged("post_install", "-at_install")
class TestImportAndMatching(TransactionCase):
    """Statement rows become bank statement lines; an incoming payment that exactly one order fits is linked."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.env["account.journal"].create(
            {"name": "ПриватБанк", "type": "bank", "code": "PRVT", "newerp_bank_source": "privatbank",
             "newerp_privat_client_id": "client-id", "newerp_privat_token": "test-token"}
        )  # fmt: skip
        cls.today = fields.Date.context_today(cls.env["res.partner"])
        cls.day = cls.today.strftime("%d.%m.%Y")
        cls.product = cls.env["product.product"].create({"name": "Сукня лляна", "list_price": 1500.0, "taxes_id": []})
        cls.iryna = cls.env["res.partner"].create({"name": "Ірина Іваненко", "phone": "+38 (067) 111-22-33"})
        cls.taras = cls.env["res.partner"].create({"name": "Тарас Шевчук", "phone": "0501234567"})
        cls.check_payment = cls.env.ref("newerp_base.tag_check_payment")

    def _order(self, partner, price=1500.0):
        return self.env["sale.order"].create(
            {
                "partner_id": partner.id,
                "tag_ids": [fields.Command.link(self.check_payment.id)],
                "order_line": [
                    fields.Command.create({"product_id": self.product.id, "price_unit": price, "tax_ids": []})
                ],
            }
        )

    def _import(self, *rows):
        with fake_privatbank(statement(*rows)):
            return self.env["newerp.bank.import"].import_statements(self.journal)

    def _line(self, ref):
        return self.env["account.bank.statement.line"].search([("newerp_bank_ref", "=", ref)])

    def test_importing_twice_adds_nothing_and_keeps_outgoing_rows(self):
        rows = [("tx-1", "C", 700.0, self.day, "Поповнення", "Хтось"), ("tx-2", "D", 200.0, self.day, "Комісія", "")]
        self.assertEqual(self._import(*rows), {"fetched": 2, "added": 2, "linked": 0})
        self.assertEqual(self._import(*rows), {"fetched": 2, "added": 0, "linked": 0})
        self.assertEqual(self._line("tx-2").amount, -200.0)  # the journal's balance needs the outgoing money too
        self.assertEqual(self._line("tx-1").journal_id, self.journal)

    def test_a_payment_naming_its_order_with_the_right_sum_is_linked(self):
        sale = self._order(self.iryna)
        result = self._import(("tx-1", "C", 1500.0, self.day, f"Оплата замовлення {sale.name}", "Іваненко Ірина"))
        self.assertEqual(result["linked"], 1)
        line = self._line("tx-1")
        self.assertEqual(line.newerp_sale_order_id, sale)
        self.assertEqual(line.partner_id, self.iryna)
        self.assertNotIn(self.check_payment, sale.tag_ids)  # the manager no longer has to check it
        self.assertEqual(sale.newerp_bank_paid, 1500.0)

    def test_two_confident_orders_are_left_for_a_person(self):
        first, second = self._order(self.iryna), self._order(self.iryna)
        self._import(("tx-1", "C", 1500.0, self.day, "Оплата, тел. 0671112233", "Іваненко Ірина"))
        self.assertFalse(self._line("tx-1").newerp_sale_order_id)
        self.assertIn(self.check_payment, first.tag_ids | second.tag_ids)

    def test_a_surname_and_a_sum_are_not_enough(self):
        self._order(self.iryna)
        self._import(("tx-1", "C", 1500.0, self.day, "Оплата за сукню", "Іваненко Ірина"))
        self.assertFalse(self._line("tx-1").newerp_sale_order_id)

    def test_a_liqpay_payout_is_never_linked(self):
        sale = self._order(self.iryna)
        self._import(("tx-1", "C", 1500.0, self.day, f"LiqPay: виплата {sale.name}", "LiqPay"))
        self.assertFalse(self._line("tx-1").newerp_sale_order_id)

    def test_the_second_payment_of_one_order_is_not_linked_automatically(self):
        sale = self._order(self.iryna)
        self._import(
            ("tx-1", "C", 1500.0, self.day, f"Оплата {sale.name}", "Іваненко Ірина"),
            ("tx-2", "C", 1500.0, self.day, f"Оплата {sale.name}", "Іваненко Ірина"),
        )
        self.assertEqual(self._line("tx-1").newerp_sale_order_id, sale)
        self.assertFalse(self._line("tx-2").newerp_sale_order_id)

    def test_auto_match_links_an_older_payment_once_its_order_exists(self):
        self._import(("tx-1", "C", 900.0, self.day, "Оплата, тел. 0501234567", "Шевчук Т."))
        sale = self._order(self.taras, price=900.0)
        self.env["account.bank.statement.line"].action_newerp_auto_match()
        self.assertEqual(self._line("tx-1").newerp_sale_order_id, sale)

    def test_a_manager_finds_links_and_unlinks_by_hand(self):
        first, second = self._order(self.iryna), self._order(self.iryna)
        self._import(("tx-1", "C", 1500.0, self.day, "Оплата, тел. 0671112233", "Іваненко Ірина"))
        manager = new_test_user(self.env, "bank-manager", groups="base.group_user,newerp_base.group_manager")
        line = self._line("tx-1").with_user(manager)

        wizard = self.env["newerp.bank.match.wizard"].browse(line.action_newerp_find_order()["res_id"])
        self.assertEqual(set(wizard.candidate_ids.order_id.ids), {first.id, second.id})
        self.assertIn("телефон", wizard.candidate_ids[0].reasons)
        wizard.with_user(manager).candidate_ids.filtered(lambda c: c.order_id == second).action_link()
        self.assertEqual(line.newerp_sale_order_id, second)
        with self.assertRaises(UserError):
            line.action_newerp_find_order()  # unlink first

        line.action_newerp_unlink_order()
        self.assertFalse(line.newerp_sale_order_id)
        line.action_newerp_hide()
        self.assertTrue(line.newerp_hidden)

    def test_the_search_finds_an_order_of_any_date(self):
        sale = self._order(self.taras, price=100.0)
        self._import(("tx-1", "C", 1500.0, self.day, "Переказ", "Невідомо"))
        wizard = self.env["newerp.bank.match.wizard"].browse(self._line("tx-1").action_newerp_find_order()["res_id"])
        self.assertNotIn(sale, wizard.candidate_ids.order_id)  # nothing fits
        wizard.search_text = "Шевчук"
        wizard.action_search()
        self.assertIn(sale, wizard.candidate_ids.order_id)

    def test_only_a_manager_links_payments(self):
        self._import(("tx-1", "C", 700.0, self.day, "Поповнення", "Хтось"))
        storekeeper = new_test_user(
            self.env, "bank-storekeeper", groups="base.group_user,newerp_base.group_storekeeper"
        )
        with self.assertRaises(AccessError):
            self.env["account.bank.statement.line"].with_user(storekeeper).action_newerp_auto_match()

    def test_a_period_longer_than_a_month_is_refused(self):
        with self.assertRaises(UserError):
            self.env["newerp.bank.import"].import_statements(
                self.journal, fields.Date.add(self.today, days=-40), self.today
            )
