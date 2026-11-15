from odoo import fields
from odoo.tests import TransactionCase, tagged

PAID = ("paid", "in_payment")


@tagged("post_install", "-at_install")
class TestReconciliation(TransactionCase):
    """A payment linked to an order with a posted invoice pays the invoice, as Odoo's reconciliation would."""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.journal = cls.env["account.journal"].create({"name": "ПриватБанк", "type": "bank", "code": "PRVT"})
        cls.product = cls.env["product.product"].create(
            {"name": "Сукня лляна", "list_price": 1500.0, "taxes_id": [], "invoice_policy": "order"}
        )
        cls.partner = cls.env["res.partner"].create({"name": "Ірина Іваненко"})

    def _order(self, price=1500.0):
        order = self.env["sale.order"].create(
            {
                "partner_id": self.partner.id,
                "order_line": [
                    fields.Command.create({"product_id": self.product.id, "price_unit": price, "tax_ids": []})
                ],
            }
        )
        order.action_confirm()
        return order

    def _invoice(self, order):
        invoice = order._create_invoices()
        invoice.action_post()
        return invoice

    def _payment(self, amount, ref="tx-1"):
        return self.env["account.bank.statement.line"].create(
            {"journal_id": self.journal.id, "date": fields.Date.today(), "amount": amount,
             "payment_ref": "Оплата", "newerp_bank_ref": ref}
        )  # fmt: skip

    def test_linking_pays_the_posted_invoice_and_unlinking_undoes_it(self):
        order = self._order()
        invoice = self._invoice(order)
        line = self._payment(1500.0)

        line._newerp_link(order)
        self.assertIn(invoice.payment_state, PAID)
        self.assertTrue(line.is_reconciled)

        line.action_newerp_unlink_order()
        self.assertEqual(invoice.payment_state, "not_paid")
        self.assertFalse(line.is_reconciled)
        _liquidity, suspense, _others = line._seek_for_lines()
        self.assertEqual(len(suspense), 1)  # back in the suspense account

    def test_an_advance_pays_part_of_the_invoice(self):
        order = self._order(price=900.0)
        invoice = self._invoice(order)
        self._payment(300.0)._newerp_link(order)
        self.assertEqual(invoice.payment_state, "partial")
        self.assertEqual(invoice.amount_residual, 600.0)

    def test_a_payment_before_the_invoice_is_reconciled_when_the_invoice_is_posted(self):
        order = self._order()
        line = self._payment(1500.0)
        line._newerp_link(order)
        self.assertFalse(line.is_reconciled)  # no invoice yet: the link alone

        invoice = self._invoice(order)
        self.assertIn(invoice.payment_state, PAID)
        self.assertTrue(line.is_reconciled)

    def test_an_order_without_an_invoice_keeps_the_line_in_suspense(self):
        line = self._payment(1500.0)
        line._newerp_link(self._order())
        _liquidity, suspense, others = line._seek_for_lines()
        self.assertEqual((len(suspense), len(others)), (1, 0))
