from datetime import datetime

from odoo.addons.newerp_bank_ua.models.bank_matching import (
    Candidate,
    Reason,
    Scored,
    confident_match,
    is_confident,
    order_numbers_in,
    rank,
)
from odoo.tests import BaseCase, tagged


def candidate(key=5, total=2000.0, linked=False, numbers=(), phone="0670000002", customer="Тарас Клієнт", **kw):
    return Candidate(key=key, numbers=frozenset(numbers), customer=customer, phone=phone, total=total,
                     advance=kw.get("advance", 0.0), paid=kw.get("paid", 0.0), linked=linked,
                     date=datetime(2026, 10, 1))  # fmt: skip


def scored(key, reasons, linked=False):
    return Scored(candidate(key, linked=linked), reasons, 0)


@tagged("post_install", "-at_install")
class TestMatchingRules(BaseCase):
    """The rules of NewErpPython (tests/test_payment_auto_match.py), without a database."""

    def test_a_confident_order_is_named_and_the_sum_fits(self):
        self.assertTrue(is_confident(scored(5, Reason.ORDER_NUMBER | Reason.TOTAL)))
        self.assertTrue(is_confident(scored(5, Reason.PHONE | Reason.PREPAYMENT)))
        self.assertFalse(is_confident(scored(5, Reason.NAME | Reason.TOTAL)))  # a namesake with the same sum
        self.assertFalse(is_confident(scored(5, Reason.ORDER_NUMBER)))  # the sum differs
        self.assertFalse(is_confident(scored(5, Reason.PHONE | Reason.TOTAL, linked=True)))  # already paid

    def test_only_exactly_one_confident_order_is_linked(self):
        sure = scored(5, Reason.ORDER_NUMBER | Reason.TOTAL)
        other = scored(6, Reason.PHONE | Reason.TOTAL)
        weak = scored(7, Reason.NAME)
        self.assertEqual(confident_match([sure, weak]).key, 5)
        self.assertIsNone(confident_match([sure, other]))  # two: a question for a person
        self.assertIsNone(confident_match([weak]))

    def test_order_numbers_are_not_parts_of_sums(self):
        self.assertEqual(order_numbers_in("Оплата зам. 2045 на суму 1500.00, S00042"), [2045, 42])

    def test_the_ranking_reads_the_number_the_sum_the_phone_and_the_surname(self):
        named = candidate(1, numbers=[2045], total=1500.0)
        by_phone = candidate(2, phone="+38 (067) 111-22-33", total=900.0, advance=300.0)
        namesake = candidate(3, customer="Ірина Іваненко", total=1500.0)
        paid = candidate(4, numbers=[2045], total=1500.0, linked=True)
        ranked = rank("Оплата зам. 2045 від Іваненко, тел. 0671112233", 1500.0, [named, by_phone, namesake, paid])
        reasons = {s.candidate.key: (s.reasons, s.score) for s in ranked}
        self.assertEqual(reasons[1], (Reason.ORDER_NUMBER | Reason.TOTAL, 75))
        self.assertEqual(reasons[2], (Reason.PHONE, 30))
        self.assertEqual(reasons[3], (Reason.TOTAL | Reason.NAME, 40))
        self.assertEqual(reasons[4], (Reason.ORDER_NUMBER | Reason.TOTAL, 35))  # another payment is linked already
        self.assertEqual(ranked[0].candidate.key, 1)

    def test_the_advance_and_the_rest_fit_as_a_prepayment(self):
        order = candidate(1, total=900.0, advance=300.0)
        self.assertEqual(rank("", 300.0, [order])[0].reasons, Reason.PREPAYMENT)
        self.assertEqual(rank("", 600.0, [order])[0].reasons, Reason.PREPAYMENT)
        self.assertEqual(rank("", 400.0, [candidate(1, total=900.0, paid=500.0)])[0].reasons, Reason.PREPAYMENT)
