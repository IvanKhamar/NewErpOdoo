import json
from contextlib import contextmanager
from datetime import date
from unittest.mock import patch

from odoo.addons.newerp_bank_ua.models.monobank_api import MonobankApi
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

# The example of monobank's documentation (api.monobank.ua/docs, /personal/statement).
ROW = {
    "id": "ZuHWzqkKGVo=", "time": 1554466347, "description": "Покупка щастя", "mcc": 7997, "originalMcc": 7997,
    "hold": False, "amount": -95000, "operationAmount": -95000, "currencyCode": 980, "commissionRate": 0,
    "cashbackAmount": 19000, "balance": 10050000, "comment": "За каву", "receiptId": "XXXX-XXXX-XXXX-XXXX",
    "invoiceId": "2103.в.27", "counterEdrpou": "3096889974", "counterIban": "UA898999980000355639201001404",
    "counterName": "ТОВАРИСТВО З ОБМЕЖЕНОЮ ВІДПОВІДАЛЬНІСТЮ «ВОРОНА»",
}  # fmt: skip
INCOMING = {"id": "mono-2", "time": 1792065600, "description": "Від: Іваненко Ірина", "amount": 150000,
            "comment": "Оплата замовлення 2045", "counterName": "Іваненко Ірина"}  # fmt: skip


class FakeResponse:
    def __init__(self, answer, status_code=200):
        self._answer = answer
        self.status_code = status_code
        self.ok = status_code < 400

    def json(self):
        return self._answer


@contextmanager
def fake_monobank(answer, status_code=200):
    calls = []

    def get(url, headers=None, timeout=None):
        calls.append({"url": url, "headers": headers})
        return FakeResponse(answer, status_code)

    with patch("odoo.addons.newerp_bank_ua.models.monobank_api.requests.get", side_effect=get):
        yield calls


@tagged("post_install", "-at_install")
class TestMonobankApi(TransactionCase):
    """The client without a network: requests.get answers with monobank's documented JSON."""

    def test_a_row_in_kopecks_and_unix_time_becomes_a_kyiv_row(self):
        with fake_monobank([ROW, INCOMING]):
            spent, paid = MonobankApi(self.env, "test-token").statement(date(2019, 4, 5), date(2019, 4, 5))
        self.assertEqual((spent.ref, spent.amount), ("ZuHWzqkKGVo=", -950.0))
        self.assertEqual((spent.date, spent.time), (date(2019, 4, 5), "15:12"))  # 12:12 UTC is 15:12 in Kyiv
        self.assertEqual(spent.purpose, "За каву Покупка щастя")
        self.assertEqual(spent.payer_account, "UA898999980000355639201001404")
        self.assertEqual(spent.details["payer_tax_code"], "3096889974")
        self.assertEqual((paid.amount, paid.payer), (1500.0, "Іваненко Ірина"))
        self.assertIn("2045", paid.purpose)

    def test_it_asks_for_whole_kyiv_days_with_the_token_header(self):
        with fake_monobank([]) as calls:
            MonobankApi(self.env, "test-token", "fop-account").statement(date(2026, 10, 15), date(2026, 10, 16))
        self.assertEqual(
            calls[0]["url"], "https://api.monobank.ua/personal/statement/fop-account/1792011600/1792184399"
        )
        self.assertEqual(calls[0]["headers"], {"X-Token": "test-token"})

    def test_refusals_are_readable(self):
        api = MonobankApi(self.env, "test-token")
        with (
            fake_monobank({"errorDescription": "Unknown 'X-Token'"}, 403),
            self.assertRaisesRegex(UserError, "X-Token"),
        ):
            api.statement(date(2026, 10, 15), date(2026, 10, 15))
        with fake_monobank({"errorDescription": "Too many requests"}, 429), self.assertRaisesRegex(UserError, "хвилин"):
            api.statement(date(2026, 10, 15), date(2026, 10, 15))

    def test_a_full_answer_asks_for_a_shorter_period(self):
        rows = [dict(INCOMING, id=f"mono-{i}") for i in range(500)]
        with fake_monobank(rows), self.assertRaisesRegex(UserError, "500"):
            MonobankApi(self.env, "test-token").statement(date(2026, 10, 1), date(2026, 10, 31))

    def test_a_monobank_journal_imports_its_rows(self):
        journal = self.env["account.journal"].create(
            {"name": "monobank ФОП", "type": "bank", "code": "MONO", "newerp_bank_source": "monobank",
             "newerp_mono_token": "test-token", "newerp_mono_account": "fop-account"}
        )  # fmt: skip
        with fake_monobank(json.loads(json.dumps([INCOMING]))):
            result = self.env["newerp.bank.import"].import_statements(journal, date(2026, 10, 15), date(2026, 10, 15))
        self.assertEqual(result["added"], 1)
        line = self.env["account.bank.statement.line"].search([("newerp_bank_ref", "=", "mono-2")])
        self.assertEqual((line.amount, line.partner_name, line.date), (1500.0, "Іваненко Ірина", date(2026, 10, 15)))
