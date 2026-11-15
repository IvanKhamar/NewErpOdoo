from datetime import timedelta

from odoo import fields, models

from ..models.account_bank_statement_line import notification


class BankImportWizard(models.TransientModel):
    _name = "newerp.bank.import.wizard"
    _description = "NewErp: load a bank statement"

    journal_ids = fields.Many2many(
        "account.journal",
        string="Рахунки",
        domain=[("type", "=", "bank"), ("newerp_bank_source", "!=", False)],
        help="Порожньо: усі рахунки з налаштованою випискою.",
    )
    date_from = fields.Date(
        "З", required=True, default=lambda self: fields.Date.context_today(self) - timedelta(days=1)
    )
    date_to = fields.Date("По", required=True, default=fields.Date.context_today)

    def action_import(self):
        self.ensure_one()
        self.env["account.bank.statement.line"]._newerp_check_access()
        journals = self.journal_ids.sudo() or None
        result = self.env["newerp.bank.import"].import_statements(journals, self.date_from, self.date_to)
        return notification(
            self.env._("Отримано рядків: %(fetched)s, нових: %(added)s, прив'язано до замовлень: %(linked)s.", **result)
        )
