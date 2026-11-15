import re

from odoo import fields, models

from .monobank_api import MonobankApi
from .privatbank_api import PrivatBankApi


def _iban(text):
    return re.sub(r"\s", "", text or "").upper()


class AccountJournal(models.Model):
    """A bank journal is one account of the shop. With a source and its keys, its statement comes from the bank."""

    _inherit = "account.journal"

    newerp_bank_source = fields.Selection([("privatbank", "ПриватБанк"), ("monobank", "monobank")], "Виписка з банку")
    newerp_privat_client_id = fields.Char("ПриватБанк: id Автоклієнта", groups="base.group_system", copy=False)
    newerp_privat_token = fields.Char("ПриватБанк: токен Автоклієнта", groups="base.group_system", copy=False)
    newerp_mono_token = fields.Char("monobank: токен", groups="base.group_system", copy=False)
    newerp_mono_account = fields.Char(
        "monobank: id рахунку",
        groups="base.group_system",
        copy=False,
        help="Id рахунку з /personal/client-info, наприклад рахунку ФОП. Порожньо: основний рахунок.",
    )

    def _newerp_fetch_statement(self, date_from, date_to):
        """The bank's rows of the period, in one shape for every bank."""
        self.ensure_one()
        sudo = self.sudo()
        if self.newerp_bank_source == "privatbank":
            rows = PrivatBankApi(self.env, sudo.newerp_privat_client_id, sudo.newerp_privat_token).statement(
                date_from, date_to
            )
            # One Autoclient may see several accounts: with the journal's number set, only its rows are kept.
            own = _iban(self.bank_acc_number)
            return [row for row in rows if not own or _iban(row.account) == own]
        if self.newerp_bank_source == "monobank":
            return MonobankApi(self.env, sudo.newerp_mono_token, sudo.newerp_mono_account).statement(date_from, date_to)
        return []

    def _newerp_has_bank_keys(self):
        self.ensure_one()
        sudo = self.sudo()
        if self.newerp_bank_source == "privatbank":
            return bool(sudo.newerp_privat_client_id and sudo.newerp_privat_token)
        if self.newerp_bank_source == "monobank":
            return bool(sudo.newerp_mono_token)
        return False

    def action_newerp_import_statement(self):
        return {
            "type": "ir.actions.act_window",
            "res_model": "newerp.bank.import.wizard",
            "view_mode": "form",
            "target": "new",
            "context": {"default_journal_ids": self.ids},
        }
