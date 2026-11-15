from datetime import date

from odoo.addons.newerp_bank_ua.models.privatbank_api import PrivatBankApi, parse_statement
from odoo.exceptions import UserError
from odoo.tests import TransactionCase, tagged

from .common import ACCOUNT, STATEMENT, fake_privatbank


@tagged("post_install", "-at_install")
class TestPrivatBankApi(TransactionCase):
    """The client without a network: requests.get answers with the documented JSON."""

    def test_the_statement_reads_incoming_and_debit(self):
        first, second = parse_statement(self.env, STATEMENT)
        self.assertEqual((first.ref, first.account, first.amount), ("tx-1", ACCOUNT, 1500.0))
        self.assertEqual((first.date, first.time), (date(2026, 10, 15), "14:05"))
        self.assertEqual(
            (first.purpose, first.payer, first.payer_account), ("Оплата зам. 2045", "Іваненко Ірина", "UA11")
        )
        self.assertEqual(first.details["payer_bank_code"], "305299")
        self.assertEqual(second.amount, -200.0)  # a debit goes out

    def test_it_sends_the_id_and_token_headers_and_reads_windows_1251(self):
        with fake_privatbank(STATEMENT, encoding="cp1251") as calls:
            rows = PrivatBankApi(self.env, "client-id", "test-token").statement(date(2026, 10, 15), date(2026, 10, 16))
        self.assertEqual(rows[0].purpose, "Оплата зам. 2045")
        self.assertEqual(calls[0]["url"], "https://acp.privatbank.ua/api/proxy/transactions")
        self.assertEqual(calls[0]["params"], {"startDate": "15-10-2026", "endDate": "16-10-2026"})
        self.assertEqual(calls[0]["headers"], {"id": "client-id", "token": "test-token"})

    def test_an_unknown_answer_or_a_refusal_is_a_readable_error(self):
        with self.assertRaises(UserError):
            parse_statement(self.env, '{"error": "Unauthorized"}')
        with fake_privatbank('{"error": "Unauthorized"}', status_code=401), self.assertRaisesRegex(UserError, "401"):
            PrivatBankApi(self.env, "client-id", "test-token").statement(date(2026, 10, 15), date(2026, 10, 15))

    def test_without_keys_there_is_nothing_to_ask(self):
        with self.assertRaises(UserError):
            PrivatBankApi(self.env, "client-id", "")

    def test_a_journal_with_its_account_number_keeps_only_its_rows(self):
        other = STATEMENT.replace(ACCOUNT, "UA000000000000000000000000002")
        journal = self.env["account.journal"].create(
            {"name": "ПриватБанк", "type": "bank", "code": "PRVT", "newerp_bank_source": "privatbank",
             "newerp_privat_client_id": "client-id", "newerp_privat_token": "test-token"}
        )  # fmt: skip
        with fake_privatbank(other):
            self.assertEqual(len(journal._newerp_fetch_statement(date(2026, 10, 15), date(2026, 10, 15))), 2)
            journal.bank_acc_number = "UA21 3052 9900 0002 6001 0000 0000 1"
            self.assertEqual(journal._newerp_fetch_statement(date(2026, 10, 15), date(2026, 10, 15)), [])
