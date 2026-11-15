import logging
from datetime import timedelta

from odoo import api, fields, models
from odoo.exceptions import UserError

_logger = logging.getLogger(__name__)

MAX_IMPORT_DAYS = 31


class BankImport(models.AbstractModel):
    """Loads the banks' statements into bank statement lines and matches the new incoming payments to orders."""

    _name = "newerp.bank.import"
    _description = "NewErp: bank statement import"

    @api.model
    def import_statements(self, journals=None, date_from=None, date_to=None):
        """Rows of the period (by default yesterday and today) for each journal with a bank source. All rows go in,
        incoming and outgoing, so the journal's balance is right; a row already loaded (the same bank id in the
        journal) is skipped, so importing again is safe. Returns the counts."""
        date_to = date_to or fields.Date.context_today(self)
        date_from = date_from or date_to - timedelta(days=1)
        if date_from > date_to:
            raise UserError(self.env._("Початок періоду пізніше за кінець."))
        if (date_to - date_from).days > MAX_IMPORT_DAYS:
            raise UserError(self.env._("Завантажувати можна не більше ніж %(days)s днів за раз.", days=MAX_IMPORT_DAYS))
        if journals is None:
            journals = self._bank_journals()
        Line = self.env["account.bank.statement.line"].sudo()
        result = {"fetched": 0, "added": 0, "linked": 0}
        added = Line.browse()
        for journal in journals:
            rows = [row for row in journal._newerp_fetch_statement(date_from, date_to) if row.amount]
            result["fetched"] += len(rows)
            known = set(
                Line.search([("journal_id", "=", journal.id), ("newerp_bank_ref", "in", [r.ref for r in rows])]).mapped(
                    "newerp_bank_ref"
                )
            )
            new = {}
            for row in rows:
                if row.ref not in known:
                    new.setdefault(row.ref, row)
            added |= Line.create([_line_values(journal, row) for row in new.values()])
        result["added"] = len(added)
        result["linked"] = len(added._newerp_auto_match())
        return result

    @api.model
    def _bank_journals(self):
        journals = (
            self.env["account.journal"].sudo().search([("type", "=", "bank"), ("newerp_bank_source", "!=", False)])
        )
        return journals.filtered(lambda journal: journal._newerp_has_bank_keys())

    @api.model
    def _cron_import(self):
        """Each journal on its own: a bank that does not answer does not stop the others."""
        for journal in self._bank_journals():
            try:
                with self.env.cr.savepoint():
                    result = self.import_statements(journal)
                _logger.info("Bank statement %s: %s", journal.name, result)
            except UserError as error:
                _logger.warning("Bank statement %s failed: %s", journal.name, error)


def _line_values(journal, row):
    return {
        "journal_id": journal.id,
        "date": row.date,
        "amount": row.amount,
        "payment_ref": row.purpose or row.payer or "/",
        "partner_name": row.payer or False,
        "account_number": row.payer_account or False,
        "transaction_details": row.details or False,
        "newerp_bank_ref": row.ref,
        "newerp_bank_time": row.time or False,
    }
