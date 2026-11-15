import re

from odoo import fields, models

from .privatbank_api import PrivatBankApi


def _iban(text):
    return re.sub(r"\s", "", text or "").upper()


class AccountJournal(models.Model):
    """A bank journal is one account of the shop. With a source and its keys, its statement comes from the bank."""

    _inherit = "account.journal"

    newerp_bank_source = fields.Selection([("privatbank", "ПриватБанк")], "Виписка з банку")
    newerp_privat_client_id = fields.Char("ПриватБанк: id Автоклієнта", groups="base.group_system", copy=False)
    newerp_privat_token = fields.Char("ПриватБанк: токен Автоклієнта", groups="base.group_system", copy=False)

    def _newerp_fetch_statement(self, date_from, date_to):
        """The bank's rows of the period. One Autoclient may see several accounts: with the journal's account
        number set, only that account's rows are kept."""
        self.ensure_one()
        sudo = self.sudo()
        if self.newerp_bank_source == "privatbank":
            rows = PrivatBankApi(self.env, sudo.newerp_privat_client_id, sudo.newerp_privat_token).statement(
                date_from, date_to
            )
        else:
            return []
        own = _iban(self.bank_acc_number)
        return [row for row in rows if not own or _iban(row.account) == own]

    def _newerp_has_bank_keys(self):
        self.ensure_one()
        sudo = self.sudo()
        if self.newerp_bank_source == "privatbank":
            return bool(sudo.newerp_privat_client_id and sudo.newerp_privat_token)
        return False

    def action_newerp_import_statement(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "newerp.bank.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_journal_ids": self.ids},
        }
